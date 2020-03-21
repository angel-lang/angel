from enum import Enum


class StringFields(Enum):
    split_char = "__string_split_char"


class Modules(Enum):
    string = "angel_string"

    @property
    def header(self) -> str:
        return self.value + ".h"
