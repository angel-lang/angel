#include <iostream>
#include <string>
#include "angel_builtins.h"


std::string __read(std::string prompt) {
    std::string result;
    std::cout << prompt;
    std::cin >> result;
    return result;
}
