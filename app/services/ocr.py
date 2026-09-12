from pathlib import Path


def extract_text(path: Path):
    if path.suffix.lower() == ".pdf":
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                image = page.to_image(resolution=200).original
                pages.append({"page_number": index, "text": _ocr_image(image)})
        return pages
    from PIL import Image
    return [{"page_number": 1, "text": _ocr_image(Image.open(path))}]


def _ocr_image(image):
    import pytesseract
    return pytesseract.image_to_string(image)
