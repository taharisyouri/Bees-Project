import sys
import time
import wave
import threading
import subprocess
import shutil
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
import tkinter as tk

# ----------------------------
# Config
# ----------------------------
HOLD_SECONDS = 2.0
ANSWER_SECONDS = 10
FLASH_INTERVAL_MS = 400
RESULT_FLASH_SECONDS = 3.0
INTERRUPT_AUDIO = True

QUIZ_ROUNDS = 5  # play 5 random insect sounds per quiz

BASE_DIR = Path(__file__).resolve().parent
SOUNDS_DIR = BASE_DIR / "sounds"
IMAGES_DIR = BASE_DIR / "images"

MAX_IMG_W = 220
MAX_IMG_H = 180

INSECT_KEYS = [f"insect{i}" for i in range(1, 9)]  # insect1..insect8


# ----------------------------
# Helpers
# ----------------------------
def find_ci(directory: Path, filename: str) -> Path:
    """Return a file path in directory matching filename (case-insensitive) if it exists."""
    direct = directory / filename
    if direct.exists():
        return direct

    target = filename.lower()
    if directory.exists():
        for p in directory.iterdir():
            if p.is_file() and p.name.lower() == target:
                return p

    return direct  # fallback (will be missing)


def first_existing_ci(directory: Path, *filenames: str) -> Optional[Path]:
    for name in filenames:
        p = find_ci(directory, name)
        if p.exists():
            return p
    return None


# Optional quiz audio files (NO auto-generation)
QUIZ_WELCOME_WAV = find_ci(SOUNDS_DIR, "quiz_welcome.wav")   # optional on short press
QUIZ_READY_WAV = find_ci(SOUNDS_DIR, "quiz_ready.wav")       # optional on quiz start
QUIZ_ABORT_WAV = find_ci(SOUNDS_DIR, "quiz_abort.wav")       # optional on abort

CORRECT_WAV = find_ci(SOUNDS_DIR, "correct.wav")             # required for feedback
INCORRECT_WAV = find_ci(SOUNDS_DIR, "incorrect.wav")         # required for feedback


# ----------------------------
# Model
# ----------------------------
@dataclass(frozen=True)
class InsectSlot:
    key: str
    image_path: Path
    sound_wav: Path
    narration_wav: Path  # optional; fallback to sound_wav if missing


def slot_list() -> List[InsectSlot]:
    slots: List[InsectSlot] = []
    for k in INSECT_KEYS:
        img = find_ci(IMAGES_DIR, f"{k}.png")
        sound = find_ci(SOUNDS_DIR, f"{k}_sound.wav")
        nar = find_ci(SOUNDS_DIR, f"{k}_narration.wav")
        slots.append(InsectSlot(key=k, image_path=img, sound_wav=sound, narration_wav=nar))
    return slots


