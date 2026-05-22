"""
Demo: play one seeded game between 3 random players and narrate every event.
Run with:  python3 demo.py
           python3 demo.py --seed 99 --players 4 --quiet
"""
import argparse
import sys
from flip7.engine.cards import NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType
from flip7.engine.state import GameState, PlayerStatus, HitStay
from flip7.engine.game import GameEngine
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

        prev_obs = self._prev_obs
        same_round = prev_obs is not None and obs.round_number == prev_obs.round_number
        if not self.quiet and self._prev_decision == HitStay.HIT and same_round and prev_obs is not None:
            self._narrate_hit_result(prev_obs, obs)

        choice = self._rng.choice([HitStay.HIT, HitStay.STAY])
        if not self.quiet:
            cards = _format_number_cards(obs.my_number_cards)
            mods  = _format_modifier_cards(obs.my_modifier_cards)
            hand  = f"{cards}{(' + ' + mods) if mods else ''}"
            print(f"    P{self.player_id} [{hand}] sum={_sum(obs)} → {choice.value.upper()}")
        self._prev_obs = obs
        self._prev_decision = choice
        return choice

    def _narrate_hit_result(self, prev: GameObservation, curr: GameObservation) -> None:
        prev_nums = {c.value for c in prev.my_number_cards}
        new_nums = [c for c in curr.my_number_cards if c.value not in prev_nums]
        new_mods = curr.my_modifier_cards[len(prev.my_modifier_cards):]

        if new_nums:
            for c in new_nums:
                print(f"      ← P{self.player_id} drew #{c.value}")
        elif new_mods:
            for m in new_mods:
                print(f"      ← P{self.player_id} drew {_card_str(m)}")
        else:
            print(f"      ← P{self.player_id} drew action card")

    def choose_target(self, action_card: ActionCard, obs: GameObservation) -> int:
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

    # Phase transition
    if prev_rs.phase != curr_rs.phase:
        lines.append(f"\n  ── {curr_rs.phase.upper()} PHASE ──")
        return lines

    # Per-player changes
    for pid in range(curr.num_players):
        prev_p = prev_rs.player_states[pid]
        curr_p = curr_rs.player_states[pid]

        # Status change
        if prev_p.status != curr_p.status:
            icon = _status_icon(curr_p.status)
            score = curr_p.current_sum()
            if curr_p.status == PlayerStatus.BUSTED:
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
            lines.append(f"  P{pid} drew #{v}  → hand {hand_str}  sum={curr_p.current_sum()}")
            if curr_p.has_flip7():
                lines.append(f"  ★ P{pid} FLIP 7! +15 bonus  round score={curr_p.current_sum()}")

        # New modifier card
        new_mods = len(curr_p.modifier_cards) - len(prev_p.modifier_cards)
        if new_mods > 0:
            added = curr_p.modifier_cards[len(prev_p.modifier_cards):]
            for m in added:
                lines.append(f"  P{pid} drew {_card_str(m)}  sum={curr_p.current_sum()}")

        # New action card held
        new_acs = len(curr_p.action_cards) - len(prev_p.action_cards)
        if new_acs > 0:
            added = curr_p.action_cards[len(prev_p.action_cards):]
            for a in added:
                lines.append(f"  P{pid} received {_card_str(a)}")

        # Lost an action card (Second Chance used or end-of-round discard)
        if len(curr_p.action_cards) < len(prev_p.action_cards):
            lines.append(f"  P{pid} used SECOND_CHANCE  (saved from bust)")

    # Queue change: something was added
    if len(curr_rs.action_queue) > len(prev_rs.action_queue):
        added = curr_rs.action_queue[len(prev_rs.action_queue):]
        for card, actor in added:
            lines.append(f"  ↳ {_card_str(card)} queued by P{actor}")

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
    args = parser.parse_args()

    print(f"Flip 7 demo  seed={args.seed}  players={args.players}")
    print(f"First to 200 wins.\n")

    players = [
        NarratingRandomPlayer(i, seed=args.seed + i, quiet=args.quiet)
        for i in range(args.players)
    ]

    engine = GameEngine(num_players=args.players, seed=args.seed)
    log = engine.play_game(players)

    # Narrate the log
    for i, curr in enumerate(log):
        if i == 0:
            continue
        prev = log[i - 1]

        # Round-end boundary: cumulative scores just updated
        if curr.cumulative_scores != prev.cumulative_scores:
            for line in narrate_round_end(prev, curr):
                print(line)
            continue

        for line in narrate_diff(prev, curr):
            print(line)

    # Final result
    final = log[-1]
    winner = max(range(args.players), key=lambda i: final.cumulative_scores[i])
    print(f"{'═'*60}")
    print(f"  GAME OVER after {final.round_number} round(s)")
    print(f"  Final scores: {dict(enumerate(final.cumulative_scores))}")
    print(f"  Winner: P{winner} with {final.cumulative_scores[winner]} points")
    print(f"{'═'*60}")
    print(f"\n  Total game state snapshots logged: {len(log)}")


if __name__ == "__main__":
    main()
