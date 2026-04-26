from __future__ import annotations

from rich.console import Console

from dbreaker.cli.prompts import prompt_human_action
from dbreaker.cli.renderer import (
    build_card_name_map,
    format_ai_turn_header,
    render_events,
    render_observation_rich,
)
from dbreaker.engine.actions import EndTurn
from dbreaker.engine.game import Game
from dbreaker.strategies.registry import default_registry


def run_interactive_play(players: int, ai_strategy: str = "basic") -> None:
    game = Game.new(player_count=players)
    registry = default_registry()
    console = Console()
    ai_players = {
        player_id: registry.create(ai_strategy) for player_id in game.state.player_order[1:]
    }

    while not game.is_terminal():
        player_id = game.active_player_id
        legal_actions = game.legal_actions(player_id)
        if player_id in ai_players:
            observation = game.observation_for(player_id)
            decision = ai_players[player_id].choose_action(observation, legal_actions)
            result = game.step(player_id, decision.action)
            name_by_id = build_card_name_map(observation)
            print(format_ai_turn_header(player_id, decision.action, name_by_id=name_by_id))
            print(render_events(result.events))
            continue

        observation = game.observation_for(player_id)
        console.print(render_observation_rich(observation))
        action = prompt_human_action(player_id, legal_actions, observation)
        result = game.step(player_id, action)
        print(render_events(result.events))


def run_non_interactive_demo(players: int) -> Game:
    game = Game.new(player_count=players)
    while not game.is_terminal() and game.state.turn <= players:
        game.step(game.state.current_player_id, EndTurn())
    return game
