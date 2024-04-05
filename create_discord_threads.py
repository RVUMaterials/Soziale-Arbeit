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
        # Split the path to analyze its structure
        path_parts = item['path'].split('/')
        # Looking for items directly under "archive/" directory
        if path_parts[0].lower() == 'archive' and len(path_parts) > 1:
            top_level_dir = path_parts[1]
            # Initialize the structure for each top-level directory
            if top_level_dir not in channels_structure:
                channels_structure[top_level_dir] = {'files': [], 'subdirs': {}}
            # Handling files within top-level directories
            if len(path_parts) == 3 and item['type'] == 'blob':  # Directly under a top-level directory
                channels_structure[top_level_dir]['files'].append(item['path'])
            elif len(path_parts) > 3:  # Nested in subdirectories
                sub_dir = '/'.join(path_parts[2:-1])  # Exclude the file name
                if sub_dir not in channels_structure[top_level_dir]['subdirs']:
                    channels_structure[top_level_dir]['subdirs'][sub_dir] = []
                channels_structure[top_level_dir]['subdirs'][sub_dir].append(path_parts[-1])

    logging.info(f"Channels structure parsed with {len(channels_structure)} top-level directories.")
    return channels_structure

def build_markdown_structure(channel_content, github_url):
    markdown = ""
    # Iterate through files directly under the top-level directory
    for file_path in channel_content['files']:
        file_name = file_path.split('/')[-1]
        # Assuming the first part of the file_path is always "Archive",
        # and the second part is the top-level directory (channel name)
        # Adjust the path to ensure it starts correctly and includes the channel name
        adjusted_path = "/".join(file_path.split('/')[1:])  # Skip the initial 'archive/' part
        encoded_path = urllib.parse.quote(adjusted_path)
        file_link = f"{github_url}/{encoded_path}"
        markdown += f"* [{file_name}](<{file_link}>)\n"

    # Iterate through subdirectories and their files
    for subdir, files in channel_content['subdirs'].items():
        # Subdirectory names are already included in their file paths
        subdir_display_name = " / ".join(subdir.split('/'))
        markdown += f"  * **{subdir_display_name}**\n"
        for file_name in files:
            # Include the full path for files in subdirectories
            full_file_path = f"archive/{subdir}/{file_name}"
            adjusted_subdir_path = "/".join(full_file_path.split('/')[1:])  # Adjust path
            encoded_file_path = urllib.parse.quote(adjusted_subdir_path)
            file_link = f"{github_url}/{encoded_file_path}"
            markdown += f"    * [{file_name}](<{file_link}>)\n"
    
    return markdown


    # Handle subdirectories and their files
    for subdir, files in channel_content['subdirs'].items():
        # Subdirectory formatting for display
        formatted_subdir = " / ".join(subdir.split('/'))
        markdown += f"  * **{formatted_subdir}**\n"
        for file_name in files:
            # For each file in a subdirectory, construct the full path correctly
            full_path = "/".join(['Archive'] + [subdir] + [file_name])
            encoded_file_path = urllib.parse.quote(full_path)
            file_link = f"{github_url}/{encoded_file_path}"
            markdown += f"    * [{file_name}](<{file_link}>)\n"
    
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
        
        markdown_message = build_markdown_structure(channel_content, github_url)
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
