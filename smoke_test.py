"""Startup smoke test for the built image.

Run inside the container before publishing an image:

    DISCORD_TOKEN=<dev bot token> REDIS_URL=<host> python smoke_test.py

It loads every cog (which imports the database layer and the native data
packages) and then opens a real Discord gateway connection with the token.
Only the connection is exercised: the cogs' ``on_ready`` handlers are not
loaded onto the gateway client, so no commands, tasks or presence updates run.
"""

import asyncio
import os

import discord
from discord.ext import commands

TIMEOUT_SECONDS = 120

COGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cogs")


async def load_cogs(bot: commands.Bot) -> None:
    """Load extensions the same way main.py does, without connecting."""
    for entry in sorted(os.listdir(COGS_DIR)):
        if entry.startswith("__"):
            continue
        name = entry[:-3] if entry.endswith(".py") else entry
        await bot.load_extension(f"cogs.{name}")
        print(f"[smoke] loaded cogs.{name}")


class GatewayProbe(discord.Client):
    async def on_ready(self) -> None:
        print(f"[smoke] connected to Discord gateway as {self.user} (id={self.user.id})")
        await self.close()


def check_database() -> None:
    if os.environ.get("SMOKE_DB_CHECK") != "1":
        return

    import database

    if not database.health_check():
        raise SystemExit("[smoke] database health check failed")
    print("[smoke] database SELECT 1 OK")


async def main() -> None:
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.AutoShardedBot(
        command_prefix=commands.when_mentioned,
        intents=intents,
        help_command=None,
    )
    await load_cogs(bot)
    # AutoShardedBot.close() only works after the shard queue exists, so close
    # the HTTP client directly: this bot is never started or connected.
    await bot.http.close()

    check_database()

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("[smoke] DISCORD_TOKEN not set; skipping Discord gateway check")
        return

    # default() avoids the privileged members/message_content intents, which
    # the dev application may not have enabled.
    probe = GatewayProbe(intents=discord.Intents.default())
    try:
        await probe.start(token)
    finally:
        # start() can raise before connect() initialises the closing task.
        await probe.http.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=TIMEOUT_SECONDS))
    print("[smoke] OK")
