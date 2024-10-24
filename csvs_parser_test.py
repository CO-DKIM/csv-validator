import pytest
from csvs_parser import CSVS_Transformer, StringLiteral


# Define a fixture for the transformer instance
@pytest.fixture
def transformer():
    return CSVS_Transformer()


def test_ident(transformer):
    assert transformer.ident(("hello",)) == "hello"
    assert transformer.ident(("\"hello\"",)) == "\"hello\""
    assert transformer.ident((1,)) == 1
    assert transformer.ident(('n',)) != "N"


def test_wildcard_literal(transformer):
    assert transformer.wildcard_literal(("*",)) == "*"
    assert transformer.wildcard_literal(("NOTHING",)) == "*"


def test_or_expr(transformer):
    def validator1(x, _y, _z):
        return x % 2 == 0

    def validator2(x, _y, _z):
        return x % 3 == 0

    or_validator = transformer.or_expr((validator1, validator2))

    row = []
    colmap = {}

    assert or_validator(2, row, colmap)
    assert or_validator(3, row, colmap)
    assert or_validator(6, row, colmap)
    assert not or_validator(5, row, colmap)


def test_and_expr(transformer):
    def validator1(x, _y, _z):
        return x % 2 == 0

    def validator2(x, _y, _z):
        return x % 3 == 0

    and_validator = transformer.and_expr((validator1, validator2))

    assert and_validator(6, [], {})
    assert not and_validator(2, [], {})
    assert not and_validator(3, [], {})
    assert not and_validator(5, [], {})


def test_is_expr(transformer):
    comparison_value = (StringLiteral("test"),)
    is_validator = transformer.is_expr(comparison_value)

    assert is_validator("test", [], {})
    assert not is_validator(23, [], {})


def test_in_expr(transformer):
    comparison_value = (StringLiteral("this is a test string"),)
    in_validator = transformer.in_expr(comparison_value)

    assert in_validator("test", [], {})
    assert not in_validator(23, [], {})
    assert not in_validator("nothing to see here", [], {})


def test_not_expr(transformer):
    comparison_value = (StringLiteral("test"),)
    not_validator = transformer.not_expr(comparison_value)

    assert not_validator("Spain", [], {})
    assert not not_validator("test", [], {})


def test_range_expr(transformer):
    range_validator_1 = transformer.range_expr(("1", 7.0))
    range_validator_2 = transformer.range_expr(("-1", "-32"))

    assert range_validator_1(3, [], {})
    assert range_validator_1("6.4", [], {})
    assert not range_validator_1(120, [], {})
    assert not range_validator_1("five", [], {})

    assert range_validator_2(-4, [], {})
    assert not range_validator_2(10, [], {})


def test_length_expr(transformer):
    length_validator_1 = transformer.length_expr(5)
    length_validator_2 = transformer.length_expr((2, 10))
    length_validator_3 = transformer.length_expr((2, '*'))
    length_validator_4 = transformer.length_expr(('*', 10))

    assert length_validator_1("words", [], {})
    assert not length_validator_1("this is a test and is too long", [], {})
    assert not length_validator_1("x", [], {})

    assert length_validator_2("word", [], {})
    assert not length_validator_2("this is a test and is too long", [], {})
    assert not length_validator_2("x", [], {})

    assert length_validator_3("word", [], {})
    assert length_validator_3("this is a test and is too long", [], {})
    assert not length_validator_3("x", [], {})

    assert length_validator_4("word", [], {})
    assert not length_validator_4("this is a test and is too long", [], {})
    assert length_validator_4("x", [], {})


def test_empty_expr(transformer):
    empty_validator = transformer.empty_expr(())
    assert empty_validator("", [], {})
    assert not empty_validator("X", [], {})


def test_not_empty_expr(transformer):
    not_empty_validator = transformer.not_empty_expr(())
    assert not not_empty_validator("", [], {})
    assert not_empty_validator("X", [], {})


def test_uri_expr(transformer):
    uri_validator = transformer.uri_expr(())
    assert uri_validator("http://data.gov.uk/some_asset", [], {})
    assert not uri_validator("http://data.gov.uk/spaces should be escaped", [], {})


def test_if_expr(transformer):
    comparison_value = (StringLiteral("test"),)
    is_validator = transformer.is_expr(comparison_value)
    if_validator = transformer.if_expr(())
    assert if_validator([(StringLiteral("test"), is_validator(StringLiteral("test"), [], {})), True], [], {})
    assert if_validator([(StringLiteral("test"), is_validator(StringLiteral("test"), [], {})), False], [], {})
