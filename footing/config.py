import functools
import tomllib


@functools.cache
def get():
    """Get the configuration"""
    with open("footing.toml", "rb") as f:
        return tomllib.load(f)
