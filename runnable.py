#!/usr/bin/env python3
import argparse

import compiler


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("in_file", nargs="?", default=None, type=argparse.FileType(encoding="utf-8"))
    argparser.add_argument("--unmangle-names", action='store_true', default=False)
    arguments = argparser.parse_args()

    if arguments.in_file:
        print(compiler.compile_string(arguments.in_file.read(), not arguments.unmangle_names))
    else:
        compiler.repl()


if __name__ == "__main__":
    main()
