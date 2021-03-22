from .errors import WormTypeError
from .wtypes import merge_types as _merge_types


class WAst:
    def __init__(self, *, src_pos=None):
        self._type = Ref(None)
        self.src_pos = src_pos

    def copy_common(self, other):
        self.src_pos = other.src_pos
        self.type = other.type
        return self

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, new):
        if isinstance(self._type, Ref):
            self._type.ref(new)
        else:
            self._type = Ref(new)


class WTopLevel(WAst):
    def __init__(self, *, entry=None, functions=(), headers=(), **kwargs):
        super().__init__(**kwargs)
        self.entry = entry
        self.functions = list(functions)
        self.headers = list(headers)
        self.symbol_table = {}

    def copy_common(self, other):
        if isinstance(other, WTopLevel):
            self.symbol_table = other.symbol_table

        return super().copy_common(other)


class WStatement(WAst):
    pass


class WExpr(WAst):
    pass


class WExprStatement(WStatement):
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.value = value


class WBlock(WStatement):
    def __init__(self, statements, **kwargs):
        super().__init__(**kwargs)
        self.statements = list(statements)
        self.injected = {}
        self.hygienic = False

    def copy_common(self, other):
        super().copy_common(other)
        if isinstance(other, WBlock):
            self.injected = other.injected
            self.hygienic = other.hygienic
        return self


class WConstant(WExpr):
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.value = value

        if isinstance(value, int):
            self.type = int
        elif isinstance(value, float):
            self.type = float
        elif isinstance(value, str):
            self.type = str
        elif isinstance(value, bool):
            self.type = bool


class WArray(WExpr):
    def __init__(self, *elements, **kwargs):
        super().__init__(**kwargs)
        self.elements = list(elements)


class WTuple(WExpr):
    def __init__(self, *elements, **kwargs):
        super().__init__(**kwargs)
        self.elements = list(elements)


class WStruct(WExpr):
    def __init__(self, *fields, **kwargs):
        super().__init__(**kwargs)
        self.fields = fields


class WName(WAst):
    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self.name = name

    def __repr__(self):
        return f"WName('{self.name}')"


class WStoreName(WAst):
    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.declaration = False

    def copy_common(self, other):
        if isinstance(other, WStoreName):
            self.declaration = other.declaration
        return super().copy_common(other)


class WUnary(WExpr):
    def __init__(self, op, operand, **kwargs):
        super().__init__(**kwargs)
        self.op = op
        self.operand = operand


class WBinary(WExpr):
    def __init__(self, op, left, right, **kwargs):
        super().__init__(**kwargs)
        self.op = op
        self.left = left
        self.right = right


class WBoolOp(WExpr):
    def __init__(self, op, *values, **kwargs):
        super().__init__(**kwargs)
        self.op = op
        self.values = list(values)


class WCompare(WExpr):
    def __init__(self, left, *rest, **kwargs):
        super().__init__(**kwargs)
        self.left = left
        self.rest = rest


class WCall(WExpr):
    def __init__(self, func, args, func_kwargs, **kwargs):
        super().__init__(**kwargs)
        self.func = func
        self.args = list(args)
        self.kwargs = func_kwargs


class WIfExpr(WExpr):
    def __init__(self, test, body, orelse, **kwargs):
        super().__init__(**kwargs)
        self.test = test
        self.body = body
        self.orelse = orelse


