from subprocess import run


def build():
    return run(["true"], check=True)
