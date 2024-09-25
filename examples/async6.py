"""A version of async5.py that restores async4.py's socket I/O."""

import inspect
import select
import socket
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


async def async_read():
    """Read data from a socket."""

    log('sleep1 = SleepToken(.1):')
    sleep1 = SleepToken(.1)
    log('sleep1 =', sleep1)

    log('sleep2 = SleepToken(1.5):')
    sleep2 = SleepToken(1.5)
    log('sleep2 =', sleep2)

    log('sleep3 = SleepToken(1.5):')
    sleep3 = SleepToken(1.5)
    log('sleep3 =', sleep3)

    log('sleep4 = SleepToken(2.5):')
    sleep4 = SleepToken(2.5)
    log('sleep4 =', sleep4)

    log('sock1 = socket.create_connection:')
    sock1 = socket.create_connection(('httpbin.org', 80))

    log('sock1.sendall:')
    sock1.sendall(b'GET /status/200 HTTP/1.0\r\n\r\n')

    log('read1 = ReadToken(sock1):')
    read1 = ReadToken(sock1)
    log('read1 =', read1)

    log('sock2 = socket.create_connection:')
    sock2 = socket.create_connection(('httpbin.org', 80))

    log('sock2.sendall:')
    sock2.sendall(b'GET /status/200 HTTP/1.0\r\n\r\n')

    log('read2 = ReadToken(sock2):')
    read2 = ReadToken(sock2)
    log('read2 =', read2)

    log('gathertoken = GatherToken(sleep1, sleep2, sleep3, sleep4, read1, sleep2):')
    gathertoken = GatherToken(sleep1, sleep2, sleep3, sleep4, read1, read2)
    log('gathertoken =', gathertoken)

    log('ret = await gathertoken')
    ret = await gathertoken
    log('ret =', ret)

    log("return 'async_read done!'")
    return 'async_read done!'


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
        assert not self.finalized
        return self._waiting_for.get_waiting_for()


class ReadWrapper(_BaseWrapper):
    """An attempt to await a ReadToken (read data from a network socket)."""

    def __init__(self, parent, sock):
        log('self =', self, 'parent =', parent, 'sock =', sock)
        super().__init__(parent)
        self.sock = sock

    def get_waiting_for(self):
        log('self =', self)
        assert not self.finalized
        return _WaitingFor(readers=[self])


class SleepWrapper(_BaseWrapper):
    """An attempt to await a SleepToken (pause execution until an amount of time has passed)."""

    def __init__(self, parent, delay):
        log('self =', self, 'parent =', parent, 'delay =', delay)
        super().__init__(parent)
        self.deadline = time.time() + delay

    def get_waiting_for(self):
        log('self =', self)
        assert not self.finalized
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
        assert not self.finalized
        readers = []
        sleeper = None
        for awaitable in self._awaitables:
            if awaitable.finalized:
                continue
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
        process_awaitables(coro.get_waiting_for())

    return coro.value


def process_awaitables(waiting_for):
    """Wait (up to the shortest SleepToken's deadline) for data from a ReadToken's socket."""

    log('readers =', waiting_for.readers, 'sleeper =', waiting_for.sleeper)

    if waiting_for.sleeper:
        now = time.time()
        if (deadline := waiting_for.sleeper.deadline) <= now:
            waiting_for.sleeper.finalize(f'deadline ({deadline}) <= now ({now})')
            return
        timeout = waiting_for.sleeper.deadline - now
    else:
        timeout = None

    rlist = [reader.sock for reader in waiting_for.readers]

    log('rlist = select.select rlist =', rlist, 'timeout =', timeout)
    rlist, _, _ = select.select(rlist, [], [], timeout)
    log('rlist =', rlist)

    if not rlist:  # select.select timed out.
        waiting_for.sleeper.finalize(f'select.select timed out after {timeout} s')
    else:
        for reader in waiting_for.readers:
            if reader.sock in rlist:
                data = reader.sock.recv(65536)
                reader.finalize(data)


def main():  # pylint: disable=missing-function-docstring
    log('ret = sync_await(async_read()):')
    ret = sync_await(async_read())
    log('ret =', ret)


if __name__ == '__main__':
    main()
