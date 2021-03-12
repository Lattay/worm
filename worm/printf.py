from typing import Union, Tuple
from dataclasses import dataclass


def parse_format(string):
    elements = []
    i = 0
    n = len(string)
    last = 0
    while i < n:
        if string[i] == "%":
            elements.append(string[last:i])
            slot, last = parse_slot(string, i)
            elements.append(slot)
            i = last
        else:
            i += 1

    actual_params = []
    for p in elements:
        if isinstance(p, Slot):
            if p.prec and p.prec[0] == "arg":
                if p.prec[1] > 0:
                    raise NotImplementedError(
                        "I don't even understand what this is supposed to do..."
                    )
                else:
                    actual_params.append("d")
            actual_params.append(p)

    return elements, actual_params


def parse_slot(string, start):
    n = len(string)
    assert string[start] == "%"
    if start + 1 >= n:
        raise FormatError("Incomplete format specifier.")
    elif string[start + 1] == "%":
        return "%", start + 2
    else:
        try:
            flag, after = parse_flags(string, start + 1)
            minwidth, after = parse_minwidth(string, after)
            prec, after = parse_prec(string, after)
            lenmod, after = parse_lenmod(string, after)
        except IndexError as e:  # if end of string is reached, there is a problem in the format
            raise FormatError(f'Unexpected end of format "{string[start:]}".') from e

        spec, after = parse_spec(string, after)
        if not spec:
            raise FormatError(f"Invalid format string: {string[start:after]}")
        return Slot(spec, flag, minwidth, prec, lenmod), after


def parse_flags(string, start):
    flags = set()
    i = start
    while string[i] in {"-", "#", "0", "I", " ", "+", "'"}:
        flags.add(string[i])
        i += 1
    return flags or None, i


def parse_minwidth(string, start):
    i = start
    while string[i].isdecimal():
        i += 1

    if i > start:
        return int(string[start:i]), i
    else:
        return None, i


def parse_prec(string, start):
    if string[start] == ".":
        if string[start + 1] == "*":
            if string[start + 2].isdecimal():
                start_dec = start + 2
                i = start_dec
                while string[i].isdecimal():
                    i += 1

                if string[i] != "$":
                    raise FormatError("Invalid precision format.")

                return ("arg", int(string[start_dec:i])), i + 1
            else:
                return ("arg", -1), start + 2
        else:
            start_dec = start + 1
            i = start_dec
            while string[i].isdecimal():
                i += 1
            return ("lit", int(string[start_dec:i])), i
    else:
        return None, start


def parse_lenmod(string, start):
    if string[start] in {"h", "L", "t", "z", "l", "j"}:
        if string[start + 1] == string[start] and string[start] in {"h", "l"}:
            return string[start : start + 2], start + 2
        else:
            return string[start : start + 1], start + 1
    else:
        return None, start


def parse_spec(string, start):
    if string[start] == "%":
        return "%", start + 1
    elif string[start] in {
        "E",
        "i",
        "o",
        "F",
        "u",
        "A",
        "e",
        "X",
        "a",
        "n",
        "G",
        "d",
        "p",
        "f",
        "g",
        "s",
        "x",
        "c",
    }:
        return string[start], start + 1
    else:
        return None, start + 1


class FormatError(Exception):
    pass


@dataclass
class Slot:
    spec: str
    flag: Union[str]
    minwidth: Union[int, None]
    prec: Union[Tuple[str, int], None]
    lenmod: Union[str, None]
