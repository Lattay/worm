from .wtypes import HigherOrderType, WormType, WormIterator
from .wast import WArray
from worm import worm


class Ptr(HigherOrderType):
    def __init__(self, pointed_type):
        super().__init__("pointer", pointed_type)
        self.pointed_type = pointed_type

    def to_c(self, other_to_c):
        return other_to_c(self.pointed_type) + '*'

    def cons(self, value, to_c):
        return "&" + to_c(value)


class Array(HigherOrderType):
    def __init__(self, element_type):
        super().__init__("array", element_type)
        self.element_type = element_type

    def needs_declaration(self):
        return True

    def to_c(self, other_to_c):
        return "struct {\nsize_t len;\n" + other_to_c(self.element_type) + "* elems;}"

    def literal_to_c(self, value, value_to_c):
        assert isinstance(value, WArray)
        return "{len=" + str(len(value.elements)) + ", elems={" + ", ".join(map(value_to_c, value.elements)) + "}}"

    @worm.method
    def empty(self):
        return self.len == 0

    @worm.method
    def iter(self):
        return ArrayIterator[self.element_type].iter(self)


class ArrayIterator(WormIterator):
    def __init__(self, element_type):
        super().__init__("array_iterator", element_type)
        self.element_type = element_type

    def needs_declaration(self):
        return True

    def to_c(self, other_to_c):
        return "struct {\n size_t len;\n size_t i;\n" + other_to_c(Array[self.element_type]) + "* array;}"

    @worm.method
    def iter(self):
        return self

    @worm.method
    def next(self):
        raise NotImplementedError()
