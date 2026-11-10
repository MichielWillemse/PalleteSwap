"""Palette Swap Studio

Apply new color schemes to a 16-color (or fewer) RGB PNG.

Layout
------
+--------------------------------------------------------------------+
| Toolbar: Open PNG | Update preview | Apply & Save PNG | Save ...   |
+--------------------------------------------------------------------+
| Color mapping (left column)        | New palette preview            |
|  Original        New palette       | (right column, about double    |
|  R G B [sw] | [sw] R G B [esw]RGB |  the dimensions of the         |
|  up/dn/x/grad ...                  |  original picture)             |
|  [+ Add color]  Palette: [v] Gradient: [v]                         |
| +------------------------------+   |                                |
| | Original image (small)       |   |                                |
| +------------------------------+   |                                |
+--------------------------------------------------------------------+

Palettes live in a dictionary that is persisted to palettes.json next to
this script, so you can hand-edit the JSON or add palettes inside the GUI
and save them under the same or a new name.

Mapping: each table row pairs one original color (left) with one new
color (right). The up/down arrows move a new color up or down between
rows (the original colors stay in place), which changes which original
color receives which new color. The preview is not auto-updated; use the
"Update preview" button in the top bar. The original image shows in a
small picture below the mapping block; the remapped image shows at the
right, about double those dimensions.

Gradients: press the grad button on a row to turn its new color into a
gradient across the image. The row's new color is the gradient start;
the end color gets its own swatch and R/G/B fields next to it (click the
swatch to pick a color, or type R/G/B values 0-255). Each gradient row
has its own direction dropdown next to its buttons; a newly enabled row
takes the direction from the "Gradient (default)" dropdown below the
table. The preview shows the result. Gradient rows are stored in
palettes.json as {"start": [r, g, b], "end": [r, g, b], "dir": "..."}
("dir" optional) and load back as gradients.

Dependencies: pillow  (pip install pillow)
Run:          python palette_swap_studio.py
"""

import json
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

MAX_COLORS = 16
PALETTE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "palettes.json")

# Preview sizes: the remapped image is about double the original preview
ORIG_PREVIEW_SIZE = (480, 360)
NEW_PREVIEW_SIZE = (960, 720)

# Safety valve for very large images (remapping loops per pixel in Python).
# None = no limit; set to a number (e.g. 4_000_000) to refuse bigger images.
MAX_IMAGE_PIXELS = None

# Directions a gradient can run across the image, as (dx, dy) in image
# coordinates (x grows right, y grows down).
GRADIENT_DIRECTIONS = {
    "left \u2192 right": (1, 0),
    "right \u2192 left": (-1, 0),
    "top \u2192 bottom": (0, 1),
    "bottom \u2192 top": (0, -1),
    "diagonal \u2198": (1, 1),
    "diagonal \u2199": (-1, 1),
}

