import math
import random
import struct
import sys
import wave
import shutil
import subprocess
import tempfile
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent / "sounds"
SAMPLE_RATE = 44100

BEES = [
    # (
    #     "honey",
    #     "Honey Bee",
    #     440,
    #     "Honey bees live in colonies and turn nectar into honey and wax. "
    #     "They use a waggle dance to tell other bees where good flowers are. "
    #     "You can find them worldwide in gardens, farms, and anywhere flowers grow.",
    # ),
    # (
    #     "bumble",
    #     "Bumble Bee",
    #     392,
    #     "Bumble bees are fuzzy pollinators that often live in small nests. "
    #     "They can buzz-pollinate by vibrating flowers to shake loose pollen. "
    #     "They are common in gardens and meadows, especially in cooler and temperate areas.",
    # ),
    # (
    #     "carpenter",
    #     "Carpenter Bee",
    #     330,
    #     "Carpenter bees are large bees with shiny, dark abdomens. "
    #     "They drill neat round holes in wood to make nesting tunnels. "
    #     "They are often found near wooden decks, fences, sheds, and dead trees.",
    # ),
    # (
    #     "leafcutter",
    #     "Leafcutter Bee",
    #     523,
    #     "Leafcutter bees are solitary bees that visit many kinds of flowers. "
    #     "They cut smooth circles from leaves and use them to line their nest cells. "
    #     "They are common in gardens, parks, and fields where leafy plants and flowers are nearby.",
    # ),
    # (
    #     "mason",
    #     "Mason Bee",
    #     349,
    #     "Mason bees are gentle solitary bees that nest in small holes and tubes. "
    #     "They use mud like mortar to seal each chamber for their eggs. "
    #     "They are commonly found in spring around orchards, gardens, and woodland edges.",
    # ),
    # (
    #     "blue_mason",
    #     "Blue Mason Bee",
    #     587,
    #     "Blue mason bees are metallic blue and look almost like tiny flying jewels. "
    #     "They are strong early-season pollinators and are great for fruit blossoms. "
    #     "They are often found in spring in orchards and backyards where nesting holes are available.",
    # ),
    # (
    #     "sweat",
    #     "Sweat Bee",
    #     659,
    #     "Sweat bees are usually small and can be green, blue, or dark colored. "
    #     "Some are attracted to salty sweat and may land on your skin for a quick sip. "
    #     "They are commonly found in sunny gardens and open areas, often nesting in the ground.",
    # ),
    # (
    #     "queen",
    #     "Queen Bee",
    #     294,
    #     "The queen bee is the main egg-layer in a honey bee colony. "
    #     "She releases pheromones that help keep the hive organized and calm. "
    #     "You will usually find her inside the hive surrounded by worker bees.",
    # ),
]

QUIZ_WELCOME_TEXT = (
    "Welcome to the Bee Quiz. [[slnc 700]] "
    "We will be asking you a few questions about bees. [[slnc 700]] "
    "You will get ten seconds to find the correct answer. [[slnc 700]] "
    "Press and hold the Quiz button for two seconds if you are ready to go. [[slnc 900]] "
    "To abort the quiz at any time after it begins, press and hold the Quiz button for two seconds."
)

QUIZ_READY_TEXT = "Great Lets start the quiz then."

QUESTIONS = [
    ("question1.wav", "Question one. Which bee makes honey? You have ten seconds. Choose now."),
    ("question2.wav", "Question two. Which bee is fuzzy and can buzz pollinate flowers? You have ten seconds. Choose now."),
    ("question3.wav", "Question three. Which bee drills round holes in wood to build a nest? You have ten seconds. Choose now."),
    ("question4.wav", "Question four. Which bee cuts circles from leaves to line its nest? You have ten seconds. Choose now."),
    ("question5.wav", "Question five. Which bee is metallic blue and active in early spring? You have ten seconds. Choose now."),
    ("question6.wav", "Question six. Which bee is the main egg layer in a honey bee colony? You have ten seconds. Choose now."),
]

CORRECT_TEXT = "That is correct."
INCORRECT_TEXT = "That is not correct."
QUIZ_COMPLETE_TEXT = "Quiz complete. Thanks for playing."

def clamp(x, lo=-1.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x

def envelope(t, total, fade=0.02):
    if t < fade:
        return t / fade
    if t > total - fade:
        return max(0.0, (total - t) / fade)
    return 1.0

def gen_buzz(freq_hz, seconds, amp=0.35, noise=0.08):
    n = int(SAMPLE_RATE * seconds)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = envelope(t, seconds)
        s = (
            math.sin(2 * math.pi * freq_hz * t) * 1.0
            + math.sin(2 * math.pi * freq_hz * 2 * t) * 0.35
            + math.sin(2 * math.pi * freq_hz * 3 * t) * 0.20
        )
        s += (random.random() * 2 - 1) * noise
        out.append(clamp(s * amp * env))
    return out

def gen_silence(seconds):
    return [0.0] * int(SAMPLE_RATE * seconds)

def write_wav(path: Path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for s in samples:
            v = int(clamp(s) * 32767)
            frames += struct.pack("<h", v)
        wf.writeframes(frames)

def make_short(freq):
    return gen_buzz(freq, 0.35) + gen_silence(0.05)

def tts_to_wav(text: str, out_wav: Path):
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as td:
            aiff = Path(td) / "tmp.aiff"
            subprocess.run(["say", "-o", str(aiff), text], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(out_wav)], check=True)
        return

    if sys.platform.startswith("win"):
        ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile("{str(out_wav)}")
$text = @'
{text}
'@
$s.Speak($text)
$s.Dispose()
"""
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=True)
        return

    espeak = shutil.which("espeak") or shutil.which("espeak-ng")
    if espeak:
        subprocess.run([espeak, "-w", str(out_wav), text], check=True)
        return

    raise RuntimeError("No TTS engine found. On Linux, install: sudo apt-get install espeak")

def main():
    random.seed(0)
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

    # Bee sounds + narrations
    for key, label, freq, narration in BEES:
        short_path = SOUNDS_DIR / f"{key}_short.wav"
        nar_path = SOUNDS_DIR / f"{key}_narration.wav"
        write_wav(short_path, make_short(freq))
        tts_to_wav(narration, nar_path)
        print(f"OK: {label} -> {short_path.name}, {nar_path.name}")

    # Quiz system audio
    tts_to_wav(QUIZ_WELCOME_TEXT, SOUNDS_DIR / "quiz_welcome.wav")
    tts_to_wav(QUIZ_READY_TEXT, SOUNDS_DIR / "quiz_ready.wav")
    tts_to_wav(CORRECT_TEXT, SOUNDS_DIR / "correct.wav")
    tts_to_wav(INCORRECT_TEXT, SOUNDS_DIR / "incorrect.wav")
    tts_to_wav(QUIZ_COMPLETE_TEXT, SOUNDS_DIR / "quiz_complete.wav")

    # Questions
    for filename, text in QUESTIONS:
        tts_to_wav(text, SOUNDS_DIR / filename)

    print("OK: quiz + questions generated in sounds/")

if __name__ == "__main__":
    main()
