"""배경 음악 합성 + 내레이션 믹스 + 영상 합치기

실행 (레포 루트):
  .venv/Scripts/python video/audio.py music   → video/audio/music.wav (어쿠스틱 팝 96BPM, 코드로 합성 — 외부 음원 없음)
  .venv/Scripts/python video/audio.py final   → video/audio/mix.wav + video/final.mp4 (frames.mp4 필요)
"""
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).resolve().parent
SR = 44100
BPM = 96
BEAT = 60 / BPM


def timeline():
    js = (HERE / "timeline.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"window\.TIMELINE = (.*);", js, re.S).group(1))


def read_wav(p):
    with wave.open(str(p)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32767
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(1)
        assert w.getframerate() == SR, w.getframerate()
    return a


def write_wav(p, a):
    a = np.clip(a, -1, 1)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def pluck(m, dur=1.2, vel=1.0):
    """우쿨렐레처럼 짧게 튕기는 소리: 배음마다 다른 감쇠"""
    t = np.arange(int(SR * dur)) / SR
    f = hz(m)
    s = sum((0.6 ** (k - 1)) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (3 + 2.2 * k)) for k in range(1, 7))
    atk = np.minimum(1, t / 0.004)
    return vel * 0.25 * s * atk


def noise_hit(dur, decay, hp=0.0, vel=1.0, seed=0):
    rng = np.random.default_rng(seed)
    n = rng.standard_normal(int(SR * dur))
    if hp:  # 간단한 1차 고역 통과
        n = np.diff(n, prepend=0) * hp + n * (1 - hp)
    t = np.arange(len(n)) / SR
    return vel * n * np.exp(-t * decay)


def music(total):
    n = int(SR * (total + 1))
    out = np.zeros(n + SR * 3, dtype=np.float32)

    def add(sig, at):
        i = int(at * SR)
        out[i:i + len(sig)] += sig[: max(0, len(out) - i)]

    # C – G – Am – F (한 마디씩)
    chords = [[60, 64, 67, 72], [55, 59, 62, 67], [57, 60, 64, 69], [53, 57, 60, 65]]
    roots = [36, 43, 45, 41]
    bar, k = 4 * BEAT, 0
    pattern = [0, 2, 1, 3, 2, 1, 3, 2]  # 8분음표 아르페지오
    while k * bar < total + 1:
        c, r, t0 = chords[k % 4], roots[k % 4], k * bar
        for j, idx in enumerate(pattern):
            add(pluck(c[idx], 1.0, 0.9 if j % 2 == 0 else 0.6), t0 + j * BEAT / 2)
        for b in (0, 2):  # 베이스: 1·3박
            tt = np.arange(int(SR * BEAT * 1.8)) / SR
            add(0.32 * np.sin(2 * np.pi * hz(r) * tt) * np.exp(-tt * 2.2) * np.minimum(1, tt / 0.01), t0 + b * BEAT)
        for j in range(16):  # 셰이커: 16분음표
            add(noise_hit(0.06, 70, hp=0.9, vel=0.05 if j % 2 else 0.08, seed=k * 16 + j), t0 + j * BEAT / 4)
        for b in (1, 3):  # 손뼉: 2·4박
            add(noise_hit(0.15, 28, hp=0.6, vel=0.16, seed=999 + k * 2 + b), t0 + b * BEAT)
        k += 1
    out = out[:n]
    t = np.arange(n) / SR
    out *= np.minimum(1, t / 1.5) * np.clip((total + 0.5 - t) / 2.5, 0, 1)
    return out / (np.abs(out).max() + 1e-9) * 0.8


def final():
    tl = timeline()
    total = tl["total"]
    m = read_wav(HERE / "audio" / "music.wav")
    n = int(SR * (total + 0.5))
    m = np.pad(m, (0, max(0, n - len(m))))[:n]
    voice = np.zeros(n, dtype=np.float32)
    speaking = np.zeros(n, dtype=np.float32)
    for s in tl["scenes"]:
        a = read_wav(HERE / "audio" / f"narr_{s['n']:02d}.wav")
        i = int(s["speechStart"] * SR)
        voice[i:i + len(a)] += a[: n - i]
        speaking[i:i + len(a)] = 1
    # 말하는 동안 음악을 낮춤 (0.3초로 부드럽게)
    k = int(0.3 * SR)
    c = np.concatenate([[0], np.cumsum(speaking)])  # 이동 평균 (누적합으로 빠르게)
    idx = np.arange(n)
    lo, hi = np.clip(idx - k // 2, 0, n), np.clip(idx + k // 2, 0, n)
    duck = (c[hi] - c[lo]) / np.maximum(1, hi - lo)
    gain = 0.22 - 0.13 * duck
    mix = voice / (np.abs(voice).max() + 1e-9) * 0.9 + m * gain
    mix = mix / max(1.0, np.abs(mix).max() / 0.97)
    write_wav(HERE / "audio" / "mix.wav", mix)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(HERE / "frames.mp4"), "-i", str(HERE / "audio" / "mix.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(HERE / "final.mp4")], check=True)
    print("완료", HERE / "final.mp4")


if __name__ == "__main__":
    if sys.argv[1] == "music":
        tl = timeline()
        write_wav(HERE / "audio" / "music.wav", music(tl["total"]))
        print("음악", round(tl["total"], 1), "초")
    else:
        final()
