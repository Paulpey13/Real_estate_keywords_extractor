import base64
import os
import requests

from src.core.utils import parse_json_content, load_pages_with_ocr

def mistral_ocr_image(png_bytes, ocr_model):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY manquant (charger .env)")
    url = "https://api.mistral.ai/v1/chat/completions"
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Transcris le texte lisible de cette image."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    payload = {"model": ocr_model, "messages": messages, "temperature": 0}
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""

def call_mistral(messages, model="mistral-large-latest"):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY manquant (charger .env)")
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "messages": messages, "temperature": 0}
    resp = requests.post(url, json=payload, headers=headers, timeout=180)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return parse_json_content(content)

def load_pages(path, max_pages, ocr_model, ocr_all):
    return load_pages_with_ocr(
        path, 
        max_pages, 
        lambda png: mistral_ocr_image(png, ocr_model),
        ocr_all=ocr_all
    )