# ----------------------------
# Audio
# ----------------------------
def wav_duration_seconds(path: Path) -> float:
    if path.suffix.lower() != ".wav":
        return 0.0
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate() or 1)
    except Exception:
        return 0.0


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

        threading.Thread(target=self._play_thread, args=(wav_path, token, on_done), daemon=True).start()

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

            print("No audio player found (need aplay or paplay).")
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
class InsectController:
    """
    Rules:
      - Only one action at a time.
      - While audio is playing, all input is blocked,
        EXCEPT Abort (Abort works anytime during an active quiz).
    """
    def __init__(self, root: tk.Tk, slots: List[InsectSlot], audio: AudioPlayer, leds: TkLedOutput, status: tk.StringVar):
        self.root = root
        self.slots = {s.key: s for s in slots}
        self.slot_keys = list(self.slots.keys())
        self.audio = audio
        self.leds = leds
        self.status = status

        self._pressed: Optional[Tuple[str, str]] = None  # ("insect"/"quiz", key)
        self.input_locked = False

        self._hold_jobs: Dict[str, str] = {}
        self._hold_fired = set()

        self._quiz_job = None
        self._quiz_hold_fired = False

        self.quiz_active = False
        self.quiz_waiting = False
        self.q_index = 0
        self.score = 0
        self._answer_timeout_job = None
        self.quiz_options: List[str] = []
        self.quiz_sequence: List[str] = []

        self._flash_job = None
        self._flash_end_job = None
        self._flash_on = False
        self._flash_keys: List[str] = []
        self._flash_map: Dict[str, str] = {}

        self.insect_buttons: Dict[str, tk.Button] = {}
        self.quiz_button: Optional[tk.Button] = None
        self.abort_button: Optional[tk.Button] = None

    # ---------- UI registration ----------
    def register_insect_button(self, key: str, btn: tk.Button) -> None:
        self.insect_buttons[key] = btn
        self._apply_ui_state()

    def set_quiz_button(self, btn: tk.Button) -> None:
        self.quiz_button = btn
        self._apply_ui_state()

    def set_abort_button(self, btn: tk.Button) -> None:
        self.abort_button = btn
        self._apply_ui_state()

    def _apply_ui_state(self) -> None:
        pressed_type = self._pressed[0] if self._pressed else None
        pressed_key = self._pressed[1] if self._pressed else None

        def is_pressed(btn_type: str, key: Optional[str]) -> bool:
            return pressed_type == btn_type and pressed_key == (key or "")

        allowed_insects = set(self.quiz_options) if self.quiz_waiting else set(self.slot_keys)

        for k, btn in self.insect_buttons.items():
            if self.input_locked:
                state = tk.NORMAL if is_pressed("insect", k) else tk.DISABLED
            else:
                if self.quiz_active and not self.quiz_waiting:
                    state = tk.DISABLED
                elif self.quiz_waiting:
                    state = tk.NORMAL if k in allowed_insects else tk.DISABLED
                else:
                    state = tk.NORMAL
            btn.config(state=state)

        if self.quiz_button:
            if self.input_locked:
                state = tk.NORMAL if is_pressed("quiz", "quiz") else tk.DISABLED
            else:
                state = tk.NORMAL if not self.quiz_active else tk.DISABLED
            self.quiz_button.config(state=state)

        if self.abort_button:
            # IMPORTANT: Abort must work ANYTIME during active quiz, even while audio is playing
            self.abort_button.config(state=(tk.NORMAL if self.quiz_active else tk.DISABLED))

    # ---------- Input lock helpers ----------
    def _lock_inputs(self) -> None:
        self.input_locked = True
        self._apply_ui_state()

    def _unlock_inputs(self) -> None:
        self.input_locked = False
        self._apply_ui_state()

    def _begin_press(self, press_type: str, key: str) -> bool:
        if self.input_locked:
            return False
        if self._pressed is not None:
            return False
        self._pressed = (press_type, key)
        self._apply_ui_state()
        return True

    def _end_press(self, press_type: str, key: str) -> None:
        if self._pressed == (press_type, key):
            self._pressed = None
            self._apply_ui_state()

    def _play_audio_locked(self, wav_path: Path, after_done: Optional[Callable[[], None]] = None) -> None:
        """
        Plays audio and locks input until it finishes.
        NOTE: If audio is force-stopped (Abort), this on_done will NOT fire.
        So Abort must force-unlock before starting its own flow.
        """
        if not wav_path.exists():
            print(f"Missing audio: {wav_path}")
            if after_done:
                self.root.after(0, after_done)
            return

        self._lock_inputs()

        def done_on_audio_thread():
            def on_ui():
                self._unlock_inputs()
                if after_done:
                    after_done()
            self.root.after(0, on_ui)

        self.audio.play(wav_path, on_done=done_on_audio_thread)

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
    def on_insect_down(self, key: str) -> None:
        if self.quiz_active:
            return
        if not self._begin_press("insect", key):
            return

        self._hold_fired.discard(key)

        old = self._hold_jobs.pop(key, None)
        if old:
            try:
                self.root.after_cancel(old)
            except Exception:
                pass

        self._hold_jobs[key] = self.root.after(int(HOLD_SECONDS * 1000), lambda k=key: self._insect_hold_fire(k))

    def on_insect_up(self, key: str) -> None:
        self._end_press("insect", key)

        if self.quiz_waiting:
            self._handle_answer(key)
            return
        if self.quiz_active or self.input_locked:
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

    def _insect_hold_fire(self, key: str) -> None:
        if self._pressed != ("insect", key):
            return
        self._hold_fired.add(key)
        self._play_slot_audio(key, short=False)

    def _play_slot_audio(self, key: str, short: bool) -> None:
        slot = self.slots[key]
        wav = slot.sound_wav if short else slot.narration_wav
        if not short and (not wav.exists()):
            wav = slot.sound_wav

        if not wav.exists():
            self.status.set(f"Missing: {wav.name}")
            return

        self._end_flash()
        self.leds.set_all("gray")
        self.leds.set_color(key, "green")
        self.status.set(f"{'Sound' if short else 'Hold'}: {key}")

        def after():
            self.leds.set_color(key, "gray")
            self.status.set("Ready")

        self._play_audio_locked(wav, after_done=after)

    # ---------- Quiz / Abort ----------
    def on_quiz_down(self) -> None:
        if self.quiz_active:
            return
        if not self._begin_press("quiz", "quiz"):
            return

        self._quiz_hold_fired = False
        if self._quiz_job:
            try:
                self.root.after_cancel(self._quiz_job)
            except Exception:
                pass
            self._quiz_job = None

        self.status.set("Quiz: holding...")
        self._quiz_job = self.root.after(int(HOLD_SECONDS * 1000), self._start_quiz_hold_fire)

    def on_quiz_up(self) -> None:
        self._end_press("quiz", "quiz")

        if self._quiz_job:
            try:
                self.root.after_cancel(self._quiz_job)
            except Exception:
                pass
            self._quiz_job = None

        if self.quiz_active or self.input_locked or self._quiz_hold_fired:
            return

        if QUIZ_WELCOME_WAV.exists():
            self.status.set("Quiz: Welcome")
            self._play_audio_locked(QUIZ_WELCOME_WAV, after_done=lambda: self.status.set("Ready"))
        else:
            self.status.set("Ready")

    def on_abort_pressed(self) -> None:
        # Abort must work anytime during quiz (even if input_locked/audio is playing)
        if not self.quiz_active:
            return
        self.abort_quiz()

    def _start_quiz_hold_fire(self) -> None:
        self._quiz_hold_fired = True
        self._quiz_job = None
        if self._pressed != ("quiz", "quiz"):
            return
        self._start_quiz()

    def _start_quiz(self) -> None:
        eligible = [k for k in self.slot_keys if self.slots[k].sound_wav.exists()]
        if len(eligible) < 4:
            self.status.set("Need at least 4 insect*_sound.wav files for the quiz.")
            self._pressed = None
            self._apply_ui_state()
            return

        if not CORRECT_WAV.exists() or not INCORRECT_WAV.exists():
            self.status.set("Missing: correct.wav or incorrect.wav")
            self._pressed = None
            self._apply_ui_state()
            return

        rounds = min(QUIZ_ROUNDS, len(eligible))
        self.quiz_sequence = random.sample(eligible, rounds)

        self.quiz_active = True
        self.quiz_waiting = False
        self.q_index = 0
        self.score = 0

        self._pressed = None
        self._apply_ui_state()

        self._end_flash()
        self.leds.set_all("gray")

        if QUIZ_READY_WAV.exists():
            self.status.set("Quiz: Ready")
            self._play_audio_locked(QUIZ_READY_WAV, after_done=self._play_question)
        else:
            self._play_question()

    def abort_quiz(self) -> None:
        # Cancel timers
        if self._answer_timeout_job:
            try:
                self.root.after_cancel(self._answer_timeout_job)
            except Exception:
                pass
            self._answer_timeout_job = None

        if self._quiz_job:
            try:
                self.root.after_cancel(self._quiz_job)
            except Exception:
                pass
            self._quiz_job = None

        # Stop flash + stop audio
        self._stop_flash()
        self.audio.stop()

        # IMPORTANT: if we were locked by a previous play, its on_done won't run.
        # So force unlock now.
        self.input_locked = False

        # Reset quiz state
        self.quiz_active = False
        self.quiz_waiting = False
        self.q_index = 0
        self.score = 0
        self.quiz_options = []
        self.quiz_sequence = []
        self._pressed = None

        self._apply_ui_state()

        self.status.set("Quiz: Aborted")

        if QUIZ_ABORT_WAV.exists():
            self._play_audio_locked(QUIZ_ABORT_WAV, after_done=lambda: self.status.set("Ready"))
        else:
            self.status.set("Ready")

    # ---------- Quiz rounds ----------
    def _pick_4_options(self, correct_key: str) -> List[str]:
        others = [k for k in self.slot_keys if k != correct_key]
        picks = random.sample(others, 3) + [correct_key]
        random.shuffle(picks)
        return picks

    def _play_question(self) -> None:
        if not self.quiz_active:
            return

        idx = self.q_index + 1
        correct_key = self.quiz_sequence[self.q_index]
        self.quiz_options = self._pick_4_options(correct_key)
        self.quiz_waiting = False
        self._apply_ui_state()

        insect_wav = self.slots[correct_key].sound_wav
        if not insect_wav.exists():
            self.status.set(f"Missing: {insect_wav.name}")
            self.abort_quiz()
            return

        self.status.set(f"Quiz: Question {idx}")
        self._play_audio_locked(insect_wav, after_done=self._start_answer_window)

    def _start_answer_window(self) -> None:
        if not self.quiz_active:
            return
        self.quiz_waiting = True
        self.status.set("Quiz: Choose an insect")
        self._apply_ui_state()

        self._flash_uniform(self.quiz_options, "yellow", FLASH_INTERVAL_MS, ANSWER_SECONDS * 1000)
        self._answer_timeout_job = self.root.after(ANSWER_SECONDS * 1000, self._timeout)

    def _timeout(self) -> None:
        self._answer_timeout_job = None
        if not self.quiz_waiting or not self.quiz_active:
            return

        self.quiz_waiting = False
        self._apply_ui_state()
        self._end_flash()
        self._feedback(correct=False)

    def _handle_answer(self, key: str) -> None:
        if not self.quiz_waiting or not self.quiz_active:
            return
        if self.input_locked:
            return
        if key not in self.quiz_options:
            return

        self.quiz_waiting = False
        self._apply_ui_state()

        if self._answer_timeout_job:
            try:
                self.root.after_cancel(self._answer_timeout_job)
            except Exception:
                pass
            self._answer_timeout_job = None

        self._end_flash()

        correct_key = self.quiz_sequence[self.q_index]
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

        correct_key = self.quiz_sequence[self.q_index]
        color_map = {k: "red" for k in self.quiz_options}
        color_map[correct_key] = "green"

        self._flash_multicolor(color_map, interval_ms=250, duration_ms=int(RESULT_FLASH_SECONDS * 1000))

        def after():
            self._end_flash()
            self._next_or_end()

        self._play_audio_locked(wav, after_done=after)

    def _next_or_end(self) -> None:
        if not self.quiz_active:
            return
        self.q_index += 1
        if self.q_index >= len(self.quiz_sequence):
            self._end_quiz()
            return
        self._play_question()

    def _end_quiz(self) -> None:
        self.quiz_active = False
        self.quiz_waiting = False
        self._end_flash()
        self._pressed = None
        self._apply_ui_state()

        self.status.set("Quiz: Complete")

        complete = first_existing_ci(
            SOUNDS_DIR,
            "quiz_complete.wav",
            "quiz_comple.wav",
            "quize_comple.wav",
            "quiz_completed.wav",
        )
        if complete:
            self._play_audio_locked(complete, after_done=lambda: self.status.set("Ready"))
        else:
            self.status.set("Ready")


