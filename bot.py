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

            await message.pin()  # Pin the message
            poll_message_id = message.id
            print(f"📌 Poll posted :3 (message ID {poll_message_id})")

# === Tally Votes on Tuesday at 12:00 PM ET ===
@tasks.loop(time=datetime.time(hour=12, minute=0, tzinfo=eastern))
async def tally_votes():
    global poll_message_id
    now = datetime.datetime.now(eastern)
    if now.weekday() == 1 and poll_message_id:  # Tuesday
        channel = bot.get_channel(CHANNEL_ID)
        try:
            message = await channel.fetch_message(poll_message_id)
            counts = {emoji: 0 for emoji in DAYS}
            hosts = []

            for reaction in message.reactions:
                users = [user async for user in reaction.users()]
                voters = [u for u in users if not u.bot]

                if reaction.emoji in DAYS:
                    counts[reaction.emoji] = len(voters)
                elif reaction.emoji == HOST_EMOJI:
                    hosts = [u.mention for u in voters]

            max_votes = max(counts.values())
            winners = [DAYS[e] for e, v in counts.items() if v == max_votes and max_votes > 0]

            embed = discord.Embed(
                title="📊 Movie Night Poll Results",
                color=discord.Color.green()
            )
            if winners:
                embed.add_field(
                    name="🏆 Top pick(s) for Movie Night:",
                    value=f"{', '.join(winners)} with {max_votes} vote(s)!",
                    inline=False
                )
            else:
                embed.add_field(name="No one voted 😢", value="Better luck next week!", inline=False)

            if hosts:
                embed.add_field(name="✅ Host volunteers:", value=", ".join(hosts), inline=False)
            else:
                embed.add_field(name="✅ Host volunteers:", value="No one volunteered yet.", inline=False)

            await channel.send(content="@everyone", embed=embed)

        except Exception as e:
            await channel.send(f"⚠️ Couldn’t tally the poll: {e}")
        finally:
            await message.unpin()
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
        content="@everyone",
        embed=embed
    )
    for emoji in DAYS:
        await message.add_reaction(emoji)
    await message.add_reaction(HOST_EMOJI)

    await message.pin()  # Pin the message
    poll_message_id = message.id
    await ctx.send("✅ Test poll posted.")


@bot.command()
async def tallynow(ctx):
    """Manually trigger tallying of the current poll (like Tuesday auto mode)"""
    global poll_message_id
    if ctx.channel.id != CHANNEL_ID:
        return await ctx.send("⚠️ You can only run this in the movie night channel.")
    if not poll_message_id:
        return await ctx.send("⚠️ No active poll found.")

    try:
        message = await ctx.channel.fetch_message(poll_message_id)
        counts = {emoji: 0 for emoji in DAYS}
        voters_by_emoji = {emoji: [] for emoji in DAYS}
        hosts = []

        for reaction in message.reactions:
            users = [user async for user in reaction.users()]
            real_users = [u for u in users if not u.bot]

            if reaction.emoji in DAYS:
                counts[reaction.emoji] = len(real_users)
                voters_by_emoji[reaction.emoji] = real_users
            elif reaction.emoji == HOST_EMOJI:
                hosts = [u.mention for u in real_users]

        max_votes = max(counts.values())
        winners = [e for e, v in counts.items() if v == max_votes and max_votes > 0]

        embed = discord.Embed(
            title="📊 Movie Night Poll Results",
            color=discord.Color.green()
        )

        if winners:
            for emoji in winners:
                day = DAYS[emoji]
                user_mentions = " ".join([u.mention for u in voters_by_emoji[emoji]])
                embed.add_field(
                    name=f"🏆 **{day}**",
                    value=f"with votes from: {user_mentions if user_mentions else 'No one? 😬'}",
                    inline=False
                )
        else:
            embed.add_field(name="No one voted 😢", value="Better luck next week!", inline=False)

        if hosts:
            embed.add_field(name="✅ Host volunteers:", value=", ".join(hosts), inline=False)
        else:
            embed.add_field(name="✅ Host volunteers:", value="No one volunteered yet.", inline=False)

        await ctx.send(content="@everyone", embed=embed)

        # Optional: Ping hosts in a separate message for visibility
        if hosts:
            await ctx.send(f"📣 Pinging host(s): {' '.join(hosts)}")

    except Exception as e:
        await ctx.send(f"⚠️ Couldn’t tally the poll: {e}")
    finally:
        poll_message_id = None  # Reset after tally






bot.run(TOKEN)
