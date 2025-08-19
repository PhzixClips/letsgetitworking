"""
A helper module for interacting with the yt-dlp command-line tool.
"""

import subprocess
import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from config import YT_DLP_PATH
from data.settings_manager import settings_manager
from utils.logging import log_upgrade
from integrations.facebook_helper import canonicalize_facebook_url


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


def is_ffmpeg_available() -> bool:
    """
    Checks if the ffmpeg executable is available and can be run.
    """
    ffmpeg_path = settings_manager.get('ffmpeg_path', 'ffmpeg')
    try:
        # We run 'ffmpeg -version', which is a quick and reliable way to check.
        # We capture output to prevent it from printing to the console.
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        # If check=True, it will raise CalledProcessError for non-zero exit codes.
        # So, if we get here, it means ffmpeg ran successfully.
        return True
    except FileNotFoundError:
        # This is the most common error: the executable doesn't exist.
        log_upgrade(f"ffmpeg not found at path: {ffmpeg_path}")
        return False
    except subprocess.CalledProcessError as e:
        # This means ffmpeg ran but returned an error code.
        log_upgrade(f"ffmpeg check failed with exit code {e.returncode}: {e.stderr}")
        return False
    except Exception as e:
        # Catch any other unexpected errors.
        log_upgrade(f"An unexpected error occurred during ffmpeg check: {e}")
        return False


def download_audio_from_url(
    url: str,
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
    logger = log_upgrade # Use the existing logger for now
    logger(f"Audio download start (FB): url={url}")

    # --- Helper to run a yt-dlp command ---
    def _run_yt_dlp(cmd: List[str]) -> (bool, str, str):
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True
            )
            return True, process.stdout.strip(), process.stderr.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stdout.strip(), e.stderr.strip()
        except FileNotFoundError:
            return False, "", "yt-dlp executable not found."
        except Exception as e:
            return False, "", f"An unexpected error occurred: {e}"

    # --- Attempt A: Native Audio-Only ---
    logger("Attempting audio-only download (Attempt A)")
    output_template = Path(outdir) / "%(title).200s.%(ext)s"
    cmd_a = [
        YT_DLP_PATH,
        '-f', 'bestaudio/bestaudio*',
        '--no-playlist', '--no-warnings', '--no-call-home',
        '--extractor-args', 'facebook:lang=en_US',
        '-o', str(output_template)
    ]
    if cookies_path:
        cmd_a.extend(['--cookies', cookies_path])
    cmd_a.append(url)

    success, stdout_a, stderr_a = _run_yt_dlp(cmd_a)

    if success:
        # Find the downloaded file
        # This is tricky as yt-dlp determines the final name
        # We can parse stdout or scan the directory
        try:
            # yt-dlp usually prints the destination file path
            filepath_str = ""
            for line in stdout_a.splitlines():
                if "[download] Destination:" in line:
                    filepath_str = line.split("Destination:")[1].strip()
                elif "has already been downloaded" in line:
                    filepath_str = line.split("[download]")[1].split("has already been downloaded")[0].strip()

            if filepath_str and Path(filepath_str).exists():
                logger(f"Successfully downloaded audio-only file: {filepath_str}")
                return DownloadResult(success=True, filepath=Path(filepath_str), error=None)
        except Exception as e:
            logger(f"Could not parse filepath from yt-dlp output, but download was successful. Error: {e}")
            # Fallback: still return success but no filepath for now
            return DownloadResult(success=True, filepath=None, error="Could not determine output file path.")


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
        output_template_b = Path(outdir) / "%(title).200s.%(ext)s"
        cmd_b = [
            YT_DLP_PATH,
            '-f', 'best/best*',
            '--no-playlist', '--no-warnings', '--no-call-home',
            '--extractor-args', 'facebook:lang=en_US',
            '--no-part', '--retries', '3', '--fragment-retries', '3',
            '--postprocessor-args', 'ExtractAudio:-vn',
            '--extract-audio', '--audio-format', preferred_ext, '--audio-quality', '0',
            '-o', str(output_template_b)
        ]
        if cookies_path:
            cmd_b.extend(['--cookies', cookies_path])
        cmd_b.append(url)

        success_b, stdout_b, stderr_b = _run_yt_dlp(cmd_b)

        if success_b:
            try:
                # When using --extract-audio, yt-dlp prints the final audio file path
                filepath_str = ""
                for line in stdout_b.splitlines():
                    if "[ExtractAudio] Destination:" in line:
                        filepath_str = line.split("Destination:")[1].strip()
                        break
                if filepath_str and Path(filepath_str).exists():
                    logger(f"Successfully downloaded and extracted audio: {filepath_str}")
                    return DownloadResult(success=True, filepath=Path(filepath_str), error=None)
                else:
                    raise ValueError("Could not find extracted audio file path in output.")
            except Exception as e:
                logger(f"Could not parse extracted audio filepath from yt-dlp output. Error: {e}")
                return DownloadResult(success=True, filepath=None, error="Could not determine output file path.")

        # --- Attempt C: Canonicalization Retry ---
        else:
            logger(f"Attempt B failed. Stderr: {stderr_b}")
            canonical_url = canonicalize_facebook_url(url)
            if canonical_url and canonical_url != url:
                logger(f"Attempting canonical URL retry (Attempt C) with: {canonical_url}")
                cmd_b[-1] = canonical_url # Replace URL in command
                success_c, stdout_c, stderr_c = _run_yt_dlp(cmd_b)
                if success_c:
                    try:
                        filepath_str = ""
                        for line in stdout_c.splitlines():
                            if "[ExtractAudio] Destination:" in line:
                                filepath_str = line.split("Destination:")[1].strip()
                                break
                        if filepath_str and Path(filepath_str).exists():
                            logger(f"Successfully downloaded on canonical URL retry: {filepath_str}")
                            return DownloadResult(success=True, filepath=Path(filepath_str), error=None)
                        else:
                            raise ValueError("Could not find extracted audio file path in output.")
                    except Exception as e:
                        logger(f"Could not parse filepath from canonical retry output. Error: {e}")
                        return DownloadResult(success=True, filepath=None, error="Could not determine output file path.")
                else:
                    logger(f"Canonical URL retry failed. Final error: {stderr_c}")
                    return DownloadResult(success=False, filepath=None, error=stderr_c)

            # If no canonical URL or it failed, return original error from attempt B
            return DownloadResult(success=False, filepath=None, error=stderr_b)

    # --- Handle other errors from Attempt A ---
    if "login required" in stderr_a.lower() or "you must log in" in stderr_a.lower():
        logger("FB: login required")
        if ui_callbacks and 'on_login_required':
            # This is tricky. The worker thread can't block on UI.
            # The UI should be prompted, get new cookies, and then re-trigger the download.
            # For now, we just report the error.
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
            # Retry the whole function
            logger("Retrying download after update.")
            return download_audio_from_url(url, cookies_path=cookies_path, outdir=outdir, preferred_ext=preferred_ext, ui_callbacks=ui_callbacks)
        else:
            short_err = f"Extractor error and update failed or was not available. Original error: {stderr_a}"
            logger(short_err)
            return DownloadResult(success=False, filepath=None, error=short_err)


    # If we've reached here, it's a generic failure from Attempt A
    logger(f"FB audio download failed: {stderr_a}")
    return DownloadResult(success=False, filepath=None, error=stderr_a)
