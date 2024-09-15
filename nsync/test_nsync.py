"""Tests for nsync."""

import pytest

import nsync

pytestmark = pytest.mark.anyio


@nsync.fix
class MyClass:
    """Test class."""

    def __init__(self, value):
        self.value = value

    async def get_value_async(self):
        """Return self.value."""

        return self.value

    def get_value_sync(self):
        """Return self.value."""

        return self.value


async def test_async():
    """Verify async."""

    obj = MyClass(1)

    assert await obj.get_value_async() == 1
    assert obj.get_value_sync() == 1


def test_sync():
    """Verify sync."""

    obj = MyClass(1)

    assert obj.get_value_async() == 1
    assert obj.get_value_sync() == 1
