"""A version of async3.py that shows how running multiple coroutines in parallel works."""

import inspect
import select
import time

start = time.time()


def log(*args):  # pylint: disable=missing-function-docstring
    stack = inspect.stack()
    caller = stack[1]
    print(f'{time.time() - start:.03f}{"    " * (len(stack) - 3)}',
          f'[{caller.function}:{caller.lineno}]', *args)


class _BaseToken:

    def __await__(self):
        log(self)
        log('ret = yield self:')
        ret = yield self
        log('ret =', ret)
        return ret


class SleepToken(_BaseToken):
    """Token to tell the event loop to resume a coroutine after a delay."""

    def __init__(self, delay):
        log(self, delay)
        self.delay = delay


class ReadToken(_BaseToken):
    """Token to tell the event loop to resume a coroutine after reading data from a socket."""

    def __init__(self, sock):
        log(self, sock)
        self.sock = sock


class GatherToken(_BaseToken):
    """Token to tell the event loop to resume after a list of 1 or more tokens finishes."""

    def __init__(self, *tokens):
        log(self, tokens)
        self.tokens = tokens


async def coro_token():
    """Coroutine that awaits a token."""

    log('sleeptoken = SleepToken(.1):')
    sleeptoken = SleepToken(.1)
    log('sleeptoken =', sleeptoken)

    log('ret = await sleeptoken:')
    ret = await sleeptoken
    log('ret =', ret)

    log("return 'coro_token final value'")
    return 'coro_token final value'


async def wait_for(token):
    """Coroutine that awaits a token."""

    log('token =', token)

    log('ret = await token:')
    ret = await token
    log('ret =', ret)

    log("return 'wait_for final value'")
    return 'wait_for final value'


async def coro_coro_token():
    """Coroutine that awaits a coroutine awaiting a token."""

    log('sleeptoken = SleepToken(.2):')
    sleeptoken = SleepToken(.2)
    log('sleeptoken =', sleeptoken)

    log('wait_for_coro = wait_for(sleeptoken):')
    wait_for_coro = wait_for(sleeptoken)
    log('wait_for_coro =', wait_for_coro)

    log('ret = await wait_for_coro:')
    ret = await wait_for_coro
    log('ret =', ret)

    log("return 'coro_coro_token final value'")
    return 'coro_coro_token final value'


async def coro_token_token():
    """Coroutine that awaits a token that contains a token."""

    log('sleeptoken = SleepToken(.3):')
    sleeptoken = SleepToken(.3)
    log('sleeptoken =', sleeptoken)

    log('gathertoken = GatherToken(sleeptoken):')
    gathertoken = GatherToken(sleeptoken)
    log('gathertoken =', gathertoken)

    log('ret = await gathertoken:')
    ret = await gathertoken
    log('ret =', ret)

    log("return 'coro_token_token final value'")
    return 'coro_token_token final value'


async def coro_token_coro_token():
    """Coroutine that awaits a token that contains a coroutine awaiting a token."""

    log('sleeptoken = SleepToken(.4):')
    sleeptoken = SleepToken(.4)
    log('sleeptoken =', sleeptoken)

    log('wait_for_coro = wait_for(sleeptoken):')
    wait_for_coro = wait_for(sleeptoken)
    log('wait_for_coro =', wait_for_coro)

    log('gathertoken = GatherToken(wait_for_coro):')
    gathertoken = GatherToken(wait_for_coro)
    log('gathertoken =', gathertoken)

    log('ret = await gathertoken:')
    ret = await gathertoken
    log('ret =', ret)

    log("return 'coro_token_coro_token final value'")
    return 'coro_token_coro_token final value'


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    log('coroutine =', coroutine)
    value = None
    while True:
        log('ret = coroutine.send', value)

        try:
            ret = coroutine.send(value)
        except StopIteration as e:
            log('StopIteration:', e)
            return e.value

        log('ret =', ret)
        if isinstance(ret, GatherToken):
            value = process_tokens(ret.tokens)
        else:
            value = process_tokens([ret])[0]


def process_tokens(tokens):
    """Read from all ReadTokens and sleep until the longest SleepToken."""

    log('tokens =', tokens)
    responses = [None] * len(tokens)
    delay = 0
    for token in tokens:
        if isinstance(token, SleepToken):
            if token.delay > delay:
                delay = token.delay
    stoptime = delay and time.time() + delay

    while True:
        rlist = []
        for i, token in enumerate(tokens):
            if isinstance(token, ReadToken) and responses[i] is None:
                rlist.append(token.sock)
        log('rlist =', rlist)

        if not rlist:
            break

        rlist, _, _ = select.select(rlist, [], [])
        log('select =', rlist)
        for sock in rlist:
            for i, token in enumerate(tokens):
                if isinstance(token, ReadToken) and token.sock is sock:
                    responses[i] = sock.recv(65536)
                    break

    if (remaining := stoptime - time.time()) > 0:
        log('remaining =', remaining)
        time.sleep(remaining)

    return responses


def main():  # pylint: disable=missing-function-docstring
    log('Coroutine waiting for a token:')
    ret = sync_await(coro_token())
    log('ret =', repr(ret))

    log('Coroutine waiting for a coroutine waiting for a token:')
    ret = sync_await(coro_coro_token())
    log('ret =', repr(ret))

    log('Coroutine waiting for a token containing a token:')
    ret = sync_await(coro_token_token())
    log('ret =', repr(ret))

    log('Coroutine waiting for a token containing a coroutine waiting for a token:')
    ret = sync_await(coro_token_coro_token())
    log('ret =', repr(ret))


if __name__ == '__main__':
    main()
