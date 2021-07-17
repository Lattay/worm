from ..transformer import hook

hook(debug=False)


from .decl import prog, __doc__

print(prog.dump_source())
