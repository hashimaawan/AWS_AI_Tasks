"""
Core pipeline logic — AWS Lambda edition.

Nothing in this file knows or cares WHERE it runs. It takes raw PDF bytes and
returns a structured result (category + extracted fields). The ONLY difference
from the local version is that text extraction uses pypdf (pure Python, packs
into a Lambda layer trivially) instead of pdfplumber (compiled binaries).

Pure functions, no I/O, no boto3. Easy to test.
"""

import io
import re

from pypdf import PdfReader


# ---------------------------------------------------------------------------
# 1. EXTRACT  —  pull the text layer out of a digitally-native PDF
# ---------------------------------------------------------------------------
def extract_text(pdf_bytes: bytes) -> str:
    """Return all selectable text from a text-native PDF (no OCR)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_form_fields(pdf_bytes: bytes) -> dict:
    """
    Bonus for fillable application forms: read the interactive field values
    directly instead of guessing with regex. Returns {} if the PDF has no
    form fields.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    fields = reader.get_form_text_fields() or {}
    return {k: v for k, v in fields.items() if v}


# ---------------------------------------------------------------------------
# 2. CLASSIFY  —  decide the business category from signal words
# ---------------------------------------------------------------------------
# Rule-based on purpose: transparent, deterministic, and free. This is the
# spot you would later swap for Amazon Bedrock or a Comprehend custom
# classifier if you needed to scale accuracy — the signature stays the same.
CATEGORY_KEYWORDS = {
    "invoice": ["invoice", "invoice no", "bill to", "total due", "amount due", "subtotal"],
    "sales_report": ["sales report", "revenue", "units sold", "quarter", "q1", "q2", "q3", "q4"],
    "application": ["application", "applicant", "date of birth", "signature", "applicant name"],
}


def classify(text: str) -> str:
    """Score each category by keyword hits; return the best, else 'uncategorised'."""
    lowered = text.lower()
    scores = {
        category: sum(keyword in lowered for keyword in keywords)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best_category = max(scores, key=scores.get)
    return best_category if scores[best_category] > 0 else "uncategorised"


# ---------------------------------------------------------------------------
# 3. EXTRACT FIELDS  —  pull the key data for whatever category we found
# ---------------------------------------------------------------------------
# One small set of regex patterns per category. re.I = case-insensitive.
FIELD_PATTERNS = {
    "invoice": {
        "invoice_no": r"invoice\s*(?:no|number|#)[:\s]+([A-Za-z0-9\-]+)",
        "po_number": r"po\s*(?:number|no|#)[:\s]+([A-Za-z0-9\-]+)",
        "date": r"date[:\s]+([0-9]{1,4}[/\-][0-9]{1,2}[/\-][0-9]{1,4})",
        "due_date": r"due\s*date[:\s]+([0-9]{1,4}[/\-][0-9]{1,2}[/\-][0-9]{1,4})",
        "bill_to": r"bill\s*to[:\s]+([A-Za-z0-9 .,&\-]+)",
        "subtotal": r"subtotal:\s*\$?([0-9,]+\.?[0-9]*)",
        "tax": r"tax[^:\n]*:\s*\$?([0-9,]+\.[0-9]{2})",
        # \b stops "total" from matching inside "subtotal" (see README lesson).
        "total": r"\btotal\s*(?:due)?[:\s]+\$?([0-9,]+\.?[0-9]*)",
        "currency": r"currency[:\s]+([A-Za-z]{3})",
    },
    "sales_report": {
        "quarter": r"(Q[1-4]\s*[0-9]{4})",
        "revenue": r"revenue[:\s]+\$?([0-9,]+\.?[0-9]*)",
        "units_sold": r"units\s*sold[:\s]+([0-9,]+)",
        # Colon-required so the table header "Region Units Sold ..." in the
        # long report doesn't get slurped in as a value.
        "region": r"region:\s*([A-Za-z\- ]+)",
        "gross_margin": r"gross\s*margin[^%]{0,60}?([0-9.]+%)",
        "yoy_growth": r"(?:yoy\s*growth|growth of|year[-\s]over[-\s]year growth)[^%]{0,40}?([0-9.]+%)",
        "net_revenue_retention": r"net\s*revenue\s*retention[^%]{0,60}?([0-9.]+%)",
    },
    "application": {
        "applicant_name": r"applicant\s*name[:\s]+([A-Za-z .]+)",
        "applicant_id": r"applicant\s*id[:\s]+([A-Za-z0-9\-]+)",
        "date_of_birth": r"date\s*of\s*birth[:\s]+([0-9]{1,4}[/\-][0-9]{1,2}[/\-][0-9]{1,4})",
        "email": r"email[:\s]+([\w.\-]+@[\w.\-]+\.\w+)",
        "phone": r"phone[:\s]+([0-9+][0-9+\-() ]{6,})",
        "address": r"address:\s*([A-Za-z0-9 ,.\-]+)",
    },
}


def extract_fields(text: str, category: str) -> dict:
    """Run the category's regex patterns over the text and return what matches."""
    patterns = FIELD_PATTERNS.get(category, {})
    found = {}
    for field_name, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found[field_name] = match.group(1).strip()
    return found


# ---------------------------------------------------------------------------
# ORCHESTRATOR  —  the one function both local and Lambda call
# ---------------------------------------------------------------------------
def process_pdf(pdf_bytes: bytes) -> dict:
    """Full pipeline for a single document. Returns a plain dict for storage."""
    text = extract_text(pdf_bytes)
    category = classify(text)

    # Prefer real form-field values for applications; fall back to regex.
    fields = extract_form_fields(pdf_bytes) if category == "application" else {}
    if not fields:
        fields = extract_fields(text, category)

    return {
        "category": category,
        "fields": fields,
        "char_count": len(text),
    }