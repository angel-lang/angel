#include <string>
#include <vector>
#include "angel_string.h"

std::vector <std::string> __string_split_char(const std::string self, const char delimiter) {
    std::vector<std::string> result;
    std::string buffer = "";

    for (auto c : self) {
        if (c != delimiter) {
            buffer += c;
        } else if (c == delimiter && buffer != "") {
            result.push_back(buffer);
            buffer = "";
        }
    }
    if (buffer != "") {
        result.push_back(buffer);
    }
    return result;
}
