"""Load an object named "package.module:attr" — how office adapters plug in."""

from importlib import import_module


def load(path: str):
    module, sep, attr = path.partition(":")
    if not sep or not module or not attr:
        raise ValueError(f"expected 'module:attr', got {path!r}")
    obj = import_module(module)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj
