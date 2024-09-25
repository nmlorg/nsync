"""A version of async3.py that shows how running multiple coroutines in parallel works."""

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
    """Token to tell the event loop to resume after a list of 1 or more tokens finishes."""

    def __init__(self, *tokens):
        log(self, tokens)
        self.tokens = tokens


async def async_read():
    """Read data from a socket."""

    log('sleeptoken = SleepToken(.1):')
    sleeptoken = SleepToken(.1)
    log('sleeptoken =', sleeptoken)

    log('ret = await sleeptoken:')
    ret = await sleeptoken
    log('ret =', ret)

    log('sleep15 = SleepToken(1.5):')
    sleep15 = SleepToken(1.5)
    log('sleep15 =', sleep15)

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

    log('gathertoken = GatherToken(read1, sleep15, read2):')
    gathertoken = GatherToken(read1, sleep15, read2)
    log('gathertoken =', gathertoken)

    log('ret = await gathertoken')
    ret = await gathertoken
    log('ret =', ret)

    log("return 'async_read done!'")
    return 'async_read done!'


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
    log('ret = sync_await(async_read()):')
    ret = sync_await(async_read())
    log('ret =', ret)


if __name__ == '__main__':
    main()
