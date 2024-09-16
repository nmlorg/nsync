"""A version of async1.py that shows how `await` works."""

import time

start = time.time()


def log(*args):  # pylint: disable=missing-function-docstring
    print(f'{time.time() - start:.03f}', *args)


class SleepToken:
    """Token to tell the event loop to resume a coroutine after a delay."""

    def __init__(self, delay):
        log('SleepToken.__init__', self, delay)
        self.delay = delay

    def __await__(self):
        log('SleepToken.__await__', self)
        log('SleepToken.__await__ yield self')
        ret = yield self
        log('SleepToken.__await__ yield self:', ret)


async def async_addone(a):
    """Add 1 to a."""

    log('async_addone', a)
    log('async_addone await SleepToken(1.1)')
    ret = await SleepToken(1.1)
    log('async_addone await SleepToken(1.1):', ret)
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
        if isinstance(ret, SleepToken):
            log('sync_await time.sleep', ret.delay)
            time.sleep(ret.delay)


def main():  # pylint: disable=missing-function-docstring
    ret = sync_await(async_addone(5))
    log('sync_await:', ret)


if __name__ == '__main__':
    main()
