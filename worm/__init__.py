from .context import WormContext


worm = WormContext()

def _worm_decorator_wrapper(decorators, worm_func):
    def dec(func):
        evaled_decs = []
        for dec in decorators:
            evaled = dec()
            if is_worm_method(evaled):
                return worm_func()
            else:
                evaled_decs.append(evaled)
        return reduce(lambda f, v: f(v), evaled_decs, func)
    return dec