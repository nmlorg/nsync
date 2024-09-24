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
    """Token to tell the event loop to resume after a list of 1 or more awaitables finishes."""

    def __init__(self, *awaitables):
        log(self, awaitables)
        self.awaitables = awaitables


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


class _BaseWrapper:
    finalized = False
    value = None

    def __init__(self, parent):
        self._parent = parent

    def finalize(self, value):
        """Mark this awaitable as finalized and notify anything waiting for it."""

        log('self =', self, 'value =', value)
        self.value = value
        self.finalized = True
        if self._parent:
            self._parent.step()

    def step(self):
        """Check whether this awaitable is still waiting, and perform as much work as possible."""

        log('self =', self)

    def get_waiting_for(self):
        """Return a _WaitingFor of everything this is waiting for (directly or indirectly)."""

        raise NotImplementedError()

    @staticmethod
    def wrap(parent, awaitable):
        """Wrap the given awaitable in the appropriate _BaseWrapper subclass."""

        log('parent =', parent, 'awaitable =', awaitable)
        if inspect.iscoroutine(awaitable):
            return CoroutineWrapper(parent, awaitable)
        if isinstance(awaitable, ReadToken):
            return ReadWrapper(parent, awaitable.sock)
        if isinstance(awaitable, SleepToken):
            return SleepWrapper(parent, awaitable.delay)
        if isinstance(awaitable, GatherToken):
            return GatherWrapper(parent, awaitable.awaitables)
        raise NotImplementedError()


class _WaitingFor:

    def __init__(self, *, readers=(), sleeper=None):
        log('self =', self, 'readers =', readers, 'sleeper =', sleeper)
        self.readers = readers
        self.sleeper = sleeper


class CoroutineWrapper(_BaseWrapper):
    """An instance of a call to an async def function."""

    def __init__(self, parent, coro):
        log('self =', self, 'parent =', parent, 'coro =', coro)
        super().__init__(parent)
        self._coro = coro
        self._send(None)

    _waiting_for = None

    def step(self):
        log('self =', self)
        if self._waiting_for.finalized:
            value = self._waiting_for.value
            self._waiting_for = None
            self._send(value)

    def _send(self, value):
        log('self =', self, 'value =', value)
        try:
            waiting_for = self._coro.send(value)
        except StopIteration as e:
            self.finalize(e.value)
        else:
            self._waiting_for = _BaseWrapper.wrap(self, waiting_for)

    def get_waiting_for(self):
        log('self =', self)
        return self._waiting_for.get_waiting_for()


class ReadWrapper(_BaseWrapper):
    """An attempt to await a ReadToken (read data from a network socket)."""

    def __init__(self, parent, sock):
        log('self =', self, 'parent =', parent, 'sock =', sock)
        super().__init__(parent)
        self._sock = sock

    def get_waiting_for(self):
        log('self =', self)
        return _WaitingFor(readers=[self])


class SleepWrapper(_BaseWrapper):
    """An attempt to await a SleepToken (pause execution until an amount of time has passed)."""

    def __init__(self, parent, delay):
        log('self =', self, 'parent =', parent, 'delay =', delay)
        super().__init__(parent)
        self.deadline = time.time() + delay

    def get_waiting_for(self):
        log('self =', self)
        return _WaitingFor(sleeper=self)


class GatherWrapper(_BaseWrapper):
    """An attempt to await a GatherToken (1 or more other awaitables)."""

    def __init__(self, parent, awaitables):
        log('self =', self, 'parent =', parent, 'awaitables =', awaitables)
        super().__init__(parent)
        self._awaitables = [_BaseWrapper.wrap(self, awaitable) for awaitable in awaitables]

    def step(self):
        log('self =', self)
        values = []
        for awaitable in self._awaitables:
            if not awaitable.finalized:
                return
            values.append(awaitable.value)
        self._awaitables = None
        self.finalize(values)

    def get_waiting_for(self):
        log('self =', self)
        readers = []
        sleeper = None
        for awaitable in self._awaitables:
            waiting_for = awaitable.get_waiting_for()
            readers.extend(waiting_for.readers)
            if sleeper is None or (waiting_for.sleeper is not None and
                                   sleeper.deadline > waiting_for.sleeper.deadline):
                sleeper = waiting_for.sleeper
        return _WaitingFor(readers=readers, sleeper=sleeper)


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    log('coroutine =', coroutine)
    coro = _BaseWrapper.wrap(None, coroutine)

    while not coro.finalized:
        waiting_for = coro.get_waiting_for()
        log('readers =', waiting_for.readers, 'sleeper =', waiting_for.sleeper)
        waiting_for.sleeper.finalize(time.sleep(waiting_for.sleeper.deadline - time.time()))
        #if isinstance(ret, GatherToken):
        #    value = process_tokens(ret.awaitables)
        #else:
        #    value = process_tokens([ret])[0]
    return coro.value


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
