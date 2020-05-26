import typing as t

from dataclasses import dataclass, field


@dataclass
class Context:
    lines: t.List[str]
    main_hash: str
    mangle_names: bool
    module_hashs: t.Dict[str, str] = field(default_factory=dict)
    imported_lines: t.Dict[str, str] = field(default_factory=dict)
