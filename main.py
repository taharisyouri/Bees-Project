import sys
import time
import wave
import threading
import subprocess
import shutil
import tempfile
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Dict, List
import tkinter as tk

# ----------------------------
# Config
# ----------------------------
HOLD_SECONDS = 2.0
ANSWER_SECONDS = 10
FLASH_INTERVAL_MS = 400
RESULT_FLASH_SECONDS = 3.0
INTERRUPT_AUDIO = True

BASE_DIR = Path(__file__).resolve().parent
SOUNDS_DIR = BASE_DIR / "sounds"
IMAGES_DIR = BASE_DIR / "images"

QUIZ_WELCOME_WAV = SOUNDS_DIR / "quiz_welcome.wav"
QUIZ_READY_WAV = SOUNDS_DIR / "quiz_ready.wav"
CORRECT_WAV = SOUNDS_DIR / "correct.wav"
INCORRECT_WAV = SOUNDS_DIR / "incorrect.wav"
QUIZ_ABORT_WAV = SOUNDS_DIR / "quiz_abort.wav"  # optional; auto-generated if missing

MAX_IMG_W = 220
MAX_IMG_H = 180

BEE_KEYS = [f"bee{i}" for i in range(1, 9)]  # bee1..bee8

# Quiz questions (answers are slots bee1..bee8)
QUESTIONS = [
    {"wav": SOUNDS_DIR / "question1.wav", "answer": "bee1"},
    {"wav": SOUNDS_DIR / "question2.wav", "answer": "bee2"},
    {"wav": SOUNDS_DIR / "question3.wav", "answer": "bee3"},
    {"wav": SOUNDS_DIR / "question4.wav", "answer": "bee4"},
    {"wav": SOUNDS_DIR / "question5.wav", "answer": "bee6"},
    {"wav": SOUNDS_DIR / "question6.wav", "answer": "bee8"},
]


# ----------------------------
# Model
# ----------------------------
@dataclass(frozen=True)
class BeeSlot:
    key: str  # bee1..bee8
    image_path: Path
    short_wav: Path
    narration_wav: Path


def slot_list() -> List[BeeSlot]:
    out: List[BeeSlot] = []
    for k in BEE_KEYS:
        out.append(
            BeeSlot(
                key=k,
                image_path=IMAGES_DIR / f"{k}.png",
                short_wav=SOUNDS_DIR / f"{k}_sound.wav",
                narration_wav=SOUNDS_DIR / f"{k}_narration.wav",
            )
        )
    return out


# ----------------------------
# Audio
# ----------------------------
def wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate() or 1)
    except Exception:
        return 0.0


def tts_to_wav(text: str, out_wav: Path) -> None:
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

    raise RuntimeError("No TTS engine found.")


class AudioPlayer:
    def __init__(self):
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._token = 0

    def stop(self) -> None:
        with self._lock:
            self._token += 1
            self._stop_event.set()
            if self._proc is not None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None

            if sys.platform.startswith("win"):
                try:
                    import winsound
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except Exception:
                    pass

    def play(self, wav_path: Path, on_done: Optional[Callable[[], None]] = None) -> None:
        if not wav_path.exists():
            print(f"Missing audio: {wav_path}")
            return

        if INTERRUPT_AUDIO:
            self.stop()

        with self._lock:
            self._stop_event.clear()
            self._token += 1
            token = self._token

        threading.Thread(
            target=self._play_thread, args=(wav_path, token, on_done), daemon=True
        ).start()

    def _play_thread(self, wav_path: Path, token: int, on_done: Optional[Callable[[], None]]):
        try:
            if sys.platform == "darwin":
                self._play_subprocess(["/usr/bin/afplay", str(wav_path)], token)
                return

            if sys.platform.startswith("win"):
                import winsound
                dur = max(0.1, wav_duration_seconds(wav_path))
                winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                end = time.time() + dur
                while time.time() < end:
                    if self._stop_event.is_set() or token != self._token:
                        return
                    time.sleep(0.05)
                return

            if shutil.which("aplay"):
                self._play_subprocess(["aplay", "-q", str(wav_path)], token)
                return
            if shutil.which("paplay"):
                self._play_subprocess(["paplay", str(wav_path)], token)
                return
        finally:
            if on_done and (not self._stop_event.is_set()) and token == self._token:
                try:
                    on_done()
                except Exception:
                    pass

    def _play_subprocess(self, cmd: list, token: int):
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self._lock:
            self._proc = proc

        while True:
            if self._stop_event.is_set() or token != self._token:
                try:
                    proc.terminate()
                except Exception:
                    pass
                return
            if proc.poll() is not None:
                return
            time.sleep(0.05)


