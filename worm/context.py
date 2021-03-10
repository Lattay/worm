from contextlib import contextmanager
from functools import wraps
from copy import deepcopy

from .wast import (
    WAst,
    WFuncDef,
    WClass,
    WExpr,
    WBlock,
)
from .program import Program


def invalidate_progam(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        self._program = None
        return f(self, *args, **kwargs)

    return wrapper


class WormContext:
    def __init__(self):
        self.functions = set()
        self.classes = set()
        self.entry_point = None

        self._scope = [{}]
        self._program = None

    @property
    def program(self):
        if self._program is None:
            self._program = Program.from_context(self)

        return self._program

    def add_to_scope(self, name, value):
        self._scope[-1][name] = value

    @contextmanager
    def scope(self, **kwargs):
        """
        Create a new scope for Worm. Keyword parameters bound Worm names to
        Python values. Those value should be compatible with Worm (either types
        or function/classes).
        """
        frame = kwargs
        self._scope.append(frame)
        try:
            yield
        finally:
            self._scope.pop()

    @invalidate_progam
    def add(self, node, /, **injected):
        """
        Used as a decorator or as a function, take a Worm function, class or
        expression. Class and functions are added to the current scope.
        Expression are not, and should be later used in function classes. The
        resulting python value is return and, in case of a decorator, bound to
        the class/function name.
        """
        if isinstance(node, WFuncDef):
            assert not injected, "worm.add does not accept keyword arguments with function definition parameter."
            self.add_to_scope(node.name, node)
            self._save_scope(node)
            self.functions.add(node)
        elif isinstance(node, WClass):
            assert not injected, "worm.add does not accept keyword arguments with class definition parameter."
            self.add_to_scope(node.name, node)
            self._save_scope(node)
            self.classes.add(node)
        else:
            b = WBlock([node]).copy_common(node)

            b.hygienic = True

            b.injected = injected
            return b

        return node

    @invalidate_progam
    def entry(self, f):
        """
        Take a worm function and register it as the program entry point.
        """
        self.add_to_scope(f.name, f)
        self._save_scope(f)
        assert isinstance(
            f, WFuncDef
        ), "Only a function can be taken as an entry point."
        self.entry_point = f
        return f

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

            with self.scope(**injected):
                self._save_scope(b)
            b.injected = injected
            return b

        wrapper._wrapped_block = True

        self.add_to_scope(f.name, wrapper)

        return wrapper

    @invalidate_progam
    def __call__(self, *args, **kwargs):
        """
        Syntactic sugar for worm.add
        """
        return self.add(*args, **kwargs)

    def _save_scope(self, f):
        assert isinstance(f, WAst), f"Expected Worm AST node but got {type(f)}."
        f._scope = deepcopy(self._scope)

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

    def expand(self, f, **kwargs):
        """
        Expand a "macro" inside a Worm block.
        """
        if kwargs:
            raise NotImplementedError()
        return f
