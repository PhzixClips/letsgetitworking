"""
A helper module for interacting with the yt-dlp command-line tool.
"""

import json
import os
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

def get_yt_dlp_version() -> Optional[str]:
    """
    Retrieves the current version of the yt-dlp executable.
    Returns the version string or None if it fails.
    """
    if not YT_DLP_PATH:
        return None

    returncode, stdout, stderr = run_cmd_safe([YT_DLP_PATH, "--version"])

    if returncode == 0:
        return safe_strip(stdout)
    else:
        log_upgrade(f"Failed to get yt-dlp version: {stderr}")
        return None

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


def run_metadata_dump(url: str, cookies: Optional[str] = None, extra_args: Optional[List[str]] = None) -> ExtractionResult:
    """
    Runs `yt-dlp --dump-json` for a given URL and returns the parsed data.
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
    ui_callbacks: Optional[Dict[str, callable]] = None
) -> DownloadResult:
    """
    Downloads audio from a URL using a multi-step fallback strategy.
    Designed to be run in a worker thread.
    """
    logger = log_upgrade
    logger(f"Audio download start: url={url}, video_id={video_id}")

    output_template = os.path.join(outdir, "%(id)s__%(title).200s.%(ext)s")

    base_cmd = [
        YT_DLP_PATH,
        '--no-playlist', '--no-warnings', '--no-call-home',
        '--restrict-filenames',
        '--no-simulate', '--no-part', '--newline',
        '--print', 'after_move:filepath',
        '--print', 'filename',
        '--extractor-args', 'facebook:lang=en_US',
        '-o', output_template
    ]

    # --- Attempt A: Native Audio-Only ---
    logger("Attempting audio-only download (Attempt A)")
    cmd_a = base_cmd + ['-f', 'bestaudio/bestaudio*']

    safe_cookies_path = safe_strip(cookies_path)
    if safe_cookies_path:
        cmd_a.extend(['--cookies', safe_cookies_path])
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

        # --- Attempt B: Muxed Fallback + Post-processing ---
        if not is_ffmpeg_available():
            logger("ffmpeg not found, aborting download.")
            if ui_callbacks and 'on_ffmpeg_missing':
                ui_callbacks['on_ffmpeg_missing']()
            return DownloadResult(success=False, filepath=None, error="ffmpeg not found. Set path in Settings.")

        logger("Attempting muxed download with audio extraction (Attempt B)")
        cmd_b = base_cmd + [
            '-f', 'best/best*',
            '--retries', '3', '--fragment-retries', '3',
            '--postprocessor-args', 'ExtractAudio:-vn',
            '--extract-audio', '--audio-format', preferred_ext, '--audio-quality', '0',
        ]
        if safe_cookies_path:
            cmd_b.extend(['--cookies', safe_cookies_path])
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

        # --- Attempt C: Canonicalization Retry ---
        else:
            logger(f"Attempt B failed. Stderr: {stderr_b}")
            canonical_url = canonicalize_facebook_url(url)
            if canonical_url and canonical_url != url:
                logger(f"Attempting canonical URL retry (Attempt C) with: {canonical_url}")
                cmd_b[-1] = canonical_url
                rc_c, stdout_c, stderr_c = run_cmd_safe(cmd_b)
                if rc_c == 0:
                    final_path_str = resolve_final_output_path(stdout_c, outdir, video_id)
                    if final_path_str:
                        logger(f"Successfully downloaded on canonical URL retry: {final_path_str}")
                        return DownloadResult(success=True, filepath=Path(final_path_str), error=None)
                    else:
                        logger(f"Canonical retry (C) seemed to succeed but could not find file from output: {stdout_c}")
                        return DownloadResult(success=False, filepath=None, error="Canonical retry successful, but could not locate the output file.")
                else:
                    logger(f"Canonical URL retry failed. Final error: {stderr_c}")
                    return DownloadResult(success=False, filepath=None, error=stderr_c)

            return DownloadResult(success=False, filepath=None, error=stderr_b)

    # --- Handle other errors from Attempt A ---
    if "login required" in stderr_a.lower() or "you must log in" in stderr_a.lower():
        logger("FB: login required")
        if ui_callbacks and 'on_login_required':
            ui_callbacks['on_login_required']()
        return DownloadResult(success=False, filepath=None, error="Login required. Please provide cookies.txt and retry.")

    if "cannot parse data" in stderr_a.lower() or "extractorerror" in stderr_a.lower():
        logger("FB: Extractor error, attempting auto-update.")
        if ui_callbacks and 'on_update_start':
            ui_callbacks['on_update_start']()

        update_result = update_yt_dlp()
        logger(f"yt-dlp update result: {update_result.message}")

        if update_result.success and update_result.updated:
            if ui_callbacks and 'on_update_complete':
                ui_callbacks['on_update_complete']()
            logger("Retrying download after update.")
            return download_audio_from_url(url, video_id, cookies_path=cookies_path, outdir=outdir, preferred_ext=preferred_ext, ui_callbacks=ui_callbacks)
        else:
            short_err = f"Extractor error and update failed or was not available. Original error: {stderr_a}"
            logger(short_err)
            return DownloadResult(success=False, filepath=None, error=short_err)

    logger(f"FB audio download failed: {stderr_a}")
    return DownloadResult(success=False, filepath=None, error=stderr_a)
