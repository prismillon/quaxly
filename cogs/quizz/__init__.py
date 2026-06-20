import asyncio

import discord
from discord import app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands

from cogs.quizz.session import QuizSession

_TYPE_MAP = {
    "all": ["flag", "capital", "map", "shape"],
    "flags": ["flag"],
    "capitals": ["capital"],
    "maps": ["map"],
    "shapes": ["shape"],
}

_TYPE_LABELS = {
    "all": "🌐 All types",
    "flags": "🚩 Flags",
    "capitals": "🏛️ Capitals",
    "maps": "🗺️ Maps",
    "shapes": "🧩 Shapes",
}

_DIFF_LABELS = {
    "easy": "🟢 Easy",
    "medium": "🟡 Medium",
    "hard": "🔴 Hard",
    "all": "🌈 All levels",
}

# Individual modes, in display order, used for the custom-mix selector.
_MODE_LABELS = {
    "flag": "🚩 Flags",
    "capital": "🏛️ Capitals",
    "map": "🗺️ Maps",
    "shape": "🧩 Shapes",
}


class ModeSelectView(discord.ui.View):
    """Lets the invoker pick their own mix of modes before starting."""

    def __init__(self, cog: "Quizz", author_id: int, channel, difficulty, questions):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id
        self.channel = channel
        self.difficulty = difficulty
        self.questions = questions
        self.selected: list[str] = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "this isn't your quiz setup", ephemeral=True
            )
            return False
        return True

    @discord.ui.select(
        placeholder="Pick the modes to include…",
        min_values=1,
        max_values=4,
        options=[
            discord.SelectOption(label="Flags", value="flag", emoji="🚩"),
            discord.SelectOption(label="Capitals", value="capital", emoji="🏛️"),
            discord.SelectOption(label="Maps", value="map", emoji="🗺️"),
            discord.SelectOption(label="Shapes", value="shape", emoji="🧩"),
        ],
    )
    async def select_modes(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        order = list(_MODE_LABELS)
        self.selected = sorted(select.values, key=order.index)
        await interaction.response.defer()

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success, emoji="▶️")
    async def start(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not self.selected:
            return await interaction.response.send_message(
                "pick at least one mode first", ephemeral=True
            )
        if self.cog.is_running(self.channel):
            return await interaction.response.send_message(
                "a quiz is already running here", ephemeral=True
            )

        q_types = list(self.selected)
        type_label = "🎛️ Custom: " + " + ".join(_MODE_LABELS[m] for m in q_types)

        for child in self.children:
            child.disabled = True
        self.stop()
        await interaction.response.edit_message(content="🎛️ Starting…", view=self)

        await self.channel.send(
            embed=self.cog.announce_embed(type_label, self.difficulty, self.questions)
        )
        await asyncio.sleep(3)
        self.cog.spawn(self.channel, q_types, self.difficulty, self.questions)


class Quizz(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, QuizSession] = {}

    def is_running(self, channel) -> bool:
        session = self.sessions.get(channel.id)
        return bool(session and session.is_active)

    def announce_embed(self, type_label, difficulty_value, questions):
        return discord.Embed(
            title="🌍 Geography Quiz",
            description=(
                f"**Type:** {type_label}\n"
                f"**Difficulty:** {_DIFF_LABELS[difficulty_value]}\n"
                f"**Questions:** {questions}\n\n"
                "Starting in **3s…**"
            ),
            color=0x3498DB,
        )

    def spawn(self, channel, q_types, difficulty_value, questions):
        session = QuizSession(
            channel, self.bot, q_types, difficulty_value, questions
        )
        self.sessions[channel.id] = session
        task = asyncio.create_task(session.start())
        session.task = task
        task.add_done_callback(lambda _: self.sessions.pop(channel.id, None))

    @app_commands.command(name="quiz")
    @app_commands.guild_only()
    @app_commands.describe(
        type="kind of questions (pick 🎛️ Custom to choose your own mix)",
        difficulty="how well-known the countries are",
        questions="number of questions (5-30)",
    )
    @app_commands.choices(
        type=[
            Choice(name="🌐 All types", value="all"),
            Choice(name="🚩 Flags only", value="flags"),
            Choice(name="🏛️ Capitals only", value="capitals"),
            Choice(name="🗺️ Maps only", value="maps"),
            Choice(name="🧩 Shapes only", value="shapes"),
            Choice(name="🎛️ Custom (pick modes)", value="custom"),
        ],
        difficulty=[
            Choice(name="🟢 Easy (well-known countries)", value="easy"),
            Choice(name="🟡 Medium (less common countries)", value="medium"),
            Choice(name="🔴 Hard (obscure countries)", value="hard"),
            Choice(name="🌈 All levels mixed", value="all"),
        ],
    )
    async def quiz(
        self,
        interaction: discord.Interaction,
        type: Choice[str] = None,
        difficulty: Choice[str] = None,
        questions: Range[int, 5, 200] = 10,
    ):
        """Start a geography quiz in this channel"""
        channel = interaction.channel

        if self.is_running(channel):
            return await interaction.response.send_message(
                "a quiz is already running here", ephemeral=True
            )

        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(
                "missing send message permission in this channel", ephemeral=True
            )

        difficulty_value = difficulty.value if difficulty else "easy"
        type_value = type.value if type else "all"

        if type_value == "custom":
            view = ModeSelectView(
                self, interaction.user.id, channel, difficulty_value, questions
            )
            return await interaction.response.send_message(
                "🎛️ **Pick the modes to include**, then press Start:",
                view=view,
                ephemeral=True,
            )

        q_types = _TYPE_MAP[type_value]
        await interaction.response.send_message(
            embed=self.announce_embed(
                _TYPE_LABELS[type_value], difficulty_value, questions
            )
        )
        await asyncio.sleep(3)
        self.spawn(channel, q_types, difficulty_value, questions)


async def setup(bot: commands.Bot):
    await bot.add_cog(Quizz(bot))
