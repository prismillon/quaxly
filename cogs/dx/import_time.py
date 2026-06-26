import re
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

import utils
from database import get_db_session
from game_utils import get_track_by_name
from models import GAME_MK8DX, TimeRecord, User, UserServer


class ImportTimeCommands:
    """Import time command for MK8DX"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_user = {}
        self._remove_user_task = self.remove_expired_user.start()

    @app_commands.command(name="import_time")
    @app_commands.guild_only()
    @app_commands.describe(
        speed="the mode your list correspond to",
        items="is it with shroom or not",
        name="the name cadoizzob display",
    )
    @app_commands.choices(speed=utils.speedChoices, items=utils.itemChoices)
    async def import_time(
        self,
        interaction: discord.Interaction,
        speed: Choice[str],
        items: Choice[str],
        name: str = None,
    ):
        """Import time from cadoizzob for MK8DX"""

        if not interaction.channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(
                "I don't have permission to send message in this channel"
            )

        name = name or interaction.user.display_name
        game = GAME_MK8DX
        race_type = items.value
        speed_value = int(speed.value)

        self.active_user[(interaction.channel_id, name.lower())] = {
            "date": datetime.now(),
            "game": game,
            "race_type": race_type,
            "speed": speed_value,
            "discord_id": interaction.user.id,
        }

        await interaction.response.send_message(
            "please use the command below quaxly will register the times from Cadoizzob for you (make sure your name match the name in cadoizzob)"
        )
        await interaction.channel.send(
            f"/tt option:{speed.name} categorie:{'shroom' if items.value == 'sh' else 'ni'} third:find four:{interaction.user.id}"
        )

    @commands.Cog.listener(name="on_message")
    async def process_cadoizzob_message(self, message: discord.Message):
        """Process Cadoizzob bot message and import times"""
        if (
            message.author.id != 543424033673445378
            or len(message.embeds) != 1
            or not message.embeds[0].title
        ):
            return

        session_key = (message.channel.id, message.embeds[0].title[9:].lower())
        if session_key not in self.active_user:
            return

        user_data = self.active_user[session_key]
        game = user_data["game"]
        race_type = user_data["race_type"]
        speed = user_data["speed"]
        discord_id = user_data["discord_id"]

        with get_db_session() as session:
            user = session.query(User).filter(User.discord_id == discord_id).first()
            if not user:
                user = User(discord_id=discord_id)
                session.add(user)
                session.flush()

                user_server = UserServer(user_id=user.id, server_id=message.guild.id)
                session.add(user_server)

            user_server = (
                session.query(UserServer)
                .filter(
                    UserServer.user_id == user.id,
                    UserServer.server_id == message.guild.id,
                )
                .first()
            )
            if not user_server:
                user_server = UserServer(user_id=user.id, server_id=message.guild.id)
                session.add(user_server)

            time_list = re.findall(
                "[a-zA-Z0-9]+ : \*\*\d+\/\d+\*\* -> \d:[0-5]\d\.\d{3}",
                message.embeds[0].description,
            )

            if len(time_list) == 0:
                await message.channel.send("ptit flop bg")
                return

            imported_count = 0
            for line in time_list:
                time_str = line.split(" -> ")[1]
                track_name = line.split(" : ")[0]

                track_name_mapping = {
                    "bcm64": "bCMo",
                    "bcmw": "bCMa",
                    "brrd": "bRRW",
                    "bsis": "bSSy",
                }

                if track_name.lower() in track_name_mapping:
                    track_name = track_name_mapping[track_name.lower()]

                track_obj = get_track_by_name(session, game, track_name)
                if not track_obj:
                    print(f"Track not found: {track_name}")
                    continue

                existing_time = (
                    session.query(TimeRecord)
                    .filter(
                        TimeRecord.user_id == user.id,
                        TimeRecord.track_id == track_obj.id,
                        TimeRecord.game == game,
                        TimeRecord.race_type == race_type,
                        TimeRecord.speed == speed,
                    )
                    .first()
                )

                time_ms = TimeRecord.time_to_milliseconds(time_str)

                if existing_time:
                    existing_time.time = time_str
                    existing_time.time_milliseconds = time_ms
                    existing_time.updated_at = datetime.utcnow()
                else:
                    new_time_record = TimeRecord(
                        user_id=user.id,
                        track_id=track_obj.id,
                        game=game,
                        time=time_str,
                        race_type=race_type,
                        speed=speed,
                        time_milliseconds=time_ms,
                    )
                    session.add(new_time_record)

                imported_count += 1

            session.commit()
            await message.add_reaction("✅")
            await message.channel.send(
                f"Successfully processed {imported_count} times!"
            )
            self.active_user.pop(session_key)

    @tasks.loop(minutes=1)
    async def remove_expired_user(self):
        """Remove expired import sessions"""
        expired_date = datetime.now() - timedelta(minutes=10)
        for user, data in list(self.active_user.items()):
            if data["date"] < expired_date:
                self.active_user.pop(user)
