import json
import os
from pathlib import Path


def extract_document(document_type, path):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    response = model.generate_content(
        [_extraction_prompt(document_type), {"mime_type": _mime_type(path), "data": Path(path).read_bytes()}],
        generation_config={"response_mime_type": "application/json"},
    )
    try:
        result = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Gemini returned invalid extraction JSON.") from error
    if not isinstance(result, dict) or not isinstance(result.get("extracted_data"), dict):
        raise ValueError("Gemini returned an invalid extraction response.")
    return result


def _mime_type(path):
    return {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}[Path(path).suffix.lower()]


def _extraction_prompt(document_type):
    schemas = {
        "invoice": "invoice_number, invoice_date, vendor_name, customer_name, line_items, subtotal, tax_amount, discount, total_amount",
        "balance_sheet": "total_assets, total_capital_and_liabilities, assets, capital_and_liabilities",
        "profit_and_loss": "total_income, total_expenditure, consolidated_net_profit",
        "cash_flow_statement": "operating_cash_flow, investing_cash_flow, financing_cash_flow, fx_adjustment, net_increase_in_cash",
    }
    return (
        f"Extract the {document_type} financial document, including its tables. "
        "Return only JSON in this exact shape: "
        '{"extracted_data":{"field_name":{"value":null,"evidence":"exact supporting text","page_number":1}},"validation_context":{}}. '
        f"Extract these canonical fields where present: {schemas[document_type]}. "
        "Preserve numbers as JSON numbers, use negative numbers for parentheses, and use null for missing values. "
        "For list fields, value must be an array of objects with relevant names and numeric values. Do not invent values."
    )
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
