"""
A helper module for interacting with the yt-dlp command-line tool.
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from config import YT_DLP_PATH
from data.settings_manager import settings_manager
from utils.logging import log_upgrade
from integrations.facebook_helper import canonicalize_facebook_url
from core.proc import run_cmd_safe
from core.strings import safe_strip
from core.file_utils import resolve_final_output_path


@dataclass
class DownloadResult:
    """Represents the result of a download operation."""
    success: bool
    filepath: Optional[Path]
    error: Optional[str]

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

def get_yt_dlp_version(engine: str = 'exe') -> Optional[str]:
    """
    Retrieves the current version of the yt-dlp executable or module.
    Returns the version string or None if it fails.
    """
    if engine == 'exe':
        if not YT_DLP_PATH:
            return None
        cmd = [YT_DLP_PATH, "--version"]
    else: # module
        cmd = [sys.executable, "-m", "yt_dlp", "--version"]

    returncode, stdout, stderr = run_cmd_safe(cmd)

    if returncode == 0:
        return safe_strip(stdout)
    else:
        log_upgrade(f"Failed to get yt-dlp version for engine={engine}: {stderr}")
        return None

def get_yt_dlp_module_version() -> Optional[str]:
    """Convenience function to get the module version."""
    return get_yt_dlp_version(engine='module')

def update_yt_dlp_module(force_master: bool = False) -> UpdateResult:
    """
    Updates the yt-dlp Python module using pip.
    """
    if force_master:
        log_upgrade("Updating yt-dlp module to master branch...")
        cmd = [sys.executable, "-m", "pip", "install", "-U", "git+https://github.com/yt-dlp/yt-dlp@master"]
    else:
        log_upgrade("Updating yt-dlp module...")
        cmd = [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"]

    returncode, stdout, stderr = run_cmd_safe(cmd)

    if returncode == 0:
        return UpdateResult(success=True, updated=True, message=stdout)
    else:
        return UpdateResult(success=False, updated=False, message=stderr)

def update_yt_dlp() -> UpdateResult:
    """
    Updates the yt-dlp executable to the latest version using the '-U' flag.
    Returns an UpdateResult object with the outcome.
    """
    if not YT_DLP_PATH:
        return UpdateResult(success=False, updated=False, message="yt-dlp path not configured.")

    returncode, stdout, stderr = run_cmd_safe([YT_DLP_PATH, "-U"])

    if returncode == 0:
        output = safe_strip(stdout)
        if "is up to date" in output:
            return UpdateResult(success=True, updated=False, message=output)
        elif "Updated" in output:
            return UpdateResult(success=True, updated=True, message=output)
        else:
            return UpdateResult(success=True, updated=False, message=output)
    else:
        error_message = f"Update command failed with exit code {returncode}.\nStderr: {stderr}"
        return UpdateResult(success=False, updated=False, message=error_message)


def run_metadata_dump(url: str, cookies: Optional[str] = None, extra_args: Optional[List[str]] = None, engine: str = 'exe') -> ExtractionResult:
    """
    Runs `yt-dlp --dump-json` for a given URL and returns the parsed data.
    """
    if engine == 'exe':
        if not YT_DLP_PATH:
            return ExtractionResult(success=False, data=None, error="yt-dlp path not configured.")
        command = [YT_DLP_PATH]
    else:
        command = [sys.executable, "-m", "yt_dlp"]

    command.extend([
        '--dump-json',
        '--no-warnings',
        '--no-call-home',
        '--concurrent-fragments', '4',
    ])

    safe_cookies_path = safe_strip(cookies)
    if safe_cookies_path:
        command.extend(['--cookies', safe_cookies_path])
    if extra_args:
        command.extend(extra_args)

    command.append(url)

    returncode, stdout, stderr = run_cmd_safe(command)

    if returncode == 0:
        try:
            return ExtractionResult(success=True, data=json.loads(stdout), error=None)
        except json.JSONDecodeError:
            return ExtractionResult(success=False, data=None, error="Failed to parse yt-dlp JSON output.")
    else:
        return ExtractionResult(success=False, data=None, error=stderr)


def is_ffmpeg_available() -> bool:
    """
    Checks if the ffmpeg executable is available and can be run.
    """
    ffmpeg_path = settings_manager.get('ffmpeg_path', 'ffmpeg')
    returncode, stdout, stderr = run_cmd_safe([ffmpeg_path, "-version"])

    if returncode != 0:
        log_upgrade(f"ffmpeg check failed. rc={returncode}, stderr={stderr}")
        return False
    return True


def download_audio_from_url(
    url: str,
    video_id: str,
    *,
    cookies_path: Optional[str],
    outdir: str,
    preferred_ext: str = "m4a",
    engine: str = 'exe',
    user_agent: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
    ui_callbacks: Optional[Dict[str, callable]] = None
) -> DownloadResult:
    """
    Downloads audio from a URL using a multi-step fallback strategy.
    Designed to be run in a worker thread.
    """
    logger = log_upgrade
    logger(f"Audio download start: url={url}, video_id={video_id}, engine={engine}")

    output_template = os.path.join(outdir, "%(id)s__%(title).200s.%(ext)s")

    if engine == 'exe':
        base_cmd_prefix = [YT_DLP_PATH]
    else:
        base_cmd_prefix = [sys.executable, "-m", "yt_dlp"]

    base_cmd_suffix = [
        '--no-playlist', '--no-warnings', '--no-call-home',
        '--restrict-filenames',
        '--no-simulate', '--no-part', '--newline',
        '--retries', '3', '--fragment-retries', '3',
        '--print', 'after_move:filepath',
        '--print', 'filename',
        '--extractor-args', 'facebook:lang=en_US',
        '-o', output_template
    ]
    base_cmd = base_cmd_prefix + base_cmd_suffix

    if user_agent:
        base_cmd.extend(['--user-agent', user_agent])

    # --- Attempt A: Native Audio-Only ---
    logger("Attempting audio-only download (Attempt A)")
    cmd_a = base_cmd + ['-f', 'bestaudio/bestaudio*']

    safe_cookies_path = safe_strip(cookies_path)
    safe_cookies_browser = safe_strip(cookies_from_browser)
    if safe_cookies_path:
        cmd_a.extend(['--cookies', safe_cookies_path])
    elif safe_cookies_browser and safe_cookies_browser != 'none':
        cmd_a.extend(['--cookies-from-browser', safe_cookies_browser])

    cmd_a.append(url)

    rc_a, stdout_a, stderr_a = run_cmd_safe(cmd_a)

    if rc_a == 0:
        final_path_str = resolve_final_output_path(stdout_a, outdir, video_id)
        if final_path_str:
            logger(f"Successfully downloaded audio-only file: {final_path_str}")
            return DownloadResult(success=True, filepath=Path(final_path_str), error=None)
        else:
            logger(f"Download (A) seemed to succeed but could not find file from output: {stdout_a}")
            return DownloadResult(success=False, filepath=None, error="Download successful, but could not locate the output file.")

    # --- Analyze Failure of Attempt A ---
    if "requested format not available" in stderr_a.lower() or "no audio-only formats found" in stderr_a.lower():
        logger("FB: no audio-only format; falling back to muxed+extract")
        if ui_callbacks and 'on_fallback':
            ui_callbacks['on_fallback']("FB: no audio-only stream; downloading muxed and extracting audio…")

        if not is_ffmpeg_available():
            logger("ffmpeg not found, aborting download.")
            if ui_callbacks and 'on_ffmpeg_missing':
                ui_callbacks['on_ffmpeg_missing']()
            return DownloadResult(success=False, filepath=None, error="ffmpeg not found. Set path in Settings.")

        logger("Attempting muxed download with audio extraction (Attempt B)")
        cmd_b = base_cmd + [
            '-f', 'best/best*',
            '--postprocessor-args', 'ExtractAudio:-vn',
            '--extract-audio', '--audio-format', preferred_ext, '--audio-quality', '0',
        ]
        if safe_cookies_path:
            cmd_b.extend(['--cookies', safe_cookies_path])
        elif safe_cookies_browser and safe_cookies_browser != 'none':
            cmd_b.extend(['--cookies-from-browser', safe_cookies_browser])

        cmd_b.append(url)

        rc_b, stdout_b, stderr_b = run_cmd_safe(cmd_b)

        if rc_b == 0:
            final_path_str = resolve_final_output_path(stdout_b, outdir, video_id)
            if final_path_str:
                logger(f"Successfully downloaded and extracted audio: {final_path_str}")
                return DownloadResult(success=True, filepath=Path(final_path_str), error=None)
            else:
                logger(f"Extraction (B) seemed to succeed but could not find file from output: {stdout_b}")
                return DownloadResult(success=False, filepath=None, error="Extraction successful, but could not locate the output file.")

        return DownloadResult(success=False, filepath=None, error=stderr_b)

    # --- Handle other errors from Attempt A ---
    # These are returned directly to the controller (e.g. FacebookAnalysisTask) to handle
    return DownloadResult(success=False, filepath=None, error=stderr_a)
