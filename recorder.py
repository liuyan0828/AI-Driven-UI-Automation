import os
import time
import json
from pathlib import Path
from tkinter import NO
from PIL import Image, ImageDraw

class ActionRecorder:
    def __init__(self, base_dir = "execution_logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def record_step(self, step_idx, before_png, after_png, prompt, response_json, x=None, y=None):
        step_path = self.base_dir / f"step_{step_idx}_{int(time.time())}"
        step_path.mkdir(exist_ok=True)

        if x is not None and y is not None:
            from io import BytesIO
            img = Image.open(BytesIO(after_png))
            draw = ImageDraw.Draw(img)
            radius = 5
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="red")
            img.save(step_path / "click_point.png")

        (step_path / "before.png").write_bytes(before_png)
        (step_path / "after.png").write_bytes(after_png)
        (step_path / "promt.txt").write_text(prompt, encoding="utf-8")
        (step_path / "response.json").write_text(response_json, encoding="utf-8")
        return step_path
    
    