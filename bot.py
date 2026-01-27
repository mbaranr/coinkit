import os
import time
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from github import Github, Auth, GithubException

from engine import run_once
from storage.sqlite import (
    get_last,
    list_metrics,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger("stonks")


BOT_START_TIME = time.time()
LAST_ENGINE_RUN = None
LAST_ENGINE_ERROR = None

ALERT_INTERVAL_SECONDS = 5 * 60

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_ID = os.getenv("DISCORD_ALERT_ROLE_ID")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

CHANNELS = {
    "rates": int(os.getenv("DISCORD_RATES_CHANNEL_ID", "0")),
    "caps": int(os.getenv("DISCORD_CAPS_CHANNEL_ID", "0")),
}

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

for name, cid in CHANNELS.items():
    if cid == 0:
        raise RuntimeError(f"DISCORD_{name.upper()}_CHANNEL_ID not set")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None,
)


def resolve_metric_name(metric_key: str) -> str:
    for m in list_metrics():
        if m["key"] == metric_key:
            return m["name"]
    return metric_key


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    alert_loop.start()


@bot.event
async def on_guild_join(guild: discord.Guild):
    greeting = (
        f"Hey! I'm **stonks**, here to help monitor your DeFi protocol metrics.\n\n"
        "**Quick start:**\n"
        "`$help`\n"
        "`$metrics`\n"
        "`$check <metric_key>`\n"
    )

    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(greeting)
            break


def format_alert(alert: dict) -> str:
    if alert["level"] == "major" and ROLE_ID:
        return f"<@&{ROLE_ID}> {alert['message']}"
    return alert["message"]


@tasks.loop(seconds=ALERT_INTERVAL_SECONDS)
async def alert_loop():
    global LAST_ENGINE_RUN, LAST_ENGINE_ERROR

    await bot.wait_until_ready()

    try:
        alerts = run_once()
        LAST_ENGINE_RUN = time.time()
        LAST_ENGINE_ERROR = None
    except Exception:
        LAST_ENGINE_ERROR = time.time()
        logger.exception("Engine error")
        return

    for alert in alerts:
        channel = bot.get_channel(CHANNELS.get(alert["category"]))
        if channel:
            await channel.send(format_alert(alert))


@bot.command()
async def help(ctx):
    await ctx.send(
        "**Commands:**\n"
        "`$metrics` – list metrics\n"
        "`$check <metric_key>` – inspect metric\n"
        "`$issue <text>` – create GitHub issue\n"
        "`$info` – bot info\n"
        "`$status` – bot health\n"
    )


@bot.command()
async def info(ctx):
    await ctx.send(
        "**Info:**\n"
        "I check metrics every 5 minutes.\n"
        "The cap threshold is 99.995%.\n"
        "Baseline for rate metrics is sticky and set on first observation.\n"
        "Keys are set as `<protocol>:<token>:<supply/borrow>:<metric>`.\n\n"

        "GitHub: https://github.com/mbaranr/stonks"
    )


@bot.command()
async def metrics(ctx):
    metrics = [
        m for m in list_metrics()
        if not m["key"].endswith(":baseline")
    ]

    if not metrics:
        await ctx.send("No metrics recorded yet.")
        return
    
    await ctx.send(
        "**Known Metrics:**\n" +
        "\n".join(f"`{m['key']}` – {m['name']}" for m in metrics)
    )


@bot.command()
async def check(ctx, metric_key: str):
    current = get_last(metric_key)
    now = time.time()
    time_since = now - LAST_ENGINE_RUN if LAST_ENGINE_RUN else None

    more_than_minute = time_since > 60

    if time_since and more_than_minute:
        time_since = time_since / 60

    if current is None:
        await ctx.send(f"❌ Unknown metric key: `{metric_key}`")
        return

    name = resolve_metric_name(metric_key)


    # caps
    if metric_key.endswith("cap"):

        await ctx.send(
            f"**{name}:**\n"
            f"{current:.2%} ({time_since:.0f}{'m' if more_than_minute else 's'} ago)\n"
        )
        return

    # rates

    await ctx.send(
        f"**{name}:**\n"
        f"{current:.2%} ({time_since:.0f}{'m' if more_than_minute else 's'} ago)\n"
    )


@bot.command()
async def status(ctx):
    now = time.time()
    
    uptime_m = int((now - BOT_START_TIME) / 60)

    last_run = (
        "never"
        if LAST_ENGINE_RUN is None
        else f"{int((now - LAST_ENGINE_RUN) / 60)}m ago"
    )

    last_error = (
        "never"
        if LAST_ENGINE_ERROR is None
        else f"{int((now - LAST_ENGINE_ERROR) / 60)}m ago"
    )

    await ctx.send(
        f"**Bot Status:**\n"
        f"Uptime: {uptime_m}m\n"
        f"Last engine run: {last_run}\n"
        f"Last engine error: {last_error}\n"
    )


@bot.command()
async def issue(ctx, *, text: str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        await ctx.send("❌ GitHub integration not configured.")
        return

    try:
        auth = Auth.Token(GITHUB_TOKEN)
        gh = Github(auth=auth)
        repo = gh.get_repo(GITHUB_REPO)

        issue = repo.create_issue(
            title=f"Issue from Discord ({ctx.author})",
            body=(
                f"Reported by: {ctx.author}\n"
                f"User ID: {ctx.author.id}\n"
                f"Channel: {ctx.channel}\n\n"
                f"{text}"
            ),
        )

        await ctx.send(f"{issue.html_url}")

    except GithubException as e:
        await ctx.send(
            f"❌ GitHub error ({e.status}): {e.data.get('message')}"
        )
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: `{e}`")


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


if __name__ == "__main__":
    bot.run(TOKEN)