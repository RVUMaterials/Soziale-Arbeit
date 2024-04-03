import os
import sys
import requests
import discord

# Define Discord intents
intents = discord.Intents.default()
intents.messages = True  # Enable message events

# Discord client
client = discord.Client(intents=intents)

# Function to fetch file tree from GitHub
def get_github_file_tree(owner, repo, branch):
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch file tree from GitHub: {response.status_code}")
        return None

# Function to create Discord threads based on file tree
async def create_discord_threads(file_tree, channel, github_url):
    for item in file_tree['tree']:
        if item['type'] == 'tree':
            folder_name = item['path']
            folder_thread = await channel.create_thread(name=folder_name, auto_archive_duration=60, type=discord.ChannelType.public)
            folder_content = ''
            for sub_item in file_tree['tree']:
                if sub_item['type'] == 'blob' and sub_item['path'].startswith(folder_name):
                    file_name = sub_item['path'].split('/')[-1]
                    file_link = f"{github_url}/{sub_item['path']}"
                    if len(folder_content) + len(file_name) + len(file_link) + 3 > 2000:  # Check if adding the file exceeds the limit
                        await folder_thread.send(folder_content)
                        folder_content = ''
                    folder_content += f"- [{file_name}]({file_link})\n"
            if folder_content:
                await folder_thread.send(folder_content)


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

    # Fetch repository details
    repo_details = os.getenv('GITHUB_REPOSITORY').split('/')
    GITHUB_OWNER = repo_details[0]
    GITHUB_REPO = repo_details[1]
    GITHUB_BRANCH = os.getenv('GITHUB_REF').split('/')[-1]

    # Fetch file tree from GitHub
    file_tree = get_github_file_tree(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)

    # Fetch the desired channel
    channel_id = 1224349080356917269  # Replace with your Discord channel ID
    channel = client.get_channel(channel_id)

    # Create Discord threads based on file tree
    await create_discord_threads(file_tree, channel)

# Run the Discord bot
client.run(sys.argv[1])
