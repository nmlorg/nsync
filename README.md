Python has [syntactic support for asynchronous programming](https://peps.python.org/pep-0492/), but nothing is built into the language itself to actually execute asynchronous functions. This is left up to separate code called an ["application framework"](https://discuss.python.org/t/calling-coroutines-from-sync-code-2/24093/15).

Confusingly, the Python standard library includes a framework (called [asyncio](https://docs.python.org/3/library/asyncio.html)), but there are other ones (like [trio](https://pypi.org/project/trio/)) you can install separately, as well as metaframeworks (like [anyio](https://pypi.org/project/anyio/)) to make code built for one framework work with code built for another framework (like a library that uses `trio.sleep` being called inside a program that uses `asyncio.run`) — i.e., this doesn't work:
```py
async def f():
    await trio.sleep(1)

asyncio.run(f())
```
nor does:
```py
async def g():
    await asyncio.sleep(1)

trio.run(f)
```
but:
```py
async def h():
    await anyio.sleep(1)
```
works with `anyio.run(h)`, `asyncio.run(h())`, and `trio.run(h)`.

(`anyio.run(g)` — calling asyncio library code while in an anyio event loop — also works, simply because anyio defaults to using asyncio's event loop under the hood.)

<hr>

Even with anyio, it's a mess.

anyio uses a package called [sniffio](https://pypi.org/project/sniffio/) to figure out what framework is being used (whether the current program is running under `asyncio.run`, `trio.run`, etc.) and generally just uses that framework's routines (`anyio.sleep` calls `asyncio.sleep` when sniffio detects it's running under `asyncio.run`, calls `trio.sleep` under `trio.run`, etc.). However, if there are behavior differences (as you'd expect — or else what is the point of having a separate framework in the first place?), anyio has to do extra work (44 thousand lines worth) to make every framework behave like every other one.

And some frameworks, like [curio](https://pypi.org/project/curio/), go so far as to intentionally break anyio, forcing libraries to either **not** support being used by programs running in curio, **only** support being used by programs running in curio, or duplicate code.

<hr>

On top of all of the above, Python still separately supports synchronous programming — no framework, no explicit event loop, just executing `__main__`'s global statements from start to finish, as fast as possible.

Asynchronous code can call synchronous code, but if the synchronous code blocks the entire application framework blocks. (Asynchronous code runs in a single process/thread.) The reverse, calling asynchronous code from synchronous code, is [very cumbersome](https://github.com/nmlorg/nsync/blob/main/examples/async1.py) (and generally intended to be impossible). 

A library that does asynchronous work (such as a user interface or a network protocol driver) therefore needs to either **only** support synchronous callers (by giving synchronous functions), **only** support asynchronous callers (by giving asynchronous functions), or duplicate code (using functions in separate `package.async` and `package.sync` modules, or methods on separate `package.AsyncClient` and `package.SyncClient` objects, etc.).

Right now, this [nsync](https://pypi.org/project/nsync/) package just provides one function:&nbsp; [`nsync.fix`](https://github.com/nmlorg/nsync/blob/main/nsync/__init__.py), which takes an asynchronous function or class with asynchronous methods and makes the asynchronous code automatically run itself inside an event loop when called by synchronous code (or at least when called outside of a detectable application framework):

```py
import anyio
import nsync


@nsync.fix
class MyClass:
    async def get_value_async(self):
        return 1

    def get_value_sync(self):
        return 1


myobj = MyClass()

async def main():
    assert myobj.get_value_sync() == 1  # Sync from async.
    assert await myobj.get_value_async() == 1  # Async from async.

anyio.run(main)

assert myobj.get_value_sync() == 1  # Sync from sync.
assert myobj.get_value_async() == 1  # Async from sync — no await.
```

<hr>

See also:

* https://pypi.org/project/deasync/
* https://pypi.org/project/syncasync/
* https://pypi.org/project/unasync/
