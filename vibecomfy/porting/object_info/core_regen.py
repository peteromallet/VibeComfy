"""Explicit heavy ComfyUI core object_info regeneration.

This module is intentionally imported only by ``schemas regen-core``. It creates
a pinned, pip-installable ComfyUI environment and executes that environment to
capture core ``object_info``. Ordinary cache reads and refresh paths must remain
offline consumers of existing JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CoreObjectInfoRunner:
    """Create a pinned ComfyUI environment and return its ``object_info``."""

    comfy_version: str
    runner: CommandRunner | None = None
    env_root: Path | None = None
    package_template: str = "comfyui=={version}"

    def capture(self) -> dict[str, Any]:
        root = self.env_root
        if root is None:
            with tempfile.TemporaryDirectory(prefix=f"vibecomfy-core-{self.comfy_version}-") as tmp:
                return self._capture_in_root(Path(tmp))
        root.mkdir(parents=True, exist_ok=True)
        return self._capture_in_root(root)

    def _capture_in_root(self, root: Path) -> dict[str, Any]:
        env_dir = root / "venv"
        if not (env_dir / "pyvenv.cfg").is_file():
            venv.EnvBuilder(with_pip=True, clear=False).create(env_dir)
        python = _venv_python(env_dir)
        runner = self.runner or _run_checked
        package = self.package_template.format(version=self.comfy_version)

        runner([str(python), "-m", "pip", "install", "--disable-pip-version-check", package])
        proc = runner([str(python), "-c", _OBJECT_INFO_CAPTURE_SCRIPT])
        payload = json.loads(proc.stdout)
        if not isinstance(payload, dict):
            raise ValueError("ComfyUI object_info capture did not return a JSON object")
        return payload


def capture_core_object_info(
    comfy_version: str,
    *,
    runner: CommandRunner | None = None,
    env_root: str | Path | None = None,
    package_template: str = "comfyui=={version}",
) -> dict[str, Any]:
    """Capture core ComfyUI ``object_info`` from a pinned pip environment."""

    return CoreObjectInfoRunner(
        comfy_version=comfy_version,
        runner=runner,
        env_root=Path(env_root) if env_root is not None else None,
        package_template=package_template,
    ).capture()


def _venv_python(env_dir: Path) -> Path:
    if sys.platform == "win32":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def _run_checked(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


_OBJECT_INFO_CAPTURE_SCRIPT = textwrap.dedent(
    """
    import json
    import threading
    import time
    import urllib.request

    try:
        import server
        import nodes
    except Exception as exc:
        raise SystemExit(f"failed to import ComfyUI modules: {exc}") from exc

    # Newer ComfyUI versions expose object_info helpers through PromptServer.
    # Run the minimal server in-process and query the same HTTP surface used by
    # runtime consumers so node registration side effects are represented.
    try:
        import main
    except Exception:
        main = None

    if main is None:
        if hasattr(nodes, "NODE_CLASS_MAPPINGS"):
            object_info = {}
            for class_type, cls in nodes.NODE_CLASS_MAPPINGS.items():
                if hasattr(cls, "INPUT_TYPES"):
                    inputs = cls.INPUT_TYPES()
                else:
                    inputs = {}
                object_info[class_type] = {
                    "input": inputs,
                    "input_order": {
                        "required": list(inputs.get("required", {}).keys()),
                        "optional": list(inputs.get("optional", {}).keys()),
                    },
                    "output": list(getattr(cls, "RETURN_TYPES", []) or []),
                    "output_name": list(getattr(cls, "RETURN_NAMES", []) or []),
                    "output_is_list": list(getattr(cls, "OUTPUT_IS_LIST", []) or []),
                    "name": class_type,
                    "display_name": getattr(cls, "DISPLAY_NAME", class_type),
                    "category": getattr(cls, "CATEGORY", ""),
                    "description": getattr(cls, "DESCRIPTION", ""),
                    "function": getattr(cls, "FUNCTION", ""),
                    "python_module": ".",
                }
            print(json.dumps(object_info, sort_keys=True))
            raise SystemExit(0)
        raise SystemExit("ComfyUI modules did not expose NODE_CLASS_MAPPINGS")

    port = 8188
    thread = threading.Thread(target=main.main, kwargs={"listen": "127.0.0.1", "port": port}, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/object_info"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                print(response.read().decode("utf-8"))
                raise SystemExit(0)
        except Exception:
            time.sleep(0.5)
    raise SystemExit("timed out waiting for ComfyUI /object_info")
    """
).strip()
