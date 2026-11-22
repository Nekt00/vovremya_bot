from collections.abc import Awaitable, Callable

CommitDatabase = Callable[[], Awaitable[None]]
