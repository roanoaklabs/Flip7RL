from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ModifierOp(Enum):
    ADD = "add"
    MULTIPLY = "multiply"


class ActionType(Enum):
    FREEZE = "freeze"
    FLIP_THREE = "flip_three"
    SECOND_CHANCE = "second_chance"


@dataclass(frozen=True)
class BaseCard:
    pass


@dataclass(frozen=True)
class NumberCard(BaseCard):
    value: int  # 0-12


@dataclass(frozen=True)
class ModifierCard(BaseCard):
    op: ModifierOp
    value: int  # 2,4,6,8,10 for ADD; 2 for MULTIPLY


@dataclass(frozen=True)
class ActionCard(BaseCard):
    type: ActionType
