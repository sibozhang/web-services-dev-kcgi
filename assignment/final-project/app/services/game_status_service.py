from enum import StrEnum


class GameStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINAL = "FINAL"
    DELAYED = "DELAYED"
    POSTPONED = "POSTPONED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


def normalize_game_status(status: dict | None) -> GameStatus:
    status = status or {}
    abstract = str(status.get("abstractGameState", "")).lower()
    detailed = str(status.get("detailedState", "")).lower()
    coded = str(status.get("codedGameState", "")).upper()
    text = f"{abstract} {detailed}"

    if "postpon" in text:
        return GameStatus.POSTPONED
    if "suspend" in text:
        return GameStatus.SUSPENDED
    if "cancel" in text:
        return GameStatus.CANCELLED
    if "delay" in text:
        return GameStatus.DELAYED
    if abstract == "final" or coded in {"F", "O"}:
        return GameStatus.FINAL
    if abstract == "live" or coded in {"I", "M", "N"}:
        return GameStatus.LIVE
    if abstract in {"preview", "pre-game"} or coded in {"S", "P"}:
        return GameStatus.SCHEDULED
    return GameStatus.UNKNOWN

