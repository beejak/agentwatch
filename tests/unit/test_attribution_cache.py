"""The coordination-signature library is loaded once and cached across attribution calls."""
from watchtower.analyst import attribution


async def test_default_library_is_cached():
    a = await attribution._get_default_library()
    b = await attribution._get_default_library()
    assert a is b           # same instance reused (not reloaded per call)
    assert a._loaded
