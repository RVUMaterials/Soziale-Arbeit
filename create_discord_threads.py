import discord
import requests
import os
import sys
import urllib.parse

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_github_file_tree(owner, repo, branch):
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch file tree from GitHub: {response.status_code}")
        return None

async def create_discord_channels_and_threads(file_tree, guild, github_url):
    archive_category = discord.utils.get(guild.categories, name="archive")
    if not archive_category:
        archive_category = await guild.create_category("archive")

    archive_folders = [item for item in file_tree['tree'] if item['path'].startswith('archive/') and item['type'] == 'tree']
    for folder in archive_folders:
        folder_name = folder['path'].split('/')[-1]
        # Check if the channel already exists
        channel = discord.utils.get(guild.text_channels, name=folder_name, category=archive_category)
        if not channel:
            # Create a channel under the "archive" category
            channel = await guild.create_text_channel(folder_name, category=archive_category)
        
        folder_content = ''
        for sub_item in file_tree['tree']:
            if sub_item['type'] == 'blob' and sub_item['path'].startswith(folder['path']):
                file_name = sub_item['path'].split('/')[-1]
                encoded_file_path = urllib.parse.quote(sub_item['path'])  # URL encode the file path
                file_link = f"{github_url}/{encoded_file_path}"
                new_entry = f"- [{file_name}]({file_link})\n"
                if len(folder_content + new_entry) > 2000:  # Check if adding the file exceeds the limit
                    await channel.send(folder_content)
                    folder_content = new_entry  # Start with the new entry that didn't fit
                else:
                    folder_content += new_entry
        if folder_content:
            await channel.send(folder_content)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

    # Fetch repository details
    repo_details = os.getenv('GITHUB_REPOSITORY').split('/')
    GITHUB_OWNER = repo_details[0]
    GITHUB_REPO = repo_details[1]
    GITHUB_BRANCH = os.getenv('GITHUB_REF').split('/')[-1]

    # Construct GitHub URL
    GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/blob/{GITHUB_BRANCH}"

    # Fetch file tree from GitHub
    file_tree = get_github_file_tree(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)

    # Find the guild by ID or name
    guild_id = 1224348075858853918  # Replace with your Discord server (guild) ID
    guild = client.get_guild(guild_id)

    # Create Discord channels and threads based on file tree
    await create_discord_channels_and_threads(file_tree, guild, GITHUB_URL)

# Run the Discord bot
client.run(sys.argv[1])
