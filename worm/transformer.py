from functools import wraps, reduce
from .errors import WormSyntaxError
from .import_hook import create_hook
import ast
from ast import (
    alias,
    arguments,
    Assign,
    Attribute,
    Call,
    Constant,
    Dict,
    Expr,
    ImportFrom,
    keyword,
    Lambda,
    List,
    Load,
    Name,
    Store,
    Tuple,
)


_op_names = {
    ast.UAdd: "+",
    ast.USub: "-",
    ast.Not: "not",
    ast.Invert: "~",
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitXor: "^",
    ast.BitAnd: "&",
    ast.MatMult: "@",
    ast.And: "and",
    ast.Or: "or",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}


prelude = [
    ImportFrom(module="worm", names=[alias(name="magics", asname="_w")], level=0),
]


def hook(debug=False):
    return create_hook(
        extensions=[".wm"],
        hook_name="worm",
        transform_ast=transform_ast,
        debug=debug,
    )


def transform_ast(node):
    tree = RewriteTopLevel().visit(node)
    return ast.fix_missing_locations(tree)


class RewriteTopLevel(ast.NodeTransformer):
    def visit_Module(self, node):
        if len(node.body) > 0 and is_docstring(node.body[0]):
            docstring, *body = node.body
            node.body = [docstring, *prelude, *map(self.visit, node.body)]
        else:
            node.body = prelude + list(map(self.visit, node.body))
        return node

    def visit_FunctionDef(self, node):
        if node.decorator_list:
            decorated_func = RewriteWorm().visit(node)
            lambda_func = make_lambda(decorated_func)
            decorators = make_list(
                node.decorator_list[0], map(make_lambda, node.decorator_list)
            )
            apply = make_apply_decorator(decorators, lambda_func)
            node.decorator_list = [apply]
        if len(node.body) > 0 and is_docstring(node.body[0]):
            docstring, *body = node.body
            node.body = [docstring, *map(self.visit, body)]
        else:
            node.body = list(map(self.visit, node.body))
        return node

    def visit_ClassDef(self, node):
        if node.decorator_list:
            decorated_func = RewriteWorm().visit(node)
            lambda_func = make_lambda(decorated_func)
            decorators = make_list(
                node.decorator_list[0], map(make_lambda, node.decorator_list)
            )
            apply = make_apply_decorator(decorators, lambda_func)
            node.decorator_list = [apply]
        if len(node.body) > 0 and is_docstring(node.body[0]):
            docstring, *body = node.body
            node.body = [docstring, *map(self.visit, body)]
        else:
            node.body = list(map(self.visit, node.body))
        return node


def wrap_last(prop):
    @wraps(prop)
    def wrapper(self, *args, **kwargs):
        if not self._entered:
            self._entered = True
            first_call = True
        else:
            first_call = False
        res = prop(self, *args, **kwargs)
        if first_call:
            return self.last_thing(res)
        else:
            return res

    return wrapper


