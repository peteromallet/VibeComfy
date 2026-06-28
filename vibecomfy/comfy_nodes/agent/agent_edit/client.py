from __future__ import annotations

from typing import Callable

DeepSeekClient = Callable[[list[dict[str, str]]], dict[str, str]]
