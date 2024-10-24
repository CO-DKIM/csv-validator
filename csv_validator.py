#! /usr/bin/env python

from csvs_parser import CSVS_Parser, CSVS_Transformer
import csv
from pprint import pprint


class CSV_Validator:
    def __init__(self, csv_file, rules):
        self.csv_file = csv_file
        self.rules = rules
        self.column_index = {}
        self.column_map = {}
        self.column_name_map = {}

    def __repr__(self):
        return self.csv_file

    def check(self):
        delimiter = self.rules['@global_directives']['separator']
        csv_file = csv.reader(
            self.csv_file.splitlines(),
            delimiter=delimiter)
        csv_list = []
        for row in csv_file:
            csv_list.append(row)
        # Check the header if needed
        if self.rules["@global_directives"]["header"]:
            # Is there a total columns directive?
            if self.rules["@global_directives"].get("total_columns", 0):
                if len(csv_list[0]) != self.rules["@global_directives"]["total_columns"]:
                    print("Wrong number of columns in the header.")
                    found = len(csv_list[0])
                    expected = self.rules["@global_directives"]["total_columns"]
                    print(f"Found {found} expected {expected}.")
                    return False
            # TODO: Allow optional columns
            col_names = csv_list[0].copy()
            col_num = 0
            cur_col = col_names.pop(0)
            for key in self.rules:
                if key != "@global_directives":
                    csvs_name = self.rules[key]["name"]
                    if len(col_names) >= 0:
                        # Optional Columns
                        if self.rules[key]["directives"]["optional"]:
                            # Optional column found
                            if cur_col == csvs_name:
                                print(f"Optional key \"{csvs_name}\" found, adding at column {col_num}.")
                                self.column_index[csvs_name] = col_num
                                self.column_map[col_num] = key
                                if col_names:
                                    cur_col = col_names.pop(0)
                                else:  # Empty list
                                    continue
                                col_num += 1
                            # Optional column not found, continue
                            else:
                                print(f"Optional key \"{csvs_name}\" not found, continuing.")
                                continue
                        # Non-optional Columns
                        else:
                            # Non-optional column found
                            if cur_col == csvs_name:
                                print(f"Key \"{csvs_name}\" found, adding at column {col_num}")
                                self.column_index[csvs_name] = col_num
                                self.column_map[col_num] = key
                                self.column_name_map[cur_col] = col_num
                                if col_names:
                                    cur_col = col_names.pop(0)
                                else:  # Empty list
                                    continue
                                col_num += 1
                            # Non-optional column not found
                            else:
                                print(f"Key \"{csvs_name}\" not found. Failed!")
                                return False
            # print(self.column_index)
            # Pop the header off the front
            csv_list = csv_list[1:]
        # Evaluate each row
        for row_num, row in enumerate(csv_list):
            for index, value in enumerate(row):
                # Key in the rules for the column
                key = self.column_map[index]
                directives = self.rules[key]["directives"]
                functions = self.rules[key]["functions"]
                for function in functions:
                    if type(function) is tuple:
                        print("CONTEXT: ")
                        for i in function:
                            print("\t", i)
                    else:
                        if directives["matchIsFalse"]:
                            if function(value, row, self.column_name_map):
                                print("Invalid element!")
                                print(f"[{row_num}, {index}]: \"{value}\"")
                                return False
                        else:
                            if not function(value, row, self.column_name_map):
                                print("Invalid element!")
                                print(f"[{row_num}, {index}]: \"{value}\"")
                                return False
        return True


if __name__ == "__main__":
    parser = CSVS_Parser("example4.csvs")
    transformer = CSVS_Transformer()

    print("--------- PARSED ---------")
    transformer.transform(parser.tree)
    pprint(transformer.rules)
    # print(transformer.rules['name']("something"))  # True
    # print(transformer.rules['name'](""))  # False
    # print(transformer.rules['age']("23"))  # True
    # print(transformer.rules['age']("ds"))  # False
    # print(transformer.rules['age']("123"))  # False
    # print(transformer.rules['gender']('m'))  # True
    # print(transformer.rules['gender']('?'))  # False

    with open("example5.csv") as csv_file:
        csvfile = csv_file.read()
    c = CSV_Validator(csvfile, transformer.rules)
    pprint(c)
    if c.check():
        print("VALID")
    else:
        print("INVALID")
