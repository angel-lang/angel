# Installing dependencies
## Libtommath
1. Clone it
2. `make`
3. Copy `libtommath.a` to `Angel/library` folder

# About Angel
Angel is a programming language that is being developed to be the best.
It is a statically-typed language (all types are known in compile-time and
cannot be changed in run-time).

Main (and the only, for now) implementation of Angel is a compiler from
Angel to C++ written in Python. You can find it in [`compiler`](compiler) package.

## Objectives for Angel
- Move as many run-time errors to compile-time as possible.
Even `IndexOutOfRange` error will be at compile-time.
- Warn programmer about possible errors in run-time.
- Beautiful syntax.
- Provide extensive standard library.
- Generate fast and portable code.

## Design decisions
- One step of indentation is exactly 4 spaces.
I would recommend to set up `Tab` key to insert 4 spaces.

# Dependencies
- `Python 3.8`
- `clang-format`

# How to run
`./runnable.py` to run REPL.

`./runnable.py my_file.angel` to compile `my_file.angel`.

`./runnable.py my_file.angel | clang-format > my_file.cpp` to get pretty
C++ code in `my_file.cpp`.

# Tutorial
## Hello, world!
`print("Hello, world!")`

## Constants
Constants are immutable. Once value is assigned to a constant, it
cannot be changed by accessing the constant.

To define a constant `c` use any of these statements:
- `let c: I8 = 1`: checks that `1` has type `I8`.
- `let c = 1`: infers type from `1`.
- `let c: I8`: exactly one assignment (type checking is present) is allowed later.

You can use any type instead of `I8` and any value of the type you have chosen.

## Variables
Variables are mutable. Value can be changed by accessing the variable.

To define a variable `v` use any of these statements:
- `var v: I8 = 1`: checks that `1` has type `I8`.
- `var v = 1`: infers type from `1`.
- `var v: I8`: can be assigned many times (type checking is present).

