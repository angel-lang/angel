# Challenge
Goal: finish Angel 1.0 compiler in 100 days

Progress: every commit has the format of `Day {current day}: {commit description}`

Start: 07.03.2020

Finish: 15.06.2020

# Angel
Angel is a programming language that is being developed to be the best.

This repository contains Angel to C++ compiler written in Python.

## How to run
`./runnable` to run REPL.

`./runnable my_file.angel` to compile `my_file.angel`.

`./runnable my_file.angel | clang-format > my_file.cpp` to get pretty
C++ code in `my_file.cpp`. 

## Tutorial
`print("Hello, world!")` prints `Hello, world!`.

Angel is a statically-typed language.

`let number: I16 = 200` creates a constant `number` with type `I16` and value `200`.
