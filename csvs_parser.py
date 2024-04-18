import re
from pathlib import Path
from lark import Lark


class SchemaError(Exception):
    def __init__(self, message):
        print(message)


class Validator:
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
        print(self._csvs_parser.parse(self._schema_text).pretty())

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
        first_line = self._schema_text.split("\n")[0]
        version = first_line.split(' ')
        if version[0] != "version" or len(version) != 2:
            raise SchemaError("Invalid version declaration")
        if version[1] not in self._valid_version:
            raise SchemaError(f"Invalid version: {version[1]}")
        else:
            return version[1]


if __name__ == "__main__":
    v = Validator("test.csvs")
