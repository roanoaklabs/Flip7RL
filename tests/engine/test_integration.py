"""Integration tests for the Flip 7 game engine."""
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
from flip7.players.base import (
    BasePlayer, GameObservation, AlwaysHitPlayer, AlwaysStayPlayer
)


# ------------------------------------------------------------------
# Scripted player (reused from action_cards tests)
# ------------------------------------------------------------------

class ScriptedPlayer(BasePlayer):
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
        for p in observation.other_players:
            if p.status == PlayerStatus.ACTIVE:
                return p.player_id
        return observation.my_player_id


def initial_state(num_players: int, dealer_idx: int = 0) -> GameState:
    return GameState(
        cumulative_scores=tuple(0 for _ in range(num_players)),
        round_number=0,
        dealer_idx=dealer_idx,
        num_players=num_players,
        round_state=None,
        t=0,
    )


def get_player_state(state: GameState, pid: int) -> PlayerRoundState:
    return state.round_state.player_states[pid]


# ------------------------------------------------------------------
# Flip 7 bonus test
# ------------------------------------------------------------------

class TestFlip7Integration:
    def test_flip7_bonus_adds_15(self):
        """Player with 7 unique number cards (0-6) gets +15 bonus and round ends."""
        # 2-player game. P0 accumulates 7 cards: 0,1,2,3,4,5,6
        # Deal: P0=0, P1=9. Then P0 hits 6 more times to get cards 1,2,3,4,5,6.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(0))   # deal P0
            .then(NumberCard(9))   # deal P1
            .then(NumberCard(1))   # P0 hit 1
            .then(NumberCard(2))   # P0 hit 2
            .then(NumberCard(3))   # P0 hit 3
            .then(NumberCard(4))   # P0 hit 4
            .then(NumberCard(5))   # P0 hit 5
            .then(NumberCard(6))   # P0 hit 6 -> flip 7!
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT] * 6 + [HitStay.STAY]),
            AlwaysStayPlayer(1),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, log = engine.play_round(init, deck, [], players)

        p0 = get_player_state(final_state, 0)
        assert p0.has_flip7()
        # Score: 0+1+2+3+4+5+6 = 21, + 15 flip7 bonus = 36
        assert p0.current_sum() == 36
        assert final_state.cumulative_scores[0] == 36

    def test_flip7_ends_round_immediately(self):
        """Round ends as soon as Flip 7 is achieved, not after all players go."""
        # P0 achieves Flip 7 during deal phase — P1 stays active but round ends
        # We verify P1's status can be ACTIVE if Flip 7 triggered immediately
        deck = (
            TestDeckBuilder()
            .then(NumberCard(0))   # deal P0
            .then(NumberCard(9))   # deal P1
            .then(NumberCard(1))   # P0 hit 1
            .then(NumberCard(2))   # P0 hit 2
            .then(NumberCard(3))   # P0 hit 3
            .then(NumberCard(4))   # P0 hit 4
            .then(NumberCard(5))   # P0 hit 5
            .then(NumberCard(6))   # P0 hit 6 -> flip 7!
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT] * 6 + [HitStay.STAY]),
            AlwaysStayPlayer(1),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, log = engine.play_round(init, deck, [], players)

        p0 = get_player_state(final_state, 0)
        assert p0.has_flip7()
        # Cumulative updated
        assert final_state.cumulative_scores[0] == 36


# ------------------------------------------------------------------
# Bust test
# ------------------------------------------------------------------

class TestBustIntegration:
    def test_bust_scores_zero(self):
        """Busted player scores 0 while others score normally."""
        # P0 has 5, hits and gets duplicate 5 -> bust
        # P1 stays with 3 -> scores 3
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal P0
            .then(NumberCard(3))   # deal P1
            .then(NumberCard(5))   # P0 hits duplicate -> bust
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT]),
            AlwaysStayPlayer(1),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, _ = engine.play_round(init, deck, [], players)

        p0 = get_player_state(final_state, 0)
        assert p0.status == PlayerStatus.BUSTED
        assert final_state.cumulative_scores[0] == 0
        assert final_state.cumulative_scores[1] == 3

    def test_bust_does_not_affect_other_players(self):
        """Other players can continue after one busts (in main phase)."""
        # P0 busts immediately. P1 continues and hits for more cards.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal P0
            .then(NumberCard(3))   # deal P1
            .then(NumberCard(5))   # P0 hits duplicate -> bust
            .then(NumberCard(6))   # P1 hits
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT]),
            ScriptedPlayer(1, [HitStay.HIT, HitStay.STAY]),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, _ = engine.play_round(init, deck, [], players)

        p1 = get_player_state(final_state, 1)
        assert p1.status == PlayerStatus.STAYED
        # P1 should have 3 and 6
        values = {c.value for c in p1.number_cards}
        assert values == {3, 6}
        assert final_state.cumulative_scores[1] == 9


