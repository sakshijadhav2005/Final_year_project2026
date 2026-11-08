"""Speech spans from the audio, and provenance placing words on speech time."""

from pydub import AudioSegment
from pydub.generators import Sine

from app.providers.vertex_stt import _speech_spans
from app.services.provenance import timed_words


def _tone(ms: int) -> AudioSegment:
    return Sine(440).to_audio_segment(duration=ms).set_frame_rate(16000).set_channels(1)


def _silence(ms: int) -> AudioSegment:
    return AudioSegment.silent(duration=ms, frame_rate=16000)


def test_speech_spans_skip_pauses_but_not_short_gaps() -> None:
    audio = _tone(2000) + _silence(1000) + _tone(1000) + _silence(200) + _tone(1000)
    spans = _speech_spans(audio, offset_sec=100.0)
    # The 1 s pause splits the speech; the 200 ms gap between "words" does not.
    assert spans == [[100.0, 102.0], [103.0, 105.2]]


def test_speech_spans_of_silence_are_empty() -> None:
    assert _speech_spans(_silence(3000), offset_sec=0.0) == []


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


def test_words_skip_pauses_when_segment_has_speech_spans() -> None:
    text = _words(80)
    seg = {"text": text, "start": 0.0, "end": 100.0, "speech": [[0.0, 40.0], [60.0, 100.0]]}
    times = [t for _, t in timed_words(text, [seg])]
    assert times[0] == 0.0
    assert times[40] == 40.0  # last word before the pause
    assert times[41] == 61.0  # first word after it: the 20 s pause holds no words
    assert times[79] == 99.0


def test_words_spread_evenly_without_speech_spans() -> None:
    text = _words(80)
    times = [t for _, t in timed_words(text, [{"text": text, "start": 0.0, "end": 100.0}])]
    assert times[40] == 50.0
    assert times[41] == 51.25


def test_bad_speech_spans_fall_back_to_even_spread() -> None:
    text = _words(10)
    seg = {"text": text, "start": 0.0, "end": 10.0, "speech": [["x"]]}
    assert [t for _, t in timed_words(text, [seg])][5] == 5.0
