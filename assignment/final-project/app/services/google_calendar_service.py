from datetime import datetime, timedelta, timezone

import requests

from app.extensions import db
from app.models import CalendarGameEvent, Game, GoogleCalendarToken
from app.services.token_service import TokenCipher


class CalendarServiceError(RuntimeError):
    pass


class GoogleCalendarService:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cipher: TokenCipher,
        base_url: str,
        session: requests.Session | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cipher = cipher
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _access_token(self, token: GoogleCalendarToken) -> str:
        now = datetime.now(timezone.utc)
        expires_at = token.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not expires_at or expires_at > now + timedelta(minutes=1):
            return self.cipher.decrypt(token.encrypted_access_token) or ""
        refresh_token = self.cipher.decrypt(token.encrypted_refresh_token)
        if not refresh_token:
            raise CalendarServiceError("Google Calendar 授权已过期，请重新连接。")
        try:
            response = self.session.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=(3.05, 15),
            )
            response.raise_for_status()
            payload = response.json()
            access_token = payload["access_token"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            db.session.delete(token)
            db.session.commit()
            raise CalendarServiceError("Google 授权已失效，请重新连接 Calendar。") from exc
        token.encrypted_access_token = self.cipher.encrypt(access_token)
        token.expires_at = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
        db.session.commit()
        return access_token

    def add_game(self, user_id: int, game: Game) -> tuple[CalendarGameEvent, bool]:
        existing = db.session.execute(
            db.select(CalendarGameEvent).where(
                CalendarGameEvent.user_id == user_id,
                CalendarGameEvent.game_pk == game.game_pk,
            )
        ).scalar_one_or_none()
        if existing:
            return existing, True
        now = datetime.now(timezone.utc)
        game_time = game.start_time_utc
        if game_time.tzinfo is None:
            game_time = game_time.replace(tzinfo=timezone.utc)
        if game_time <= now:
            raise CalendarServiceError("过去的比赛不能添加到 Calendar。")
        if game.normalized_status in {"POSTPONED", "CANCELLED", "SUSPENDED"}:
            raise CalendarServiceError("该比赛当前为延期、取消或暂停状态，暂不能添加。")
        token = db.session.execute(
            db.select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user_id)
        ).scalar_one_or_none()
        if token is None:
            raise CalendarServiceError("请先连接 Google Calendar。")
        access_token = self._access_token(token)
        body = {
            "summary": f"{game.away_team.name} @ {game.home_team.name}",
            "description": (
                f"球场：{game.venue_name or '待定'}\n"
                f"比赛页面：{self.base_url}/games/{game.game_pk}\n"
                f"MLB gamePk：{game.game_pk}"
            ),
            "start": {"dateTime": game.start_time_jst.isoformat(), "timeZone": "Asia/Tokyo"},
            "end": {
                "dateTime": (game.start_time_jst + timedelta(hours=3)).isoformat(),
                "timeZone": "Asia/Tokyo",
            },
        }
        try:
            response = self.session.post(
                self.EVENTS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json=body,
                timeout=(3.05, 15),
            )
            if response.status_code in {401, 403}:
                db.session.delete(token)
                db.session.commit()
                raise CalendarServiceError("Google 授权已撤销，请重新连接 Calendar。")
            response.raise_for_status()
            event_id = response.json()["id"]
        except CalendarServiceError:
            raise
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise CalendarServiceError("Google Calendar 暂时不可用，请稍后重试。") from exc
        event = CalendarGameEvent(
            user_id=user_id, game_pk=game.game_pk, google_event_id=event_id
        )
        db.session.add(event)
        db.session.commit()
        return event, False
