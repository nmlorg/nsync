"""Modify classes/functions to convert coroutines into self-awaiting functions."""

import functools
import inspect

import anyio
import sniffio


def fix_class(cls):
    """Convert cls' coroutine methods into self-awaiting function methods."""

    for name, member in cls.__dict__.items():
        if inspect.iscoroutinefunction(member):
            setattr(cls, name, fix_coroutinefunction(member))
    return cls


def fix_coroutinefunction(func):
    """Convert coroutine func into a self-awaiting function."""

    @functools.wraps(func)
    def unasync(*args, **kwargs):
        call = lambda: func(*args, **kwargs)
        try:
            sniffio.current_async_library()
            return call()
        except sniffio.AsyncLibraryNotFoundError:
            return anyio.run(call)

    return unasync


def fix(obj):
    """Modify a class or function to convert coroutines into self-awaiting functions."""

    if inspect.isclass(obj):
        return fix_class(obj)

    if inspect.iscoroutinefunction(obj):
        return fix_coroutinefunction(obj)

    return obj
