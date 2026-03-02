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

# ----------------------------
# Insects (bee1..bee8 => insect1..insect8)
# ----------------------------
INSECTS = [
    ("insect1", "Butterfly",
     "Butterflies are colorful insects with scaly wings that sip nectar from flowers. [[slnc 700]] "
     "They go through a full metamorphosis, changing from caterpillar to butterfly. [[slnc 700]] "
     "You can find them in gardens, meadows, forests, and parks around the world."),
    ("insect2", "Cicada",
     "Cicadas are stout insects known for their loud summer buzzing sounds. [[slnc 700]] "
     "Some species spend many years underground as nymphs before emerging all at once. [[slnc 700]] "
     "They are common in warm regions with trees, like forests, neighborhoods, and city parks."),
    ("insect3", "Mosquito",
     "Mosquitoes are small flying insects with a thin body and a long mouthpart for feeding. [[slnc 700]] "
     "Only females bite, because they need protein from blood to make eggs. [[slnc 700]] "
     "They live near standing water in most parts of the world, especially in warm and humid areas."),
    ("insect4", "Moth",
     "Moths are night flying insects with soft bodies and dusty wings. [[slnc 700]] "
     "Many moths use the moon for navigation, which is why bright lights can confuse them. [[slnc 700]] "
     "They are found almost everywhere, from forests and fields to backyards and porch lights."),
    ("insect5", "Grasshopper",
     "Grasshoppers are jumping insects with strong back legs and chewing mouthparts. [[slnc 700]] "
     "They make a rasping sound by rubbing their legs or wings together. [[slnc 700]] "
     "They are common in grassy fields, farms, prairies, and roadside plants."),
    ("insect6", "Fly",
     "Flies are fast flying insects with large eyes and a single pair of wings. [[slnc 700]] "
     "Houseflies taste with their feet and can walk on walls using tiny sticky pads. [[slnc 700]] "
     "They are found worldwide, especially around people, trash, food, and animals."),
    ("insect7", "Cricket",
     "Crickets are small insects that usually sing at night. [[slnc 700]] "
     "Males chirp by rubbing their wings together to attract mates. [[slnc 700]] "
     "They live in grass, leaf litter, gardens, and warm sheltered places."),
    ("insect8", "Wasp",
     "Wasps are slender insects with narrow waists and often bright warning colors. [[slnc 700]] "
     "Many wasps are predators that hunt other insects, helping control pests. [[slnc 700]] "
     "They are found in gardens, woodlands, and around buildings where they build nests."),
]

# ----------------------------
# Quiz speech (with pauses)
# ----------------------------
QUIZ_WELCOME_TEXT = (
    "Welcome to the Insect Quiz. [[slnc 700]] "
    "We will play different insect sounds. [[slnc 700]] "
    "You will get ten seconds to find the correct insect for the sound you hear. [[slnc 700]] "
    "Press and hold the Quiz button for two seconds if you are ready to go. [[slnc 900]] "
    "To abort the quiz at any time press the ABORT button. [[slnc 900]]"
)

QUIZ_READY_TEXT = "Great. Let's start the quiz.[[slnc 900]]"



CORRECT_TEXT = "That is correct."
INCORRECT_TEXT = "That is not correct."
QUIZ_COMPLETE_TEXT = "Quiz complete. Thanks for playing."
QUIZ_ABORT_TEXT = "Quiz aborted."

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

    # Create insect narrations: insect1_narration.wav ... insect8_narration.wav
    for key, label, narration in INSECTS:
        out_path = SOUNDS_DIR / f"{key}_narration.wav"
        tts_to_wav(narration, out_path)
        print(f"OK: {label} -> {out_path.name}")

    # Quiz system audio
    tts_to_wav(QUIZ_WELCOME_TEXT, SOUNDS_DIR / "quiz_welcome.wav")
    tts_to_wav(QUIZ_READY_TEXT, SOUNDS_DIR / "quiz_ready.wav")
    tts_to_wav(QUIZ_ABORT_TEXT, SOUNDS_DIR / "quiz_abort.wav")
    tts_to_wav(CORRECT_TEXT, SOUNDS_DIR / "correct.wav")
    tts_to_wav(INCORRECT_TEXT, SOUNDS_DIR / "incorrect.wav")
    tts_to_wav(QUIZ_COMPLETE_TEXT, SOUNDS_DIR / "quiz_complete.wav")

    # Questions
    for filename, text in QUESTIONS:
        tts_to_wav(text, SOUNDS_DIR / filename)

    print("OK: insect narrations + quiz audio generated in sounds/")

if __name__ == "__main__":
    main()