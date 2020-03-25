#ifndef ANGEL_ANGEL_BUILTINS_H
#define ANGEL_ANGEL_BUILTINS_H

#include <string>
#include <iostream>

std::string __read(std::string prompt) {
    std::string result;
    std::cout << prompt;
    std::cin >> result;
    return result;
}

template <typename T>
void __print(T value) {
    std::cout << value << std::endl;
}

void __print(bool value) {
    if (value) {
        std::cout << "True" << std::endl;
    } else {
        std::cout << "False" << std::endl;
    }
}

#endif //ANGEL_ANGEL_BUILTINS_H
