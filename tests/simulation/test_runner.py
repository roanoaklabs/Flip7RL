"""Tests for the simulation runner."""
import pytest
from flip7.players.base import RandomPlayer
from flip7.players.rule_based import RuleBasedPlayer
from flip7.players.heuristic import HeuristicPlayer
from flip7.simulation.runner import run_game, run_games, GameResult

WIN_SCORE = 200


def make_random_players(n=3, seed=0):
    return [RandomPlayer(i, seed=seed + i) for i in range(n)]


def make_rule_players(n=3):
    return [RuleBasedPlayer(i, stay_threshold=15) for i in range(n)]


# ------------------------------------------------------------------
# run_game
# ------------------------------------------------------------------

def test_run_game_returns_game_result():
    result = run_game(make_random_players(), seed=42)
    assert isinstance(result, GameResult)


def test_run_game_winner_meets_win_condition():
    result = run_game(make_random_players(), seed=42)
    assert result.final_scores[result.winner_id] >= WIN_SCORE


def test_run_game_all_scores_non_negative():
    result = run_game(make_random_players(), seed=0)
    assert all(s >= 0 for s in result.final_scores)


def test_run_game_num_rounds_positive():
    result = run_game(make_random_players(), seed=1)
    assert result.num_rounds >= 1


def test_run_game_seeded_is_reproducible():
    r1 = run_game(make_random_players(seed=7), seed=99)
    r2 = run_game(make_random_players(seed=7), seed=99)
    assert r1.winner_id == r2.winner_id
    assert r1.final_scores == r2.final_scores
    assert r1.num_rounds == r2.num_rounds


def test_run_game_different_seeds_differ():
    r1 = run_game(make_random_players(seed=0), seed=1)
    r2 = run_game(make_random_players(seed=0), seed=2)
    # Not guaranteed to differ in theory, but essentially certain with different seeds
    assert not (r1.winner_id == r2.winner_id and r1.num_rounds == r2.num_rounds
                and r1.final_scores == r2.final_scores)


def test_run_game_no_log_by_default():
    result = run_game(make_random_players(), seed=0)
    assert result.log is None


def test_run_game_full_log_attached():
    result = run_game(make_random_players(), seed=0, full_log=True)
    assert result.log is not None
    assert len(result.log) == result.num_states
    assert result.num_states > 0


def test_run_game_two_players():
    players = [RuleBasedPlayer(0), RuleBasedPlayer(1)]
    result = run_game(players, seed=5)
    assert result.winner_id in (0, 1)
    assert len(result.final_scores) == 2


def test_run_game_heuristic_players():
    # seed=11 terminates naturally in 8 rounds (verified empirically)
    players = [HeuristicPlayer(i) for i in range(4)]
    result = run_game(players, seed=11)
    assert result.final_scores[result.winner_id] >= WIN_SCORE


# ------------------------------------------------------------------
# run_games
# ------------------------------------------------------------------

def test_run_games_returns_correct_count():
    results = run_games(10, lambda: make_random_players(), seed=0)
    assert len(results) == 10


def test_run_games_all_results_are_game_results():
    results = run_games(5, lambda: make_rule_players(), seed=0)
    assert all(isinstance(r, GameResult) for r in results)


def test_run_games_all_winners_valid():
    results = run_games(5, lambda: make_random_players(n=2), seed=0)
    for r in results:
        assert r.winner_id in (0, 1)
        assert r.final_scores[r.winner_id] >= WIN_SCORE


def test_run_games_seeded_reproducible():
    factory = lambda: make_random_players(seed=3)
    r1 = run_games(5, factory, seed=0)
    r2 = run_games(5, factory, seed=0)
    assert [r.winner_id for r in r1] == [r.winner_id for r in r2]


def test_run_games_without_full_log_saves_memory():
    results = run_games(5, lambda: make_random_players(), seed=0, full_log=False)
    assert all(r.log is None for r in results)


def test_run_games_with_full_log():
    results = run_games(3, lambda: make_random_players(), seed=0, full_log=True)
    assert all(r.log is not None for r in results)


def test_run_one_game_via_run_games():
    results = run_games(1, lambda: make_random_players(), seed=42)
    assert len(results) == 1
    assert results[0].final_scores[results[0].winner_id] >= WIN_SCORE
