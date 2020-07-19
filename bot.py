import re
import json
import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from config import INVOCATION, DATETIME_STRING_FORMAT, GITHUB_REPO
from datetime import datetime, timedelta
import asyncio
from time import sleep
bot = commands.Bot(command_prefix=INVOCATION)

load_dotenv()
discord_token = os.getenv("DISCORD_TOKEN")

ACCEPTED = "✅"
TENTATIVE = "❔"
REJECTED = "❌"
ALARM_CLOCK = "https://img.icons8.com/doodle/48/000000/alarm-clock.png"
GREEN_CHECK = "https://img.icons8.com/flat_round/64/000000/checkmark.png"


async def fetch_context_from_channel_with_pin(channel_id: int):
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


def fetch_timedelta_string(timedelta):
    seconds = int(timedelta.total_seconds())
    periods = [
        ('year',        60*60*24*365),
        ('month',       60*60*24*30),
        ('day',         60*60*24),
        ('hour',        60*60),
        ('minute',      60),
        ('second',      1)
    ]

    strings = []
    for period_name, period_seconds in periods:
        if seconds > period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            has_s = 's' if period_value > 1 else ''
            strings.append("%s %s%s" % (period_value, period_name, has_s))

    return ", ".join(strings)


@bot.event
async def on_ready():
    print("Connected!")
    git_status = discord.Game(GITHUB_REPO)
    await bot.change_presence(activity=git_status)


async def gather_accepted_and_tentative_rsvps(message: discord.Message):
    for reaction in message.reactions:
        if reaction.emoji in [ACCEPTED, TENTATIVE]:
            users_that_reacted = await reaction.users().flatten()
            users_that_reacted.remove(bot.user)
            return users_that_reacted


async def send_notification(message: discord.Message, event_datetime: datetime):
    ctx = await bot.get_context(message)
    time_until_event = event_datetime - datetime.now()
    time_until_event_formatted = fetch_timedelta_string(time_until_event)
    if time_until_event.seconds < 20 and message.embeds[0].footer.text.startswith("Everyone"):
        await ctx.send(
            f"The following event is starting:\n{message.jump_url}\n@everyone")
    elif time_until_event.seconds < 20:
        users_that_reacted = await gather_accepted_and_tentative_rsvps(ctx.message)
        notification_text = f"The following event is starting:\n{message.jump_url}"
        for user in users_that_reacted:
            notification_text += f"\n{user.mention}"
        await ctx.send(content=notification_text)
    elif message.embeds[0].footer.text.startswith("Everyone"):
        await ctx.send(content=f"The following event is starting in {time_until_event_formatted}:\n{message.jump_url}\n@everyone")
    else:
        users_that_reacted = await gather_accepted_and_tentative_rsvps(ctx.message)
        notification_text = f"The following event is starting in {time_until_event_formatted}:\n{message.jump_url}"
        for user in users_that_reacted:
            notification_text += f"\n{user.mention}"
        await ctx.send(content=notification_text)


async def event_heartbeat():
    await bot.wait_until_ready()
    while True:
        await check_for_events()
        await asyncio.sleep(15)


async def fetch_event_datetime(message: discord.Message):
    if message.author == bot.user and len(message.embeds) > 0 and not message.embeds[0].footer.icon_url == GREEN_CHECK:
        for field in message.embeds[0].fields:
            if field.name == "WHEN":
                datetime_str = re.sub(
                    r"\s\([A-Za-z]*\)$", "", field.value)
                event_datetime = datetime.strptime(
                    datetime_str, DATETIME_STRING_FORMAT)
                return event_datetime


async def check_for_events():
    for guild in bot.guilds:
        for category_channel in guild.channels:
            if hasattr(category_channel, "text_channels"):
                for text_channel in category_channel.text_channels:
                    pinned_messages = await text_channel.pins()
                    for pinned_message in pinned_messages:
                        message = await text_channel.fetch_message(pinned_message.id)
                        event_datetime = await fetch_event_datetime(message)
                        if event_datetime is not None:
                            if event_datetime > datetime.now():
                                time_until_event = event_datetime - datetime.now()
                                if time_until_event.days == 0 and (time_until_event.seconds < 915 and not message.embeds[0].footer.icon_url == ALARM_CLOCK):
                                    await send_notification(message, event_datetime)
                                    updated_embed = message.embeds[0]
                                    updated_embed.set_footer(
                                        text=updated_embed.footer.text, icon_url=ALARM_CLOCK)
                                    await message.edit(embed=updated_embed)
                                elif time_until_event.days == 0 and (time_until_event.seconds < 20):
                                    await send_notification(message, event_datetime)
                                    updated_embed = message.embeds[0]
                                    updated_embed.set_footer(
                                        text=updated_embed.footer.text, icon_url=GREEN_CHECK)
                                    await message.edit(embed=updated_embed)
                                    await message.unpin()


@bot.command()
async def send_notice(ctx: commands.Context, message_url: str):
    event_message_id = re.search(r"([0-9]*)$", message_url).groups()[0]
    event_message = await ctx.fetch_message(event_message_id)
    event_datetime = await fetch_event_datetime(event_message)
    if event_datetime is not None:
        await send_notification(event_message, event_datetime)
    else:
        ctx.send("This doesn't seem to be a future event.")


@bot.command()
async def create_event(ctx: commands.Context):
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

    def everyone_check(m):
        return m.content[0].lower() in ["y", "n"] and m.channel == ctx.channel and m.author == ctx.author
    everyone_req = await ctx.send(content="Would you like to send the event notifications to everybody in this channel?(This refers to the notifications right before the events starts and not the creation notification)")
    everyone_resp = await bot.wait_for('message', check=everyone_check)
    if everyone_resp.content[0].lower() == "y":
        notify_everyone = True
    elif everyone_resp.content[0].lower() == "n":
        notify_everyone = False
    await create_event_message(ctx, name_resp.content, desc_resp.content, datetime_resp.content, notify_everyone)
    for message in [everyone_resp, everyone_req, datetime_resp, datetime_req, desc_resp, desc_req, name_resp, name_req, ctx.message]:
        await message.delete()


async def create_event_message(ctx: commands.Context, name: str, description: str, event_datetime: datetime, notify_everyone: bool):
    event_datetime = datetime.strptime(
        event_datetime, DATETIME_STRING_FORMAT)
    displayed_time = event_datetime.strftime(f'{DATETIME_STRING_FORMAT} (%A)')
    embed = discord.Embed(
        title=name, description=description, color=0x00ff00)
    embed.set_author(name=ctx.message.author.display_name,
                     icon_url=ctx.message.author.avatar_url)
    embed.add_field(name="WHEN", value=displayed_time, inline=False)
    embed.add_field(name="Are you joining?", value="""\
Yes? Hit that ✅\n\
Maybe? Hit that ❔\n\
No? Hit that ❌""")
    if notify_everyone:
        embed.set_footer(
            text="Everyone in this channel will be notified when this event will be starting soon.")
    else:
        embed.set_footer(
            text="You will receive a notification when the event will be starting soon if you hit ✅ or ❔.")
    message = await ctx.send(content="@everyone! The following event has been created!", embed=embed)
    await message.pin()
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
        for reaction in ctx.message.reactions:
            if not reaction.emoji in [ACCEPTED, TENTATIVE, REJECTED]:
                await reaction.clear()

bot.loop.create_task(event_heartbeat())
bot.run(discord_token)
