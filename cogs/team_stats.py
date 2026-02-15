import asyncio
import re
import statistics
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands

from autocomplete import mkc_team_autocomplete
from utils import lounge_season, loungeGameChoices, mkc_data, statChoices

MAX_FIELDS = 21
MAX_EMBEDS = 10
LOUNGE_API = "https://lounge.mkcentral.com/api"


async def check_for_none(data: list) -> bool:
    return any(item is not None for item in data)


async def id_to_stat(
    discord_id: int, season: Optional[int] = None, game: str = "mkworld24p"
):
    season_param = f"&season={season}" if season else ""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{LOUNGE_API}/player/details?discordId={discord_id}&game={game}{season_param}"
        ) as response:
            if response.status == 200:
                user_data = await response.json()
                if "mmr" not in user_data:
                    return None
                user_data.setdefault("eventsPlayed", 0)
                user_data.setdefault("maxMmr", user_data["mmr"])
                user_data["discordId"] = discord_id
                user_data["id"] = user_data["playerId"]
                return user_data


async def fc_to_stat(
    fc: str,
    season: Optional[int] = None,
    game: str = "mkworld24p",
    discord_id: int = None,
):
    season_param = f"&season={season}" if season else ""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{LOUNGE_API}/player/details?fc={fc}&game={game}{season_param}"
        ) as response:
            if response.status == 200:
                user_data = await response.json()
                if "mmr" not in user_data:
                    return None
                user_data["discordId"] = user_data.get("discordId", discord_id)
                user_data.setdefault("eventsPlayed", 0)
                user_data.setdefault("maxMmr", user_data["mmr"])
                user_data["id"] = user_data["playerId"]
                return user_data


async def create_stat_embeds(
    title: str, users: list, stat_field: str, thumbnail_url: str = None
):
    embeds = [discord.Embed(title=title)]
    if thumbnail_url:
        embeds[0].set_thumbnail(url=thumbnail_url)

    for i, user in enumerate(users):
        if i % MAX_FIELDS == 0 and i != 0:
            embeds.append(discord.Embed())
        embeds[-1].add_field(
            name=user["name"],
            value=f"<@{user['discordId']}> ([{user[stat_field]}](https://lounge.mkcentral.com/PlayerDetails/{user['id']}))",
        )

    if len(embeds) > MAX_EMBEDS:
        raise ValueError("Too many users to display")

    stats = [user[stat_field] for user in users]
    embeds[-1].add_field(name="\u200b", value="\u200b", inline=False)
    embeds[-1].add_field(name="average", value=f"__{round(statistics.fmean(stats))}__")
    embeds[-1].add_field(
        name="top 6", value=f"__{round(statistics.fmean(stats[:6]))}__"
    )

    return embeds


@app_commands.command()
@app_commands.guild_only()
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.choices(stat=statChoices, game=loungeGameChoices)
@app_commands.describe(
    role="the role you want to check stats from",
    stat="the type of stats",
    season="the season you want this info from",
    game="the game to check stats for",
)
async def role_stats(
    interaction: discord.Interaction,
    role: discord.Role,
    stat: Choice[str] = None,
    season: Optional[int] = None,
    game: Choice[str] = None,
):
    """Check stats of a discord role"""
    await interaction.response.defer()
    stat = stat or statChoices[0]
    game_value = game.value if game else "mkworld24p"

    try:
        member_tasks = [
            id_to_stat(member.id, season=season, game=game_value)
            for member in role.members
        ]
        user_data = sorted(
            list(filter(None, await asyncio.gather(*member_tasks))),
            key=lambda k: k[stat.value],
            reverse=True,
        )

        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="no users found",
                    description="could not find anyone in lounge from this role",
                )
            )
            return

        embeds = await create_stat_embeds(
            f"{role.name} average {stat.name}", user_data, stat.value
        )
        await interaction.followup.send(embeds=embeds)

    except ValueError:
        await interaction.followup.send(
            embed=discord.Embed(
                title="too many users",
                description="too many users in this role, please select less people",
            )
        )