class WGetAttr(WExpr):
    def __init__(self, value, attr, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.attr = attr


class WSetAttr(WAst):
    def __init__(self, value, attr, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.attr = attr


class WGetItem(WExpr):
    def __init__(self, value, slice_, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.slice = slice_


class WSetItem(WExpr):
    def __init__(self, value, slice_, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.slice = slice_


class WSlice(WExpr):
    def __init__(self, lower, upper, step, **kwargs):
        super().__init__(**kwargs)
        self.lower = lower
        self.upper = upper
        self.step = step


class WAssign(WStatement):
    def __init__(self, targets, value, annotation=None, **kwargs):
        super().__init__(**kwargs)
        self.targets = list(targets)
        self.value = value
        self.type = annotation or self.type


class WRaise(WStatement):
    def __init__(self, exc, cause, **kwargs):
        super().__init__(**kwargs)
        self.exc = exc
        self.cause = cause


class WAssert(WStatement):
    def __init__(self, test, message, **kwargs):
        super().__init__(**kwargs)
        self.test = test
        self.message = message


class WDel(WStatement):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.targets = list(args)


class WPass(WStatement):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class WIf(WStatement):
    def __init__(self, test, body, orelse, **kwargs):
        super().__init__(**kwargs)
        self.test = test
        self.body = body
        self.orelse = orelse


class WFor(WStatement):
    def __init__(self, target, iter, body, orelse, **kwargs):
        super().__init__(**kwargs)
        self.target = target
        self.iter = iter
        self.body = body
        self.orelse = orelse


class WWhile(WStatement):
    def __init__(self, test, body, orelse, **kwargs):
        super().__init__(**kwargs)
        self.test = test
        self.body = body
        self.orelse = orelse


class WBreak(WStatement):
    pass


class WContinue(WStatement):
    pass


class WFuncDef(WStatement):
    def __init__(self, name, args, defaults, body, returns, docstring=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.docstring = docstring
        self.args = list(args)
        self.defaults = list(defaults)
        self.body = body
        self._returns = Ref(returns)
        self.attached = {}

    @property
    def returns(self):
        return self._returns

    @returns.setter
    def returns(self, new):
        if isinstance(self._returns, Ref):
            self._returns.ref(new)
        else:
            self._returns = Ref(new)

    @property
    def prototype(self):
        return {
            "name": self.name,
            "return": self.returns.deref(),
            "args": [arg.type for arg in self.args],
        }

    def copy_common(self, other):
        super().copy_common(other)
        if isinstance(other, WFuncDef):
            self.attached = other.attached
            self.docstring = other.docstring
        return self


class WArg(WAst):
    def __init__(self, name, annot, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.type = annot


class WClass(WStatement):
    def __init__(self, name, bases, body, docstring=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.bases = list(bases)
        self.body = body
        self.docstring = docstring

    def copy_common(self, other):
        if isinstance(other, WClass):
            self.docstring = other.docstring
        return super().copy_common(other)


class WReturn(WStatement):
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.value = value


class WPrimitiveExpr(WExpr):
    pass


class WPtr(WPrimitiveExpr):
    _primitive = True

    def __init__(self, *args, **kwargs):
        if len(args) != 1:
            raise WormTypeError("ptr must be applied to exaclty one value.")
        val = args[0]
        if kwargs:
            raise WormTypeError("ptr does not accept keyword arguments.", at=val)

        self.value = val


class WDeref(WPrimitiveExpr):
    _primitive = True

    def __init__(self, *args, **kwargs):
        if len(args) != 1:
            raise WormTypeError("deref must be applied to exaclty one value.")
        val = args[0]
        if kwargs:
            raise WormTypeError("deref does not accept keyword arguments.", at=val)

        self.value = val


class Ref:
    def __init__(self, value):
        self.refered = value

    def _root(self):
        if isinstance(self.refered, Ref):
            return self.refered._root()
        else:
            return self

    def deref(self):
        return self._root().refered

    def ref(self, value):
        self._root()._ref(value)

    def _ref(self, value):
        """
        self MUST be its own root
        """
        if isinstance(value, Ref):
            root = value._root()
            if root is self:
                pass
            else:
                self.refered = root
        else:
            self.refered = value

    def __repr__(self):
        return f"Ref({repr(self.deref())})"


def merge_types(a, b):
    new_type = Ref(_merge_types(a.deref(), b.deref()))
    if new_type is None:
        return None
    a.ref(new_type)
    b.ref(a)
    return new_type
