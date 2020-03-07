#!/usr/bin/env python3
import argparse

import compiler


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("in_file", nargs="?", default=None, type=argparse.FileType(encoding="utf-8"))
    args = argparser.parse_args()

    if args.in_file:
        print(compiler.compile_string(args.in_file.read()))
    else:
        compiler.repl()


if __name__ == "__main__":
    main()
