import sys
from vibecomfy._compile import _resolve as _real
sys.modules[__name__] = _real
