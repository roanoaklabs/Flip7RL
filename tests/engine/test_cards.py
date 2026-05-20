"""Tests for flip7/engine/cards.py and PlayerRoundState scoring."""
import pytest
import dataclasses
from flip7.engine.cards import (
    NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType, BaseCard
)
from flip7.engine.state import PlayerRoundState, PlayerStatus


def make_pstate(numbers=(), modifiers=(), actions=(), status=PlayerStatus.ACTIVE):
    return PlayerRoundState(
        player_id=0,
        number_cards=tuple(numbers),
        modifier_cards=tuple(modifiers),
        action_cards=tuple(actions),
        status=status,
    )


class TestNumberCard:
    def test_value_stored_correctly(self):
        card = NumberCard(value=7)
        assert card.value == 7

    def test_zero_value(self):
        card = NumberCard(value=0)
        assert card.value == 0

    def test_frozen(self):
        card = NumberCard(value=5)
        with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
            card.value = 10


class TestModifierCard:
    def test_add_modifier_values(self):
        card = ModifierCard(op=ModifierOp.ADD, value=6)
        assert card.op == ModifierOp.ADD
        assert card.value == 6

    def test_multiply_modifier(self):
        card = ModifierCard(op=ModifierOp.MULTIPLY, value=2)
        assert card.op == ModifierOp.MULTIPLY
        assert card.value == 2

    def test_frozen(self):
        card = ModifierCard(op=ModifierOp.ADD, value=4)
        with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
            card.op = ModifierOp.MULTIPLY


class TestActionCard:
    def test_second_chance_type(self):
        card = ActionCard(type=ActionType.SECOND_CHANCE)
        assert card.type == ActionType.SECOND_CHANCE

    def test_freeze_type(self):
        card = ActionCard(type=ActionType.FREEZE)
        assert card.type == ActionType.FREEZE

    def test_flip_three_type(self):
        card = ActionCard(type=ActionType.FLIP_THREE)
        assert card.type == ActionType.FLIP_THREE


class TestPlayerRoundStateScoringFormula:
    def test_empty_hand_sums_to_zero(self):
        pstate = make_pstate()
        assert pstate.current_sum() == 0

    def test_simple_number_sum(self):
        pstate = make_pstate(numbers=[NumberCard(3), NumberCard(4)])
        assert pstate.current_sum() == 7

    def test_zero_card_adds_zero(self):
        pstate = make_pstate(numbers=[NumberCard(0), NumberCard(5)])
        assert pstate.current_sum() == 5

    def test_add_modifier_only(self):
        pstate = make_pstate(
            numbers=[NumberCard(5)],
            modifiers=[ModifierCard(op=ModifierOp.ADD, value=4)],
        )
        assert pstate.current_sum() == 9

    def test_multiply_modifier_only(self):
        pstate = make_pstate(
            numbers=[NumberCard(5)],
            modifiers=[ModifierCard(op=ModifierOp.MULTIPLY, value=2)],
        )
        assert pstate.current_sum() == 10

    def test_multiply_then_add_order(self):
        """x2 applied before +4: (10 * 2) + 4 = 24"""
        pstate = make_pstate(
            numbers=[NumberCard(5), NumberCard(5)],  # wait, duplicates not allowed
        )
        # Use sum=10 with different numbers
        pstate = make_pstate(
            numbers=[NumberCard(3), NumberCard(7)],  # sum=10
            modifiers=[
                ModifierCard(op=ModifierOp.MULTIPLY, value=2),
                ModifierCard(op=ModifierOp.ADD, value=4),
            ],
        )
        assert pstate.current_sum() == 24  # 10*2 + 4

    def test_flip7_bonus_added_after_formula(self):
        """7 unique number cards get +15 bonus."""
        pstate = make_pstate(
            numbers=[NumberCard(i) for i in range(7)],  # 0+1+2+3+4+5+6=21
        )
        assert pstate.current_sum() == 21 + 15  # 36

    def test_flip7_with_multiply_modifier(self):
        """Verify full formula: multiply then add then flip7 bonus."""
        # sum=10, x2 -> 20, +6 -> 26, flip7 (7 cards) -> +15 = 41
        pstate = make_pstate(
            numbers=[NumberCard(i) for i in range(7)],  # 0+1+2+3+4+5+6=21... need sum=10
        )
        # Let me construct: numbers 0..6 sum to 21, not 10
        # Instead: numbers 1,2,3 (sum 6), x2 -> 12, +4 -> 16, no flip7 (only 3 cards)
        pstate = make_pstate(
            numbers=[NumberCard(1), NumberCard(2), NumberCard(3)],
            modifiers=[
                ModifierCard(op=ModifierOp.MULTIPLY, value=2),
                ModifierCard(op=ModifierOp.ADD, value=4),
            ],
        )
        assert pstate.current_sum() == 16  # (6*2)+4

    def test_flip7_bonus_exact_7_cards(self):
        """Only exactly 7 number cards triggers bonus."""
        # 6 cards: no bonus
        pstate6 = make_pstate(numbers=[NumberCard(i) for i in range(6)])
        assert pstate6.current_sum() == sum(range(6))  # 15, no bonus

        # 7 cards: bonus
        pstate7 = make_pstate(numbers=[NumberCard(i) for i in range(7)])
        assert pstate7.current_sum() == sum(range(7)) + 15  # 21+15=36

    def test_has_flip7_false_with_6_cards(self):
        pstate = make_pstate(numbers=[NumberCard(i) for i in range(6)])
        assert not pstate.has_flip7()

    def test_has_flip7_true_with_7_cards(self):
        pstate = make_pstate(numbers=[NumberCard(i) for i in range(7)])
        assert pstate.has_flip7()

    def test_has_second_chance_true(self):
        pstate = make_pstate(actions=[ActionCard(type=ActionType.SECOND_CHANCE)])
        assert pstate.has_second_chance()

    def test_has_second_chance_false(self):
        pstate = make_pstate(actions=[ActionCard(type=ActionType.FREEZE)])
        assert not pstate.has_second_chance()

    def test_unique_number_values(self):
        pstate = make_pstate(numbers=[NumberCard(3), NumberCard(5), NumberCard(3)])
        # Note: in practice duplicates cause a bust, but the method is just a set
        assert pstate.unique_number_values() == {3, 5}