# ----------------------------
# LED output (tk test)
# ----------------------------
class TkLedOutput:
    def __init__(self, dots: Dict[str, tk.Canvas]):
        self.dots = dots

    def set_color(self, key: str, color: str) -> None:
        c = self.dots.get(key)
        if c:
            c.itemconfigure("lamp", fill=color)

    def set_all(self, color: str) -> None:
        for k in self.dots:
            self.set_color(k, color)


# ----------------------------
# Controller
# ----------------------------
class BeeController:
    """
    Hardware-ready methods:
      - on_bee_down("bee1")
      - on_bee_up("bee1")
      - on_quiz_down()
      - on_quiz_up()
    """
    def __init__(self, root: tk.Tk, slots: List[BeeSlot], audio: AudioPlayer, leds: TkLedOutput, status: tk.StringVar):
        self.root = root
        self.slots = {s.key: s for s in slots}
        self.slot_keys = list(self.slots.keys())
        self.audio = audio
        self.leds = leds
        self.status = status

        # learn-mode hold timers
        self._hold_jobs: Dict[str, str] = {}
        self._hold_fired = set()

        # LOCK: while a learn-mode narration is playing, ignore all other presses
        self.learn_narration_lock = False

        # quiz button timer (used for start OR abort depending on state)
        self._quiz_job = None
        self._quiz_hold_fired = False

        # quiz state
        self.quiz_active = False
        self.quiz_waiting = False
        self.q_index = 0
        self.score = 0
        self._answer_timeout_job = None
        self.quiz_options: List[str] = []

        # flashing
        self._flash_job = None
        self._flash_end_job = None
        self._flash_on = False
        self._flash_keys: List[str] = []
        self._flash_map: Dict[str, str] = {}

    # ---------- Flash helpers ----------
    def _stop_flash(self):
        if self._flash_job:
            try:
                self.root.after_cancel(self._flash_job)
            except Exception:
                pass
            self._flash_job = None
        if self._flash_end_job:
            try:
                self.root.after_cancel(self._flash_end_job)
            except Exception:
                pass
            self._flash_end_job = None
        self._flash_on = False

    def _end_flash(self):
        self._stop_flash()
        self.leds.set_all("gray")

    def _flash_uniform(self, keys: List[str], color: str, interval_ms: int, duration_ms: int):
        self._stop_flash()
        self._flash_keys = list(keys)
        self._flash_on = False
        self.leds.set_all("gray")

        def tick():
            self._flash_on = not self._flash_on
            self.leds.set_all("gray")
            for k in self._flash_keys:
                self.leds.set_color(k, color if self._flash_on else "gray")
            self._flash_job = self.root.after(interval_ms, tick)

        tick()
        self._flash_end_job = self.root.after(duration_ms, self._end_flash)

    def _flash_multicolor(self, color_map: Dict[str, str], interval_ms: int, duration_ms: int):
        self._stop_flash()
        self._flash_map = dict(color_map)
        self._flash_on = False
        self.leds.set_all("gray")

        def tick():
            self._flash_on = not self._flash_on
            self.leds.set_all("gray")
            if self._flash_on:
                for k, col in self._flash_map.items():
                    self.leds.set_color(k, col)
            self._flash_job = self.root.after(interval_ms, tick)

        tick()
        self._flash_end_job = self.root.after(duration_ms, self._end_flash)

    # ---------- Learn mode ----------
    def on_bee_down(self, key: str) -> None:
        if self.learn_narration_lock:
            return
        if self.quiz_active:
            return

        self._hold_fired.discard(key)

        old = self._hold_jobs.pop(key, None)
        if old:
            try:
                self.root.after_cancel(old)
            except Exception:
                pass

        self._hold_jobs[key] = self.root.after(int(HOLD_SECONDS * 1000), lambda k=key: self._bee_hold_fire(k))

    def on_bee_up(self, key: str) -> None:
        if self.learn_narration_lock:
            return

        if self.quiz_waiting:
            self._handle_answer(key)
            return
        if self.quiz_active:
            return

        job = self._hold_jobs.pop(key, None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass

        if key in self._hold_fired:
            return

        self._play_slot_audio(key, short=True)

    def _bee_hold_fire(self, key: str) -> None:
        # start narration and LOCK until narration completes
        self._hold_fired.add(key)
        self._play_slot_audio(key, short=False)

    def _play_slot_audio(self, key: str, short: bool) -> None:
        slot = self.slots[key]
        wav = slot.short_wav if short else slot.narration_wav
        if not wav.exists():
            self.status.set(f"Missing: {wav.name}")
            return

        if not short:
            self.learn_narration_lock = True

        self._end_flash()
        self.leds.set_all("gray")
        self.leds.set_color(key, "green")
        self.status.set(f"{'Sound' if short else 'Narration'}: {key}")

        def done():
            self.leds.set_color(key, "gray")
            self.status.set("Ready")
            if not short:
                self.learn_narration_lock = False

        self.audio.play(wav, on_done=lambda: self.root.after(0, done))

    # ---------- Quiz button ----------
    def on_quiz_down(self) -> None:
        if self.learn_narration_lock:
            return

        # If quiz is active, holding Quiz means ABORT.
        if self.quiz_active:
            self._schedule_quiz_hold(self._abort_quiz_hold_fire, msg="Quiz: hold to abort...")
            return

        # Otherwise, holding Quiz means START quiz.
        self._schedule_quiz_hold(self._start_quiz_hold_fire, msg="Quiz: holding...")

    def on_quiz_up(self) -> None:
        if self.learn_narration_lock:
            return

        # cancel hold timer if any
        if self._quiz_job:
            try:
                self.root.after_cancel(self._quiz_job)
            except Exception:
                pass
            self._quiz_job = None

        # If quiz is active, tap does nothing (avoid accidental abort)
        if self.quiz_active:
            return

        # If hold already fired, ignore release
        if self._quiz_hold_fired:
            return

        # Tap = welcome
        if not QUIZ_WELCOME_WAV.exists():
            self.status.set("Missing: quiz_welcome.wav")
            return

        self.status.set("Quiz: Welcome")
        self.audio.play(QUIZ_WELCOME_WAV, on_done=lambda: self.root.after(0, lambda: self.status.set("Ready")))

    def _schedule_quiz_hold(self, fire_fn: Callable[[], None], msg: str):
        self._quiz_hold_fired = False
        if self._quiz_job:
            try:
                self.root.after_cancel(self._quiz_job)
            except Exception:
                pass
            self._quiz_job = None

        self.status.set(msg)
        self._quiz_job = self.root.after(int(HOLD_SECONDS * 1000), fire_fn)

    def _start_quiz_hold_fire(self) -> None:
        self._quiz_hold_fired = True
        self._quiz_job = None
        self._start_quiz()

    def _abort_quiz_hold_fire(self) -> None:
        self._quiz_hold_fired = True
        self._quiz_job = None
        self.abort_quiz()

    # ---------- Quiz flow ----------
    def _start_quiz(self) -> None:
        if not QUIZ_READY_WAV.exists():
            self.status.set("Missing: quiz_ready.wav")
            return
        for q in QUESTIONS:
            if not q["wav"].exists():
                self.status.set(f"Missing: {q['wav'].name}")
                return

        self.quiz_active = True
        self.quiz_waiting = False
        self.q_index = 0
        self.score = 0

        self._end_flash()
        self.leds.set_all("gray")

        self.status.set("Quiz: Ready")
        self.audio.play(QUIZ_READY_WAV, on_done=lambda: self.root.after(0, self._play_question))

    def abort_quiz(self) -> None:
        # cancel answer timer
        if self._answer_timeout_job:
            try:
                self.root.after_cancel(self._answer_timeout_job)
            except Exception:
                pass
            self._answer_timeout_job = None

        # cancel flashing
        self._end_flash()

        # stop audio
        self.audio.stop()

        # unlock learn narration (safety)
        self.learn_narration_lock = False

        # reset quiz state
        self.quiz_active = False
        self.quiz_waiting = False
        self.q_index = 0
        self.score = 0
        self.quiz_options = []

        self.status.set("Quiz: Aborted")

        # play abort message
        if QUIZ_ABORT_WAV.exists():
            self.audio.play(QUIZ_ABORT_WAV, on_done=lambda: self.root.after(0, lambda: self.status.set("Ready")))
        else:
            try:
                tts_to_wav("Quiz aborted.", QUIZ_ABORT_WAV)
                self.audio.play(QUIZ_ABORT_WAV, on_done=lambda: self.root.after(0, lambda: self.status.set("Ready")))
            except Exception:
                self.root.after(800, lambda: self.status.set("Ready"))

    def _pick_4_options(self, correct_key: str) -> List[str]:
        others = [k for k in self.slot_keys if k != correct_key]
        picks = random.sample(others, 3) + [correct_key]
        random.shuffle(picks)
        return picks

    def _play_question(self) -> None:
        q = QUESTIONS[self.q_index]
        correct_key = q["answer"]
        self.quiz_options = self._pick_4_options(correct_key)

        self.status.set(f"Quiz: Question {self.q_index + 1}")
        self.audio.play(q["wav"], on_done=lambda: self.root.after(0, self._start_answer_window))

    def _start_answer_window(self) -> None:
        self.quiz_waiting = True
        self.status.set("Quiz: Choose a bee")

        # Only 4 options flash yellow
        self._flash_uniform(self.quiz_options, "yellow", FLASH_INTERVAL_MS, ANSWER_SECONDS * 1000)
        self._answer_timeout_job = self.root.after(ANSWER_SECONDS * 1000, self._timeout)

    def _timeout(self) -> None:
        self._answer_timeout_job = None
        if not self.quiz_waiting:
            return

        self.quiz_waiting = False
        self._end_flash()
        self._feedback(correct=False)

    def _handle_answer(self, key: str) -> None:
        if not self.quiz_waiting:
            return

        # Only accept answers from the 4 options
        if key not in self.quiz_options:
            return

        self.quiz_waiting = False
        if self._answer_timeout_job:
            try:
                self.root.after_cancel(self._answer_timeout_job)
            except Exception:
                pass
            self._answer_timeout_job = None

        self._end_flash()

        correct_key = QUESTIONS[self.q_index]["answer"]
        correct = (key == correct_key)
        if correct:
            self.score += 1

        self._feedback(correct=correct)

    def _feedback(self, correct: bool) -> None:
        wav = CORRECT_WAV if correct else INCORRECT_WAV
        if not wav.exists():
            self.status.set(f"Missing: {wav.name}")
            self.abort_quiz()
            return

        self.status.set("Quiz: Correct" if correct else "Quiz: Not correct")

        # Always show 1 green (correct) + 3 red (other options), flash for 3 seconds
        correct_key = QUESTIONS[self.q_index]["answer"]
        color_map = {k: "red" for k in self.quiz_options}
        color_map[correct_key] = "green"
        self._flash_multicolor(color_map, interval_ms=250, duration_ms=int(RESULT_FLASH_SECONDS * 1000))

        def done():
            self._end_flash()
            self._next_or_end()

        self.audio.play(wav, on_done=lambda: self.root.after(0, done))

    def _next_or_end(self) -> None:
        self.q_index += 1
        if self.q_index >= len(QUESTIONS):
            self._end_quiz()
            return
        self._play_question()

    def _end_quiz(self) -> None:
        self.quiz_active = False
        self.quiz_waiting = False
        self._end_flash()

        total = len(QUESTIONS)
        msg = f"You had {self.score} questions correct. Congratulations. Thanks for playing."
        self.status.set(f"Quiz: Score {self.score}/{total}")

        score_wav = SOUNDS_DIR / "quiz_score.wav"
        try:
            tts_to_wav(msg, score_wav)
            self.audio.play(score_wav, on_done=lambda: self.root.after(0, lambda: self.status.set("Ready")))
        except Exception:
            self.root.after(1200, lambda: self.status.set("Ready"))


# ----------------------------
# UI (minimal test panel)
# ----------------------------
def load_and_scale_photo(path: Path) -> Optional[tk.PhotoImage]:
    if not path.exists():
        return None
    try:
        img = tk.PhotoImage(file=str(path))
    except Exception:
        return None

    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return img

    sx = max(1, (w + MAX_IMG_W - 1) // MAX_IMG_W)
    sy = max(1, (h + MAX_IMG_H - 1) // MAX_IMG_H)
    s = max(sx, sy)
    if s > 1:
        img = img.subsample(s, s)
    return img


def build_ui(root: tk.Tk, controller: BeeController, slots: List[BeeSlot]) -> TkLedOutput:
    root.title("Bee Project (bee1..bee8)")

    photos: List[tk.PhotoImage] = []
    root._photos = photos  # keep refs alive

    grid = tk.Frame(root)
    grid.pack(padx=10, pady=10)

    dots: Dict[str, tk.Canvas] = {}

    for i, slot in enumerate(slots):
        r = i // 4
        c = i % 4

        cell = tk.Frame(grid, padx=10, pady=10)
        cell.grid(row=r, column=c, sticky="n")

        photo = load_and_scale_photo(slot.image_path)
        if photo:
            photos.append(photo)
            tk.Label(cell, image=photo).pack(pady=(0, 6))
        else:
            tk.Label(cell, text=f"Missing image\n{slot.image_path.name}", width=22, height=8).pack(pady=(0, 6))

        dot = tk.Canvas(cell, width=26, height=26, highlightthickness=0)
        dot.create_oval(4, 4, 22, 22, fill="gray", outline="", tags=("lamp",))
        dot.pack(pady=(0, 8))
        dots[slot.key] = dot

        # Minimal button (no text)
        btn = tk.Button(cell, text="", width=18, height=2)
        btn.pack()
        btn.bind("<ButtonPress-1>", lambda e, k=slot.key: controller.on_bee_down(k))
        btn.bind("<ButtonRelease-1>", lambda e, k=slot.key: controller.on_bee_up(k))

    bottom = tk.Frame(root)
    bottom.pack(pady=(0, 10))

    quiz_btn = tk.Button(bottom, text="Quiz", width=18, height=2)
    quiz_btn.pack()
    quiz_btn.bind("<ButtonPress-1>", lambda e: controller.on_quiz_down())
    quiz_btn.bind("<ButtonRelease-1>", lambda e: controller.on_quiz_up())

    return TkLedOutput(dots)


def main():
    slots = slot_list()
    root = tk.Tk()

    status = tk.StringVar(value="Ready")
    audio = AudioPlayer()

    leds = TkLedOutput({})
    controller = BeeController(root, slots, audio, leds, status)

    leds = build_ui(root, controller, slots)
    controller.leds = leds

    tk.Label(root, textvariable=status, anchor="w").pack(fill="x", padx=10, pady=(0, 10))

    def on_close():
        audio.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()