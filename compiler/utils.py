from . import errors, nodes


def dispatch(dispatcher, key, *args):
    func = dispatcher.get(key)
    if func is None:
        raise errors.AngelNotImplemented(f'cannot dispatch {key}')
    return func(*args)


def get_all_subclasses(cls):
    result = set()
    for subclass in cls.__subclasses__():
        subclass_subclasses = get_all_subclasses(subclass)
        if subclass_subclasses:
            # Don't add subclass that has subclasses.
            result = result.union(subclass_subclasses)
        else:
            result.add(subclass.__name__)
    return result


NODES = get_all_subclasses(nodes.Node)
EXPRS = get_all_subclasses(nodes.Expression)
TYPES = get_all_subclasses(nodes.Type)
ASSIGNMENTS = get_all_subclasses(nodes.AssignmentLeft)
