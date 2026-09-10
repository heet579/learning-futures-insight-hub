from io import BytesIO
from docx import Document

def markdown_bytes(content: str) -> bytes:
    return content.encode("utf-8")

def docx_bytes(content: str) -> bytes:
    doc = Document()
    for line in content.splitlines():
        if line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("- "):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif line.strip():
            doc.add_paragraph(line.replace("**", ""))
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()

