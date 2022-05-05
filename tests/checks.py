


def is_immutable(new, immutable_attrs):
    sub = new()
    it = iter(immutable_attrs)
    for atr in it:
        try:
            setattr(sub, atr, getattr(sub, atr, None))
        except AttributeError:
            continue
        else:
            raise AssertionError(f"attribute `{sub.__class__.__qualname__}.{atr}` is mutable")
    return sub