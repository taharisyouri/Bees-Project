import threading
import math
import pyttsx3


class AudioManager:
    """Manage text-to-speech playback and ensure a minimum playback duration."""
    def __init__(self, rate=150, volume=0.9):
        self._lock = threading.Lock()
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', rate)
        self.engine.setProperty('volume', volume)
        self._current_thread = None

    def _estimate_duration_seconds(self, text, rate_wpm=None):
        words = len(text.split())
        rate = rate_wpm if rate_wpm is not None else self.engine.getProperty('rate')
        # rate is roughly words per minute
        if rate <= 0:
            rate = 150
        return words / rate * 60.0

    def _speak_blocking(self, text):
        try:
            self.engine.stop()
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception:
            pass

    def play_intro(self, bee_name, intro_text, min_seconds=60):
        """Play an introduction for the given bee for at least min_seconds.

        This runs the TTS playback in a background thread and will repeat the
        intro text if needed to reach roughly the requested duration.
        """
        def worker():
            with self._lock:
                # Estimate single-pass duration
                single = self._estimate_duration_seconds(intro_text)
                if single <= 0:
                    to_say = f"Here is an introduction to the {bee_name}."
                else:
                    repeats = max(1, math.ceil(min_seconds / single))
                    to_say = (f"Introduction to the {bee_name}: " + intro_text + " ") * repeats

                # Speak (blocking inside this thread)
                self._speak_blocking(to_say)

        # Stop any previous playback thread if running
        if self._current_thread and self._current_thread.is_alive():
            try:
                self.engine.stop()
            except Exception:
                pass

        t = threading.Thread(target=worker, daemon=True)
        self._current_thread = t
        t.start()
