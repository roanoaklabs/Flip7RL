"""
Demo: play one seeded game between 3 random players and narrate every event.
Run with:  python3 demo.py
           python3 demo.py --seed 99 --players 4 --quiet
           python3 demo.py --no-gui   (text-only narration)
"""
import argparse
import sys
from flip7.engine.cards import NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType
from flip7.engine.state import GameState, PlayerStatus, HitStay
from flip7.engine.game import GameEngine, WIN_SCORE
from flip7.players.base import BasePlayer, GameObservation


# ── Verbose random player ──────────────────────────────────────────────────────

import random as _random

_last_round_narrated = 0  # shared sentinel so only the first player prints the header

class NarratingRandomPlayer(BasePlayer):
    """Hits or stays randomly; prints its decision."""
    def __init__(self, player_id: int, seed=None, quiet: bool = False):
        super().__init__(player_id)
        self._rng = _random.Random(seed)
        self.quiet = quiet
        self._prev_obs: GameObservation | None = None
        self._prev_decision: HitStay | None = None

    def observe(self, obs: GameObservation) -> None:
        pass

    def decide(self, obs: GameObservation) -> HitStay:
        global _last_round_narrated
        if not self.quiet and obs.round_number != _last_round_narrated:
            _last_round_narrated = obs.round_number
            print(f"\n  ── Round {obs.round_number} ──")

        choice = self._rng.choice([HitStay.HIT, HitStay.STAY])
        if not self.quiet:
            cards = _format_number_cards(obs.my_number_cards)
            mods  = _format_modifier_cards(obs.my_modifier_cards)
            hand  = f"{cards}{(' + ' + mods) if mods else ''}"
            print(f"    P{self.player_id} [{hand}] sum={_sum(obs)} → {choice.value.upper()}")
        self._prev_obs = obs
        self._prev_decision = choice
        return choice

    def on_hit_result(self, obs: GameObservation) -> None:
        if self.quiet or self._prev_obs is None:
            self._prev_obs = obs
            return
        prev = self._prev_obs
        prev_nums = {c.value for c in prev.my_number_cards}
        new_nums = [c for c in obs.my_number_cards if c.value not in prev_nums]
        new_mods = obs.my_modifier_cards[len(prev.my_modifier_cards):]

        if new_nums:
            for c in new_nums:
                print(f"      ← P{self.player_id} drew #{c.value}")
        elif new_mods:
            for m in new_mods:
                print(f"      ← P{self.player_id} drew {_card_str(m)}")
        else:
            print(f"      ← P{self.player_id} drew action card")
        self._prev_obs = obs

    def choose_target(self, action_card: ActionCard, obs: GameObservation) -> int:
        global _last_round_narrated
        if not self.quiet and obs.round_number != _last_round_narrated:
            _last_round_narrated = obs.round_number
            print(f"\n  ── Round {obs.round_number} ──")
        active = [p.player_id for p in obs.other_players
                  if p.status == PlayerStatus.ACTIVE]
        if not active:
            return self.player_id
        target = self._rng.choice(active)
        if not self.quiet:
            print(f"      ↳ P{self.player_id} plays {_card_str(action_card)} → P{target}")
        return target


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _format_number_cards(cards) -> str:
    if not cards:
        return "—"
    return "[" + " ".join(str(c.value) for c in sorted(cards, key=lambda c: c.value)) + "]"

def _format_modifier_cards(cards) -> str:
    parts = []
    for c in cards:
        if c.op == ModifierOp.MULTIPLY:
            parts.append(f"x{c.value}")
        else:
            parts.append(f"+{c.value}")
    return " ".join(parts)

def _sum(obs) -> int:
    from flip7.engine.state import PlayerRoundState
    prs = PlayerRoundState(
        player_id=obs.my_player_id,
        number_cards=obs.my_number_cards,
        modifier_cards=obs.my_modifier_cards,
        action_cards=obs.my_action_cards,
        status=obs.my_status,
    )
    return prs.current_sum()

def _card_str(card) -> str:
    if isinstance(card, NumberCard):
        return f"#{card.value}"
    if isinstance(card, ModifierCard):
        if card.op == ModifierOp.MULTIPLY:
            return f"x{card.value}"
        return f"+{card.value}"
    if isinstance(card, ActionCard):
        return {
            ActionType.FREEZE: "FREEZE",
            ActionType.FLIP_THREE: "FLIP_THREE",
            ActionType.SECOND_CHANCE: "SECOND_CHANCE",
        }[card.type]
    return str(card)

