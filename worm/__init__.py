from .context import WormContext, WormMode


def new_prog():
    return WormContext(mode=WormMode.PROGRAM)


def new_lib():
    return WormContext(mode=WormMode.LIBRARY)
