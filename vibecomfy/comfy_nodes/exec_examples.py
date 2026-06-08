from __future__ import annotations

EXEC_HELP_TEXT = """
`vibecomfy.exec` runs arbitrary Python in-process inside ComfyUI.

Contract:
- `io.inputs` declares semantic names for fixed wire slots `in_0..in_15`.
- `io.outputs` declares semantic names that the body must return in a dict.
- The body must return exactly the declared `io.outputs` keys.
- `torch`, `np`, and `Image` are pre-injected when available.

Safety:
- There is no sandbox and no reliable timeout.
- Hung, crashing, or segfaulting code can freeze or kill the ComfyUI process.
- Save your work before queueing an exec node you do not fully trust.
""".strip()


EXEC_EXAMPLES: dict[str, dict[str, object]] = {
    "brightness_contrast": {
        "title": "Brightness / contrast",
        "summary": "Adjust an IMAGE tensor with torch math while preserving the original shape.",
        "io": {
            "inputs": [["image", "IMAGE"], ["brightness", "FLOAT"], ["contrast", "FLOAT"]],
            "outputs": [["image", "IMAGE"]],
        },
        "source": """
image = image.float()
image = ((image - 0.5) * contrast) + 0.5
image = image + brightness
image = image.clamp(0.0, 1.0)
return {"image": image}
""".strip(),
    },
    "pil_resize": {
        "title": "PIL resize",
        "summary": "Round-trip a single IMAGE through Pillow for a simple nearest-neighbor resize.",
        "io": {
            "inputs": [["image", "IMAGE"], ["width", "INT"], ["height", "INT"]],
            "outputs": [["image", "IMAGE"]],
        },
        "source": """
frame = image[0].clamp(0.0, 1.0).mul(255).byte().cpu().numpy()
pil = Image.fromarray(frame)
resized = pil.resize((int(width), int(height)), Image.NEAREST)
array = np.asarray(resized).astype("float32") / 255.0
result = torch.from_numpy(array).unsqueeze(0)
return {"image": result}
""".strip(),
    },
    "mask_from_luminance": {
        "title": "Mask from luminance",
        "summary": "Convert an IMAGE tensor into a MASK by averaging RGB luminance.",
        "io": {
            "inputs": [["image", "IMAGE"]],
            "outputs": [["mask", "MASK"]],
        },
        "source": """
mask = image[..., :3].mean(dim=-1)
return {"mask": mask.clamp(0.0, 1.0)}
""".strip(),
    },
    "debug_shape_passthrough": {
        "title": "Debug shape passthrough",
        "summary": "Print the incoming tensor shape and pass the IMAGE through unchanged.",
        "io": {
            "inputs": [["image", "IMAGE"]],
            "outputs": [["image", "IMAGE"]],
        },
        "source": """
print("exec image shape:", tuple(image.shape) if hasattr(image, "shape") else type(image).__name__)
return {"image": image}
""".strip(),
    },
}


__all__ = ["EXEC_EXAMPLES", "EXEC_HELP_TEXT"]
