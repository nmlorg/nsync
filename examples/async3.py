"""A version of async2.py that shows how feeding data back into `await` works."""

import inspect
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


async def async_read():
    """Read data from a socket."""

    log('sleeptoken = SleepToken(.1):')
    sleeptoken = SleepToken(.1)
    log('sleeptoken =', sleeptoken)

    log('ret = await sleeptoken:')
    ret = await sleeptoken
    log('ret =', ret)

    log('sock = socket.create_connection:')
    sock = socket.create_connection(('httpbin.org', 80))

    log('sock.sendall:')
    sock.sendall(b'GET /get HTTP/1.0\r\n\r\n')

    log('readtoken = ReadToken(sock):')
    readtoken = ReadToken(sock)
    log('readtoken =', readtoken)

    log('ret = await readtoken:')
    ret = await readtoken
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
        value = None
        if isinstance(ret, SleepToken):
            log('time.sleep', ret.delay)
            time.sleep(ret.delay)
        elif isinstance(ret, ReadToken):
            log(ret.sock, 'read')
            value = ret.sock.recv(65536)


def main():  # pylint: disable=missing-function-docstring
    log('ret = sync_await(async_read()):')
    ret = sync_await(async_read())
    log('ret =', ret)


if __name__ == '__main__':
    main()
