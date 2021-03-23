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


class MetaHigherOrderType(type):
    def __getitem__(self, params):
        if isinstance(params, tuple):
            return self.specialize(*params)
        else:
            return self.specialize(params)


class HigherOrderType(WormType, metaclass=MetaHigherOrderType):
    type_names = {}
    name_counter = [0]

    def __init__(self, basename, *args):
        """
        Subclasses must pass arguments to this constructor to allow instances to be hased and identified.
        """
        super().__init__()
        self.caracteristic = (self.__class__.__name__, *args)
        self.id = self.unique_id(basename, *args)
        if self.id not in self.type_names:
            self.name_counter[0] += 1
            self.type_names[self.id] = f"{basename}_{self.name_counter[0]}"

        self.name = self.type_names[self.id]

    def unique_id(self, *args):
        return args

    def is_declared(self):
        return True

    def declaration(self, to_c):
        return f"typedef {self.type_to_c(to_c)} {self.name};"

    def __eq__(self, other):
        return (
            isinstance(other, HigherOrderType)
            and len(self.caracteristic) == len(other.caracteristic)
            and all(s == o for s, o in zip(self.caracteristic, other.caracteristic))
        )

    def __hash__(self):
        return hash(self.caracteristic)

    @classmethod
    def specialize(cls, *args, **kwargs):
        return cls(*args, **kwargs)


class SimpleType(WormType):
    def __init__(self, name):
        self.name = name

    def type_to_c(self, _):
        return self.name


class Primitive(HigherOrderType):
    def to_primitives(self):
        return self


class Ptr(Primitive):
    def __init__(self, pointed_type):
        super().__init__("pointer", pointed_type)
        self.pointed_type = pointed_type

    def type_to_c(self, other_to_c):
        return other_to_c(self.pointed_type) + "*"

    def is_declared(self):
        return False


class Deref(HigherOrderType):
    def __init__(self, derefed_type):
        super().__init__("deref", derefed_type)
        self.derefed_type = derefed_type

    def type_to_c(self, other_to_c):
        raise NotImplementedError()
        return other_to_c(self.derefed_type) + "*"

    def is_declared(self):
        return False


class Struct(Primitive):
    def __init__(self, **fields):
        super().__init__("struct", tuple(fields.items()))
        self.fields = fields

    def expose_attr(self, name):
        if name in self.fields:
            return name

    def get_attr(self, name, default=None):
        return self.fields.get(name, default)

    def type_to_c(self, other_to_c):
        code = ["struct {"]
        for name, type in self.fields.items():
            code.append(f"{other_to_c(type)} {name};")
        code.append("}")
        return "\n".join(code)

    def value_to_c(self, **fields):
        return (
            "{" + ", ".join(f".{name}={value}" for name, value in fields.items()) + "}"
        )


class CArray(Primitive):
    def __init__(self, elements_type, size=None):
        super().__init__("array", (elements_type, size))
        self.elements_type = elements_type
        self.size = size

    def type_to_c(self, other_to_c):
        return (
            other_to_c(self.elements_type) + "[]"
            if self.size is None
            else f"[{self.size}]"
        )


class Array(HigherOrderType):
    def __init__(self, element_type):
        super().__init__("array", element_type)
        self.element_type = element_type
        self.struct = Struct(len=int, elems=self.element_type)

    def value_to_c(self, elements):
        return f"{{.length={len(elements)}, .elements={{"
        +", ".join(elements)
        +"}}"

    def to_primitives(self):
        return self.struct


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


def merge_types(a, b):
    """
    Should be used to merge partial types.
    """
    # TODO
    if a == b:
        return a
    else:
        return None
