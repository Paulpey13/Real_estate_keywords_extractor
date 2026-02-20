import io
import json
import re
from pathlib import Path

import pdfplumber

def page_to_png_bytes(page, resolution=200):
    img = page.to_image(resolution=resolution).original
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def flatten_pages(pages, max_chars=32000):
    chunks = []
    total = 0
    for page_no, text in pages:
        snippet = f"[page {page_no}]\n{text.strip()}\n"
        total += len(snippet)
        if total > max_chars:
            break
        chunks.append(snippet)
    return "\n".join(chunks)

def collect_fields(obj, prefix=""):
    fields = []
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if path.startswith("meta."):
            continue
        if isinstance(v, dict) and "expected_type" in v:
            fields.append((path, path, v.get("expected_type", "")))
        elif isinstance(v, dict):
            fields.extend(collect_fields(v, path))
    return fields

def build_prompt_content(doc_text, field_specs):
    fields = "\n".join(f"- {p} | {label} | {typ}" for p, label, typ in field_specs)
    system = "Tu es un assistant qui extrait des champs factuels depuis un document immobilier. Réponds UNIQUEMENT avec un objet JSON, sans texte avant ou après."
    user_lines = [
        "Produit un objet JSON avec exactement les clés dot-path listées ci-dessous.",
        "Pour chaque clé, renvoie {\"value\": <valeur ou \"not found\">, \"page\": <numero de page ou null>, \"excerpt\": <phrase source ou \"\">}.",
        "Si tu ne trouves pas, value = \"not found\", page = null, excerpt = \"\".",
        "Si c'est une liste : renvoie un tableau JSON.",
        "Si c'est un boolean : true/false.",
        "Si c'est un objet contact : {\"email\": \"...\", \"telephone\": \"...\"}.",
        f"Champs à extraire :\n{fields}\n\nDocument paginé :\n{doc_text}",
    ]
    user = "\n".join(user_lines)
    return system, user

def parse_json_content(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = content[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return {}
    return {}

def set_path(root, path, value, page, excerpt):
    parts = path.split(".")
    cursor = root
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    leaf = cursor.get(parts[-1])
    if isinstance(leaf, dict):
        leaf["value"] = value
        src = leaf.get("source")
        if isinstance(src, dict):
            leaf["source"]["page"] = page
            leaf["source"]["excerpt"] = excerpt
        else:
            leaf["source"] = {"page": page, "excerpt": excerpt}
    else:
        cursor[parts[-1]] = {"value": value, "source": {"page": page, "excerpt": excerpt}}

def is_found(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in ("", "not found")
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return any(str(v).strip().lower() not in ("", "not found") for v in value.values())
    return True

def merge_extractions(base, update):
    if not isinstance(update, dict):
        return base
    for key, val in update.items():
        if not isinstance(val, dict):
            continue
        if is_found(val.get("value")):
            base[key] = val
    return base

def find_relevant_pages(pages, field_specs):
    tokens = set()
    for _, label, _ in field_specs:
        for t in re.split(r"[^a-zA-Z0-9]+", label.lower()):
            if len(t) > 3:
                tokens.add(t)
    selected = []
    for page_no, text in pages:
        low = text.lower()
        if any(t in low for t in tokens):
            selected.append((page_no, text))
    return selected

def load_pages_with_ocr(path, max_pages, ocr_callback, ocr_all=False):
    pages = []
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()
    
    if suffix == ".pdf":
        with pdfplumber.open(path_obj) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                if max_pages and idx > max_pages:
                    break
                text = (page.extract_text() or "").strip()
                needs_ocr = ocr_all or len(text) < 80
                if needs_ocr:
                    try:
                        png_bytes = page_to_png_bytes(page)
                        ocr_text = ocr_callback(png_bytes)
                        if ocr_text and ocr_text not in text:
                            text = (text + "\n" + ocr_text).strip() if text else ocr_text
                    except Exception:
                        pass
                pages.append((idx, text))
    else:
        try:
            png_bytes = path_obj.read_bytes()
            ocr_text = ocr_callback(png_bytes)
            pages.append((1, ocr_text))
        except Exception:
            pages.append((1, ""))
    return pages