def _status_icon(status: PlayerStatus) -> str:
    return {
        PlayerStatus.ACTIVE:  "▶",
        PlayerStatus.STAYED:  "✓",
        PlayerStatus.BUSTED:  "✗",
        PlayerStatus.FROZEN:  "❄",
    }[status]


# ── Diff-based narration ───────────────────────────────────────────────────────

def narrate_diff(prev: GameState, curr: GameState) -> list[str]:
    """Compare two consecutive snapshots and return human-readable lines."""
    lines = []

    if prev.round_number != curr.round_number:
        lines.append(f"\n{'═'*60}")
        lines.append(f"  ROUND {curr.round_number}   (dealer: P{curr.dealer_idx})")
        lines.append(f"{'═'*60}")
        lines.append(f"  Cumulative before: {dict(enumerate(prev.cumulative_scores))}")
        return lines

    # Round state changes
    prev_rs = prev.round_state
    curr_rs = curr.round_state
    if prev_rs is None or curr_rs is None:
        return lines

    is_deal = curr_rs.phase == "deal"

    # Queue change: card added (action card drawn and queued)
    if len(curr_rs.action_queue) > len(prev_rs.action_queue):
        added = curr_rs.action_queue[len(prev_rs.action_queue):]
        for card, actor in added:
            if is_deal:
                lines.append(f"  P{actor} dealt {_card_str(card)}")
            else:
                lines.append(f"  ↳ {_card_str(card)} queued by P{actor}")

    # Queue change: card removed (action card resolved — infer target from same-diff changes)
    if len(curr_rs.action_queue) < len(prev_rs.action_queue):
        removed = prev_rs.action_queue[:len(prev_rs.action_queue) - len(curr_rs.action_queue)]
        for card, actor in removed:
            target_str = ""
            if card.type == ActionType.FLIP_THREE:
                targets = [
                    pid for pid in range(curr.num_players)
                    if (set(c.value for c in curr_rs.player_states[pid].number_cards) !=
                        set(c.value for c in prev_rs.player_states[pid].number_cards))
                    or (prev_rs.player_states[pid].status != PlayerStatus.BUSTED and
                        curr_rs.player_states[pid].status == PlayerStatus.BUSTED)
                ]
                if targets:
                    target_str = f" → P{targets[0]}"
            elif card.type == ActionType.FREEZE:
                frozen = [
                    pid for pid in range(curr.num_players)
                    if (prev_rs.player_states[pid].status != PlayerStatus.FROZEN and
                        curr_rs.player_states[pid].status == PlayerStatus.FROZEN)
                ]
                if frozen:
                    target_str = f" → P{frozen[0]}"
            lines.append(f"  ↳ P{actor} applies {_card_str(card)}{target_str}:")

    # Per-player changes
    for pid in range(curr.num_players):
        prev_p = prev_rs.player_states[pid]
        curr_p = curr_rs.player_states[pid]

        # Status change
        if prev_p.status != curr_p.status:
            icon = _status_icon(curr_p.status)
            score = curr_p.current_sum()
            if curr_p.status == PlayerStatus.BUSTED:
                if curr_p.bust_card_value is not None:
                    hand_had = _format_number_cards(curr_p.number_cards)
                    verb = "dealt" if is_deal else "drew"
                    lines.append(
                        f"  {icon} P{pid} {verb} #{curr_p.bust_card_value}"
                        f" — duplicate! (had {hand_had}) → BUSTED  (score this round: 0)"
                    )
                else:
                    lines.append(f"  {icon} P{pid} BUSTED  (score this round: 0)")
            elif curr_p.status == PlayerStatus.STAYED:
                lines.append(f"  {icon} P{pid} STAYED  (round score: {score})")
            elif curr_p.status == PlayerStatus.FROZEN:
                lines.append(f"  {icon} P{pid} FROZEN  (round score: {score})")

        # New number card
        new_nums = set(c.value for c in curr_p.number_cards) - set(c.value for c in prev_p.number_cards)
        for v in new_nums:
            hand = _format_number_cards(curr_p.number_cards)
            mods = _format_modifier_cards(curr_p.modifier_cards)
            hand_str = f"{hand}{(' + ' + mods) if mods else ''}"
            verb = "dealt" if is_deal else "drew"
            lines.append(f"  P{pid} {verb} #{v}  → hand {hand_str}  sum={curr_p.current_sum()}")
            if curr_p.has_flip7():
                lines.append(f"  ★ P{pid} FLIP 7! +15 bonus  round score={curr_p.current_sum()}")

        # New modifier card
        new_mods = len(curr_p.modifier_cards) - len(prev_p.modifier_cards)
        if new_mods > 0:
            added = curr_p.modifier_cards[len(prev_p.modifier_cards):]
            for m in added:
                verb = "dealt" if is_deal else "drew"
                lines.append(f"  P{pid} {verb} {_card_str(m)}  sum={curr_p.current_sum()}")

        # New action card held (Second Chance given to player)
        new_acs = len(curr_p.action_cards) - len(prev_p.action_cards)
        if new_acs > 0:
            added = curr_p.action_cards[len(prev_p.action_cards):]
            for a in added:
                lines.append(f"  P{pid} received {_card_str(a)}")

        # Lost an action card (Second Chance used)
        if len(curr_p.action_cards) < len(prev_p.action_cards):
            lines.append(f"  P{pid} used SECOND_CHANCE  (saved from bust)")

    return lines


