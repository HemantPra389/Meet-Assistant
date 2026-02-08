import io
import os
import sys
import argparse
import logging
# import speech_recognition as sr # Removed
import numpy as np

# Suppress Hugging Face warnings and HTTP logs
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["CTRANSLATE2_ROOT_LOG_LEVEL"] = "ERROR"

# Suppress httpx and other verbose loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from faster_whisper import WhisperModel

# Configure logging - only show warnings/errors
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def transcribe_audio(file_path, model):
    """
    Transcribes the given audio file using faster-whisper 'base' model.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    try:
        logger.info(f"Starting transcription for: {file_path}")
        segments, info = model.transcribe(file_path, beam_size=5)

        logger.info(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

        print("\n--- Transcription Start ---\n")
        # Segments is a generator, so code will block here processing audio
        for segment in segments:
            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
        print("\n--- Transcription End ---\n")

        logger.info("Transcription completed successfully.")

    except Exception as e:
        logger.error(f"An error occurred during transcription: {e}")
        # Not exiting here to allow caller to handle if needed, or just return

import pyaudio
import wave

def transcribe_mic(model, device_index=None):
    """
    Listens to the microphone using PyAudio and transcribes in real-time.
    """
    # PyAudio configuration
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    RECORD_SECONDS = 3  # Shorter chunks for faster response
    ENERGY_THRESHOLD = 20 # Very low threshold for quiet mics

    p = pyaudio.PyAudio()

    try:
        # If no device index provided, use default
        kwargs = {
            'format': FORMAT,
            'channels': CHANNELS,
            'rate': RATE,
            'input': True,
            'frames_per_buffer': CHUNK
        }
        if device_index is not None:
            kwargs['input_device_index'] = int(device_index)
            logger.info(f"Using device ID: {device_index}")

        stream = p.open(**kwargs)
    except Exception as e:
        logger.error(f"Could not open microphone stream: {e}")
        return

    print("Listening... Speak now! (Press Ctrl+C to stop)")
    
    try:
        while True:
            frames = []
            
            # Record for a few seconds
            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                except KeyboardInterrupt:
                    raise
            
            audio_data = b''.join(frames)
            
            # Simple energy check to skip silence
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_np**2))

            if rms > ENERGY_THRESHOLD:
                # Transcribe
                # Convert raw bytes to file-like WAV object
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(audio_data)
                wav_buffer.seek(0)
                
                segments, info = model.transcribe(wav_buffer, beam_size=5)
                
                for segment in segments:
                    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except:
            pass
        p.terminate()

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio file or microphone input using faster-whisper.")
    parser.add_argument("--file", nargs='?', help="Path to the input audio file. If omitted, uses microphone.")
    parser.add_argument("--device", help="Device ID for microphone (optional).")
    
    args = parser.parse_args()

    # Initialize model
    print("Loading model...")
    try:
        model = WhisperModel("base", device="auto", compute_type="int8")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)

    if args.file:
        transcribe_audio(args.file, model)
    else:
        transcribe_mic(model, device_index=args.device)

if __name__ == "__main__":
    main()
