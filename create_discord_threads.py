import discord
import requests
import os
import urllib.parse
import logging
from collections import defaultdict

# Setup basic logging
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.all()
client = discord.Client(intents=intents)

def get_github_file_tree(owner, repo, branch):
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1'
    response = requests.get(url)
    if response.status_code == 200:
        logging.info("Successfully fetched file tree from GitHub.")
        return response.json()
    else:
        logging.error(f"Failed to fetch file tree from GitHub: {response.status_code}")
        return None

def build_markdown_structure(files):
    def insert_path(structure, path, link):
        parts = path.split('/')
        for part in parts[:-1]:
            structure = structure.setdefault(part, {})
        structure[parts[-1]] = link

    def generate_markdown(structure, depth=0):
        markdown = ""
        indent = "  " * depth
        for key, value in structure.items():
            if isinstance(value, dict):
                markdown += f"\n{indent}* **{key}**"
                markdown += generate_markdown(value, depth + 1)
            else:
                markdown += f"\n{indent}* [{key}]({value})"
        return markdown

    structure = {}
    for file in files:
        path = file['path']
        if path.lower().startswith('archive/'):
            file_name = path.split('/')[-1]
            encoded_path = urllib.parse.quote(path)
            file_link = f"{github_url}/{encoded_path}"
            insert_path(structure, path[len('archive/'):], file_link)

    return generate_markdown(structure)

async def create_discord_structure(file_tree, guild, github_url):
    archive_category = discord.utils.get(guild.categories, name="archive")
    if not archive_category:
        archive_category = await guild.create_category("archive")
        logging.info('Created "archive" category.')
    else:
        logging.info('"archive" category already exists.')

    archive_items = [item for item in file_tree['tree'] if item['path'].lower().startswith('archive/')]

    markdown_message = build_markdown_structure(archive_items)

    # Split markdown_message by top-level folders to send separate messages for each
    folder_messages = markdown_message.strip().split("\n\n* **")
    for message in folder_messages:
        if message.startswith("* **"):
            channel_name = message.split("\n", 1)[0][4:-2]  # Extract channel name
        else:
            channel_name, message = message.split("\n", 1)
            message = "* **" + message
        channel = discord.utils.get(guild.text_channels, name=channel_name, category=archive_category)
        if not channel:
            channel = await guild.create_text_channel(channel_name, category=archive_category)
            logging.info(f'Created channel: {channel_name}')
        await channel.send(message)

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    repo_details = os.getenv('GITHUB_REPOSITORY').split('/')
    GITHUB_OWNER = repo_details[0]
    GITHUB_REPO = repo_details[1]
    GITHUB_BRANCH = os.getenv('GITHUB_REF').split('/')[-1]
    GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/blob/{GITHUB_BRANCH}"
    file_tree = get_github_file_tree(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)
    if not file_tree:
        logging.error('Failed to obtain file tree. Exiting...')
        return

    guild_id = 1224348075858853918  # Replace with your Discord server (guild) ID
    guild = client.get_guild(guild_id)
    if not guild:
        logging.error('Failed to find guild with the provided ID. Exiting...')
        return

    logging.info(f"Found guild: {guild.name}")
    await create_discord_structure(file_tree, guild, GITHUB_URL)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)
else:
    logging.error('Discord token not found. Please ensure DISCORD_TOKEN is set in your environment variables.')


