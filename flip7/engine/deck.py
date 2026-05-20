import random
from typing import Optional
from .cards import BaseCard, NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType

# Single source of truth for deck composition
DECK_COMPOSITION: list[BaseCard] = []

# Number cards: one 0, one 1, two 2s, three 3s, four 4s, five 5s, six 6s,
#               seven 7s, eight 8s, nine 9s, ten 10s, eleven 11s, twelve 12s
# Total: 1+1+2+3+4+5+6+7+8+9+10+11+12 = 79
for _v, _count in [
    (0, 1), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6),
    (7, 7), (8, 8), (9, 9), (10, 10), (11, 11), (12, 12),
]:
    DECK_COMPOSITION.extend([NumberCard(value=_v)] * _count)

# Modifier cards (6): +2, +4, +6, +8, +10, x2 (one each)
DECK_COMPOSITION.extend([
    ModifierCard(op=ModifierOp.ADD, value=2),
    ModifierCard(op=ModifierOp.ADD, value=4),
    ModifierCard(op=ModifierOp.ADD, value=6),
    ModifierCard(op=ModifierOp.ADD, value=8),
    ModifierCard(op=ModifierOp.ADD, value=10),
    ModifierCard(op=ModifierOp.MULTIPLY, value=2),
])

# Action cards (9): Freeze x3, FlipThree x3, SecondChance x3
DECK_COMPOSITION.extend([
    ActionCard(type=ActionType.FREEZE),
    ActionCard(type=ActionType.FREEZE),
    ActionCard(type=ActionType.FREEZE),
    ActionCard(type=ActionType.FLIP_THREE),
    ActionCard(type=ActionType.FLIP_THREE),
    ActionCard(type=ActionType.FLIP_THREE),
    ActionCard(type=ActionType.SECOND_CHANCE),
    ActionCard(type=ActionType.SECOND_CHANCE),
    ActionCard(type=ActionType.SECOND_CHANCE),
])


class Deck:
    """A deck of cards. draw() returns the next card in sequence."""

    def __init__(self, cards: Optional[list[BaseCard]] = None):
        """
        Initialize deck. cards is the draw order: index 0 = first drawn.
        Internally stored reversed so pop() from end is O(1).
        """
        if cards is None:
            self._cards = list(reversed(DECK_COMPOSITION))
        else:
            self._cards = list(reversed(cards))

    def shuffle(self, seed: Optional[int] = None) -> None:
        """Shuffle the deck in place. Uses random.Random for seedability."""
        rng = random.Random(seed)
        rng.shuffle(self._cards)

    def draw(self) -> Optional[BaseCard]:
        """Draw the top card. Returns None if deck is empty."""
        if not self._cards:
            return None
        return self._cards.pop()

    def is_empty(self) -> bool:
        return len(self._cards) == 0

    @property
    def remaining(self) -> int:
        return len(self._cards)

    def add_to_bottom(self, cards: list[BaseCard]) -> None:
        """Add cards to the bottom of the deck (they will be drawn last)."""
        # In our reversed storage, bottom = index 0
        self._cards = list(reversed(cards)) + self._cards

    def peek_all(self) -> list[BaseCard]:
        """Return all cards in draw order (first drawn first). Does not modify deck."""
        return list(reversed(self._cards))
