import pandas
import json
import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from config import invocation
from datetime import datetime
import asyncio
bot = commands.Bot(command_prefix=invocation)

load_dotenv()
discord_token = os.getenv("DISCORD_TOKEN")

datetime_string_format = "%m/%d/%y %H:%M:%S"

# async def hourly_update():
#     await bot.wait_until_ready()
#     while True:
#         ctx = await fetch_context_from_channel_with_pin(730194660617617561) #this is the #scheduler channel id for the server dev_bot_testing
#         await asyncio.sleep(3600)


async def fetch_context_from_channel_with_pin(channel_id):
    channel = bot.get_channel(channel_id)
    async for message in channel.history(limit=200):
        if message.pinned:
            ctx = await bot.get_context(message)
            return ctx


@bot.event
async def on_ready():
    print("Connecting to Guilds...")
    guildsDisplay = {
        "Guild Name": [],
        "Total Memebers": [],
        "Members Online": [],
    }

    for guild in bot.guilds:
        membersOnline = 0
        guildsDisplay["Guild Name"].append(guild.name)
        guildsDisplay["Total Memebers"].append(len(guild.members))
        for member in guild.members:
            if member.status.name == "online":
                membersOnline += 1
        guildsDisplay["Members Online"].append(membersOnline)

    df = pandas.DataFrame(guildsDisplay)

    print(df.to_string(index=False))


@bot.command(help="Testing")
async def create_event(ctx):


bot.run(discord_token)