class RewriteWorm(ast.NodeTransformer):
    def __init__(self):
        self.state = []
        self._entered = False

    def visit_Expr(self, node):
        return make_node(node, "exprStatement", values=[self.visit(node.value)])

    def visit_Constant(self, node):
        return make_node(node, "constant", values=[node])

    def visit_List(self, node):
        if isinstance(node.ctx, Load):
            return make_node(node, "list", values=map(self.visit, node.elts))
        elif len(node.elts) == 1:
            return self.visit(node.elts[0])
        else:
            raise NotImplementedError()

    def visit_Tuple(self, node):
        if isinstance(node.ctx, Load):
            return make_node(node, "tuple", values=map(self.visit, node.elts))
        elif len(node.elts) == 1:
            return self.visit(node.elts[0])
        else:
            raise NotImplementedError()

    def visit_Set(self, node):
        pass

    def visit_Dict(self, node):
        if any(not isinstance(key, Name) for key in node.keys):
            raise WormSyntaxError(
                "Struct literals takes only symbols as keys.", at=node.src_pos
            )

        return make_node(
            node,
            "struct",
            values=[
                copy_loc(node, Tuple([self.visit(key), self.visit(val)], ctx=Load()))
                for key, val in zip(node.keys, node.values)
            ],
        )

    def visit_Name(self, node):
        if isinstance(node.ctx, Store):
            return make_node(
                node, "storeName", values=[copy_loc(node, Constant(value=node.id))]
            )
        else:
            return make_node(
                node, "name", values=[copy_loc(node, Constant(value=node.id))]
            )

    def visit_Starred(self, node):
        raise WormSyntaxError(
            "splat operator is not supported in Worm.", at=get_loc(node)
        )

    def visit_UnaryOp(self, node):
        return make_node(
            node, "unary", values=[op_table(node.op), self.visit(node.operand)]
        )

    def visit_BinOp(self, node):
        return make_node(
            node,
            "binary",
            values=[
                op_table(node.op),
                self.visit(node.left),
                self.visit(node.right),
            ],
        )

    def visit_BoolOp(self, node):
        return make_node(
            node,
            "boolOp",
            values=[op_table(node.op), *map(self.visit, node.values)],
        )

    def visit_Compare(self, node):
        return make_node(
            node,
            "compare",
            values=[
                self.visit(node.left),
                *(
                    copy_loc(
                        node, Tuple(elts=[op_table(op), self.visit(val)], ctx=Load())
                    )
                    for op, val in zip(node.ops, node.comparators)
                ),
            ],
        )

    def visit_Call(self, node):
        if is_unquoting(node.func):
            if isinstance(node.func, Name) and node.func.id == "_x":
                n = node.func
                node.func = copy_loc(
                    n,
                    Attribute(
                        # FIXME that shit will explode
                        value=copy_loc(n, Name(id="worm", ctx=Load())),
                        attr="expand",
                        ctx=Load(),
                    ),
                )

                tr = RewriteTopLevel()
                node.args = list(map(tr.visit, node.args))

                for kw in node.keywords:
                    kw.value = self.visit(kw.value)

            else:
                raise NotImplementedError()
            return node
        else:
            return make_node(
                node,
                "call",
                values=[
                    self.visit(node.func),
                    copy_loc(
                        node, List(elts=list(map(self.visit, node.args)), ctx=Load())
                    ),
                    copy_loc(
                        node,
                        Dict(
                            keys=[Constant(k.arg) for k in node.keywords],
                            values=[self.visit(k.value) for k in node.keywords],
                        ),
                    ),
                ],
            )

    def visit_IfExp(self, node):
        return make_node(
            node,
            "ifexpr",
            values=[
                self.visit(node.test),
                self.visit(node.body),
                self.visit(node.orelse),
            ],
        )

    def visit_Attribute(self, node):
        if isinstance(node.ctx, Load):
            return make_node(
                node,
                "getAttr",
                values=[
                    self.visit(node.value),
                    Constant(node.attr),
                ],
            )
        elif isinstance(node.ctx, Store):
            return make_node(
                node,
                "setAttr",
                values=[
                    self.visit(node.value),
                    Constant(node.attr),
                ],
            )
        else:
            raise NotImplementedError()

    def visit_NamedExpr(self, node):
        raise NotImplementedError()

    def visit_SubScript(self, node):
        if isinstance(node.ctx, Load):
            return make_node(
                node,
                "getItem",
                values=[
                    self.visit(node.value),
                    self.visit(node.slice),
                ],
            )
        elif isinstance(node.ctx, Store):
            return make_node(
                node,
                "setItem",
                values=[
                    self.visit(node.value),
                    self.visit(node.slice),
                ],
            )
        else:
            raise NotImplementedError()

    def visit_Slice(self, node):
        return make_node(
            node,
            "slice",
            values=[
                self.visit(node.lower),
                self.visit(node.upper),
                self.visit(node.step),
            ],
        )

    def visit_Assign(self, node):
        return make_node(
            node,
            "assign",
            values=[
                copy_loc(
                    node, List(elts=list(map(self.visit, node.targets)), ctx=Load())
                ),
                self.visit(node.value),
            ],
        )

    def visit_AnnAssign(self, node):
        return make_node(
            node,
            "assign",
            values=[
                copy_loc(node.target, List(elts=[self.visit(node.target)], ctx=Load())),
                self.visit(node.value),
                self.visit(node.annotation or copy_loc(node, Constant(None))),
            ],
        )

    def visit_AugAssign(self, node):
        target = self.visit(node.target)
        return make_node(
            node,
            "assign",
            values=[
                copy_loc(target, List(elts=[target], ctx=Load())),
                make_node(
                    node,
                    "binary",
                    values=[
                        op_table(node.op),
                        target,
                        self.visit(node.value),
                    ],
                ),
            ],
        )

    def visit_Raise(self, node):
        return make_node(
            node,
            "raise",
            values=[
                self.visit(node.exc),
                self.visit(node.cause),
            ],
        )

    def visit_Assert(self, node):
        return make_node(
            node,
            "assert",
            values=[
                self.visit(node.test),
                self.visit(node.message),
            ],
        )

    def visit_Delete(self, node):
        return make_node(node, "del", values=map(self.visit, node.targets))

    def visit_Pass(self, node):
        return make_node(node, "pass")

    def visit_Import(self, node):
        raise WormSyntaxError(
            "import are not valid inside Worm code, use them at Python level only.",
            at=get_loc(node),
        )

    def visit_ImportFrom(self, node):
        raise WormSyntaxError(
            "import are not valid inside Worm code, use them at Python level only.",
            at=get_loc(node),
        )

    def visit_If(self, node):
        return make_node(
            node,
            "if",
            values=[
                self.visit(node.test),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, node.body)), ctx=Load()),
                        )
                    ],
                ),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, node.orelse)), ctx=Load()),
                        )
                    ],
                ),
            ],
        )

    def visit_For(self, node):
        return make_node(
            node,
            "for",
            values=[
                self.visit(node.target),
                self.visit(node.iter),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, node.body)), ctx=Load()),
                        )
                    ],
                ),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, node.orelse)), ctx=Load()),
                        )
                    ],
                ),
            ],
        )

    def visit_While(self, node):
        return make_node(
            node,
            "while",
            values=[
                self.visit(node.test),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, node.body)), ctx=Load()),
                        )
                    ],
                ),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, node.orelse)), ctx=Load()),
                        )
                    ],
                ),
            ],
        )

    def visit_Break(self, node):
        return make_node(node, "break")

    def visit_Continue(self, node):
        return make_node(node, "continue")

    def visit_Try(self, node):
        raise NotImplementedError()

    def visit_FunctionDef(self, node):
        if node.args.posonlyargs:
            raise WormSyntaxError(
                "Worm does not support positional only arguments.", at=get_loc(node)
            )

        if node.args.kwonlyargs:
            raise WormSyntaxError(
                "Worm does not support keyword only arguments.", at=get_loc(node)
            )

        args = copy_loc(
            node, List(elts=list(map(self.visit_arg, node.args.args)), ctx=Load())
        )
        defaults = copy_loc(
            node, List(elts=list(map(self.visit, node.args.defaults)), ctx=Load())
        )

        if len(node.body) > 0 and is_docstring(node.body[0]):
            d, *body = node.body
            docstring = d.value
        else:
            docstring = Constant(None)
            body = node.body

        func = make_node(
            node,
            "funcDef",
            values=[
                copy_loc(node, Constant(node.name)),
                args,
                defaults,
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, body)), ctx=Load()),
                        )
                    ],
                ),
                node.returns or copy_loc(node, Constant(None)),
                docstring,
            ],
        )

        return reduce(compose_dec, reversed(node.decorator_list), func)

    def visit_arg(self, node):
        annot = self.visit(node.annotation or copy_loc(node, Constant(None)))
        return make_node(
            node, "arg", values=[copy_loc(node, Constant(node.arg)), annot]
        )

    def visit_Return(self, node):
        return make_node(
            node,
            "return",
            values=[self.visit(node.value) if node.value else Constant(None)],
        )

    def visit_ClassDef(self, node):
        if node.keywords:
            raise WormSyntaxError(
                "Worm does not support keywords in class definition.", at=get_loc(node)
            )

        if len(node.body) > 0 and is_docstring(node.body[0]):
            d, *body = node.body
            docstring = d.value
        else:
            docstring = Constant(None)
            body = node.body

        class_ = make_node(
            node,
            "class",
            values=[
                copy_loc(node, Constant(node.name)),
                copy_loc(
                    node, List(elts=list(map(self.visit, node.bases)), ctx=Load())
                ),
                make_node(
                    node,
                    "block",
                    values=[
                        copy_loc(
                            node,
                            List(elts=list(map(self.visit, body)), ctx=Load()),
                        )
                    ],
                ),
                docstring,
            ],
        )

        return reduce(compose_dec, reversed(node.decorator_list), class_)