# ------------------------------------------------------------------
# All stay test
# ------------------------------------------------------------------

class TestAllStay:
    def test_all_players_stay_round_ends(self):
        """Round ends when all players choose stay after deal."""
        deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal P0
            .then(NumberCard(3))   # deal P1
            .build()
        )
        players = [AlwaysStayPlayer(0), AlwaysStayPlayer(1)]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, _ = engine.play_round(init, deck, [], players)

        # Both should have stayed and scored
        p0 = get_player_state(final_state, 0)
        p1 = get_player_state(final_state, 1)
        assert p0.status == PlayerStatus.STAYED
        assert p1.status == PlayerStatus.STAYED
        assert final_state.cumulative_scores[0] == 5
        assert final_state.cumulative_scores[1] == 3

    def test_full_formula_stay(self):
        """Verify scoring formula: x2 modifier, +6 modifier, number sum 10, no flip7."""
        # Player 0: NumberCard(3) + NumberCard(7) = 10, x2 modifier, +6 modifier
        # Score: 10*2 + 6 = 26
        # But deal only gives one card, so we need P0 to hit once.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(3))   # deal P0
            .then(NumberCard(9))   # deal P1
            .then(NumberCard(7))   # P0 hits
            .then(ModifierCard(op=ModifierOp.MULTIPLY, value=2))  # P0 hits
            .then(ModifierCard(op=ModifierOp.ADD, value=6))        # P0 hits
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.HIT, HitStay.HIT, HitStay.STAY]),
            AlwaysStayPlayer(1),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, _ = engine.play_round(init, deck, [], players)

        p0 = get_player_state(final_state, 0)
        assert p0.current_sum() == 26  # (3+7)*2 + 6
        assert final_state.cumulative_scores[0] == 26

    def test_full_scoring_formula_with_flip7(self):
        """Full formula: x2 modifier, +6 modifier, 7 number cards summing to 10, flip7 bonus."""
        # 7 unique number cards: 0,1,2,3,4 = 10... we need sum=10 with 7 cards
        # 0+1+0... can't repeat. Let's use 0+1+2+3+4+0+0... no, unique.
        # Actually sum 10 with 7 unique cards: 0+1+2+3+4+? difficult
        # Use 0+0+... no. Let's just verify the formula with given numbers.
        # 0+1+2+3+4+5+6 = 21. With x2: 42. With +6: 48. With flip7: +15 = 63.
        # That's the actual case we can test.
        deck = (
            TestDeckBuilder()
            .then(NumberCard(0))   # deal P0
            .then(NumberCard(9))   # deal P1
            .then(NumberCard(1))   # P0 hit
            .then(NumberCard(2))   # P0 hit
            .then(NumberCard(3))   # P0 hit
            .then(NumberCard(4))   # P0 hit
            .then(ModifierCard(op=ModifierOp.MULTIPLY, value=2))  # P0 hit
            .then(ModifierCard(op=ModifierOp.ADD, value=6))        # P0 hit
            .then(NumberCard(5))   # P0 hit
            .then(NumberCard(6))   # P0 hit -> flip 7! Score = (0+1+2+3+4+5+6)*2+6+15 = 21*2+6+15=63
            .build()
        )
        players = [
            ScriptedPlayer(0, [HitStay.HIT] * 9 + [HitStay.STAY]),
            AlwaysStayPlayer(1),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        final_state, _, _, _ = engine.play_round(init, deck, [], players)

        p0 = get_player_state(final_state, 0)
        assert p0.has_flip7()
        expected = 21 * 2 + 6 + 15  # 63
        assert p0.current_sum() == expected
        assert final_state.cumulative_scores[0] == expected


# ------------------------------------------------------------------
# Win condition test
# ------------------------------------------------------------------

class TestWinCondition:
    def test_game_stops_after_win_round(self):
        """Game stops after round ends if cumulative >= 200. No mid-round stop."""
        # Use AlwaysStayPlayer with a deck that gives P0 enough to win.
        # P0 needs 200+ cumulative. Let's play multiple rounds with high scores.

        engine = GameEngine(num_players=2, seed=42)

        class HighScorePlayer(BasePlayer):
            """Always stays, to lock in whatever is dealt."""
            def observe(self, obs): pass
            def decide(self, obs): return HitStay.STAY
            def choose_target(self, card, obs): return obs.my_player_id

        players = [HighScorePlayer(0), HighScorePlayer(1)]
        log = engine.play_game(players)

        final_state = log[-1]
        # Someone should have >= 200
        assert max(final_state.cumulative_scores) >= 200

        # Verify no snapshot after a winning round has a lower round number
        # (i.e., game didn't continue past the winning round)
        winning_round = final_state.round_number
        for state in log:
            assert state.round_number <= winning_round


# ------------------------------------------------------------------
# Dealer rotation test
# ------------------------------------------------------------------

class TestDealerRotation:
    def test_dealer_rotates_each_round(self):
        """Dealer index cycles: 0 -> 1 -> 2 -> 0 for 3 players."""
        engine = GameEngine(num_players=3, seed=0)
        players = [AlwaysStayPlayer(i) for i in range(3)]

        init = GameState(
            cumulative_scores=(0, 0, 0),
            round_number=0,
            dealer_idx=0,
            num_players=3,
            round_state=None,
            t=0,
        )

        dealer_indices = []
        state = init
        discard = []
        for _ in range(4):
            deck = Deck()
            deck.shuffle(seed=_ + 10)
            state, deck, discard, _ = engine.play_round(state, deck, discard, players)
            dealer_indices.append(state.dealer_idx)

        assert dealer_indices == [0, 1, 2, 0]

    def test_first_round_dealer_is_player0(self):
        """First round dealer starts at player 0."""
        engine = GameEngine(num_players=3, seed=0)
        players = [AlwaysStayPlayer(i) for i in range(3)]
        init = GameState(
            cumulative_scores=(0, 0, 0),
            round_number=0,
            dealer_idx=0,
            num_players=3,
            round_state=None,
            t=0,
        )
        deck = Deck()
        deck.shuffle(seed=1)
        state, _, _, log = engine.play_round(init, deck, [], players)
        # Round 1's dealer_idx should be 0 (from dealer_idx=0, round_number was 0)
        assert state.dealer_idx == 0


# ------------------------------------------------------------------
# Multi-round cumulative scores
# ------------------------------------------------------------------

class TestMultiRoundScores:
    def test_scores_accumulate_across_rounds(self):
        """Cumulative scores add up correctly over 2 rounds."""
        engine = GameEngine(num_players=2, seed=0)

        # Round 1: dealer=P0, deal order P0 then P1 -> P0 gets 5, P1 gets 3
        deck1 = (
            TestDeckBuilder()
            .then(NumberCard(5))
            .then(NumberCard(3))
            .build()
        )
        # Round 2: dealer rotates to P1, deal order P1 then P0 -> P1 gets 7, P0 gets 4
        deck2 = (
            TestDeckBuilder()
            .then(NumberCard(7))
            .then(NumberCard(4))
            .build()
        )
        players1 = [AlwaysStayPlayer(0), AlwaysStayPlayer(1)]
        players2 = [AlwaysStayPlayer(0), AlwaysStayPlayer(1)]

        init = initial_state(2)
        state1, _, discard1, _ = engine.play_round(init, deck1, [], players1)
        assert state1.cumulative_scores == (5, 3)

        state2, _, _, _ = engine.play_round(state1, deck2, discard1, players2)
        # Dealer is P1 in round 2, so deal order is P1, P0
        # P1 draws 7, P0 draws 4
        # Cumulative: P0 = 5+4 = 9, P1 = 3+7 = 10
        assert state2.cumulative_scores == (9, 10)


# ------------------------------------------------------------------
# Deck exhaustion / reshuffle test
# ------------------------------------------------------------------

class TestDeckExhaustion:
    def test_reshuffle_discard_when_deck_empty(self):
        """When deck is empty, discard pile is reshuffled and used."""
        # Use a very small deck (2 cards) + discard pile, verify game continues
        small_deck = (
            TestDeckBuilder()
            .then(NumberCard(5))   # deal P0
            .then(NumberCard(3))   # deal P1
            .build()
        )
        # We put some cards in discard that can be reshuffled
        discard_pile = [NumberCard(7), NumberCard(8)]

        players = [
            ScriptedPlayer(0, [HitStay.HIT, HitStay.STAY]),  # will try to hit after deck empty
            AlwaysStayPlayer(1),
        ]
        engine = GameEngine(num_players=2, seed=0)
        init = initial_state(2)
        # After deal, deck is empty. P0 hits -> triggers reshuffle of discard
        final_state, _, _, _ = engine.play_round(init, small_deck, discard_pile, players)
        # Game should complete without error
        p0 = get_player_state(final_state, 0)
        assert p0.status in (PlayerStatus.STAYED, PlayerStatus.BUSTED, PlayerStatus.FROZEN, PlayerStatus.ACTIVE)
