class WormType:
    pass


class SimpleType(WormType):
    def __init__(self, name):
        self.name = name

    def to_c(self):
        return self.name


class CompoundType(WormType):
    def __init__(self, name, params):
        self.name = name
        self.params = params


class GeneralType(WormType):
    def __init__(self, name, params):
        self.name = name
        self.params = params

    def __getitem__(self, params):
        if isinstance(params, (tuple, list)):
            _params = params
        else:
            _params = (params,)
        return CompoundType(self.name, dict(zip(self.params, _params)))


def worm_type(name, params=()):
    if not params:
        return SimpleType(name)
    else:
        return GeneralType(name, params)


void = worm_type("void")
ptr = worm_type("ptr", params=["refered_type"])

Array = worm_type("array", params=["element_type"])
Prod = worm_type("prod", params=["element_types"])

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
    ptr,
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
    elif hasattr(type, 'to_c'):
        return type.to_c()
    else:
        raise NotImplementedError(f'{type} is not supported yet')


def merge_types(a, b):
    '''
    Should be used to merge partial types.
    '''
    # TODO
    if a == b:
        return a
    else:
        return None