@app_commands.command()
@app_commands.autocomplete(team=mkc_team_autocomplete)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.choices(stat=statChoices, game=loungeGameChoices)
@app_commands.describe(
    team="the team you want to check stats from",
    stat="the type of stats",
    season="the season you want this info from",
    game="the game to check stats for",
)
async def mkc_stats(
    interaction: discord.Interaction,
    team: str,
    stat: Choice[str] = None,
    season: Optional[int] = None,
    game: Choice[str] = None,
):
    """Check stats of a Mario Kart Central team"""
    game_value = game.value if game else "mkworld24p"
    season = season or lounge_season.data(game_value)
    stat = stat or statChoices[0]

    await interaction.response.defer()

    if "-" not in team:
        await interaction.followup.send(
            embed=discord.Embed(
                title="team not found",
                description="could not find the team you typed in the mkc database",
            )
        )
        return

    team_id = int(team.split("-")[0])
    roster_id = int(team.split("-")[1])

    roster = await mkc_data.get_team_details(team_id, roster_id)

    if not roster:
        await interaction.followup.send(
            embed=discord.Embed(
                title="team not found",
                description="could not get team details from mkc database",
            )
        )
        return

    try:
        member_tasks = []
        for player in roster["players"]:
            friend_codes = player.get("friend_codes", [])
            fc = None
            discord_id = None
            discord_data = player.get("discord", None)
            if discord_data:
                discord_id = discord_data.get("discord_id", None)

            for fc_entry in friend_codes:
                if fc_entry.get("is_primary"):
                    fc = fc_entry.get("fc")
                    break

            if not fc:
                for fc_entry in friend_codes:
                    if fc_entry.get("is_active"):
                        fc = fc_entry.get("fc")
                        break

            if not fc and friend_codes:
                fc = friend_codes[0].get("fc")

            if fc:
                member_tasks.append(
                    fc_to_stat(
                        fc,
                        season=season,
                        game=game_value,
                        discord_id=discord_id,
                    )
                )

        if not member_tasks:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="no friend codes found",
                    description="could not find any friend codes for this team",
                )
            )
            return

        user_data = sorted(
            list(filter(None, await asyncio.gather(*member_tasks))),
            key=lambda k: k[stat.value],
            reverse=True,
        )

        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="no users found",
                    description="could not find anyone in lounge from this team",
                )
            )
            return

        thumbnail = None
        if roster.get("logo"):
            thumbnail = f"https://mkcentral.com{roster['logo']}"

        embeds = await create_stat_embeds(
            f"{roster['name']} average {stat.name}",
            user_data,
            stat.value,
            thumbnail or "",
        )
        await interaction.followup.send(embeds=embeds)

    except ValueError:
        await interaction.followup.send(
            embed=discord.Embed(
                title="too many users",
                description="too many users in this role, please select less people",
            )
        )


@app_commands.command()
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.choices(stat=statChoices, game=loungeGameChoices)
@app_commands.describe(
    room="message with the list of fc",
    team_size="the size of the team for this event",
    stat="the type of stats",
    season="the season you want this info from",
    game="the game to check stats for",
)
async def fc_stats(
    interaction: discord.Interaction,
    room: str,
    team_size: Range[int, 1, 6] = None,
    stat: Choice[str] = None,
    season: Optional[int] = None,
    game: Choice[str] = None,
):
    """Get stats from a room with friend codes"""
    friend_codes = re.findall(r"\d{4}-\d{4}-\d{4}", room)
    if not friend_codes:
        await interaction.response.send_message(
            content="no valid friend codes found in the message",
            ephemeral=True,
        )
        return

    if team_size:
        if len(friend_codes) != 12:
            await interaction.response.send_message(
                content="when providing a team size, room must contain exactly 12 friend codes",
                ephemeral=True,
            )
            return
        if 12 % team_size != 0:
            await interaction.response.send_message(
                content=f"12 players cannot be divided into teams of {team_size}",
                ephemeral=True,
            )
            return

    await interaction.response.defer()
    game_value = game.value if game else "mkworld24p"
    season = season or lounge_season.data(game_value)
    stat = stat or statChoices[0]

    players = await asyncio.gather(
        *[fc_to_stat(fc, season, game_value) for fc in friend_codes]
    )
    valid_players = list(filter(None, players))

    if not valid_players:
        await interaction.followup.send(
            embed=discord.Embed(
                title="no users found",
                description="could not find anyone in lounge from these friend codes",
            )
        )
        return

    if team_size:
        teams = [players[i : i + team_size] for i in range(0, len(players), team_size)]
        room_avg = round(statistics.fmean([p[stat.value] for p in valid_players]))
        embed = discord.Embed(title=f"room average {stat.name}: {room_avg}")

        for i, team in enumerate(teams):
            title = f"team {i + 1}: "
            if await check_for_none(team):
                team_avg = round(
                    statistics.fmean([p[stat.value] for p in filter(None, team)])
                )
                title += str(team_avg)
            else:
                title += "N/A"

            value = ""
            for member in team:
                if member:
                    value += f"[{member['name']}](https://lounge.mkcentral.com/PlayerDetails/{member['id']}): {member[stat.value]}\n"
                else:
                    value += "not in lounge\n"

            embed.add_field(name=title, value=value, inline=False)
    else:
        sorted_players = sorted(
            valid_players, key=lambda p: p[stat.value], reverse=True
        )
        embed = discord.Embed(title=f"Player {stat.name} Stats")

        value = ""
        for player in sorted_players:
            value += f"[{player['name']}](https://lounge.mkcentral.com/PlayerDetails/{player['id']}): {player[stat.value]}\n"

        if value:
            embed.description = value
            avg = round(statistics.fmean([p[stat.value] for p in sorted_players]))
            embed.add_field(name="average", value=str(avg), inline=True)

    await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    bot.tree.add_command(fc_stats)
    bot.tree.add_command(role_stats)
    bot.tree.add_command(mkc_stats)
