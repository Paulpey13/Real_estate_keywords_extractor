# CLI tool for extracting data using Google Gemini API
# Supports parallel processing and 2-pass extraction strategy

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    print("Missing dependency. Install with: pip install google-genai")
    exit(1)

from src.core.config import DOC_TEMPLATES
from src.core.utils import (
    build_prompt_content,
    collect_fields,
    find_relevant_pages,
    flatten_pages,
    is_found,
    merge_extractions,
    set_path,
)
from src.services.gemini import call_gemini, load_pages, select_model

def main():
    start_time = time.time()
    load_dotenv(dotenv_path=Path(".env"), override=True)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in .env")
        exit(1)

    parser = argparse.ArgumentParser(description="Extraction multi-docs via Gemini (texte + OCR).")
    parser.add_argument("doc_type", help="carnet|reglement|dta|crep|ct|occupants|devis")
    parser.add_argument("document", help="Document à analyser (PDF/PNG/XLSX...)")
    parser.add_argument("--output", help="Chemin de sortie JSON", default=None)
    parser.add_argument("--model", default="", help="Modèle texte (optionnel)")
    parser.add_argument("--vision-model", default="", help="Modèle vision/OCR (optionnel)")
    parser.add_argument("--max-pages", type=int, default=12, help="Nb max de pages PDF")
    parser.add_argument("--ocr-all", action="store_true", help="Forcer l'OCR sur toutes les pages")
    parser.add_argument("--ocr-cache-dir", default=".ocr_cache", help="Dossier cache OCR (vide pour désactiver)")
    parser.add_argument("--chunk-pages", type=int, default=8, help="Nb de pages par chunk")
    parser.add_argument("--parallel-api", type=int, default=2, help="Nombre d'appels API en parallèle")
    parser.add_argument("--second-pass", action="store_true", help="Seconde passe ciblée sur champs manquants")
    args = parser.parse_args()

    client = genai.Client(api_key=api_key)

    # Select appropriate models (default to Pro versions for better reasoning)
    text_model = args.model or os.getenv("GEMINI_TEXT_MODEL") or select_model(client, prefer_pro=True)
    vision_model = args.vision_model or os.getenv("GEMINI_VISION_MODEL") or text_model
    
    if not text_model:
        print("No compatible Gemini model found for generateContent")
        exit(1)

    template_path = DOC_TEMPLATES.get(args.doc_type, DOC_TEMPLATES["carnet"])
    template_file = Path(template_path)
    if not template_file.exists():
        raise FileNotFoundError(f"Template introuvable: {template_path}")

    output_path = (
        Path(args.output)
        if args.output
        else template_file.with_name(template_file.stem + "_fill.json")
    )

    template_obj = json.loads(template_file.read_text(encoding="utf-8"))
    field_specs = collect_fields(template_obj)

    # Load pages with OCR support (caching enabled if configured)
    doc_path = Path(args.document)
    pages = load_pages(
        doc_path,
        max_pages=args.max_pages,
        client=client,
        vision_model=vision_model,
        ocr_all=args.ocr_all,
        ocr_cache_dir=(args.ocr_cache_dir or None),
    )
    
    # Pass 1: Split document into chunks and process in parallel
    # This helps with long documents and avoids context window limits
    llm_result = {}
    chunk_pages = max(1, int(args.chunk_pages))
    chunks = [pages[i:i + chunk_pages] for i in range(0, len(pages), chunk_pages)]

    def run_chunk(chunk):
        doc_text = flatten_pages(chunk)
        system, user = build_prompt_content(doc_text, field_specs)
        prompt = system + "\n\n" + user
        return call_gemini(client, prompt, model=text_model)

    if args.parallel_api and args.parallel_api > 1 and len(chunks) > 1:
        with ThreadPoolExecutor(max_workers=args.parallel_api) as executor:
            futures = [executor.submit(run_chunk, chunk) for chunk in chunks]
            for future in as_completed(futures):
                llm_result = merge_extractions(llm_result, future.result())
    else:
        for chunk in chunks:
            llm_result = merge_extractions(llm_result, run_chunk(chunk))

    # Pass 2: Target missing fields by looking at relevant pages only
    # Searches for keywords related to missing fields to focus the LLM
    if args.second_pass:
        missing = []
        for path, label, typ in field_specs:
            val = llm_result.get(path, {}).get("value") if isinstance(llm_result.get(path), dict) else None
            if not is_found(val):
                missing.append((path, label, typ))

        if missing:
            relevant = find_relevant_pages(pages, missing)
            if relevant:
                doc_text = flatten_pages(relevant)
                system, user = build_prompt_content(doc_text, missing)
                prompt = system + "\n\n" + user
                llm_result = merge_extractions(llm_result, call_gemini(client, prompt, model=text_model))

    set_path(template_obj, "meta.file_type", doc_path.suffix.lstrip("."), None, "")
    set_path(template_obj, "meta.file_name", doc_path.name, None, "")

    for path, _, _ in field_specs:
        payload = llm_result.get(path, {})
        value = payload.get("value", "not found") if isinstance(payload, dict) else "not found"
        page = payload.get("page") if isinstance(payload, dict) else None
        excerpt = payload.get("excerpt") if isinstance(payload, dict) else ""
        set_path(template_obj, path, value, page, excerpt)

    output_path.write_text(json.dumps(template_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Écrit : {output_path}")
    elapsed = time.time() - start_time
    print(f"Temps d'execution: {elapsed:.2f}s")

if __name__ == "__main__":
    main()
