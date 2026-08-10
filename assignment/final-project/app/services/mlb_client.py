import json
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class MLBClientError(RuntimeError):
    pass


class MLBClient:
    RETRY_STATUSES = (429, 500, 502, 503, 504)

    def __init__(
        self,
        base_url: str = "https://statsapi.mlb.com/api/v1",
        connect_timeout: float = 3.05,
        read_timeout: float = 15,
        session: requests.Session | None = None,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = (connect_timeout, read_timeout)
        self.session = session or requests.Session()
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=0.5,
            status_forcelist=self.RETRY_STATUSES,
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "KCGI-MLB-Dugout/1.0 (educational project)",
            }
        )

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        base_url: str | None = None,
    ) -> dict:
        url = f"{(base_url or self.base_url).rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, params=params or {}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise MLBClientError(f"MLB API request failed: {endpoint}") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise MLBClientError(f"MLB API returned invalid JSON: {endpoint}") from exc
        if not isinstance(payload, dict):
            raise MLBClientError(f"MLB API returned an unexpected payload: {endpoint}")
        return payload

    def teams(self) -> dict:
        return self.get("teams", {"sportId": 1, "hydrate": "venue,division,league"})

    def schedule(self, start: str, end: str) -> dict:
        return self.get(
            "schedule",
            {
                "sportId": 1,
                "startDate": start,
                "endDate": end,
                "hydrate": "team,probablePitcher,linescore,venue,decisions",
            },
        )

    def standings(self, season: int) -> dict:
        return self.get(
            "standings",
            {
                "leagueId": "103,104",
                "season": season,
                "standingsTypes": "regularSeason",
                "hydrate": "division,team",
            },
        )

    def roster(
        self,
        team_id: int,
        season: int,
        roster_type: str = "active",
        *,
        hydrate_stats: bool = False,
    ) -> dict:
        hydrate = "person"
        if hydrate_stats:
            hydrate = (
                "person(stats(group=[hitting,pitching],"
                f"type=[season],season={season}))"
            )
        return self.get(
            f"teams/{team_id}/roster",
            {
                "season": season,
                "rosterType": roster_type,
                "hydrate": hydrate,
            },
        )

    def team_stats(self, team_id: int, season: int) -> dict:
        return self.get(
            f"teams/{team_id}/stats",
            {"stats": "season", "group": "hitting,pitching", "season": season},
        )

    def player_stats(self, player_id: int, season: int) -> dict:
        return self.get(
            f"people/{player_id}/stats",
            {"stats": "season", "group": "hitting,pitching", "season": season},
        )

    def boxscore(self, game_pk: int) -> dict:
        return self.get(f"game/{game_pk}/boxscore")

    def live_feed(self, game_pk: int) -> dict:
        live_base_url = (
            self.base_url.removesuffix("/v1") + "/v1.1"
            if self.base_url.endswith("/v1")
            else self.base_url
        )
        return self.get(f"game/{game_pk}/feed/live", base_url=live_base_url)
