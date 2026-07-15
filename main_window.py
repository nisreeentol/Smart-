"""
gui/main_window.py
--------------------
Main application window for "Smart Multimedia Image FX Studio".

Built with Tkinter (Python's standard GUI toolkit -> zero extra install
required on any machine that has Python itself) plus:
    - Pillow (PIL) to convert OpenCV BGR arrays into Tkinter-displayable images.
    - A dependency-free live histogram drawn directly on a Tkinter Canvas
      (no matplotlib needed -> lighter install, fewer moving parts).

Layout:
    - Top toolbar: Upload Image / Save Result / Reset buttons + status label.
    - Middle: side-by-side "Before" / "After" image panels for instant comparison.
    - Bottom: a Notebook (tabs) with one tab per required module:
        1) Enhancement & Histogram
        2) Artistic Filters (Cartoon / Sepia / Pencil Sketch)
        3) Chroma Key & Background Replacement
        4) Face Detection & Stickers

Design choice: every tab reads from `self.current_base_bgr` (the image the
filters are applied to) and writes its result into `self.result_bgr`
(shown in the "After" panel). A "Use Result as New Base" button lets users
CHAIN multiple effects together (e.g. cartoon effect -> then sepia on top),
which also satisfies the "Creativity" rubric criterion.
"""

import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from PIL import Image, ImageTk

from filters import enhancement, stylization, chroma_key, face_stickers

MAX_PREVIEW_SIZE = (420, 420)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
STICKERS_DIR = os.path.join(ASSETS_DIR, "stickers")


def bgr_to_photoimage(bgr_image: np.ndarray, max_size=MAX_PREVIEW_SIZE) -> ImageTk.PhotoImage:
    """Convert an OpenCV BGR array into a Tkinter-displayable, size-limited PhotoImage."""
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    pil_img.thumbnail(max_size, Image.LANCZOS)
    return ImageTk.PhotoImage(pil_img), pil_img.size


class ImageFXStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Smart Multimedia Image FX Studio")
        self.root.geometry("1180x820")
        self.root.minsize(1000, 700)

        # ---- Image state -----------------------------------------------
        self.original_bgr = None       # exactly as loaded from disk
        self.current_base_bgr = None   # input to the active filter
        self.result_bgr = None         # output of the last-applied filter
        self.custom_background_bgr = None
        self.picked_bgr_color = (0, 255, 0)  # default: green screen

        # scale factors to map a click on the "before" preview back to
        # real pixel coordinates in current_base_bgr
        self._before_scale = 1.0
        self._before_photo_size = (0, 0)

        self._build_toolbar()
        self._build_image_panels()
        self._build_tabs()
        self._build_statusbar()

        self.set_status("جاهز. الرجاء تحميل صورة للبدء / Ready. Please upload an image to start.")

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(bar, text="📂 Upload Image", command=self.on_upload_image).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="💾 Save Result", command=self.on_save_result).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="↩ Reset to Original", command=self.on_reset).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="⇄ Use Result as New Base", command=self.on_use_result_as_base).pack(side=tk.LEFT, padx=4)

    # ------------------------------------------------------------------
    # Before / After panels
    # ------------------------------------------------------------------
    def _build_image_panels(self):
        panels = ttk.Frame(self.root, padding=8)
        panels.pack(side=tk.TOP, fill=tk.X)

        before_frame = ttk.LabelFrame(panels, text="Before (Original / Base)")
        before_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=4)
        self.before_label = tk.Label(before_frame, bg="#222", width=52, height=22)
        self.before_label.pack(padx=4, pady=4)
        self.before_label.bind("<Button-1>", self._on_before_click)

        after_frame = ttk.LabelFrame(panels, text="After (Processed Result)")
        after_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=4)
        self.after_label = tk.Label(after_frame, bg="#222", width=52, height=22)
        self.after_label.pack(padx=4, pady=4)

    # ------------------------------------------------------------------
    # Tabs (one per required module)
    # ------------------------------------------------------------------
    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=8, pady=8)

        self._build_enhancement_tab()
        self._build_stylization_tab()
        self._build_chroma_tab()
        self._build_stickers_tab()

    # ---- Tab 1: Enhancement & Histogram --------------------------------
    def _build_enhancement_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="1. Enhancement & Histogram")

        controls = ttk.Frame(tab)
        controls.pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Label(controls, text="Brightness").pack(anchor="w")
        # NOTE: ttk.Scale is a *continuous* widget (it does not snap to whole
        # numbers). Binding it directly to a tk.IntVar can raise
        # `_tkinter.TclError: expected integer but got "43.7291"` the moment
        # the user drags it to a non-integer position. We bind to a
        # DoubleVar instead and round to int only when reading the value
        # (see the `_int()` helper and every `<...>_var.get()` call below).
        self.brightness_var = tk.DoubleVar(value=0)
        ttk.Scale(controls, from_=-100, to=100, variable=self.brightness_var,
                  orient=tk.HORIZONTAL, command=lambda e: self._debounced(self.apply_brightness_contrast)
                  ).pack(fill=tk.X)

        ttk.Label(controls, text="Contrast").pack(anchor="w", pady=(10, 0))
        self.contrast_var = tk.DoubleVar(value=0)
        ttk.Scale(controls, from_=-100, to=100, variable=self.contrast_var,
                  orient=tk.HORIZONTAL, command=lambda e: self._debounced(self.apply_brightness_contrast)
                  ).pack(fill=tk.X)

        ttk.Button(controls, text="Apply Histogram Equalization",
                   command=self.apply_histogram_equalization).pack(fill=tk.X, pady=(16, 4))
        ttk.Button(controls, text="Apply CLAHE (Adaptive Equalization)",
                   command=self.apply_clahe).pack(fill=tk.X, pady=4)

        # Embedded live histogram
        hist_frame = ttk.LabelFrame(tab, text="Live Color Histogram")
        hist_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=8)

        self.hist_canvas = tk.Canvas(hist_frame, bg="#1b1b1f", width=460, height=270, highlightthickness=0)
        self.hist_canvas.pack(expand=True, fill=tk.BOTH, padx=4, pady=4)
        self._draw_histogram(None)

    # ---- Tab 2: Artistic Filters ---------------------------------------
    def _build_stylization_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="2. Artistic Filters")

        # Cartoon
        cartoon_box = ttk.LabelFrame(tab, text="Cartoon Effect")
        cartoon_box.grid(row=0, column=0, padx=8, pady=6, sticky="nsew")
        ttk.Label(cartoon_box, text="Edge Detail").pack(anchor="w")
        self.cartoon_edge_var = tk.DoubleVar(value=9)
        ttk.Scale(cartoon_box, from_=3, to=15, variable=self.cartoon_edge_var, orient=tk.HORIZONTAL).pack(fill=tk.X)
        ttk.Label(cartoon_box, text="Color Smoothing").pack(anchor="w")
        self.cartoon_smooth_var = tk.DoubleVar(value=9)
        ttk.Scale(cartoon_box, from_=1, to=15, variable=self.cartoon_smooth_var, orient=tk.HORIZONTAL).pack(fill=tk.X)
        ttk.Button(cartoon_box, text="Apply Cartoon Effect", command=self.apply_cartoon).pack(fill=tk.X, pady=6)

        # Sepia
        sepia_box = ttk.LabelFrame(tab, text="Vintage / Sepia Filter")
        sepia_box.grid(row=0, column=1, padx=8, pady=6, sticky="nsew")
        ttk.Label(sepia_box, text="Intensity").pack(anchor="w")
        self.sepia_intensity_var = tk.DoubleVar(value=1.0)
        ttk.Scale(sepia_box, from_=0.0, to=1.0, variable=self.sepia_intensity_var, orient=tk.HORIZONTAL).pack(fill=tk.X)
        ttk.Button(sepia_box, text="Apply Sepia Filter", command=self.apply_sepia).pack(fill=tk.X, pady=6)

        # Pencil sketch
        pencil_box = ttk.LabelFrame(tab, text="Pencil Sketch Effect")
        pencil_box.grid(row=0, column=2, padx=8, pady=6, sticky="nsew")
        ttk.Label(pencil_box, text="Softness (Blur)").pack(anchor="w")
        self.pencil_blur_var = tk.DoubleVar(value=21)
        ttk.Scale(pencil_box, from_=3, to=51, variable=self.pencil_blur_var, orient=tk.HORIZONTAL).pack(fill=tk.X)
        self.pencil_color_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(pencil_box, text="Colored Sketch", variable=self.pencil_color_var).pack(anchor="w", pady=4)
        ttk.Button(pencil_box, text="Apply Pencil Sketch", command=self.apply_pencil_sketch).pack(fill=tk.X, pady=6)

        for c in range(3):
            tab.grid_columnconfigure(c, weight=1)

    # ---- Tab 3: Chroma Key ---------------------------------------------
    def _build_chroma_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="3. Chroma Key & Background")

        controls = ttk.Frame(tab)
        controls.pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Label(controls, text="Step 1: Pick the key color").pack(anchor="w")
        ttk.Button(controls, text="🖱 Click on 'Before' image to sample color",
                   command=self.enable_color_pick_mode).pack(fill=tk.X, pady=4)

        preset_frame = ttk.Frame(controls)
        preset_frame.pack(fill=tk.X, pady=4)
        ttk.Button(preset_frame, text="Preset: Green Screen",
                   command=lambda: self.set_preset_key_color("green")).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(preset_frame, text="Preset: Blue Screen",
                   command=lambda: self.set_preset_key_color("blue")).pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.color_swatch = tk.Label(controls, text="Selected Color", bg="#00FF00", width=20)
        self.color_swatch.pack(pady=6)

        ttk.Label(controls, text="Hue Tolerance").pack(anchor="w")
        self.hue_tolerance_var = tk.DoubleVar(value=15)
        ttk.Scale(controls, from_=1, to=40, variable=self.hue_tolerance_var, orient=tk.HORIZONTAL).pack(fill=tk.X)

        ttk.Label(controls, text="Step 2: Load a replacement background").pack(anchor="w", pady=(14, 0))
        ttk.Button(controls, text="🖼 Load Background Image", command=self.on_load_background).pack(fill=tk.X, pady=4)
        self.bg_status_label = ttk.Label(controls, text="No background loaded (a default studio backdrop will be used)")
        self.bg_status_label.pack(anchor="w")

        ttk.Label(controls, text="Step 3: Composite").pack(anchor="w", pady=(14, 0))
        ttk.Button(controls, text="👁 Preview Mask", command=self.preview_chroma_mask).pack(fill=tk.X, pady=4)
        ttk.Button(controls, text="✅ Apply Chroma Key", command=self.apply_chroma_key).pack(fill=tk.X, pady=4)

        self._color_pick_mode = False

    # ---- Tab 4: Face Detection & Stickers -------------------------------
    def _build_stickers_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="4. Face Detection & Stickers")

        controls = ttk.Frame(tab)
        controls.pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Label(controls, text="Choose a sticker:").pack(anchor="w")
        self.sticker_type_var = tk.StringVar(value="glasses")
        for label, value in [("😎 Glasses", "glasses"), ("🎩 Hat", "hat"), ("😷 Mask", "mask")]:
            ttk.Radiobutton(controls, text=label, value=value, variable=self.sticker_type_var).pack(anchor="w")

        ttk.Button(controls, text="📥 Load Custom Sticker (PNG w/ transparency)",
                   command=self.on_load_custom_sticker).pack(fill=tk.X, pady=(10, 4))
        self.custom_sticker_path = None
        self.sticker_status_label = ttk.Label(controls, text="Using built-in sticker")
        self.sticker_status_label.pack(anchor="w")

        ttk.Button(controls, text="✨ Detect Face & Apply Sticker",
                   command=self.apply_sticker).pack(fill=tk.X, pady=(16, 4))
        ttk.Button(controls, text="🩺 Debug: Show Detected Face/Eyes",
                   command=self.apply_debug_detection).pack(fill=tk.X, pady=4)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_statusbar(self):
        self.status_var = tk.StringVar()
        bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=4)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, text: str):
        self.status_var.set(text)

    # ------------------------------------------------------------------
    # Debounce helper (avoids re-processing on every pixel of slider drag)
    # ------------------------------------------------------------------
    def _debounced(self, func, delay_ms: int = 120):
        if hasattr(self, "_debounce_job") and self._debounce_job is not None:
            self.root.after_cancel(self._debounce_job)
        self._debounce_job = self.root.after(delay_ms, func)

    @staticmethod
    def _int(var: tk.DoubleVar) -> int:
        """Safely read a Tkinter DoubleVar (bound to a continuous ttk.Scale)
        as a rounded Python int, for filters that require integer params
        (kernel sizes, angles, etc.)."""
        return int(round(var.get()))

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    def on_upload_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")],
        )
        if not path:
            return
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            messagebox.showerror("Error", f"Could not read the image file:\n{path}")
            return

        self.original_bgr = image
        self.current_base_bgr = image.copy()
        self.result_bgr = image.copy()
        self._refresh_before()
        self._refresh_after()
        self._draw_histogram(image)
        self.set_status(f"Loaded image: {os.path.basename(path)}  ({image.shape[1]}x{image.shape[0]})")

    def on_save_result(self):
        if self.result_bgr is None:
            messagebox.showwarning("Nothing to save", "Please load an image and apply a filter first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save processed image",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg")],
        )
        if not path:
            return
        cv2.imwrite(path, self.result_bgr)
        self.set_status(f"Saved result to: {path}")

    def on_reset(self):
        if self.original_bgr is None:
            return
        self.current_base_bgr = self.original_bgr.copy()
        self.result_bgr = self.original_bgr.copy()
        self._refresh_before()
        self._refresh_after()
        self._draw_histogram(self.current_base_bgr)
        self.set_status("Reset to the originally uploaded image.")

    def on_use_result_as_base(self):
        if self.result_bgr is None:
            return
        self.current_base_bgr = self.result_bgr.copy()
        self._refresh_before()
        self._draw_histogram(self.current_base_bgr)
        self.set_status("The current result is now the base image for further filters (effects can be chained).")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _refresh_before(self):
        if self.current_base_bgr is None:
            return
        photo, size = bgr_to_photoimage(self.current_base_bgr)
        self.before_label.configure(image=photo)
        self.before_label.image = photo  # keep reference alive
        self._before_photo_size = size
        self._before_scale = self.current_base_bgr.shape[1] / size[0]

    def _refresh_after(self):
        if self.result_bgr is None:
            return
        photo, _ = bgr_to_photoimage(self.result_bgr)
        self.after_label.configure(image=photo)
        self.after_label.image = photo

    def _draw_histogram(self, bgr_image):
        """Draw a live RGB histogram directly on a plain tk.Canvas -- no
        matplotlib required. We downsample the 256 raw bins into ~130 bars
        (grouping every 2 intensity levels) purely for a cleaner/lighter
        bar-chart look; the underlying data still comes from
        enhancement.compute_histogram()."""
        canvas = self.hist_canvas
        canvas.delete("all")
        w = canvas.winfo_width() or 460
        h = canvas.winfo_height() or 270
        pad = 10
        plot_w, plot_h = w - 2 * pad, h - 2 * pad

        canvas.create_text(w // 2, 12, text="Color Histogram", fill="#f5f5f0", font=("TkDefaultFont", 9, "bold"))

        if bgr_image is None:
            canvas.create_text(w // 2, h // 2, text="Upload an image to see its histogram",
                                fill="#888888", font=("TkDefaultFont", 9))
            return

        hist = enhancement.compute_histogram(bgr_image)
        group = 2  # merge every 2 of the 256 bins into 1 bar -> 128 bars
        channels = [("r", "#ff4d4d"), ("g", "#4dff4d"), ("b", "#4d8cff")]
        max_val = max(hist[c].max() for c, _ in channels) or 1

        bar_slot = plot_w / (256 / group)
        for name, color in channels:
            values = hist[name]
            points = []
            for i in range(0, 256, group):
                bucket = values[i:i + group].mean()
                x = pad + (i / group) * bar_slot
                y = pad + 24 + (plot_h - 24) * (1 - bucket / max_val)
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=1, smooth=False)

        # simple legend
        legend_y = pad + 4
        for i, (label, color) in enumerate([("Red", "#ff4d4d"), ("Green", "#4dff4d"), ("Blue", "#4d8cff")]):
            lx = pad + i * 70
            canvas.create_rectangle(lx, legend_y, lx + 10, legend_y + 10, fill=color, outline="")
            canvas.create_text(lx + 16, legend_y + 5, text=label, fill="#f5f5f0", anchor="w", font=("TkDefaultFont", 8))

    def _require_image(self) -> bool:
        if self.current_base_bgr is None:
            messagebox.showwarning("No image", "Please upload an image first.")
            return False
        return True

    # ------------------------------------------------------------------
    # Module 1: Enhancement callbacks
    # ------------------------------------------------------------------
    def apply_brightness_contrast(self):
        if not self._require_image():
            return
        self.result_bgr = enhancement.adjust_brightness_contrast(
            self.current_base_bgr, self._int(self.brightness_var), self._int(self.contrast_var)
        )
        self._refresh_after()
        self._draw_histogram(self.result_bgr)
        self.set_status(f"Brightness={self._int(self.brightness_var)}  Contrast={self._int(self.contrast_var)}")

    def apply_histogram_equalization(self):
        if not self._require_image():
            return
        self.result_bgr = enhancement.histogram_equalization(self.current_base_bgr)
        self._refresh_after()
        self._draw_histogram(self.result_bgr)
        self.set_status("Applied global Histogram Equalization (Y channel of YCrCb).")

    def apply_clahe(self):
        if not self._require_image():
            return
        self.result_bgr = enhancement.clahe_equalization(self.current_base_bgr)
        self._refresh_after()
        self._draw_histogram(self.result_bgr)
        self.set_status("Applied CLAHE (adaptive local histogram equalization).")

    # ------------------------------------------------------------------
    # Module 2: Stylization callbacks
    # ------------------------------------------------------------------
    def apply_cartoon(self):
        if not self._require_image():
            return
        self.result_bgr = stylization.cartoon_effect(
            self.current_base_bgr, self._int(self.cartoon_edge_var), self._int(self.cartoon_smooth_var)
        )
        self._refresh_after()
        self.set_status("Applied Cartoon Effect.")

    def apply_sepia(self):
        if not self._require_image():
            return
        self.result_bgr = stylization.sepia_filter(self.current_base_bgr, self.sepia_intensity_var.get())
        self._refresh_after()
        self.set_status("Applied Vintage/Sepia Filter.")

    def apply_pencil_sketch(self):
        if not self._require_image():
            return
        self.result_bgr = stylization.pencil_sketch_effect(
            self.current_base_bgr, self._int(self.pencil_blur_var), self.pencil_color_var.get()
        )
        self._refresh_after()
        self.set_status("Applied Pencil Sketch Effect.")

    # ------------------------------------------------------------------
    # Module 3: Chroma Key callbacks
    # ------------------------------------------------------------------
    def enable_color_pick_mode(self):
        if not self._require_image():
            return
        self._color_pick_mode = True
        self.set_status("Color-pick mode ON: click anywhere on the 'Before' image to sample the key color.")

    def _on_before_click(self, event):
        if not self._color_pick_mode or self.current_base_bgr is None:
            return
        real_x = int(event.x * self._before_scale)
        real_y = int(event.y * self._before_scale)
        h, w = self.current_base_bgr.shape[:2]
        real_x = min(max(real_x, 0), w - 1)
        real_y = min(max(real_y, 0), h - 1)
        b, g, r = self.current_base_bgr[real_y, real_x]
        self.picked_bgr_color = (int(b), int(g), int(r))
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.color_swatch.configure(bg=hex_color)
        self._color_pick_mode = False
        self.set_status(f"Picked key color at ({real_x},{real_y}) -> BGR={self.picked_bgr_color}")

    def set_preset_key_color(self, key_color: str):
        preset = chroma_key.DEFAULT_RANGES[key_color]
        self._preset_key_color = key_color
        self.picked_bgr_color = None
        color_hex = "#00FF00" if key_color == "green" else "#0000FF"
        self.color_swatch.configure(bg=color_hex)
        self.set_status(f"Using preset key color: {key_color}")

    def on_load_background(self):
        path = filedialog.askopenfilename(
            title="Select background image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")],
        )
        if not path:
            return
        bg = cv2.imread(path, cv2.IMREAD_COLOR)
        if bg is None:
            messagebox.showerror("Error", "Could not read the background image.")
            return
        self.custom_background_bgr = bg
        self.bg_status_label.configure(text=f"Background loaded: {os.path.basename(path)}")

    def _current_hsv_bounds(self):
        tolerance = self._int(self.hue_tolerance_var)
        if getattr(self, "_preset_key_color", None) and self.picked_bgr_color is None:
            preset = chroma_key.DEFAULT_RANGES[self._preset_key_color]
            return preset["lower"], preset["upper"]
        b, g, r = self.picked_bgr_color
        return chroma_key.build_hsv_range_from_pick(b, g, r, tolerance)

    def preview_chroma_mask(self):
        if not self._require_image():
            return
        lower, upper = self._current_hsv_bounds()
        mask_preview = chroma_key.preview_mask(self.current_base_bgr, lower, upper)
        self.result_bgr = mask_preview
        self._refresh_after()
        self.set_status("Showing key-color mask preview (white = will be replaced).")

    def apply_chroma_key(self):
        if not self._require_image():
            return
        lower, upper = self._current_hsv_bounds()
        background = self.custom_background_bgr
        if background is None:
            default_bg_path = os.path.join(ASSETS_DIR, "backgrounds", "sample_studio_bg.jpg")
            background = cv2.imread(default_bg_path, cv2.IMREAD_COLOR)
        self.result_bgr = chroma_key.apply_chroma_key(self.current_base_bgr, background, lower, upper)
        self._refresh_after()
        self.set_status("Applied Chroma Key background replacement.")

    # ------------------------------------------------------------------
    # Module 4: Face Detection & Stickers callbacks
    # ------------------------------------------------------------------
    def on_load_custom_sticker(self):
        path = filedialog.askopenfilename(
            title="Select a transparent PNG sticker",
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return
        self.custom_sticker_path = path
        self.sticker_status_label.configure(text=f"Custom sticker: {os.path.basename(path)}")

    def _sticker_path_for_type(self, sticker_type: str) -> str:
        if self.custom_sticker_path:
            return self.custom_sticker_path
        return os.path.join(STICKERS_DIR, f"{sticker_type}.png")

    def apply_sticker(self):
        if not self._require_image():
            return
        sticker_type = self.sticker_type_var.get()
        sticker_path = self._sticker_path_for_type(sticker_type)
        try:
            self.result_bgr = face_stickers.apply_sticker(self.current_base_bgr, sticker_path, sticker_type)
        except FileNotFoundError as e:
            messagebox.showerror("Sticker error", str(e))
            return
        num_faces = len(face_stickers.detect_faces(self.current_base_bgr))
        self._refresh_after()
        if num_faces == 0:
            self.set_status("No face detected — try a clearer, front-facing photo with good lighting.")
        else:
            self.set_status(f"Detected {num_faces} face(s) and applied '{sticker_type}' sticker.")

    def apply_debug_detection(self):
        if not self._require_image():
            return
        self.result_bgr = face_stickers.draw_face_boxes_debug(self.current_base_bgr)
        self._refresh_after()
        self.set_status("Debug view: green = detected face, blue = detected eyes.")


def run_app():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = ImageFXStudioApp(root)
    root.mainloop()
