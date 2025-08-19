"""
Media processing for video downloads, transcription, and frame extraction
"""

import os
from pathlib import Path
from typing import Optional, Callable, Dict

import whisper
from config import YT_DLP_PATH, FFMPEG_PATH, FRAMES_DIR_NAME, AUDIO_FILE_NAME, AUDIO_CLIPS_PATH
from utils.logging import log_upgrade
from core.yt_dlp_helper import download_audio_from_url, DownloadResult
from data.settings_manager import settings_manager
from core.proc import run_cmd_safe
from core.strings import safe_strip

class MediaProcessor:
    """Handles video downloads, audio extraction, and transcription"""

    def __init__(self):
        self.whisper_model = None

    def download_video(self, video_id: str, url: str, output_path: Path,
                      progress_callback: Optional[Callable] = None) -> bool:
        """Download video using yt-dlp"""
        try:
            # Note: safe_strip is not strictly needed here as Path handles objects, but good practice.
            output_template = str(output_path / '%(title)s.%(ext)s')

            cmd = [
                YT_DLP_PATH,
                '--no-mtime',
                '-o', output_template,
                url
            ]

            if progress_callback:
                progress_callback("Starting download...")

            returncode, stdout, stderr = run_cmd_safe(cmd)

            if returncode == 0:
                log_upgrade(f"Successfully downloaded video {video_id}")
                return True
            else:
                log_upgrade(f"Download failed for {video_id}: {stderr}")
                return False

        except Exception as e:
            log_upgrade(f"Download error for {video_id}: {e}")
            return False

    def download_video_for_processing(self, video_id: str, url: str,
                                    output_path: Path) -> Optional[Path]:
        """Download video in MP4 format for processing"""
        try:
            video_file = output_path / f"{video_id}.mp4"

            cmd = [
                YT_DLP_PATH,
                '-f', 'mp4',
                '--no-mtime',
                '-o', str(video_file),
                url
            ]

            returncode, stdout, stderr = run_cmd_safe(cmd)

            if returncode == 0 and video_file.exists():
                return video_file
            else:
                log_upgrade(f"Video download failed: {stderr}")
                return None

        except Exception as e:
            log_upgrade(f"Error downloading video for processing: {e}")
            return None

    def extract_keyframes(self, video_path: Path, output_dir: Path,
                         fps: int = 2) -> bool:
        """Extract keyframes from video using ffmpeg"""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            frame_pattern = str(output_dir / '%04d.jpg')

            cmd = [
                FFMPEG_PATH,
                '-y',  # Overwrite output files
                '-i', str(video_path),
                '-vf', f"fps={fps}",
                frame_pattern
            ]

            returncode, stdout, stderr = run_cmd_safe(cmd)

            if returncode == 0:
                log_upgrade(f"Successfully extracted frames to {output_dir}")
                return True
            else:
                log_upgrade(f"Frame extraction failed: {stderr}")
                return False

        except Exception as e:
            log_upgrade(f"Error extracting keyframes: {e}")
            return False

    def extract_audio(self, video_path: Path, audio_path: Path) -> bool:
        """Extract audio from video using ffmpeg"""
        try:
            audio_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                FFMPEG_PATH,
                '-y',  # Overwrite output files
                '-i', str(video_path),
                '-vn',  # No video
                '-ac', '1',  # Mono audio
                '-ar', '16000',  # 16kHz sample rate
                str(audio_path)
            ]

            returncode, stdout, stderr = run_cmd_safe(cmd)

            if returncode == 0:
                log_upgrade(f"Successfully extracted audio to {audio_path}")
                return True
            else:
                log_upgrade(f"Audio extraction failed: {stderr}")
                return False

        except Exception as e:
            log_upgrade(f"Error extracting audio: {e}")
            return False

    def normalize_audio(self, input_path: Path) -> Optional[Path]:
        """
        Normalizes an audio file to 16kHz mono for Whisper.
        Returns the path to the new, normalized file on success.
        """
        try:
            if not input_path.exists():
                log_upgrade(f"Cannot normalize, input file not found: {input_path}")
                return None

            # Create a new path for the normalized file
            output_path = input_path.with_name(f"{input_path.stem}_16k_mono.m4a")

            log_upgrade(f"Normalizing '{input_path}' to '{output_path}'...")

            cmd = [
                FFMPEG_PATH,
                '-y',  # Overwrite output files
                '-i', str(input_path),
                '-ac', '1',  # Mono audio
                '-ar', '16000',  # 16kHz sample rate
                '-c:a', 'aac',
                '-b:a', '128k',
                str(output_path)
            ]

            returncode, stdout, stderr = run_cmd_safe(cmd)

            if returncode == 0:
                log_upgrade(f"Successfully normalized audio to {output_path}")
                return output_path
            else:
                log_upgrade(f"Audio normalization failed for {input_path}: {stderr}")
                return None

        except Exception as e:
            log_upgrade(f"Error normalizing audio: {e}")
            return None

    def download_audio(self,
                       url: str,
                       video_id: str,
                       output_path: Path,
                       *,
                       cookies_path: Optional[str] = None,
                       ui_callbacks: Optional[Dict[str, callable]] = None) -> DownloadResult:
        """
        Downloads audio from a URL using the centralized yt-dlp helper.
        This is the new, robust implementation.
        """
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            preferred_ext = settings_manager.get('preferred_audio_format', 'm4a')

            # The actual download logic is now delegated to the helper
            result = download_audio_from_url(
                url=url,
                video_id=video_id,
                cookies_path=cookies_path,
                outdir=str(output_path),
                preferred_ext=preferred_ext,
                ui_callbacks=ui_callbacks
            )

            if not result.success:
                log_upgrade(f"Audio download failed: {result.error}")

            return result
        except Exception as e:
            log_upgrade(f"Error preparing audio download: {e}")
            return DownloadResult(success=False, filepath=None, error=str(e))

    def transcribe_audio(self, audio_path: Path,
                        progress_callback: Optional[Callable] = None) -> Optional[str]:
        """Transcribe audio using Whisper"""
        try:
            if progress_callback:
                progress_callback("Loading Whisper model...")

            # Load model if not already loaded
            if self.whisper_model is None:
                self.whisper_model = whisper.load_model("tiny")

            if progress_callback:
                progress_callback("Transcribing audio...")

            result = self.whisper_model.transcribe(str(audio_path))

            log_upgrade(f"Successfully transcribed audio from {audio_path}")
            return result["text"]

        except Exception as e:
            log_upgrade(f"Transcription error: {e}")
            return None

    def process_video_for_analysis(self, video_id: str, url: str,
                                  base_output_path: Path,
                                  progress_callback: Optional[Callable] = None) -> dict:
        """Complete video processing pipeline for analysis"""
        results = {
            'video_path': None,
            'frames_dir': None,
            'audio_path': None,
            'success': False
        }

        try:
            # Create output directory
            output_dir = base_output_path / video_id
            output_dir.mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback("Downloading video...")

            # Download video
            video_path = self.download_video_for_processing(video_id, url, output_dir)
            if not video_path:
                return results

            results['video_path'] = video_path

            if progress_callback:
                progress_callback("Extracting frames...")

            # Extract frames
            frames_dir = output_dir / FRAMES_DIR_NAME
            if self.extract_keyframes(video_path, frames_dir):
                results['frames_dir'] = frames_dir

            if progress_callback:
                progress_callback("Extracting audio...")

            # Extract audio
            audio_path = output_dir / AUDIO_FILE_NAME
            if self.extract_audio(video_path, audio_path):
                results['audio_path'] = audio_path

            results['success'] = True
            return results

        except Exception as e:
            log_upgrade(f"Error in video processing pipeline: {e}")
            return results

    def create_safe_filename(self, text: str, max_length: int = 50) -> str:
        """Create safe filename from text"""
        # Remove invalid characters
        safe_chars = []
        for char in text:
            if char.isalnum() or char in (' ', '-', '_'):
                safe_chars.append(char)
            else:
                safe_chars.append('_')

        # Use safe_strip on the input text before processing
        processed_text = safe_strip(text)

        safe_chars = []
        for char in processed_text:
            if char.isalnum() or char in (' ', '-', '_'):
                safe_chars.append(char)
            else:
                safe_chars.append('_')

        safe_name = ''.join(safe_chars)

        # Limit length
        if len(safe_name) > max_length:
            safe_name = safe_name[:max_length].rstrip()

        return safe_name or 'video'

    def get_output_path(self, query: str, video_title: str = "") -> Path:
        """Generate output path based on query and video title"""
        from config import CLIPHUSTLE_BASE_PATH

        safe_query = self.create_safe_filename(query, 30)
        base_path = CLIPHUSTLE_BASE_PATH / safe_query

        if video_title:
            safe_title = self.create_safe_filename(video_title, 20)
            return base_path / safe_title
        else:
            return base_path
