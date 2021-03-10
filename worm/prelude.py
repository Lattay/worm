from .wast import WConstant, Ref
from .type_checker import FunctionPrototype, check_type
from .wtypes import Array, void, ptr
from .printf import parse_format


class PrintfChecker(FunctionPrototype):
    def __init__(self):
        self.returns = Ref(void)

    def check_args(self, format, *args):
        if not isinstance(format, WConstant) or format.type.deref() != str:
            return False
        _, param_convs = parse_format(format.value)
        expected_types = [formatconv_to_type(p.spec) for p in param_convs]
        return (
            len(expected_types) == len(args)
            and all(map(check_type, expected_types, args))
        )


def formatconv_to_type(conv):
    if conv in {'d', 'i', 'o', 'u', 'x', 'X'}:
        return int
    elif conv in {'f', 'F', 'e', 'E', 'g', 'G', 'a', 'A'}:
        return float
    elif conv == 's':
        return str
    elif conv == 'c':
        return chr
    elif conv == 'p':
        return ptr


prelude = {
    "printf": Ref(PrintfChecker()),
    "main": Ref(FunctionPrototype(int, int, Array[int])),
}
