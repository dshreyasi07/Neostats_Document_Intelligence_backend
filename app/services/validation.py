import mimetypes
from pathlib import Path

from PIL import Image

from ..config import SUPPORTED_EXTENSIONS


def validate_file(path: Path, original_name: str):
    extension = Path(original_name).suffix.lower().lstrip(".")
    mime = mimetypes.types_map.get(f".{extension}", "application/octet-stream")
    result = {"file_type": mime, "is_supported": extension in SUPPORTED_EXTENSIONS, "is_readable": False, "page_count": None, "status": "FAIL"}
    if extension not in SUPPORTED_EXTENSIONS or not path.exists() or path.stat().st_size == 0:
        return result, "Only readable PDF, JPG, JPEG, and PNG files are supported."
    try:
        if extension == "pdf":
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                result["page_count"] = len(pdf.pages)
        else:
            with Image.open(path) as image:
                image.verify()
            result["page_count"] = 1
        result["is_readable"] = True
    except Exception:
        return result, "The uploaded file is empty, corrupted, or unreadable."
    if result["page_count"] > 3:
        return result, "Documents are limited to three pages."
    result["status"] = "PASS"
    return result, None
