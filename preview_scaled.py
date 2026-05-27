"""Genera un preview 4x escalado de los 4 frames de animación."""
from renderer import render_frames
from PIL import Image

frames = render_frames(session=0.72, week=0.45, design=0.30)

# Poner los 4 frames lado a lado en 4x
scale = 4
W, H = 128 * scale, 128 * scale
strip = Image.new("RGB", (W * 4, H), (20, 20, 20))

for i, frame in enumerate(frames):
    scaled = frame.resize((W, H), Image.NEAREST)
    strip.paste(scaled, (i * W, 0))

strip.save("preview_4x.png")
print("Guardado preview_4x.png (4 frames lado a lado, escala 4x)")
