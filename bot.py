import os
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from github import Github, Auth, GithubException

from engine import run_once
from db.repo import (
    list_metrics,
    add_subscription,
    remove_subscription,
    subscriptions_for_metric,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger("stonks")


ALERT_INTERVAL_SECONDS = 5 * 60
ALERT_TTL_SECONDS = 12 * 60 * 60

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

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


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    alert_loop.start()


@bot.event
async def on_guild_join(guild: discord.Guild):
    greeting = (
        f"Meow! I'm CoinKit, purr-suing your crypto signals claw-sely.\n\n"
        "**Quick start:**\n"
        "`$help`\n"
        "`$toys`"
    )

    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(greeting)
            break


def subscriber_mentions(alert: dict) -> str:
    """
    Build a mention string for users subscribed to this metric.
    Mentions are added to the alert message in-channel (no DMs needed).
    """
    metric_key = alert.get("metric_key")
    if not metric_key:
        return ""

    user_ids = subscriptions_for_metric(metric_key)
    if not user_ids:
        return ""

    return " ".join(f"<@{uid}>" for uid in user_ids)


@tasks.loop(seconds=ALERT_INTERVAL_SECONDS)
async def alert_loop():
    await bot.wait_until_ready()

    try:
        alerts = run_once()
    except Exception:
        logger.exception("Engine error")
        return

    for alert in alerts:
        channel = bot.get_channel(CHANNELS.get(alert["category"]))
        if channel:
            level = alert.get("level")
            mentions = "@everyone" if level == "major" else subscriber_mentions(alert)
            message = alert["message"]
            if mentions:
                message = f"{message}\n{mentions}"

            await channel.send(
                message,
                delete_after=ALERT_TTL_SECONDS,
            )


@bot.command()
async def help(ctx):
    await ctx.send(
        "**Commands:**\n"
        "`$help` – this message\n"
        "`$toys` – list what I'm batting around\n"
        "`$sub <key>` – be tagged on alerts for a toy\n"
        "`$unsub <key>` – stop hearing about a toy\n"
        "`$info` – how this cat-bot works\n"
        "`$issue <text>` – open a GitHub issue\n"
    )


@bot.command()
async def info(ctx):
    await ctx.send(
        "**Info:**\n"
        "I sniff metrics and discrete events every 5 minutes.\n"
        "Alerts curl up and disappear after 12 hours.\n"
        "Cap utilization threshold: 99.995%.\n"
        "Rate anchors are sticky from first observation.\n\n"

        "GitHub: https://github.com/mbaranr/coinkit"
    )


@bot.command(name="toys")
async def toys(ctx):
    metrics = [
        m for m in list_metrics()
        if not m["key"].endswith(":anchor")
    ]

    if not metrics:
        await ctx.send(
            "No metrics recorded yet. I'll fill the toy box after the next prowl."
        )
        return

    await ctx.send(
        "**Toy Basket:**\n"
        + "\n".join(f"`{m['key']}` – {m['name']}" for m in metrics)
        + "\n\nSubscribe with `$sub <key>` to get a ping when I hiss about it."
    )


@bot.command(name="sub")
async def subscribe(ctx, metric_key: str):
    metrics = {
        m["key"]
        for m in list_metrics()
        if not m["key"].endswith(":anchor")
    }

    if metric_key not in metrics:
        await ctx.send(
            f"❌ Unknown toy: `{metric_key}`. Try `$toys` to see my toy basket."
        )
        return

    created = add_subscription(ctx.author.id, metric_key)
    if created:
        await ctx.send(
            f"✅ Subscribed to `{metric_key}`. I'll tag you in-channel when this yarn ball moves."
        )
    else:
        await ctx.send(f"You're already curled up on `{metric_key}`.")


@bot.command(name="unsub")
async def unsubscribe(ctx, metric_key: str):
    metrics = {
        m["key"]
        for m in list_metrics()
        if not m["key"].endswith(":anchor")
    }

    if metric_key not in metrics:
        await ctx.send(
            f"❌ Unknown toy: `{metric_key}`. Try `$toys` to see my toy basket."
        )
        return

    removed = remove_subscription(ctx.author.id, metric_key)
    if removed:
        await ctx.send(
            f"✅ Unsubscribed from `{metric_key}`. I'll stop batting you when this moves."
        )
    else:
        await ctx.send(f"You're not currently stalking `{metric_key}`.")


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
    await ctx.send(
        "pong"
    )


if __name__ == "__main__":
    bot.run(TOKEN)
