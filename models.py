import re

from sqlalchemy import (
    DECIMAL,
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql import func

Base = declarative_base()

GAME_MK8DX = "mk8dx"
GAME_MKWORLD = "mkworld"
GAME_MKWII = "mkwii"
VALID_GAMES = [GAME_MK8DX, GAME_MKWORLD, GAME_MKWII]


class Cup(Base):
    """Cups (track groups) for different Mario Kart games"""

    __tablename__ = "cups"

    id = Column(Integer, primary_key=True)
    game = Column(String(20), nullable=False)
    cup_name = Column(String(100), nullable=False)
    cup_emoji_name = Column(String(50), nullable=False)
    cup_emoji_id = Column(String(50), nullable=False)
    cup_url = Column(Text)
    tracks: Mapped[list["Track"]] = relationship(
        "Track", back_populates="cup", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cups_game_emoji_name", "game", "cup_emoji_name"),
        Index("ix_cups_game_id", "game", "id"),
        Index("ix_cups_unique_game_id", "game", "id", unique=True),
    )


class Track(Base):
    """Tracks for different Mario Kart games"""

    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game = Column(String(20), nullable=False)
    track_id = Column(Integer, nullable=False)
    track_name = Column(String(50), nullable=False)
    full_name = Column(String(200), nullable=False)
    track_url = Column(Text)
    cup_id = Column(Integer, ForeignKey("cups.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cup: Mapped["Cup"] = relationship("Cup", back_populates="tracks")
    time_records: Mapped[list["TimeRecord"]] = relationship(
        "TimeRecord", back_populates="track", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tracks_game_track_name", "game", "track_name"),
        Index("ix_tracks_game_track_id", "game", "track_id"),
        Index("ix_tracks_cup_id", "cup_id"),
        Index("ix_tracks_unique_game_track_id", "game", "track_id", unique=True),
        Index("ix_tracks_unique_game_track_name", "game", "track_name", unique=True),
    )


class User(Base):
    """Discord users"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    server_memberships: Mapped[list["UserServer"]] = relationship(
        "UserServer", back_populates="user", cascade="all, delete-orphan"
    )
    time_records: Mapped[list["TimeRecord"]] = relationship(
        "TimeRecord", back_populates="user", cascade="all, delete-orphan"
    )
    __table_args__ = (Index("ix_users_discord_id", "discord_id"),)


class UserServer(Base):
    """Tracks which Discord servers a user is registered in"""

    __tablename__ = "user_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    server_id = Column(BigInteger, nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="server_memberships")
    __table_args__ = (
        Index("ix_user_servers_user_server", "user_id", "server_id"),
        Index("ix_user_servers_server_id", "server_id"),
    )


class TimeRecord(Base):
    """Individual time records for tracks across different games"""

    __tablename__ = "time_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    game = Column(String(20), nullable=False)

    time = Column(String(8), nullable=False)

    race_type = Column(String(2), nullable=False)

    speed = Column(Integer, nullable=False)

    time_milliseconds = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="time_records")
    track: Mapped["Track"] = relationship("Track", back_populates="time_records")

    __table_args__ = (
        Index(
            "ix_time_records_unique",
            "user_id",
            "track_id",
            "game",
            "race_type",
            "speed",
            unique=True,
        ),
        Index("ix_time_records_game", "game"),
        Index("ix_time_records_race_type", "race_type"),
        Index("ix_time_records_speed", "speed"),
        Index("ix_time_records_time_ms", "time_milliseconds"),
        Index(
            "ix_time_records_user_game_race", "user_id", "game", "race_type", "speed"
        ),
        Index(
            "ix_time_records_track_game_race", "track_id", "game", "race_type", "speed"
        ),
    )

    @staticmethod
    def time_to_milliseconds(time_str: str) -> int:
        """Convert time string M:SS.mmm to milliseconds"""
        if not re.match(r"^\d:[0-5]\d\.\d{3}$", time_str):
            raise ValueError(f"Invalid time format: {time_str}")

        parts = time_str.split(":")
        minutes = int(parts[0])
        seconds_parts = parts[1].split(".")
        seconds = int(seconds_parts[0])
        milliseconds = int(seconds_parts[1])

        return (minutes * 60 * 1000) + (seconds * 1000) + milliseconds

    @staticmethod
    def milliseconds_to_time(milliseconds: int) -> str:
        """Convert milliseconds to time string M:SS.mmm"""
        ms = milliseconds % 1000
        total_seconds = milliseconds // 1000
        seconds = total_seconds % 60
        minutes = total_seconds // 60

        return f"{minutes}:{seconds:02d}.{ms:03d}"


class WarEvent(Base):
    """War/battle events (overall match between teams) for different games"""

    __tablename__ = "war_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game = Column(String(20), nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    tag = Column(String(100), nullable=False)
    enemy_tag = Column(String(100), nullable=False)

    incoming_track = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    races: Mapped[list["Race"]] = relationship(
        "Race", back_populates="war_event", cascade="all, delete-orphan"
    )
    __table_args__ = (
        Index("ix_war_events_game", "game"),
        Index("ix_war_events_channel_id", "channel_id"),
        Index("ix_war_events_date", "date"),
        Index("ix_war_events_game_tags", "game", "tag", "enemy_tag"),
    )


class Race(Base):
    """Individual races within a war event for different games"""

    __tablename__ = "races"

    id = Column(Integer, primary_key=True, autoincrement=True)
    war_event_id = Column(Integer, ForeignKey("war_events.id"), nullable=False)
    game = Column(String(20), nullable=False)
    race_number = Column(Integer, nullable=False)
    track_name = Column(String(50), nullable=True)

    home_score = Column(DECIMAL(5, 1), nullable=False)
    enemy_score = Column(DECIMAL(5, 1), nullable=False)
    score_diff = Column(Integer, nullable=False)

    positions = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    war_event: Mapped["WarEvent"] = relationship("WarEvent", back_populates="races")
    track: Mapped["Track"] = relationship(
        "Track",
        foreign_keys=[track_name],
        primaryjoin="and_(Race.track_name == Track.track_name, Race.game == Track.game)",
    )
    __table_args__ = (
        Index("ix_races_game", "game"),
        Index("ix_races_war_event", "war_event_id"),
        Index("ix_races_game_track", "game", "track_name"),
        Index("ix_races_war_race", "war_event_id", "race_number", unique=True),
    )


def validate_time_format(time_str: str) -> bool:
    """Validate time format M:SS.mmm"""
    return bool(re.match(r"^\d:[0-5]\d\.\d{3}$", time_str))


def validate_race_type(race_type: str) -> bool:
    """Validate race type"""
    valid_types = ["sh", "ni"]
    return race_type in valid_types


def validate_speed(speed: int) -> bool:
    """Validate speed"""
    valid_speeds = [150, 200]
    return speed in valid_speeds


def get_user_by_discord_id(session, discord_id: int):
    """Get user by Discord ID"""
    return session.query(User).filter(User.discord_id == discord_id).first()


def get_track_by_name(session, track_name: str):
    """Get track by name (case-insensitive)"""
    return session.query(Track).filter(Track.track_name.ilike(track_name)).first()


def get_user_time_record(
    session, user_id: int, track_id: int, game: str, race_type: str, speed: int
):
    """Get a user's time record for a specific track, game, race type, and speed"""
    return (
        session.query(TimeRecord)
        .filter(
            TimeRecord.user_id == user_id,
            TimeRecord.track_id == track_id,
            TimeRecord.game == game,
            TimeRecord.race_type == race_type,
            TimeRecord.speed == speed,
        )
        .first()
    )


def get_leaderboard(
    session, track_id: int, game: str, race_type: str, speed: int, limit: int = None
):
    """Get leaderboard for a track, game, race type, and speed"""
    query = (
        session.query(TimeRecord)
        .filter(
            TimeRecord.track_id == track_id,
            TimeRecord.game == game,
            TimeRecord.race_type == race_type,
            TimeRecord.speed == speed,
        )
        .order_by(TimeRecord.time_milliseconds)
    )

    if limit:
        query = query.limit(limit)

    return query.all()
