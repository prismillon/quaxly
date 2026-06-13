import re

import discord
from discord import Embed, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from database import get_db_session
from models import GAME_MKWORLD, TimeRecord, Track, get_user_by_discord_id
from utils import itemChoices

TIME_PATTERN = re.compile(
    r"(?:^|\s)(?:(3DS|DS|N64|Wii|Tour|GCN|SNES|NSW)\s+)?([A-Za-z0-9\'?.\- ]+?):\s+(\d:\d{2}\.\d{3})",
    re.IGNORECASE,
)


class Dump(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(items=itemChoices)
    @app_commands.describe(
        items="are you using shrooms?",
        times="the list of time from your profile on lakitu bot",
    )
    async def import_times(
        self, interaction: discord.Interaction, items: Choice[str], times: str
    ):
        """import times from lakitu bot by copy pasting your leaderboard"""

        matches = TIME_PATTERN.findall(times)

        if not matches:
            return await interaction.response.send_message(
                "No valid times found in the input.", ephemeral=True
            )

        response_lines = []
        with get_db_session() as session:
            user = get_user_by_discord_id(session, interaction.user.id)
            if not user:
                return await interaction.response.send_message(
                    "please use /register first", ephemeral=True
                )

            for track_source, time in matches:
                track = (
                    session.query(Track)
                    .filter(
                        Track.game == GAME_MKWORLD,
                        Track.full_name.ilike(f"%{track_source}%"),
                    )
                    .first()
                )
                if not track:
                    continue

                existing_record = (
                    session.query(TimeRecord)
                    .filter(
                        TimeRecord.user_id == user.id,
                        TimeRecord.track_id == track.id,
                        TimeRecord.game == GAME_MKWORLD,
                        TimeRecord.race_type == items.value,
                        TimeRecord.speed == 150,
                    )
                    .first()
                )

                time_ms = TimeRecord.time_to_milliseconds(time)

                if existing_record:
                    if existing_record.time_milliseconds <= time_ms:
                        continue
                    else:
                        existing_record.time = time
                        existing_record.time_milliseconds = time_ms
                else:
                    new_record = TimeRecord(
                        user_id=user.id,
                        track_id=track.id,
                        game=GAME_MKWORLD,
                        time=time,
                        race_type=items.value,
                        speed=150,
                        time_milliseconds=time_ms,
                    )
                    session.add(new_record)
                session.commit()

                response_lines.append(f"**{track.full_name}**: `{time}`")

        if len(response_lines) == 0:
            return await interaction.response.send_message(
                "no time to import", ephemeral=True
            )

        response = "\n".join(response_lines)

        await interaction.response.send_message(
            embed=Embed(
                title=f"Imported times ({items.name})",
                description=response,
                color=0x47E0FF,
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Dump(bot))
