import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..config import UPLOAD_DIR
from ..database import save_result
from .extraction import extract_document
from .financial import validate_financials
from .ocr import extract_text
from .validation import validate_file

def process_document(file_storage, document_type):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file_storage.filename or "document").name
    path = UPLOAD_DIR / f"{uuid4().hex}_{safe_name}"
    file_storage.save(path)
    started = time.perf_counter()
    file_validation, error = validate_file(path, safe_name)
    if error:
        raise ValueError(error)
    try:
        extracted = extract_document(document_type, path)
        extracted_data = extracted.get("extracted_data", {}) if isinstance(extracted, dict) else {}
        if not _has_usable_extraction(extracted_data):
            raise ValueError("No usable financial fields could be extracted from the document.")
        validation = validate_financials(document_type, extracted_data)
        extraction_error = None
    except Exception as error:
        extracted_data = {}
        validation = {"checks": [], "overall_status": "FAIL", "issues": ["extraction_failed"]}
        extraction_error = str(error)
    result = {
        "document_name": safe_name,
        "document_type": document_type,
        "processing_status": "PASS" if validation["overall_status"] == "PASS" else "FAILED",
        "file_validation": file_validation,
        "extracted_data": extracted_data,
        "validation": validation,
        "processing_metadata": {"ocr_used": False, "extraction_source": "gemini_document_input", "validation_source": "gemini_and_deterministic_rules", "processed_at": datetime.now(timezone.utc).isoformat(), "processing_time_ms": round((time.perf_counter() - started) * 1000)},
    }
    if extraction_error:
        result["processing_error"] = extraction_error
    save_result(result)
    return result


def _has_usable_extraction(extracted_data):
    if not extracted_data:
        return False
    for item in extracted_data.values():
        value = item.get("value") if isinstance(item, dict) else item
        if value not in (None, ""):
            return True
    return False
