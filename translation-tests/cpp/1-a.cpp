#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <vector>

std::vector<std::string> __split_string(const std::string self,
                                        const char delimiter) {
  std::vector<std::string> result;
  std::string buffer{""};
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

std::optional<std::int_fast8_t> getN(std::int_fast8_t i) {
  if (i <= 3) {
    return i;
  }
  return std::nullopt;
}
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
  float f32WithEverything = 10.20;
  float f32WithoutType = 120.1;
  double f64WithEverything = 10.20;
  double f64WithoutType = 340282370000000000808640304032688192896.1;
  std::vector<void*> emptyVectorWithoutType = {};
  std::vector<std::int_fast8_t> emptyVectorWithType = {};
  std::vector<std::int_fast16_t> vectorWithoutType = {1, 260};
  std::vector<std::int_fast8_t> vectorWithType = {1};
  std::map<void*, void*> emptyDictWithoutType;
  std::map<std::string, std::int_fast8_t> emptyDictWithType;
  std::map<std::string, std::int_fast8_t> __tmp_0;
  __tmp_0["a"] = 1;
  __tmp_0["c"] = 0;
  __tmp_0["b"] = 3;
  std::map<std::string, std::int_fast8_t> dictWithoutType = __tmp_0;
  std::map<std::string, std::int_fast8_t> __tmp_1;
  __tmp_1["a"] = 1;
  std::map<std::string, std::int_fast8_t> dictWithType = __tmp_1;
  std::optional<void*> someOptional = std::nullopt;
  std::optional<std::string> optionalName = "John";
  if (optionalName == std::nullopt) {
    std::cout << "No" << std::endl;
  } else {
    std::cout << "YES" << std::endl;
  }
  auto __tmp_2 = optionalName;
  if (__tmp_2 != std::nullopt) {
    std::string realName = *__tmp_2;
    std::cout << realName << std::endl;
  } else {
    std::cout << "No name" << std::endl;
  }
  std::int_fast8_t lol = 0;
  auto __tmp_3 = getN(lol);
  while (__tmp_3 != std::nullopt) {
    std::int_fast8_t n = *__tmp_3;
    std::cout << n << std::endl;
    lol = lol + 1;
    __tmp_3 = getN(lol);
  }
  std::vector<std::string> names = __split_string("John,Mike,Kale", ',');
  std::string name = "Mike";
  std::uint_fast64_t length = name.length();
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
