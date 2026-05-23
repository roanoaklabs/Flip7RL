from dataclasses import dataclass, field
from typing import Optional, Callable
from ..engine.game import GameEngine
from ..engine.state import GameState


@dataclass
class GameResult:
    winner_id: int
    final_scores: tuple
    num_rounds: int
    num_states: int          # total state snapshots recorded
    log: Optional[list] = field(default=None, repr=False)


def run_game(
    players: list,
    seed: Optional[int] = None,
    full_log: bool = False,
) -> GameResult:
    """Run a single complete game and return its result.

    Set full_log=True to attach the full GameState snapshot list; omit for
    bulk runs where memory matters.
    """
    engine = GameEngine(num_players=len(players), seed=seed)
    log = engine.play_game(players)
    final = log[-1]
    winner_id = max(range(len(players)), key=lambda i: final.cumulative_scores[i])
    return GameResult(
        winner_id=winner_id,
        final_scores=final.cumulative_scores,
        num_rounds=final.round_number,
        num_states=len(log),
        log=log if full_log else None,
    )


def run_games(
    n: int,
    player_factory: Callable[[], list],
    seed: Optional[int] = None,
    full_log: bool = False,
) -> list[GameResult]:
    """Run n independent games.

    player_factory() is called once per game and must return a fresh list of
    players — reusing stateful players across games will produce incorrect results.
    Seeds are derived as seed+i so each game is independently reproducible.
    """
    results = []
    for i in range(n):
        game_seed = seed + i if seed is not None else None
        results.append(run_game(player_factory(), seed=game_seed, full_log=full_log))
    return results
