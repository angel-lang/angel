#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <variant>
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
class User {
 public:
  User() {}
  std::string firstName;
  std::string lastName;
  Email email;
  bool isAdmin;
  User(std::string firstName,
       std::string lastName,
       Email email,
       bool isAdmin = false) {
    this->firstName = firstName;
    this->lastName = lastName;
    this->email = email;
    this->isAdmin = isAdmin;
  }
  void makeAdmin() { this->isAdmin = true; }
};
template <typename A>
class Stack {
 public:
  Stack() {}
  std::vector<A> data;
  Stack(std::vector<A> data) { this->data = data; }
  A push(A element) {
    this->data.push_back(element);
    return element;
  }
  std::uint_fast64_t depth() { return this->data.size(); }
};
class Color_a_Red {
 public:
  Color_a_Red() {}
  std::int_fast8_t data;
  Color_a_Red(std::int_fast8_t data) { this->data = data; }
  std::string getEstimation() {
    if (this->data < 10) {
      return "Small";
    }
    return "Big";
  }
};
class Color_a_Blue {
 public:
  Color_a_Blue() {}
  std::int_fast8_t data;
  Color_a_Blue(std::int_fast8_t data) { this->data = data; }
};
class Color_a_Green {
 public:
  Color_a_Green() {}
  std::int_fast8_t data;
  Color_a_Green(std::int_fast8_t data) { this->data = data; }
};
std::string Color_m_word(
    std::variant<Color_a_Red, Color_a_Blue, Color_a_Green> self) {
  return "word";
}
class Beautiful {
 public:
  std::string beautifulValue;
  void showBeauty() {}
};
class Cool : public Beautiful {};
class Person : public Cool {
 public:
  Person() {}
  std::string firstName;
  std::string secondName;
  std::uint_fast8_t age;
  std::string beautifulValue;
  Person(std::string firstName,
         std::string secondName,
         std::uint_fast8_t age,
         std::string beautifulValue) {
    this->firstName = firstName;
    this->secondName = secondName;
    this->age = age;
    this->beautifulValue = beautifulValue;
  }
  void showBeauty() { __print(this->beautifulValue); }
};
class V {
 public:
  V() {}
  std::int_fast8_t first;
  std::int_fast8_t second;
  V(std::int_fast8_t first, std::int_fast8_t second) {
    this->first = first;
    this->second = second;
  }
  void report() {
    __print(std::to_string(this->first) + " " + std::to_string(this->second));
  }
  V operator+(V other) {
    return V(this->first + other.first, this->second + other.second);
  }
  V operator-(V other) {
    return V(this->first - other.first, this->second - other.second);
  }
  V operator*(V other) {
    return V(this->first * other.first, this->second * other.second);
  }
  V operator/(V other) {
    return V(this->first / other.first, this->second / other.second);
  }
};
class Vec {
 public:
  Vec() {}
  std::int_fast8_t x;
  std::int_fast8_t y;
  Vec(std::int_fast8_t x, std::int_fast8_t y) {
    this->x = x;
    this->y = y;
  }
  std::string toString() {
    return "(" + std::to_string(this->x) + ", " + std::to_string(this->y) + ")";
  }
};
void change(std::string* r) {
  *r = "New one";
}
template <typename A, typename B>
class MyPair {
 public:
  MyPair() {}
  A x;
  B y;
  MyPair(A x, B y) {
    this->x = x;
    this->y = y;
  }
  bool operator==(MyPair<A, B> other) {
    return this->x == other.x && this->y == other.y;
  }
};
class C {
 public:
  C() {}
  std::string value;
  C(std::string value) { this->value = value; }
};
template <typename A>
A pass(A value) {
  return value;
}
std::ostream& operator<<(std::ostream& _arg1, Vec& _arg2) {
  _arg1 << _arg2.toString();
  return _arg1;
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
  std::vector<std::int_fast8_t> tmp_0 = {1, 2, 3};
  std::vector<std::int_fast8_t> tmp_1 = {4};
  tmp_0.insert(tmp_0.end(), tmp_1.begin(), tmp_1.end());
  std::vector<std::int_fast8_t> l = tmp_0;
  std::map<void*, void*> emptyDictWithoutType;
  std::map<std::string, std::int_fast8_t> emptyDictWithType;
  std::map<std::string, std::int_fast8_t> tmp_2;
  tmp_2["a"] = 1;
  tmp_2["c"] = 0;
  tmp_2["b"] = 3;
  std::map<std::string, std::int_fast8_t> dictWithoutType = tmp_2;
  std::map<std::string, std::int_fast8_t> tmp_3;
  tmp_3["a"] = 1;
  std::map<std::string, std::int_fast8_t> dictWithType = tmp_3;
  __print((std::int_fast16_t)(dictWithoutType["a"]));
  __print(dictWithoutType.size());
  std::optional<void*> someOptional = std::nullopt;
  std::optional<std::string> optionalName = "John";
  if (optionalName == std::nullopt) {
    __print("No");
  } else {
    __print("YES");
  }
  auto tmp_4 = optionalName;
  if (tmp_4 != std::nullopt) {
    std::string realName = *tmp_4;
    __print(realName);
  } else {
    __print("No name");
  }
  std::int_fast8_t lol = 0;
  auto tmp_5 = getN(lol);
  while (tmp_5 != std::nullopt) {
    std::int_fast8_t n = *tmp_5;
    __print(n);
    lol = lol + 1;
    tmp_5 = getN(lol);
  }
  std::string names = "John,Mike,Kale";
  std::vector<std::string> parts = __string_split_char(names, ',');
  std::string name = "Mike";
  __print(name[1]);
  std::uint_fast64_t length = name.length();
  __print(parts[2]);
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
  User user = User("John", "Smith", advancedEmail);
  __print(user.email.userName);
  __print(user.isAdmin);
  user.makeAdmin();
  __print(user.isAdmin);
  Stack<std::int_fast8_t> stack = Stack<std::int_fast8_t>({1, 2, 3});
  std::int_fast8_t element = stack.data[2];
  std::int_fast8_t same = stack.push(4);
  __print(stack.data.size());
  __print(stack.depth());
  std::variant<Color_a_Red, Color_a_Blue, Color_a_Green> color1 =
      Color_a_Red(120);
  std::variant<Color_a_Red, Color_a_Blue, Color_a_Green> color2 =
      Color_a_Blue(0);
  __print((std::int_fast16_t)(std::get<Color_a_Blue>(color2).data));
  std::int_fast8_t colorData = std::get<Color_a_Blue>(color2).data;
  std::string estimation = std::get<Color_a_Red>(color1).getEstimation();
  __print(estimation);
  color1 = Color_a_Green(10);
  __print((std::int_fast16_t)(std::get<Color_a_Green>(color1).data));
  __print(Color_m_word(color1));
  V v1 = V(1, 2);
  V v2 = V(2, 2);
  V v3 = v1 + v2;
  V v4 = v1 - v2;
  V v5 = v1 * v2;
  V v6 = v1 / v2;
  v3.report();
  v4.report();
  v5.report();
  v6.report();
  __print(Vec(1, 2));
  __print(Vec(1, 2).toString());
  __print(((Vec)(Vec(1, 2))).toString());
  __print(__vector_to_string<std::int_fast16_t>({1, 2, 3}));
  __print(__vector_to_string<std::string>({"John", "Mike"}));
  std::vector<std::int_fast8_t> tmp_6 = {1, 2, 3};
  for (std::vector<std::int_fast8_t>::iterator tmp_7 = tmp_6.begin();
       tmp_7 != tmp_6.end(); ++tmp_7) {
    std::int_fast8_t element = *tmp_7;
    __print((std::int_fast16_t)(element));
  }
  std::string tmp_8 = "John";
  for (std::string::iterator tmp_9 = tmp_8.begin(); tmp_9 != tmp_8.end();
       ++tmp_9) {
    char element = *tmp_9;
    __print(element);
  }
  std::int_fast8_t tmp_10 = 1;
  std::int_fast8_t* p = &tmp_10;
  std::int_fast8_t* r = p;
  __print((std::int_fast16_t)(*p));
  __print((std::int_fast16_t)(*r));
  *p = 2;
  __print((std::int_fast16_t)(*p));
  __print((std::int_fast16_t)(*r));
  std::string tmp_11 = "Hello";
  std::string* ps = &tmp_11;
  change(ps);
  __print((*ps)[0]);
  MyPair<std::int_fast8_t, std::string> myPair1 =
      MyPair<std::int_fast8_t, std::string>(1, "John");
  MyPair<std::int_fast8_t, C> myPair2 =
      MyPair<std::int_fast8_t, C>(2, C("John"));
  __print(myPair1 == myPair1);
  __print(pass("value"));
  return 0;
}