# ---------------------------------------------------------------------------
# The editable palette dictionary.
# Add new palettes here, or via the GUI (Save Palette / Save As New).
# Each palette is a list of entries; order maps to the colors in the image.
# An entry is either [R, G, B] (flat color) or, for a gradient row,
# {"start": [R, G, B], "end": [R, G, B], "dir": "left \u2192 right"}.
# ---------------------------------------------------------------------------
DEFAULT_PALETTES = {
    "Original 16 gray": [[c, c, c] for c in range(0, 256, 17)],
    "Sepia tones": [[43, 29, 14], [59, 42, 23], [74, 55, 31],
                    [92, 68, 38], [109, 82, 48], [125, 96, 56],
                    [140, 109, 64], [156, 123, 72], [171, 137, 80],
                    [185, 151, 91], [198, 164, 104], [210, 178, 120],
                    [221, 192, 138], [231, 207, 160], [240, 221, 182],
                    [249, 236, 208]],
    "Cyberpunk neon": [[13, 2, 33], [25, 1, 54], [36, 0, 75],
                       [45, 10, 84], [60, 10, 99], [82, 22, 138],
                       [123, 31, 162], [156, 39, 176], [224, 64, 251],
                       [255, 77, 210], [255, 110, 199], [255, 128, 171],
                       [100, 255, 218], [0, 229, 255], [41, 121, 255],
                       [179, 136, 255]],
    "Forest greens": [[10, 31, 13], [18, 48, 23], [26, 65, 34],
                      [34, 81, 44], [43, 98, 55], [52, 114, 65],
                      [61, 131, 75], [70, 147, 86], [85, 168, 104],
                      [106, 189, 123], [127, 201, 139], [147, 215, 158],
                      [169, 229, 176], [191, 238, 197], [214, 245, 218],
                      [234, 251, 233]],
    "Sunset gradient": [
        {"start": [24, 10, 44], "end": [70, 18, 100],
         "dir": "top \u2192 bottom"},
        {"start": [255, 0, 0], "end": [255, 204, 0],
         "dir": "left \u2192 right"},
        {"start": [255, 110, 0], "end": [255, 224, 130],
         "dir": "diagonal \u2198"},
        [96, 24, 64], [128, 34, 74], [158, 48, 84], [186, 64, 94],
        [206, 92, 112], [224, 122, 132], [238, 152, 152], [246, 182, 172],
        [251, 208, 192], [253, 227, 212], [254, 241, 230], [255, 251, 242],
    ],
}


