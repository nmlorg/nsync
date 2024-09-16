"""A version of async2.py that shows how feeding data back into `await` works."""

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


async def async_read():
    """Read data from a socket."""

    log('async_read')
    log('async_read await SleepToken(1.1)')
    ret = await SleepToken(1.1)
    log('async_read await SleepToken(1.1):', ret)
    sock = socket.create_connection(('httpbin.org', 80))
    sock.sendall(b'GET /get HTTP/1.0\r\n\r\n')
    log('async_read await ReadToken')
    ret = await ReadToken(sock)
    log('async_read await ReadToken:', ret)
    return ret


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
        value = None
        if isinstance(ret, SleepToken):
            log('sync_await time.sleep', ret.delay)
            time.sleep(ret.delay)
        elif isinstance(ret, ReadToken):
            log('sync_await', ret.sock, 'read')
            value = ret.sock.recv(65536)


def main():  # pylint: disable=missing-function-docstring
    ret = sync_await(async_read())
    log('sync_await:', ret)


if __name__ == '__main__':
    main()
