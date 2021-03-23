from functools import reduce
from contextlib import contextmanager

from .errors import WormBindingError, WormTypeError
from .visitor import WormVisitor
from .wast import (
    WTopLevel,
    WBlock,
    WName,
    WStoreName,
    WFuncDef,
    WClass,
    WArg,
    WAssign,
    WExpr,
)
from .prelude import prelude
from .wtypes import to_c_type, void, WormType, Array
from .type_checker import ResolveTypes, AnnotateSymbols, PropagateAndCheckTypes


class Program:
    def __init__(self, entry_point, functions, exported):
        self.entry_point = entry_point
        self.functions = functions
        self.exported = exported

    @classmethod
    def from_context(cls, context):
        functions = context.functions
        entry_point = context.entry_point

        exported = set()

        for f in functions:
            if f.name in context.exported:
                exported.add(f)

        return cls(entry_point, functions, exported)

    def dump_source(self):
        headers = ["#include <stdio.h>", "#include <stdlib.h>", "#include <stdint.h>"]

        scope = {**prelude}

        pipeline = [
            Unsugar(),
            Renaming(scope),
            ResolveTypes(scope),
            ValidateMain(),
            AnnotateSymbols(scope),
            PropagateAndCheckTypes(scope),
            MakeCSource(),
        ]

        def transform(node):
            return reduce(lambda n, t: t.visit(n), pipeline, node)


        top_level = WTopLevel(
            entry=self.entry_point, functions=self.functions, headers=headers, exported=self.exported
        )

        return transform(top_level)

    def save_source(self, file):
        if isinstance(file, str):
            with open(file, "w") as f:
                f.write(self.dump_source())
        else:
            file.write(self.dump_source())

    def save_program(self, filename):
        pass

    def save_library(self, filename):
        pass


