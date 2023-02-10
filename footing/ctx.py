import contextlib
import copy
import dataclasses
import typing


_ctx = None


@dataclasses.dataclass
class Ctx:
    """Global context"""

    cache: bool = True
    debug: bool = False
    entry_add: str = ""
    env: dict = dataclasses.field(default_factory=dict)

    def update(self, **kwargs):
        for key, val in kwargs.items():
            if isinstance(val, dict):
                val = getattr(self, key, {}) | val

            setattr(self, key, val)


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
        ctx.update(**kwargs)
        yield ctx
    finally:
        _ctx = prev
