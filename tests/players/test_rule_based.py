"""Tests for RuleBasedPlayer."""
import pytest
from flip7.engine.cards import NumberCard, ActionCard, ActionType
from flip7.engine.state import PlayerRoundState, PlayerStatus
from flip7.players.base import GameObservation
from flip7.players.rule_based import RuleBasedPlayer
from flip7.engine.state import HitStay


def _obs(
    my_id=0,
    numbers=(),
    other_players=(),
    cumulative=(0, 0),
    status=PlayerStatus.ACTIVE,
) -> GameObservation:
    return GameObservation(
        my_player_id=my_id,
        my_number_cards=tuple(NumberCard(v) for v in numbers),
        my_modifier_cards=(),
        my_action_cards=(),
        my_status=status,
        other_players=other_players,
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


# ------------------------------------------------------------------
# decide()
# ------------------------------------------------------------------

def test_hits_below_threshold():
    player = RuleBasedPlayer(0, stay_threshold=15)
    obs = _obs(numbers=(5, 3))  # sum = 8
    assert player.decide(obs) == HitStay.HIT


def test_stays_exactly_at_threshold():
    player = RuleBasedPlayer(0, stay_threshold=15)
    obs = _obs(numbers=(7, 8))  # sum = 15
    assert player.decide(obs) == HitStay.STAY


def test_stays_above_threshold():
    player = RuleBasedPlayer(0, stay_threshold=15)
    obs = _obs(numbers=(10, 8))  # sum = 18
    assert player.decide(obs) == HitStay.STAY


def test_custom_threshold_zero_always_stays():
    player = RuleBasedPlayer(0, stay_threshold=0)
    obs = _obs(numbers=())  # sum = 0
    assert player.decide(obs) == HitStay.STAY


def test_custom_threshold_high_always_hits():
    player = RuleBasedPlayer(0, stay_threshold=999)
    obs = _obs(numbers=(12, 11, 10, 9, 8, 7))  # large sum but < 999
    assert player.decide(obs) == HitStay.HIT


def test_observe_does_not_raise():
    player = RuleBasedPlayer(0)
    player.observe(_obs())


# ------------------------------------------------------------------
# choose_target()
# ------------------------------------------------------------------

def test_targets_highest_cumulative_score():
    # Player 0 chooses between opponents 1 (score 20) and 2 (score 80)
    opponents = (
        _pstate(1),
        _pstate(2),
    )
    obs = _obs(my_id=0, other_players=opponents, cumulative=(0, 20, 80))
    player = RuleBasedPlayer(0)
    freeze = ActionCard(type=ActionType.FREEZE)
    assert player.choose_target(freeze, obs) == 2


def test_targets_only_active_opponents():
    # Opponent 1 busted — target must be player 2
    opponents = (
        _pstate(1, status=PlayerStatus.BUSTED),
        _pstate(2),
    )
    obs = _obs(my_id=0, other_players=opponents, cumulative=(0, 100, 30))
    player = RuleBasedPlayer(0)
    freeze = ActionCard(type=ActionType.FREEZE)
    assert player.choose_target(freeze, obs) == 2


def test_targets_self_when_no_active_opponents():
    opponents = (
        _pstate(1, status=PlayerStatus.STAYED),
        _pstate(2, status=PlayerStatus.BUSTED),
    )
    obs = _obs(my_id=0, other_players=opponents, cumulative=(0, 50, 80))
    player = RuleBasedPlayer(0)
    freeze = ActionCard(type=ActionType.FREEZE)
    assert player.choose_target(freeze, obs) == 0
