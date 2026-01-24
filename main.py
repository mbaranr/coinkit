import os
import time
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from github import Github

from notifiers.alerts import run_once
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
LAST_ALERT_COUNT = 0

ALERT_INTERVAL_SECONDS = 2 * 60

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
        "wsg, **stonks** here.\n\n"
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
    global LAST_ENGINE_RUN, LAST_ENGINE_ERROR, LAST_ALERT_COUNT

    await bot.wait_until_ready()

    try:
        alerts = run_once()
        LAST_ENGINE_RUN = time.time()
        LAST_ENGINE_ERROR = None
        LAST_ALERT_COUNT = len(alerts)
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
        "🛠 **Commands**\n"
        "`$metrics` – list metrics\n"
        "`$check <metric_key>` – inspect metric\n"
        "`$issue <text>` – create GitHub issue\n"
        "`$status` – bot health\n"
        "`$ping`\n"
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
        "📈 **Known metrics:**\n" +
        "\n".join(f"- `{m['key']}` — {m['name']}" for m in metrics)
    )


@bot.command()
async def check(ctx, metric_key: str):
    current = get_last(metric_key)

    if current is None:
        await ctx.send(f"❌ Unknown metric key: `{metric_key}`")
        return

    name = resolve_metric_name(metric_key)

    # caps
    if metric_key.endswith("cap"):
        state = "🧢 AT CAP" if current >= 1.0 else "⚠️ BELOW CAP"

        await ctx.send(
            f"📊 **{name}**\n"
            f"Usage: {current:.2%}\n"
            f"State: {state}"
        )
        return

    # rates
    baseline = get_last(f"{metric_key}:baseline")

    if baseline is None:
        await ctx.send(
            f"📊 **{name}**\n"
            f"Current: {current:.2%}\n"
            f"Baseline: not set yet"
        )
        return

    delta = current - baseline
    direction = "⬆️" if delta > 0 else "⬇️"

    await ctx.send(
        f"📊 **{name}**\n"
        f"Current: {current:.2%}\n"
        f"Baseline: {baseline:.2%}\n"
        f"Change: {direction} {delta:+.2%}"
    )


@bot.command()
async def status(ctx):
    await ctx.send(
        f"🧠 **Status**\n"
        f"Uptime: {int((time.time() - BOT_START_TIME) / 60)}m\n"
        f"Last alerts: {LAST_ALERT_COUNT}"
    )


@bot.command()
async def issue(ctx, *, text: str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        await ctx.send("GitHub not configured.")
        return

    repo = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)
    issue = repo.create_issue(
        title=f"Issue from {ctx.author}",
        body=text,
    )
    await ctx.send(issue.html_url)


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


if __name__ == "__main__":
    bot.run(TOKEN)