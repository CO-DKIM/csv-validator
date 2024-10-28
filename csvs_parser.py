import re
from pathlib import Path
from urllib.parse import unquote, urlparse
from lark import Lark, Transformer
from external_validators import file_checksum

# This parser is for CSVS version 1.0
VERSION = 1.0


class StringLiteral:
    # Just so we can treat all string provider types the same
    def __init__(self, value):
        self._value = value
        self.row = []
        self.colmap = 0

    def __repr__(self):
        return self._value

    def resolve(self):
        return self._value


class ColumnReference:
    def __init__(self, column_name: str):
        self._column_name = column_name
        self._row = []
        self._colmap = 0

    def __repr__(self):
        return f"${self._column_name} {self._row} {self._colmap}"

    @property
    def column_name(self):
        return self._column_name

    @property
    def row(self):
        return self._row

    @row.setter
    def row(self, row_value: list):
        self._row = row_value

    @property
    def colmap(self):
        return self._colmap

    @colmap.setter
    def colmap(self, colmap_value):
        self._colmap = colmap_value

    def resolve(self):
        index = self._colmap[self._column_name]
        return self._row[index]


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
        self.column_counter = 0
        self._rules = {
            "@global_directives": {
                "separator": ',',
                "quoted": False,
                "header": True,
                "ignoreColumnCase": False
            }
        }

    # TODO: This is v1.0 so lets make 3!

    # start: prolog body // 1

    # prolog: version_decl global_directives // 2

    # version_decl: "version 1.0" // 3
    def version_decl(self, vd):
        (vd,) = vd
        if vd != 1.0:
            raise SchemaError("Incorrect version of CSVS.")
        self._rules["@global_directives"]["version"] = vd
        return vd

    # global_directives: ( separator_directive | quoted_directive |
    # total_columns_directive | no_header_directive |
    # ignore_column_name_case_directive )* // 4
    def global_directives(self, gd):
        return gd

    # directive_prefix: "@" // 5
    def directive_prefix(self, dp):
        return dp

    # separator_directive: directive_prefix "separator"
    # ( separator_tab_expr | separator_char ) // 6
    def separator_directive(self, tree):
        (_, tree) = tree
        self._rules["@global_directives"]["separator"] = tree
        return tree

    # separator_tab_expr: "TAB" | "\\t" // 7
    def separator_tab_expr(self, tree):
        return "\t"

    # separator_char: character_literal // 8
    def separator_char(self, sc):
        (sc,) = sc
        return sc

    # quoted_directive: directive_prefix "quoted" // 9
    def quoted_directive(self, tree):
        self._rules["@global_directives"]["quoted"] = True

    # total_columns_directive: directive_prefix "totalColumns"
    # positive_non_zero_integer_literal// 10
    def total_columns_directive(self, tree):
        (_, tree) = tree
        print("Total Columns: ", tree)
        self._rules["@global_directives"]["total_columns"] = int(tree.value)
        return tree

    # no_header_directive: directive_prefix "noHeader" // 11
    def no_header_directive(self, tree):
        self._rules["@global_directives"]["header"] = False

    # ignore_column_name_case_directive: directive_prefix
    # "ignoreColumnNameCase" // 12
    def ignore_column_name_case_directives(self, tree):
        self._rules["@global_directives"]["ignoreColumnCase"] = True

    # body: body_part+ // 13

    # body_part: column_definition // 14

    # column_definition: (column_identifier |
    # quoted_column_identifier) ":" column_rule // 18
    def column_definition(self, tree):
        (column, rules) = tree
        col_num = self.column_counter
        self.column_counter += 1
        self._rules[col_num] = {
            "name": column.value
        }
        self._rules[col_num]["directives"] = rules[-1]
        self._rules[col_num]["functions"] = rules[0:-1]
        return column

    # column_identifier: positive_non_zero_integer_literal |
    # ident // 19
    def column_identifier(self, tree):
        (tree, ) = tree
        return tree

    # quoted_column_identifier: string_literal // 20
    def quoted_column_identifier(self, tree):
        (tree, ) = tree
        tree = tree.resolve()
        return tree

    # column_rule: column_validation_expr* column_directives // 21
    def column_rule(self, tree):
        return tree

    # column_directives: ( optional_directive | match_is_false_directive |
    # ignore_case_directive | warning_directive )* // 22
    def column_directives(self, tree):
        directives = {
            "optional": False,
            "matchIsFalse": False,
            "ignoreCase": False,
            "warning": False,
            }
        for directive in tree:
            directives[directive] = True
        return directives

    # optional_directive: directive_prefix "optional" // 23
    def optional_directive(self, tree):
        return "optional"

    # match_is_false_directive: directive_prefix "matchIsFalse" // 24
    def match_is_false_directive(self, tree):
        return "matchIsFalse"

    # ignore_case_directive: directive_prefix "ignoreCase" // 25
    def ignore_case_directive(self, tree):
        return "ignoreCase"

    # warning_directive: directive_prefix ("warning"|"warningDirective") // 26
    # in some example 1.0  warningDirective is used
    def warning_directive(self, tree):
        return "warning"

    # column_validation_expr: combinatorial_expr | non_combinatorial_expr // 27
    def column_validation_expr(self, tree):
        (tree, ) = tree
        return tree

    # combinatorial_expr: or_expr | and_expr // 28
    def combinatorial_expr(self, tree):
        return tree[0]

    # or_expr: non_combinatorial_expr "or" column_validation_expr // 29
    def or_expr(self, tree):
        (or1, or2) = tree

        def or_validator(value, row, colmap):
            return or1(value, row, colmap) or or2(value, row, colmap)
        return or_validator

    # and_expr: non_combinatorial_expr "and" column_validation_expr // 30
    def and_expr(self, tree):
        (and1, and2) = tree

        def and_validator(value, row, colmap):
            return and1(value, row, colmap) and and2(value, row, colmap)
        return and_validator

    # non_combinatorial_expr: non_conditional_expr | conditional_expr // 31
    def non_combinatorial_expr(self, tree):
        # print("NCE: ", tree)
        (tree, ) = tree
        # print(tree)
        return tree

    # non_conditional_expr: single_expr |
    # external_single_expr | parenthesized_expr // 32
    def non_conditional_expr(self, tree):
        (tree, ) = tree
        print(tree)
        return tree

    # single_expr: explicit_context_expr? ( is_expr | not_expr |
    # in_expr | starts_with_expr | ends_with_expr | reg_exp_expr |
    # range_expr | length_expr | empty_expr | not_empty_expr |
    # unique_expr | uri_expr | xsd_date_time_expr | xsd_date_expr |
    # xsd_time_expr | uk_date_expr | date_expr| partial_uk_date_expr |
    # partial_date_expr | uuid4_expr | positive_integer_expr ) // 33
    def single_expr(self, tree):
        if len(tree) == 1:
            (expr, ) = tree
            return expr
        else:
            (context, expr) = tree

            def contextual_validator(value, row, colmap):
                # Set the context for the column reference
                context.row = row
                context.colmap = colmap
                context_value = context.resolve()
                return expr(context_value, row, colmap)
            return contextual_validator

    # explicit_context_expr: column_ref "/" // 34
    def explicit_context_expr(self, tree):
        (column_reference,) = tree
        return column_reference

    # column_ref: "$" ( column_identifier | quoted_column_identifier ) // 35
    def column_ref(self, tree):
        (tree,) = tree
        col_ref = ColumnReference(tree)
        return col_ref

    # is_expr: "is(" string_provider ")" // 36
    def is_expr(self, tree):
        (string_provider,) = tree

        def is_validator(value, row, colmap):
            if isinstance(string_provider, ColumnReference):
                string_provider.row = row
                string_provider.colmap = colmap
            return value == string_provider.resolve()
        return is_validator

    # not_expr: "not(" string_provider ")" // 37
    def not_expr(self, tree):
        (tree,) = tree

        def not_validator(value, row, colmap):
            tree.row = row
            tree.colmap = colmap
            return value != tree.resolve()
        return not_validator

    # in_expr: "in(" string_provider ")" // 38
    def in_expr(self, tree):
        (tree, ) = tree

        def in_validator(value, row, colmap):
            tree.row = row
            tree.colmap = colmap
            try:
                return value in tree.resolve()
            except TypeError:
                return False
        return in_validator

    # starts_with_expr: "starts(" string_provider ")" // 39
    def starts_with_expr(self, tree):
        (string_provider, ) = tree

        def starts_with_validator(value, row, colmap):
            # Strip the white space if there is any
            if isinstance(string_provider, ColumnReference):
                string_provider.row = row
                string_provider.colmap = colmap
            target = string_provider.resolve()
            return value.startswith(target)
        return starts_with_validator

    # ends_with_expr: "ends(" string_provider ")" // 40
    def ends_with_expr(self, tree):
        (tree, ) = tree

        def ends_with_validator(value, row, colmap):
            tree.row = row
            tree.colmap = colmap
            ends_with_value = tree.resolve()
            value = value.strip()
            return ends_with_value == value[-len(ends_with_value):]
        return ends_with_validator

    # reg_exp_expr: "regex(" string_literal ")" // 41
    def reg_exp_expr(self, tree):
        (regex, ) = tree

        def regex_validator(value, _row, _colmap):
            match_re = re.compile(r"^" + regex.resolve() + "$")
            if re.match(match_re, value):
                return True
            else:
                return False
        return regex_validator

    # range_expr: "range(" numeric_literal "," numeric_literal ")" // 42
    def range_expr(self, tree):
        # Parser will only allow numbers
        min_val = min([float(tree[0]), float(tree[1])])
        max_val = max([float(tree[0]), float(tree[1])])

        def range_validator(value, _row, _colmap):
            try:
                x = float(value)
            except ValueError:
                return False
            return min_val <= x <= max_val
        return range_validator

    # length_expr: "length(" ( positive_integer_or_any ",")?
    # positive_integer_or_any ")" // 43
    def length_expr(self, tree):
        if type(tree) is int:
            def length_validator(value, _row, _colmap):
                return len(value) == tree
        else:
            if tree[1] == '*':
                def length_validator(value, _row, _colmap):
                    return tree[0] <= len(value)
            elif tree[0] == '*':
                def length_validator(value, _row, _colmap):
                    return len(value) <= tree[1]
            else:
                def length_validator(value, _row, _colmap):
                    return tree[0] <= len(value) <= tree[1]
        return length_validator

    # positive_integer_or_any: positive_integer_literal |
    # wildcard_literal // 44
    def positive_integer_or_any(self, tree):
        (tree, ) = tree
        return tree

    # empty_expr: "empty" // 45
    def empty_expr(self, _):
        return lambda x, _y, _z: not bool(x)

    # not_empty_expr: "notEmpty" // 46
    def not_empty_expr(self, _x):
        return lambda x, _y, _z: bool(x)

    # unique_expr: "unique" ("("
    #   column_ref ("," column_ref)* ")")? // 47

    # uri_expr: "uri" // 48
    def uri_expr(self, _):
        def uri_validator(value, _row, _colmap):
            from rfc3986_validator import validate_rfc3986
            return validate_rfc3986(value)
        return uri_validator

    # xsd_date_time_expr: "xDateTime" ("(" xsd_date_time_literal ","
    #   xsd_date_time_literal ")")? // 49

    # xsd_date_expr: "xDate" ("(" xsd_date_literal "," xsd_date_literal ")")?
    # // 50

    # xsd_time_expr: "xTime" ( "(" xsd_time_literal "," xsd_time_literal ")")?
    # // 51

    # uk_date_expr: "ukDate" ("(" uk_date_literal "," uk_date_literal ")")
    # // 52

    # date_expr: "date(" string_provider "," string_provider ","
    # string_provider ("," xsd_date_literal "," xsd_date_literal)? ")" // 53

    # partial_uk_date_expr: "partUkDate" // 54

    # partial_date_expr: "partDate("
    # string_provider "," string_provider "," string_provider ")" // 55

    # uuid4_expr: "uuid4" // 56
    def uuid4_expr(self, _):
        def uuid4_validator(value, _row, _colmap):
            regex = re.compile(
                r"^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab]"
                r"[a-f0-9]{3}-?[a-f0-9]{12}$", re.I
            )
            match = regex.match(value.strip())
            return bool(match)
        return uuid4_validator

    # positive_integer_expr: "positiveInteger" // 57
    def positive_integer_expr(self, _):
        def positive_integer_validator(value, _row, _colmap):
            return float(value) == int(value) and int(value) > 0
        return positive_integer_validator

    # string_provider: column_ref | string_literal // 58
    def string_provider(self, sp):
        (sp,) = sp
        return sp

    # external_single_expr: explicit_context_expr? (file_exists_expr |
    # checksum_expr | file_count_expr) // 59
    def external_single_expr(self, tree):
        (tree,) = tree
        return tree

    # file_exists_expr: "fileExists" ("(" string_provider ")")? // 60
    def file_exists_expr(self, tree):
        if len(tree) == 0:

            def file_exists_validator(path_provider, row, colmap):
                if isinstance(path_provider, ColumnReference):
                    path_provider.row = row
                    path_provider.colmap = colmap
                    path_str = path_provider.resolve()
                else:
                    path_str = path_provider
                # Decode it form a uri
                path_str = unquote(urlparse(path_str).path)
                return Path(path_str).exists()
        else:
            base_provider, = tree

            def file_exists_validator(path_provider, row, colmap):
                if isinstance(base_provider, ColumnReference):
                    base_provider.row = row
                    base_provider.colmap = colmap
                    base = base_provider.resolve()
                else:
                    base = base_provider
                if isinstance(path_provider, ColumnReference):
                    path_provider.row = row
                    path_provider.colmap = colmap
                    file_path = path_provider.resolve()
                else:
                    file_path = path_provider
                file_path = str(base) + str(file_path)
                file_path = unquote(urlparse(file_path).path)

                path_str = Path(file_path)
                print("PATH EXISTS:", path_str)
                return path_str.exists()
        return file_exists_validator

    # checksum_expr: "checksum(" file_expr "," string_literal ")" // 61
    def checksum_expr(self, tree):
        file_expr, checksum_type = tree

        def checksum_validator(value, row, colmap):
            if isinstance(checksum_type, ColumnReference):
                checksum_type.row = row
                checksum_type.colmap = colmap
                checksum_lib = checksum_type.resolve()
            elif isinstance(checksum_type, StringLiteral):
                checksum_lib = checksum_type.resolve()
            else:
                checksum_lib = checksum_type

            return value == file_checksum(file_expr(value, row, colmap), checksum_lib)

        return checksum_validator

    # file_expr: "file(" (string_provider "," )? string_provider ")" // 62
    def file_expr(self, tree):
        if len(tree) == 1:
            # Single argument form: file(path)
            (path_provider,) = tree

            def resolve_path(value, row, colmap):
                if isinstance(path_provider, ColumnReference):
                    path_provider.row = row
                    path_provider.colmap = colmap
                    path_str = path_provider.resolve()
                else:
                    path_str = path_provider
                return Path(unquote(urlparse(path_str).path))

        else:
            # 2 argument form: file(base, path)
            base_provider, path_provider = tree

            def resolve_path(value, row, colmap):
                if isinstance(base_provider, ColumnReference):
                    base_provider.row = row
                    base_provider.colmap = colmap
                    base = base_provider.resolve()
                else:
                    base = base_provider
                if isinstance(path_provider, ColumnReference):
                    path_provider.row = row
                    path_provider.colmap = colmap
                    file_path = path_provider.resolve()
                else:
                    file_path = path_provider
                file_path = str(base) + str(file_path)
                file_path = unquote(urlparse(file_path).path)
                return Path(file_path)

        return resolve_path

    # file_count_expr: "fileCount(" file_expr ")" // 63

    # parenthesized_expr: "(" column_validation_expr+ ")" // 64
    def parenthesized_expr(self, tree):
        (tree,) = tree
        return tree

    # conditional_expr: if_expr // 65
    def conditional_expr(self, tree):
        (tree,) = tree
        return tree

    # if_expr: "if(" ( combinatorial_expr | non_conditional_expr ) ","
    #    column_validation_expr+ ("," column_validation_expr+)? ")" // 66
    def if_expr(self, tree):
        print("IF", tree)

        if len(tree) == 3:
            def if_validator(value, row, colmap):
                context = tree[0]
                (comparator, condition) = context
                comparator.row = row
                comparator.colmap = colmap
                comparator = comparator.resolve()
                if condition(comparator, row, colmap):
                    return tree[1](value, row, colmap)
                else:
                    return tree[2](value, row, colmap)
        else:
            def if_validator(value, row, colmap):
                context = tree[0]
                (comparator, condition) = context
                comparator.row = row
                comparator.colmap = colmap
                comparator = comparator.resolve()
                if condition(comparator, row, colmap):
                    return tree[1](value, row, colmap)
                else:
                    return True
        return if_validator

    # xsd_date_time_literal: xsd_date_without_timezone_component "T"
    #     xsd_time_literal // 67

    # xsd_date_literal: xsd_date_without_timezone_component
    #    xsd_timezone_component // 68

    # xsd_time_literal: xsd_time_without_timezone_component
    #    xsd_timezone_component // 69

    # xsd_date_without_timezone_component:
    # /-?[0-9]{4}-(((0(1|3|5|7|8)|1(0|2))-(0[1-9]|(1|2)[0-9]|3[0-1]))|
    #    ((0(4|6|9)|11)-(0[1-9]|(1|2)[0-9]|30))|(02-(0[1-9]|(1|2)[0-9])))/
    # // 70

    # xsd_time_without_timezone_component:
    # /([0-1][0-9]|2[0-4]):(0[0-9]|[1-5][0-9]):(0[0-9]|
    #    [1-5][0-9])(\.[0-9]{3})?/ // 71

    # xsd_timezone_component:
    # /((\+|-)(0[1-9]|1[0-9]|2[0-4]):(0[0-9]|[1-5][0-9])|Z)/ // 72

    # uk_date_literal:
    # /(((0[1-9]|(1|2)[0-9]|3[0-1])\/(0(1|3|5|7|8)|1(0|2)))|
    #    ((0[1-9]|(1|2)[0-9]|30)\/(0(4|6|9)|11))|
    #    ((0[1-9]|(1|2)[0-9])\/02))\/[0-9]{4}/ // 73

    # positive_non_zero_integer_literal: /[1-9][0-9]*/ // 74
    def positive_non_zero_integer_literal(self, pnz):
        (pnz,) = pnz
        return pnz

    # positive_integer_literal: /[0-9]+/ // 75
    def positive_integer_literal(self, pi):
        (pi,) = pi
        return int(pi)

    # numeric_literal: /-?[0-9]+(\.[0-9]+)?/ // 76
    def numeric_literal(self, nl):
        (nl,) = nl
        return float(nl)

    # string_literal: /\"(\\.|[^\"])*\"/
    # Allows escapes quote marks in string literal
    def string_literal(self, sl):
        (sl,) = sl
        sl = StringLiteral(sl[1:-1])
        return sl

    # character_literal: /'[^\r\n\f']'/ // 78
    def character_literal(self, cl):
        (cl, ) = cl
        return cl[1:-1]

    # wildcard_literal: /"*"/ // 79
    def wildcard_literal(self, wc):
        return "*"

    # ident: /[A-Za-z0-9\-_\.]+/ // 80
    def ident(self, id):
        (id,) = id
        return id

    @property
    def rules(self):
        return self._rules
