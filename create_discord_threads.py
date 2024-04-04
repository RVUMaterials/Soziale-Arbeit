import os
import sys
import requests
import discord
import urllib.parse

# Define Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

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

# Helper function to ensure channels and threads creation
async def ensure_channel_and_thread(guild, category_id, channel_name, thread_name):
    channel = discord.utils.get(guild.channels, name=channel_name, category_id=category_id)
    if not channel:
        channel = await guild.create_text_channel(name=channel_name, category=discord.Object(id=category_id))
    
    thread = discord.utils.get(channel.threads, name=thread_name)
    if not thread:
        thread = await channel.create_thread(name=thread_name, auto_archive_duration=60)
    
    return thread

# Function to post file links in the thread
async def post_file_links(file_tree, guild, category_id, github_url):
    for item in file_tree['tree']:
        if item['type'] == 'blob':  # If it's a file
            path_elements = item['path'].split('/')
            if path_elements[0] == "Archive" and len(path_elements) > 2:  # Ensure structure matches Archive/Semester X/Hausaufgaben
                channel_name = path_elements[1]  # Semester X
                thread_name = path_elements[2]  # Hausaufgaben
                thread = await ensure_channel_and_thread(guild, category_id, channel_name, thread_name)
                
                file_name = path_elements[-1]
                file_path = urllib.parse.quote('/'.join(path_elements))  # Encode the file path for URL
                file_link = f"{github_url}/{file_path}"
                await thread.send(f"- [{file_name}]({file_link})")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    GITHUB_OWNER = 'RWUMaterials'
    GITHUB_REPO = 'Soziale-Arbeit'
    GITHUB_BRANCH = 'main'  # Adjust if your branch name is different
    ARCHIVE_CATEGORY_ID = 1225256226699477073  # The Discord category ID for ARCHIVE
    GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/blob/{GITHUB_BRANCH}"
    
    guild = client.guilds[0]  # Assumes the bot is in one guild, adjust as needed
    file_tree = get_github_file_tree(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)
    
    await post_file_links(file_tree, guild, ARCHIVE_CATEGORY_ID, GITHUB_URL)

client.run(sys.argv[1])  # Your bot's token as the first command-line argument
