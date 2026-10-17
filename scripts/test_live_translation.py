"""End-to-end live translation test script for LayoutLingua server."""

import io
import json
import urllib.request
import urllib.parse
import pymupdf

def run_test():
    server_url = "http://127.0.0.1:8765"
    
    # 1. Create a realistic academic test PDF with two columns, citations, and formulas
    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page(width=595.3, height=841.9) # A4
    
    # Title
    page.insert_text((50, 70), "Attention Is All You Need in Modern Deep Learning", fontsize=18, fontname="helv")
    
    # Authors & Abbreviation
    page.insert_text((50, 100), "Ashish Vaswani et al. - Google Brain & Research", fontsize=11, fontname="helv")
    
    # Abstract
    page.insert_text((50, 130), "Abstract", fontsize=13, fontname="helv")
    abstract_text = (
        "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. "
        "We propose the Transformer, a model architecture eschewing recurrence and entirely relying on an attention mechanism [1, 2]. "
        "Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable."
    )
    # Insert textbox for nice wrapping
    page.insert_textbox(pymupdf.Rect(50, 145, 545, 230), abstract_text, fontsize=10, fontname="helv")
    
    # Section 1
    page.insert_text((50, 250), "1. Introduction", fontsize=13, fontname="helv")
    intro_col1 = (
        "Recurrent neural networks, long short-term memory [3], and gated recurrent neural networks have been firmly "
        "established as state-of-the-art approaches in sequence modeling. "
        "Attention mechanisms have become an integral part of compelling sequence modeling in various tasks."
    )
    page.insert_textbox(pymupdf.Rect(50, 270, 280, 420), intro_col1, fontsize=9.5, fontname="helv")
    
    intro_col2 = (
        "In this work we introduce the Transformer, a model architecture eschewing recurrence. "
        "The Transformer allows for significantly more parallelization and can reach a new state of the art in translation "
        "after being trained for as little as twelve hours on eight P100 GPUs [4]."
    )
    page.insert_textbox(pymupdf.Rect(305, 270, 545, 420), intro_col2, fontsize=9.5, fontname="helv")
    
    # Add TOC bookmark
    sample_toc = [
        [1, "Attention Is All You Need", 1],
        [1, "1. Introduction", 1]
    ]
    pdf_doc.set_toc(sample_toc)
    
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()
    
    print(f"[*] Created synthetic academic test PDF ({len(pdf_bytes)} bytes)")
    
    # 2. Upload to server
    upload_req = urllib.request.Request(
        f"{server_url}/api/upload",
        data=pdf_bytes,
        headers={"Content-Type": "application/pdf", "X-Filename": "attention_paper.pdf"}
    )
    with urllib.request.urlopen(upload_req) as resp:
        upload_res = json.loads(resp.read().decode("utf-8"))
        doc_id = upload_res["id"]
        print(f"[+] Uploaded successfully! Doc ID: {doc_id}")
        print(f"    Pages: {upload_res['page_count']}, Words: {upload_res['word_count']}, Detected Lang: {upload_res['detected_lang']}")
    
    # 3. Call translation with Google RPC
    translate_payload = {
        "doc_id": doc_id,
        "target_lang": "vi",
        "provider": "google",
        "page_range": "all"
    }
    trans_req = urllib.request.Request(
        f"{server_url}/api/translate",
        data=json.dumps(translate_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    print("[*] Translating document via Google provider...")
    with urllib.request.urlopen(trans_req, timeout=30.0) as resp:
        trans_res = json.loads(resp.read().decode("utf-8"))
        print(f"[+] Translation completed: {trans_res}")
        
    # 4. Export translated PDF
    export_url = f"{server_url}/api/download?id={doc_id}&mode=mono"
    with urllib.request.urlopen(export_url) as resp:
        trans_pdf_bytes = resp.read()
        print(f"[+] Exported translated PDF ({len(trans_pdf_bytes)} bytes)")
        
    # 5. Render translated preview
    trans_doc = pymupdf.open(stream=trans_pdf_bytes, filetype="pdf")
    page0 = trans_doc[0]
    pix = page0.get_pixmap(dpi=150)
    out_img_path = "tests/test_live_output.png"
    pix.save(out_img_path)
    print(f"[+] Rendered preview image saved to: {out_img_path}")
    
    # Extract translated text sample
    extracted_text = page0.get_text()
    print("\n--- SAMPLE TRANSLATED TEXT IN RESULT PDF ---")
    print(extracted_text[:400])
    print("--------------------------------------------\n")
    trans_doc.close()

if __name__ == "__main__":
    run_test()
