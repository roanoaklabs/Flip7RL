"""Tests for simulation statistics."""
import pytest
from flip7.players.base import RandomPlayer
from flip7.simulation.runner import run_games, GameResult
from flip7.simulation.stats import compute_stats, print_stats, GameStats
from flip7.engine.game import WIN_SCORE


def _results(n=20, num_players=3, seed=0):
    factory = lambda: [RandomPlayer(i, seed=seed + i) for i in range(num_players)]
    return run_games(n, factory, seed=seed)


# ------------------------------------------------------------------
# compute_stats
# ------------------------------------------------------------------

def test_compute_stats_returns_game_stats():
    results = _results()
    stats = compute_stats(results)
    assert isinstance(stats, GameStats)


def test_compute_stats_num_games():
    results = _results(n=15)
    stats = compute_stats(results)
    assert stats.num_games == 15


def test_compute_stats_num_players():
    results = _results(num_players=4)
    stats = compute_stats(results)
    assert stats.num_players == 4


def test_compute_stats_win_rates_sum_to_one():
    results = _results(n=50)
    stats = compute_stats(results)
    assert abs(sum(stats.win_rates) - 1.0) < 1e-9


def test_compute_stats_all_win_rates_non_negative():
    stats = compute_stats(_results())
    assert all(r >= 0 for r in stats.win_rates)


def test_compute_stats_all_win_rates_at_most_one():
    stats = compute_stats(_results())
    assert all(r <= 1.0 for r in stats.win_rates)


def test_compute_stats_avg_rounds_positive():
    stats = compute_stats(_results())
    assert stats.avg_rounds > 0


def test_compute_stats_min_max_rounds():
    stats = compute_stats(_results(n=30))
    assert stats.min_rounds >= 1
    assert stats.max_rounds >= stats.min_rounds


def test_compute_stats_avg_final_score_non_negative():
    stats = compute_stats(_results())
    assert all(s >= 0 for s in stats.avg_final_score)


def test_compute_stats_winner_avg_score_above_floor():
    # Each time a player wins they score >= 200, so their avg must be >= 200 * win_rate
    stats = compute_stats(_results(n=50))
    for i in range(stats.num_players):
        assert stats.avg_final_score[i] >= WIN_SCORE * stats.win_rates[i] - 1e-9


def test_compute_stats_empty_raises():
    with pytest.raises(ValueError):
        compute_stats([])


def test_compute_stats_single_game():
    factory = lambda: [RandomPlayer(i) for i in range(2)]
    results = run_games(1, factory, seed=0)
    stats = compute_stats(results)
    assert stats.num_games == 1
    assert abs(sum(stats.win_rates) - 1.0) < 1e-9


# ------------------------------------------------------------------
# print_stats
# ------------------------------------------------------------------

def test_print_stats_default_names(capsys):
    stats = compute_stats(_results(n=10))
    print_stats(stats)
    out = capsys.readouterr().out
    assert "Player 0" in out
    assert "win_rate" in out


def test_print_stats_custom_names(capsys):
    stats = compute_stats(_results(n=10, num_players=2))
    print_stats(stats, player_names=["Alice", "Bob"])
    out = capsys.readouterr().out
    assert "Alice" in out
    assert "Bob" in out


def test_print_stats_shows_round_info(capsys):
    stats = compute_stats(_results(n=10))
    print_stats(stats)
    out = capsys.readouterr().out
    assert "avg=" in out
    assert "min=" in out
    assert "max=" in out
