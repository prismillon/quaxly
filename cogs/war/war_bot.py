import json
import re
from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands, tasks

from autocomplete import mkc_tag_autocomplete
from cogs.war.base import Base
from database import get_db_session, r, rs
from game_utils import get_track_by_name
from models import GAME_MK8DX, GAME_MKWII, GAME_MKWORLD, Race, WarEvent
from utils import warGameChoices

_SCORE = (15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1)
_SCORE_MKWII = (15, 12, 10, 8, 6, 4, 3, 2, 1, 0)

WAR_FORMATS = {
    GAME_MK8DX: {
        "score": _SCORE,
        "total": sum(_SCORE),
        "team_size": 6,
        "max_pos": 12,
        "spots_re": "^((?!--)[0-9+-])+$",
    },
    GAME_MKWORLD: {
        "score": _SCORE,
        "total": sum(_SCORE),
        "team_size": 6,
        "max_pos": 12,
        "spots_re": "^((?!--)[0-9+-])+$",
    },
    GAME_MKWII: {
        "score": _SCORE_MKWII,
        "total": sum(_SCORE_MKWII),
        "team_size": 5,
        "max_pos": 10,
        "spots_re": "^((?!--)[0-9-])+$",
    },
}


def get_war_format(game: str):
    return WAR_FORMATS.get(game, WAR_FORMATS[GAME_MKWORLD])


def text_to_score(text: str, fmt=WAR_FORMATS[GAME_MKWORLD]):
    twelve = fmt["max_pos"] >= 12
    data = []
    prev = None
    next_list = []
    loopFlag = False
    while text:
        next_list = []
        if text.startswith("-"):
            loopFlag = True
            text = text[1:]
            if data:
                prev = data[-1]
            else:
                prev = 0
        if text.startswith("0"):
            next_list = [10]
            text = text[1:]
        elif twelve and text.startswith("+"):
            next_list = [11]
            text = text[1:]
        elif text.startswith("10"):
            next_list = [10]
            text = text[2:]
        elif text.startswith("110"):
            next_list = [1, 10]
            text = text[3:]
        elif twelve and text.startswith("1112"):
            next_list = [11, 12]
            text = text[4:]
        elif twelve and text.startswith("111"):
            next_list = [1, 11]
            text = text[3:]
        elif twelve and text.startswith("112"):
            next_list = [1, 12]
            text = text[3:]
        elif twelve and text.startswith("11"):
            next_list = [11]
            text = text[2:]
        elif twelve and text.startswith("12"):
            if data:
                next_list = [12]
            else:
                next_list = [1, 2]
            text = text[2:]
        elif text:
            next_list = [int(text[0], 16)]
            text = text[1:]
        if loopFlag:
            if not next_list:
                next_list = [fmt["max_pos"]]
            next = next_list[0]
            while next - prev > 1:
                data.append(prev + 1)
                prev += 1
            loopFlag = False
        data += next_list
    return validate_score(set(data), fmt)


def validate_score(data: set, fmt=WAR_FORMATS[GAME_MKWORLD]):
    last_spot = fmt["max_pos"]
    while len(data) < fmt["team_size"]:
        data.add(last_spot)
        last_spot -= 1
    return sorted(list(data))[: fmt["team_size"]]


def make_embed(war):
    embed = discord.Embed(
        color=0x47E0FF, title=f"Total Score after Race {len(war['diff'])}"
    )
    home_pen = war.get("home_pen", 0)
    enemy_pen = war.get("enemy_pen", 0)
    home_total = sum(war["home_score"]) - home_pen
    enemy_total = sum(war["enemy_score"]) - enemy_pen
    diff = home_total - enemy_total
    embed.add_field(name=war["tag"], value=home_total)
    embed.add_field(name=war["enemy_tag"], value=enemy_total)
    embed.add_field(
        name="Difference",
        value=f"{diff if diff < 0 else '+' + str(diff)}",
        inline=False,
    )
    if home_pen or enemy_pen:
        pen_lines = []
        if home_pen:
            pen_lines.append(f"{war['tag']}: -{home_pen}")
        if enemy_pen:
            pen_lines.append(f"{war['enemy_tag']}: -{enemy_pen}")
        embed.add_field(name="Penalties", value="\n".join(pen_lines), inline=False)
    if len(war["diff"]) > 0:
        race_field_value = "```\n"
        for i, (spot, diff, track) in enumerate(
            zip(war["spots"], war["diff"], war["tracks"])
        ):
            diff = str(diff) if diff < 0 else "+" + str(diff)
            spot = re.sub("[\\[\\] ]", "", str(spot))
            race_field_value += f"{i + 1:2}: {diff:>3} | {spot:14} {'(' + track + ')' if track else ''}\n"
        race_field_value += "```"
        embed.add_field(name="Races", value=race_field_value, inline=False)
    return embed


