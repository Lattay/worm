from ..transformer import hook

hook(debug=False)


def test_hygienic():
    from .hygienic import prog, __doc__

    assert __doc__ == prog.dump_source()


def test_fib():
    from .fib import prog, __doc__

    assert __doc__ == prog.dump_source()


def test_type_check():
    from .typed import prog, __doc__

    assert __doc__ == prog.dump_source()


# def test_custom_type():
#     from .. import worm
#     # prevent inter test pollution
#     worm.setup_fresh_state()
#
#     from .custom_type import prog, __doc__
#
#     assert __doc__ == prog.dump_source()


# def test_quote():
#     from .quote import prog, __doc__
#     assert prog.dump_source() == __doc__


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