## Assignment
Assignment is a statement that assigns new value to some
variable (or constant if it doesn't have value yet).

In general it looks like this: `variable = 100`.
Type checking is performed to ensure that new value has the type of the variable.

## While
You can see the great power of `while` in this example:
```
var i = 0
while i <= 10:
    print(i)
    i = i + 1
```
This program prints all integers from 0 to 10.
Expression `i <= 10` will be recomputed at the start of each cycle.
It is not cached.

## For loop
You can iterate through elements of some container (only Vector or String for now).
```
for element in [1, 2, 3]:
    print(element)
```

## If
Who needs `if` statement if you already have `while-break`? I'm just joking.
```
if 1 > 2:
    print("Really?")
elif 0 > 2:
    print("Are you sure?")
else:
    print("OK")
```
This program prints `OK`, because first-grade math is working in Angel.
First `1 > 2` will be computed. It is `False`, so we compute `0 > 2`.
It is `False` too, so we execute the `else` branch.

Only one of the branches will be executed.

## Functions
```
fun printNumbers(end: I8):
    var i = 0
    while i < end:
        print(i)
        i += 1

printNumbers(5)
```

## Structs
```
struct Person:
    first: String
    last: String
```

The field is private if its name starts with `_`.
Private fields can be used only in methods.

Default init will be generated if structure doesn't have `init`s.
It will expect all public fields as arguments and assign these arguments
to corresponding fields. All private fields must have a default value because
these will be initialized by their default values.

```
struct Person:
    first: String
    last: String

    init(first: String, last: String):
        self.first = first
        self.last = last
```

Structures can have several `init`s. They must have different signatures.

```
struct Email:
    userName: String
    domain: String

    init(userName: String, domain: String):
        self.userName = userName
        self.domain = domain

    init():
        self.userName = "test"
        self.domain = "mail.com"

    fun changeDomain(domain: String):
        self.domain = domain
```

You can access fields by `.`.

```
let myEmail = Email("noob", "some-mail.com")
let domain = myEmail.domain
```

You can call methods:
```
var email = Email()
email.changeDomain("new-domain.com")
```

Structures can be generic.
```
struct Stack<A>:
    data: [A]

    fun push(element: A) -> A:
        self.data.append(element)
        return element

let stack = Stack([1, 2, 3])
```

## Extensions
You can split struct declarations into small extensions.
```
struct Vec:
    x: I8
    y: I8


extension Vec is ConvertibleToString:
    fun as -> String:
        return "(" + self.x as String + ", " + self.y as String + ")"
```

You can define methods and new constructors (not yet) in extensions. Fields cannot be declared in extensions.

## Algebraic Data Types
```
algebraic Number:
    struct Signed:
        signed: I64

    struct Unsigned:
        unsigned: U64

        fun isGoodForU8() -> Bool:
            return self.unsigned <= 256

    fun zero() -> I64:
        return 0

let number = Number.Unsigned(42)
let n = number.unsigned
let isGood = number.isGoodForU8()
let zero = n.zero()
```

Algebraic data types can have several constructors. Its constructors can have different fields and methods.
Algebraics can have their own methods.

## Interfaces
```
interface Empty


interface Beautiful is Empty:
    beautifulValue: String

    fun showBeauty()
```

Interfaces can contain field and method declarations and inherit them from other interfaces.

You can implement interfaces in structs.
All fields and methods must be present in the struct.
All fields/methods must have the same types/signatures as their prototypes in interfaces.
```
struct Person is Beautiful:
    firstName: String
    secondName: String
    age: U8
    beautifulValue: String

    fun showBeauty():
        print(self.beautifulValue)
```

### Object
Every type (struct, interface, algebraic data type) in Angel implements `Object` interface.

### Operator overloading
To overload `+` operator, struct must implement `Addable` interface. `Self` is the implementor's type.
```
interface Addable:
    fun __add__(other: Self) -> Self
```

Example:
```
struct V is Addable:
    first: I8
    second: I8

    fun __add__(other: V) -> V:
        return V(self.first + other.first, self.second + other.second)

let v = V(1, 2) + V(3, 4)
```

### Type conversions
To convert type `A` to type `B`:
```
struct A:
    // some code

    fun as -> B:
        return B()

let b = A() as B    // calls `as` method
```

For example:
```
struct Vec is ConvertibleToString:
    x: I8
    y: I8

    fun as -> String:
        return "(" + self.x as String + ", " + self.y as String + ")"


// prints the same
print(Vec(1, 2))
print(Vec(1, 2) as String)
```

## Reading Input and Writing Output
```
let name = read("Enter your name: ")
print("Your name is")
print(name)
```

Function `read(prompt: String) -> String` prints `prompt` to stdout,
reads input from stdin and returns it.

Function `print`:
- `print(value: String)`: converts `value` to `String` and prints the result.
- `print(value: ConvertibleToString)`: prints `value`.


## Built-in Types
### Signed finite integer types
- `I8`: `-128 <= I8 <= 127`
- `I16`: `-32768 <= I16 <= 32767`
- `I32`: `-2147483648 <= I32 <= 2147483647`
- `I64`: `-9223372036854775808 <= I64 <= 9223372036854775807`

### Unsigned finite integer types
- `U8`: `0 <= U8 <= 255`
- `U16`: `0 <= U16 <= 65535`
- `U32`: `0 <= U32 <= 4294967295`
- `U64`: `0 <= U64 <= 18446744073709551615`

Literal for finite integer types is just a number in
type's range: e.g. `100` for `I8`.

### Finite float types
- `F32`:
```
-3.402823700000000000000000000E+38 <= F32 <= -1.17549400000000000000000000E-38
or
1.17549400000000000000000000E-38 <= F32 <= 3.402823700000000000000000000E+38
or
F32 == 0
```
- `F64`:
```
-1.79769313486231570000000000E+308 <= F64 <= -2.22507385850720140000000000E-308
or
2.22507385850720140000000000E-308 <= F64 <= 1.79769313486231570000000000E+308
or
F64 == 0
```

Literal for finite float types is just a decimal number in
type's range: e.g. `20.034` for `F32`.
### `Char`
Literal is exactly one character surrounded by single quotes (`'`), e.g. `'a'`.

### `Bool`
Literal can be `True` or `False`.

### `String`
Literal can be any text surrounded by double quotes (`"`),
e.g. `"I am a string!"`

#### `fun String.split(by delimiter: Char) -> [String]`
Splits `self` string by `delimiter` character and returns the list of
all strings between `delimiter` strings. `delimiter` is not included in the list.

#### `String.length: U64`
Stores the length of the string.

### Vector type `[ElementType]`
`ElementType` can be any type, e.g. `[I8]`. Literal for vector type has the
format of `[ElementTypeLiteral, ...]`, e.g. `[1, 2, 3, 4]` for `[I8]` type.

#### `fun [A].append(element: A)`
Adds `element` to the end of the vector.

#### `[A].length: U64`
Stores the length of the vector.

### Dict type `[KeyType: ValueType]`
`KeyType` and `ValueType` can be any types, e.g. `[String: I8]`.
Literal for this type has the format of `[KeyLiteral: ValueLiteral, ...]`,
e.g. `["a": 1, "c": 0, "b": 3]` for `[String: I8]` type.

### Optional type `T?`
It is defined as
```
algebraic Optional<T>:
    Some(value: T)
  | None

    fun __eq__(other: T?) -> Bool
```

Examples of usage:
```
let example = Optional.None
let example: String? = Optional.Some("John")
```

It supports `==` and `!=` operators.

To get real value from Optional type use `if let`:
```
if let realValue = getRandomOptionalValue():
    print(realValue)
else:
    print("No value because of Optional.None")
```

Or you can use `while let`:
```
while let realValue = getRandomOptionalValue():
    print(realValue)
```

### Ref type `ref T`
```
var p: ref I8 = ref 10
var r = p
// p.value == r.value == 10

p.value = 20
// p.value == r.value == 20
```

You can acess real value by `value` field.
