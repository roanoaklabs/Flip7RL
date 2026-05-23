from .base import BasePlayer, GameObservation
from ..engine.cards import ActionCard, ModifierOp, ActionType
from ..engine.state import PlayerStatus, HitStay


class HumanPlayer(BasePlayer):
    """Interactive CLI player — prompts a human for every decision."""

    def __init__(self, player_id: int, name: str = "Human"):
        super().__init__(player_id)
        self.name = name

    def observe(self, observation: GameObservation) -> None:
        self._display_state(observation)

    def _display_state(self, observation: GameObservation) -> None:
        sep = "=" * 52
        print(f"\n{sep}")
        print(f"  Player {observation.my_player_id} — {self.name}")
        print(sep)

        num_vals = [str(c.value) for c in observation.my_number_cards]
        print(f"  Number cards : {', '.join(num_vals) if num_vals else '(none)'}")

        mod_strs = []
        for m in observation.my_modifier_cards:
            mod_strs.append(f"x{m.value}" if m.op == ModifierOp.MULTIPLY else f"+{m.value}")
        print(f"  Modifiers    : {', '.join(mod_strs) if mod_strs else '(none)'}")

        act_strs = [c.type.value for c in observation.my_action_cards]
        print(f"  Action cards : {', '.join(act_strs) if act_strs else '(none)'}")
        print(f"  Current sum  : {observation.my_current_sum()}")
        print(f"  Cumulative   : {observation.my_cumulative_score()}")
        print()
        print("  Other players:")
        for p in observation.other_players:
            total = observation.cumulative_scores[p.player_id]
            print(
                f"    Player {p.player_id}: sum={p.current_sum():>3}  "
                f"total={total:>3}  status={p.status.value}"
            )

    def decide(self, observation: GameObservation) -> HitStay:
        while True:
            raw = input(f"\n  [{self.name}] Hit or Stay? (h/s): ").strip().lower()
            if raw in ("h", "hit"):
                return HitStay.HIT
            if raw in ("s", "stay"):
                return HitStay.STAY
            print("  Please enter 'h' for Hit or 's' for Stay.")

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        print(f"\n  [{self.name}] Choose target for {action_card.type.value}:")

        # Build candidate list: active opponents + self if active
        candidates: list[int] = [
            p.player_id for p in observation.other_players
            if p.status == PlayerStatus.ACTIVE
        ]
        if observation.my_status == PlayerStatus.ACTIVE:
            candidates.append(observation.my_player_id)

        if not candidates:
            return observation.my_player_id

        for i, pid in enumerate(candidates, start=1):
            label = f"Player {pid}"
            if pid == observation.my_player_id:
                label += " (you)"
            total = observation.cumulative_scores[pid]
            print(f"    {i}. {label}  total={total}")

        while True:
            raw = input("  Choice: ").strip()
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(candidates):
                    return candidates[idx]
            except ValueError:
                pass
            print(f"  Enter a number between 1 and {len(candidates)}.")
