import discord
import requests
import os
import sys
import urllib.parse
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
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

async def create_discord_channels_and_threads(file_tree, guild, github_url):
    archive_category = discord.utils.get(guild.categories, name="archive")
    if not archive_category:
        archive_category = await guild.create_category("archive")
        logging.info('Created "archive" category.')
    else:
        logging.info('"archive" category already exists.')

    archive_folders = [item for item in file_tree['tree'] if item['path'].startswith('Archive/') and item['type'] == 'tree']
    if not archive_folders:
        logging.info('No folders found under "archive" in the GitHub repository.')
    else:
        logging.info(f"Found {len(archive_folders)} folders under 'archive'. Processing...")

    for folder in archive_folders:
        folder_name = folder['path'].split('/')[-1]
        channel = discord.utils.get(guild.text_channels, name=folder_name, category=archive_category)
        if not channel:
            channel = await guild.create_text_channel(folder_name, category=archive_category)
            logging.info(f'Created channel: {folder_name}')
        else:
            logging.info(f'Channel "{folder_name}" already exists.')

        folder_content = ''
        for sub_item in file_tree['tree']:
            if sub_item['type'] == 'blob' and sub_item['path'].startswith(folder['path']):
                file_name = sub_item['path'].split('/')[-1]
                encoded_file_path = urllib.parse.quote(sub_item['path'])
                file_link = f"{github_url}/{encoded_file_path}"
                new_entry = f"- [{file_name}]({file_link})\n"
                if len(folder_content + new_entry) > 2000:
                    await channel.send(folder_content)
                    folder_content = new_entry
                else:
                    folder_content += new_entry
        if folder_content:
            await channel.send(folder_content)
            logging.info(f'Posted content to channel: {folder_name}')

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

    guild_id = 1224348075858853918  # Your Discord server (guild) ID
    guild = client.get_guild(guild_id)
    if not guild:
        logging.error('Failed to find guild with the provided ID. Exiting...')
        return
    else:
        logging.info(f"Found guild: {guild.name}")

    await create_discord_channels_and_threads(file_tree, guild, GITHUB_URL)

# Retrieve the Discord bot token from GitHub Secrets mapped to environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)
else:
    logging.error('Discord token not found. Please ensure DISCORD_TOKEN is set in your environment variables.')
