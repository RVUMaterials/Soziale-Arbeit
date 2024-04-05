import discord
import requests
import os
import urllib.parse
import logging

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

def build_markdown_structure(files, github_url):
    def insert_path(structure, path, link):
        parts = path.split('/')
        current_level = structure
        for part in parts[:-1]:
            if part not in current_level or not isinstance(current_level[part], dict):
                current_level[part] = {}
            current_level = current_level[part]
        current_level[parts[-1]] = link

    def generate_markdown(structure, depth=0):
        markdown = ""
        indent = "  " * depth
        for key, value in sorted(structure.items()):
            if isinstance(value, dict):
                markdown += f"\n{indent}* **{key}**"
                markdown += generate_markdown(value, depth + 1)
            else:
                # Enclose the URL in angle brackets to prevent embeds
                markdown += f"\n{indent}* [{key}](<{value}>)"
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

    # Adjusted to parse the tree for channels
    channels_structure = parse_tree_for_channels(file_tree['tree'])

    for channel_name, channel_content in channels_structure.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name, category=archive_category)
        if not channel:
            channel = await guild.create_text_channel(channel_name, category=archive_category)
            logging.info(f'Created channel: {channel_name}')
        
        # Build and send the markdown message for each channel
        markdown_message = build_markdown_structure(channel_content, github_url)
        # The sending logic with character limit handling remains the same

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
