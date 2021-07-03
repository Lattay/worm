from .errors import WormTypeError
from .visitor import WormVisitor
from .wtypes import is_atom_type, void
from .wast import WName, WStoreName


class AnnotateWithTypes(WormVisitor):
    def __init__(self):
        self.subst = SubstitutionTable()

    def visit(self, node):
        if node is None:
            return None
        if node.type is None:
            node.type = self.subst.new_var()
        return super().visit(node)

    def visit_topLevel(self, node):
        new_top = super().visit(node)
        new_top.subst = self.subst
        return new_top


class FlattenTypes(WormVisitor):
    def __init__(self):
        self.subst = None

    def visit(self, node):
        if node is None:
            return None
        if self.subst is not None:
            node.type = self.subst.resolve(node.type)
            if isinstance(node.type, TypeVar):
                raise WormTypeError("Dangling type", node.type, "")
        return super().visit(node)

    def visit_topLevel(self, node):
        node.subst = self.subst
        new_top = super().visit(node)
        return new_top


class ValidateMain(WormVisitor):
    def visit_topLevel(self, node):
        # FIXME authorize main parameters ?
        if node.entry is not None:
            if node.entry.returns is None:
                node.entry.type = make_function_type(void)
            else:
                node.entry.type = make_function_type(int)
        return node


class UnifyTypes(WormVisitor):
    """
    This visitor will apply the relations between node types
    """

    def __init__(self):
        self.current_function_return = []

    def visit_topLevel(self, node):
        self.subst = node.subst

        tl = super().visit_topLevel(node)

        return tl

    # def visit_array(self, node):
    #     super().visit_array(node)
    #     if node.elements:
    #         this_type = reduce(lambda a, b: self.subst.unify_types(a, b),
    #                            (e.type for e in node.elements))
    #         self.subst.unify_types(node.type, this_type)
    #     else:
    #         self.subst.unify_types(Array[None], node.type)

    #     return node

    # def visit_struct(self, node):
    #     super().visit_struct(node)
    #     self.subst.unify_types(node.type, Struct(
    #         **{key.name: val.type for key, val in node.fields}
    #     ))
    #     return node

    def visit_tuple(self, node):
        return self.visit_array(node)

    def visit_unary(self, node):
        # FIXME take polymorphism in account
        node.operand = self.visit(node.operand)
        self.subst.unify_types(
            node.op.type,
            make_function_type(self.subst.new_var(), node.operand.type)
        )
        self.subst.unify_types(node.type, node.op.type.return_type)
        return node

    # def visit_ptr(self, node):
    #     node.value = self.visit(node.value)
    #     self.subst.unify_types(node.type, Ptr(node.value.type))
    #     return node

    # def visit_deref(self, node):
    #     node.value = self.visit(node.value)
    #     self.subst.unify_types(node.type, Deref(node.value.type))
    #     return node

    def visit_binary(self, node):
        # FIXME take operator overloading in account
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        self.subst.unify_types(
            node.op.type,
            make_function_type(self.subst.new_var(), node.left.type, node.right.type)
        )
        self.subst.unify_types(node.type, node.op.type.return_type)
        return node

    def visit_boolOp(self, node):
        # FIXME take operator overloading in account
        node.values = list(map(self.visit, node.values))
        for v in node.values:
            self.subst.unify_types(bool, v.type)
        self.subst.unify_types(bool, node.type)
        return node

    def visit_compare(self, node):
        node.left = self.visit(node.left)
        node.rest = [(op, self.visit(val)) for op, val in node.rest]
        # FIXME ensure types from left and rest are compatible with the operator
        self.subst.unify_types(bool, node.type)
        return node

    def visit_ifExpr(self, node):
        node.body = self.visit(node.body)
        node.orelse = self.visit(node.orelse)
        node.test = self.visit(node.test)
        self.subst.unify_types(bool, node.test.type)
        self.subst.unify_types(node.body.type, node.orelse.type)
        self.subst.unify_types(node.type, node.body.type)
        return node

    def visit_getAttr(self, node):
        node.value = self.visit(node.value)
        t = node.value.type.deref()
        if t.expose_attr(node.attr):
            node.type = t.get_attr(node.attr)
        else:
            raise WormTypeError(f"The type {t} does not exposes attribute {node.attr}.")
        return node

    def visit_getItem(self, node):
        raise NotImplementedError("Type of item")

    def visit_slice(self, node):
        raise NotImplementedError("Type of slice")

    def visit_assign(self, node):
        node.value = self.visit(node.value)
        if len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, WStoreName):
                self.subst.unify_types(target.type, node.value.type)
                self.subst.unify_types(node.type, target.type)
            else:
                raise NotImplementedError(
                    f"Assignement to complex target: expected {WStoreName} but got {type(target)}."
                )
        else:
            raise NotImplementedError("Multiple targets in assignment")
        return node

    def visit_funcDef(self, node):
        self.current_function_return.append(node.returns)
        res = super().visit_funcDef(node)

        self.subst.unify_types(
            res.type,
            make_function_type(res.returns.type,
                               *(e.type for e in res.args)),
        )

        self.current_function_return.pop()
        return res

    def visit_return(self, node):
        if node.value:
            node.value = self.visit(node.value)
            self.subst.unify_types(node.value.type, self.current_function_return[-1])
            self.subst.unify_types(node.type, node.value.type)
        else:
            self.subst.unify_types(node.type, void)
        return node

    def visit_call(self, node):
        if not isinstance(node.func, WName):
            raise NotImplementedError("Calling an expression")

        node.args = list(map(self.visit, node.args))
        # node.kwargs = {key: self.visit(arg) for key, arg in node.kwargs.items()}

        self.subst.unify_types(
            make_function_type(node.type,
                               *(e.type for e in node.args)),
            node.func.type,
        )

        return node


