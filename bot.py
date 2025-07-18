import discord
from discord.ext import commands, tasks
import datetime
import pytz
import os
import asyncio
from dotenv import load_dotenv

# === Load Environment Variables ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# === Config ===
DAYS = {
    "🇹": "Tuesday",
    "🇼": "Wednesday",
    "🇷": "Thursday",
    "🌞": "Sunday"
}
HOST_EMOJI = "✅"
eastern = pytz.timezone("US/Eastern")

# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === Store Poll Message ID ===
poll_message_id = None

# === On Ready ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    post_poll.start()
    tally_votes.start()

# === Post Poll on Sunday at 9:00 AM ET ===
@tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=eastern))
async def post_poll():
    global poll_message_id
    now = datetime.datetime.now(eastern)
    if now.weekday() == 6:  # Sunday
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🎥 Movie Night Poll",
                description=(
                    "psyduck says: **PSY PSY (MOVIE NIGHT POLL TIME! what days work this week?)**\n\n"
                    "You can choose more than one!\n\n"
                    f"{' '.join([f'{e} {d}' for e, d in DAYS.items()])}\n\n"
                    f"{HOST_EMOJI} = Can host this week"
                ),
                color=discord.Color.yellow()
            )
            embed.set_author(name="Psyduck Bot")
            embed.set_footer(text="🕒 Poll ends Tuesday at noon")
            embed.set_thumbnail(url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/54.png")

            message = await channel.send(
                content="@everyone",
                embed=embed
            )
            for emoji in DAYS:
                await message.add_reaction(emoji)
            await message.add_reaction(HOST_EMOJI)

            try:
                await message.pin() # Pin the message
            except discord.Forbidden:
                print("⚠️ Missing permission to pin the message.")

            poll_message_id = message.id
            print(f"📌 Poll posted :3 (message ID {poll_message_id})")

# === Tally Votes on Tuesday at 12:00 PM ET ===
@tasks.loop(time=datetime.time(hour=21, minute=0, tzinfo=eastern))  # Sunday at 9 PM ET
async def tally_votes():
    global poll_message_id
    channel = bot.get_channel(CHANNEL_ID)
    if not channel or not poll_message_id:
        print("Missing channel or poll_message_id.")
        return

    message = await channel.fetch_message(poll_message_id)
    top_day, top_voters, hosts = await collect_poll_data(message)
    await send_poll_results(channel, message, top_day, top_voters, hosts, ping_everyone=True)


    # Reset poll message ID for next week
    poll_message_id = None


# === Manual Test Command ===
@bot.command()
async def testpoll(ctx):
    """Manually trigger a test poll in the same channel (with embed styling)"""
    global poll_message_id
    if ctx.channel.id != CHANNEL_ID:
        return await ctx.send("⚠️ You can only run this in the movie night channel!")
    if poll_message_id:
        return await ctx.send("⚠️ A poll is already active! Use `!tallynow` or wait until it resets.")

    embed = discord.Embed(
        title="🎥 Movie Night Poll",
        description=(
            "psyduck says: **PSY PSY \n (MOVIE NIGHT POLL TIME!)**\n\n"
            "What days work for you? Choose 1 or more!\n\n"
            f"{' '.join([f'{e} {d}' for e, d in DAYS.items()])}\n\n"
            f"{HOST_EMOJI} = Can host this week"
        ),
        color=discord.Color.yellow()
    )
    embed.set_author(name="Psyduck Bot")
    embed.set_footer(text="🕒 Poll ends Tuesday at noon")
    embed.set_thumbnail(url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/54.png")

    message = await ctx.send(
        content="@ insert-role-here",
        embed=embed
    )
    for emoji in DAYS:
        await message.add_reaction(emoji)
    await message.add_reaction(HOST_EMOJI)

    try:
        await message.pin()
    except discord.Forbidden:
        print("⚠️ Missing permission to pin the message.")

    poll_message_id = message.id
    await ctx.send("✅ Test poll posted.")


@bot.command()
async def tallynow(ctx):
    """Manually trigger the movie night poll tally."""
    global poll_message_id
    await ctx.send("🔵 Tallying votes now!")

    message = await ctx.fetch_message(poll_message_id)
    top_day, top_voters, hosts = await collect_poll_data(message)
    await send_poll_results(ctx, message, top_day, top_voters, hosts, ping_everyone=False)


## helper functions

async def collect_poll_data(message):
    votes = {day: [] for day in DAYS.keys()}
    host_volunteers = []

    for reaction in message.reactions:
        if reaction.emoji in DAYS:
            async for user in reaction.users():
                if not user.bot:
                    votes[reaction.emoji].append(user)
        elif reaction.emoji == "✅":
            async for user in reaction.users():
                if not user.bot:
                    host_volunteers.append(user)

    sorted_votes = sorted(votes.items(), key=lambda x: len(x[1]), reverse=True)
    if sorted_votes and len(sorted_votes[0][1]) > 0:
        top_day = sorted_votes[0][0]
        top_voters = sorted_votes[0][1]
    else:
        top_day = None
        top_voters = []

    return top_day, top_voters, host_volunteers


async def send_poll_results(channel, poll_message, top_day, top_voters, hosts, ping_everyone=False):
    embed = discord.Embed(
        title="📊 Movie Night Poll Results",
        color=discord.Color.green()
    )

    clean_day = DAYS.get(top_day, top_day)
    if isinstance(top_day, tuple):
        clean_day = top_day[1]

    embed.add_field(
        name="🏆 Top pick(s) for Movie Night:",
        value=f"**{clean_day}**\nwith {len(top_voters)} vote(s)!" if top_voters else "No votes recorded.",
        inline=False
    )

    if top_voters:
        voter_mentions = "\n".join(v.mention for v in top_voters)
        embed.add_field(
            name="🗳️ with votes from:",
            value=voter_mentions,
            inline=False
        )

    if hosts:
        host_mentions = "\n".join(h.mention for h in hosts)
        embed.add_field(
            name="✅ Host volunteers:",
            value=host_mentions,
            inline=False
        )

    await channel.send(
        content="@everyone" if ping_everyone else "@ insert-role-here",
        embed=embed
    )

    # ⬇️ Unpin the original poll message
    try:
        await poll_message.unpin()
    except discord.Forbidden:
        print("⚠️ Missing permission to unpin poll message.")



bot.run(TOKEN)
