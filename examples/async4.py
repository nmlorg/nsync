"""A version of async3.py that shows how running multiple coroutines in parallel works."""

import select
import socket
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


class ReadToken:
    """Token to tell the event loop to resume a coroutine after reading data from a socket."""

    def __init__(self, sock):
        log('ReadToken.__init__', self, sock)
        self.sock = sock

    def __await__(self):
        log('ReadToken.__await__', self)
        log('ReadToken.__await__ yield self')
        ret = yield self
        log('ReadToken.__await__ yield self:', ret)
        return ret


class GatherToken:
    """Token to tell the event loop to resume after a list of 1 or more tokens finishes."""

    def __init__(self, *tokens):
        log('GatherToken.__init__', self, tokens)
        self.tokens = tokens

    def __await__(self):
        log('GatherToken.__await__', self)
        log('GatherToken.__await__ yield self')
        ret = yield self
        log('GatherToken.__await__ yield self:', ret)
        return ret


async def async_read():
    """Read data from a socket."""

    log('async_read')

    log('async_read await SleepToken(1.1)')
    ret = await SleepToken(1.1)
    log('async_read await SleepToken(1.1):', ret)

    sleep15 = SleepToken(1.5)

    log('async_read socket.create_connection')
    sock1 = socket.create_connection(('httpbin.org', 80))
    log('async_read sock.sendall')
    sock1.sendall(b'GET /get HTTP/1.0\r\n\r\n')
    read1 = ReadToken(sock1)

    log('async_read socket.create_connection')
    sock2 = socket.create_connection(('httpbin.org', 80))
    log('async_read sock.sendall')
    sock2.sendall(b'GET /get HTTP/1.0\r\n\r\n')
    read2 = ReadToken(sock2)

    log('async_read await GatherToken')
    read1ret, _, read2ret = await GatherToken(read1, sleep15, read2)
    log('async_read await GatherToken:', read1ret, read2ret)
    return read1ret, read2ret


def sync_await(coroutine):
    """Run the coroutine manually, returning its value; equivalent to `await coroutine`."""

    log('sync_await', coroutine)
    value = None
    while True:
        log('sync_await coroutine.send')

        try:
            ret = coroutine.send(value)
        except StopIteration as e:
            log('sync_await StopIteration', e)
            return e.value

        log('sync_await coroutine.send:', ret)
        if isinstance(ret, GatherToken):
            value = process_tokens(ret.tokens)
        else:
            value = process_tokens([ret])[0]


def process_tokens(tokens):
    """Read from all ReadTokens and sleep until the longest SleepToken."""

    log('process_tokens', tokens)
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
        log('process_tokens rlist =', rlist)

        if not rlist:
            break

        rlist, _, _ = select.select(rlist, [], [])
        log('process_tokens select =', rlist)
        for sock in rlist:
            for i, token in enumerate(tokens):
                if isinstance(token, ReadToken) and token.sock is sock:
                    responses[i] = sock.recv(65536)
                    break

    if (remaining := stoptime - time.time()) > 0:
        log('process_tokens remaining =', remaining)
        time.sleep(remaining)

    return responses


def main():  # pylint: disable=missing-function-docstring
    ret = sync_await(async_read())
    log('sync_await:', ret)


if __name__ == '__main__':
    main()
