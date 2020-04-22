import cmd
import sys
import traceback
import typing as t
import subprocess

from . import (
    parsers, translators, generators, environment, errors, clarification, repl_evaluation, analysis
)
from .utils import get_hash


DEBUG = False


def compile_file(file_path: str) -> str:
    """Translate Angel code contained in `file_path` into C++ code and returns it."""
    with open(file_path) as file:
        contents = file.read()
    return compile_string(contents)


def compile_string(string: str, mangle_names: bool = True) -> str:
    """Translate Angel code represented by `string` into C++ code and returns it."""
    lines = string.split("\n")
    parser = parsers.Parser()
    hash_ = get_hash(string)
    clarifier = clarification.Clarifier(hash_, mangle_names)
    analyzer = analysis.Analyzer(lines, hash_, mangle_names)
    translator = translators.Translator()
    try:
        cpp_ast = translator.translate(
            analyzer.analyze_ast(clarifier.clarify_ast(parser.parse(string)))
        )
    except errors.AngelError as e:
        if DEBUG:
            raise e
        else:
            print(str(e))
            print()
            sys.exit(1)
    else:
        return generators.generate_cpp(cpp_ast)


def angel_repl_eval(string: str, env: environment.Environment) -> t.Any:
    """Evaluate Angel code represented by `string` and returns the result."""
    lines = string.split("\n")
    parser = parsers.Parser()
    clarifier = clarification.Clarifier('', mangle_names=False)
    analyzer = analysis.Analyzer(lines, '', mangle_names=False, env=env)
    repl_evaluator = repl_evaluation.REPLEvaluator('', mangle_names=False, env=env)
    try:
        return repl_evaluator.estimate_ast(
            analyzer.analyze_ast(clarifier.clarify_ast(parser.parse(string)))
        )
    except errors.AngelError as e:
        if DEBUG:
            raise e
        else:
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
    identchars = " "
    input_: t.List[str] = []
    buffer: t.List[str] = []
    indentation_expected: bool = False
    real_inp: str
    env: environment.Environment = environment.Environment()

    def precmd(self, line):
        # Save line with leading whitespaces.
        self.real_inp = line
        return line

    def do_eval(self):
        try:
            proc = subprocess.run(
                ['clang-format', '--assume-filename=a.cpp'],
                input=compile_string("\n".join(self.input_), mangle_names=False), encoding="utf-8",
                stdout=subprocess.PIPE
            )
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
        if self.indentation_expected:
            self.indentation_expected = False
            self.prompt = ">>> "
            self.input_.extend(self.buffer)
            angel_repl_eval("\n".join(self.buffer), env=self.env)

    def default(self, inp):
        if inp == "EOF":
            return True
        elif inp.startswith(":"):
            if self.indentation_expected:
                return True
            self.command(inp.split(":")[1])
        else:
            if self.indentation_expected:
                self.buffer.append(self.real_inp)
            elif inp.endswith(":"):
                self.indentation_expected = True
                self.prompt = "... "
                self.buffer = [inp]
            else:
                self.input_.append(inp)
                angel_repl_eval(inp, env=self.env)

    do_quit = do_exit
    do_q = do_exit
    do_e = do_exit


def repl():
    """Start Angel REPL."""
    try:
        REPL().cmdloop()
    except KeyboardInterrupt:
        pass
