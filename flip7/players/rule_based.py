from .base import BasePlayer, GameObservation
from ..engine.cards import ActionCard
from ..engine.state import PlayerStatus, HitStay


class RuleBasedPlayer(BasePlayer):
    """Simple rule-based player with a configurable stay threshold.

    Strategy: stay if current sum >= threshold; target the active opponent
    with the highest cumulative score.
    """

    def __init__(self, player_id: int, stay_threshold: int = 15):
        super().__init__(player_id)
        self.stay_threshold = stay_threshold

    def observe(self, observation: GameObservation) -> None:
        pass

    def decide(self, observation: GameObservation) -> HitStay:
        if observation.my_current_sum() >= self.stay_threshold:
            return HitStay.STAY
        return HitStay.HIT

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        active_others = [
            p for p in observation.other_players
            if p.status == PlayerStatus.ACTIVE
        ]
        if not active_others:
            return observation.my_player_id
        return max(active_others, key=lambda p: observation.cumulative_scores[p.player_id]).player_id
