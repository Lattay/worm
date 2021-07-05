from .errors import WormTypeError, WormTypeInferenceError
from .visitor import WormVisitor
from .wtypes import is_atom_type, void, from_name
from .wast import WName, WStoreName


class IntroduceSymbolTypes(WormVisitor):
    def __init__(self, metadata):
        self.symbol_table = metadata.symbol_table

    def visit_name(self, node):
        node.type = self.symbol_table.get(node.name, None)
        return super().visit_name(node)


class AnnotateWithTypes(WormVisitor):
    def __init__(self, metadata):
        self.subst = metadata.subst = SubstitutionTable()

    def visit(self, node):
        if node is None:
            return None
        node.type = self.treat_type(node.type)
        return super().visit(node)

    def visit_funcDef(self, node):
        node.returns = self.treat_type(node.returns)
        return super().visit_funcDef(node)

    def treat_type(self, type_):
        if type_ is None:
            return self.subst.new_var()
        elif isinstance(type_, WName):
            t = from_name(type_.name)
            if t:
                return t
            else:
                raise WormTypeInferenceError(f"Unbound type name {type_}")
        else:
            return type_


class FlattenTypes(WormVisitor):
    def __init__(self, metadata):
        self.subst = metadata.subst

    def visit(self, node):
        if node is None:
            return None
        if self.subst is not None:
            node.type = self.treat_type(node.type)
            if not node.type:
                raise WormTypeInferenceError(f"Dangling type var for {node}", at=get_loc(node))
        return super().visit(node)

    def visit_funcDef(self, node):
        node.returns = self.treat_type(node.returns)
        if not node.returns:
            raise WormTypeInferenceError(f"Dangling type var for return type of {node.name}", at=get_loc(node))
        return super().visit_funcDef(node)

    def treat_type(self, type_):
        if isinstance(type_, TypeVar):
            res = self.subst.resolve(type_)
            if isinstance(res, TypeVar):
                return None
            else:
                return res
        else:
            return type_


class ValidateMain(WormVisitor):
    def visit_topLevel(self, node):
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

    def __init__(self, metadata):
        self.current_function_return = []
        self.subst = metadata.subst

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
            get_unary_op_type(node.op),
            make_function_type(self.subst.new_var(), node.operand.type),
            at=get_loc(node),
        )
        self.subst.unify_types(node.type, get_unary_op_type(node.op).ret_type, at=get_loc(node))
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
            get_binary_op_type(node.op),
            make_function_type(self.subst.new_var(), node.left.type, node.right.type),
            at=get_loc(node),
        )
        self.subst.unify_types(node.type, get_binary_op_type(node.op).ret_type, at=get_loc(node))
        return node

    def visit_boolOp(self, node):
        # FIXME take operator overloading in account
        node.values = list(map(self.visit, node.values))
        for v in node.values:
            self.subst.unify_types(bool, v.type, at=get_loc(v))
        self.subst.unify_types(bool, node.type, at=get_loc(node))
        return node

    def visit_compare(self, node):
        node.left = self.visit(node.left)
        node.rest = [(op, self.visit(val)) for op, val in node.rest]
        # FIXME ensure types from left and rest are compatible with the operator
        self.subst.unify_types(bool, node.type, at=get_loc(node))
        return node

    def visit_ifExpr(self, node):
        node.body = self.visit(node.body)
        node.orelse = self.visit(node.orelse)
        node.test = self.visit(node.test)
        self.subst.unify_types(bool, node.test.type)
        self.subst.unify_types(node.body.type, node.orelse.type, at=get_loc(node.body))
        self.subst.unify_types(node.type, node.body.type, at=get_loc(node))
        return node

    def visit_getAttr(self, node):
        node.value = self.visit(node.value)
        # FIXME
        # self.subst.unify_types(with_attr_type(node.value.name, node.value.type), node.type)

        raise NotImplementedError("Type of attribute")
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
                self.subst.unify_types(target.type, node.value.type, at=get_loc(node.value))
                self.subst.unify_types(node.type, target.type, at=get_loc(node))
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
            make_function_type(res.returns,
                               *(e.type for e in res.args)),
            at=get_loc(res),
        )

        self.current_function_return.pop()
        return res

    def visit_return(self, node):
        if node.value:
            node.value = self.visit(node.value)
            self.subst.unify_types(node.value.type, self.current_function_return[-1], at=get_loc(node.value))
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
            at=get_loc(node.func),
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

        assert var, "You cannot resolve None."

        while isinstance(var, TypeVar):
            prev = var
            var = self.vars[var.name]

        return var or prev

    def unify_types(self, type_a, type_b, at=None):
        """Unify type_a and type_b or raise a WormTypeError
        """

        ta, tb = self.resolve(type_a), self.resolve(type_b)
        if isinstance(ta, TypeVar):
            self.vars[ta.name] = tb
        elif isinstance(tb, TypeVar):
            self.unify_types(tb, ta, at=at)
        elif is_atom_type(ta) and is_atom_type(tb):
            if ta != tb:
                raise WormTypeError("Could not unify these types", ta, tb, at=at)
        elif isinstance(ta, FunctionType) and isinstance(tb, FunctionType):
            self.unify_types(ta.ret_type, tb.ret_type, at=at)
            for a, b in zip(ta.args_types, tb.args_types):
                # FIXME consider different number of parameters
                # FIXME consider function polymorphism
                self.unify_types(a, b, at=at)
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


def get_binary_op_type(op):
    # FIXME Actually implement that
    return make_function_type(int, int, int)


def get_unary_op_type(op):
    # FIXME Actually implement that
    return make_function_type(int, int)


def get_loc(node):
    return node.src_pos
