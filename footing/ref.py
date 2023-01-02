import yaml

import footing.util


def load():
    """Load the refs"""
    try:
        with open(footing.util.local_refs_path()) as f:
            return yaml.load(f, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        return {}


def get(uri):
    """Get the current ref for an object"""
    return load().get(uri)


def set(uri, value):
    refs = load()
    refs[uri] = value
    with open(footing.util.local_refs_path(), "w") as local_refs_file:
        yaml.dump(refs, local_refs_file, Dumper=yaml.SafeDumper)
