from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from ..engine.cards import ActionCard
from ..engine.state import GameState, PlayerStatus, HitStay


@dataclass
class GameObservation:
    """Limited view of game state — only what a human at the table can see."""
    my_player_id: int
    my_number_cards: tuple
    my_modifier_cards: tuple
    my_action_cards: tuple
    my_status: PlayerStatus
    other_players: tuple   # tuple of PlayerRoundState (face-up info)
    cumulative_scores: tuple
    round_number: int
    num_players: int
    deck_remaining: int    # approximate count only


class BasePlayer(ABC):
    def __init__(self, player_id: int):
        self.player_id = player_id

    @abstractmethod
    def observe(self, observation: GameObservation) -> None:
        """Called to update player's internal state with current observation."""

    @abstractmethod
    def decide(self, observation: GameObservation) -> HitStay:
        """Return HIT or STAY."""

    @abstractmethod
    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        """Return player_id to target with action card."""


class AlwaysHitPlayer(BasePlayer):
    """Simple player that always hits. Used for testing."""

    def observe(self, observation: GameObservation) -> None:
        pass

    def decide(self, observation: GameObservation) -> HitStay:
        return HitStay.HIT

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        # Target first available active player (not self)
        for p in observation.other_players:
            if p.status == PlayerStatus.ACTIVE:
                return p.player_id
        return observation.my_player_id


class AlwaysStayPlayer(BasePlayer):
    """Simple player that always stays. Used for testing."""

    def observe(self, observation: GameObservation) -> None:
        pass

    def decide(self, observation: GameObservation) -> HitStay:
        return HitStay.STAY

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        for p in observation.other_players:
            if p.status == PlayerStatus.ACTIVE:
                return p.player_id
        return observation.my_player_id


class RandomPlayer(BasePlayer):
    """Player that makes random decisions. Used for testing."""

    def __init__(self, player_id: int, seed: Optional[int] = None):
        super().__init__(player_id)
        import random
        self._rng = random.Random(seed)

    def observe(self, observation: GameObservation) -> None:
        pass

    def decide(self, observation: GameObservation) -> HitStay:
        return self._rng.choice([HitStay.HIT, HitStay.STAY])

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        active = [p for p in observation.other_players if p.status == PlayerStatus.ACTIVE]
        if active:
            return self._rng.choice(active).player_id
        return observation.my_player_id
