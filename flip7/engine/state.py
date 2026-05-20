from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from .cards import BaseCard, NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType


class PlayerStatus(Enum):
    ACTIVE = "active"
    STAYED = "stayed"
    BUSTED = "busted"
    FROZEN = "frozen"  # banked and exited, like stayed but forced


class HitStay(Enum):
    HIT = "hit"
    STAY = "stay"


@dataclass(frozen=True)
class PlayerRoundState:
    player_id: int
    number_cards: tuple  # tuple[NumberCard, ...]
    modifier_cards: tuple  # tuple[ModifierCard, ...]
    action_cards: tuple  # tuple[ActionCard, ...] - held action cards (SecondChance)
    status: PlayerStatus

    def current_sum(self) -> int:
        """Compute score: sum numbers, apply x2, add +N, add 15 if flip7."""
        num_sum = sum(c.value for c in self.number_cards)
        # Apply multiply modifiers first
        for m in self.modifier_cards:
            if m.op == ModifierOp.MULTIPLY:
                num_sum *= m.value
        # Then add modifiers
        for m in self.modifier_cards:
            if m.op == ModifierOp.ADD:
                num_sum += m.value
        # Flip 7 bonus: exactly 7 number cards
        if len(self.number_cards) == 7:
            num_sum += 15
        return num_sum

    def has_flip7(self) -> bool:
        return len(self.number_cards) == 7

    def has_second_chance(self) -> bool:
        return any(a.type == ActionType.SECOND_CHANCE for a in self.action_cards)

    def unique_number_values(self) -> set:
        return {c.value for c in self.number_cards}


@dataclass(frozen=True)
class RoundState:
    player_states: tuple  # tuple[PlayerRoundState, ...] indexed by player_id
    deck_remaining: int   # count only (for observation)
    current_player_idx: int  # whose turn it is
    action_queue: tuple   # tuple of (ActionCard, acting_player_id)
    phase: str            # "deal" or "main"


@dataclass(frozen=True)
class GameState:
    # Game-level (persists across rounds)
    cumulative_scores: tuple  # tuple[int, ...] indexed by player_id
    round_number: int
    dealer_idx: int
    num_players: int

    # Round-level (None between rounds)
    round_state: Optional[RoundState]

    # Step index / timestamp
    t: int
