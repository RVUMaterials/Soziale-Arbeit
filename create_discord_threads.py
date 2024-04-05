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

async def create_discord_structure(file_tree, guild, github_url):
    archive_category = discord.utils.get(guild.categories, name="archive")
    if not archive_category:
        archive_category = await guild.create_category("archive")
        logging.info('Created "archive" category.')
    else:
        logging.info('"archive" category already exists.')

    # Create channels and markdown message
    processed_folders = {}  # Cache of processed folders to avoid duplication
    markdown_message = ""
    for item in file_tree['tree']:
        path_segments = item['path'].split('/')
        if len(path_segments) < 3 or item['type'] != 'blob':  # Skip top-level or non-file items
            continue

        folder_name, file_name = path_segments[1], path_segments[2]
        if folder_name not in processed_folders:
            folder_channel = discord.utils.get(guild.text_channels, name=folder_name, category=archive_category)
            if not folder_channel:
                folder_channel = await guild.create_text_channel(folder_name, category=archive_category)
                logging.info(f'Created channel: {folder_name}')
            processed_folders[folder_name] = folder_channel
            markdown_message += f"- **{folder_name}**\n"
        else:
            folder_channel = processed_folders[folder_name]

        # Append file link or markdown message
        if len(path_segments) == 3:  # File directly inside the folder
            encoded_file_path = urllib.parse.quote(item['path'])
            file_link = f"{github_url}/{encoded_file_path}"
            markdown_message += f"  - [{file_name}](#{file_name.lower().replace(' ', '-')})\n"
            markdown_message += f"    - [Link]({file_link})\n"
        else:  # Subfolders
            subfolder_name = path_segments[2]
            markdown_message += f"  - **{subfolder_name}**\n"

            if len(path_segments) > 3:  # Nested subfolders
                subfolder_path = ' '.join(path_segments[3:])
                markdown_message += f"    - [{subfolder_path}](#)\n"
            else:  # Subfolder with only links
                markdown_message += f"    - [Google](https://google.com)\n"
                markdown_message += f"    - [GitHub](https://github.com)\n"

    # Send markdown message
    for folder_name, folder_channel in processed_folders.items():
        await folder_channel.send(markdown_message)


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
