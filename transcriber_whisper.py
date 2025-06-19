import whisper
from concurrent.futures import ProcessPoolExecutor
import os

MODEL_SIZE = "base"  # or "small", "medium", "large"
_model = None

def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(MODEL_SIZE)
    return _model

def transcribe_whisper_sync(audio_path):
    model = get_model()
    result = model.transcribe(audio_path)
    return result['text']

def transcribe_files_parallel(audio_paths):
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(transcribe_whisper_sync, path) for path in audio_paths]
        results = []
        for future in futures:
            results.append(future.result())
        return results 