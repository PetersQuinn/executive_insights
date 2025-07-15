import fitz  # PyMuPDF

def parse_pdf_status(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text()
    return {
        "parsed": {},  # Could add more intelligent parsing later
        "raw_text": text
    }