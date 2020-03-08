import cmd
import sys
import traceback
import typing as t
import subprocess

from . import parser, translators, generators, analyzers, environment, errors


def compile_file(file_path: str) -> str:
    """Translates Angel code contained in `file_path` into C++ code and returns it."""
    with open(file_path) as file:
        contents = file.read()
    return compile_string(contents)


def compile_string(string: str) -> str:
    """Translates Angel code represented by `string` into C++ code and returns it."""
    lines = string.split("\n")
    try:
        ast = analyzers.Analyzer(lines).analyze(parser.Parser().parse(string))
        cpp_ast = translators.Translator(lines).translate(ast)
    except errors.AngelError as e:
        print(str(e))
        print()
        sys.exit(1)
    else:
        return generators.generate_cpp(cpp_ast)


def angel_repl_eval(string: str) -> t.Any:
    """Evaluates Angel code represented by `string` and returns the result."""
    lines = string.split("\n")
    try:
        ast = analyzers.Analyzer(lines).analyze(parser.Parser().parse(string))
        return translators.Translator(lines).repl_eval(ast)
    except errors.AngelError as e:
        print(str(e))
        print()
        sys.exit(1)


class REPL(cmd.Cmd):
    intro = """Angel REPL. Available commands:
:gencpp     prints generated C++ code
:clear      clears virtual file
:undo       removes last statement from virtual file
:exit :quit :q :e   exits"""
    prompt = ">>> "
    input_: t.List[str] = []

    def do_eval(self):
        try:
            proc = subprocess.run(
                ['clang-format', '--assume-filename=a.cpp'], input=compile_string("\n".join(self.input_)),
                encoding="utf-8", stdout=subprocess.PIPE)
            print(proc.stdout)
        except Exception:
            traceback.print_exc(chain=False)

    def command(self, command):
        if command == "gencpp":
            self.do_eval()
        elif command == "clear":
            self.input_ = []
        elif command == "undo":
            self.input_ = self.input_[:-1]

    def do_exit(self, _):
        sys.exit(0)

    def emptyline(self):
        pass

    def default(self, inp):
        if inp == "EOF":
            return True
        elif inp.startswith(":"):
            self.command(inp.split(":")[1])
        else:
            self.input_.append(inp)
            evaluated = angel_repl_eval("\n".join(self.input_))
            if evaluated is not None:
                print(evaluated)

    do_quit = do_exit
    do_q = do_exit
    do_e = do_exit


def repl():
    """Starts Angel REPL."""
    try:
        REPL().cmdloop()
    except KeyboardInterrupt:
        pass
