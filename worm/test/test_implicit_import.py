from ast import (
    NodeTransformer,
    ImportFrom,
    alias,
)
from ..import_hook import create_hook


import_math = ImportFrom(
    module="math",
    names=[alias(name="*")],
    level=0,
)


class RewriteAst(NodeTransformer):
    def visit_Module(self, node):
        node.body = [import_math] + [self.generic_visit(n) for n in node.body]
        return node


def transform_ast(node):
    return RewriteAst().visit(node)


def test_trigo():
    create_hook(
        extensions=[".tr"],
        hook_name="trigo",
        transform_ast=transform_ast,
    )

    from .trigo import result

    assert result, "Implicit imports"


if __name__ == "__main__":
    test_trigo()
