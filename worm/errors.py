class WormError(Exception):
    def __init__(self, msg, at=None):
        if at:
            _msg = f"At L{at[0]}C{at[1]}-{at[3]}: {msg}"
        else:
            _msg = msg
        super().__init__(_msg)


class WormTypeError(WormError):
    def __init__(self, msg, expect=None, got=None, **kwargs):
        if expect or got:
            _msg = f"{msg} Expected {expect} but got {got}."
        else:
            _msg = msg

        super().__init__(_msg, **kwargs)


class WormSyntaxError(WormError):
    pass


class WormBindingError(WormError):
    pass
