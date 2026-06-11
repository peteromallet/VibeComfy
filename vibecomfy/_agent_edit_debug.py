from vibecomfy.cli._debug import *
from vibecomfy.cli._debug import main  # noqa: F401 - not in __all__ but used by __main__

if __name__ == "__main__":
    raise SystemExit(main())
