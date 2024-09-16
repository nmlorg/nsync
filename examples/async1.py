"""Example of running a coroutine manually."""

import time

start = time.time()


def log(*args):  # pylint: disable=missing-function-docstring
    print(f'{time.time() - start:.03f}', *args)


async def async_addone(a):
    """Add 1 to a."""

    log('async_addone', a)
    return a + 1


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    log('sync_await', coroutine)
    while True:
        log('sync_await coroutine.send')

        try:
            ret = coroutine.send(None)
        except StopIteration as e:
            log('sync_await StopIteration', e)
            return e.value

        log('sync_await coroutine.send:', ret)


def main():  # pylint: disable=missing-function-docstring
    ret = sync_await(async_addone(5))
    log('sync_await:', ret)


if __name__ == '__main__':
    main()