class Unsugar(WormVisitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scope = [{}]

    def lookup(self, name):
        for frame in reversed(self.scope):
            if name in frame:
                return frame[name]
        return None

    def visit_funcDef(self, node):
        self.scope.append(node.attached)

        return super().visit_funcDef(node)

    def visit_exprStatement(self, node):
        val = super().visit(node.value)
        if isinstance(val, WExpr):
            node.value = val
            return node
        else:
            # have been expanded into a non-expr
            return val

    def visit_call(self, node):
        if isinstance(node.func, WName):
            bind = self.lookup(node.func.name)
            if bind:
                if getattr(bind, "_wrapped_block", False):
                    return bind(*node.args, **node.kwargs)
                elif getattr(bind, "_primitive", False):
                    return bind(super().visit_call(node))
        return super().visit_call(node)


class Renaming(WormVisitor):
    """
    This visitor rename variables to use a unique symbol for each variable in the program.
    """

    def __init__(self, prelude, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._counter = 0
        # FIXME Add the outer scope
        self.scope = [[extract_name_from_scope(prelude)]]
        self.symbols = set()
        self.globals = {}

    # internals
    # def get_name(self, base):
    #     known_name = self.in_scope(base)
    #     if known_name is None:
    #         known_name = self.add_to_scope(base)
    #     return known_name

    def in_local_scope(self, base):
        """
        Return the replacement identifier in the local major frame or None.
        """
        for frame in reversed(self.scope[-1]):
            if base in frame:
                return frame[base]
        return None

    def in_scope(self, base):
        """
        Return the replacement identifier in any major frame or None.
        """
        for major in reversed(self.scope):
            for frame in reversed(major):
                if base in frame:
                    return frame[base]
        return None

    def add_to_scope(self, base, new_name=None):
        frame = self.scope[-1][-1]
        if new_name is None:
            self._counter += 1
            frame[base] = f"v{self._counter}_{base}"
        else:
            frame[base] = new_name

        self.symbols.add(frame[base])
        return frame[base]

    @contextmanager
    def major_frame(self):
        self.scope.append([{}])
        yield
        self.scope.pop()

    @contextmanager
    def minor_frame(self):
        self.scope[-1].append({})
        yield
        self.scope[-1].pop()

    # Visitors
    def visit_topLevel(self, node):

        self.stop_at_proto = True  # first just pass collect the function names
        functions = list(map(self.visit, node.functions))
        self.stop_at_proto = False
        functions = list(map(self.visit, functions))

        if node.entry:
            node.entry.name = "__main"

            entry = self.visit(node.entry)
        else:
            entry = None

        top_level = WTopLevel(
            entry=entry,
            functions=functions,
            headers=node.headers,
        ).copy_common(node)

        top_level.symbols = self.symbols
        return top_level

    def visit_funcDef(self, node):
        if self.stop_at_proto:
            assert node.name != "__main"
            node.name = self.add_to_scope(node.name)
            return node

        if node.name == "__main":
            name = "main"
        else:
            name = node.name

        with self.major_frame():
            defaults = list(map(self.visit, node.defaults))

            with self.minor_frame():
                args = [
                    WArg(self.add_to_scope(arg.name), arg.type).copy_common(arg)
                    for arg in node.args
                ]

                return WFuncDef(
                    name, args, defaults, self.visit(node.body), node.returns
                ).copy_common(node)

    def visit_block(self, node):
        if node.hygienic:
            new_frame = self.major_frame
        else:
            new_frame = self.minor_frame
        with new_frame():
            prelude = []
            for local_name, ext_val in node.injected.items():
                if isinstance(ext_val, WName):
                    name = self.in_scope(ext_val.name)
                    if not name:
                        raise WormBindingError(
                            f"Injected name {ext_val.name} is unbound.", at=node.src_pos
                        )
                    self.add_to_scope(local_name, name)
                elif isinstance(ext_val, WExpr):
                    prelude.append(WAssign([WStoreName(local_name)], ext_val))

            return WBlock(map(self.visit, prelude + node.statements)).copy_common(node)

    def visit_class(self, node):
        with self.major_frame():
            name = self.add_to_scope(node.name)
            bases = list(map(self.visit, node.bases))
            with self.minor_frame():
                return WClass(name, bases, self.visit(node.body)).copy_common(node)

    def visit_name(self, node):
        renamed = self.in_scope(node.name)
        if not renamed:
            raise WormBindingError(
                f"Unbound symbol {node.name}. {self.scope}", at=node.src_pos
            )
        return WName(renamed).copy_common(node)

    def visit_storeName(self, node):
        local_name = self.in_local_scope(node.name)
        if local_name:  # set a local variable
            renamed = local_name
            declaration = False
        else:  # create a new variable, eventually shadowing an external one
            renamed = self.add_to_scope(node.name)
            declaration = True
        n = WStoreName(renamed).copy_common(node)
        n.declaration = declaration
        return n


class ValidateMain(WormVisitor):
    def visit_topLevel(self, node):
        if node.entry is not None:
            if node.entry.returns.deref() is None:
                node.entry.returns = void
                self.returns = void
            else:
                self.returns = int
                node.entry.returns = int
            self.visit(node.entry.body)

        return node

    def visit_return(self, node):
        if self.returns.deref() == void:
            if node.value is not None:
                raise WormTypeError(
                    "The entry point has a non void return.", at=node.src_pos
                )
        elif node.value.type.deref() != int:
            raise WormTypeError(
                "The entry point has a non int return.", at=node.src_pos
            )


class CollectRequiredSymbols(WormVisitor):
    def __init__(self):
        self.required = {}

    def visit_topLevel(self, node):
        functions = {f.name: f for f in node.functions}
        types = {t.id: t for t in node.types}
        if node.entry is not None:
            self.visit(node.entry)
        else:
            for f in node.exported:
                self.required[f.name] = f
                self.visit(f)
        diff = set(self.required.keys())
        while diff:
            prev = set(self.required.keys())
            for symbol, val in diff.items():
                if isinstance(val, WAst):
                    self.visit(val)

            diff = prev.difference(self.required.keys())

        node.required = self.required

        return node

    # FIXME collecter les symboles sans mettre des trucs locaux dans required
    # Probleme: Renaming sert justement à ne plus avoir besoin de connaitre le scope des
    # symboles alors comment faire le tri dans cette passe ?

class MakeCSource(WormVisitor):
    def visit_topLevel(self, node):
        code = node.headers

        for k, t in node.required.items():
            if isinstance(t, WormType) and t.is_declared():
                code.append(t.declaration(to_c_type))

        for k, f in node.required.items():
            if isinstance(f, WFuncDef):
                proto = f.prototype
                arg_list = ", ".join(to_c_type(type.deref()) for type in proto["args"])
                code.append(to_c_type(proto["return"]) + f' {proto["name"]}({arg_list});')

        if node.entry is not None:
            code.append(self.visit(node.entry))

        for f in node.functions:
            code.append(self.visit(f))

        return "\n".join(code)

    def visit_constant(self, node):
        if isinstance(node.value, str):
            return "\"" + repr(node.value)[1:-1] + "\""
        else:
            return repr(node.value)

    def visit_array(self, node):
        return Array(node.elements.type.deref()).value_to_c(
            list(map(self.visit, node.elements))
        )

    def visit_tuple(self, node):
        raise NotImplementedError()

    def visit_struct(self, node):
        return (
            f"({to_c_type(node.type.deref())}){{"
            + ", ".join(f".{self.visit(name)}={self.visit(val)}" for name, val in node.fields)
            + "}"
        )

    def visit_name(self, node):
        return node.name

    def visit_unary(self, node):
        return f"{node.op}{self.visit(node.operand)}"

    def visit_ptr(self, node):
        return f"*({self.visit(node.value)})"

    def visit_binary(self, node):
        a, b = self.visit(node.left), self.visit(node.right)

        if node.op == "**":
            raise NotImplementedError()
        return f"({a} {node.op} {b})"

    def visit_boolOp(self, node):
        if node.op == "and":
            op = " && "
        else:
            op = " || "

        return "(" + op.join(node.values) + ")"

    def visit_compare(self, node):
        left = self.visit(node.left)
        operations = []
        for op, operand in node.rest:
            operand_ = self.visit(operand)
            operations.append(f"({left} {op} {operand_})")

        return "(" + " && ".join(operations) + ")"

    def visit_exprStatement(self, node):
        return self.visit(node.value) + ";"

    def visit_block(self, node):
        return "\n".join(map(self.visit, node.statements))

    def visit_call(self, node):
        if not isinstance(node.func, WName):
            raise NotImplementedError()

        arg_list = ", ".join(map(self.visit, node.args))

        return f"{node.func.name}({arg_list})"

    def visit_ifExpr(self, node):
        test = self.visit(node.test)
        body = self.visit(node.body)
        orelse = self.visit(node.body)
        return f"({test}?{body}:{orelse})"

    def visit_getAttr(self, node):
        # FIXME probably too rigid, may need some participation of the type
        return f"{self.visit(node.value)}.{node.attr}"

    def visit_setAttr(self, node):
        raise NotImplementedError()

    def visit_getItem(self, node):
        raise NotImplementedError()

    def visit_setItem(self, node):
        raise NotImplementedError()

    def visit_slice(self, node):
        raise NotImplementedError()

    def visit_assign(self, node):
        if len(node.targets) > 1:
            raise NotImplementedError()
        target = node.targets[0]
        if not isinstance(target, WStoreName):
            raise NotImplementedError(target)

        expr = self.visit(node.value)

        if target.declaration:
            return f"{to_c_type(node.type.deref())} {target.name} = {expr};"
        else:
            return f"{target.name} = {expr};"

    def visit_raise(self, node):
        raise NotImplementedError()

    def visit_assert(self, node):
        raise NotImplementedError()

    def visit_del(self, node):
        raise NotImplementedError()

    def visit_pass(self, node):
        return ""

    def visit_if(self, node):
        test = self.visit(node.test)
        body = self.visit(node.body)
        orelse = self.visit(node.orelse)
        return f"if({test}){{\n{body}\n}} else {{\n{orelse}\n}}"

    def visit_for(self, node):
        raise NotImplementedError()

    def visit_while(self, node):
        test = self.visit(node.test)
        body = self.visit(node.body)
        # FIXME (gotta implement break first I guess)
        # orelse = '\n'.join(map(self.visit, node.orelse))
        return f"while({test}){{\n{body}\n}}"

    def visit_continue(self, node):
        raise NotImplementedError()

    def visit_funcDef(self, node):
        prelude = []
        for name, value in node.attached.items():
            # FIXME attached is weird, it represent both values put in scope and types and is used at different moments
            if isinstance(value, (int, bool, float, str)):
                t = to_c_type(type(value))
                prelude.append(f"{t} {name} = {repr(value)};")
            elif isinstance(value, (WormType, type(lambda: 0))):
                pass  # we probably don't need that
            else:
                continue
                # FIXME there is really to many things, we may need to split attached into two separate things again
                raise NotImplementedError(f"We got a {name}={value} in attached values of {node.name}")
        body = self.visit(node.body)
        returns = to_c_type(node.returns.deref())
        args = [f"{to_c_type(arg.type.deref())} {arg.name}" for arg in node.args]
        arg_list = ", ".join(args)
        head = f"{returns} {node.name}({arg_list}){{"
        return "\n".join(prelude + [head, body, "}"])

    def visit_class(self, node):
        pass

    def visit_return(self, node):
        value = self.visit(node.value)
        return f"return {value};"


def extract_name_from_scope(scope):
    return {name: name for name in scope}
