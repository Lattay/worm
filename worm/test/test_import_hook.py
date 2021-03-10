import ast

from ..import_hook import create_hook, remove_hook


class FractionWrapper(ast.NodeTransformer):
    """Wraps all integers in a call to Integer()"""

    def visit_Module(self, node):
        node.body.insert(
            0,
            ast.ImportFrom(
                module="fractions",
                names=[ast.alias(name="Fraction")],
                level=0,
            ),
        )
        for b in node.body:
            self.generic_visit(b)
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, int):
            return ast.Call(
                func=ast.Name(id="Fraction", ctx=ast.Load()), args=[node], keywords=[]
            )
        return node


def transform_ast(tree):
    """Transforms the Abstract Syntax Tree"""
    print("transform")
    tree = FractionWrapper().visit(tree)
    ast.fix_missing_locations(tree)
    return tree


def add_hook():
    """Creates and automatically adds the import hook in sys.meta_path"""
    hook = create_hook(
        extensions=[".frac"],
        hook_name=__name__,
        transform_ast=transform_ast,
    )
    return hook


def test_fractions():
    k = add_hook()
    from .addition import result

    assert result, f"Simple fraction {result}"

    remove_hook(k)


if __name__ == '__main__':
    test_fractions()
