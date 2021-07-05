from functools import reduce
from contextlib import contextmanager

from .errors import WormBindingError

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
from .wtypes import to_c_type

from .type_checker import AnnotateWithTypes, ValidateMain, UnifyTypes, FlattenTypes, IntroduceSymbolTypes


class Program:
    def __init__(self, entry_point, functions, exported):
        self.entry_point = entry_point
        self.functions = functions
        self.exported = exported

    @classmethod
    def from_context(cls, context):
        return cls(context.entry_point, context.functions, context.exported)

    def dump_source(self):
        headers = ["#include <stdio.h>", "#include <stdlib.h>", "#include <stdint.h>"]

        scope = {**prelude}

        pipeline = [
            Unsugar(),
            Renaming(),
            CollectRequiredSymbols(),
            InjectExternalSymbols(scope),
            IntroduceSymbolTypes(),
            ValidateMain(),
            AnnotateWithTypes(),
            UnifyTypes(),
            FlattenTypes(),
            CollectRequiredTypes(),
            MakeCSource(scope),
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


class InjectExternalSymbols:
    def __init__(self, scope):
        self.scope = scope

    def visit(self, top_level):
        for name in top_level.required:
            if name in top_level.functions:
                self.scope[name] = top_level.functions[name].type

        missing = set(top_level.required.keys()).difference(self.scope.keys())
        if missing:
            raise WormBindingError(f"Unbound symbol(s) {missing}")
        else:
            top_level.type_table = {
                name: self.scope[name] for name, symbol in top_level.required.items()
            }
        return top_level


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

    # FIXME This visitor should also collect free variables from functions
    # to create the list of required symbols
    # Also self.symbols is useless now, maybe there is a way of killing two birds
    # with one stone

    def __init__(self):
        self._counter = 0
        self.scope = []
        self.current_function = []
        self.symbols = set()

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
            if base not in self.symbols:
                frame[base] = base
            else:
                counter = 2
                n = f"{base}_{counter}"
                while n in self.symbols:
                    counter += 1
                    n = f"{base}_{counter}"
                frame[base] = n
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
        if node.entry:
            node.entry.name = "__main"
            entry = self.visit(node.entry)
        else:
            entry = None

        top_level = WTopLevel(
            entry=entry,
            functions={name: self.visit(f) for name, f in node.functions.items()},
            headers=node.headers,
        ).copy_common(node)

        # top_level.symbols = self.symbols
        return top_level

    def visit_funcDef(self, node):
        if node.name == "__main":
            name = "main"
        else:
            name = node.name

        self.current_function.append(node)

        with self.major_frame():
            defaults = list(map(self.visit, node.defaults))

            with self.minor_frame():
                self.add_to_scope(name)
                args = [
                    WArg(self.add_to_scope(arg.name), arg.type).copy_common(arg)
                    for arg in node.args
                ]

                final = WFuncDef(
                    name, args, defaults, self.visit(node.body), node.returns
                )

        self.current_function.pop()

        return final.copy_common(node)

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
                        self.current_function[-1].free_vars.add(ext_val.name)
                        name = ext_val.name
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
            self.current_function[-1].free_vars.add(node.name)
            return node
        else:
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


class CollectRequiredTypes(WormVisitor):
    def __init__(self):
        self.types = set()
        self.subst = None

    def visit(self, node):
        if node is None:
            return None
        if self.subst:
            self.types.add(self.subst.resolve(node.type))
        return super().visit(node)

    def visit_topLevel(self, node):
        self.subst = node.subst
        new_top = super().visit_topLevel(node)
        new_top.types = self.types
        return new_top


class CollectRequiredSymbols(WormVisitor):
    def __init__(self):
        self.required = {}

    def visit_topLevel(self, node):
        if node.entry:
            diff = node.entry.free_vars
        else:
            diff = node.exported

        other = set()

        while diff:
            added = {}
            req = set()
            for name in diff:
                if name in node.functions:
                    added[name] = node.functions[name]
                    req.update(node.functions[name].free_vars)
                else:
                    other.add(name)

            self.required.update(added)
            diff = req.difference(self.required.keys())

        self.required.update({name: None for name in other})

        node.required = self.required

        return node


class MakeCSource(WormVisitor):
    def __init__(self, prelude):
        self.prelude = prelude
        self.functions = {}

    def visit_topLevel(self, node):
        code = node.headers

        print("Required types")
        for t in node.types:
            print(t)
            # code.append(t.declaration(to_c_type))

        print("Required symbols")
        for k, f in node.required.items():
            if isinstance(f, WFuncDef):
                proto = f.prototype
                arg_list = ", ".join(to_c_type(type) for type in proto["args"])
                code.append(to_c_type(proto["return"]) + f' {proto["name"]}({arg_list});')
            else:
                print(k, f)

        if node.entry is not None:
            code.append(self.visit(node.entry))

        for name, f in node.functions.items():
            code.append(self.visit(f))

        return "\n".join(code)

    def visit_constant(self, node):
        if isinstance(node.value, str):
            return "\"" + repr(node.value)[1:-1] + "\""
        else:
            return repr(node.value)

    def visit_array(self, node):
        return node.type.value_to_c(
            list(map(self.visit, node.elements))
        )

    def visit_tuple(self, node):
        raise NotImplementedError()

    def visit_struct(self, node):
        return (
            f"({to_c_type(node.type)}){{"
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
            return f"{to_c_type(node.type)} {target.name} = {expr};"
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
        body = self.visit(node.body)
        returns = to_c_type(node.returns)
        args = [f"{to_c_type(arg.type)} {arg.name}" for arg in node.args]
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
