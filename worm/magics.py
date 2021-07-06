from functools import reduce as _reduce

from .wast import *
from .wtypes import *


def is_worm_method(thing):
    return getattr(thing, "_worm_method_tag", False)


def worm_decorator_wrapper(decorators, worm_func):
    def dec(func):
        evaled_decs = []
        for dec in decorators:
            evaled = dec()
            if is_worm_method(evaled):
                return worm_func()
            else:
                evaled_decs.append(evaled)
        return _reduce(lambda f, v: f(v), evaled_decs, func)

    return dec
