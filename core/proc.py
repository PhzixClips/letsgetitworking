from subprocess import Popen, PIPE, STDOUT
from typing import List, Optional, Tuple

def run_cmd_safe(args: List[str], cwd: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[int, str, str]:
    """
    Run a command and return (returncode, stdout, stderr).
    Robust on Windows: safe Unicode decoding and no console popups.
    """
    # Windows flag to prevent console window flashing
    creationflags = 0
    try:
        import subprocess
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    except Exception:
        pass

    # Use text mode with explicit encoding and errors='replace'
    proc = Popen(
        args,
        cwd=cwd,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except Exception:
        proc.kill()
        out, err = proc.communicate()

    # Always return strings; never None
    out = out if isinstance(out, str) else ""
    err = err if isinstance(err, str) else ""
    return proc.returncode, out, err
