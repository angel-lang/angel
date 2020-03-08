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
`print("Hello, world!")` prints `Hello, world!`.

Angel is a statically-typed language.

`var number: I16 = 200` creates a variable `number` with type `I16` and value `200`.

`number = 100` assigns value `100` to `number`.

Every group of statements will create a constant `name` with type `String`
(inferred from value) and value `"John"`
```
let name: String
name = "John"

let name: String = "John"

let name = "John"
```

You can use variables and constants in expressions, e.g. `print(number)`.
