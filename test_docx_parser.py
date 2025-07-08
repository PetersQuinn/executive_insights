from utils.parser_docx import parse_docx_status

result = parse_docx_status("data/raw/bigtest.docx")
print(result["parsed"])
