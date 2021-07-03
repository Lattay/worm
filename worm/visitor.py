from .wast import (
    WTopLevel,
    WExprStatement,
    WBlock,
    WAst,
    WArray,
    WTuple,
    WStruct,
    WUnary,
    WPtr,
    WDeref,
    WBinary,
    WBoolOp,
    WCompare,
    WCall,
    WIfExpr,
    WGetAttr,
    WSetAttr,
    WGetItem,
    WSetItem,
    WSlice,
    WAssign,
    WRaise,
    WAssert,
    WDel,
    WIf,
    WFor,
    WWhile,
    WFuncDef,
    WArg,
    WClass,
    WReturn,
)


class WormVisitor:
    def visit(self, node):
        if node is None:
            return None
        assert isinstance(node, WAst)
        classname = node.__class__.__name__
        return getattr(self, "visit_" + reformat(classname))(node)

    def visit_topLevel(self, node):
        return WTopLevel(
            entry=self.visit(node.entry),
            functions={name: self.visit(f) for name, f in node.functions.items()},
            headers=node.headers,
        ).copy_common(node)

    def visit_constant(self, node):
        return node

    def visit_array(self, node):
        return WArray(*map(self.visit, node.elements)).copy_common(node)

    def visit_tuple(self, node):
        return WTuple(*map(self.visit, node.elements)).copy_common(node)

    def visit_struct(self, node):
        return WStruct(
            *((name, self.visit(val)) for name, val in node.fields)
        ).copy_common(node)

    def visit_name(self, node):
        return node

    def visit_storeName(self, node):
        return node

    def visit_unary(self, node):
        return WUnary(node.op, self.visit(node.operand)).copy_common(node)

    def visit_ptr(self, node):
        return WPtr(node.value).copy_common(node)

    def visit_deref(self, node):
        return WDeref(node.value).copy_common(node)

    def visit_binary(self, node):
        return WBinary(node.op, *map(self.visit, (node.left, node.right))).copy_common(
            node
        )

    def visit_boolOp(self, node):
        return WBoolOp(node.op, *map(self.visit, node.values)).copy_common(node)

    def visit_compare(self, node):
        rest = ((op, self.visit(val)) for op, val in node.rest)
        return WCompare(self.visit(node.left), *rest).copy_common(node)

    def visit_exprStatement(self, node):
        return WExprStatement(self.visit(node.value)).copy_common(node)

    def visit_block(self, node):
        return WBlock(map(self.visit, node.statements)).copy_common(node)

    def visit_call(self, node):
        return WCall(
            self.visit(node.func),
            map(self.visit, node.args),
            {arg: self.visit(val) for arg, val in node.kwargs.items()},
        ).copy_common(node)

    def visit_ifExpr(self, node):
        return WIfExpr(
            *map(self.visit, (node.test, node.body, node.orelse))
        ).copy_common(node)

    def visit_getAttr(self, node):
        return WGetAttr(self.visit(node.value), node.attr).copy_common(node)

    def visit_setAttr(self, node):
        return WSetAttr(self.visit(node.value), node.attr).copy_common(node)

    def visit_getItem(self, node):
        return WGetItem(*map(self.visit, (node.value, node.slice_))).copy_common(node)

    def visit_setItem(self, node):
        return WSetItem(*map(self.visit, (node.value, node.slice_))).copy_common(node)

    def visit_slice(self, node):
        return WSlice(
            *map(self.visit, (node.lower, node.upper, node.step))
        ).copy_common(node)

    def visit_assign(self, node):
        return WAssign(
            map(self.visit, node.targets),
            self.visit(node.value),
        ).copy_common(node)

    def visit_raise(self, node):
        return WRaise(self.visit(node.value)).copy_common(node)

    def visit_assert(self, node):
        return WAssert(*map(self.visit, (node.test, node.message))).copy_common(node)

    def visit_del(self, node):
        return WDel(self.visit(node.value)).copy_common(node)

    def visit_if(self, node):
        return WIf(*map(self.visit, (node.test, node.body, node.orelse))).copy_common(
            node
        )

    def visit_for(self, node):
        return WFor(
            *map(
                self.visit,
                (node.target, node.iter, node.body, node.orelse),
            )
        ).copy_common(node)

    def visit_while(self, node):
        return WWhile(
            *map(
                self.visit,
                (node.test, node.body, node.orelse),
            )
        ).copy_common(node)

    def visit_pass(self, node):
        return node

    def visit_continue(self, node):
        return node

    def visit_break(self, node):
        return node

    def visit_funcDef(self, node):
        return WFuncDef(
            node.name,
            map(self.visit, node.args),
            map(self.visit, node.defaults),
            self.visit(node.body),
            node.returns,
        ).copy_common(node)

    def visit_arg(self, node):
        return node

    def visit_class(self, node):
        return WClass(
            node.name,
            node.bases,
            self.visit(node.body),
        ).copy_common(node)

    def visit_return(self, node):
        return WReturn(self.visit(node.value)).copy_common(node)


def reformat(name):
    assert name.startswith("W")
    return name[1].lower() + name[2:]
