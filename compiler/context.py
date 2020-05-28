import typing as t
from dataclasses import dataclass, field

from . import nodes


@dataclass
class Context:
    lines: t.List[str]
    main_hash: str
    mangle_names: bool
    module_hashs: t.Dict[str, str] = field(default_factory=dict)
    imported_lines: t.Dict[str, str] = field(default_factory=dict)
    template_types: t.List[t.Optional[nodes.Type]] = field(default_factory=list)
