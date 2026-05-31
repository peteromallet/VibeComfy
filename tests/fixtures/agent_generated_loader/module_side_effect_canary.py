open("__CANARY_PATH__", "w", encoding="utf-8").write("executed")


def build():
    raise AssertionError("build must not run")
