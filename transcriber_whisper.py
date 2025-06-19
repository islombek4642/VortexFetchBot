from faster_whisper import WhisperModel

MODEL_SIZE = "base"  # or "small", "medium", "large-v2"

# Model is loaded once per process
_model = None

def get_model():
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model

def transcribe_whisper_sync(audio_path):
    model = get_model()
    segments, info = model.transcribe(audio_path, beam_size=1)
    text = " ".join([segment.text.strip() for segment in segments])
    return text

def transcribe_whisper_stream(audio_path):
    model = get_model()
    segments, info = model.transcribe(audio_path, beam_size=1)
    for idx, segment in enumerate(segments, start=1):
        yield idx, len(segments), segment.text.strip()

def transcribe_whisper_full(audio_path):
    model = get_model()
    segments, info = model.transcribe(audio_path, beam_size=1)
    text = " ".join([segment.text.strip() for segment in segments])
    detected_lang = info.get("language", "unknown")
    return text, detected_lang 