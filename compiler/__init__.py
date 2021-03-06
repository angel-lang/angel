import cmd
import sys
import traceback
import typing as t
import subprocess
import itertools

from . import (
    nodes,
    parsers,
    translators,
    generators,
    environment,
    errors,
    clarification,
    repl_evaluation,
    analysis,
)
from .utils import get_hash
from .context import Context


DEBUG = False


def compile_file(file_path: str) -> str:
    """Translate Angel code contained in `file_path` into C++ code and returns it."""
    with open(file_path) as file:
        contents = file.read()
    return compile_string(contents)


def _handle_angel_error(exception: errors.AngelError) -> t.NoReturn:
    if DEBUG:
        raise exception
    else:
        print(str(exception))
        print()
        sys.exit(1)


def _run_frontend(string: str, compilation_context: Context, env: t.Optional[environment.Environment] = None) -> t.Iterable[nodes.Node]:
    parser = parsers.Parser()
    clarifier = clarification.Clarifier(compilation_context)
    analyzer = analysis.Analyzer(compilation_context, env=env)
    clarified_ast: t.Iterable[nodes.Node] = clarifier.clarify_ast(parser.parse(string))
    for module_name, module_content in compilation_context.imported_lines.items():
        module_hash = compilation_context.module_hashs[module_name]
        compilation_context.main_hash = module_hash
        clarified_ast = itertools.chain(
            clarifier.clarify_ast(parser.parse(module_content)), clarified_ast
        )
    yield from analyzer.analyze_ast(clarified_ast)


def compile_string(string: str, mangle_names: bool = True) -> str:
    """Translate Angel code represented by `string` into C++ code and returns it."""
    lines = string.split("\n")
    hash_ = get_hash(string)

    compilation_context = Context(lines, hash_, mangle_names)
    translator = translators.Translator(compilation_context)
    try:
        cpp_ast = translator.translate(_run_frontend(string, compilation_context))
    except errors.AngelError as e:
        _handle_angel_error(e)
    else:
        return generators.generate_cpp(cpp_ast)


def angel_repl_eval(string: str, env: environment.Environment) -> t.Any:
    """Evaluate Angel code represented by `string` and returns the result."""
    lines = string.split("\n")
    compilation_context = Context(lines, main_hash="", mangle_names=False)
    repl_evaluator = repl_evaluation.REPLEvaluator(compilation_context, env=env)
    try:
        return repl_evaluator.estimate_ast(_run_frontend(string, compilation_context, env=env))
    except errors.AngelError as e:
        _handle_angel_error(e)


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
                ["clang-format", "--assume-filename=a.cpp"],
                input=compile_string("\n".join(self.input_), mangle_names=False),
                encoding="utf-8",
                stdout=subprocess.PIPE,
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
