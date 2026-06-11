import sys
from vibecomfy._compile import _graph as _real
sys.modules[__name__] = _real
