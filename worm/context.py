from functools import wraps
from enum import Enum, auto

from .errors import WormContextError

from .wast import (
    WFuncDef,
    WClass,
    WBlock,
)
from .program import Program


def tag(f):
    f._worm_method_tag = True
    return f


def invalidate_progam(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        self._program = None
        return f(self, *args, **kwargs)

    return wrapper


class WormMode(Enum):
    PROGRAM = auto()
    LIBRARY = auto()


class WormContext:
    def __init__(self, mode=WormMode.PROGRAM):
        self.mode = mode
        self.setup_fresh_state()
        tag(self)

    def setup_fresh_state(self):
        """
        Clear all states and setup the context for a new program.
        """
        self.functions = {}
        self.classes = {}
        self.entry_point = None
        self.exported = set()

        self._program = None

    @property
    def program(self):
        if self.mode == WormMode.PROGRAM and self.entry_point is None:
            raise WormContextError("The program have no entry point.")

        if self._program is None:
            self._program = Program.from_context(self)

        return self._program

    @tag
    @invalidate_progam
    def add(self, node, /, **injected):
        """
        Used as a decorator or as a function, take a Worm function, class or
        expression. The resulting python value is return and, in case of a
        decorator, bound to the class/function name.
        """
        if isinstance(node, WFuncDef):
            assert (
                not injected
            ), "worm.add does not accept keyword arguments with function definition parameter."
            self.functions[node.name] = node
        elif isinstance(node, WClass):
            assert (
                not injected
            ), "worm.add does not accept keyword arguments with class definition parameter."
            self.classes[node.name] = node
        else:
            b = WBlock([node]).copy_common(node)

            b.hygienic = True

            b.injected = injected
            return b

        return node

    @tag
    @invalidate_progam
    def entry(self, f):
        """
        Take a worm function and register it as the program entry point.
        """
        assert isinstance(
            f, WFuncDef
        ), "Only a function can be taken as an entry point."
        self.entry_point = f
        return f

    @tag
    @invalidate_progam
    def export(self, f):
        """
        Take a worm function and register it as an exported function.
        """
        if self.mode == WormMode.PROGRAM:
            raise WormContextError("A program cannot export functions.")

        assert isinstance(
            f, WFuncDef
        ), "Only a function can be exported."  # FIXME export types too
        self.exported.add(f.name)
        return f

    @tag
    @invalidate_progam
    def block(self, f):
        """
        Used as a decorator, the decorated function is made into an hygienic
        Worm block of statements block to be used in Worm function.
        """

        def wrapper(**kwargs):
            defaults = f.defaults
            args = [arg.name for arg in f.args]
            offset = len(args) - len(defaults)
            injected = {}

            for i, arg in enumerate(args):
                if arg in kwargs:
                    injected[arg] = kwargs[arg]
                elif i < offset:
                    raise TypeError(
                        f"{f.name} missing required positional argument {arg}"
                    )
                else:
                    injected[arg] = defaults[i - offset]

            b = f.body

            b.hygienic = True
            b.injected = injected

            return b

        wrapper._wrapped_block = True

        return wrapper

    @invalidate_progam
    def __call__(self, *args, **kwargs):
        """
        Syntactic sugar for worm.add
        """
        return self.add(*args, **kwargs)

    def dump_source(self):
        """
        Return the current program as a string of C source.
        """
        return self.program.dump_source()

    def save_source(self, file):
        """
        Dump the current program into the given file in the form of a C source
        file.
        The file parameter may be a string (filename) or a file-like object.
        """
        return self.program.save_source(file)

    def save_program(self, file):
        """
        Compile the current program and write on disk under filename.
        The file parameter may be a string (filename) or a file-like object.
        """
        return self.program.save_program(file)
