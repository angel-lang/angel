#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <vector>
#include "angel_builtins.h"
#include "angel_string.h"
std::optional<std::int_fast8_t> getN(std::int_fast8_t i) {
  if (i <= 3) {
    return i;
  }
  return std::nullopt;
}
class Email {
 public:
  std::string userName;
  std::string domain;
  Email(std::string userName, std::string domain) {
    this->userName = userName;
    this->domain = domain;
  }
  Email() {
    this->userName = "test";
    this->domain = "mail.com";
  }
};
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
    __print("No");
  } else {
    __print("YES");
  }
  auto __tmp_2 = optionalName;
  if (__tmp_2 != std::nullopt) {
    std::string realName = *__tmp_2;
    __print(realName);
  } else {
    __print("No name");
  }
  std::int_fast8_t lol = 0;
  auto __tmp_3 = getN(lol);
  while (__tmp_3 != std::nullopt) {
    std::int_fast8_t n = *__tmp_3;
    __print(n);
    lol = lol + 1;
    __tmp_3 = getN(lol);
  }
  std::string names = "John,Mike,Kale";
  std::vector<std::string> parts = __string_split_char(names, ',');
  std::string name = "Mike";
  std::uint_fast64_t length = name.length();
  std::int_fast8_t age = 20;
  age = 21;
  __print(name);
  __print((std::int_fast16_t)(age));
  if (true) {
    __print(true);
  } else if (age == 21) {
    __print(true);
  } else {
    __print(false);
  }
  while (age < 30) {
    if (age == 25) {
      __print("HA-HA");
    }
    age = age + 1;
  }
  Email basicEmail = Email();
  __print(basicEmail.userName);
  __print(basicEmail.domain);
  Email advancedEmail = Email("john", "mail.com");
  __print(advancedEmail.userName);
  __print(advancedEmail.domain);
  return 0;
}
