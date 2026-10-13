import os
import sys
import numpy as np
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from guardian.voice.tts import EdgeTTSSynthesizer
from guardian.voice.wake import OpenWakeWordDetector
import soundfile as sf
import io

def synthesize_audio(text, voice="en-US-GuyNeural"):
    tts = EdgeTTSSynthesizer(voice=voice)
    result = tts.synthesize(text)
    return result.audio_bytes

def test_wake_word(audio_bytes, threshold):
    detector = OpenWakeWordDetector(wake_word="hey_mycroft", threshold=threshold)
    
    # Need to read as 16kHz mono int16
    data, samplerate = sf.read(io.BytesIO(audio_bytes))
    if len(data.shape) > 1:
        data = data[:, 0]
    
    # Resample not needed as EdgeTTS usually outputs 16kHz or 24kHz. Let's assume sf gives us float32.
    # Convert to int16
    audio_int16 = (data * 32767).astype(np.int16)
    
    # Process in chunks
    chunk_size = 1280
    for i in range(0, len(audio_int16), chunk_size):
        chunk = audio_int16[i:i+chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        
        res = detector.process_chunk(chunk)
        if res.detected:
            return True, res.score
    return False, 0.0

def main():
    positives = [
        "Hey Mycroft, tell me a joke.",
        "Hey Mycroft, what's the weather like?",
        "Hey Mycroft, execute order 66."
    ]
    
    negatives = [
        "Hey Michael, tell me a joke.",
        "Hi Mycroft, how are you?",
        "Hey Microsoft, open word.",
        "A regular sentence with no wake word."
    ]
    
    print("Synthesizing audio samples...")
    pos_audio = [synthesize_audio(p) for p in positives]
    neg_audio = [synthesize_audio(n) for n in negatives]
    
    print("\nTuning threshold...")
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
        print(f"\n--- Threshold {threshold} ---")
        
        pos_detected = 0
        for i, audio in enumerate(pos_audio):
            detected, score = test_wake_word(audio, threshold)
            print(f"Positive '{positives[i]}': {'DETECTED' if detected else 'missed'} (score {score:.2f})")
            if detected: pos_detected += 1
            
        neg_detected = 0
        for i, audio in enumerate(neg_audio):
            detected, score = test_wake_word(audio, threshold)
            print(f"Negative '{negatives[i]}': {'FALSE ALARM' if detected else 'passed'} (score {score:.2f})")
            if detected: neg_detected += 1
            
        print(f"Summary for {threshold}: True Positive Rate: {pos_detected}/{len(positives)}, False Positive Rate: {neg_detected}/{len(negatives)}")

if __name__ == "__main__":
    main()
