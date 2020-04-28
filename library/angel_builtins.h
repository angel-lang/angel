#ifndef ANGEL_ANGEL_BUILTINS_H
#define ANGEL_ANGEL_BUILTINS_H

#include <iostream>
#include <sstream>
#include <string>
#include <vector>

std::string __read(std::string prompt) {
  std::string result;
  std::cout << prompt;
  std::cin >> result;
  return result;
}

template <typename T>
std::string __vector_to_string(std::vector<T> value) {
  std::ostringstream s;
  s << "[";
  auto it = value.begin();
  if (it != value.end()) {
    s << *it;
    it++;
  }
  for (; it != value.end(); it++)
    s << ", " << *it;
  s << "]";
  return s.str();
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

#endif  // ANGEL_ANGEL_BUILTINS_H
