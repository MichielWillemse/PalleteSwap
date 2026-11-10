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

## Gradients

Press the ∇ button on a mapping row to turn its new color into a gradient
across the image. The row's new color is the gradient start; the end color
gets its own swatch plus editable R/G/B fields (0–255) next to it — click
the swatch to open a color picker, or type values directly. The
**Gradient** dropdown below the table sets the direction for all gradient
rows (left→right, right→left, top→bottom, bottom→top, diagonals). The
preview and **Apply & Save PNG** include the gradient.

Palette entries in `palettes.json` are `[r, g, b]` triplets (or legacy
`"#rrggbb"` hex strings); gradient rows are stored as
`{"start": [r, g, b], "end": [r, g, b]}`. Their order maps to the image's
colors.
