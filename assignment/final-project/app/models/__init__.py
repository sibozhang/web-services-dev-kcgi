from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return bool(self.password_hash and check_password_hash(self.password_hash, password))


class OAuthAccount(db.Model):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = db.Column(db.String(40), nullable=False)
    provider_subject = db.Column(db.String(255), nullable=False)
    provider_email = db.Column(db.String(320))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("oauth_accounts", cascade="all, delete-orphan"))


class GoogleCalendarToken(db.Model):
    __tablename__ = "google_calendar_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    encrypted_access_token = db.Column(db.Text, nullable=False)
    encrypted_refresh_token = db.Column(db.Text)
    expires_at = db.Column(db.DateTime(timezone=True))
    scopes = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("calendar_token", uselist=False))


class CalendarGameEvent(db.Model):
    __tablename__ = "calendar_game_events"
    __table_args__ = (
        UniqueConstraint("user_id", "game_pk", name="uq_calendar_user_game"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_pk = db.Column(db.BigInteger, db.ForeignKey("games.game_pk", ondelete="CASCADE"), nullable=False)
    google_event_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class Team(TimestampMixin, db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    mlb_team_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    abbreviation = db.Column(db.String(10), nullable=False)
    league = db.Column(db.String(40), nullable=False)
    division = db.Column(db.String(40), nullable=False)
    logo_url = db.Column(db.String(500))
    venue_name = db.Column(db.String(160))


class Player(TimestampMixin, db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    mlb_player_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    primary_position = db.Column(db.String(50))
    bat_side = db.Column(db.String(20))
    pitch_hand = db.Column(db.String(20))
    birth_date = db.Column(db.Date)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Roster(TimestampMixin, db.Model):
    __tablename__ = "rosters"
    __table_args__ = (
        UniqueConstraint("team_id", "player_id", "season", name="uq_roster_team_player_season"),
    )

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season = db.Column(db.Integer, nullable=False)
    jersey_number = db.Column(db.String(10))
    position = db.Column(db.String(50))
    roster_status = db.Column(db.String(50))
    team = db.relationship("Team", backref="roster_entries")
    player = db.relationship("Player", backref="roster_entries")


class Game(TimestampMixin, db.Model):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            "normalized_status IN ('SCHEDULED','LIVE','FINAL','DELAYED','POSTPONED',"
            "'SUSPENDED','CANCELLED','UNKNOWN')",
            name="game_normalized_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    game_pk = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    season = db.Column(db.Integer, nullable=False)
    game_type = db.Column(db.String(10))
    official_date = db.Column(db.Date, nullable=False)
    start_time_utc = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    start_time_jst = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    abstract_status = db.Column(db.String(50))
    detailed_status = db.Column(db.String(100))
    normalized_status = db.Column(db.String(20), nullable=False, default="UNKNOWN")
    current_inning = db.Column(db.Integer)
    inning_half = db.Column(db.String(20))
    venue_name = db.Column(db.String(160))
    probable_home_pitcher_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    probable_away_pitcher_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    winning_pitcher_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    losing_pitcher_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    save_pitcher_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    home_team = db.relationship("Team", foreign_keys=[home_team_id], backref="home_games")
    away_team = db.relationship("Team", foreign_keys=[away_team_id], backref="away_games")
    probable_home_pitcher = db.relationship("Player", foreign_keys=[probable_home_pitcher_id])
    probable_away_pitcher = db.relationship("Player", foreign_keys=[probable_away_pitcher_id])
    winning_pitcher = db.relationship("Player", foreign_keys=[winning_pitcher_id])
    losing_pitcher = db.relationship("Player", foreign_keys=[losing_pitcher_id])
    save_pitcher = db.relationship("Player", foreign_keys=[save_pitcher_id])


class Standing(TimestampMixin, db.Model):
    __tablename__ = "standings"
    __table_args__ = (
        UniqueConstraint("season", "team_id", name="uq_standing_season_team"),
    )

    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    wins = db.Column(db.Integer, nullable=False, default=0)
    losses = db.Column(db.Integer, nullable=False, default=0)
    winning_percentage = db.Column(db.Numeric(5, 3))
    games_back = db.Column(db.String(10))
    division_rank = db.Column(db.Integer)
    league_rank = db.Column(db.Integer)
    home_wins = db.Column(db.Integer, default=0)
    home_losses = db.Column(db.Integer, default=0)
    away_wins = db.Column(db.Integer, default=0)
    away_losses = db.Column(db.Integer, default=0)
    last_ten_wins = db.Column(db.Integer, default=0)
    last_ten_losses = db.Column(db.Integer, default=0)
    streak = db.Column(db.String(10))
    runs_scored = db.Column(db.Integer, default=0)
    runs_allowed = db.Column(db.Integer, default=0)
    team = db.relationship("Team", backref="standings")

    @hybrid_property
    def run_differential(self):
        return (self.runs_scored or 0) - (self.runs_allowed or 0)


class TeamSeasonStats(TimestampMixin, db.Model):
    __tablename__ = "team_season_stats"
    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_team_stats_team_season"),
    )

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    season = db.Column(db.Integer, nullable=False)
    games_played = db.Column(db.Integer)
    batting_avg = db.Column(db.Numeric(5, 3))
    obp = db.Column(db.Numeric(5, 3))
    slg = db.Column(db.Numeric(5, 3))
    ops = db.Column(db.Numeric(5, 3))
    runs = db.Column(db.Integer)
    hits = db.Column(db.Integer)
    home_runs = db.Column(db.Integer)
    batting_strikeouts = db.Column(db.Integer)
    batting_walks = db.Column(db.Integer)
    era = db.Column(db.Numeric(6, 2))
    whip = db.Column(db.Numeric(6, 2))
    wins = db.Column(db.Integer)
    losses = db.Column(db.Integer)
    saves = db.Column(db.Integer)
    pitching_strikeouts = db.Column(db.Integer)
    pitching_walks = db.Column(db.Integer)
    home_runs_allowed = db.Column(db.Integer)
    team = db.relationship("Team", backref="season_stats")


class PlayerHittingStats(TimestampMixin, db.Model):
    __tablename__ = "player_hitting_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "team_id", "season", name="uq_hitting_player_team_season"),
    )

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    season = db.Column(db.Integer, nullable=False)
    games_played = db.Column(db.Integer)
    plate_appearances = db.Column(db.Integer)
    at_bats = db.Column(db.Integer)
    runs = db.Column(db.Integer)
    hits = db.Column(db.Integer)
    doubles = db.Column(db.Integer)
    triples = db.Column(db.Integer)
    home_runs = db.Column(db.Integer)
    rbi = db.Column(db.Integer)
    walks = db.Column(db.Integer)
    strikeouts = db.Column(db.Integer)
    stolen_bases = db.Column(db.Integer)
    avg = db.Column(db.Numeric(5, 3))
    obp = db.Column(db.Numeric(5, 3))
    slg = db.Column(db.Numeric(5, 3))
    ops = db.Column(db.Numeric(5, 3))
    player = db.relationship("Player", backref="hitting_stats")
    team = db.relationship("Team")


class PlayerPitchingStats(TimestampMixin, db.Model):
    __tablename__ = "player_pitching_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "team_id", "season", name="uq_pitching_player_team_season"),
    )

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    season = db.Column(db.Integer, nullable=False)
    games_played = db.Column(db.Integer)
    games_started = db.Column(db.Integer)
    wins = db.Column(db.Integer)
    losses = db.Column(db.Integer)
    saves = db.Column(db.Integer)
    innings_outs = db.Column(db.Integer, nullable=False, default=0)
    hits = db.Column(db.Integer)
    earned_runs = db.Column(db.Integer)
    home_runs = db.Column(db.Integer)
    walks = db.Column(db.Integer)
    strikeouts = db.Column(db.Integer)
    era = db.Column(db.Numeric(6, 2))
    whip = db.Column(db.Numeric(6, 2))
    player = db.relationship("Player", backref="pitching_stats")
    team = db.relationship("Team")

    @property
    def innings_pitched(self) -> str:
        return f"{self.innings_outs // 3}.{self.innings_outs % 3}"


class GameSnapshot(db.Model):
    __tablename__ = "game_snapshots"
    __table_args__ = (
        UniqueConstraint("game_pk", "snapshot_type", "source_hash", name="uq_snapshot_source"),
    )

    id = db.Column(db.Integer, primary_key=True)
    game_pk = db.Column(db.BigInteger, db.ForeignKey("games.game_pk"), nullable=False)
    snapshot_type = db.Column(db.String(30), nullable=False)
    inning = db.Column(db.Integer)
    source_hash = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class AIAnalysis(db.Model):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        UniqueConstraint(
            "game_pk", "player_id", "analysis_type", "source_hash", name="uq_ai_analysis_source"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    game_pk = db.Column(db.BigInteger, db.ForeignKey("games.game_pk"))
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"))
    analysis_type = db.Column(db.String(20), nullable=False)
    source_hash = db.Column(db.String(64), nullable=False, index=True)
    model_name = db.Column(db.String(120), nullable=False)
    prompt_version = db.Column(db.String(30), nullable=False)
    content = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class ApiResponse(db.Model):
    __tablename__ = "api_responses"

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(255), unique=True, nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    params_hash = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)


__all__ = [
    "AIAnalysis",
    "ApiResponse",
    "CalendarGameEvent",
    "Game",
    "GameSnapshot",
    "GoogleCalendarToken",
    "OAuthAccount",
    "Player",
    "PlayerHittingStats",
    "PlayerPitchingStats",
    "Roster",
    "Standing",
    "Team",
    "TeamSeasonStats",
    "User",
]
