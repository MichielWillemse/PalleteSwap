# PalleteSwap

Palette Swap Studio — a small Tkinter GUI to apply new color schemes
(palettes) to a 16-color (or fewer) RGB PNG.

## Requirements

    pip install pillow

## Run

    python palette_swap_studio.py

## Usage

1. **Open PNG** — load an RGB PNG; its unique colors (up to 16) are listed.
2. Each mapping row pairs one original color (left, read-only) with one
   new color (right). Click a new-color swatch to pick a color, or type
   R/G/B values directly.
3. ▲ / ▼ move a new color up/down between rows (the original colors stay
   in place); ✕ removes a row; **+ Add color** adds one.
4. The **Palette** dropdown loads a saved palette. **Save Palette (same
   name)** / **Save Palette As New...** persist palettes to
   `palettes.json` next to the script (hand-editable JSON).
5. **Update preview** renders the remapped image on the right (about 2x
   the small original preview at the bottom-left). **Apply & Save PNG**
   writes the remapped image to disk.

## Gradients (per color)

Press the ∇ button on a mapping row to turn its new color into a gradient
across the image. The row's new color is the gradient start; the end color
gets its own swatch plus editable R/G/B fields (0–255) next to it — click
the swatch for a color picker, or type values directly.

Each gradient row has its **own direction dropdown** next to its buttons
(left→right, right→left, top→bottom, bottom→top, diagonals), so different
colors can gradient in different directions in one pass. A newly enabled
row starts from the **Gradient (default)** dropdown below the table. The
preview and **Apply & Save PNG** include the gradients.

Palette entries in `palettes.json` are `[r, g, b]` triplets (or legacy
`"#rrggbb"` hex strings); gradient rows are stored as
`{"start": [r, g, b], "end": [r, g, b], "dir": "left → right"}` — `dir` is
optional and must be one of the `GRADIENT_DIRECTIONS` keys in the script.

## Large images

The remap loop is per-pixel Python. Set `MAX_IMAGE_PIXELS` at the top of
`palette_swap_studio.py` to a number to refuse larger images on open
(`None`, the default, means no limit).
