"""A single quiz session running in one channel. Players answer in chat."""

import asyncio
import unicodedata

import discord

from cogs.quizz.maps import generate_country_map, generate_country_shape
from cogs.quizz.questions import generate_questions

QUESTION_TIMEOUT = 15
INTER_QUESTION_GAP = 3
# Stop the quiz once this many questions in a row pass with nobody chatting.
MAX_INACTIVE_STREAK = 2


def _normalize(text: str) -> str:
    """Lower-case, strip accents, and drop everything that isn't a letter or
    digit. This forgives differences in special characters only — spaces,
    dashes, apostrophes, dots — but not actual typos (Iran ≠ Iraq)."""
    nfkd = unicodedata.normalize("NFKD", text.lower().strip())
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return "".join(c for c in stripped if c.isalnum())


def _progress_bar(current: int, total: int, width: int = 12) -> str:
    filled = round(width * current / max(total, 1))
    return "█" * filled + "░" * (width - filled)


class QuizSession:
    def __init__(self, channel, bot, question_types, difficulty, num_questions):
        self.channel = channel
        self.bot = bot
        self.question_types = question_types
        self.difficulty = difficulty
        self.num_questions = num_questions

        self.scores: dict[int, int] = {}
        self.usernames: dict[int, str] = {}
        self.questions: list[dict] = []
        self.current_idx = 0
        self.is_active = True
        self.inactive_streak = 0
        self.task: asyncio.Task | None = None

    async def start(self):
        self.questions = generate_questions(
            self.question_types, self.difficulty, self.num_questions
        )
        self.num_questions = len(self.questions)
        try:
            for i, question in enumerate(self.questions):
                if not self.is_active:
                    break
                self.current_idx = i
                await self._ask_question(i, question)
                if self.is_active and i < self.num_questions - 1:
                    await asyncio.sleep(INTER_QUESTION_GAP)
            if self.is_active:
                await self._show_final_scores()
        except asyncio.CancelledError:
            pass
        finally:
            self.is_active = False

    def stop(self):
        self.is_active = False
        if self.task:
            self.task.cancel()

    async def _ask_question(self, idx: int, question: dict):
        embed = self._build_question_embed(idx, question)
        file: discord.File | None = None

        if question["type"] == "flag":
            embed.set_image(
                url=f"https://flagcdn.com/w640/{question['iso2'].lower()}.png"
            )
        elif question["type"] == "map":
            try:
                map_io = await generate_country_map(question["country_en"])
                file = discord.File(map_io, filename="map.png")
                embed.set_image(url="attachment://map.png")
            except Exception as exc:
                print(f"[quizz] map error: {exc}")
        elif question["type"] == "shape":
            try:
                shape_io = await generate_country_shape(question["country_en"])
                file = discord.File(shape_io, filename="shape.png")
                embed.set_image(url="attachment://shape.png")
            except Exception as exc:
                print(f"[quizz] shape error: {exc}")

        await self.channel.send(embed=embed, file=file)

        accepted = [question["answer"], *question.get("aliases", [])]
        accepted_norm = {_normalize(a) for a in accepted}
        correct_users: list[discord.User] = []
        correct_ids: set[int] = set()
        participated = False

        def check(m: discord.Message) -> bool:
            return (
                m.channel.id == self.channel.id
                and not m.author.bot
                and m.author.id not in correct_ids
            )

        end_time = asyncio.get_event_loop().time() + QUESTION_TIMEOUT
        while self.is_active:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                reply = await asyncio.wait_for(
                    self.bot.wait_for("message", check=check),
                    timeout=min(remaining, 1.0),
                )
                participated = True
                if _normalize(reply.content) in accepted_norm:
                    correct_ids.add(reply.author.id)
                    correct_users.append(reply.author)
                    asyncio.create_task(reply.add_reaction("✅"))
                    break
            except asyncio.TimeoutError:
                continue

        if not self.is_active:
            return

        for user in correct_users:
            if user.id not in self.scores:
                self.scores[user.id] = 0
                self.usernames[user.id] = user.display_name
            self.scores[user.id] += 1

        await self.channel.send(
            embed=self._build_result_embed(idx, question, correct_users)
        )

        # Abandon the quiz if the channel has gone quiet for too long.
        self.inactive_streak = 0 if participated else self.inactive_streak + 1
        if self.inactive_streak >= MAX_INACTIVE_STREAK:
            self.is_active = False
            await self.channel.send(
                embed=discord.Embed(
                    title="⏹️ Quiz stopped",
                    description="No one is playing — stopping the quiz.",
                    color=0xE74C3C,
                )
            )

    def _build_question_embed(self, idx: int, question: dict) -> discord.Embed:
        total = self.num_questions
        bar = _progress_bar(idx + 1, total)

        type_to_color = {
            "flag": 0x3498DB,
            "capital": 0x9B59B6,
            "map": 0xE67E22,
            "shape": 0x1ABC9C,
        }
        color = type_to_color.get(question["type"], 0x3498DB)

        embed = discord.Embed(
            title=f"Question {idx + 1} / {total}  [{bar}]",
            description=question["text"],
            color=color,
        )
        embed.set_footer(text=f"✏️ Type your answer · ⏱️ {QUESTION_TIMEOUT}s")
        return embed

    def _build_result_embed(
        self, idx: int, question: dict, correct_users: list
    ) -> discord.Embed:
        answer = question.get("display_answer", question["answer"])
        if correct_users:
            names = ", ".join(u.display_name for u in correct_users)
            return discord.Embed(
                description=f"✅ **{answer}** · 🎉 {names}",
                color=0x2ECC71,
            )
        return discord.Embed(
            description=f"❌ **{answer}**",
            color=0xE74C3C,
        )

    async def _show_final_scores(self):
        if not self.scores:
            await self.channel.send(
                embed=discord.Embed(
                    title="🏁 Quiz Over!",
                    description="No one took part… empty quiz 🌵",
                    color=0xE74C3C,
                )
            )
            return

        sorted_scores = sorted(self.scores.items(), key=lambda x: -x[1])
        medals = ["🥇", "🥈", "🥉"]
        lines = [
            f"{medals[i] if i < 3 else f'#{i + 1}'} **{self.usernames.get(uid, 'Unknown')}** : "
            f"{pts} / {self.num_questions} pt{'s' if pts != 1 else ''}"
            for i, (uid, pts) in enumerate(sorted_scores)
        ]

        embed = discord.Embed(
            title="🏁 Quiz Over! Final results",
            description="\n".join(lines),
            color=0xF1C40F,
        )
        embed.set_footer(text="Thanks for playing! · /quiz to play again")
        await self.channel.send(embed=embed)