def make_node(node, name, values=[]):
    """
    Return a Call node to produce a Worm AST node at python runtime.
    """
    return copy_loc(
        node,
        Call(
            func=copy_loc(node, from_w("W" + name[0].upper() + name[1:])),
            args=list(values),
            keywords=[
                keyword(
                    arg="src_pos",
                    value=copy_loc(
                        node,
                        List(
                            list(
                                map(
                                    Constant,
                                    get_loc(node),
                                )
                            ),
                            ctx=Load(),
                        ),
                    ),
                )
            ],
        ),
    )


class WormEscape(Expr):
    pass


def compose_dec(func, decorator):
    """
    Return a Call node which allow decorator (python code) to be called on func
    where func is a Worm AST node representing a function.
    """
    return copy_loc(
        decorator,
        Call(
            func=decorator,
            args=[func],
            keywords=[],
        ),
    )


def copy_loc(src, dest):
    dest.lineno = src.lineno
    dest.col_offset = src.col_offset
    dest.end_lineno = src.end_lineno
    dest.end_col_offset = src.end_col_offset
    return dest


def get_loc(node):
    return [
        node.lineno,
        node.col_offset,
        node.end_lineno,
        node.end_col_offset,
    ]


def make_assign(target, value):
    """
    Return an assign node to assign value to target.
    """
    return copy_loc(
        value,
        Assign(
            targets=[target],
            value=value,
        ),
    )


def make_lambda(expr):
    """
    Take an expression and return a thunk node evaluating to that expression
    """
    return copy_loc(
        expr,
        Lambda(
            args=arguments(
                posonlyargs=[],
                args=[],
                varargs=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=expr,
        ),
    )


def make_list(ref, gen):
    """
    Take some sort of iterable and produce a List node
    """
    return copy_loc(ref, List(elts=list(gen), ctx=Load()))


def make_apply_decorator(decorators, func):
    return copy_loc(
        func,
        Call(
            func=copy_loc(func, from_w("worm_decorator_wrapper")),
            args=[decorators, func],
            keywords=[],
        ),
    )


def from_w(name, store=False):
    return Attribute(
        value=Name(id="_w", ctx=Load()),
        attr=name,
        ctx=Store() if store else Load(),
    )


_op_table = {k: Constant(o) for k, o in _op_names.items()}


def op_table(op):
    return _op_table[op.__class__]


def is_docstring(node):
    "Return True if the node is a str constant."
    return (
        isinstance(node, Expr)
        and isinstance(node.value, Constant)
        and isinstance(node.value.value, str)
    )


def is_unquoting(*args):
    return False