# ----------------------------
# UI
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


def build_ui(root: tk.Tk, controller: InsectController, slots: List[InsectSlot]) -> TkLedOutput:
    root.title("Insect Project (insect1..insect8)")

    photos: List[tk.PhotoImage] = []
    root._photos = photos  # keep refs alive

    grid = tk.Frame(root)
    grid.pack(padx=10, pady=10)

    for c in range(4):
        grid.grid_columnconfigure(c, uniform="col")

    dots: Dict[str, tk.Canvas] = {}

    for i, slot in enumerate(slots):
        r = i // 4
        c = i % 4

        cell = tk.Frame(grid, padx=10, pady=10)
        cell.grid(row=r, column=c, sticky="n")

        img_holder = tk.Frame(cell, width=MAX_IMG_W, height=MAX_IMG_H)
        img_holder.pack_propagate(False)
        img_holder.pack(pady=(0, 6))

        photo = load_and_scale_photo(slot.image_path)
        if photo:
            photos.append(photo)
            tk.Label(img_holder, image=photo).pack(expand=True)
        else:
            tk.Label(img_holder, text=f"Missing image\n{slot.image_path.name}").pack(expand=True)

        dot = tk.Canvas(cell, width=26, height=26, highlightthickness=0)
        dot.create_oval(4, 4, 22, 22, fill="gray", outline="", tags=("lamp",))
        dot.pack(pady=(0, 8))
        dots[slot.key] = dot

        btn = tk.Button(cell, text="", width=18, height=2)
        btn.pack()
        btn.bind("<ButtonPress-1>", lambda e, k=slot.key: controller.on_insect_down(k), add="+")
        btn.bind("<ButtonRelease-1>", lambda e, k=slot.key: controller.on_insect_up(k), add="+")

        controller.register_insect_button(slot.key, btn)

    bottom = tk.Frame(root)
    bottom.pack(pady=(0, 10))

    quiz_btn = tk.Button(bottom, text="Quiz", width=18, height=2)
    quiz_btn.grid(row=0, column=0, padx=(0, 10))
    quiz_btn.bind("<ButtonPress-1>", lambda e: controller.on_quiz_down(), add="+")
    quiz_btn.bind("<ButtonRelease-1>", lambda e: controller.on_quiz_up(), add="+")
    controller.set_quiz_button(quiz_btn)

    abort_btn = tk.Button(bottom, text="Abort", width=18, height=2, state=tk.DISABLED, command=controller.on_abort_pressed)
    abort_btn.grid(row=0, column=1)
    controller.set_abort_button(abort_btn)

    return TkLedOutput(dots)


def main():
    slots = slot_list()
    root = tk.Tk()

    status = tk.StringVar(value="Ready")
    audio = AudioPlayer()

    leds = TkLedOutput({})
    controller = InsectController(root, slots, audio, leds, status)

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