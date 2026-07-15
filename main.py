"""
main.py
--------
Entry point for "Smart Multimedia Image FX Studio".

Run with:
    python main.py

Requirements (see requirements.txt):
    opencv-python-headless, numpy, pillow
    (tkinter ships with standard Python installers on Windows/macOS;
     on Linux install it via your package manager, e.g.:
         sudo apt install python3-tk)
"""

import sys
import os

# Make sure the project root is on sys.path so `filters` and `gui` packages
# can be imported regardless of the working directory main.py is run from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import run_app


def main():
    run_app()


if __name__ == "__main__":
    main()
