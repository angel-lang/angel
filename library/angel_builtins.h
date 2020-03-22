#ifndef ANGEL_ANGEL_BUILTINS_H
#define ANGEL_ANGEL_BUILTINS_H

std::string __read(std::string prompt);

template <typename T>
void __print(T value) {
    std::cout << value << std::endl;
}

#endif //ANGEL_ANGEL_BUILTINS_H
