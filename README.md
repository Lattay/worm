# The Worm language

## About

Worm is a system programming language embedded in and meta-programmed by Python.
The Worm compiler is a pure Python program that uses `ast` and `importlib` module to plug into the python compilation process and produce C sources.

It uses the same grammar and syntax as python with a slightly different semantic.

Basically Worm is like C with a powerful language instead of a macro system.

## Ideas and principles

Worm is built around the idea to be totally implemented in Python and totally relying on its parser.
Hence, the syntax is the python syntax.
However, the semantic can be different.

- `import` statements as well as `with` statements are not permitted in Worm code, indeed the module system of Worm is
  resolved as compile time and directly use the Python import system
- Python have literal sets and dictionaries, Worm use dictionaries syntax for anonymous structs and
  does not use set syntax

## Current state

The Worm compiler is a very early project in exploratory phase.
Basically nothing is stable and a lot is not working or not implemented.
You can check out the [TODO list](TODO.md) to know where the project is and where it goes.

## Caveats

Worm decorators are recognized by name (`worm.decorator`) because the parser needs to recognize them before Python affected any meaning to the object, which means the user cannot do the following:
```
prog2 = WormContext()
@prog2.entry
def f():
    return 2
```

The previous snippet will raise an error because the `WormContext` instance needs `WFuncDef` instances to be passed to `entry` but the `transformer` did not know that `prog2.entry` is actually a Worm decorator.
