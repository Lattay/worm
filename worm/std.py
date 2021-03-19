class Array(HigherOrderType):
    def __init__(self, elements_type):
        super().__init__("array", elements_type)
        self.elements_type = elements_type

    def to_primitives(self):
        return Struct(length=int, elems=CArray(self.elements_type))

    @worm.method
    def reduce(self, fn, init):
        acc: self.elements_type = init
        for i in range(self.length):
            acc = fn(acc, self.elems[i])

        return acc
