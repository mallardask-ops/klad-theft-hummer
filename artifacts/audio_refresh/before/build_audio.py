"""Build UI/music cues, retaining imported CC0 recordings when available."""
from pathlib import Path
import math
import random
import shutil
import struct
import wave

RATE = 22050
OUT = Path(__file__).resolve().parents[1] / "assets" / "audio"
OUT.mkdir(parents=True, exist_ok=True)
RECORDED = OUT / "recorded" / "processed"
rng = random.Random(272)


def write(name, seconds, synth):
    recording = RECORDED / f"{name}.wav"
    if recording.exists():
        shutil.copyfile(recording, OUT / recording.name)
        return
    samples = []
    for i in range(int(seconds * RATE)):
        sample = max(-0.85, min(0.85, synth(i / RATE, i)))
        samples.append(int(sample * 32767))
    with wave.open(str(OUT / f"{name}.wav"), "wb") as target:
        target.setparams((1, 2, RATE, len(samples), "NONE", "not compressed"))
        target.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def tone(freq, t):
    return math.sin(math.tau * freq * t)


def noise():
    return rng.uniform(-1, 1)


write("step", 0.12, lambda t, i: noise() * math.exp(-t * 40) * 0.35)
write("swing", 0.34, lambda t, i: noise() * math.sin(math.pi * t / 0.34) ** 3 * 0.17)
write("impact", 0.24, lambda t, i: (tone(75, t) * 0.6 + noise() * 0.32) * math.exp(-t * 23))
write("crash", 0.65, lambda t, i: (noise() * 0.7 + tone(48, t) * 0.25) * math.exp(-t * 7))
write("door", 0.28, lambda t, i: (noise() * 0.28 + tone(92, t) * 0.5) * math.exp(-t * 29))
write("hurt", 0.35, lambda t, i: (tone(160 - t * 130, t) + tone(240, t) * 0.3) * 0.28 * math.exp(-t * 9))
write("ui", 0.075, lambda t, i: tone(660, t) * 0.18 * math.exp(-t * 35))
write("pickup", 0.24, lambda t, i: tone(550 if t < 0.12 else 880, t) * 0.22 * math.exp(-t * 6))
write("mission_start", 0.8, lambda t, i: (tone(147, t) + tone(220, t) * 0.4) * math.sin(math.pi * t / 0.8) * 0.2)
write("mission_pass", 1.8, lambda t, i: tone([392, 494, 587, 784, 587, 784][min(5, int(t / 0.3))], t) * 0.4 * math.exp(-(t % 0.3) * 7))
write("fail", 1.5, lambda t, i: (tone(155 - t * 40, t) + tone(116, t)) * 0.18 * math.exp(-t * 2))
write("engine", 2, lambda t, i: tone(55, t) * 0.23 + tone(110, t) * 0.09 + tone(165, t) * 0.025)
write("siren", 4, lambda t, i: tone(540 + 150 * math.sin(math.tau * t / 2), t) * 0.17)
wind = 0


def ambience(t, i):
    global wind
    wind = wind * 0.985 + noise() * 0.015
    return wind * 0.65 + tone(86, t) * 0.018


write("ambience", 8, ambience)
BEAT = 0.48
BASS = [55, 55, 65.406, 55, 73.416, 55, 49, 49, 55, 55, 65.406, 55, 82.407, 73.416, 65.406, 49]
MELODY = [220, 0, 261.626, 0, 293.665, 261.626, 220, 0, 196, 220, 0, 329.628, 293.665, 0, 261.626, 196]


def radio(t, i):
    beat = int(t / BEAT) % 16
    local = t % BEAT
    bass = tone(BASS[beat], t) * 0.16 * min(1, local * 45) * math.exp(-local * 3)
    kick = tone(45 + 75 * math.exp(-local * 45), local) * 0.33 * math.exp(-local * 27)
    hat = noise() * 0.055 * math.exp(-(t % (BEAT / 2)) * 120)
    snare = noise() * 0.13 * math.exp(-local * 22) if beat % 4 in (1, 3) else 0
    mel = tone(MELODY[beat], t) * 0.075 * math.exp(-local * 9) if MELODY[beat] else 0
    pad = (tone(110, t) + tone(130.813, t) + tone(164.814, t)) * 0.018
    return bass + kick + hat + snare + mel + pad


write("radio", BEAT * 16, radio)
for recording in RECORDED.glob("*.wav"):
    shutil.copyfile(recording, OUT / recording.name)
static_path = RECORDED / "radio_static.wav"
if static_path.exists():
    with wave.open(str(OUT / "radio.wav"), "rb") as music_file:
        music_params = music_file.getparams()
        music_samples = list(struct.unpack(f"<{music_file.getnframes()}h", music_file.readframes(music_file.getnframes())))
    with wave.open(str(static_path), "rb") as static_file:
        static_samples = struct.unpack(f"<{static_file.getnframes()}h", static_file.readframes(static_file.getnframes()))
    for offset_seconds in (0.0, BEAT * 8):
        offset = int(offset_seconds * RATE)
        for i, sample in enumerate(static_samples[:int(RATE * .32)]):
            j = (offset + i) % len(music_samples)
            envelope = math.sin(math.pi * i / max(1, int(RATE * .32) - 1)) ** 2
            music_samples[j] = max(-30000, min(30000, music_samples[j] + round(sample * .16 * envelope)))
    with wave.open(str(OUT / "radio.wav"), "wb") as music_file:
        music_file.setparams(music_params)
        music_file.writeframes(struct.pack(f"<{len(music_samples)}h", *music_samples))
print(f"Built {len(list(OUT.glob('*.wav')))} WAV assets; {len(list(RECORDED.glob('*.wav')))} are imported recordings")
