from .context import WormContext


def new_prog():
    WormContext()


class WormMaster:
    @staticmethod
    def entry(prog):
        def dec(func, **kwargs):
            prog.entry(func, **kwargs)
            return func
        return dec

    @staticmethod
    def export(prog):
        def dec(func, **kwargs):
            prog.export(func, **kwargs)
            return func
        return dec

    @staticmethod
    def block(prog):
        def dec(func, **kwargs):
            prog.block(func, **kwargs)
            return func
        return dec

    def __call__(self, prog):
        def dec(func, **kwargs):
            prog.add(func, **kwargs)
            return func
        return dec


worm = WormMaster()
