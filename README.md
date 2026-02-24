# Bee Mural Project (Python + Tkinter)

This project runs a small Tkinter app that simulates an interactive bee mural using:
- 8 bee slots (`bee1` to `bee8`)
- a Quiz button
- sound playback and LED-style feedback (shown as small circles)

## What you need on your laptop

### 1) Python
Install Python 3.9 or newer.

Check:
bash
python3 --version


2) Tkinter

Tkinter is usually included with Python on macOS and Windows.

Check:

python3 -c "import tkinter as tk; r=tk.Tk(); r.destroy(); print('Tkinter OK')"

If Tkinter is missing on Linux:

Ubuntu/Debian:

sudo apt-get update
sudo apt-get install python3-tk


2) Tkinter

Tkinter is usually included with Python on macOS and Windows.

Check:

python3 -c "import tkinter as tk; r=tk.Tk(); r.destroy(); print('Tkinter OK')"

If Tkinter is missing on Linux:

Ubuntu/Debian:

sudo apt-get update
sudo apt-get install python3-tk

How to Run 

1) Create and activate a virtual environment

macOS / Linux:

python3 -m venv .venv
source .venv/bin/activate

Windows (PowerShell):

python -m venv .venv
.\.venv\Scripts\Activate.ps1
2) (Optional) Generate sample sounds

If you have make_sounds.py configured and want to regenerate audio:

python make_sounds.py
3) Run the app
python main.py
Audio playback notes

macOS uses afplay (built-in)

Windows uses winsound (built-in)

Linux needs aplay or paplay

On Ubuntu/Debian you can install audio tools with:

sudo apt-get install alsa-utils pulseaudio-utils
