"""
Candado por voz — grabá tu frase y desbloqueá ArgusAdmin.
Huella local (3 muestras + vector medio) + hash estable en Render.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from .config_local import config_dir, load

_PROFILE = config_dir() / 'voice_profile.json'
_SAMPLES_DIR = config_dir() / 'voice_samples'
_MIN_SAMPLES = 3
_FINGERPRINT_VERSION = 2
_CHUNKS = 96
_FEATURE_DIM = _CHUNKS * 2 + 2  # 194 — fijo para que enroll y unlock coincidan


class VoiceProfileOutdated(Exception):
    """Perfil guardado con otro algoritmo; hay que Regrabar voz."""


def _voice_threshold() -> float:
    try:
        v = float(load().get('voice_threshold', 0.45))
        return min(0.85, max(0.30, v))
    except (TypeError, ValueError):
        return 0.45


def voice_threshold_percent() -> int:
    return int(_voice_threshold() * 100)


def _normalize_audio(data: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(data))) + 1e-9
    if peak > 0.01:
        data = data / peak * 0.92
    return data.astype(np.float32)


def fingerprint_from_wav(path: str | Path) -> np.ndarray:
    import wave
    with wave.open(str(path), 'rb') as w:
        n = w.getnframes()
        raw = w.readframes(n)
        sw = w.getsampwidth()
    dtype = np.int16 if sw == 2 else np.int8
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if data.size < 800:
        raise ValueError('Audio demasiado corto — hablá más fuerte y más cerca del mic.')
    rms = float(np.sqrt(np.mean(data ** 2)))
    if rms < 80:
        raise ValueError(
            'Casi no se escuchó tu voz. Subí el volumen del micrófono o acercate al mic.'
        )
    data = _normalize_audio(data)
    if data.size > 16000 * 20:
        data = data[:: max(1, data.size // 160000)]
    step = max(1, len(data) // _CHUNKS)
    feats: list[float] = []
    for i in range(_CHUNKS):
        seg = data[i * step : (i + 1) * step]
        if seg.size < 2:
            feats.extend([0.0, 0.0])
        else:
            feats.append(float(np.sqrt(np.mean(seg ** 2))))
            zc = np.sum(np.abs(np.diff(np.sign(seg)))) / (2 * seg.size)
            feats.append(float(zc))
    feats.append(float(np.mean(data)))
    feats.append(float(np.std(data)))
    v = np.array(feats, dtype=np.float32)
    if v.shape[0] != _FEATURE_DIM:
        raise RuntimeError(f'Huella interna inválida ({v.shape[0]} != {_FEATURE_DIM})')
    norm = np.linalg.norm(v) + 1e-9
    return v / norm


def fingerprint_hash(vec: np.ndarray) -> str:
    return hashlib.sha256(vec.tobytes()).hexdigest()


def _vec_dim(vec) -> int:
    try:
        return len(vec)
    except TypeError:
        return 0


def _profile_is_current(prof: dict) -> bool:
    if prof.get('fingerprint_version') != _FINGERPRINT_VERSION:
        return False
    for v in prof.get('vectors') or []:
        if _vec_dim(v) != _FEATURE_DIM:
            return False
    mv = prof.get('mean_vector')
    if mv and _vec_dim(mv) != _FEATURE_DIM:
        return False
    return True


def profile_needs_reenroll() -> bool:
    prof = _load_profile()
    if not prof.get('vectors'):
        return False
    return not _profile_is_current(prof)


def _ensure_profile_current(prof: dict) -> None:
    if not _profile_is_current(prof):
        raise VoiceProfileOutdated(
            'Tu perfil de voz es de una versión anterior.\n'
            'Usá «Regrabar voz» y grabá las 3 muestras de nuevo.'
        )


def _unit(vec: np.ndarray) -> np.ndarray:
    return vec / (np.linalg.norm(vec) + 1e-9)


def _similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape[0] != b.shape[0]:
        return 0.0
    return float(np.dot(_unit(a), _unit(b)))


def record_wav(seconds: float = 4.5, rate: int = 16000) -> Path:
    _SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    path = _SAMPLES_DIR / f'sample_{int(time.time() * 1000)}.wav'
    try:
        import sounddevice as sd
        audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype='int16')
        sd.wait()
        with __import__('wave').open(str(path), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(audio.tobytes())
        fingerprint_from_wav(path)
        return path
    except ImportError:
        pass
    except ValueError:
        raise
    except Exception as e:
        err = str(e).lower()
        if 'device' in err or 'portaudio' in err:
            raise RuntimeError(
                'Micrófono no disponible. Conectá el headset y probá de nuevo.'
            ) from e
        raise
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        with sr.Microphone() as src:
            r.adjust_for_ambient_noise(src, duration=0.4)
            audio = r.listen(src, timeout=seconds + 6, phrase_time_limit=seconds + 2)
        with open(path, 'wb') as f:
            f.write(audio.get_wav_data(convert_rate=rate))
        fingerprint_from_wav(path)
        return path
    except ImportError:
        raise ImportError(
            'Instalá micrófono: pip install sounddevice numpy\n'
            'O alternativa: pip install SpeechRecognition pyaudio'
        ) from None
    except sr.WaitTimeoutError:
        raise RuntimeError('No escuché nada. Hablá cuando aparezca el cuadro de grabación.') from None


def reset_profile() -> None:
    phrase = load().get('phrase', 'desbloqueo argus')
    _save_profile({
        'vectors': [],
        'hashes': [],
        'phrase': phrase,
        'server_synced': False,
        'fingerprint_version': _FINGERPRINT_VERSION,
    })


def enroll_sample(wav_path: Path) -> None:
    vec = fingerprint_from_wav(wav_path)
    prof = _load_profile()
    if prof.get('vectors') and not _profile_is_current(prof):
        reset_profile()
        prof = _load_profile()
    prof['fingerprint_version'] = _FINGERPRINT_VERSION
    prof['vectors'].append(vec.tolist())
    prof['hashes'].append(fingerprint_hash(vec))
    prof['server_synced'] = False
    _save_profile(prof)


def finalize_profile() -> str:
    prof = _load_profile()
    _ensure_profile_current(prof)
    vectors = [v for v in (prof.get('vectors') or []) if _vec_dim(v) == _FEATURE_DIM]
    if len(vectors) < _MIN_SAMPLES:
        return ''
    arr = np.array(vectors, dtype=np.float32)
    mean = np.mean(arr, axis=0)
    mean = _unit(mean)
    h = fingerprint_hash(mean)
    prof['mean_vector'] = mean.tolist()
    prof['primary_hash'] = h
    prof['fingerprint_version'] = _FINGERPRINT_VERSION
    hashes = list(dict.fromkeys([h] + list(prof.get('hashes') or [])))
    prof['hashes'] = hashes
    _save_profile(prof)
    return h


def all_fingerprint_hashes() -> list[str]:
    prof = _load_profile()
    out: list[str] = []
    for h in prof.get('hashes') or []:
        if h and h not in out:
            out.append(h)
    ph = (prof.get('primary_hash') or '').strip()
    if ph and ph not in out:
        out.insert(0, ph)
    return out


def mark_server_synced() -> None:
    prof = _load_profile()
    prof['server_synced'] = True
    _save_profile(prof)


def is_server_synced() -> bool:
    return bool(_load_profile().get('server_synced'))


def _load_profile() -> dict:
    if _PROFILE.is_file():
        try:
            raw = _PROFILE.read_text(encoding='utf-8').strip()
            if raw:
                return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {
        'vectors': [],
        'hashes': [],
        'phrase': load().get('phrase', 'desbloqueo argus'),
        'server_synced': False,
        'fingerprint_version': _FINGERPRINT_VERSION,
    }


def _save_profile(prof: dict) -> None:
    _PROFILE.write_text(json.dumps(prof), encoding='utf-8')


def _mean_vector(prof: dict) -> np.ndarray | None:
    mv = prof.get('mean_vector')
    if mv and _vec_dim(mv) == _FEATURE_DIM:
        return _unit(np.array(mv, dtype=np.float32))
    vectors = [v for v in (prof.get('vectors') or []) if _vec_dim(v) == _FEATURE_DIM]
    if not vectors:
        return None
    mean = np.mean(np.array(vectors, dtype=np.float32), axis=0)
    return _unit(mean)


def is_enrolled() -> bool:
    if profile_needs_reenroll():
        return False
    prof = _load_profile()
    n = len([v for v in (prof.get('vectors') or []) if _vec_dim(v) == _FEATURE_DIM])
    if n >= _MIN_SAMPLES and not prof.get('primary_hash'):
        finalize_profile()
        prof = _load_profile()
    return n >= _MIN_SAMPLES and bool(prof.get('primary_hash'))


def verify_wav(wav_path: Path, threshold: float | None = None) -> tuple[bool, float, str]:
    prof = _load_profile()
    _ensure_profile_current(prof)
    vectors = [v for v in (prof.get('vectors') or []) if _vec_dim(v) == _FEATURE_DIM]
    if len(vectors) < _MIN_SAMPLES:
        return False, 0.0, ''
    thr = threshold if threshold is not None else _voice_threshold()
    probe = fingerprint_from_wav(wav_path)
    best = 0.0
    mean = _mean_vector(prof)
    if mean is not None:
        best = _similarity(probe, mean)
    for stored in vectors:
        best = max(best, _similarity(probe, np.array(stored, dtype=np.float32)))
    ok = best >= thr
    fp = (prof.get('primary_hash') or '').strip() or finalize_profile()
    return ok, best, fp


def primary_fingerprint_hash() -> str:
    prof = _load_profile()
    if profile_needs_reenroll():
        return ''
    ph = (prof.get('primary_hash') or '').strip()
    if ph:
        return ph
    return finalize_profile()
