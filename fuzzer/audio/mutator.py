"""
오디오 뮤테이터 — sapphirelab mutator.py와 동일한 패턴.

mutator.py의 Mutator/MUTATOR_MAP/RandomMutatePolicy 구조를 따름.
LLMBackend 불필요 (DSP 기반 변이이므로).

15가지 오디오 변이 전략:
  [Perturbation]  AdversarialNoise, PGDTransfer, PsychoacousticMasking, TimeStretch
  [HiddenSpeech]  UltrasonicEmbed, Backmasking, WhisperOverlay
  [Frequency]     BandAmplify, SpectralWatermark, FormantShift, BandShuffle
  [Confusion]     RoomImpulse, CodecArtifact, Jitter, EnvironmentalNoise
"""

import io
import random
import base64

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, stft, istft


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def audio_to_numpy(data: bytes, target_sr=None):
    """WAV bytes → (numpy float32 mono, sample_rate)."""
    samples, sr = sf.read(io.BytesIO(data), dtype="float32")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    if target_sr and target_sr != sr:
        import librosa
        samples = librosa.resample(samples, orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    return samples, sr


def numpy_to_wav(samples, sr):
    """numpy float32 → WAV bytes."""
    buf = io.BytesIO()
    sf.write(buf, np.clip(samples, -1, 1).astype(np.float32), sr,
             format="WAV", subtype="FLOAT")
    return buf.getvalue()


def wav_to_data_uri(wav_bytes, mime="audio/wav"):
    """WAV bytes → data:audio/wav;base64,... URI (챗봇 attachment용)."""
    return f"data:{mime};base64,{base64.b64encode(wav_bytes).decode()}"


def generate_audio_seeds():
    """기본 오디오 시드 코퍼스 (WAV bytes 리스트). 합성 생성."""
    seeds = []
    # 합성 음성 (포먼트 시뮬레이션)
    for dur in [1.0, 2.0, 3.0, 5.0]:
        sr = 16000
        t = np.linspace(0, dur, int(sr * dur), dtype=np.float32)
        glottal = np.sign(np.sin(2 * np.pi * (120 + 5 * np.sin(2 * np.pi * 5 * t)) * t)) * 0.3
        result = np.zeros_like(t)
        for center, bw in [(700, 100), (1200, 200), (2500, 300)]:
            sos = butter(2, [max(center - bw, 20), min(center + bw, sr // 2 - 1)],
                         btype="bandpass", fs=sr, output="sos")
            result += sosfilt(sos, glottal).astype(np.float32)
        result = result / (np.abs(result).max() + 1e-10) * 0.7
        seeds.append(numpy_to_wav(result, sr))
    # 사인파
    for freq in [440, 1000, 8000]:
        t = np.linspace(0, 2, 32000, dtype=np.float32)
        seeds.append(numpy_to_wav(0.5 * np.sin(2 * np.pi * freq * t), 16000))
    # 무음
    seeds.append(numpy_to_wav(np.zeros(32000, dtype=np.float32), 16000))
    # 백색소음
    seeds.append(numpy_to_wav(np.random.normal(0, 0.3, 32000).astype(np.float32), 16000))
    return seeds


# ---------------------------------------------------------------------------
# Mutator base  (mutator.py의 Mutator와 동일 패턴)
# ---------------------------------------------------------------------------

class AudioMutator:
    """모든 오디오 뮤테이터의 베이스. mutator.py Mutator와 동일 인터페이스."""

    @property
    def name(self):
        return self.__class__.__name__

    def mutate(self, wav_bytes, pool=None):
        """WAV bytes → 변이된 WAV bytes. pool은 시드 리스트(미사용 가능)."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# [Perturbation] 4종
# ---------------------------------------------------------------------------

class AdversarialNoiseMutator(AudioMutator):
    """가우시안 노이즈를 다양한 SNR로 주입."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        snr_db = random.uniform(5, 40)
        rms = np.sqrt(np.mean(samples ** 2)) + 1e-10
        noise = np.random.normal(0, rms / (10 ** (snr_db / 20)), samples.shape).astype(np.float32)
        return numpy_to_wav(samples + noise, sr)


class PGDTransferMutator(AudioMutator):
    """PGD adversarial perturbation — wav2vec2 surrogate transfer attack.
    Carlini & Wagner (2018) 기반. surrogate 특징 공간에서 최대 divergence."""
    _model = None

    def mutate(self, wav_bytes, pool=None):
        import torch, torchaudio
        if PGDTransferMutator._model is None:
            bundle = torchaudio.pipelines.WAV2VEC2_BASE
            PGDTransferMutator._model = bundle.get_model().eval()
            PGDTransferMutator._sr = bundle.sample_rate

        samples, _ = audio_to_numpy(wav_bytes, target_sr=self._sr)
        x = torch.tensor(samples).unsqueeze(0)
        delta = torch.zeros_like(x, requires_grad=True)
        eps, steps, lr = 0.02, 30, 0.001

        for _ in range(steps):
            adv = x + delta
            with torch.no_grad():
                cf, _ = self._model.extract_features(x)
            af, _ = self._model.extract_features(adv)
            loss = -sum(torch.nn.functional.mse_loss(a, c) for a, c in zip(af, cf))
            loss.backward()
            delta.data = torch.clamp(delta.data - lr * delta.grad.sign(), -eps, eps)
            delta.grad.zero_()

        return numpy_to_wav((x + delta).detach().squeeze().numpy(), self._sr)


class PsychoacousticMaskingMutator(AudioMutator):
    """마스킹 임계값 이하 주파수 빈에 인지 불가능 노이즈 주입.
    Schoherr et al. (2019) 기반."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        f, t, Zxx = stft(samples, fs=sr, nperseg=2048)
        mag = np.abs(Zxx)
        pdb = 20 * np.log10(mag + 1e-10)
        threshold = pdb.max(axis=0, keepdims=True) - 32
        below = pdb < threshold
        noise = np.random.uniform(0, mag.max() * 0.01, mag.shape) * np.exp(
            1j * np.random.uniform(-np.pi, np.pi, mag.shape))
        Zxx_m = Zxx.copy()
        Zxx_m[below] += noise[below].astype(Zxx.dtype)
        _, out = istft(Zxx_m, fs=sr, nperseg=2048)
        return numpy_to_wav(out[:len(samples)].astype(np.float32), sr)


class TimeStretchMutator(AudioMutator):
    """시간축 변형으로 ASR 혼동."""
    def mutate(self, wav_bytes, pool=None):
        import librosa
        samples, sr = audio_to_numpy(wav_bytes)
        return numpy_to_wav(librosa.effects.time_stretch(samples, rate=random.uniform(0.7, 1.5)), sr)


# ---------------------------------------------------------------------------
# [HiddenSpeech] 3종
# ---------------------------------------------------------------------------

class UltrasonicEmbedMutator(AudioMutator):
    """초음파 대역(>16kHz)에 AM 변조 명령 삽입. DolphinAttack (Zhang 2017) 기반."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        if sr < 44100:
            import librosa
            samples = librosa.resample(samples, orig_sr=sr, target_sr=44100)
            sr = 44100
        n = len(samples)
        cmd = sosfilt(butter(4, [200, 4000], btype="bandpass", fs=sr, output="sos"),
                      np.random.normal(0, 0.5, n).astype(np.float32))
        t = np.arange(n) / sr
        carrier = np.sin(2 * np.pi * 20000 * t).astype(np.float32)
        mod = carrier * (1.0 + cmd)
        mod = mod / (np.abs(mod).max() + 1e-10) * 0.3
        return numpy_to_wav(np.clip(samples + mod, -1, 1), sr)


class BackmaskingMutator(AudioMutator):
    """구간 역재생(backmasking). 일부 ASR은 역재생 음성도 부분 인식."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        seg = int(len(samples) * 0.2)
        start = random.randint(0, max(len(samples) - seg, 0))
        out = samples.copy()
        out[start:start + seg] = out[start:start + seg][::-1]
        return numpy_to_wav(out, sr)


class WhisperOverlayMutator(AudioMutator):
    """극저볼륨 핑크노이즈 속삭임 오버레이."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        n = len(samples)
        fft = np.fft.rfft(np.random.normal(0, 1, n).astype(np.float32))
        freqs = np.fft.rfftfreq(n); freqs[0] = 1
        pink = np.fft.irfft(fft / np.sqrt(freqs), n=n).astype(np.float32)
        whisper = sosfilt(butter(3, [300, 3000], btype="bandpass", fs=sr, output="sos"), pink)
        whisper = whisper / (np.abs(whisper).max() + 1e-10) * random.uniform(0.005, 0.03)
        return numpy_to_wav(np.clip(samples + whisper, -1, 1), sr)


# ---------------------------------------------------------------------------
# [Frequency] 4종
# ---------------------------------------------------------------------------

class BandAmplifyMutator(AudioMutator):
    """특정 주파수 대역 증폭/감쇠."""
    BANDS = [(0, 300), (300, 1000), (1000, 3000), (3000, 6000), (6000, 12000)]
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        lo, hi = random.choice(self.BANDS)
        gain = 10 ** (random.uniform(-20, 20) / 20)
        fft = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(len(samples), 1.0 / sr)
        fft[(freqs >= lo) & (freqs <= hi)] *= gain
        return numpy_to_wav(np.fft.irfft(fft, n=len(samples)).astype(np.float32), sr)


class SpectralWatermarkMutator(AudioMutator):
    """스펙트로그램 매그니튜드에 랜덤 패턴 임프린트."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        f, t, Z = stft(samples, fs=sr, nperseg=1024)
        mag, phase = np.abs(Z), np.angle(Z)
        pattern = np.random.choice([0, 1], size=Z.shape, p=[0.8, 0.2])
        _, out = istft((mag * (1 + 0.3 * pattern)) * np.exp(1j * phase), fs=sr, nperseg=1024)
        return numpy_to_wav(out[:len(samples)].astype(np.float32), sr)


class FormantShiftMutator(AudioMutator):
    """포먼트(피치) 시프팅 — 화자 특성 변조."""
    def mutate(self, wav_bytes, pool=None):
        import librosa
        samples, sr = audio_to_numpy(wav_bytes)
        return numpy_to_wav(
            librosa.effects.pitch_shift(samples, sr=sr, n_steps=random.uniform(-5, 5)), sr)


class BandShuffleMutator(AudioMutator):
    """주파수 대역 순서 셔플."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        fft = np.fft.rfft(samples)
        nb = 8
        bs = len(fft) // nb
        bands = [fft[i * bs:(i + 1) * bs] for i in range(nb)]
        rem = fft[nb * bs:]
        random.shuffle(bands)
        return numpy_to_wav(
            np.fft.irfft(np.concatenate(bands + [rem]), n=len(samples)).astype(np.float32), sr)


# ---------------------------------------------------------------------------
# [Confusion] 4종
# ---------------------------------------------------------------------------

class RoomImpulseMutator(AudioMutator):
    """합성 룸 임펄스 응답(RIR) 컨볼루션 — 반향 시뮬레이션."""
    ROOMS = [(0.1, "small"), (0.3, "office"), (0.6, "classroom"), (1.2, "hall"), (2.5, "cathedral")]
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        rt60, _ = random.choice(self.ROOMS)
        length = max(int(sr * rt60), 10)
        t = np.arange(length) / sr
        rir = np.random.normal(0, 1, length).astype(np.float32) * np.exp(-6.9 * t / rt60)
        rir[0] = 1.0
        for d in [5, 12, 20, 35]:
            idx = int(sr * d / 1000)
            if idx < length:
                rir[idx] += random.uniform(0.3, 0.7)
        rir /= np.abs(rir).max() + 1e-10
        conv = np.convolve(samples, rir, "full")[:len(samples)]
        return numpy_to_wav((conv / (np.abs(conv).max() + 1e-10)).astype(np.float32), sr)


class CodecArtifactMutator(AudioMutator):
    """저비트 양자화 + 다운샘플링으로 코덱 아티팩트."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        bits = random.choice([4, 6, 8, 12])
        lv = 2 ** bits
        q = np.round(samples * (lv / 2)) / (lv / 2)
        if random.random() > 0.5:
            import librosa
            low = random.choice([4000, 8000, 11025])
            q = librosa.resample(librosa.resample(q, orig_sr=sr, target_sr=low),
                                 orig_sr=low, target_sr=sr)[:len(samples)]
        return numpy_to_wav(np.clip(q, -1, 1).astype(np.float32), sr)


class JitterMutator(AudioMutator):
    """시간축 미세 변동(jitter)."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        ms = int(sr * 10 / 1000)
        cs = sr // 10
        chunks = [samples[i:i + cs] for i in range(0, len(samples), cs)]
        out = []
        for c in chunks:
            s = random.randint(-ms, ms)
            out.append(np.concatenate([np.zeros(s, dtype=np.float32), c]) if s > 0
                       else c[abs(s):] if s < 0 else c)
        r = np.concatenate(out)[:len(samples)]
        if len(r) < len(samples):
            r = np.pad(r, (0, len(samples) - len(r)))
        return numpy_to_wav(r.astype(np.float32), sr)


class EnvironmentalNoiseMutator(AudioMutator):
    """환경 소음 오버레이 (white/pink/brown/babble/traffic)."""
    def mutate(self, wav_bytes, pool=None):
        samples, sr = audio_to_numpy(wav_bytes)
        ntype = random.choice(["white", "pink", "brown", "babble", "traffic"])
        snr_db = random.uniform(0, 20)
        n = len(samples)
        w = np.random.normal(0, 1, n).astype(np.float32)
        if ntype == "white":
            noise = w
        elif ntype == "pink":
            ft = np.fft.rfft(w); fr = np.fft.rfftfreq(n); fr[0] = 1
            noise = np.fft.irfft(ft / np.sqrt(fr), n=n).astype(np.float32)
        elif ntype == "brown":
            noise = np.cumsum(w * 0.01).astype(np.float32)
        elif ntype == "babble":
            noise = sum(sosfilt(butter(3, [200, 3500], btype="bandpass", fs=sr, output="sos"),
                                np.random.normal(0, 1, n).astype(np.float32)) for _ in range(6)) / 6
        else:
            noise = sosfilt(butter(4, 500, btype="lowpass", fs=sr, output="sos"), w)
        rms_s = np.sqrt(np.mean(samples ** 2)) + 1e-10
        noise = noise / (np.sqrt(np.mean(noise ** 2)) + 1e-10) * rms_s / (10 ** (snr_db / 20))
        return numpy_to_wav(np.clip(samples + noise, -1, 1).astype(np.float32), sr)


# ---------------------------------------------------------------------------
# Registry + Policy  (mutator.py MUTATOR_MAP / RandomMutatePolicy 동일 패턴)
# ---------------------------------------------------------------------------

AUDIO_MUTATOR_MAP = {
    'AdversarialNoise':      AdversarialNoiseMutator,
    'PGDTransfer':           PGDTransferMutator,
    'PsychoacousticMasking': PsychoacousticMaskingMutator,
    'TimeStretch':           TimeStretchMutator,
    'UltrasonicEmbed':       UltrasonicEmbedMutator,
    'Backmasking':           BackmaskingMutator,
    'WhisperOverlay':        WhisperOverlayMutator,
    'BandAmplify':           BandAmplifyMutator,
    'SpectralWatermark':     SpectralWatermarkMutator,
    'FormantShift':          FormantShiftMutator,
    'BandShuffle':           BandShuffleMutator,
    'RoomImpulse':           RoomImpulseMutator,
    'CodecArtifact':         CodecArtifactMutator,
    'Jitter':                JitterMutator,
    'EnvironmentalNoise':    EnvironmentalNoiseMutator,
}


class AudioMutatePolicy:
    """mutator.py RandomMutatePolicy와 동일 인터페이스.
    mutate(wav_bytes, pool) → (mutated_wav_bytes, mutator_name)
    """
    def __init__(self, mutators):
        self.mutators = mutators

    def mutate(self, wav_bytes, pool=None):
        mutator = random.choice(self.mutators)
        return mutator.mutate(wav_bytes, pool), mutator.name


class AudioRetryPolicy:
    """mutator.py RetryMutatePolicy와 동일 인터페이스.
    거부된 오디오를 다른 뮤테이터로 재변형.
    """
    def __init__(self, mutators):
        self.mutators = mutators

    def mutate(self, wav_bytes, pool=None):
        mutator = random.choice(self.mutators)
        return mutator.mutate(wav_bytes, pool), mutator.name


# ---------------------------------------------------------------------------
# Policy builders  (mutator.py build_policy_from_config 동일 패턴)
# ---------------------------------------------------------------------------

def build_audio_policy_from_config(cfg):
    """AudioFuzz config → AudioMutatePolicy 생성."""
    names = cfg.get('Strategies', list(AUDIO_MUTATOR_MAP.keys()))
    mutators = [AUDIO_MUTATOR_MAP[n]() for n in names if n in AUDIO_MUTATOR_MAP]
    if not mutators:
        raise ValueError(f"유효한 전략 없음. 선택 가능: {list(AUDIO_MUTATOR_MAP)}")
    return AudioMutatePolicy(mutators)


def build_audio_retry_policy_from_config(cfg):
    """AudioFuzz config → AudioRetryPolicy 생성."""
    names = cfg.get('RetryStrategies', list(AUDIO_MUTATOR_MAP.keys()))
    mutators = [AUDIO_MUTATOR_MAP[n]() for n in names if n in AUDIO_MUTATOR_MAP]
    if not mutators:
        mutators = [AUDIO_MUTATOR_MAP[n]() for n in AUDIO_MUTATOR_MAP]
    return AudioRetryPolicy(mutators)
