"""A version of async6.py that supports coroutines running in the background."""

import contextvars
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
        log('self =', self)
        log('ret = yield self:')
        ret = yield self
        log('ret =', ret)
        return ret


class SleepToken(_BaseToken):
    """Token to tell the event loop to resume a coroutine after a delay."""

    def __init__(self, delay):
        log('self =', self, 'delay =', delay)
        self.delay = delay


class ReadToken(_BaseToken):
    """Token to tell the event loop to resume a coroutine after reading data from a socket."""

    def __init__(self, sock):
        log('self =', self, 'sock =', sock)
        self.sock = sock


class GatherToken(_BaseToken):
    """Token to tell the event loop to resume after a list of 1 or more awaitables finishes."""

    def __init__(self, *awaitables):
        log('self =', self, 'awaitables =', awaitables)
        self.awaitables = awaitables


async def async_fetch(delay):
    """Read data from a socket after the given delay."""

    log('delay =', delay)
    log('await SleepToken(delay):')
    await SleepToken(delay)
    log('sock = socket.create_connection:')
    sock = socket.create_connection(('httpbin.org', 80))
    log('sock.sendall:')
    sock.sendall(b'GET /status/200 HTTP/1.0\r\n\r\n')
    log('ret = await ReadToken(sock):')
    ret = await ReadToken(sock)
    log('ret =', ret)
    log("return f'async_fetch({delay}) done!'")
    return f'async_fetch({delay}) done!'


async def async_main():
    """Spawn two background tasks off and return."""

    log('task1 = create_task(async_fetch(.1))')
    task1 = create_task(async_fetch(.1))
    log('task1 =', task1)

    log('task2 = create_task(async_fetch(.2))')
    task2 = create_task(async_fetch(.2))
    log('task2 =', task2)

    log("return 'async_main done!'")
    return 'async_main done!'


class _BaseWrapper:
    finalized = False
    value = None

    def __init__(self, parent):
        self._parent = parent

    def finalize(self, value):
        """Mark this awaitable as finalized and notify anything waiting for it."""

        log('self =', self, 'value =', value)
        assert not self.finalized
        self.value = value
        self.finalized = True
        if self._parent:
            self._parent.step()

    def step(self):
        """Check whether this awaitable is still waiting, and perform as much work as possible."""

        log('self =', self)
        assert not self.finalized

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

    def __init__(self, *, readers=(), runnables=(), sleeper=None):
        log('self =', self, 'readers =', readers, 'runnables =', runnables, 'sleeper =', sleeper)
        self.readers = readers
        self.runnables = runnables
        self.sleeper = sleeper


class CoroutineWrapper(_BaseWrapper):
    """An instance of a call to an async def function."""

    def __init__(self, parent, coro):
        log('self =', self, 'parent =', parent, 'coro =', coro)
        super().__init__(parent)
        self._coro = coro

    _waiting_for = None

    def step(self):
        log('self =', self)
        assert not self.finalized
        if self._waiting_for is None:
            self._send(None)
        elif self._waiting_for.finalized:
            value = self._waiting_for.value
            self._waiting_for = None
            self._send(value)

    def _send(self, value):
        log('self =', self, 'value =', value)
        assert not self.finalized
        try:
            waiting_for = self._coro.send(value)
        except StopIteration as e:
            self.finalize(e.value)
        else:
            self._waiting_for = _BaseWrapper.wrap(self, waiting_for)

    def get_waiting_for(self):
        log('self =', self)
        assert not self.finalized
        if self._waiting_for is None:
            return _WaitingFor(runnables=[self])
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
        self._awaitables = []
        for awaitable in awaitables:
            self.add(awaitable)

    def add(self, awaitable):
        """Don't finalize this gather until awaitable finalizes."""

        log('self =', self, 'awaitable =', awaitable)
        assert not self.finalized
        task = _BaseWrapper.wrap(self, awaitable)
        self._awaitables.append(task)
        return task

    def step(self):
        log('self =', self)
        assert not self.finalized
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
        runnables = []
        sleeper = None
        for awaitable in self._awaitables:
            if awaitable.finalized:
                continue
            waiting_for = awaitable.get_waiting_for()
            readers.extend(waiting_for.readers)
            runnables.extend(waiting_for.runnables)
            if sleeper is None or (waiting_for.sleeper is not None and
                                   sleeper.deadline > waiting_for.sleeper.deadline):
                sleeper = waiting_for.sleeper
        return _WaitingFor(readers=readers, runnables=runnables, sleeper=sleeper)


TOP_LEVEL = contextvars.ContextVar('top-level GatherWrapper')


def create_task(awaitable):
    """Run awaitable "in the background" (alongside the coroutine passed to sync_await)."""

    log('awaitable =', awaitable)
    return TOP_LEVEL.get().add(awaitable)


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    return contextvars.copy_context().run(_sync_await, coroutine)


def _sync_await(coroutine):
    log('coroutine =', coroutine)
    top_level = GatherWrapper(None, ())
    log('top_level =', top_level)
    TOP_LEVEL.set(top_level)

    create_task(coroutine)

    while not top_level.finalized:
        process_awaitables(top_level.get_waiting_for())

    return top_level.value[0]


def process_awaitables(waiting_for):
    """Wait (up to the shortest SleepToken's deadline) for data from a ReadToken's socket."""

    log('readers =', waiting_for.readers, 'runnables =', waiting_for.runnables, 'sleeper =',
        waiting_for.sleeper)

    if waiting_for.runnables:
        for runnable in waiting_for.runnables:
            runnable.step()
        return

    if waiting_for.sleeper:
        now = time.time()
        if (deadline := waiting_for.sleeper.deadline) <= now:
            waiting_for.sleeper.finalize(f'deadline ({deadline}) <= now ({now})')
            return
        timeout = waiting_for.sleeper.deadline - now
    else:
        timeout = None

    rlist = {reader.sock for reader in waiting_for.readers}

    log('rlist = select.select rlist =', rlist, 'timeout =', timeout)
    rlist, _, _ = select.select(rlist, [], [], timeout)
    log('rlist =', rlist)

    if not rlist:  # select.select timed out.
        waiting_for.sleeper.finalize(f'select.select timed out after {timeout} s')
    else:
        datas = {}
        for sock in rlist:
            datas[sock] = sock.recv(65536)
        for reader in waiting_for.readers:
            if reader.sock in datas:
                reader.finalize(datas[reader.sock])


def main():  # pylint: disable=missing-function-docstring
    log('ret = sync_await(async_main()):')
    ret = sync_await(async_main())
    log('ret =', ret)


if __name__ == '__main__':
    main()
