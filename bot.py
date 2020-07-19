import re
import pandas
import json
import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from config import invocation, datetime_string_format
from datetime import datetime, timedelta
import asyncio
from time import sleep
bot = commands.Bot(command_prefix=invocation)

load_dotenv()
discord_token = os.getenv("DISCORD_TOKEN")

ACCEPTED = "✅"
TENTATIVE = "❔"
REJECTED = "❌"
ALARM_CLOCK = "https://img.icons8.com/doodle/48/000000/alarm-clock.png"
GREEN_CHECK = "https://img.icons8.com/flat_round/64/000000/checkmark.png"


async def fetch_context_from_channel_with_pin(channel_id):
    channel = bot.get_channel(channel_id)
    async for message in channel.history(limit=200):
        if message.pinned:
            ctx = await bot.get_context(message)
            return ctx


async def fetch_context_from_payload(payload):
    channel = await bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
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


async def send_notification(message: discord.Message, event_datetime: datetime):
    ctx = await bot.get_context(message)
    for reaction in ctx.message.reactions:
        if reaction.emoji in [ACCEPTED, TENTATIVE]:
            users_that_reacted = await reaction.users().flatten()
            for user in users_that_reacted[1:]:
                await user.send(
                    content=f"Howdy! You have the event {message.embeds[0].title} at {event_datetime.strftime(datetime_string_format +' (%A)')}!")


async def event_heartbeat():
    await bot.wait_until_ready()
    while True:
        await check_for_events()
        await asyncio.sleep(15)


async def fetch_event_datetime(message):
    if message.author == bot.user and len(message.embeds) > 0 and not message.embeds[0].footer.icon_url == GREEN_CHECK:
        for field in message.embeds[0].fields:
            if field.name == "WHEN":
                datetime_str = re.sub(
                    r"\s\([A-Za-z]*\)$", "", field.value)
                event_datetime = datetime.strptime(
                    datetime_str, datetime_string_format)
                return event_datetime


async def check_for_events():
    for guild in bot.guilds:
        for category_channel in guild.channels:
            if hasattr(category_channel, "text_channels"):
                for text_channel in category_channel.text_channels:
                    async for message in text_channel.history(limit=200):
                        event_datetime = await fetch_event_datetime(message)
                        if event_datetime is not None:
                            if event_datetime > datetime.now():
                                difference = event_datetime - datetime.now()
                                if difference.days == 0 and (difference.seconds > 845 and difference.seconds < 915 and not message.embeds[0].footer.icon_url == ALARM_CLOCK):
                                    await send_notification(message, event_datetime)
                                    updated_embed = message.embeds[0]
                                    updated_embed.set_footer(
                                        text=updated_embed.footer.text, icon_url=ALARM_CLOCK)
                                    await message.edit(embed=updated_embed)
                                elif difference.days == 0 and (difference.seconds < 20):
                                    await send_notification(message, event_datetime)
                                    updated_embed = message.embeds[0]
                                    updated_embed.set_footer(
                                        text=updated_embed.footer.text, icon_url=GREEN_CHECK)
                                    await message.edit(embed=updated_embed)


@bot.command()
async def send_notice(ctx, message_url):
    event_message_id = re.search(r"([0-9]*)$", message_url).groups()[0]
    event_message = await ctx.fetch_message(event_message_id)
    event_datetime = await fetch_event_datetime(event_message)
    if event_datetime is not None:
        await send_notification(event_message, event_datetime)
    else:
        ctx.send("This doesn't seem to be a future event.")


@bot.command()
async def create_event(ctx):
    def check(m):
        return m.channel == ctx.channel and m.author == ctx.author
    name_req = await ctx.send(content="What would you like to name your event?")
    name_resp = await bot.wait_for('message', check=check)
    desc_req = await ctx.send(content=f"What can you tell me about >>>{name_resp.content}<<<?")
    desc_resp = await bot.wait_for('message', check=check)

    def datetime_check(m):
        pattern = re.compile(
            r"[0-9]{2}\/[0-9]{2}\/[0-9]{2}\s[0-9]{2}\:[0-9]{2}")
        if pattern.match(m.content):
            return m.channel == ctx.channel and m.author == ctx.author
    datetime_req = await ctx.send(content=f"When will >>>{name_resp.content}<<< be happening?")
    datetime_resp = await bot.wait_for('message', check=datetime_check)
    await create_event_message(ctx, name_resp.content, desc_resp.content, datetime_resp.content)
    for message in [datetime_resp, datetime_req, desc_resp, desc_req, name_resp, name_req, ctx.message]:
        await message.delete()


async def create_event_message(ctx, name, description, event_datetime):
    event_datetime = datetime.strptime(
        event_datetime, datetime_string_format)
    displayed_time = event_datetime.strftime(f'{datetime_string_format} (%A)')
    embed = discord.Embed(
        title=name, description=description, color=0x00ff00)
    embed.add_field(name="WHEN", value=displayed_time, inline=False)
    embed.add_field(name="Are you joining?", value="""\
Yes? Hit that ✅\n\
Maybe? Hit that ❔\n\
No? Hit that ❌""")
    embed.set_footer(
        text="You will receive a notification when the event will be starting soon if you hit ✅ or ❔.")
    message = await ctx.send(content="@everyone", embed=embed)
    await message.add_reaction(ACCEPTED)
    await message.add_reaction(TENTATIVE)
    await message.add_reaction(REJECTED)


@bot.listen()
async def on_raw_reaction_add(payload):
    ctx = await fetch_context_from_payload(payload)
    if ctx.author == ctx.me and not payload.member == ctx.me:
        if payload.emoji.name in [ACCEPTED, TENTATIVE, REJECTED]:
            for reaction in ctx.message.reactions:
                users_that_reacted = await reaction.users().flatten()
                if payload.member in users_that_reacted and not payload.emoji.name == reaction.emoji:
                    await reaction.remove(payload.member)
        else:
            for reaction in ctx.message.reactions:
                if payload.emoji.name == reaction.emoji:
                    await reaction.remove(payload.member)

bot.loop.create_task(event_heartbeat())
bot.run(discord_token)
