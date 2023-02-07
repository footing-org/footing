# TODO: consider renaming this the settings module

import contextlib
import copy
import dataclasses


_ctx = None


@dataclasses.dataclass
class Ctx:
    """Global context"""

    cache: bool = True
    debug: bool = False


def get():
    global _ctx

    if not _ctx:
        _ctx = Ctx()

    return _ctx


@contextlib.contextmanager
def set(**kwargs):
    global _ctx

    # TODO consider deepcopy when we have mutable objects
    ctx = get()
    prev = copy.copy(ctx)

    try:
        for key, val in kwargs.items():
            setattr(ctx, key, val)

        yield ctx
    finally:
        _ctx = prev
