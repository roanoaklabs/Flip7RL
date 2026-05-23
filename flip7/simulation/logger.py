import json
from pathlib import Path
from typing import Union

from ..engine.state import GameState, PlayerRoundState, RoundState
from ..engine.cards import NumberCard, ModifierCard, ActionCard


def _card_to_dict(card) -> dict:
    if isinstance(card, NumberCard):
        return {"type": "number", "value": card.value}
    if isinstance(card, ModifierCard):
        return {"type": "modifier", "op": card.op.value, "value": card.value}
    if isinstance(card, ActionCard):
        return {"type": "action", "action_type": card.type.value}
    return {}


def _player_state_to_dict(ps: PlayerRoundState) -> dict:
    return {
        "player_id": ps.player_id,
        "number_cards": [_card_to_dict(c) for c in ps.number_cards],
        "modifier_cards": [_card_to_dict(c) for c in ps.modifier_cards],
        "action_cards": [_card_to_dict(c) for c in ps.action_cards],
        "status": ps.status.value,
        "bust_card_value": ps.bust_card_value,
        "current_sum": ps.current_sum(),
    }


def _state_to_dict(state: GameState) -> dict:
    d: dict = {
        "t": state.t,
        "round_number": state.round_number,
        "dealer_idx": state.dealer_idx,
        "num_players": state.num_players,
        "cumulative_scores": list(state.cumulative_scores),
        "round_state": None,
    }
    if state.round_state is not None:
        rs = state.round_state
        d["round_state"] = {
            "phase": rs.phase,
            "deck_remaining": rs.deck_remaining,
            "current_player_idx": rs.current_player_idx,
            "player_states": [_player_state_to_dict(p) for p in rs.player_states],
            "action_queue": [
                {"card": _card_to_dict(card), "acting_player": pid}
                for card, pid in rs.action_queue
            ],
        }
    return d


def serialize_game(log: list[GameState]) -> dict:
    """Convert a full game log into a JSON-serializable dict."""
    return {
        "num_states": len(log),
        "states": [_state_to_dict(s) for s in log],
    }


def save_game(log: list[GameState], path: Union[str, Path], indent: int = 2) -> None:
    """Write a game log to a JSON file."""
    Path(path).write_text(json.dumps(serialize_game(log), indent=indent))


def load_game(path: Union[str, Path]) -> dict:
    """Load a saved game log dict from a JSON file."""
    return json.loads(Path(path).read_text())
