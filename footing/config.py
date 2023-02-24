import functools
import tomllib


@functools.cache
def get():
    """Get the configuration"""
    with open("footing.toml", "rb") as f:
        return tomllib.load(f)


def find(uri):
    config = get()

    try:
        for part in uri.split("."):
            config = config[part]

        return config
    except KeyError as exc:
        raise KeyError(f"Unable to find '{uri}' in config") from exc
