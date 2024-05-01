import re
from pathlib import Path
from lark import Lark, Transformer
import csv
import pprint


class SchemaError(Exception):
    def __init__(self, message):
        print(message)


class CSVS_Parser:
    def __init__(self, csvs_file):
        self._valid_version = ["1.0", "1.1", "1.2"]
        with open(csvs_file) as csvs_text:
            self._schema_text = self._strip_comments(csvs_text.read())
        print(self._schema_text)
        self._version = self._get_version()
        print(f"CSVS version {self._version}")
        lark_file_version = Path()
        if self._version == "1.0":
            lark_file_version = Path("data/csvs_1.0.lark")
        elif self._version == "1.1":
            lark_file_version = Path("data/csvs_1.1.lark")
        elif self._version == "1.2":
            lark_file_version = Path("data/csvs_1.2.lark")

        with open(lark_file_version) as lark_file:
            lark_text = lark_file.read()
        self._csvs_parser = Lark(lark_text, start="start", lexer="dynamic")
        # print(self._csvs_parser.parse(self._schema_text).pretty())
        self._tree = self._csvs_parser.parse(self._schema_text)

    def _strip_comments(self, schema):
        # Block comments, everything between "/*" and "*/"
        schema = re.sub(r"/\*.*?\*/", "", schema, flags=re.S)
        # Line comments, everything after "//"
        # Note, in order to not capture http://foo.bar
        # There must be a space or newline before the "//"
        # No s-flag so it stops at the end of the line or file
        schema = re.sub(r"(?:\s|^)(\/\/(.*))", "", schema)
        # replace 3 or more spaces/newlines with one newline to
        # trim the white space for readability
        schema = re.sub(r"[\n\r\s]{3,}", "\n", schema, flags=re.M)
        return schema

    def _get_version(self):
        first_line = self._schema_text.strip().split("\n")[0]
        version = first_line.split(' ')
        if version[0] != "version" or len(version) != 2:
            raise SchemaError("Invalid version declaration")
        if version[1] not in self._valid_version:
            raise SchemaError(f"Invalid version: {version[1]}")
        else:
            return version[1]

    @property
    def tree(self):
        return self._tree


class CSVS_Transformer(Transformer):
    def __init__(self):
        self._rules = {
            "@global_directives": {
                "separator": ',',
                "quoted": False,
                "header": True,
            }
        }

    def ident(self, id):
        (id,) = id
        return id

    def wilcard_literal(self, wc):
        (wc,) = wc
        return wc

    def string_literal(self, sl):
        (sl,) = sl
        return sl[1:-1]

    def character_literal(self, cl):
        (cl, ) = cl
        return cl[1:-1]

    def numeric_literal(self, nl):
        (nl,) = nl
        return float(nl)

    def positive_integer_literal(self, pi):
        (pi,) = pi
        return int(pi)

    def positive_non_zero_integer_literal(self, pnz):
        (pnz,) = pnz
        return pnz

    def directive_prefix(self, dp):
        return dp

    # TODO: DATES!

    # Globals
    def separator_directive(self, tree):
        (_, tree) = tree
        separator = tree
        print("Separator:", separator)
        self._rules["@global_directives"]["separator"] = tree
        return tree

    def separator_tab_expr(self, tree):
        return "TAB"

    def separator_char(self, sc):
        (sc,) = sc
        return sc

    def total_columns_directive(self, tree):
        (_, tree) = tree
        print("Total Columns: ", tree)
        self._rules["@global_directives"]["total_columns"] = int(tree.value)
        return tree

    def quoted_directive(self, tree):
        self._rules["@global_directives"]["quoted"] = True

    def no_header_directive(self, tree):
        self._rules["@global_directives"]["header"] = False

    # Columns

    def single_expr(self, tree):
        if len(tree) == 1:
            (tree, ) = tree
        else:
            (tree, _) = tree
        return tree

    def explicit_context_expr(self, tree):
        (tree,) = tree
        return tree

    def combinatorial_expr(self, tree):
        return tree[0]

    def non_combinatorial_expr(self, tree):
        (tree, ) = tree
        return tree

    def non_conditional_expr(self, tree):
        (tree, ) = tree
        return tree

    def column_validation_expr(self, tree):
        (tree, ) = tree
        return tree

    def or_expr(self, tree):
        (or1, or2) = tree

        def or_validator(value):
            return or1(value) or or2(value)
        return or_validator

    def and_expr(self, tree):
        def and_validator(value):
            return tree[0](value) and tree[1](value)
        return and_validator

    def is_expr(self, tree):
        def is_validator(value):
            return value == tree[0].children[0]
        return is_validator

    def not_expr(self, tree):
        def not_validator(value):
            return tree[0].children[0] != value
        return not_validator

    def positive_integer_or_any_expr(self, tree):
        def pos_or_any_validator(value):
            if value == "*":
                return True
            else:
                return float(value) == int(value) and value > 0
        return pos_or_any_validator

    def range_expr(self, tree):
        min_val = float(tree[0])
        max_val = float(tree[1])

        def range_validator(value):
            try:
                x = float(value)
            except ValueError:
                return False
            return min_val <= x <= max_val
        return range_validator

    def column_definition(self, tree):
        (column, rules) = tree
        self._rules[column.value] = rules
        return column

    def column_rule(self, tree):
        return tree[0]

    def column_identifier(self, tree):
        (tree, ) = tree
        return tree

    def quoted_column_identifier(self, tree):
        (tree, ) = tree
        return tree

    def empty_expr(self, _):
        return lambda x: not bool(x)

    def not_empty_expr(self, _):
        return lambda x: bool(x)

    def uuid4_expr(self, _):
        def uuid4_validator(value):
            regex = re.compile(r"^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}$", re.I)
            match = regex.match(value.strip())
            return bool(match)
        return uuid4_validator

    def positive_integer_expr(self, _):
        def positive_integer_validator(value):
            return float(value) == int(value) and value > 0
        return positive_integer_validator

    @property
    def rules(self):
        return self._rules


if __name__ == "__main__":
    parser = CSVS_Parser("example1.csvs")
    transformer = CSVS_Transformer()

    print("--------- PARSED ---------")
    transformer.transform(parser.tree)
    pprint.pprint(transformer.rules)
    print(transformer.rules['name']("something"))  # True
    print(transformer.rules['name'](""))  # False
    print(transformer.rules['age']("23"))  # True
    print(transformer.rules['age']("ds"))  # False
    print(transformer.rules['age']("123"))  # False
    print(transformer.rules['gender']('m'))  # True
    print(transformer.rules['gender']('?'))  # False
