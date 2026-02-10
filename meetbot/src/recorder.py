
import subprocess
import os
import datetime
import time
from pathlib import Path
from .logger import setup_logger
from .config import (
    FFMPEG_CMD, AUDIO_DEVICE_NAME, RECORDINGS_DIR, VIDEO_RECORDING_ENABLED,
    FRAMERATE, AUDIO_FORMAT, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_BITRATE,
    AUDIO_BIT_DEPTH,
)

logger = setup_logger(__name__)

class MeetingRecorder:
    def __init__(self):
        self.process = None
        self.output_file = None
        self._ensure_recordings_dir()

    def _ensure_recordings_dir(self):
        """Creates the recordings directory if it doesn't exist."""
        if not os.path.exists(RECORDINGS_DIR):
            os.makedirs(RECORDINGS_DIR)

    def start_recording(self, window_title: str = None):
        """
        Starts recording audio and optionally video using ffmpeg.
        window_title: The title of the window to capture (exact match required for gdigrab).
                      If None, only audio is recorded (or fails if video is enforced).
        """
        if self.process:
            logger.warning("Recording is already in progress.")
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Determine extension and format
        ext = AUDIO_FORMAT if AUDIO_FORMAT else ("mp4" if VIDEO_RECORDING_ENABLED else "mp3")
        filename = f"meeting_{timestamp}.{ext}"
        self.output_file = os.path.abspath(os.path.join(RECORDINGS_DIR, filename))
        logger.info(f"Preparing to record to: {self.output_file}")

        command = [FFMPEG_CMD]

        # Video Input (gdigrab) - ONLY if enabled AND format is not audio-only like wav/mp3
        is_audio_only = ext in ["wav", "mp3", "aac"]
        
        if VIDEO_RECORDING_ENABLED and window_title and not is_audio_only:
            command.extend([
                "-f", "gdigrab",
                "-framerate", str(FRAMERATE),
                "-i", f"title={window_title}"
            ])
        if VIDEO_RECORDING_ENABLED and not window_title and not is_audio_only:
             logger.warning("Video recording enabled but no window title provided. Falling back to audio only.")

        # Audio Input
        import platform
        system = platform.system()

        if system == "Windows":
            command.extend([
                "-f", "dshow",
                "-thread_queue_size", "1024",
                "-i", f"audio={AUDIO_DEVICE_NAME}"
            ])
        elif system == "Linux":
             # Use PulseAudio
             command.extend([
                 "-f", "pulse",
                 "-thread_queue_size", "1024",
                 "-i", AUDIO_DEVICE_NAME
             ])
        else:
            logger.warning(f"Unsupported OS: {system}. Audio recording might fail.")

        # Audio quality settings
        command.extend([
            "-ar", str(AUDIO_SAMPLE_RATE),  # Sample rate (48 kHz)
            "-ac", str(AUDIO_CHANNELS),      # Channels (mono)
        ])

        # Output codec & format options
        if ext == "wav":
             # 24-bit PCM for higher dynamic range
             command.extend(["-c:a", f"pcm_{AUDIO_BIT_DEPTH}"])
        else:
             # For compressed formats, set bitrate
             command.extend(["-b:a", AUDIO_BITRATE])

        command.extend([
            "-y",  # Overwrite
            self.output_file
        ])

        logger.info(f"Starting recording with command: {' '.join(command)}")
        
        try:
            # shell=False is safer. We assume ffmpeg is in PATH or FFMPEG_CMD is absolute.
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, # Capture stdout/stderr to debug if needed, or set to DEVNULL
                stderr=subprocess.PIPE
            )
            
            # Check if process crashed immediately (e.g. invalid device or window title)
            time.sleep(1)
            if self.process.poll() is not None:
                _, stderr = self.process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                logger.error(f"FFmpeg process terminated immediately. Recording failed.\nError: {error_msg}")
                self.process = None
                return

            logger.info(f"Recording started successfully. Saving to {self.output_file}")

        except FileNotFoundError:
             logger.error(f"FFmpeg not found at '{FFMPEG_CMD}'. Please install FFmpeg or check config.")
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")

    def stop_recording(self):
        """Stops the recording gracefully."""
        if not self.process:
            return

        logger.info("Stopping recording...")
        
        try:
            # Communicate 'q' to ffmpeg to stop gracefully
            self.process.communicate(input=b'q', timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Gentle stop timed out, terminating ffmpeg process...")
            self.process.kill()
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            if self.process:
                self.process.kill()
        
        self.process = None
        logger.info(f"Recording stopped. File saved: {self.output_file}")
