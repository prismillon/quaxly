from typing import List, Optional

import aiohttp
import discord
from discord.app_commands import Choice

allowed_tables = ["Sh150", "Ni150", "Sh200", "Ni200"]
speedChoices = [Choice(name="150cc", value="150"), Choice(name="200cc", value="200")]
itemChoices = [Choice(name="Shrooms", value="sh"), Choice(name="No items", value="ni")]
gameChoices = [
    Choice(name="Mario Kart 8 Deluxe", value="mk8dx"),
    Choice(name="Mario Kart World", value="mkworld"),
]
loungeGameChoices = [
    Choice(name="Mario Kart 8 Deluxe", value="mk8dx"),
    Choice(name="Mario Kart World (24p)", value="mkworld24p"),
    Choice(name="Mario Kart World (12p)", value="mkworld12p"),
]
statChoices = [
    Choice(name="mmr", value="mmr"),
    Choice(name="peak", value="maxMmr"),
    Choice(name="events", value="eventsPlayed"),
]


class LoungeData:
    def __init__(self):
        self.base_url = "https://lounge.mkcentral.com/api"

    async def search_players(
        self, search: str = "", game: str = "mkworld", season: int = 0, limit: int = 50
    ) -> Optional[List[dict]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/player/leaderboard?game={game}&season={season}&search={search}&limit={limit}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                return None

    async def find_player_by_discord_id(
        self, discord_id: int, game: str = "mkworld"
    ) -> Optional[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/player/details?discordId={discord_id}&game={game}"
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def find_player_by_name(
        self, name: str, game: str = "mkworld"
    ) -> Optional[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/player/details?name={name}&game={game}"
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None


class MkcData:
    def __init__(self):
        self.base_url = "https://mkcentral.com/api"

    async def search_teams(
        self, search: str = "", limit: int = 25
    ) -> Optional[List[dict]]:
        """Search for teams and return their rosters"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/registry/teams?is_historical=false&is_active=true&sort_by_newest=false&min_player_count=6&name_or_tag={search}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    teams = data.get("teams", [])
                    rosters = []
                    for team in teams:
                        team_rosters = team.get("rosters", [])
                        for roster in team_rosters:
                            if roster["game"] == "mkworld" or roster["game"] == "mk8dx":
                                rosters.append(roster)
                    return rosters[:limit] if limit else rosters
                return None

    async def get_team_details(self, team_id: int, roster_id: int) -> Optional[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/registry/teams/{team_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    rosters = data.get("rosters", [])
                    for roster in rosters:
                        if int(roster.get("id")) == int(roster_id):
                            roster["logo"] = data.get("logo")
                            return roster
                return None


class LoungeSeason:
    def __init__(self):
        self._data = {}
        self.base_url = "https://lounge.mkcentral.com/api"

    async def lounge_season(self, game: str = "mkworld"):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/player/details?id=14324&game={game}"
            ) as response:
                if response.status == 200:
                    _data_full = await response.json()
                    self._data[game] = _data_full.get("season", 0)

    def data(self, game: str = "mkworld"):
        return self._data.get(game)


class Paginator(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, embeds: List[discord.Embed]):
        super().__init__(timeout=600)
        self.interaction = interaction
        self.embeds = embeds
        self.page_num = 1
        self.index.label = f"1/{len(embeds)}"
        self.first.disabled = True
        self.before.disabled = True
        if len(embeds) == 1:
            self.after.disabled = True
            self.last.disabled = True

    @discord.ui.button(label="<<", style=discord.ButtonStyle.blurple)
    async def first(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_num = 1
        self.index.label = f"{self.page_num}/{len(self.embeds)}"
        self.first.disabled = True
        self.before.disabled = True
        self.after.disabled = False
        self.last.disabled = False
        await interaction.response.edit_message(
            embed=self.embeds[self.page_num - 1], view=self
        )

    @discord.ui.button(label="<", style=discord.ButtonStyle.red)
    async def before(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_num -= 1
        self.index.label = f"{self.page_num}/{len(self.embeds)}"
        self.after.disabled = False
        self.last.disabled = False
        if self.page_num == 1:
            self.first.disabled = True
            self.before.disabled = True
        await interaction.response.edit_message(
            embed=self.embeds[self.page_num - 1], view=self
        )

    @discord.ui.button(style=discord.ButtonStyle.gray, disabled=True)
    async def index(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label=">", style=discord.ButtonStyle.green)
    async def after(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_num += 1
        self.index.label = f"{self.page_num}/{len(self.embeds)}"
        self.first.disabled = False
        self.before.disabled = False
        if self.page_num == len(self.embeds):
            self.after.disabled = True
            self.last.disabled = True
        await interaction.response.edit_message(
            embed=self.embeds[self.page_num - 1], view=self
        )

    @discord.ui.button(label=">>", style=discord.ButtonStyle.blurple)
    async def last(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_num = len(self.embeds)
        self.index.label = f"{self.page_num}/{len(self.embeds)}"
        self.first.disabled = False
        self.before.disabled = False
        self.after.disabled = True
        self.last.disabled = True
        await interaction.response.edit_message(
            embed=self.embeds[self.page_num - 1], view=self
        )

    async def on_timeout(self):
        self.first.disabled = True
        self.before.disabled = True
        self.after.disabled = True
        self.last.disabled = True
        if not self.interaction.is_expired():
            await self.interaction.edit_original_response(view=self)


class ConfirmButton(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.answer = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.answer = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.answer = False
        self.stop()


lounge_season = LoungeSeason()
lounge_data = LoungeData()
mkc_data = MkcData()
