"""Tests for flip7/engine/state.py — immutability and state structure."""
import dataclasses
import pytest
from flip7.engine.state import (
    GameState, RoundState, PlayerRoundState, PlayerStatus, HitStay
)
from flip7.engine.cards import NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType


def make_player_state(pid=0, status=PlayerStatus.ACTIVE):
    return PlayerRoundState(
        player_id=pid,
        number_cards=(),
        modifier_cards=(),
        action_cards=(),
        status=status,
    )


def make_round_state(player_states=None, phase="main"):
    if player_states is None:
        player_states = (make_player_state(0), make_player_state(1))
    return RoundState(
        player_states=player_states,
        deck_remaining=50,
        current_player_idx=0,
        action_queue=(),
        phase=phase,
    )


def make_game_state(round_state=None, t=0, cumulative=(0, 0)):
    return GameState(
        cumulative_scores=tuple(cumulative),
        round_number=1,
        dealer_idx=0,
        num_players=2,
        round_state=round_state,
        t=t,
    )


class TestImmutability:
    def test_game_state_is_frozen(self):
        state = make_game_state()
        with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
            state.round_number = 99

    def test_round_state_is_frozen(self):
        rs = make_round_state()
        with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
            rs.phase = "deal"

    def test_player_round_state_is_frozen(self):
        pstate = make_player_state()
        with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
            pstate.status = PlayerStatus.BUSTED

    def test_producing_new_snapshot_leaves_original_unchanged(self):
        state = make_game_state(t=5, cumulative=(10, 20))
        # Simulate creating a new state with updated t
        new_state = GameState(
            cumulative_scores=state.cumulative_scores,
            round_number=state.round_number,
            dealer_idx=state.dealer_idx,
            num_players=state.num_players,
            round_state=state.round_state,
            t=state.t + 1,
        )
        assert state.t == 5
        assert new_state.t == 6
        assert state.cumulative_scores == (10, 20)

    def test_cumulative_scores_immutable(self):
        state = make_game_state(cumulative=(10, 20))
        with pytest.raises((TypeError, AttributeError)):
            state.cumulative_scores[0] = 999


class TestGameStateStructure:
    def test_t_field_present(self):
        state = make_game_state(t=42)
        assert state.t == 42

    def test_round_number(self):
        state = make_game_state()
        assert state.round_number == 1

    def test_round_state_none_between_rounds(self):
        state = make_game_state(round_state=None)
        assert state.round_state is None

    def test_cumulative_scores_persist_across_rounds(self):
        """Simulate two rounds and check cumulative scores accumulate."""
        state1 = make_game_state(cumulative=(15, 20))
        # After round 2, player 0 scores 10, player 1 scores 5
        round2_scores = (10, 5)
        new_cumulative = tuple(
            state1.cumulative_scores[i] + round2_scores[i]
            for i in range(2)
        )
        state2 = GameState(
            cumulative_scores=new_cumulative,
            round_number=2,
            dealer_idx=1,
            num_players=2,
            round_state=None,
            t=state1.t + 1,
        )
        assert state2.cumulative_scores == (25, 25)

    def test_t_increments_on_each_snapshot(self):
        state = make_game_state(t=0)
        snapshots = []
        t = state.t
        for _ in range(3):
            t += 1
            snapshots.append(GameState(
                cumulative_scores=state.cumulative_scores,
                round_number=state.round_number,
                dealer_idx=state.dealer_idx,
                num_players=state.num_players,
                round_state=state.round_state,
                t=t,
            ))
        assert [s.t for s in snapshots] == [1, 2, 3]


class TestRoundStateReset:
    def test_player_states_reset_between_rounds(self):
        """Round-level fields (player cards, status) start fresh each round."""
        # Simulate end of round 1: player has cards
        pstate_round1 = PlayerRoundState(
            player_id=0,
            number_cards=(NumberCard(value=5), NumberCard(value=3)),
            modifier_cards=(),
            action_cards=(),
            status=PlayerStatus.STAYED,
        )
        # Round 2: player starts fresh
        pstate_round2 = PlayerRoundState(
            player_id=0,
            number_cards=(),
            modifier_cards=(),
            action_cards=(),
            status=PlayerStatus.ACTIVE,
        )
        assert pstate_round2.number_cards == ()
        assert pstate_round2.status == PlayerStatus.ACTIVE
        assert pstate_round1.number_cards != pstate_round2.number_cards


class TestHitStay:
    def test_hit_stay_values(self):
        assert HitStay.HIT.value == "hit"
        assert HitStay.STAY.value == "stay"
