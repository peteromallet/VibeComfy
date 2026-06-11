from vibecomfy.porting.wrappers.discovery import *

# Keep the original __all__
from vibecomfy.porting.wrappers.discovery import __all__  # noqa: F401

# Re-export module-level imports not in __all__ but accessed externally
import vibecomfy.porting.wrappers.discovery as _disc
urllib = _disc.urllib
json = _disc.json
