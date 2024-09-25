"""A version of async1.py that shows how `await` works."""

import inspect
import time

start = time.time()


def log(*args):  # pylint: disable=missing-function-docstring
    stack = inspect.stack()
    caller = stack[1]
    print(f'{time.time() - start:.03f}{"    " * (len(stack) - 3)}',
          f'[{caller.function}:{caller.lineno}]', *args)


class SleepToken:
    """Token to tell the event loop to resume a coroutine after a delay."""

    def __init__(self, delay):
        log('self =', self, 'delay =', delay)
        self.delay = delay

    def __await__(self):
        log('self =', self)
        log('ret = yield self:')
        ret = yield self
        log('ret =', ret)


async def async_addone(a):
    """Add 1 to a."""

    log('a =', a)

    log('sleeptoken = SleepToken(.1):')
    sleeptoken = SleepToken(.1)
    log('sleeptoken =', sleeptoken)

    log('ret = await sleeptoken:')
    ret = await sleeptoken
    log('ret =', ret)

    log('return a + 1')
    return a + 1


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    log('coroutine =', coroutine)
    while True:
        log('ret = coroutine.send', None)

        try:
            ret = coroutine.send(None)
        except StopIteration as e:
            log('StopIteration:', e)
            return e.value

        log('ret =', ret)
        if isinstance(ret, SleepToken):
            log('time.sleep', ret.delay)
            time.sleep(ret.delay)


def main():  # pylint: disable=missing-function-docstring
    log('ret = sync_await(async_addone(5)):')
    ret = sync_await(async_addone(5))
    log('ret =', ret)


if __name__ == '__main__':
    main()
