from . import errors


def dispatch(dispatcher, key, *args):
    func = dispatcher.get(key)
    if func is None:
        raise errors.AngelNotImplemented(f'cannot dispatch {key}')
    return func(*args)
