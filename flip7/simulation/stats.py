from dataclasses import dataclass
from typing import Optional
from .runner import GameResult


@dataclass
class GameStats:
    num_games: int
    num_players: int
    win_rates: tuple         # fraction of games won, per player
    avg_final_score: tuple   # mean final cumulative score, per player
    avg_rounds: float
    min_rounds: int
    max_rounds: int
    avg_states: float        # mean log snapshots per game (proxy for game complexity)


def compute_stats(results: list[GameResult]) -> GameStats:
    """Aggregate statistics across a list of GameResult objects."""
    if not results:
        raise ValueError("No results to compute stats from")

    n = len(results)
    num_players = len(results[0].final_scores)

    win_counts = [0] * num_players
    score_sums = [0] * num_players

    for r in results:
        win_counts[r.winner_id] += 1
        for i, s in enumerate(r.final_scores):
            score_sums[i] += s

    rounds = [r.num_rounds for r in results]
    states = [r.num_states for r in results]

    return GameStats(
        num_games=n,
        num_players=num_players,
        win_rates=tuple(c / n for c in win_counts),
        avg_final_score=tuple(s / n for s in score_sums),
        avg_rounds=sum(rounds) / n,
        min_rounds=min(rounds),
        max_rounds=max(rounds),
        avg_states=sum(states) / n,
    )


def print_stats(stats: GameStats, player_names: Optional[list[str]] = None) -> None:
    names = player_names or [f"Player {i}" for i in range(stats.num_players)]
    print(f"Results over {stats.num_games} game(s)  ({stats.num_players} players):")
    print(f"  Rounds : avg={stats.avg_rounds:.1f}  min={stats.min_rounds}  max={stats.max_rounds}")
    print(f"  States : avg={stats.avg_states:.1f}")
    print()
    for i in range(stats.num_players):
        print(
            f"  {names[i]:20s}  win_rate={stats.win_rates[i]:.1%}  "
            f"avg_score={stats.avg_final_score[i]:.1f}"
        )
