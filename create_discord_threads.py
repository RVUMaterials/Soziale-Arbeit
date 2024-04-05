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
    for item in file_tree:
        path_parts = item['path'].split('/')
        if path_parts[0].lower() == 'archive' and len(path_parts) > 1:
            top_level_dir = path_parts[1]
            if top_level_dir not in channels_structure:
                channels_structure[top_level_dir] = {'files': [], 'subdirs': {}}
            if len(path_parts) == 3 and item['type'] == 'blob':
                channels_structure[top_level_dir]['files'].append(item['path'])
            elif len(path_parts) > 3:
                sub_dir_path = '/'.join(path_parts[1:-1])  # Include the top-level dir and any subdirs
                if sub_dir_path not in channels_structure[top_level_dir]['subdirs']:
                    channels_structure[top_level_dir]['subdirs'][sub_dir_path] = []
                channels_structure[top_level_dir]['subdirs'][sub_dir_path].append(path_parts[-1])
    logging.info(f"Channels structure parsed with {len(channels_structure)} top-level directories.")
    return channels_structure

def get_github_file_link(file_path, github_url):
    # Replace 'archive/' with 'Archive/' to match GitHub's case sensitivity
    # Use urllib.parse.quote to encode the URL correctly
    adjusted_path = file_path.replace('archive/', 'Archive/', 1)
    encoded_path = urllib.parse.quote(adjusted_path)
    full_link = f"{github_url}/{encoded_path}"
    return full_link

def build_markdown_structure(channel_content, github_url):
    markdown = ""
    # Files directly under the top-level directory
    for file_path in channel_content['files']:
        file_name = file_path.split('/')[-1]
        file_link = get_github_file_link(file_path, github_url)
        # Ensure links are not embedded
        markdown += f"* [{file_name}](<{file_link}>)\n"

    # Subdirectories and their files
    for subdir_path, files in channel_content['subdirs'].items():
        # For displaying, only use the last segment of the subdir path
        subdir_display_name = subdir_path.split('/')[-1]
        markdown += f"  * **{subdir_display_name}**\n"
        for file_name in files:
            # Construct the full file path including the top-level dir and subdir
            full_file_path = '/'.join(['archive', subdir_path, file_name])
            file_link = get_github_file_link(full_file_path, github_url)
            markdown += f"    * [{file_name}](<{file_link}>)\n"
    return markdown

async def send_large_message(channel, message):
    max_length = 2000
    while message:
        split_point = message.rfind('\n', 0, max_length) + 1
        if split_point == 0:
            split_point = max_length
        part, message = message[:split_point], message[split_point:]
        await channel.send(part)

async def create_discord_structure(file_tree, guild, github_url):
    archive_category = discord.utils.get(guild.categories, name="archive")
    if not archive_category:
        archive_category = await guild.create_category("archive")
        logging.info('Created "archive" category.')
    else:
        logging.info('"archive" category already exists.')

    channels_structure = parse_tree_for_channels([item for item in file_tree['tree'] if item['path'].lower().startswith('archive/')])
    for channel_name, content in channels_structure.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name, category=archive_category)
        if not channel:
            channel = await guild.create_text_channel(channel_name, category=archive_category)
            logging.info(f'Created channel: {channel_name}')
        else:
            logging.info(f'Channel "{channel_name}" already exists.')
        markdown_message = build_markdown_structure(content, github_url)
        logging.info(f'Sending markdown message for "{channel_name}"...')
        await send_large_message(channel, markdown_message)

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
