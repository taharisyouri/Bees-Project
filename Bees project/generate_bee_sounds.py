import os
import math
import random
import wave
import struct

SR = 44100
DURATION = 2.5  # seconds

BEE_IDS = [
    "bumbleBee",
    "carpenterBee",
    "cicadakiller",
    "dirtdauber",
    "honeyBee",
    "hoverfly",
    "paperwasp",
    "yellowjacket",
]

# different base buzz frequencies so each sounds a bit different
BASE_FREQ = {
    "bumbleBee": 180,
    "carpenterBee": 165,
    "cicadakiller": 220,
    "dirtdauber": 195,
    "honeyBee": 200,
    "hoverfly": 240,
    "paperwasp": 210,
    "yellowjacket": 230,
}

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def write_wav(path, samples, sr=SR):
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(clamp(s, -1.0, 1.0) * 32767)))

def make_buzz(bee_id: str, seconds=DURATION, sr=SR):
    n = int(seconds * sr)
    base = BASE_FREQ.get(bee_id, 200)

    # slow amplitude modulation (wing “throb” feel)
    am_rate = random.uniform(18, 32)

    # small frequency wobble
    wobble_rate = random.uniform(3.0, 6.0)
    wobble_amt = random.uniform(6.0, 14.0)

    # fade in/out so it doesn't click
    fade = int(0.04 * sr)

    samples = []
    phase = 0.0
    for i in range(n):
        t = i / sr

        am = 0.65 + 0.35 * math.sin(2 * math.pi * am_rate * t)
        wobble = wobble_amt * math.sin(2 * math.pi * wobble_rate * t)

        f = base + wobble
        phase += (2 * math.pi * f) / sr

        # fundamental + harmonics
        s = (
            0.70 * math.sin(phase) +
            0.20 * math.sin(2 * phase) +
            0.10 * math.sin(3 * phase)
        )

        # a bit of noise for texture
        s += 0.06 * (random.random() * 2 - 1)

        # apply AM
        s *= am

        # fade envelope
        if i < fade:
            s *= i / fade
        elif i > n - fade:
            s *= (n - i) / fade

        # overall level
        s *= 0.7

        samples.append(s)

    return samples

def main():
    out_dir = os.path.join("static", "sounds")
    os.makedirs(out_dir, exist_ok=True)

    for bee_id in BEE_IDS:
        path = os.path.join(out_dir, f"{bee_id}.wav")
        samples = make_buzz(bee_id)
        write_wav(path, samples)
        print("Wrote", path)

if __name__ == "__main__":
    main()
