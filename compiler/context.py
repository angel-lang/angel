import typing as t

from dataclasses import dataclass


@dataclass
class Context:
    lines: t.List[str]
    main_hash: str
    mangle_names: bool
