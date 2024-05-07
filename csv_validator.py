from csvs_parser import CSVS_Parser, CSVS_Transformer
from pprint import pprint


class CSV_Validator:
    def __init__(self, csv_file, rules):
        self.csv_file = csv_file
        self.rules = rules

    def __repr__(self):
        return self.csv_file


if __name__ == "__main__":
    parser = CSVS_Parser("example1.csvs")
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

    with open("example2.csv") as csv_file:
        csvfile = csv_file.read()
    c = CSV_Validator(csvfile, transformer.rules)
    pprint(c)
