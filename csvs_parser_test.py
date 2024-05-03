import pytest
from csvs_parser import CSVS_Transformer


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
    def validator1(x):
        return x % 2 == 0

    def validator2(x):
        return x % 3 == 0

    or_validator = transformer.or_expr((validator1, validator2))

    assert or_validator(2)
    assert or_validator(3)
    assert or_validator(6)
    assert not or_validator(5)


def test_and_expr(transformer):
    def validator1(x):
        return x % 2 == 0

    def validator2(x):
        return x % 3 == 0

    and_validator = transformer.and_expr((validator1, validator2))

    assert and_validator(6)
    assert not and_validator(2)
    assert not and_validator(3)
    assert not and_validator(5)


def test_is_expr(transformer):
    comparison_value = ("test",)
    is_validator = transformer.is_expr(comparison_value)

    assert is_validator("test")
    assert not is_validator(23)


def test_not_expr(transformer):
    comparison_value = ("test",)
    not_validator = transformer.not_expr(comparison_value)

    assert not_validator("Spain")
    assert not not_validator("test")


def test_positive_integer_or_any_expr(transformer):
    pos_or_any = transformer.positive_integer_or_any_expr()

    assert pos_or_any('1')
    assert pos_or_any(2)
    assert pos_or_any(0)
    assert pos_or_any('*')
    assert not pos_or_any(-1)
    assert not pos_or_any('bad')


def test_range_expr(transformer):
    range_validator_1 = transformer.range_expr(("1", 7.0))
    range_validator_2 = transformer.range_expr(("-1", "-32"))

    assert range_validator_1(3)
    assert range_validator_1("6.4")
    assert not range_validator_1(120)
    assert not range_validator_1("five")

    assert range_validator_2(-4)
    assert not range_validator_2(10)