def narrate_round_end(prev: GameState, curr: GameState) -> list[str]:
    lines = []
    if curr.round_state is None:
        return lines
    if curr.cumulative_scores != prev.cumulative_scores:
        lines.append(f"\n  Round {curr.round_number} scores:")
        for pid in range(curr.num_players):
            gained = curr.cumulative_scores[pid] - prev.cumulative_scores[pid]
            total  = curr.cumulative_scores[pid]
            icon = _status_icon(curr.round_state.player_states[pid].status)
            lines.append(f"    P{pid} {icon}  +{gained}  →  cumulative {total}")
        lines.append("")
    return lines


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed",    type=int, default=42)
    parser.add_argument("--players", type=int, default=3)
    parser.add_argument("--quiet",   action="store_true", help="suppress hit/stay prints")
    parser.add_argument("--no-gui",  action="store_false", dest="visual", help="disable pygame replay viewer")
    args = parser.parse_args()

    if args.visual:
        from flip7.players.base import RandomPlayer
        from flip7.simulation.runner import run_game
        from flip7.ui import replay_game
        players = [RandomPlayer(i, seed=args.seed + i) for i in range(args.players)]
        result  = run_game(players, seed=args.seed, full_log=True)
        winner  = result.winner_id
        print(f"Game finished — P{winner} wins  "
              f"({result.num_rounds} rounds, {result.num_states} states recorded)")
        assert result.log is not None
        player_names = [type(p).__name__ for p in players]
        replay_game(result.log, title=f"Flip 7 — seed={args.seed} players={args.players}",
                    player_names=player_names)
        return

    print(f"Flip 7 demo  seed={args.seed}  players={args.players}")
    print(f"First to 200 wins.\n")

    players = [
        NarratingRandomPlayer(i, seed=args.seed + i, quiet=args.quiet)
        for i in range(args.players)
    ]

    engine = GameEngine(num_players=args.players, seed=args.seed)
    state, deck = engine.new_game()
    discard: list = []
    prev_state = state

    while True:
        state, deck, discard, round_log = engine.play_round(state, deck, discard, players)

        # Narrate this round immediately after it finishes
        combined = [prev_state] + round_log
        for i in range(1, len(combined)):
            p, c = combined[i - 1], combined[i]
            if c.cumulative_scores != p.cumulative_scores:
                for line in narrate_round_end(p, c):
                    print(line)
            else:
                for line in narrate_diff(p, c):
                    print(line)

        prev_state = state

        if max(state.cumulative_scores) >= WIN_SCORE:
            break

    # Final result
    winner = max(range(args.players), key=lambda i: state.cumulative_scores[i])
    print(f"{'═'*60}")
    print(f"  GAME OVER after {state.round_number} round(s)")
    print(f"  Final scores: {dict(enumerate(state.cumulative_scores))}")
    print(f"  Winner: P{winner} with {state.cumulative_scores[winner]} points")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
