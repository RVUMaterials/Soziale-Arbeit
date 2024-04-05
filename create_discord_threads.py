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

def parse_tree_for_channels(file_tree):
    channels_structure = {}
    # First, identify all directories within 'archive/'
    for item in file_tree:
        if item['path'].startswith('archive/') and item['type'] == 'tree':
            dir_path_parts = item['path'].split('/')
            if len(dir_path_parts) == 2:  # Directly under 'archive/'
                dir_name = dir_path_parts[1]
                if dir_name not in channels_structure:
                    channels_structure[dir_name] = {'files': [], 'subdirs': {}}
    
    # Next, process all files, assigning them to their respective directories
    for item in file_tree:
        if item['path'].startswith('archive/') and item['type'] == 'blob':
            file_path_parts = item['path'].split('/')
            if len(file_path_parts) > 2:  # Inside a subdirectory under 'archive/'
                top_level_dir = file_path_parts[1]
                sub_dir_path = '/'.join(file_path_parts[2:-1])  # Path without the filename and 'archive/'
                file_name = file_path_parts[-1]
                if top_level_dir in channels_structure:
                    if sub_dir_path not in channels_structure[top_level_dir]['subdirs']:
                        channels_structure[top_level_dir]['subdirs'][sub_dir_path] = []
                    channels_structure[top_level_dir]['subdirs'][sub_dir_path].append(file_name)
                else:
                    # If the file does not belong to a recognized top-level directory (unlikely due to the first loop, but just in case)
                    logging.warning(f"File {item['path']} does not belong to a recognized top-level directory.")
    
    logging.info(f"Channels structure parsed with {len(channels_structure.keys())} top-level directories.")
    return channels_structure

def build_markdown_structure(files, github_url):
    markdown = ""
    for file_path in files:
        file_name = file_path.split('/')[-1]
        encoded_path = urllib.parse.quote(file_path)
        file_link = f"{github_url}/{encoded_path}"
        markdown += f"* [{file_name}](<{file_link}>)\n"
    return markdown

async def create_discord_structure(file_tree, guild, github_url):
    archive_category = discord.utils.get(guild.categories, name="archive")
    if not archive_category:
        archive_category = await guild.create_category("archive")
        logging.info('Created "archive" category.')
    else:
        logging.info('"archive" category already exists.')

    channels_structure = parse_tree_for_channels([item for item in file_tree['tree'] if item['path'].lower().startswith('archive/')])

    for channel_name, files in channels_structure.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name, category=archive_category)
        if not channel:
            channel = await guild.create_text_channel(channel_name, category=archive_category)
            logging.info(f'Created channel: {channel_name}')
        else:
            logging.info(f'Channel "{channel_name}" already exists.')
        
        markdown_message = build_markdown_structure(files, github_url)
        logging.info(f'Sending markdown message for "{channel_name}" with length {len(markdown_message)}.')
        if len(markdown_message) > 2000:
            while len(markdown_message) > 0:
                part = markdown_message[:2000]
                newline_pos = part.rfind('\n')
                if newline_pos != -1 and len(markdown_message) > 2000:
                    part = part[:newline_pos]
                await channel.send(part)
                markdown_message = markdown_message[len(part):]
                logging.info(f'Sent part of markdown message for "{channel_name}".')
        else:
            await channel.send(markdown_message)
            logging.info(f'Complete markdown message sent for "{channel_name}".')

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

    guild_id = 1224348075858853918
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