class WarBot(Base):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_war = {}

        cached_war = rs.keys("*")

        for war in cached_war:
            war_data = rs.get(war)
            war_data = json.loads(war_data)

            if "incoming_track" in war_data:
                self.active_war[int(war)] = war_data

        self._remove_war_task = self.remove_expired_war.start()

    @app_commands.command(name="start")
    @app_commands.guild_only()
    @app_commands.autocomplete(tag=mkc_tag_autocomplete, enemy_tag=mkc_tag_autocomplete)
    @app_commands.choices(game=warGameChoices)
    @app_commands.describe(
        tag="the tag of your team", enemy_tag="the tag of the enemy team"
    )
    async def warstart(
        self,
        interaction: discord.Interaction,
        tag: str,
        enemy_tag: str,
        game: Choice[str] = None,
    ):
        """start a war in the channel"""

        game_value = game.value if game else "mkworld"

        if not interaction.channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(
                content="missing send message permission in this channel, can't start war",
                ephemeral=True,
            )

        date = datetime.now(UTC)

        with get_db_session() as session:
            war_event = WarEvent(
                game=game_value,
                channel_id=interaction.channel.id,
                date=date,
                tag=tag,
                enemy_tag=enemy_tag,
                incoming_track=None,
            )
            session.add(war_event)
            session.commit()

            war_data = {
                "id": war_event.id,
                "channel_id": interaction.channel.id,
                "game": game_value,
                "date": date.isoformat(),
                "tag": tag,
                "enemy_tag": enemy_tag,
                "home_score": [],
                "enemy_score": [],
                "home_pen": 0,
                "enemy_pen": 0,
                "spots": [],
                "diff": [],
                "tracks": [],
                "incoming_track": None,
            }

            self.active_war[interaction.channel.id] = war_data

            await r.set(
                interaction.channel.id,
                json.dumps(war_data, default=str),
            )

        return await interaction.response.send_message(
            f"started war between `{tag}` and `{enemy_tag}` \n(obs overlay: https://waroverlay.prismillon.com/overlay/{interaction.channel.id})"
        )

    @app_commands.command(name="stop")
    @app_commands.guild_only()
    async def warstop(self, interaction: discord.Interaction):
        """stop the war"""

        if interaction.channel.id in self.active_war:
            await r.delete(interaction.channel.id)
            self.active_war.pop(interaction.channel.id)
            return await interaction.response.send_message("stopped war")
        await interaction.response.send_message("no active war")

    @app_commands.command(name="edit_race")
    @app_commands.guild_only()
    @app_commands.describe(race_nb="the race number", spots="the new spots")
    async def edit_race(
        self, interaction: discord.Interaction, race_nb: Range[int, 1], spots: str
    ):
        """edit a race number spots"""
        if interaction.channel.id not in self.active_war:
            return await interaction.response.send_message(
                content="no active war", ephemeral=True
            )

        war = self.active_war[interaction.channel.id]
        fmt = get_war_format(war.get("game", GAME_MKWORLD))

        if len(war["spots"]) < race_nb:
            return await interaction.response.send_message(
                content="invalid race number", ephemeral=True
            )

        if not re.fullmatch(fmt["spots_re"], spots):
            return await interaction.response.send_message(
                content="invalid spots format", ephemeral=True
            )

        spots = text_to_score(spots, fmt)
        scored = sum(map(lambda r: fmt["score"][r - 1], spots))
        enemy_scored = fmt["total"] - scored
        war["spots"][race_nb - 1] = spots
        war["home_score"][race_nb - 1] = scored
        war["enemy_score"][race_nb - 1] = enemy_scored
        war["diff"][race_nb - 1] = scored - enemy_scored

        with get_db_session() as session:
            war_event = session.query(WarEvent).filter(WarEvent.id == war["id"]).first()

            if war_event:
                race = (
                    session.query(Race)
                    .filter(
                        Race.war_event_id == war_event.id, Race.race_number == race_nb
                    )
                    .first()
                )

                if race:
                    race.positions = spots
                    race.score_diff = scored - enemy_scored
                    race.home_score = scored
                    race.enemy_score = enemy_scored
                    session.commit()

        await r.set(interaction.channel.id, json.dumps(war, default=str))

        embed = make_embed(war)
        return await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=1)
    async def remove_expired_war(self):
        expired_date = datetime.now(UTC) - timedelta(hours=6)
        to_remove = []
        for channel_id, war in self.active_war.items():
            war_date = datetime.fromisoformat(war["date"])
            if war_date < expired_date:
                to_remove.append(channel_id)
        for channel_id in to_remove:
            await r.delete(channel_id)
            self.active_war.pop(channel_id)

    @commands.Cog.listener(name="on_message")
    async def war_score(self, message: discord.Message):
        if message.channel.id not in self.active_war:
            return

        war = self.active_war[message.channel.id]

        if message.content.startswith("race "):
            data = message.content.split(" ")
            if not data[1].isnumeric() or len(data) != 3:
                return
            with get_db_session() as session:
                track = get_track_by_name(
                    session, war.get("game", GAME_MKWORLD), data[2]
                )
            if not track:
                return
            war["tracks"][int(data[1]) - 1] = track.track_name
            self.active_war[message.channel.id] = war
            with get_db_session() as session:
                race = (
                    session.query(Race)
                    .filter(
                        (Race.war_event_id == war["id"]) & (Race.race_number == data[1])
                    )
                    .first()
                )
                if race:
                    race.track_name = track.track_name
            await r.set(
                message.channel.id,
                json.dumps(self.active_war[message.channel.id], default=str),
            )
            return await message.reply(embed=make_embed(war), mention_author=False)

        pen_match = re.fullmatch(r"(un)?pen (-?[0-9]+)", message.content.lower())
        if pen_match:
            amount = int(pen_match.group(2))
            if amount == 0:
                return
            team = "enemy_pen" if amount > 0 else "home_pen"
            if pen_match.group(1):
                war[team] = max(0, war.get(team, 0) - abs(amount))
            else:
                war[team] = war.get(team, 0) + abs(amount)
            self.active_war[message.channel.id] = war

            await r.set(
                message.channel.id,
                json.dumps(war, default=str),
            )
            return await message.reply(embed=make_embed(war), mention_author=False)

        if message.content.lower() == "back":
            race_id = len(war["spots"])
            war["spots"] = war["spots"][: race_id - 1]
            war["diff"] = war["diff"][: race_id - 1]
            war["tracks"] = war["tracks"][: race_id - 1]
            war["home_score"] = war["home_score"][: race_id - 1]
            war["enemy_score"] = war["enemy_score"][: race_id - 1]
            self.active_war[message.channel.id] = war

            with get_db_session() as session:
                session.query(Race).filter(
                    (Race.war_event_id == war["id"]) & (Race.race_number == race_id)
                ).delete()
                session.commit()

            await r.set(
                message.channel.id,
                json.dumps(war, default=str),
            )
            return await message.reply(embed=make_embed(war), mention_author=False)

        fmt = get_war_format(war.get("game", GAME_MKWORLD))
        if re.fullmatch(fmt["spots_re"], message.content):
            spots = text_to_score(message.content, fmt)
            scored = sum(map(lambda r: fmt["score"][r - 1], spots))
            home_score = scored
            enemy_score = fmt["total"] - scored
            diff = home_score - enemy_score

            war["spots"].append(spots)
            war["diff"].append(diff)
            war["tracks"].append(war["incoming_track"])
            war["home_score"].append(home_score)
            war["enemy_score"].append(enemy_score)
            war["incoming_track"] = None

            with get_db_session() as session:
                war_event = (
                    session.query(WarEvent).filter(WarEvent.id == war["id"]).first()
                )

                if war_event:
                    race = Race(
                        war_event_id=war_event.id,
                        game=war_event.game,
                        race_number=len(war["spots"]),
                        track_name=war["tracks"][-1],
                        home_score=home_score,
                        enemy_score=enemy_score,
                        score_diff=diff,
                        positions=spots,
                    )
                    session.add(race)

                    war_event.incoming_track = None
                    session.commit()

            await r.set(message.channel.id, json.dumps(war, default=str))

            embed = make_embed(war)
            return await message.channel.send(embed=embed)

        with get_db_session() as session:
            track = get_track_by_name(
                session, war.get("game", GAME_MKWORLD), message.content
            )
            if not track:
                return

            war["incoming_track"] = track.track_name
            self.active_war[message.channel.id] = war
            await message.add_reaction("✅")
