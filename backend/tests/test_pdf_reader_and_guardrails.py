import os
import io
import zipfile
import pytest
from backend.services.agent_tools import ReadFileTool, BashTool

def test_execute_bash_blocks_pip_install():
    bash_tool = BashTool()
    
    blocked_commands = [
        "pip install PyMuPDF",
        "pip3 install numpy",
        "python -m pip install pypdf",
        "python.exe -m pip install pypdf",
        "pip install -r requirements.txt",
        "conda install scipy",
        "mamba install pytorch",
        "npm install -g pnpm",
        "npm i -g yarn",
    ]
    
    for cmd in blocked_commands:
        res = bash_tool.execute({"command": cmd})
        assert "[Error] GUARDRAIL BLOCKED: Package management commands" in res
        assert "read_file" in res

def test_execute_bash_allows_safe_commands():
    bash_tool = BashTool()
    res = bash_tool.execute({"command": "echo guardrail_test_pass"})
    assert "guardrail_test_pass" in res

def test_read_file_with_pdf(tmp_path):
    import pypdf
    from pypdf import PdfWriter
    
    # Create a test PDF with 7 pages
    pdf_path = tmp_path / "test_doc.pdf"
    writer = PdfWriter()
    for i in range(1, 8):
        page = pypdf.PageObject.create_blank_page(width=200, height=200)
        writer.add_page(page)
    with open(pdf_path, "wb") as f:
        writer.write(f)
        
    read_tool = ReadFileTool()
    
    # Test 1: Single page reading
    res_page_1 = read_tool.execute({"path": str(pdf_path), "page": "1"})
    assert "--- [Page 1 of 7] ---" in res_page_1
    assert "--- [Page 2 of 7] ---" not in res_page_1
    
    # Test 2: Page range
    res_range = read_tool.execute({"path": str(pdf_path), "start_page": "2", "end_page": "4"})
    assert "--- [Page 2 of 7] ---" in res_range
    assert "--- [Page 3 of 7] ---" in res_range
    assert "--- [Page 4 of 7] ---" in res_range
    assert "--- [Page 1 of 7] ---" not in res_range
    assert "--- [Page 5 of 7] ---" not in res_range
    
    # Test 3: Default truncation for >5 pages when no page specified
    res_default = read_tool.execute({"path": str(pdf_path)})
    assert "--- [Page 1 of 7] ---" in res_default
    assert "--- [Page 5 of 7] ---" in res_default
    assert "--- [Page 6 of 7] ---" not in res_default
    assert "[Note: PDF 'test_doc.pdf' has 7 pages total. Showing pages 1 to 5." in res_default

    # Test 4: Invalid page bounds
    res_err1 = read_tool.execute({"path": str(pdf_path), "page": "99"})
    assert "[Error] start_page (99) is beyond total page count (7)." in res_err1

    res_err2 = read_tool.execute({"path": str(pdf_path), "start_page": "5", "end_page": "2"})
    assert "[Error] end_page (2) cannot be less than start_page (5)." in res_err2

def test_read_file_with_docx(tmp_path):
    # Construct a minimal docx file
    docx_path = tmp_path / "sample.docx"
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p><w:r><w:t>第一段：媚吻锋的微课讲义</w:t></w:r></w:p>
            <w:p><w:r><w:t>第二段：STM32 寄存器映射原理</w:t></w:r></w:p>
        </w:body>
    </w:document>"""
    
    with zipfile.ZipFile(docx_path, "w") as zf:
        zf.writestr("word/document.xml", doc_xml.encode("utf-8"))
        
    read_tool = ReadFileTool()
    res = read_tool.execute({"path": str(docx_path)})
    assert "第一段：媚吻锋的微课讲义" in res
    assert "第二段：STM32 寄存器映射原理" in res

def test_read_real_downloaded_pdf():
    # If the user's downloaded navier-stokes.pdf exists, verify real-world extraction
    pdf_path = r"C:\Users\EDvisa\Downloads\navier-stokes.pdf"
    if os.path.exists(pdf_path):
        read_tool = ReadFileTool()
        res = read_tool.execute({"path": pdf_path, "page": "1"})
        assert "--- [Page 1 of 166] ---" in res
        assert "FINITE TIME BLOWUP FOR" in res
        assert "OPENAI" in res
