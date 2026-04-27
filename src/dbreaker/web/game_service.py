from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from dbreaker.engine.actions import Action
from dbreaker.engine.game import Game
from dbreaker.strategies.base import BaseStrategy
from dbreaker.strategies.registry import create_strategy
from dbreaker.web import db as db_mod
from dbreaker.web.config import WebConfig
from dbreaker.web.inspector_service import build_inspector_state


@dataclass(slots=True)
class LiveSession:
    game: Game
    human_player_id: str
    seed: int | None
    ai_strategy: str
    ai_strategies: dict[str, BaseStrategy] = field(default_factory=dict)
    last_replay_id: str | None = None
    replay_persisted: bool = False


class GameService:
    def __init__(self, config: WebConfig, conn: sqlite3.Connection) -> None:
        self._config = config
        self._conn = conn
        self._lock = threading.RLock()
        self._sessions: dict[str, LiveSession] = {}

    def new_session(
        self,
        *,
        player_count: int,
        human_player_id: str,
        ai_strategy: str,
        seed: int | None = None,
    ) -> dict[str, Any]:
        game = Game.new(player_count=player_count, seed=seed)
        if human_player_id not in game.state.player_order:
            raise ValueError("human_player_id must be a seat in this table")
        ai_strategies: dict[str, BaseStrategy] = {
            pid: create_strategy(ai_strategy)
            for pid in game.state.player_order
            if pid != human_player_id
        }
        game_id = f"game_{uuid.uuid4().hex[:12]}"
        session = LiveSession(
            game=game,
            human_player_id=human_player_id,
            seed=seed,
            ai_strategy=ai_strategy,
            ai_strategies=ai_strategies,
        )
        with self._lock:
            self._sessions[game_id] = session
        db_mod.insert_game(
            self._conn,
            game_id=game_id,
            source="live",
            player_count=player_count,
            seed=seed,
            strategy_specs={
                "human": human_player_id,
                "ai": ai_strategy,
            },
        )
        return {
            "game_id": game_id,
            "version": 0,
            "inspector": build_inspector_state(
                game,
                game_id=game_id,
                viewer=human_player_id,
            ),
        }

    def get_session(self, game_id: str) -> LiveSession | None:
        with self._lock:
            return self._sessions.get(game_id)

    def inspect(self, game_id: str, *, viewer: str) -> dict[str, Any] | None:
        session = self.get_session(game_id)
        if session is None:
            return None
        return build_inspector_state(
            session.game, game_id=game_id, viewer=viewer
        )

    def apply_action(
        self,
        game_id: str,
        *,
        player_id: str,
        expected_version: int,
        action: Action,
    ) -> dict[str, Any] | None:
        with self._lock:
            session = self._sessions.get(game_id)
            if session is None:
                return None
            g = session.game
            v = len(g.action_log)
            if v != expected_version:
                return {"error": "stale", "version": v}
            if g.is_terminal():
                return {"error": "terminal", "version": v}
            if g.active_player_id != player_id:
                return {"error": "not_active", "version": v}
            result = g.step(player_id, action)
            v2 = len(g.action_log)
            human = session.human_player_id
            ended = g.is_terminal()
        events = [asdict(e) for e in result.events]
        if ended:
            self._persist_replay_on_complete(game_id)
        session2 = self.get_session(game_id)
        g2 = session2.game if session2 else g
        return {
            "game_id": game_id,
            "version": v2,
            "accepted": result.accepted,
            "events": events,
            "inspector": build_inspector_state(
                g2, game_id=game_id, viewer=human
            ),
        }

    def ai_step(
        self, game_id: str, *, expected_version: int, max_steps: int
    ) -> dict[str, Any] | None:
        with self._lock:
            session = self._sessions.get(game_id)
            if session is None:
                return None
        steps = 0
        while steps < max_steps:
            with self._lock:
                session = self._sessions.get(game_id)
                assert session is not None
                g = session.game
                v = len(g.action_log)
                human = session.human_player_id
                if g.is_terminal():
                    return {
                        "game_id": game_id,
                        "version": v,
                        "steps_run": steps,
                        "done": "terminal",
                        "inspector": build_inspector_state(
                            g, game_id=game_id, viewer=human
                        ),
                    }
                if v != expected_version and steps == 0:
                    return {"error": "stale", "version": v}
                active = g.active_player_id
                if active == human:
                    return {
                        "game_id": game_id,
                        "version": v,
                        "steps_run": steps,
                        "done": "human_turn",
                        "inspector": build_inspector_state(
                            g, game_id=game_id, viewer=human
                        ),
                    }
                strategy = session.ai_strategies[active]
                legal = g.legal_actions(active)
                if not legal:
                    return {
                        "game_id": game_id,
                        "version": v,
                        "steps_run": steps,
                        "done": "no_legal",
                        "inspector": build_inspector_state(
                            g, game_id=game_id, viewer=human
                        ),
                    }
                obs = g.observation_for(active)
                decision = strategy.choose_action(obs, legal)
                g.step(active, decision.action)
                steps += 1
                if g.is_terminal():
                    self._persist_replay_on_complete_unsafe(game_id, session)
                    return {
                        "game_id": game_id,
                        "version": len(g.action_log),
                        "steps_run": steps,
                        "done": "terminal",
                        "inspector": build_inspector_state(
                            g, game_id=game_id, viewer=human
                        ),
                    }
        with self._lock:
            session = self._sessions[game_id]
            g = session.game
            v = len(g.action_log)
            human = session.human_player_id
            return {
                "game_id": game_id,
                "version": v,
                "steps_run": steps,
                "done": "max_steps",
                "inspector": build_inspector_state(
                    g, game_id=game_id, viewer=human
                ),
            }

    def _persist_replay_on_complete(self, game_id: str) -> None:
        with self._lock:
            session = self._sessions.get(game_id)
            if session is None:
                return
            if not session.game.is_terminal():
                return
            self._persist_replay_on_complete_unsafe(game_id, session)

    def _persist_replay_on_complete_unsafe(
        self, game_id: str, session: LiveSession
    ) -> None:
        g = session.game
        if not g.is_terminal() or session.replay_persisted:
            return
        session.replay_persisted = True
        replay_id = f"replay_{uuid.uuid4().hex[:12]}"
        rel_path = f"replays/{game_id}.json"
        out = self._config.artifact_root / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": 1,
            "format": "dbreaker-action-log",
            "game_id": game_id,
            "player_count": len(g.state.player_order),
            "seed": session.seed,
            "action_log": g.action_log,
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        turns = g.state.turn
        db_mod.update_game_complete(
            self._conn,
            game_id,
            status="completed",
            winner_id=g.state.winner_id,
            ended_by="winner" if g.state.winner_id else None,
            turn_count=turns,
            replay_path=rel_path,
            action_log_json=json.dumps(g.action_log),
        )
        db_mod.insert_replay(
            self._conn,
            replay_id=replay_id,
            game_id=game_id,
            path=rel_path,
            event_count=len(g.event_log),
            first_turn=0,
            last_turn=turns,
            metadata={"source": "web_live"},
        )
        session.last_replay_id = replay_id
