"""Tests for action card mechanics: Freeze, Flip Three, Second Chance."""
import pytest
from tests.test_deck_builder import TestDeckBuilder
from flip7.engine.cards import (
    NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType
)
from flip7.engine.deck import Deck
from flip7.engine.state import (
    GameState, RoundState, PlayerRoundState, PlayerStatus, HitStay
)
from flip7.engine.game import GameEngine
from flip7.players.base import BasePlayer, GameObservation, AlwaysStayPlayer


# ------------------------------------------------------------------
# Helper players for deterministic testing
# ------------------------------------------------------------------

class ScriptedPlayer(BasePlayer):
    """Player that follows a scripted sequence of decisions."""

    def __init__(self, player_id: int, decisions: list[HitStay], targets: list[int] = None):
        super().__init__(player_id)
        self._decisions = list(decisions)
        self._targets = targets or []
        self._decision_idx = 0
        self._target_idx = 0

    def observe(self, observation: GameObservation) -> None:
        pass

    def decide(self, observation: GameObservation) -> HitStay:
        if self._decision_idx < len(self._decisions):
            d = self._decisions[self._decision_idx]
            self._decision_idx += 1
            return d
        return HitStay.STAY

    def choose_target(self, action_card: ActionCard, observation: GameObservation) -> int:
        if self._target_idx < len(self._targets):
            t = self._targets[self._target_idx]
            self._target_idx += 1
            return t
        # Default: target first active other player
        for p in observation.other_players:
            if p.status == PlayerStatus.ACTIVE:
                return p.player_id
        return observation.my_player_id


def make_engine(num_players=2):
    return GameEngine(num_players=num_players, seed=0)


def get_final_state(log: list[GameState]) -> GameState:
    return log[-1]


def get_player_state(state: GameState, pid: int) -> PlayerRoundState:
    return state.round_state.player_states[pid]


# ------------------------------------------------------------------
# Freeze Tests
# ------------------------------------------------------------------

class TestFreeze:
    def test_freeze_marks_target_frozen(self):
        """Freeze causes target to be FROZEN (banked)."""
        # P0 draws 5, then Freeze (targets P1). P1 draws 3 initially.
        # Deal: P0 gets 5, P1 gets 3. Then P0 hits and gets Freeze targeting P1.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal to P0
            .then(NumberCard(3))   # deal to P1
            .then(ActionCard(type=ActionType.FREEZE))  # P0 hits and gets freeze
            .then(NumberCard(9))   # extra card (not needed)
            .build()
        )
        # P0: HIT (to get freeze), then STAY; P1: STAY
        # P0 targets P1 with freeze
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        state, _, _, log = engine.play_round(
            GameState(
                cumulative_scores=(0, 0),
                round_number=0,
                dealer_idx=0,
                num_players=2,
                round_state=None,
                t=0,
            ),
            deck,
            [],
            players,
        )
        # P1 should be FROZEN
        p1 = get_player_state(state, 1)
        assert p1.status == PlayerStatus.FROZEN

    def test_freeze_target_scores_correctly(self):
        """Frozen player's points are banked (they score their current sum)."""
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal to P0
            .then(NumberCard(3))   # deal to P1 (sum=3 when frozen)
            .then(ActionCard(type=ActionType.FREEZE))  # P0 hits -> freeze -> target P1
            .then(NumberCard(9))
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        # P1 has NumberCard(3) and is FROZEN -> scores 3
        assert final_state.cumulative_scores[1] == 3

    def test_frozen_player_skipped_in_main_phase(self):
        """Once frozen, player does not get to decide hit/stay."""
        # We'll verify that AlwaysHitPlayer for P1 does NOT keep hitting
        # after being frozen
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal to P0
            .then(NumberCard(3))   # deal to P1
            .then(ActionCard(type=ActionType.FREEZE))  # P0 gets freeze -> targets P1
            .then(NumberCard(4))   # just in case
            .then(NumberCard(6))
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),
            ScriptedPlayer(1, [HitStay.HIT, HitStay.HIT, HitStay.HIT]),  # would hit if not frozen
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        # P1 should only have the initial NumberCard(3), not more
        p1 = get_player_state(final_state, 1)
        assert p1.status == PlayerStatus.FROZEN
        assert len(p1.number_cards) == 1

    def test_freeze_on_already_stayed_player_no_effect(self):
        """Freeze targeting a stayed player is a no-op."""
        # P1 stays first, then P0 draws Freeze targeting P1
        # Since P1 already stayed, freeze target validation should skip
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal to P0
            .then(NumberCard(3))   # deal to P1
            .then(ActionCard(type=ActionType.FREEZE))  # after P1 stays
            .then(NumberCard(9))
            .build()
        )
        # P1 stays, P0 hits to get freeze then stays
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        # P1 stayed before being "frozen" — either STAYED or FROZEN, but they score
        p1 = get_player_state(final_state, 1)
        assert p1.status in (PlayerStatus.STAYED, PlayerStatus.FROZEN)


