getattr(__builtins__, "__import__")("os")


def build():
    raise AssertionError("build must not run")
