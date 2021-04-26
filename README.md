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

Worm is highly experimental and I am not sure yet of what it should be.
It probably don't work very well right now, but I hope to find time and motivation to change that.