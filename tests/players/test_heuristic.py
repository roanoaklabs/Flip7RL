"""Tests for HeuristicPlayer."""
import pytest
from flip7.engine.cards import NumberCard, ActionCard, ActionType
from flip7.engine.state import PlayerRoundState, PlayerStatus, HitStay
from flip7.players.base import GameObservation
from flip7.players.heuristic import HeuristicPlayer


def _obs(
    my_id=0,
    numbers=(),
    other_players=(),
    cumulative=None,
    status=PlayerStatus.ACTIVE,
) -> GameObservation:
    if cumulative is None:
        cumulative = tuple(0 for _ in range(max(2, len(other_players) + 1)))
    return GameObservation(
        my_player_id=my_id,
        my_number_cards=tuple(NumberCard(v) for v in numbers),
        my_modifier_cards=(),
        my_action_cards=(),
        my_status=status,
        other_players=tuple(other_players),
        cumulative_scores=cumulative,
        round_number=1,
        num_players=len(cumulative),
        deck_remaining=40,
    )


def _pstate(pid, numbers=(), status=PlayerStatus.ACTIVE):
    return PlayerRoundState(
        player_id=pid,
        number_cards=tuple(NumberCard(v) for v in numbers),
        modifier_cards=(),
        action_cards=(),
        status=status,
    )


player = HeuristicPlayer(0)


# ------------------------------------------------------------------
# decide() — core rules
# ------------------------------------------------------------------

def test_six_unique_cards_always_hits():
    obs = _obs(numbers=(0, 1, 2, 3, 4, 5))  # 6 unique
    assert player.decide(obs) == HitStay.HIT


def test_seven_unique_cards_already_flip7_returns_hit():
    # 7 cards means flip7 — round is over, but if decide is called it still hits
    obs = _obs(numbers=(0, 1, 2, 3, 4, 5, 6))  # 7 unique
    assert player.decide(obs) == HitStay.HIT


def test_banking_now_wins_overrides_all():
    # cumulative=195, current sum=10 → 205 ≥ 200, stay even with 6 unique cards
    obs = _obs(numbers=(0, 1, 2, 3, 4, 5), cumulative=(195, 0))  # sum = 0+1+2+3+4+5 = 15
    # 195 + 15 = 210 ≥ 200
    assert player.decide(obs) == HitStay.STAY


def test_zero_cards_hits():
    obs = _obs(numbers=())
    assert player.decide(obs) == HitStay.HIT


def test_one_card_hits():
    obs = _obs(numbers=(12,))  # sum = 12, threshold for 1 card = 100
    assert player.decide(obs) == HitStay.HIT


def test_two_cards_hits_below_threshold():
    obs = _obs(numbers=(3, 7))  # sum = 10, threshold for 2 = 12
    assert player.decide(obs) == HitStay.HIT


def test_two_cards_stays_at_threshold():
    obs = _obs(numbers=(5, 7))  # sum = 12, threshold for 2 = 12
    assert player.decide(obs) == HitStay.STAY


def test_three_cards_hits_below_threshold():
    obs = _obs(numbers=(2, 5, 8))  # sum = 15, threshold for 3 = 16
    assert player.decide(obs) == HitStay.HIT


def test_three_cards_stays_at_threshold():
    obs = _obs(numbers=(2, 5, 9))  # sum = 16
    assert player.decide(obs) == HitStay.STAY


def test_five_cards_hits_below_threshold():
    obs = _obs(numbers=(1, 2, 3, 4, 5))  # sum = 15, threshold for 5 = 24
    assert player.decide(obs) == HitStay.HIT


def test_five_cards_stays_at_threshold():
    obs = _obs(numbers=(4, 5, 6, 7, 2))  # sum = 24
    assert player.decide(obs) == HitStay.STAY


def test_aggressive_when_opponent_near_200():
    # Opponent at 165, threshold for 3 cards (=16) should drop to 11
    opp = _pstate(1)
    obs = _obs(numbers=(1, 5, 4), other_players=(opp,), cumulative=(0, 165))
    # sum = 10, adjusted threshold = max(16-5,5) = 11, so 10 < 11 → HIT
    assert player.decide(obs) == HitStay.HIT


def test_not_aggressive_when_opponent_not_near():
    # Opponent at 100, normal threshold applies
    opp = _pstate(1)
    # sum = 16, threshold = 16, stays normally
    obs = _obs(numbers=(2, 5, 9), other_players=(opp,), cumulative=(0, 100))
    assert player.decide(obs) == HitStay.STAY


# ------------------------------------------------------------------
# choose_target()
# ------------------------------------------------------------------

def test_freeze_targets_highest_total_threat():
    # Opponent 1: cumulative=80 + round_sum=5=85; Opponent 2: cumulative=50 + round_sum=20=70
    opp1 = _pstate(1, numbers=(2, 3))      # round sum = 5
    opp2 = _pstate(2, numbers=(9, 11))    # round sum = 20
    obs = _obs(my_id=0, other_players=(opp1, opp2), cumulative=(0, 80, 50))
    freeze = ActionCard(type=ActionType.FREEZE)
    # opp1 threat = 85, opp2 threat = 70
    assert player.choose_target(freeze, obs) == 1


def test_flip_three_targets_player_with_most_cards():
    # Opponent 2 has 4 cards, opponent 1 has 2 cards
    opp1 = _pstate(1, numbers=(3, 5))
    opp2 = _pstate(2, numbers=(1, 2, 4, 6))
    obs = _obs(my_id=0, other_players=(opp1, opp2), cumulative=(0, 0, 0))
    flip3 = ActionCard(type=ActionType.FLIP_THREE)
    assert player.choose_target(flip3, obs) == 2


def test_targets_self_when_no_active_opponents():
    opp = _pstate(1, status=PlayerStatus.STAYED)
    obs = _obs(my_id=0, other_players=(opp,), cumulative=(0, 50))
    freeze = ActionCard(type=ActionType.FREEZE)
    assert player.choose_target(freeze, obs) == 0


def test_observe_does_not_raise():
    player.observe(_obs())