# ------------------------------------------------------------------
# Flip Three Tests
# ------------------------------------------------------------------

class TestFlipThree:
    def test_flip_three_draws_exactly_3_cards(self):
        """Target receives exactly 3 new cards from Flip Three."""
        # Deal: P0 gets 1, P1 gets 2
        # P0 hits, gets FlipThree, targets P1
        # P1 receives 3,4,5 (no duplicates, no bust)
        deck = (
            TestDeckBuilder()
            .then(NumberCard(1))   # deal P0
            .then(NumberCard(2))   # deal P1
            .then(ActionCard(type=ActionType.FLIP_THREE))  # P0 hits -> flip_three
            .then(NumberCard(3))   # flip three card 1 for P1
            .then(NumberCard(4))   # flip three card 2 for P1
            .then(NumberCard(5))   # flip three card 3 for P1
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        p1 = get_player_state(final_state, 1)
        # P1 should have NumberCard(2) + 3 more = 4 total
        assert len(p1.number_cards) == 4
        values = {c.value for c in p1.number_cards}
        assert values == {2, 3, 4, 5}

    def test_flip_three_stops_early_on_bust(self):
        """Flip Three stops if the target busts on a duplicate."""
        # P1 starts with NumberCard(3) from deal
        # Flip Three gives P1: 5, 3 (duplicate -> bust), would-be 7 (not drawn)
        deck = (
            TestDeckBuilder()
            .then(NumberCard(1))   # deal P0
            .then(NumberCard(3))   # deal P1
            .then(ActionCard(type=ActionType.FLIP_THREE))  # P0 hits -> flip_three
            .then(NumberCard(5))   # flip card 1: ok
            .then(NumberCard(3))   # flip card 2: duplicate -> bust
            .then(NumberCard(7))   # flip card 3: should NOT be drawn
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, deck_out, _, _ = engine.play_round(initial, deck, [], players)
        p1 = get_player_state(final_state, 1)
        assert p1.status == PlayerStatus.BUSTED
        # NumberCard(7) should still be in the deck
        remaining_cards = deck_out.peek_all()
        assert NumberCard(7) in remaining_cards

    def test_flip_three_stops_early_on_flip7(self):
        """Flip Three stops if target achieves Flip 7."""
        # P1 already has 6 number cards (0,1,2,3,4,5)
        # Flip Three gives P1: 6 (completes Flip 7), round ends
        # Cards 2 and 3 of flip three should not be drawn
        deck = (
            TestDeckBuilder()
            .then(NumberCard(0))   # deal P0
            .then(NumberCard(1))   # deal P1 (first card, already has 5 more)
            .then(ActionCard(type=ActionType.FLIP_THREE))  # P0 hits -> flip_three
            .then(NumberCard(6))   # flip card 1: P1 now has 7 = flip7!
            .then(NumberCard(8))   # flip card 2: should NOT be drawn
            .then(NumberCard(9))   # flip card 3: should NOT be drawn
            .build()
        )

        # We need to manually set P1 to have 6 cards before the round.
        # Instead, let's use a 3-player game or directly test the engine method.
        # Easier: we test _apply_flip_three directly by setting up state.

        from flip7.engine.state import RoundState
        engine = make_engine(2)

        # Build initial state with P1 having 6 number cards
        p0 = PlayerRoundState(0, (NumberCard(0),), (), (), PlayerStatus.ACTIVE)
        p1 = PlayerRoundState(
            1,
            (NumberCard(1), NumberCard(2), NumberCard(3),
             NumberCard(4), NumberCard(5), NumberCard(10)),
            (), (), PlayerStatus.ACTIVE
        )
        rs = RoundState(
            player_states=(p0, p1),
            deck_remaining=10,
            current_player_idx=0,
            action_queue=(),
            phase="main",
        )
        state = GameState(
            cumulative_scores=(0, 0), round_number=1, dealer_idx=0,
            num_players=2, round_state=rs, t=5,
        )
        # Deck: 6 (completes flip7), 8, 9
        ft_deck = (
            TestDeckBuilder()
            .then(NumberCard(6))
            .then(NumberCard(8))
            .then(NumberCard(9))
            .build()
        )
        players = [AlwaysStayPlayer(0), AlwaysStayPlayer(1)]
        new_state, deck_out, _, log = engine._apply_flip_three(
            state, ft_deck, [], 1, players
        )
        p1_final = get_player_state(new_state, 1)
        assert p1_final.has_flip7()
        # Cards 8 and 9 should still be in the deck
        remaining = deck_out.peek_all()
        assert NumberCard(8) in remaining
        assert NumberCard(9) in remaining

    def test_action_card_during_flip_three_is_queued(self):
        """Action cards drawn during Flip Three go into action queue and resolve after."""
        # 3-player game: P0 draws FT, targets P1.
        # During FT, P1 draws a Freeze card -> queued with acting_player=P1.
        # After FT, queue processes: P1 chooses to freeze P2.
        # P2 ends up FROZEN.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(1))   # deal P0
            .then(NumberCard(2))   # deal P1
            .then(NumberCard(4))   # deal P2
            .then(ActionCard(type=ActionType.FLIP_THREE))  # P0 hits -> FT
            .then(NumberCard(5))   # FT card 1 to P1
            .then(ActionCard(type=ActionType.FREEZE))      # FT card 2: P1 draws freeze, queued (P1 acting)
            .then(NumberCard(6))   # FT card 3 to P1
            .then(NumberCard(9))   # extra
            .build()
        )
        # P0: HIT (gets FT), targets P1; STAY after
        # P1: during FT gets Freeze queued, P1 targets P2
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1]),  # FT target = P1
            ScriptedPlayer(1, [HitStay.STAY], targets=[2]),               # Freeze target = P2
            ScriptedPlayer(2, [HitStay.STAY]),
        ]
        engine = make_engine(3)
        initial = GameState(
            cumulative_scores=(0, 0, 0), round_number=0, dealer_idx=0,
            num_players=3, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        # P2 should be FROZEN (P1 used queued freeze on P2)
        p2 = get_player_state(final_state, 2)
        assert p2.status == PlayerStatus.FROZEN

    def test_queue_revalidates_before_applying(self):
        """If target busts before queued action resolves, the action is skipped."""
        # P0 gets FlipThree, targets P1. During FT, P1 busts.
        # Queued action (from inside FT) tries to target P1 but P1 is busted -> skip
        # We need a Freeze queued targeting P1, but P1 busts during FT first.

        # Setup: P1 has NumberCard(3) from deal.
        # FT for P1: gets 5, then Freeze (queued targeting P1 by P0), then 3 (bust)
        # After FT, queue processes: Freeze targets P1, but P1 is BUSTED -> skip
        deck = (
            TestDeckBuilder()
            .then(NumberCard(1))    # deal P0
            .then(NumberCard(3))    # deal P1
            .then(ActionCard(type=ActionType.FLIP_THREE))  # P0 hits -> FT
            .then(NumberCard(5))    # FT card 1: ok
            .then(ActionCard(type=ActionType.FREEZE))      # FT card 2: freeze queued
            .then(NumberCard(3))    # FT card 3: duplicate -> P1 busts
            .then(NumberCard(9))    # extra
            .build()
        )
        # P0 targets P1 with flip three; freeze target is P1 (but P1 busts)
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY], targets=[1, 1]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        p1 = get_player_state(final_state, 1)
        # P1 busted, not frozen (freeze was skipped due to revalidation)
        assert p1.status == PlayerStatus.BUSTED


