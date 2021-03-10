"""import_hook.py
------------------
This module contains the core functions required to create an import hook.
"""

import ast
import os
import sys

from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_file_location, decode_source

from . import console

from ast import fix_missing_locations

PYTHON = os.path.dirname(os.__file__).lower()


class CustomMetaFinder(MetaPathFinder):
    """A custom finder to locate modules. The main reason for this code
    is to ensure that our custom loader, which does the code transformations,
    is used."""

    def __init__(
        self,
        transform_ast=None,
        extensions=None,
        debug=False
    ):
        self.transform_ast = transform_ast
        self.extensions = extensions or [".py"]
        self.debug = debug

    def find_spec(self, fullname, path=None, target=None):
        """finds the appropriate properties (spec) of a module, and sets
        its loader."""

        if not path:
            _path = sys.path
        else:
            _path = path

        for path in _path:
            if "." in fullname:
                name = fullname.split(".")[-1]
            else:
                name = fullname

            for ext in self.extensions:
                filename = os.path.join(path, name + ext)

                if os.path.exists(filename):
                    return spec_from_file_location(
                        fullname,
                        filename,
                        loader=CustomLoader(
                            filename,
                            transform_ast=self.transform_ast,
                            debug=self.debug,
                        ),
                    )
        return None  # we don't know how to import this


class CustomLoader(Loader):
    """A custom loader which will transform the source prior to its execution"""

    def __init__(
        self,
        filename,
        transform_ast,
        debug=False
    ):
        self.filename = filename
        self.transform_ast = transform_ast
        self.debug = debug

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        """Import the source code, transform it before executing it so that
        it is known to Python.
        """
        with open(self.filename, mode="r+b") as f:
            source = decode_source(f.read())

        tree = ast.parse(source, self.filename)
        tree = self.transform_ast(tree)
        tree = fix_missing_locations(tree)

        if self.debug:
            print(ast.dump(tree, indent=2))
            print(ast.unparse(tree))

        code_object = compile(tree, self.filename, "exec")
        exec(code_object, module.__dict__)


def create_hook(transform_ast, extensions, hook_name=None, debug=False):
    """Function to facilitate the creation of an import hook.
    It sets the parameters to be used by the import hook, and also
    does so for the interactive console.
    """
    hook = CustomMetaFinder(
        extensions=extensions,
        transform_ast=transform_ast,
        debug=debug
    )

    sys.meta_path.append(hook)

    console.configure(
        transform_ast=transform_ast,
    )

    return hook


def remove_hook(hook):
    """Function used to remove a previously import hook inserted in sys.meta_path"""
    for index, h in enumerate(sys.meta_path):
        if h == hook:
            break
    else:
        print("Import hook not found in remove_hook.")
        return
    del sys.meta_path[index]
    console.configure()
