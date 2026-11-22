import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from medication_reminder.telegram.wizard import (
    AddRegimen,
    cancel_wizard,
    restart_wizard,
)


def make_context() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=2, user_id=3),
    )


@pytest.mark.asyncio
async def test_cancel_clears_state_and_data() -> None:
    context = make_context()
    await context.set_state(AddRegimen.times)
    await context.set_data({"medication_name": "D3"})

    assert await cancel_wizard(context) is True
    assert await context.get_state() is None
    assert await context.get_data() == {}


@pytest.mark.asyncio
async def test_restart_clears_data_and_returns_to_first_step() -> None:
    context = make_context()
    await context.set_state(AddRegimen.summary)
    await context.set_data({"medication_name": "D3"})

    await restart_wizard(context)

    assert await context.get_state() == AddRegimen.name.state
    assert await context.get_data() == {}