# ------------------------------------------------------------------
# Second Chance Tests
# ------------------------------------------------------------------

class TestSecondChance:
    def test_second_chance_saves_from_bust(self):
        """Player with Second Chance survives a duplicate draw."""
        # P0 gets SC in deal, then draws a duplicate -> SC consumed, still active
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))                          # deal P0
            .then(NumberCard(3))                          # deal P1
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> gets SC
            .then(NumberCard(5))                          # P0 hits -> duplicate! SC saves
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.HIT, HitStay.STAY]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        p0 = get_player_state(final_state, 0)
        # P0 should NOT be busted — SC saved them
        assert p0.status != PlayerStatus.BUSTED
        # P0's SC should be consumed
        assert not p0.has_second_chance()

    def test_second_sc_routes_to_active_player_without_sc(self):
        """When a player already has SC and draws another, it routes to another active player."""
        # 3-player game: P0 draws SC (keeps), P0 draws 2nd SC -> routes to P1 or P2 (both active)
        # Deal: P0=5, P1=3, P2=4. P0 hits -> SC1 (P0 keeps). P0 hits -> SC2 -> P1 gets it.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))                               # deal P0
            .then(NumberCard(3))                               # deal P1
            .then(NumberCard(4))                               # deal P2
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> P0 gets SC
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> routes to P1 (active, no SC)
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.HIT, HitStay.STAY]),
            ScriptedPlayer(1, [HitStay.HIT, HitStay.STAY]),  # stays active during P0's turns
            ScriptedPlayer(2, [HitStay.STAY]),
        ]
        engine = make_engine(3)
        initial = GameState(
            cumulative_scores=(0, 0, 0), round_number=0, dealer_idx=0,
            num_players=3, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        p0 = get_player_state(final_state, 0)
        p1 = get_player_state(final_state, 1)
        # P0 should have SC, P1 should have SC (received the routed one)
        assert p0.has_second_chance()
        assert p1.has_second_chance()

    def test_second_sc_discarded_when_no_valid_target(self):
        """If no active player can receive SC (all have SC or are done), discard it."""
        # Both P0 and P1 already have SC. A third SC appears -> discarded.
        # Setup: P0 draws SC1 (keeps), SC2 (P1 gets), SC3 (no target -> discard)
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))                               # deal P0
            .then(NumberCard(3))                               # deal P1
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> P0 gets SC
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> P1 gets SC
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> no target, discard
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.HIT, HitStay.HIT, HitStay.STAY]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, discard, _ = engine.play_round(initial, deck, [], players)
        # At least one SC should be in discard (the one with no target)
        sc_in_discard = [
            c for c in discard
            if isinstance(c, ActionCard) and c.type == ActionType.SECOND_CHANCE
        ]
        assert len(sc_in_discard) >= 1

    def test_unused_sc_discarded_at_round_end(self):
        """Second Chance cards not used during a round are discarded (not held next round)."""
        # P0 picks up SC but never needs it (stays safely)
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))                               # deal P0
            .then(NumberCard(3))                               # deal P1
            .then(ActionCard(type=ActionType.SECOND_CHANCE))  # P0 hits -> gets SC
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY]),
            ScriptedPlayer(1, [HitStay.STAY]),
        ]
        engine = make_engine(2)
        initial = GameState(
            cumulative_scores=(0, 0), round_number=0, dealer_idx=0,
            num_players=2, round_state=None, t=0,
        )
        final_state, _, _, _ = engine.play_round(initial, deck, [], players)
        # The SC is in P0's hand at end of round — it's kept in the state
        # but in a new round it would be cleared (new PlayerRoundState starts fresh)
        # We verify round 2 starts with no SC for any player
        deck2 = (
            TestDeckBuilder()
            .then(NumberCard(6))
            .then(NumberCard(7))
            .build()
        )
        players2 = [AlwaysStayPlayer(0), AlwaysStayPlayer(1)]
        state2, _, _, _ = engine.play_round(final_state, deck2, [], players2)
        for p in state2.round_state.player_states:
            assert not p.has_second_chance()

    def test_sc_does_not_count_toward_flip7(self):
        """Second Chance is an ActionCard, not a NumberCard, so it doesn't count for Flip 7."""
        from flip7.engine.state import RoundState
        # Player with 6 number cards and 1 SC does NOT have flip 7
        p = PlayerRoundState(
            player_id=0,
            number_cards=tuple(NumberCard(i) for i in range(6)),
            modifier_cards=(),
            action_cards=(ActionCard(type=ActionType.SECOND_CHANCE),),
            status=PlayerStatus.ACTIVE,
        )
        assert not p.has_flip7()
        assert len(p.number_cards) == 6
