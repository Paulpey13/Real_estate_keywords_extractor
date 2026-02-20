# CLI tool for extracting data using Mistral API
# Handles command line arguments for document processing

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.core.config import DOC_TEMPLATES
from src.core.utils import (
    build_prompt_content,
    collect_fields,
    flatten_pages,
    set_path,
)
from src.services.mistral import call_mistral, load_pages

def main():
    load_dotenv(dotenv_path=Path(".env"), override=True)
    parser = argparse.ArgumentParser(description="Extraction multi-docs via Mistral (texte + OCR).")
    parser.add_argument("doc_type", help="carnet|reglement|dta|crep|ct|occupants|devis")
    parser.add_argument("document", help="Document à analyser (PDF/PNG/XLSX...)")
    parser.add_argument("--output", help="Chemin de sortie JSON", default=None)
    parser.add_argument("--model", default="mistral-large-latest", help="Modèle texte")
    parser.add_argument("--ocr-model", default="pixtral-large-latest", help="Modèle vision/OCR")
    parser.add_argument("--max-pages", type=int, default=12, help="Nb max de pages PDF")
    parser.add_argument("--ocr-all", action="store_true", help="Forcer l'OCR sur toutes les pages")
    args = parser.parse_args()

    # Load the extraction template
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

    # Load and process document pages (with optional OCR)
    doc_path = Path(args.document)
    pages = load_pages(
        doc_path,
        max_pages=args.max_pages,
        ocr_model=args.ocr_model,
        ocr_all=args.ocr_all,
    )
    doc_text = flatten_pages(pages)
    
    # Build prompt and call Mistral API
    system, user = build_prompt_content(doc_text, field_specs)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    
    llm_result = call_mistral(messages, model=args.model)

    # Fill metadata
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

if __name__ == "__main__":
    main()
