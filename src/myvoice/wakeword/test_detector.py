import numpy as np

from myvoice.audio.recorder import AudioRecorder
from myvoice.wakeword.detector import WakeWordDetector


def main():
    recorder = AudioRecorder()
    detector = WakeWordDetector()

    buffer = np.array([], dtype=np.float32)

    print("Listening for 'Hey Jarvis'...")

    for chunk in recorder.stream():
        buffer = np.concatenate([buffer, chunk])

        while len(buffer) >= 1280:
            wake_chunk = buffer[:1280]
            buffer = buffer[1280:]

            detected = detector.process(wake_chunk)

            if detected:
                print("✅ WAKE WORD DETECTED")


if __name__ == "__main__":
    main()