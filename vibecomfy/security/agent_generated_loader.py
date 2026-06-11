import sys
from vibecomfy.loader import agent_generated_loader as _real
sys.modules[__name__] = _real
