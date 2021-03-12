from ..transformer import hook

hook(debug=False)


def test_hygienic():
    from .hygienic import worm, __doc__

    assert worm.dump_source() == __doc__


def test_type_check():
    from .typed import worm, __doc__

    assert worm.dump_source() == __doc__


def test_custom_type():
    from .custom_type import worm, __doc__

    assert worm.dump_source() == __doc__


# def test_quote():
#     from .quote import worm, __doc__
#     assert worm.dump_source() == __doc__


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
