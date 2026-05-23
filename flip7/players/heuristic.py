from .base import BasePlayer, GameObservation
from ..engine.cards import ActionCard, ActionType
from ..engine.state import PlayerStatus, HitStay


class HeuristicPlayer(BasePlayer):
    """Sophisticated hand-tuned player using multi-factor heuristics.

    Key rules:
    - Always hit with 6 unique cards (one more = Flip 7 bonus)
    - Stay immediately if banking now wins the game
    - Dynamic stay threshold that rises with card count
    - Become more aggressive when an opponent is close to 200
    - Freeze the biggest cumulative+round threat; Flip Three the player
      with the most cards (highest bust risk for them)
    """

    # Stay threshold indexed by number of unique cards held (0–5)
    _THRESHOLDS = [100, 100, 12, 16, 20, 24]

    def observe(self, observation: GameObservation) -> None:
        pass

    def decide(self, observation: GameObservation) -> HitStay:
        my_sum = observation.my_current_sum()
        my_total = observation.my_cumulative_score()
        num_unique = observation.my_unique_card_count()

        # Banking now wins — no need to risk further cards
        if my_total + my_sum >= 200:
            return HitStay.STAY

        # Six unique cards: one more unique card = Flip 7 bonus + round ends
        if num_unique >= 6:
            return HitStay.HIT

        threshold = self._THRESHOLDS[num_unique]

        # Become more aggressive when an opponent is close to winning
        max_opp_total = max(
            (observation.cumulative_scores[p.player_id] for p in observation.other_players),
            default=0,
        )
        if max_opp_total >= 160:
            threshold = max(threshold - 5, 5)

        return HitStay.STAY if my_sum >= threshold else HitStay.HIT

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        active_others = [p for p in observation.other_players if p.status == PlayerStatus.ACTIVE]
        if not active_others:
            return observation.my_player_id

        if action_card.type == ActionType.FREEZE:
            # Freeze the biggest threat: cumulative score + current round sum
            return max(
                active_others,
                key=lambda p: observation.cumulative_scores[p.player_id] + p.current_sum(),
            ).player_id

        if action_card.type == ActionType.FLIP_THREE:
            # Force cards on the player with the most unique cards (hardest to hit safely)
            return max(active_others, key=lambda p: len(p.number_cards)).player_id

        # Default: highest cumulative score
        return max(
            active_others,
            key=lambda p: observation.cumulative_scores[p.player_id],
        ).player_id
