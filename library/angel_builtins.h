#ifndef ANGEL_ANGEL_BUILTINS_H
#define ANGEL_ANGEL_BUILTINS_H

#include <string>
#include <iostream>

std::string __read(std::string prompt);

template <typename T>
void __print(T value) {
    if (typeid(T) == typeid(bool)) {
        if (value) {
            std::cout << "True" << std::endl;
        } else {
            std::cout << "False" << std::endl;
        }
    } else {
        std::cout << value << std::endl;
    }
}

#endif //ANGEL_ANGEL_BUILTINS_H
