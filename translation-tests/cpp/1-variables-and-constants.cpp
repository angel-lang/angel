#include <cstdint>
#include <iostream>
#include <string>
int main() {
  std::string name = "Mike";
  std::int_fast8_t age = 20;
  age = 21;
  std::cout << true << std::endl;
  std::cout << false << std::endl;
  std::cout << name << std::endl;
  std::cout << (std::int_fast16_t)(age) << std::endl;
  return 0;
}
