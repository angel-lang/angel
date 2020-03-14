#include <cstdint>
#include <iostream>
#include <string>
int main() {
  std::int_fast8_t constantWithEverything = 1;
  std::int_fast8_t constantWithoutType = 1;
  std::int_fast8_t constantWithoutValue;
  std::int_fast8_t variableWithEverything = 1;
  std::int_fast8_t variableWithoutType = 1;
  std::int_fast8_t variableWithoutValue;
  constantWithoutValue = 1;
  variableWithEverything = 2;
  variableWithoutType = 2;
  variableWithoutValue = 2;
  variableWithoutValue = 3;
  char charWithEverything = 'a';
  char charWithoutType = 'b';
  std::string name = "Mike";
  std::int_fast8_t age = 20;
  age = 21;
  std::cout << name << std::endl;
  std::cout << (std::int_fast16_t)(age) << std::endl;
  if (true) {
    std::cout << true << std::endl;
  } else if (age == 21) {
    std::cout << true << std::endl;
  } else {
    std::cout << false << std::endl;
  }
  while (age < 30) {
    if (age == 25) {
      std::cout << "HA-HA" << std::endl;
    }
    age = age + 1;
  }
  return 0;
}
