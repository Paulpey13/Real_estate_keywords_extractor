# API Web for extracting data from documents using Mistral LLM
# Uses FastAPI to handle HTTP requests

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from src.core.config import DOC_TEMPLATES
from src.core.utils import (
    build_prompt_content,
    collect_fields,
    flatten_pages,
    set_path,
)
from src.services.mistral import call_mistral, load_pages

load_dotenv(dotenv_path=Path(".env"), override=True)

app = FastAPI(title="Extraction 70 champs", version="1.0.0")

@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    doc_type: str = Form("carnet"),
    template_path: str = Form(""),
    model: str = Form("mistral-large-latest"),
    ocr_model: str = Form("pixtral-large-latest"),
    max_pages: int = Form(12),
    ocr_all: bool = Form(False),
):
    # Save uploaded file temporarily to process it
    suffix = Path(file.filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        doc_path = Path(tmp.name)

    try:
        # Load the appropriate JSON template based on document type
        selected_template = template_path or DOC_TEMPLATES.get(doc_type, DOC_TEMPLATES.get("carnet"))
        template_file = Path(selected_template)
        if not template_file.exists():
            return JSONResponse(status_code=400, content={"error": "template not found"})

        template = template_file.read_text(encoding="utf-8")
        template_obj = json.loads(template)

        # Load document pages, performing OCR if necessary (e.g. for scanned PDFs or images)
        pages = load_pages(
            doc_path,
            max_pages=max_pages,
            ocr_model=ocr_model,
            ocr_all=ocr_all,
        )
        doc_text = flatten_pages(pages)
        field_specs = collect_fields(template_obj)
        
        # Prepare the prompt for the LLM using document text and expected fields
        system, user = build_prompt_content(doc_text, field_specs)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        
        # Call Mistral API to extract data
        llm_result = call_mistral(messages, model=model)

        # Fill metadata
        set_path(template_obj, "meta.file_type", suffix.lstrip("."), None, "")
        set_path(template_obj, "meta.file_name", Path(file.filename).name, None, "")

        # Populate the template with extracted values
        for path, _, _ in field_specs:
            payload = llm_result.get(path, {})
            value = payload.get("value", "not found") if isinstance(payload, dict) else "not found"
            page = payload.get("page") if isinstance(payload, dict) else None
            excerpt = payload.get("excerpt") if isinstance(payload, dict) else ""
            set_path(template_obj, path, value, page, excerpt)

        return {"result": template_obj}
    finally:
        try:
            doc_path.unlink()
        except Exception:
            pass

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api_web:app", host="0.0.0.0", port=8000, reload=True)
