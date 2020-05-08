import typing as t
from dataclasses import dataclass


@dataclass
class CompilationContext:
    code_lines: t.List[str]
    main_file_hash: str
    mangle_names: bool
