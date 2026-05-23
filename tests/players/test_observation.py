"""Tests for GameObservation helper methods."""
import pytest
from flip7.engine.cards import NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType
from flip7.engine.state import PlayerRoundState, PlayerStatus
from flip7.players.base import GameObservation


def _obs(
    my_id=0,
    numbers=(),
    modifiers=(),
    actions=(),
    other_players=(),
    cumulative=(0, 50),
    status=PlayerStatus.ACTIVE,
) -> GameObservation:
    return GameObservation(
        my_player_id=my_id,
        my_number_cards=tuple(NumberCard(v) for v in numbers),
        my_modifier_cards=tuple(modifiers),
        my_action_cards=tuple(actions),
        my_status=status,
        other_players=other_players,
        cumulative_scores=cumulative,
        round_number=1,
        num_players=len(cumulative),
        deck_remaining=40,
    )


# ------------------------------------------------------------------
# my_current_sum
# ------------------------------------------------------------------

def test_sum_no_cards():
    obs = _obs(numbers=())
    assert obs.my_current_sum() == 0


def test_sum_number_cards_only():
    obs = _obs(numbers=(3, 7, 2))
    assert obs.my_current_sum() == 12


def test_sum_with_add_modifier():
    obs = _obs(numbers=(5,), modifiers=(ModifierCard(op=ModifierOp.ADD, value=8),))
    assert obs.my_current_sum() == 13


def test_sum_with_multiply_modifier():
    obs = _obs(numbers=(5,), modifiers=(ModifierCard(op=ModifierOp.MULTIPLY, value=2),))
    assert obs.my_current_sum() == 10


def test_sum_multiply_before_add():
    # sum=6 → x2 → 12 → +4 → 16
    obs = _obs(
        numbers=(6,),
        modifiers=(
            ModifierCard(op=ModifierOp.MULTIPLY, value=2),
            ModifierCard(op=ModifierOp.ADD, value=4),
        ),
    )
    assert obs.my_current_sum() == 16


def test_sum_flip7_bonus():
    # 7 unique cards: 0+1+2+3+4+5+6 = 21, plus 15 bonus = 36
    obs = _obs(numbers=(0, 1, 2, 3, 4, 5, 6))
    assert obs.my_current_sum() == 36


# ------------------------------------------------------------------
# my_unique_card_count
# ------------------------------------------------------------------

def test_unique_card_count_empty():
    assert _obs(numbers=()).my_unique_card_count() == 0


def test_unique_card_count_some():
    assert _obs(numbers=(1, 5, 9)).my_unique_card_count() == 3


# ------------------------------------------------------------------
# my_cumulative_score
# ------------------------------------------------------------------

def test_cumulative_score():
    obs = _obs(my_id=1, cumulative=(30, 75))
    assert obs.my_cumulative_score() == 75
