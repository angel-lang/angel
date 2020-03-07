import cmd
import sys
import traceback
import typing as t
import subprocess

from . import parser, translators, generators


def compile_file(file_path: str) -> str:
    """Translates Angel code contained in `file_path` into C++ code and returns it."""
    with open(file_path) as file:
        contents = file.read()
    return compile_string(contents)


def compile_string(string: str) -> str:
    """Translates Angel code represented by `string` into C++ code and returns it."""
    ast = parser.Parser().parse(string)
    cpp_ast = translators.Translator().translate(ast)
    return generators.generate_cpp(cpp_ast)


def angel_repl_eval(string: str) -> t.Any:
    """Evaluates Angel code represented by `string` and returns the result."""
    ast = parser.Parser().parse(string)
    assert len(ast) == 1
    return translators.Translator().repl_eval(ast[0])


class REPL(cmd.Cmd):
    intro = """Angel REPL. Available commands:
:gencpp     prints generated C++ code
:clear      clears virtual file
:undo       removes last statement from virtual file
:exit :quit :q :e   exits"""
    prompt = ">>> "
    input_ = []

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
            evaluated = angel_repl_eval(inp)
            if evaluated is not None:
                print(evaluated)
            self.input_.append(inp)

    do_quit = do_exit
    do_q = do_exit
    do_e = do_exit


def repl():
    """Starts Angel REPL."""
    try:
        REPL().cmdloop()
    except KeyboardInterrupt:
        pass
