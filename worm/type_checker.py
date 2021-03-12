from functools import reduce

from .errors import WormTypeError
from .visitor import WormVisitor
from .wtypes import void, ptr, Array, SimpleType
from .wast import WName, WStoreName, WConstant, Ref, merge_types


class AnnotateSymbols(WormVisitor):
    """
    This visitor will built a mapping of symbols and there types and put it into toplevel node,
    including functions.
    """

    def __init__(self, prelude):
        self.symbol_table = {**prelude}

    def visit_topLevel(self, node):
        new_top = super().visit_topLevel(node)
        new_top.symbol_table = self.symbol_table
        return new_top

    def visit_funcDef(self, node):
        for arg in node.args:
            self.symbol_table[arg.name] = Ref(arg.type)
        self.symbol_table[node.name] = Ref(
            FunctionPrototype(node.returns, *(arg.type for arg in node.args))
        )
        return super().visit_funcDef(node)

    def visit_assign(self, node):
        if len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, WStoreName):
                name = target.name
                if name not in self.symbol_table:
                    if not node.type.deref():
                        node.type = Missing(node.src_pos)
                    self.symbol_table[name] = Ref(node.type)
            else:
                raise NotImplementedError(
                    f"Assignement to complex target: expected {WStoreName} but got {type(target)}."
                )
        else:
            raise NotImplementedError("Multiple targets in assignment")
        return super().visit_assign(node)


class PropagateAndCheckTypes(WormVisitor):
    """
    This visitor will check for all nodes where types should match.
    (ex: both side of an assignment, parameters to a function call...)
    """

    def __init__(self, prelude):
        self.globals = prelude
        self.current_function_return = []

    def visit_topLevel(self, node):
        self.symbol_table = node.symbol_table

        return super().visit_topLevel(node)

    def visit_name(self, node):
        node.type = self.symbol_table[node.name]
        return node

    def visit_array(self, node):
        super().visit_array(node)
        if node.elements:
            node.type = reduce(merge_types, (e.type for e in node.elements))
            if node.type.deref() is not None:
                node.type = Array[node.elements[0].type]
            else:
                raise WormTypeError("Non homogeneous array.", at=node.src_pos)
        else:
            node.type = Array[None]

        return node

    def visit_tuple(self, node):
        return self.visit_array(node)

    def visit_unary(self, node):
        # FIXME take operator overloading in account
        node.operand = self.visit(node.operand)
        node.type = node.operand.type
        return node

    def visit_binary(self, node):
        # FIXME take operator overloading in account
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        if node.left.type.deref() != node.right.type.deref():
            raise WormTypeError(
                "Incompatible types in binary operation.",
                at=node.src_pos,
                expect=node.left.type,
                got=node.right.type,
            )
        node.left.type.ref(node.right.type)
        node.type = node.right.type
        return node

    def visit_boolOp(self, node):
        # FIXME take operator overloading in account
        node.values = list(map(self.visit, node.values))
        if any(val.type.deref() != bool for val in node.values):
            raise WormTypeError(
                "Incompatible types in boolean operation.", at=node.src_pos
            )
        node.type = bool
        return node

    def visit_compare(self, node):
        node.left = self.visit(node.left)
        node.rest = [(op, self.visit(val)) for op, val in node.rest]
        node.type = bool
        return node

    def visit_ifExpr(self, node):
        node.body = self.visit(node.body)
        node.orelse = self.visit(node.orelse)
        if node.body.type.deref() != node.orelse.type.deref():
            raise WormTypeError(
                "Incompatible types in if-expr",
                at=node.src_pos,
                expect=node.body.type,
                got=node.orelse.type,
            )
        node.test = self.visit(node.test)
        node.body.type = node.orelse.type
        node.type = node.body.type
        return node

    def visit_getAttr(self, node):
        raise NotImplementedError("Type of attribute")

    def visit_getItem(self, node):
        raise NotImplementedError("Type of item")

    def visit_slice(self, node):
        raise NotImplementedError("Type of slice")

    def visit_assign(self, node):
        node.value = self.visit(node.value)
        if len(node.targets) != 1:
            raise NotImplementedError("Multiple target")
        target = node.targets[0]
        if not isinstance(target, WStoreName):
            raise NotImplementedError(
                f"Assignement to complex target: expected {WStoreName} but got {type(target)}."
            )

        if node.value.type.deref() != self.symbol_table[target.name].deref():
            raise WormTypeError(
                "Incompatible type in assignment.",
                at=node.src_pos,
                expect=self.symbol_table[target.name],
                got=node.value.type,
            )

        self.symbol_table[target.name] = node.value.type

        return node

    def visit_funcDef(self, node):
        self.current_function_return.append(node.returns)
        res = super().visit_funcDef(node)
        self.current_function_return.pop()
        return res

    def visit_return(self, node):
        node.value = self.visit(node.value)
        if node.value.type.deref() != self.current_function_return[-1].deref():
            raise WormTypeError(
                "Incompatible type returned.",
                at=node.src_pos,
                expect=self.current_function_return[-1],
                got=node.value.type,
            )
        self.current_function_return[-1] = node.value.type
        return node

    def visit_call(self, node):
        if not isinstance(node.func, WName):
            raise NotImplementedError("Calling an expression")
        proto = self.symbol_table[node.func.name].deref()

        node.args = list(map(self.visit, node.args))
        node.kwargs = {key: self.visit(arg) for key, arg in node.kwargs.items()}

        # FIXME funcdef does not support keywords so I don't implement them here yet
        if not proto.check_args(*node.args):
            # FIXME how to point to the faulty parameter ?
            raise WormTypeError(
                f'Incompatible argument type in call: {", ".join(str(arg.type) for arg in node.args)}',
                at=node.src_pos,
            )

        node.type = proto.returns
        return node


class FunctionPrototype:
    def __init__(self, returns, *args):
        self.returns = Ref(returns)
        self.args = [Ref(arg) for arg in args]

    def check_return(self, ret):
        return check_type(self.returns, ret)

    def check_args(self, *args):
        return all(check_type(ref, arg) for ref, arg in zip(self.args, args))


def check_type(expected, instance):
    if isinstance(expected, Ref):
        _expected = expected.deref()
    else:
        _expected = expected
    return (
        (isinstance(_expected, type) and isinstance(instance, _expected))
        or instance.type.deref() == _expected
        or (
            _expected == chr
            and isinstance(instance, WConstant)
            and isinstance(instance.value, str)
            and len(instance.value) == 1
        )
        or (_expected is void and instance.type.deref() is None)
        or (_expected is int and isinstance(instance, ptr))
    )


class Missing(SimpleType):
    """
    Special class for the any type
    """

    def __init__(self, at):
        super().__init__("missing")
        self.at = at

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def to_c(self):
        raise WormTypeError("Missing type information", at=self.at)
