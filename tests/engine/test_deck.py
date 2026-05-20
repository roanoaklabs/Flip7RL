"""Tests for flip7/engine/deck.py"""
import pytest
from flip7.engine.deck import Deck, DECK_COMPOSITION
from flip7.engine.cards import NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType


class TestDeckComposition:
    def test_total_card_count(self):
        assert len(DECK_COMPOSITION) == 94

    def test_number_card_count(self):
        number_cards = [c for c in DECK_COMPOSITION if isinstance(c, NumberCard)]
        assert len(number_cards) == 79

    def test_modifier_card_count(self):
        modifier_cards = [c for c in DECK_COMPOSITION if isinstance(c, ModifierCard)]
        assert len(modifier_cards) == 6

    def test_action_card_count(self):
        action_cards = [c for c in DECK_COMPOSITION if isinstance(c, ActionCard)]
        assert len(action_cards) == 9

    def test_freeze_count(self):
        freezes = [c for c in DECK_COMPOSITION
                   if isinstance(c, ActionCard) and c.type == ActionType.FREEZE]
        assert len(freezes) == 3

    def test_flip_three_count(self):
        ft = [c for c in DECK_COMPOSITION
              if isinstance(c, ActionCard) and c.type == ActionType.FLIP_THREE]
        assert len(ft) == 3

    def test_second_chance_count(self):
        sc = [c for c in DECK_COMPOSITION
              if isinstance(c, ActionCard) and c.type == ActionType.SECOND_CHANCE]
        assert len(sc) == 3

    def test_modifier_add_cards(self):
        adds = [c for c in DECK_COMPOSITION
                if isinstance(c, ModifierCard) and c.op == ModifierOp.ADD]
        add_values = sorted(c.value for c in adds)
        assert add_values == [2, 4, 6, 8, 10]

    def test_modifier_multiply_card(self):
        muls = [c for c in DECK_COMPOSITION
                if isinstance(c, ModifierCard) and c.op == ModifierOp.MULTIPLY]
        assert len(muls) == 1
        assert muls[0].value == 2

    def test_number_card_counts_per_value(self):
        """Verify count of each number card value."""
        expected = {
            0: 1, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6,
            7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12,
        }
        actual = {}
        for c in DECK_COMPOSITION:
            if isinstance(c, NumberCard):
                actual[c.value] = actual.get(c.value, 0) + 1
        assert actual == expected


class TestDeck:
    def test_default_deck_has_94_cards(self):
        deck = Deck()
        assert deck.remaining == 94

    def test_draw_reduces_remaining(self):
        deck = Deck()
        deck.draw()
        assert deck.remaining == 93

    def test_draw_returns_none_when_empty(self):
        deck = Deck(cards=[])
        assert deck.draw() is None

    def test_is_empty(self):
        deck = Deck(cards=[])
        assert deck.is_empty()

    def test_not_empty_with_cards(self):
        deck = Deck()
        assert not deck.is_empty()

    def test_shuffle_seed_reproducible(self):
        deck1 = Deck()
        deck2 = Deck()
        deck1.shuffle(seed=42)
        deck2.shuffle(seed=42)
        order1 = deck1.peek_all()
        order2 = deck2.peek_all()
        assert order1 == order2

    def test_shuffle_different_seeds_differ(self):
        deck1 = Deck()
        deck2 = Deck()
        deck1.shuffle(seed=1)
        deck2.shuffle(seed=2)
        # Very unlikely to be identical with different seeds
        assert deck1.peek_all() != deck2.peek_all()

    def test_draw_order_preserved(self):
        """Cards are drawn in the order supplied to Deck(cards=...)."""
        cards = [NumberCard(value=5), NumberCard(value=3), NumberCard(value=7)]
        deck = Deck(cards=cards)
        assert deck.draw() == NumberCard(value=5)
        assert deck.draw() == NumberCard(value=3)
        assert deck.draw() == NumberCard(value=7)
        assert deck.draw() is None

    def test_remaining_decrements_to_zero(self):
        cards = [NumberCard(value=i) for i in range(5)]
        deck = Deck(cards=cards)
        for _ in range(5):
            deck.draw()
        assert deck.remaining == 0
        assert deck.is_empty()
