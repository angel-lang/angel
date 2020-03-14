# Challenge
Goal: finish Angel 1.0 compiler in 100 days

Progress: every commit has the format of `Day {current day}: {commit description}`

Start: 07.03.2020

Finish: 15.06.2020

# Angel
Angel is a programming language that is being developed to be the best.

This repository contains Angel to C++ compiler written in Python.

## Dependencies
- `Python 3.8`
- `clang-format`

## How to run
`./runnable.py` to run REPL.

`./runnable.py my_file.angel` to compile `my_file.angel`.

`./runnable.py my_file.angel | clang-format > my_file.cpp` to get pretty
C++ code in `my_file.cpp`. 

## Tutorial
### General Knowledge
Angel is a statically-typed language (types cannot be changed in runtime).

Some of the objectives for Angel:
- Move as many run-time errors to compile-time as possible.
Even `IndexOutOfRange` error will be at compile-time.
- Warn programmer about possible errors in run-time.
- Keep syntax beautiful.
- Provide extensive standard library.
- Generate fast and portable code.

One step of indentation is exactly 4 spaces.
I would recommend to set up `Tab` key to insert 4 spaces.

### Hello, world!
`print("Hello, world!")`

### Constants
Constants are immutable. Once value is assigned to a constant, it
cannot be changed by accessing the constant.

To define a constant `c` use any of these statements:
- `let c: I8 = 1`: checks that `1` has type `I8`.
- `let c = 1`: infers type from `1`.
- `let c: I8`: exactly one assignment (type checking is present) is allowed later.

You can use any type instead of `I8` and any value of the type you have chosen.

### Variables
Variables are mutable. Value can be changed by accessing the variable.

To define a variable `v` use any of these statements:
- `var v: I8 = 1`: checks that `1` has type `I8`.
- `var v = 1`: infers type from `1`.
- `var v: I8`: can be assigned many times (type checking is present).

### Assignment
Assignment is a statement that assigns new value to some
variable (or constant if it doesn't have value yet).

In general it looks like this: `variable = 100`.
Type checking is performed to ensure that new value has the type of the variable. 

### While
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

### If
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
First `1 > 2` will be computed. It is `false`, so we compute `0 > 2`.
It is `false` too, so we execute the `else` branch.

Only one of the branches will be executed.

### Functions
```
fun printNumbers(end: I8):
    var i = 0
    while i < end:
        print(i)
        i += 1

printNumbers(5)
```

### Structs
```
struct Person:
    first: String
    last: String
```

### Reading Input and Writing Output
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


### Built-in Types
Signed finite integer types:
- `I8`: `-128 <= I8 <= 127`
- `I16`: `-32768 <= I16 <= 32767`
- `I32`: `-2147483648 <= I32 <= 2147483647`
- `I64`: `-9223372036854775808 <= I64 <= 9223372036854775807`

Unsigned finite integer types:
- `U8`: `0 <= U8 <= 255`
- `U16`: `0 <= U16 <= 65535`
- `U32`: `0 <= U32 <= 4294967295`
- `U64`: `0 <= U64 <= 18446744073709551615`

Literal for finite integer types is just a number in
type's range: e.g. `100` for `I8`.

Other primitive types:
- `Char`: literal is exactly one character surrounded by single quotes (`'`),
e.g. `'a'`.
- `Bool`: literal can be `true` or `false`.

Container types:
- `String`: literal is any string surrounded by double quotes (`"`),
e.g. `"I am a string!"`

## Coming soon
- Defined structs cannot be used
- Functions with `return` will be tested soon
- `self`
