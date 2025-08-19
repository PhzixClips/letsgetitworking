"""
A helper module for interacting with the yt-dlp command-line tool.
"""

import subprocess
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from config import YT_DLP_PATH
from utils.logging import log_upgrade

@dataclass
class UpdateResult:
    """Represents the result of a yt-dlp update check."""
    success: bool
    updated: bool
    message: str

@dataclass
class ExtractionResult:
    """Represents the result of a metadata extraction."""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]

def get_yt_dlp_version() -> Optional[str]:
    """
    Retrieves the current version of the yt-dlp executable.
    Returns the version string or None if it fails.
    """
    if not YT_DLP_PATH:
        return None
    try:
        result = subprocess.run(
            [YT_DLP_PATH, "--version"],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log_upgrade(f"Failed to get yt-dlp version: {e}")
        return None

def update_yt_dlp() -> UpdateResult:
    """
    Updates the yt-dlp executable to the latest version using the '-U' flag.
    Returns an UpdateResult object with the outcome.
    """
    if not YT_DLP_PATH:
        return UpdateResult(success=False, updated=False, message="yt-dlp path not configured.")
    try:
        result = subprocess.run(
            [YT_DLP_PATH, "-U"],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        output = result.stdout.strip()
        if "is up to date" in output:
            return UpdateResult(success=True, updated=False, message=output)
        elif "Updated" in output:
            return UpdateResult(success=True, updated=True, message=output)
        else:
            return UpdateResult(success=True, updated=False, message=output)
    except subprocess.CalledProcessError as e:
        error_message = f"Update command failed with exit code {e.returncode}.\nStderr: {e.stderr.strip()}"
        return UpdateResult(success=False, updated=False, message=error_message)
    except FileNotFoundError:
        return UpdateResult(success=False, updated=False, message="yt-dlp executable not found.")
    except Exception as e:
        return UpdateResult(success=False, updated=False, message=f"An unexpected error occurred: {e}")

def run_metadata_dump(url: str, cookies: Optional[str] = None, extra_args: Optional[List[str]] = None) -> ExtractionResult:
    """
    Runs `yt-dlp --dump-json` for a given URL and returns the parsed data.

    This is a wrapper that centralizes the call to yt-dlp for metadata extraction.
    """
    if not YT_DLP_PATH:
        return ExtractionResult(success=False, data=None, error="yt-dlp path not configured.")

    command = [
        YT_DLP_PATH,
        '--dump-json',
        '--no-warnings',
        '--no-call-home',
        '--concurrent-fragments', '4',
    ]
    if cookies:
        command.extend(['--cookies', cookies])
    if extra_args:
        command.extend(extra_args)

    command.append(url)

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        return ExtractionResult(success=True, data=json.loads(process.stdout), error=None)
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip()
        return ExtractionResult(success=False, data=None, error=error_output)
    except json.JSONDecodeError:
        return ExtractionResult(success=False, data=None, error="Failed to parse yt-dlp JSON output.")
    except Exception as e:
        return ExtractionResult(success=False, data=None, error=f"An unexpected error occurred: {e}")
