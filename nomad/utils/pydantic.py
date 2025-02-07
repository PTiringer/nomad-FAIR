from pydantic.v1.error_wrappers import ErrorWrapper


class CustomErrorWrapper(ErrorWrapper):
    """ErrorWrapper that supports dict conversion via dict(instance)."""

    def __iter__(self):
        """Yields (key, value) pairs for dict conversion: error and location."""
        yield 'msg', str(self.exc)
        yield 'loc', self.loc_tuple()

    def __getitem__(self, key):
        """Enables dictionary-style access: error['loc'] and error['msg']."""
        if key == 'loc':
            return self.loc_tuple()
        elif key == 'msg':
            return str(self.exc)
        raise KeyError(key)
