"""
Set the basis of Worm type system.
Summary:
- all Worm types are instances of WormType
- higher order types (applications from types to types) are subclasses of HigherOrderType
  (which is a subclasses of WormType)
- type derivated from an higher order type are instance of class defining the higer order type
- higher order types are not types themself and must be specialized to be used
"""
from uuid import uuid1


class WormType:
    def __init__(self):
        self.methods = {}
        self.id = uuid1()

    def value_to_c(self, value):
        raise NotImplementedError("This type does not have literal values.")

    def is_declared(self):
        return False

    def declaration(self, to_c):
        raise NotImplementedError("This type cannot be declared.")

    def type_to_c(self, to_c):
        raise NotImplementedError("This type is not expressed in C")

    def expose_attr(self, attr):
        return False

    def get_attr(self, attr, default=None):
        return default


class SimpleType(WormType):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __repr__(self):
        return f"SimpleType({self.name!r})"

    def type_to_c(self, _):
        return self.name


void = SimpleType("void")
char = SimpleType("char")


def to_c_type(type_):
    if type_ == int:
        return "int64_t"
    elif type_ == bool:
        return "bool"
    elif type_ == float:
        return "double"
    elif type_ == str:
        return "char*"
    elif isinstance(type_, WormType):
        if type_.is_declared():
            return type_.name
        elif hasattr(type_, "to_primitives"):
            return to_c_type(type_.to_primitives())
        else:
            return type_.type_to_c(to_c_type)
    else:
        raise NotImplementedError(f"{type_} is not a valid type.")


def is_atom_type(t):
    return t in {
        int,
        bool,
        float,
        str,
    } or isinstance(t, SimpleType)


def from_name(t):
    return {
        "int": int,
        "bool": bool,
        "float": float,
        "str": str,
        "void": void,
        "char": char,
    }.get(t, None)

