from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID


class EventAction(StrEnum):
    VIEW = "v"
    TAKE = "t"
    SNOOZE = "z"
    SKIP = "s"
    UNDO = "u"


@dataclass(frozen=True, slots=True)
class EventCallback:
    event_id: UUID
    action: EventAction

    PREFIX = "ie"

    def encode(self) -> str:
        return f"{self.PREFIX}:{self.action.value}:{self.event_id}"

    @classmethod
    def decode(cls, value: str) -> EventCallback:
        parts = value.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            raise ValueError("Invalid intake event callback")
        try:
            action = EventAction(parts[1])
            event_id = UUID(parts[2])
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid intake event callback") from error
        canonical = cls(event_id=event_id, action=action)
        if canonical.encode() != value:
            raise ValueError("Invalid intake event callback")
        return canonical


@dataclass(frozen=True, slots=True)
class SnoozeCallback:
    event_id: UUID
    minutes: int

    PREFIX = "is"
    ALLOWED_MINUTES = frozenset({15, 30, 60})

    def encode(self) -> str:
        if self.minutes not in self.ALLOWED_MINUTES:
            raise ValueError("Invalid snooze duration")
        return f"{self.PREFIX}:{self.minutes}:{self.event_id}"

    @classmethod
    def decode(cls, value: str) -> SnoozeCallback:
        parts = value.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            raise ValueError("Invalid snooze callback")
        try:
            callback = cls(event_id=UUID(parts[2]), minutes=int(parts[1]))
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid snooze callback") from error
        if callback.minutes not in cls.ALLOWED_MINUTES or callback.encode() != value:
            raise ValueError("Invalid snooze callback")
        return callback


@dataclass(frozen=True, slots=True)
class SetTakeAllCallback:
    set_id: UUID
    local_date: date

    PREFIX = "sa"

    def encode(self) -> str:
        return f"{self.PREFIX}:{self.local_date:%Y%m%d}:{self.set_id}"

    @classmethod
    def decode(cls, value: str) -> SetTakeAllCallback:
        parts = value.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            raise ValueError("Invalid set callback")
        try:
            callback = cls(
                UUID(parts[2]), date.fromisoformat(f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:]}")
            )
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid set callback") from error
        if callback.encode() != value:
            raise ValueError("Invalid set callback")
        return callback


class RegimenAction(StrEnum):
    VIEW = "v"
    EDIT = "e"
    PAUSE = "p"
    RESUME = "r"
    COMPLETE = "c"
    CONFIRM_COMPLETE = "cc"
    DELETE = "d"
    CONFIRM_DELETE = "dd"


@dataclass(frozen=True, slots=True)
class RegimenCallback:
    regimen_id: UUID
    action: RegimenAction

    PREFIX = "rg"

    def encode(self) -> str:
        return f"{self.PREFIX}:{self.action.value}:{self.regimen_id}"

    @classmethod
    def decode(cls, value: str) -> RegimenCallback:
        parts = value.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            raise ValueError("Invalid regimen callback")
        try:
            callback = cls(regimen_id=UUID(parts[2]), action=RegimenAction(parts[1]))
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid regimen callback") from error
        if callback.encode() != value:
            raise ValueError("Invalid regimen callback")
        return callback
