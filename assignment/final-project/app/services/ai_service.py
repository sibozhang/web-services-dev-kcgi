import hashlib
import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.extensions import db
from app.models import AIAnalysis, Game, Player
from app.services.game_context_service import (
    probable_pitching_stats_by_game,
    recent_team_records,
)


logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    pass


class PregameAnalysisUnavailable(AIServiceError):
    pass


class AIRateLimitError(AIServiceError):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Gemini 免费配额暂时受限，请在 {retry_after} 秒后重试。")


class AIService:
    PROMPT_VERSION = "post-game-v6"
    PROMPT_VERSIONS = {
        "PRE_GAME": "pre-game-v2",
        "LIVE": "live-v6",
        "POST_GAME": PROMPT_VERSION,
        "PLAYER": "player-v1",
    }

    def __init__(
        self,
        api_key: str,
        model_name: str,
        timeout: tuple[float, float] = (3.05, 45),
        session: requests.Session | None = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.session = session or requests.Session()
        retry = Retry(
            total=2,
            status=2,
            connect=2,
            read=0,
            backoff_factor=0.7,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    @staticmethod
    def source_hash(source: dict) -> str:
        canonical = json.dumps(source, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> int:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        details = ((payload.get("error") or {}).get("details") or [])
        for detail in details:
            if str(detail.get("@type", "")).endswith("RetryInfo"):
                value = str(detail.get("retryDelay") or "")
                match = re.match(r"([0-9.]+)s", value)
                if match:
                    return max(1, min(300, math.ceil(float(match.group(1)))))
        message = str((payload.get("error") or {}).get("message") or "")
        match = re.search(r"retry in ([0-9.]+)s", message, re.IGNORECASE)
        if match:
            return max(1, min(300, math.ceil(float(match.group(1)))))
        return 60

    @staticmethod
    def _latest_analysis(
        game_pk: int,
        analysis_type: str,
        language: str = "zh",
    ) -> AIAnalysis | None:
        query = db.select(AIAnalysis).where(
            AIAnalysis.game_pk == game_pk,
            AIAnalysis.analysis_type == analysis_type,
        )
        query = query.where(
            AIAnalysis.prompt_version.like("%-ja")
            if language == "ja"
            else AIAnalysis.prompt_version.not_like("%-ja")
        )
        return db.session.execute(
            query.order_by(AIAnalysis.created_at.desc()).limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def _compact_boxscore(
        boxscore: dict | None, *, include_bullpen: bool = False
    ) -> dict:
        if not boxscore:
            return {}
        batting_keys = (
            "name",
            "position",
            "at_bats",
            "runs",
            "hits",
            "home_runs",
            "rbi",
            "walks",
            "strikeouts",
        )
        pitching_keys = (
            "name",
            "role",
            "innings",
            "hits",
            "runs",
            "earned_runs",
            "walks",
            "strikeouts",
            "home_runs",
            "note",
        )
        batting_total_keys = (
            "atBats",
            "runs",
            "hits",
            "rbi",
            "baseOnBalls",
            "strikeOuts",
            "homeRuns",
        )
        pitching_total_keys = (
            "inningsPitched",
            "hits",
            "runs",
            "earnedRuns",
            "baseOnBalls",
            "strikeOuts",
            "homeRuns",
        )
        bullpen_keys = (
            "name",
            "games",
            "innings",
            "era",
            "whip",
            "saves",
            "holds",
            "blown_saves",
            "strikeouts",
            "walks",
            "listed_in_bullpen",
        )
        result = {}
        for side in ("away", "home"):
            team = boxscore.get(side) or {}
            batters = sorted(
                team.get("batters") or [],
                key=lambda row: (
                    row.get("rbi") or 0,
                    row.get("hits") or 0,
                    row.get("runs") or 0,
                    row.get("walks") or 0,
                ),
                reverse=True,
            )[:6]
            result[side] = {
                "team_name": team.get("team_name"),
                "key_batters": [
                    {key: row.get(key) for key in batting_keys}
                    for row in batters
                ],
                "pitchers": [
                    {key: row.get(key) for key in pitching_keys}
                    for row in (team.get("pitchers") or [])[:6]
                ],
                "batting_totals": {
                    key: (team.get("batting_totals") or {}).get(key)
                    for key in batting_total_keys
                },
                "pitching_totals": {
                    key: (team.get("pitching_totals") or {}).get(key)
                    for key in pitching_total_keys
                },
            }
            if include_bullpen:
                bullpen = sorted(
                    team.get("bullpen") or [],
                    key=lambda row: (
                        row.get("saves") or 0,
                        row.get("holds") or 0,
                        row.get("games") or 0,
                    ),
                    reverse=True,
                )[:5]
                result[side]["listed_bullpen"] = [
                    {key: row.get(key) for key in bullpen_keys}
                    for row in bullpen
                ]
        return result

    @staticmethod
    def _pitcher_context(pitcher, stats) -> dict | None:
        if pitcher is None:
            return None
        season_stats = None
        if stats is not None:
            games = stats.games_played or 0
            starts = stats.games_started or 0
            if games and starts == 0:
                usage_pattern = "relief_only_so_far"
            elif games and starts * 2 < games:
                usage_pattern = "mixed_relief_or_opener_usage"
            elif starts:
                usage_pattern = "regular_starter_usage"
            else:
                usage_pattern = "insufficient_usage_data"
            season_stats = {
                "games": stats.games_played,
                "games_started": stats.games_started,
                "wins": stats.wins,
                "losses": stats.losses,
                "innings_pitched": stats.innings_pitched,
                "era": str(stats.era) if stats.era is not None else None,
                "whip": str(stats.whip) if stats.whip is not None else None,
                "strikeouts": stats.strikeouts,
                "walks": stats.walks,
                "usage_pattern": usage_pattern,
            }
        return {
            "name": pitcher.full_name,
            "season_stats": season_stats,
        }

    @classmethod
    def game_source(cls, game: Game, snapshot: dict | None = None) -> dict:
        details = dict(snapshot or {})
        details["boxscore"] = cls._compact_boxscore(
            details.get("boxscore"),
            include_bullpen=game.normalized_status == "LIVE",
        )
        source = {
            "game_pk": game.game_pk,
            "status": game.normalized_status,
            "start_time_jst": game.start_time_jst.isoformat(),
            "venue": game.venue_name,
            "away": {
                "name": game.away_team.name,
                "score": game.away_score,
                "probable_pitcher": (
                    game.probable_away_pitcher.full_name
                    if game.probable_away_pitcher
                    else None
                ),
            },
            "home": {
                "name": game.home_team.name,
                "score": game.home_score,
                "probable_pitcher": (
                    game.probable_home_pitcher.full_name
                    if game.probable_home_pitcher
                    else None
                ),
            },
            "inning": game.current_inning,
            "inning_half": game.inning_half,
            "decisions": {
                "winning_pitcher": (
                    game.winning_pitcher.full_name if game.winning_pitcher else None
                ),
                "losing_pitcher": (
                    game.losing_pitcher.full_name if game.losing_pitcher else None
                ),
                "save_pitcher": (
                    game.save_pitcher.full_name if game.save_pitcher else None
                ),
            },
            "game_details": details,
        }
        if game.normalized_status not in ("LIVE", "FINAL"):
            probable_stats = probable_pitching_stats_by_game([game]).get(
                game.game_pk, {}
            )
            source["pregame_context"] = {
                "away_probable_pitcher": cls._pitcher_context(
                    game.probable_away_pitcher, probable_stats.get("away")
                ),
                "home_probable_pitcher": cls._pitcher_context(
                    game.probable_home_pitcher, probable_stats.get("home")
                ),
                "recent_10": recent_team_records(game),
            }
        return source

    @classmethod
    def prompt_version_for(cls, analysis_type: str, language: str = "zh") -> str:
        version = cls.PROMPT_VERSIONS.get(analysis_type, cls.PROMPT_VERSION)
        return f"{version}-ja" if language == "ja" else version

    def cache_hash(
        self,
        source: dict,
        analysis_type: str | None = None,
        language: str = "zh",
    ) -> str:
        if analysis_type is None:
            status = source.get("status")
            analysis_type = (
                "POST_GAME"
                if status == "FINAL"
                else "LIVE" if status == "LIVE" else "PRE_GAME"
            )
        return self.source_hash(
            {
                "model_name": self.model_name,
                "prompt_version": self.prompt_version_for(analysis_type, language),
                "source": source,
            }
        )

    @staticmethod
    def analysis_type_for(game: Game) -> str:
        if game.normalized_status == "FINAL":
            return "POST_GAME"
        if game.normalized_status == "LIVE":
            return "LIVE"
        return "PRE_GAME"

    @staticmethod
    def _instructions(analysis_type: str, language: str = "zh") -> str:
        schemas = {
            "PRE_GAME": (
                "starter_matchup（字符串，2至3句）、team_form（字符串，1至2句）、"
                "outlook（字符串，1至2句）"
            ),
            "LIVE": (
                "turning_points（1至3项字符串数组，按时间顺序说明改变领先方或明显改变分差的局；"
                "不得虚构具体打席事件）、"
                "key_players（3至5项字符串数组，选择双方今日真正关键的击球手或投手；"
                "每项写明今日数据以及该表现对当前局面的意义）、"
                "bullpen_outlook（字符串，3至5句；结合当前局数与分差、已登板投手今日表现、"
                "listed_bullpen中的赛季ERA/WHIP/SV/HLD，对双方后续走势作有依据的条件式判断；"
                "最后一句必须明确目前哪一队走势更有利，以及另一队需要什么场上变化才可能扭转）"
            ),
            "POST_GAME": (
                "summary（字符串，2至4句比赛概述）、turning_point（字符串）、"
                "key_players（最多4项的字符串数组）、home_team_review（字符串）、"
                "away_team_review（字符串）。如果数据不足以判断转折点或关键球员，"
                "必须明确写“现有数据不足”，不可猜测"
            ),
        }
        output_language = (
            "本文はすべて自然な日本語で記述し、"
            if language == "ja"
            else "请使用中文，"
        )
        instructions = (
            "你是谨慎的棒球数据编辑。只能使用提供的数据，不得补充记忆中的当前赛季事实，"
            "不得编造精确胜率。不得从统计组合推断未明确提供的打席事件或投手角色；"
            "逐局得分只可用于说明比分变化。"
            + output_language
            + "只返回合法 JSON 对象。字段："
            + schemas.get(analysis_type, schemas["PRE_GAME"])
        )
        if analysis_type == "LIVE":
            instructions += (
                "。这是进行中分析，不要重复用户在记分牌上已经能看到的当前比分，"
                "bullpen_outlook必须直接从已登板投手和潜在后援开始，不能出现当前局数、当前比分、"
                "领先或落后几分等记分牌信息。不要复述LIVE状态代码，不要解释胜败投尚未产生，"
                "不要把失误、安打或保送写成失分的确定原因，不要提出未经数据支持的战术建议。"
                "如果数据只显示某队后续局数未得分，只能写“后续局数未得分”，不得擅自写成"
                "“受制于投手群”或“被牛棚封锁”。"
                "不要返回data_limitations或任何未列出的字段。避免逐项抄写Boxscore，"
                "优先解释数据为何重要。使用自然、面向球迷的表达，避免“定性选择”等生硬术语。"
                "可以使用“更有利”“仍有机会”“走势取决于”等语言，但不得给出精确概率。"
                "listed_bullpen只表示牛棚名单中的潜在后续人选；只能写“若可以登板”或“名单中有”，"
                "不能写“可用”“可供选择”或断言球员一定会登板"
            )
        elif analysis_type == "PRE_GAME":
            instructions += (
                "。这是简短的赛前展望，总计不超过6句。starter_matchup必须比较两位预告先发的"
                "本赛季W-L、ERA、WHIP、局数与K/BB；不要只罗列数字，要说明数据代表的稳定性或风险。"
                "结合games_started与games判断使用方式：如果先发占比很低，只能谨慎指出可能是假先发、"
                "opener或牛棚日安排，不能断言球队一定采用该策略。team_form只根据recent_10中的实际"
                "胜负评价双方近期状态；不足10场时不得假装样本完整。outlook给出简短的条件式判断，"
                "不得给出精确胜率。不要复述比赛时间、球场和对阵信息，不要输出confidence、"
                "data_limitations或任何未列出的字段"
            )
        return instructions

    @staticmethod
    def _normalize_content(analysis_type: str, content: dict) -> dict:
        if analysis_type == "PRE_GAME":
            return {
                key: content[key].strip()
                for key in ("starter_matchup", "team_form", "outlook")
                if isinstance(content.get(key), str) and content[key].strip()
            }
        if analysis_type != "LIVE":
            return content
        normalized = {}
        limits = {
            "turning_points": 3,
            "key_players": 5,
        }
        for key, limit in limits.items():
            value = content.get(key)
            if isinstance(value, str):
                value = [value]
            if isinstance(value, list):
                rows = [item.strip() for item in value if isinstance(item, str) and item.strip()]
                if rows:
                    normalized[key] = rows[:limit]
        outlook = content.get("bullpen_outlook")
        if isinstance(outlook, str) and outlook.strip():
            normalized["bullpen_outlook"] = outlook.strip()
        return normalized

    def analyze_game(
        self,
        game: Game,
        snapshot: dict | None = None,
        *,
        language: str = "zh",
    ) -> tuple[AIAnalysis, bool]:
        analysis_type = self.analysis_type_for(game)
        if analysis_type == "PRE_GAME" and not (
            game.probable_away_pitcher and game.probable_home_pitcher
        ):
            raise PregameAnalysisUnavailable(
                "双方预告先发投手公布后才能生成 AI 赛前展望。"
            )
        source = self.game_source(game, snapshot)
        prompt_version = self.prompt_version_for(analysis_type, language)
        source_hash = self.cache_hash(source, analysis_type, language)
        cached = db.session.execute(
            db.select(AIAnalysis).where(
                AIAnalysis.game_pk == game.game_pk,
                AIAnalysis.analysis_type == analysis_type,
                AIAnalysis.source_hash == source_hash,
            )
        ).scalar_one_or_none()
        if cached:
            return cached, True
        if analysis_type == "LIVE":
            refresh_cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)
            recent = db.session.execute(
                db.select(AIAnalysis)
                .where(
                    AIAnalysis.game_pk == game.game_pk,
                    AIAnalysis.analysis_type == analysis_type,
                    AIAnalysis.created_at >= refresh_cutoff,
                )
                .order_by(AIAnalysis.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if recent:
                return recent, True
        if not self.api_key or not self.model_name:
            raise AIServiceError("AI 服务尚未配置，请设置 GEMINI_API_KEY 和 GEMINI_MODEL。")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent"
        )
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": self._instructions(analysis_type, language)
                            + "\nDATA:\n"
                            + json.dumps(source, ensure_ascii=False, default=str)
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": (
                    700
                    if analysis_type == "PRE_GAME"
                    else 1400 if analysis_type == "LIVE" else 2048
                ),
                "thinkingConfig": {"thinkingLevel": "minimal"},
            },
        }
        try:
            response = self.session.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": self.api_key,
                },
                json=body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            content = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
            if not isinstance(content, dict) or not content:
                raise ValueError("Gemini response is not an object")
            content = self._normalize_content(analysis_type, content)
            if analysis_type == "PRE_GAME" and not all(
                content.get(key)
                for key in ("starter_matchup", "team_form", "outlook")
            ):
                raise ValueError("Gemini pregame response is incomplete")
            if analysis_type == "LIVE" and not all(
                content.get(key)
                for key in ("turning_points", "key_players", "bullpen_outlook")
            ):
                raise ValueError("Gemini live response is incomplete")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                retry_after = self._retry_after_seconds(exc.response)
                previous = self._latest_analysis(
                    game.game_pk, analysis_type, language
                )
                logger.warning(
                    "Gemini %s quota limited for game %s; retry after %ss; fallback=%s",
                    analysis_type,
                    game.game_pk,
                    retry_after,
                    bool(previous),
                )
                if previous:
                    return previous, True
                raise AIRateLimitError(retry_after) from exc
            logger.warning(
                "Gemini %s HTTP request failed for game %s: %r",
                analysis_type,
                game.game_pk,
                exc,
            )
            raise AIServiceError(
                "AI 分析暂时不可用，比赛数据仍可正常查看，请稍后重试。"
            ) from exc
        except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Gemini %s analysis failed for game %s: %r",
                analysis_type,
                game.game_pk,
                exc,
            )
            raise AIServiceError("AI 分析暂时不可用，比赛数据仍可正常查看，请稍后重试。") from exc

        analysis = AIAnalysis(
            game_pk=game.game_pk,
            analysis_type=analysis_type,
            source_hash=source_hash,
            model_name=self.model_name,
            prompt_version=prompt_version,
            content=content,
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis, False

    @staticmethod
    def _player_instructions(language: str) -> str:
        if language == "ja":
            return (
                "あなたは慎重な野球データ編集者です。提供されたシーズン成績と直近の出場成績だけを使い、"
                "記憶上の事実や怪我、契約、起用法を推測しないでください。簡潔で自然な日本語を使用し、"
                "season_review（2〜3文）、recent_form（1〜2文）、outlook（1〜2文）の3フィールドを持つ"
                "正しいJSONオブジェクトだけを返してください。投打両方のデータがある場合は両方を評価し、"
                "データがない項目は明確に不足と述べ、精密な将来予測や確率は書かないでください。"
            )
        return (
            "你是谨慎的棒球数据编辑。只使用提供的赛季统计与近期出场成绩，不得补充记忆中的事实，"
            "不得猜测伤病、合同或球队安排。请使用简明自然的中文，只返回合法JSON对象，字段为"
            "season_review（2至3句）、recent_form（1至2句）、outlook（1至2句）。"
            "如果同时提供投打数据，需要分别评价；缺少的数据必须明确说明，不得给出精确预测概率。"
        )

    def analyze_player(
        self,
        player: Player,
        source: dict,
        *,
        language: str = "zh",
    ) -> tuple[AIAnalysis, bool]:
        analysis_type = "PLAYER"
        prompt_version = self.prompt_version_for(analysis_type, language)
        source_hash = self.cache_hash(source, analysis_type, language)
        cached = db.session.execute(
            db.select(AIAnalysis).where(
                AIAnalysis.player_id == player.id,
                AIAnalysis.analysis_type == analysis_type,
                AIAnalysis.source_hash == source_hash,
            )
        ).scalar_one_or_none()
        if cached:
            return cached, True
        if not self.api_key or not self.model_name:
            raise AIServiceError("AI 服务尚未配置，请设置 GEMINI_API_KEY 和 GEMINI_MODEL。")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent"
        )
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": self._player_instructions(language)
                            + "\nDATA:\n"
                            + json.dumps(source, ensure_ascii=False, default=str)
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": 800,
                "thinkingConfig": {"thinkingLevel": "minimal"},
            },
        }
        try:
            response = self.session.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": self.api_key,
                },
                json=body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            content = json.loads(
                text.strip().removeprefix("```json").removesuffix("```").strip()
            )
            if not isinstance(content, dict) or not all(
                isinstance(content.get(key), str) and content[key].strip()
                for key in ("season_review", "recent_form", "outlook")
            ):
                raise ValueError("Gemini player response is incomplete")
            content = {
                key: content[key].strip()
                for key in ("season_review", "recent_form", "outlook")
            }
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                retry_after = self._retry_after_seconds(exc.response)
                previous = db.session.execute(
                    db.select(AIAnalysis)
                    .where(
                        AIAnalysis.player_id == player.id,
                        AIAnalysis.analysis_type == analysis_type,
                        AIAnalysis.prompt_version == prompt_version,
                    )
                    .order_by(AIAnalysis.created_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if previous:
                    return previous, True
                raise AIRateLimitError(retry_after) from exc
            logger.warning(
                "Gemini player HTTP request failed for %s: %r",
                player.mlb_player_id,
                exc,
            )
            raise AIServiceError("AI 分析暂时不可用，请稍后重试。") from exc
        except (
            requests.RequestException,
            KeyError,
            IndexError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                "Gemini player analysis failed for %s: %r",
                player.mlb_player_id,
                exc,
            )
            raise AIServiceError("AI 分析暂时不可用，请稍后重试。") from exc
        analysis = AIAnalysis(
            player_id=player.id,
            analysis_type=analysis_type,
            source_hash=source_hash,
            model_name=self.model_name,
            prompt_version=prompt_version,
            content=content,
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis, False
