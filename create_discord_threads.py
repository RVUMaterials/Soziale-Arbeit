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

async def create_discord_structure(file_tree, guild, github_url, category_name="Archive", parent_channel=None, indentation=0):
    # Check if "Archive" category exists, if not create it
    archive_category = discord.utils.get(guild.categories, name=category_name)
    if not archive_category:
        archive_category = await guild.create_category(category_name)
        logging.info(f'Created "{category_name}" category.')
    
    # Process only items within the "Archive" directory
    for item in file_tree['tree']:
        path_segments = item['path'].split('/')
        if len(path_segments) < 2 or item['type'] != 'blob' or path_segments[0].lower() != 'archive':  # Skip non-archive items
            continue
        
        folder_name = path_segments[1]
        if folder_name.startswith('.'):  # Skip hidden folders
            continue
        
        # Create channel for the folder
        folder_channel = discord.utils.get(guild.text_channels, name=folder_name, category=archive_category)
        if not folder_channel:
            folder_channel = await guild.create_text_channel(folder_name, category=archive_category)
            logging.info(f'Created channel: {folder_name}')
        
        # Construct markdown message for folder structure
        markdown_message = "```markdown\n"
        markdown_message += f"{indentation * '  '}- **{folder_name}**\n"
        
        # Process subfolders recursively
        subfolder_items = [subitem for subitem in file_tree['tree'] if subitem['path'].startswith(f'archive/{folder_name}/')]
        if subfolder_items:
            subfolder_structure = await create_discord_structure(
                {'tree': subfolder_items}, guild, github_url, category_name=None, 
                parent_channel=folder_channel, indentation=indentation + 1
            )
            markdown_message += subfolder_structure
        
        # Process files in the folder
        files_in_folder = [file_item for file_item in file_tree['tree'] if file_item['path'].startswith(f'archive/{folder_name}/') and file_item['type'] == 'blob']
        for file_item in files_in_folder:
            file_name = file_item['path'].split('/')[-1]
            encoded_file_path = urllib.parse.quote(file_item['path'])
            file_link = f"{github_url}/{encoded_file_path}"
            markdown_message += f"{(indentation + 1) * '  '}- [{file_name}]({file_link})\n"
        
        markdown_message += "```"
        
        # Send markdown message to channel
        if parent_channel:
            await parent_channel.send(markdown_message)
        else:
            await folder_channel.send(markdown_message)
    
    # Return the markdown message for subfolders
    return markdown_message

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


