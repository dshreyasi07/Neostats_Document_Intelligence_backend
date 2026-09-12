import re


def extract_document(document_type, pages):
    text = "\n".join(page["text"] for page in pages).strip()
    return _heuristic_extract(text)


def _heuristic_extract(text):
    extracted = {"raw_text": {"value": text or None, "evidence": text[:240] or None, "page_number": 1}}
    for label, value in re.findall(r"(?im)^\s*([A-Za-z][A-Za-z &/()-]{2,40})\s*[:|=-]\s*([^\n]+)", text):
        key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        extracted[key] = {"value": _number_or_text(value.strip()), "evidence": value.strip(), "page_number": 1}
    return {"extracted_data": extracted, "validation_context": {}}


def _number_or_text(value):
    cleaned = value.replace(",", "").replace("$", "").replace("£", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except ValueError:
        return value
