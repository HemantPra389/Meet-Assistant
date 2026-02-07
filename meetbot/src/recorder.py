
import subprocess
import os
import datetime
import time
from pathlib import Path
from .logger import setup_logger
from .config import FFMPEG_CMD, AUDIO_DEVICE_NAME, RECORDINGS_DIR, VIDEO_RECORDING_ENABLED, FRAMERATE

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
        ext = "mp4" if VIDEO_RECORDING_ENABLED else "mp3"
        self.output_file = os.path.join(RECORDINGS_DIR, f"meeting_{timestamp}.{ext}")

        command = [FFMPEG_CMD]

        # Video Input (gdigrab)
        if VIDEO_RECORDING_ENABLED and window_title:
            command.extend([
                "-f", "gdigrab",
                "-framerate", str(FRAMERATE),
                "-i", f"title={window_title}"
            ])
        elif VIDEO_RECORDING_ENABLED and not window_title:
             logger.warning("Video recording enabled but no window title provided. Falling back to audio only.")

        # Audio Input (dshow)
        command.extend([
            "-f", "dshow",
            "-i", f"audio={AUDIO_DEVICE_NAME}"
        ])

        # Output options
        command.extend([
            "-y", # Overwrite
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
