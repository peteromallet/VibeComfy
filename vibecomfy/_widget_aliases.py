import sys
from vibecomfy._compile import _widgets as _real
sys.modules[__name__] = _real
