import os
from pathlib import Path

# Base directory relative to this file
# This file is in src/core/config.py, so parent.parent is src/
SRC_DIR = Path(__file__).resolve().parent.parent

def get_template_path(filename):
    return str(SRC_DIR / "empty_json_template" / filename)

DOC_TEMPLATES = {
    "carnet": get_template_path("carnet_entretien_empty.json"),
    "reglement": get_template_path("reglement_propriete_empty.json"),
    "dta": get_template_path("DTA_empty.json"),
    "crep": get_template_path("CREP_empty.json"),
    "ct": get_template_path("CT_quinquenal_ascenseur_empty.json"),
    "occupants": get_template_path("liste_occupant_empty.json"),
    "devis": get_template_path("devis_facture_travaux_empty.json"),
}

DEFAULT_MISTRAL_MODEL = "mistral-large-latest"
DEFAULT_OCR_MODEL = "pixtral-large-latest"
DEFAULT_MAX_PAGES = 12