def _to_rgb(entry):
    """Convert one palette entry to an (R, G, B) tuple.

    Accepts [r, g, b] lists (the native RGB format) and, for backward
    compatibility, old "#rrggbb" hex strings.
    """
    if isinstance(entry, str) and entry.startswith("#"):
        return tuple(int(entry[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(v) for v in entry[:3])


def _parse_entry(entry):
    """Parse one palette entry into (color, gradient_end, direction).

    Flat entries ([r, g, b] or "#rrggbb") return (color, None, None).
    Gradient entries {"start": ..., "end": ..., "dir": ...} return
    (start, end, dir); "dir" is optional and must be a key of
    GRADIENT_DIRECTIONS, otherwise it is dropped (None).
    """
    if isinstance(entry, dict):
        direction = entry.get("dir")
        if direction not in GRADIENT_DIRECTIONS:
            direction = None
        return (_to_rgb(entry.get("start", [0, 0, 0])),
                _to_rgb(entry.get("end", [255, 255, 255])),
                direction)
    return _to_rgb(entry), None, None


def load_palettes():
    if os.path.exists(PALETTE_FILE):
        try:
            with open(PALETTE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {name: [list(c) for c in colors]
            for name, colors in DEFAULT_PALETTES.items()}


def save_palettes_to_disk(palettes):
    try:
        with open(PALETTE_FILE, "w", encoding="utf-8") as f:
            json.dump(palettes, f, indent=2)
    except OSError as exc:
        messagebox.showerror("Save error", f"Could not save palettes:\n{exc}")


class MappingRow:
    """One row of the color-mapping block.

    Grid columns: 0-2 original R,G,B | 3 original square | 4 new square |
    5-7 new R,G,B | 8 gradient end square | 9-11 gradient end R,G,B |
    12 order/remove/gradient buttons + per-row direction dropdown. The
    end square/fields and the dropdown are only shown on gradient rows.
    All rows share one grid, so everything stays aligned automatically.
    """

    def __init__(self, app, parent, grid_row, orig, new, end=None,
                 direction=None):
        self.app = app
        self.parent = parent
        self.grid_row = grid_row
        self.orig = orig  # (r, g, b) or None when no image is loaded
        self.updating = False
        self.gradient = end is not None
        self._grad_shown = False
        self._widgets = []

        def put(widget, column, **kw):
            widget.grid(row=grid_row, column=column, **kw)
            self._widgets.append(widget)

        # Original R, G, B: readonly boxes
        for col in range(3):
            txt = str(orig[col]) if orig else "\u2013"
            var = tk.StringVar(value=txt)
            entry = tk.Entry(parent, width=4, textvariable=var,
                             justify="center", state="readonly",
                             readonlybackground="white")
            put(entry, col, padx=1, pady=1)

        # Original color square
        self.orig_swatch = tk.Label(parent, width=4, height=1,
                                    relief="groove")
        put(self.orig_swatch, 3, padx=4)
        if orig:
            self.orig_swatch.config(bg="#%02x%02x%02x" % orig)

        # New color square (click to pick a color; gradient start if grad)
        self.new_swatch = tk.Label(parent, width=4, height=1,
                                   relief="groove", cursor="hand2")
        put(self.new_swatch, 4, padx=4)
        self.new_swatch.bind("<Button-1>", lambda _e: self.pick_new_color())

        # New R, G, B: editable boxes
        self.new_vars = []
        for i, v in enumerate(new):
            var = tk.StringVar(value=str(v))
            entry = tk.Entry(parent, width=4, textvariable=var,
                             justify="center")
            var.trace_add("write", self._on_new_rgb_typed)
            put(entry, 5 + i, padx=1, pady=1)
            self.new_vars.append(var)

        # Gradient end square + editable R,G,B fields (only gridded
        # while this row is a gradient)
        self.end_swatch = tk.Label(parent, width=3, height=1,
                                   relief="groove", cursor="hand2")
        self._widgets.append(self.end_swatch)
        self.end_swatch.bind("<Button-1>", lambda _e: self.pick_end_color())
        self.end_vars = []
        self.end_entries = []
        for _i in range(3):
            var = tk.StringVar(value="255")
            entry = tk.Entry(parent, width=4, textvariable=var,
                             justify="center")
            var.trace_add("write", self._on_end_rgb_typed)
            self.end_vars.append(var)
            self.end_entries.append(entry)
            self._widgets.append(entry)

        # Order, remove and gradient-toggle buttons
        btns = tk.Frame(parent)
        put(btns, 12, padx=(6, 0))
        tk.Button(btns, text="\u25b2", relief="flat",
                  command=lambda: app.move_new_color(self, -1)
                  ).pack(side="left")
        tk.Button(btns, text="\u25bc", relief="flat",
                  command=lambda: app.move_new_color(self, +1)
                  ).pack(side="left")
        tk.Button(btns, text="\u2715", fg="#b00", relief="flat",
                  command=self.remove).pack(side="left")
        self.grad_btn = tk.Button(btns, text="\u2207", relief="flat",
                                  command=self.toggle_gradient)
        self.grad_btn.pack(side="left", padx=(4, 0))
        # Per-row gradient direction (only shown on gradient rows)
        self.dir_var = tk.StringVar()
        self.dir_combo = ttk.Combobox(btns, textvariable=self.dir_var,
                                      state="readonly", width=11,
                                      values=list(GRADIENT_DIRECTIONS))

        self.set_new_color(new)
        self.set_end_color(end if end else (255, 255, 255))
        self.set_direction(direction)
        self.set_gradient(self.gradient)

    def destroy(self):
        for w in self._widgets:
            w.destroy()

    def remove(self):
        self.app.remove_mapping_row(self)

    def pick_new_color(self):
        hexcode = "#%02x%02x%02x" % self.get_new_color()
        chosen = colorchooser.askcolor(initialcolor=hexcode)
        if chosen and chosen[0]:
            self.set_new_color(tuple(int(c) for c in chosen[0]))

    def toggle_gradient(self):
        self.set_gradient(not self.gradient)

    def set_gradient(self, on):
        on = bool(on)
        if on and not self._grad_shown:
            self.end_swatch.grid(row=self.grid_row, column=8, padx=4)
            for i, entry in enumerate(self.end_entries):
                entry.grid(row=self.grid_row, column=9 + i, padx=1, pady=1)
            self.dir_combo.pack(side="left", padx=(4, 0))
            self._grad_shown = True
        elif not on and self._grad_shown:
            self.end_swatch.grid_remove()
            for entry in self.end_entries:
                entry.grid_remove()
            self.dir_combo.pack_forget()
            self._grad_shown = False
        self.gradient = on
        self.grad_btn.config(relief="sunken" if on else "flat")

    def pick_end_color(self):
        hexcode = "#%02x%02x%02x" % self.get_end_color()
        chosen = colorchooser.askcolor(initialcolor=hexcode)
        if chosen and chosen[0]:
            self.set_end_color(tuple(int(c) for c in chosen[0]))

    def _on_end_rgb_typed(self, *_):
        if self.updating:
            return
        self._clamp(self.end_vars)
        self._paint_end_swatch()

    def get_end_color(self):
        vals = []
        for var in self.end_vars:
            txt = var.get()
            n = int(txt) if txt.isdigit() else 0
            vals.append(max(0, min(255, n)))
        return tuple(vals)

    def set_end_color(self, color):
        self.updating = True
        for var, v in zip(self.end_vars, color):
            var.set(str(v))
        self.updating = False
        self._paint_end_swatch()

    def _paint_end_swatch(self):
        self.end_swatch.config(bg="#%02x%02x%02x" % self.get_end_color())

    def get_direction(self):
        d = self.dir_var.get()
        return d if d in GRADIENT_DIRECTIONS else None

    def set_direction(self, direction):
        if direction not in GRADIENT_DIRECTIONS:
            direction = self.app.gradient_dir_var.get()
        self.dir_var.set(direction)

    def snapshot(self):
        """The movable 'new' side of the row: color, end, flag, dir."""
        return (self.get_new_color(), self.get_end_color(),
                self.gradient, self.get_direction())

    def restore(self, snap):
        color, end, gradient, direction = snap
        self.set_new_color(color)
        self.set_end_color(end)
        self.set_direction(direction)
        self.set_gradient(gradient)

    def _on_new_rgb_typed(self, *_):
        if self.updating:
            return
        self._clamp(self.new_vars)
        self._paint_new_swatch()

    @staticmethod
    def _clamp(vars_):
        for var in vars_:
            txt = var.get()
            if not (txt == "" or txt.isdigit()):
                var.set("".join(ch for ch in txt if ch.isdigit())[:3])
            if var.get().isdigit() and int(var.get()) > 255:
                var.set("255")

    def set_new_color(self, color):
        self.updating = True
        for var, v in zip(self.new_vars, color):
            var.set(str(v))
        self.updating = False
        self._paint_new_swatch()

    def get_new_color(self):
        vals = []
        for var in self.new_vars:
            txt = var.get()
            n = int(txt) if txt.isdigit() else 0
            vals.append(max(0, min(255, n)))
        return tuple(vals)

    def _paint_new_swatch(self):
        rgb = self.get_new_color()
        self.new_swatch.config(bg="#%02x%02x%02x" % rgb)


class PaletteSwapStudio(tk.Tk):
    HEADER_ROWS = 2  # section titles row + R/G/B labels row

    def __init__(self):
        super().__init__()
        self.title("Palette Swap Studio")
        self.minsize(1280, 700)

        self.palettes = load_palettes()
        self.source_image = None
        self.original_colors = []
        self.rows = []
        self.gradient_dir_var = tk.StringVar(value="left \u2192 right")

        self._build_toolbar()
        self._build_main()
        self._build_mapper()
        self._build_preview()
        self._refresh_palette_dropdown()
        self.on_palette_selected()

    # ----------------------------------------------------------- toolbar
    def _build_toolbar(self):
        bar = tk.Frame(self, bd=1, relief="raised")
        bar.pack(side="top", fill="x")
        tk.Button(bar, text="Open PNG",
                  command=self.open_image).pack(side="left", padx=4, pady=4)
        tk.Button(bar, text="Update preview",
                  command=self.update_preview).pack(side="left", padx=4)
        tk.Button(bar, text="Apply & Save PNG",
                  command=self.apply_and_save).pack(side="left", padx=4)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y",
                                                   padx=6, pady=3)
        tk.Button(bar, text="Save Palette (same name)",
                  command=self.save_palette).pack(side="left", padx=4)
        tk.Button(bar, text="Save Palette As New...",
                  command=self.save_palette_as).pack(side="left", padx=4)
        self.status = tk.Label(bar, text="Open a PNG to begin.", anchor="w",
                               fg="#444")
        self.status.pack(side="left", padx=12)

    # ------------------------------------------------------------- main
    def _build_main(self):
        """Two-column body: mapping + original image left, preview right."""
        self.main = tk.Frame(self)
        self.main.pack(side="top", fill="both", expand=True, padx=8, pady=6)
        self.left = tk.Frame(self.main)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.right = tk.Frame(self.main)
        self.right.pack(side="left", fill="both", expand=True, padx=(6, 0))

    # ----------------------------------------------------------- mapper
    def _build_mapper(self):
        box = tk.LabelFrame(self.left, text="Color mapping")
        box.pack(side="top", fill="both", expand=True)

        self.table_frame = tk.Frame(box)
        self.table_frame.pack(fill="both", expand=True, padx=6, pady=(4, 2))

        # Header: section titles, and R/G/B labels once, on top of the
        # RGB fields.
        tk.Label(self.table_frame, text="Original",
                 font=("", 9, "bold")
                 ).grid(row=0, column=0, columnspan=3, sticky="ew")
        tk.Label(self.table_frame, text="New palette",
                 font=("", 9, "bold")
                 ).grid(row=0, column=5, columnspan=3, sticky="ew")
        tk.Label(self.table_frame, text="Gradient end",
                 font=("", 9, "bold")
                 ).grid(row=0, column=9, columnspan=3, sticky="ew")
        for col, channel in enumerate(("R", "G", "B")):
            tk.Label(self.table_frame, text=channel, fg="#666"
                     ).grid(row=1, column=col)
            tk.Label(self.table_frame, text=channel, fg="#666"
                     ).grid(row=1, column=5 + col)
            tk.Label(self.table_frame, text=channel, fg="#666"
                     ).grid(row=1, column=9 + col)
        tk.Label(self.table_frame, text="\u2192", fg="#666"
                 ).grid(row=1, column=8)

        # Bottom bar: add-color button, palette dropdown, gradient dir
        bottom = tk.Frame(box)
        bottom.pack(fill="x", padx=6, pady=(2, 6))
        tk.Button(bottom, text="+ Add color",
                  command=self.add_mapping_row).pack(side="left")
        tk.Label(bottom, text="Palette:").pack(side="left", padx=(18, 6))
        self.palette_var = tk.StringVar()
        self.dropdown = ttk.Combobox(bottom, textvariable=self.palette_var,
                                     state="readonly", width=24)
        self.dropdown.pack(side="left", expand=True, fill="x")
        self.dropdown.bind("<<ComboboxSelected>>", self.on_palette_selected)
        tk.Label(bottom, text="Gradient (default):").pack(side="left",
                                                            padx=(18, 6))
        ttk.Combobox(bottom, textvariable=self.gradient_dir_var,
                     state="readonly", width=13,
                     values=list(GRADIENT_DIRECTIONS)
                     ).pack(side="left")

    # ----------------------------------------------------------- preview
    def _build_preview(self):
        # Right column: remapped image, about double the original preview
        new_box = tk.LabelFrame(self.right, text="New palette preview")
        new_box.pack(side="top", fill="both", expand=True)
        self.new_preview = tk.Label(new_box)
        self.new_preview.pack(expand=True)

        # Left column, below the mapping block: small original picture
        orig_box = tk.LabelFrame(self.left, text="Original image")
        orig_box.pack(side="bottom", fill="x", pady=(6, 0))
        self.orig_preview = tk.Label(orig_box)
        self.orig_preview.pack(padx=6, pady=6)
        self._clear_preview()

    def _clear_preview(self):
        self.orig_preview.config(image="", text="Click 'Update preview'")
        self.new_preview.config(image="", text="Click 'Update preview'")

    def update_preview(self):
        if not self.source_image:
            messagebox.showinfo("Preview", "Open a PNG first.")
            return
        try:
            remapped = self.build_remap_image()
        except Exception as exc:
            messagebox.showerror("Preview error", str(exc))
            return
        for label, img, size in ((self.orig_preview, self.source_image,
                                  ORIG_PREVIEW_SIZE),
                                 (self.new_preview, remapped,
                                  NEW_PREVIEW_SIZE)):
            thumb = img.copy()
            thumb.thumbnail(size)
            label._photo = ImageTk.PhotoImage(thumb)
            label.config(image=label._photo, text="")

    # ------------------------------------------------------- image logic
    def open_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as exc:
            messagebox.showerror("Open error", str(exc))
            return

        if (MAX_IMAGE_PIXELS is not None
                and img.width * img.height > MAX_IMAGE_PIXELS):
            messagebox.showwarning(
                "Open",
                f"Image has {img.width * img.height} pixels; this build "
                f"allows at most {MAX_IMAGE_PIXELS}.")
            return

        colors = sorted(set(img.getdata()))[:MAX_COLORS]
        if not colors:
            messagebox.showerror("Open error", "No colors found.")
            return

        self.source_image = img
        self.original_colors = colors
        # Keep the current new colors, pad or drop to the row count needed
        news = [row.get_new_color() for row in self.rows]
        ends = [row.get_end_color() if row.gradient else None
                for row in self.rows]
        dirs = [row.get_direction() if row.gradient else None
                for row in self.rows]
        n = max(len(colors), len(news))
        origs = list(colors) + [None] * (n - len(colors))
        news += [(0, 0, 0)] * (n - len(news))
        ends += [None] * (n - len(ends))
        dirs += [None] * (n - len(dirs))
        self._rebuild_table(origs, news, ends, dirs)
        self._clear_preview()
        self.status.config(text=f"{os.path.basename(path)} \u2014 "
                                f"{len(colors)} unique colors")

    # ------------------------------------------------------------ table
    def _rebuild_table(self, origs, news, ends=None, dirs=None):
        for row in self.rows:
            row.destroy()
        self.rows = []
        ends = list(ends) if ends else [None] * len(news)
        dirs = list(dirs) if dirs else [None] * len(news)
        for i in range(len(origs)):
            end = ends[i] if i < len(ends) else None
            direction = dirs[i] if i < len(dirs) else None
            self.rows.append(MappingRow(self, self.table_frame,
                                        len(self.rows) + self.HEADER_ROWS,
                                        origs[i], news[i], end, direction))

    def add_mapping_row(self):
        orig = (self.original_colors[len(self.rows)]
                if len(self.rows) < len(self.original_colors) else None)
        self.rows.append(MappingRow(self, self.table_frame,
                                    len(self.rows) + self.HEADER_ROWS,
                                    orig, (255, 255, 255)))

    def remove_mapping_row(self, row):
        if row not in self.rows:
            return
        idx = self.rows.index(row)
        origs = [r.orig for r in self.rows]
        news = [r.get_new_color() for r in self.rows]
        ends = [r.get_end_color() if r.gradient else None
                for r in self.rows]
        dirs = [r.get_direction() if r.gradient else None
                for r in self.rows]
        del origs[idx]
        del news[idx]
        del ends[idx]
        del dirs[idx]
        self._rebuild_table(origs, news, ends, dirs)

    def move_new_color(self, row, delta):
        """Move a row's new color up (-1) or down (+1) between rows.

        The original colors stay in place; the whole 'new' side of the
        row (color, gradient end, gradient flag) swaps with the
        neighbouring row, which changes which original color receives
        which new color.
        """
        if row not in self.rows:
            return
        idx = self.rows.index(row)
        nidx = idx + delta
        if nidx < 0 or nidx >= len(self.rows):
            return
        other = self.rows[nidx]
        a = row.snapshot()
        b = other.snapshot()
        row.restore(b)
        other.restore(a)

    # -------------------------------------------------------- palettes
    def _refresh_palette_dropdown(self):
        names = list(self.palettes.keys())
        self.dropdown["values"] = names
        if self.palette_var.get() not in names and names:
            self.palette_var.set(names[0])

    def get_current_palette(self):
        """Return the new colors as palette entries.

        Flat rows become [R, G, B] lists; gradient rows become
        {"start": [R, G, B], "end": [R, G, B], "dir": ...} dicts.
        """
        entries = []
        for r in self.rows:
            color = list(r.get_new_color())
            if r.gradient:
                entries.append({"start": color, "end": list(r.get_end_color()),
                                "dir": r.get_direction()})
            else:
                entries.append(color)
        return entries

    def on_palette_selected(self, _event=None):
        name = self.palette_var.get()
        entries = list(self.palettes.get(name, [])) or [(0, 0, 0)]
        parsed = [_parse_entry(e) for e in entries]
        news = [color for color, _end, _dir in parsed]
        ends = [end for _color, end, _dir in parsed]
        dirs = [d for _color, _end, d in parsed]
        origs = list(self.original_colors) if self.source_image else []
        n = max(len(origs), len(news))
        origs += [None] * (n - len(origs))
        news += [(0, 0, 0)] * (n - len(news))
        ends += [None] * (n - len(ends))
        dirs += [None] * (n - len(dirs))
        self._rebuild_table(origs, news, ends, dirs)

    def save_palette(self):
        name = self.palette_var.get().strip()
        if not name:
            messagebox.showwarning("Save", "No palette selected.")
            return
        self.palettes[name] = self.get_current_palette()
        save_palettes_to_disk(self.palettes)
        self._refresh_palette_dropdown()
        self.status.config(text=f"Palette '{name}' saved.")

    def save_palette_as(self):
        name = simpledialog.askstring(
            "Save As New", "New palette name:",
            initialvalue=self.palette_var.get() + " copy")
        if not name:
            return
        self.palette_var.set(name)
        self.save_palette()

    # ------------------------------------------------------- remapping
    def build_remap_image(self):
        if not self.source_image:
            return None
        flat = {}
        grads = []  # (original color, start, end, direction key)
        for row in self.rows:
            if row.orig is None:
                continue
            if row.gradient:
                grads.append((row.orig, row.get_new_color(),
                              row.get_end_color(), row.get_direction()))
            else:
                flat[row.orig] = row.get_new_color()

        img = self.source_image.copy()
        pix = img.load()
        w, h = img.size
        # Per-direction projection ranges, computed once: for each
        # direction the gradient spans the whole image edge to edge.
        default_dir = self.gradient_dir_var.get()
        dir_params = {}  # direction key -> (dx, dy, pmin, span)
        for _o, _s, _e, dkey in grads:
            key = dkey if dkey in GRADIENT_DIRECTIONS else default_dir
            if key in dir_params:
                continue
            dx, dy = GRADIENT_DIRECTIONS[key]
            projs = [x * dx + y * dy
                     for x, y in ((0, 0), (w - 1, 0), (0, h - 1),
                                  (w - 1, h - 1))]
            pmin, pmax = min(projs), max(projs)
            dir_params[key] = (dx, dy, pmin, (pmax - pmin) or 1)
        for y in range(h):
            for x in range(w):
                c = pix[x, y]
                if c in flat:
                    pix[x, y] = flat[c]
                elif grads:
                    for orig, start, end, dkey in grads:
                        if c == orig:
                            key = (dkey if dkey in GRADIENT_DIRECTIONS
                                   else default_dir)
                            dx, dy, pmin, span = dir_params[key]
                            t = (x * dx + y * dy - pmin) / span
                            t = min(1.0, max(0.0, t))
                            pix[x, y] = tuple(
                                round(s + t * (e - s))
                                for s, e in zip(start, end))
                            break
        return img

    def apply_and_save(self):
        if not self.source_image:
            messagebox.showwarning("Apply", "Open a PNG first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG images", "*.png")])
        if not path:
            return
        try:
            self.build_remap_image().save(path, "PNG")
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))
            return
        self.status.config(text=f"Saved {os.path.basename(path)}")


if __name__ == "__main__":
    app = PaletteSwapStudio()
    app.mainloop()
