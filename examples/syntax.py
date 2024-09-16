"""Example showing roughly how `async def` and `await` map to generators."""

import asyncio
import types


@types.coroutine
def generator_addone(a):
    """Add 1 to a."""

    return (yield from _async_addone(a))


async def async_addone(a):
    """Add 1 to a."""

    return await _async_addone(a)


async def _async_addone(a):
    return a + 1


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    while True:
        try:
            coroutine.send(None)
        except StopIteration as e:
            return e.value


assert sync_await(async_addone(5)) == 6
assert sync_await(generator_addone(6)) == 7


async def main():
    """Demonstrate sync_await(coroutine) == await coroutine."""

    assert await async_addone(7) == 8
    assert await generator_addone(8) == 9


asyncio.run(main())
