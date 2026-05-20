"""Shared fixtures and helpers for the test suite."""
import pytest
from flip7.engine.cards import NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType
from flip7.engine.deck import Deck
from flip7.engine.state import PlayerRoundState, PlayerStatus
from flip7.players.base import AlwaysHitPlayer, AlwaysStayPlayer, RandomPlayer


# ------------------------------------------------------------------
# Convenience card constructors
# ------------------------------------------------------------------

def num(v: int) -> NumberCard:
    return NumberCard(value=v)


def add_mod(v: int) -> ModifierCard:
    return ModifierCard(op=ModifierOp.ADD, value=v)


def mul_mod(v: int) -> ModifierCard:
    return ModifierCard(op=ModifierOp.MULTIPLY, value=v)


def freeze() -> ActionCard:
    return ActionCard(type=ActionType.FREEZE)


def flip_three() -> ActionCard:
    return ActionCard(type=ActionType.FLIP_THREE)


def second_chance() -> ActionCard:
    return ActionCard(type=ActionType.SECOND_CHANCE)


def make_player_state(
    player_id: int,
    numbers=(),
    modifiers=(),
    actions=(),
    status=PlayerStatus.ACTIVE,
) -> PlayerRoundState:
    return PlayerRoundState(
        player_id=player_id,
        number_cards=tuple(numbers),
        modifier_cards=tuple(modifiers),
        action_cards=tuple(actions),
        status=status,
    )