class FunctionPrototype:
    def __init__(self, returns, *args):
        self.returns = returns
        self.args = [arg for arg in args]

    def check_return(self, ret):
        return check_type(self.returns, ret)

    def check_args(self, *args):
        return all(check_type(ref, arg) for ref, arg in zip(self.args, args))


class SubstitutionTable:
    def __init__(self):
        self.vars = {}

    def new_id(self):
        """Return a new unique id
        """
        return object()

    def new_var(self):
        """Return a fresh type variable
        """
        n = self.new_id()
        v = TypeVar(n)
        self.vars[n] = None
        return v

    def resolve(self, var):
        """Get the best representation of the type corresponding to var.

        Loop over the dependency chain of type variables until it reach either None
        (meaning the type variable is still dangling) and thus return the last
        type variable encountered, or it reaches a concreate type.
        """

        while isinstance(var, TypeVar):
            prev = var
            var = self.vars[var.name]

        return var or prev

    def unify_types(self, type_a, type_b):
        """Unify type_a and type_b or raise a WormTypeError
        """

        ta, tb = self.resolve(type_a), self.resolve(type_b)
        if isinstance(ta, TypeVar):
            self.vars[ta.name] = tb
        elif isinstance(tb, TypeVar):
            self.unify_types(tb, ta)
        elif is_atom_type(ta) and is_atom_type(tb):
            if ta != tb:
                raise WormTypeError("Could not unify these types", ta, tb)
        elif isinstance(ta, FunctionType) and isinstance(tb, FunctionType):
            self.unify_types(ta.ret_type, tb.ret_type)
            for a, b in zip(ta.args_types, tb.args_types):
                # FIXME consider different number of parameters
                # FIXME consider function polymorphism
                self.unify_types(a, b)
        else:
            raise WormTypeError("Could not unify these types", ta, tb)


class TypeVar:
    def __init__(self, name):
        self.name = name


class FunctionType:
    def __init__(self, ret_type, args_types):
        self.ret_type = ret_type
        self.args_types = args_types


def make_function_type(ret_type, *args_types):
    return FunctionType(ret_type, args_types)


def check_type(expected, observed):
    pass
