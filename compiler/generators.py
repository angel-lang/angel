import typing as t

from . import cpp_nodes


def generate_cpp(nodes: t.List[cpp_nodes.Node]) -> str:
    return "\n".join(node.to_code() for node in nodes)
