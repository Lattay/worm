from ..transformer import hook

hook(debug=False)


def test_hygienic():
    from .. import worm
    # prevent inter test pollution
    worm.setup_fresh_state()

    from .hygienic import worm, __doc__

    assert __doc__ == worm.dump_source()


def test_fib():
    from .. import worm
    # prevent inter test pollution
    worm.setup_fresh_state()

    from .fib import worm, __doc__

    assert __doc__ == worm.dump_source()


# def test_type_check():
#     from .. import worm
#     # prevent inter test pollution
#     worm.setup_fresh_state()
#
#     from .typed import worm, __doc__
#
#     assert __doc__ == worm.dump_source()


# def test_custom_type():
#     from .. import worm
#     # prevent inter test pollution
#     worm.setup_fresh_state()
#
#     from .custom_type import worm, __doc__
#
#     assert __doc__ == worm.dump_source()


# def test_quote():
#     from .quote import worm, __doc__
#     assert worm.dump_source() == __doc__


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
