import base64
import hashlib
from pathlib import Path

from src.core.utils import parse_json_content, load_pages_with_ocr

def select_model(client, prefer_pro=True):
    model_name = None
    for m in client.models.list():
        name = getattr(m, "name", "")
        if "generateContent" not in getattr(m, "supported_actions", []):
            continue
        if prefer_pro and "pro" in name:
            model_name = name
            break
        if model_name is None and "flash" in name:
            model_name = name
    return model_name

def ocr_cache_path(cache_dir, png_bytes):
    if not cache_dir:
        return None
    h = hashlib.sha256(png_bytes).hexdigest()
    return Path(cache_dir) / f"{h}.txt"

def read_ocr_cache(cache_dir, png_bytes):
    path = ocr_cache_path(cache_dir, png_bytes)
    if not path or not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None

def write_ocr_cache(cache_dir, png_bytes, text):
    path = ocr_cache_path(cache_dir, png_bytes)
    if not path:
        return
    try:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        path.write_text(text or "", encoding="utf-8")
    except Exception:
        pass

def gemini_ocr_image(client, png_bytes, vision_model, cache_dir=None):
    cached = read_ocr_cache(cache_dir, png_bytes)
    if cached is not None:
        return cached
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    contents = [
        {
            "role": "user",
            "parts": [
                {"text": "Transcris le texte lisible de cette image."},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
        }
    ]
    resp = client.models.generate_content(model=vision_model, contents=contents)
    text = getattr(resp, "text", "") or ""
    write_ocr_cache(cache_dir, png_bytes, text)
    return text

def call_gemini(client, prompt, model):
    resp = client.models.generate_content(model=model, contents=prompt)
    text = getattr(resp, "text", "") or ""
    return parse_json_content(text)

def load_pages(path, max_pages, client, vision_model, ocr_all, ocr_cache_dir=None):
    return load_pages_with_ocr(
        path,
        max_pages,
        lambda png: gemini_ocr_image(client, png, vision_model, cache_dir=ocr_cache_dir),
        ocr_all=ocr_all
    )
