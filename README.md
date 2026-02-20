# Real Estate Keyword and Data Extractor

This project allows for the automatic extraction of structured data from real estate documents (Maintenance Log, Regulations, Diagnostics, etc.) using LLM models (Mistral or Google Gemini) and OCR.

## Features

- Extraction of specific fields based on JSON templates.
- Support for PDF and image files.
- Integrated OCR for scanned documents or images.
- Web API (FastAPI) for integration.
- CLI tools for batch processing or testing.
- Conversion of JSON results into styled Excel files.

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure environment variables:
    - Copy `env_example` to `.env`.
    - Fill in `MISTRAL_API_KEY` or `GEMINI_API_KEY` depending on the model used.

## Usage

### Web API

Start the API server:
```bash
python -m src.api_web
```
The API will be accessible at `http://localhost:8000`. Interactive documentation at `http://localhost:8000/docs`.

Example usage (curl):
```bash
curl -X POST http://localhost:8000/extract \
  -F "file=@path/to/your/document.pdf" \
  -F "doc_type=carnet" \
  -F "model=mistral-large-latest" \
  -F "ocr_model=pixtral-large-latest"
```

Example usage (Python):
```python
import requests

url = "http://localhost:8000/extract"
files = {"file": open("docs/my_logbook.pdf", "rb")}
data = {
    "doc_type": "carnet",
    "model": "mistral-large-latest",
    "ocr_model": "pixtral-large-latest"
}
response = requests.post(url, files=files, data=data)
print(response.json())
```

### Mistral CLI

To extract data with Mistral:
```bash
python -m src.cli_mistral <doc_type> <file_path> --output result.json
```
Example:
```bash
python -m src.cli_mistral carnet "docs/my_logbook.pdf" --output result_logbook.json
```

### Gemini CLI

To extract data with Gemini (supports OCR cache and multi-threading):
```bash
python -m src.cli_gemini <doc_type> <file_path> --output result.json
```

### Excel Conversion

To convert a JSON result into a styled Excel file:
```bash
python -m src.json_to_excel_style result.json --output result.xlsx
```

## Project Structure

- `src/api_web.py`: Entry point for the REST API.
- `src/cli_mistral.py`: Command-line tool using Mistral.
- `src/cli_gemini.py`: Command-line tool using Gemini.
- `src/json_to_excel_style.py`: Tool to convert JSON output to styled Excel.
- `src/core/`: Shared logic and configuration.
- `src/services/`: Specific integrations for AI providers (Mistral, Gemini).
- `empty_json_template/`: JSON templates defining the fields to extract for each document type.

## License

This project is licensed under the terms of the MIT License.
