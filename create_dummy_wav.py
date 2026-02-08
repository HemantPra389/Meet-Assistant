import wave
import struct

def create_dummy_wav(filename="dummy_audio.wav", duration=1.0, framerate=44100):
    num_samples = int(duration * framerate)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
        wav_file.setframerate(framerate)
        
        # Generate silence (or simple tone if needed, but silence is enough to check file read)
        data = []
        for i in range(num_samples):
            data.append(struct.pack('<h', 0))
            
        wav_file.writeframes(b''.join(data))
    print(f"Created {filename}")

if __name__ == "__main__":
    create_dummy_wav()
