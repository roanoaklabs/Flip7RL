"""Tests for the simulation logger."""
import json
import pytest
from pathlib import Path
from flip7.players.base import RandomPlayer
from flip7.simulation.runner import run_game
from flip7.simulation.logger import serialize_game, save_game, load_game


def _log(seed=0, n=3):
    players = [RandomPlayer(i, seed=seed + i) for i in range(n)]
    result = run_game(players, seed=seed, full_log=True)
    return result.log


# ------------------------------------------------------------------
# serialize_game
# ------------------------------------------------------------------

def test_serialize_game_is_json_serializable():
    log = _log()
    data = serialize_game(log)
    # Must not raise
    json.dumps(data)


def test_serialize_game_num_states_correct():
    log = _log()
    data = serialize_game(log)
    assert data["num_states"] == len(log)
    assert len(data["states"]) == len(log)


def test_serialize_game_first_state_structure():
    log = _log()
    data = serialize_game(log)
    s = data["states"][0]
    assert "t" in s
    assert "round_number" in s
    assert "cumulative_scores" in s
    assert "num_players" in s


def test_serialize_game_round_state_included():
    log = _log()
    data = serialize_game(log)
    # Find a state that has a round_state
    round_states = [s["round_state"] for s in data["states"] if s["round_state"] is not None]
    assert len(round_states) > 0
    rs = round_states[0]
    assert "phase" in rs
    assert "player_states" in rs
    assert "deck_remaining" in rs


def test_serialize_number_card():
    log = _log()
    data = serialize_game(log)
    # Find at least one number card across all player states
    number_cards = []
    for s in data["states"]:
        if s["round_state"]:
            for ps in s["round_state"]["player_states"]:
                number_cards.extend(ps["number_cards"])
    if number_cards:
        c = number_cards[0]
        assert c["type"] == "number"
        assert "value" in c


def test_serialize_current_sum_included():
    log = _log()
    data = serialize_game(log)
    for s in data["states"]:
        if s["round_state"]:
            for ps in s["round_state"]["player_states"]:
                assert "current_sum" in ps


# ------------------------------------------------------------------
# save_game / load_game round-trip
# ------------------------------------------------------------------

def test_save_and_load_round_trip(tmp_path):
    log = _log()
    path = tmp_path / "game.json"
    save_game(log, path)

    loaded = load_game(path)
    assert loaded["num_states"] == len(log)
    assert len(loaded["states"]) == len(log)


def test_save_creates_valid_json_file(tmp_path):
    log = _log()
    path = tmp_path / "out.json"
    save_game(log, path)
    assert path.exists()
    # File must be valid JSON
    content = path.read_text()
    parsed = json.loads(content)
    assert "states" in parsed


def test_load_preserves_cumulative_scores(tmp_path):
    log = _log(seed=7)
    path = tmp_path / "game.json"
    save_game(log, path)
    loaded = load_game(path)
    final_original = log[-1].cumulative_scores
    final_loaded = tuple(loaded["states"][-1]["cumulative_scores"])
    assert final_original == final_loaded
