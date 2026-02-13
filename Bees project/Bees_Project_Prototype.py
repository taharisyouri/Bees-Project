
import tkinter as tk
from tkinter import messagebox
import time
import random
import threading
import pygame  # for audio playback

pygame.mixer.init()

# -----------------------------
# Bee Data
# -----------------------------
bees = {
    "Worker Bee": "audio/worker.mp3",
    "Drone Bee": "audio/drone.mp3",
    "Queen Bee": "audio/queen.mp3",
    "Nurse Bee": "audio/nurse.mp3",
    "Guard Bee": "audio/guard.mp3",
    "Scout Bee": "audio/scout.mp3",
    "Forager Bee": "audio/forager.mp3",
    "Builder Bee": "audio/builder.mp3"
}

bee_list = list(bees.keys())

# -----------------------------
# Main Application
# -----------------------------
class BeeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bees Project Interface")
        self.hold_start = None
        self.current_mode = None

        self.main_frame = tk.Frame(root)
        self.main_frame.pack(pady=20)

        self.create_main_buttons()

    # -----------------------------
    # Main Buttons
    # -----------------------------
    def create_main_buttons(self):
        tk.Button(self.main_frame, text="Interactive Mode", width=20, height=2,
                  command=self.interactive_mode).pack(pady=10)

        tk.Button(self.main_frame, text="Game Mode", width=20, height=2,
                  command=self.game_mode).pack(pady=10)

    # -----------------------------
    # INTERACTIVE MODE
    # -----------------------------
    def interactive_mode(self):
        self.clear_frame()
        tk.Label(self.main_frame, text="Interactive Bee Mode", font=("Arial", 16)).pack(pady=10)

        for bee in bee_list:
            btn = tk.Button(self.main_frame, text=bee, width=20, height=2)
            btn.pack(pady=5)

            btn.bind("<ButtonPress-1>", lambda e, b=bee: self.start_hold(b))
            btn.bind("<ButtonRelease-1>", lambda e, b=bee: self.end_hold(b))

        tk.Button(self.main_frame, text="Back", command=self.reset).pack(pady=20)

    def start_hold(self, bee):
        self.hold_start = time.time()

    def end_hold(self, bee):
        hold_time = time.time() - self.hold_start

        if hold_time >= 3:
            self.play_intro(bee)
        else:
            messagebox.showinfo("Bee Type", f"You selected: {bee}")

    def play_intro(self, bee):
        messagebox.showinfo("Bee Introduction", f"Playing 1-minute introduction for {bee}...")

        audio_file = bees[bee]
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
        except:
            messagebox.showerror("Audio Error", f"Audio file not found: {audio_file}")

    # -----------------------------
    # GAME MODE
    # -----------------------------
    def game_mode(self):
        self.clear_frame()
        tk.Label(self.main_frame, text="Bee Quiz Game", font=("Arial", 16)).pack(pady=10)

        self.correct_bee = random.choice(bee_list)
        options = random.sample(bee_list, 4)

        if self.correct_bee not in options:
            options[random.randint(0, 3)] = self.correct_bee

        self.option_buttons = []

        for bee in options:
            btn = tk.Button(self.main_frame, text=bee, width=20, height=2, bg="white",
                            command=lambda b=bee: self.check_answer(b))
            btn.pack(pady=5)
            self.option_buttons.append(btn)

        tk.Button(self.main_frame, text="Back", command=self.reset).pack(pady=20)

    def check_answer(self, selected_bee):
        for btn in self.option_buttons:
            if btn["text"] == self.correct_bee:
                btn.config(bg="green")
            else:
                btn.config(bg="red")

        if selected_bee == self.correct_bee:
            messagebox.showinfo("Correct!", "You chose the correct bee!")
        else:
            messagebox.showerror("Wrong!", "That is not the correct bee.")

    # -----------------------------
    # Utility
    # -----------------------------
    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def reset(self):
        self.clear_frame()
        self.create_main_buttons()


# -----------------------------
# Run App
# -----------------------------
root = tk.Tk()
app = BeeApp(root)
root.mainloop()
