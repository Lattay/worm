"""
Set the basis of Worm type system.
Summary:
- all Worm types are instances of WormType
- higher order types (applications from types to types) are subclasses of HigherOrderType
  (which is a subclasses of WormType)
- type derivated from an higher order type are instance of class defining the higer order type
- higher order types are not types themself and must be specialized to be used
"""


class WormType:
    def __init__(self):
        self.methods = {}

    def literal_to_c(self, value):
        raise NotImplementedError("This type does not have literal values.")

    def needs_declaration(self):
        return False

    def declaration(self):
        raise NotImplementedError("This type cannot be declared.")


class MetaHigherOrderType(type):
    def __getitem__(self, params):
        return self.specialize(params)


class HigherOrderType(WormType, metaclass=MetaHigherOrderType):
    type_names = {}
    name_counter = [0]

    def __init__(self, basename, *args):
        """
        Subclasses must pass arguments to this constructor to allow instances to be hased and identified.
        """
        super().__init__()
        self.caracteristic = (basename, *args)

    def unique_id(self, *args, **kwargs):
        return (args, tuple(sorted(kwargs.items())))

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

    def to_c(self):
        return self.name


def worm_type(name, params=()):
    if not params:
        return SimpleType(name)
    else:
        return GeneralType(name, params)


void = worm_type("void")

builtin_types = {
    int,
    str,
    float,
}

atomic_types = {
    # TODO add other flavor or int and floats (unsigned, other sizes...)
    int,
    chr,
    str,
    float,
}


def to_c_type(type):
    if type == int:
        return "int64_t"
    elif type == bool:
        return "bool"
    elif type == float:
        return "double"
    elif type == str:
        return "char*"
    elif type == chr:
        return "char"
    elif hasattr(type, "to_c"):
        return type.to_c()
    else:
        raise NotImplementedError(f"{type} is not supported yet")


def merge_types(a, b):
    """
    Should be used to merge partial types.
    """
    # TODO
    if a == b:
        return a
    else:
        return None
