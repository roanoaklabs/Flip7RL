"""TestDeckBuilder — a helper for constructing deterministic decks in tests."""
from flip7.engine.cards import BaseCard
from flip7.engine.deck import Deck


class TestDeckBuilder:
    """
    Builds a Deck with cards in a specified draw order.

    Usage:
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))
            .then(NumberCard(3))
            .build()
        )
        # deck.draw() -> NumberCard(5) first, then NumberCard(3)
    """

    def __init__(self):
        self._cards: list[BaseCard] = []

    def then(self, card: BaseCard) -> 'TestDeckBuilder':
        """Append a card to the draw sequence."""
        self._cards.append(card)
        return self

    def build(self) -> Deck:
        """Return a Deck with exactly these cards in this draw order."""
        # Deck.__init__ takes draw-order list (index 0 = first drawn)
        return Deck(cards=list(self._cards))
