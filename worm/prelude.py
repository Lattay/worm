from .wast import WConstant, WPtr, WDeref
from .type_checker import FunctionPrototype, check_type
from .wtypes import void, char  # , Ptr, Array
from .printf import parse_format


class PrintfPrototype(FunctionPrototype):
    def __init__(self):
        self.returns = void

    def check_args(self, format, *args):
        if not isinstance(format, WConstant) or format.type.deref() != str:
            return False
        _, param_convs = parse_format(format.value)
        expected_types = [formatconv_to_type(p.spec) for p in param_convs]
        return len(expected_types) == len(args) and all(
            map(check_type, expected_types, args)
        )


def formatconv_to_type(conv):
    if conv in {"d", "i", "o", "u", "x", "X"}:
        return int
    elif conv in {"f", "F", "e", "E", "g", "G", "a", "A"}:
        return float
    elif conv == "s":
        return str
    elif conv == "c":
        return chr
    # elif conv == "p":
    #     return Ptr(void)


prelude = {
    "printf": PrintfPrototype(),
    "main": FunctionPrototype(int),  # , int, Array[int]),
    "ptr": WPtr,
    "deref": WDeref,
    "int": int,
    "float": float,
    "chr": char,
    "bool": bool,
    "void": void,
}
