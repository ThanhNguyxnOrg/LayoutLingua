#!/usr/bin/env python3
"""Generate a comprehensive multi-page scientific benchmark PDF for LayoutLingua testing.

Features included:
1. Academic paper metadata (title, abstract, authors, DOI).
2. Complex mathematics: LaTeX display equations, matrices, summation, scaled dot-product attention.
3. Physics & Electrodynamics: Maxwell's equations, Stokes' theorem surface integrals, relativity.
4. Chemistry & Kinetics: Reversible reaction equilibria (Haber-Bosch), Michaelis-Menten kinetics.
5. Embedded vector figure / diagram with caption.
6. Structured data table with codes, metrics, and text.
7. Full academic references and sources explicitly noted for each equation and dataset.

Usage:
    python scripts/generate_sample_pdf.py
    # Output: examples/sample_scientific_document.pdf
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF


def create_sample_diagram() -> bytes:
    """Create a clean 2D vector architecture diagram in PNG format."""
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 480, 160), False)
    pix.set_rect(pix.irect, (245, 247, 250))  # light slate background
    doc = fitz.open()
    page = doc.new_page(width=480, height=160)

    # Background rect
    page.draw_rect(fitz.Rect(0, 0, 480, 160), color=(0.85, 0.90, 0.95), fill=(0.96, 0.98, 1.0))

    # Draw boxes for Encoder -> Attention -> Decoder
    boxes = [
        (fitz.Rect(30, 45, 140, 115), "Input Embeddings\n[Batch, Seq, D]", (0.12, 0.44, 0.85)),
        (fitz.Rect(185, 45, 295, 115), "Multi-Head Attention\nSoftmax(QK^T / sqrt(d))", (0.05, 0.60, 0.45)),
        (fitz.Rect(340, 45, 450, 115), "Feed-Forward Network\nReLU(W1 x + b1) W2", (0.80, 0.35, 0.15)),
    ]

    for rect, text, stroke in boxes:
        page.draw_rect(rect, color=stroke, fill=(1, 1, 1), width=1.5)
        lines = text.split("\n")
        page.insert_text(fitz.Point(rect.x0 + 8, rect.y0 + 32), lines[0], fontsize=9, fontname="helv", color=stroke)
        if len(lines) > 1:
            page.insert_text(fitz.Point(rect.x0 + 8, rect.y0 + 52), lines[1], fontsize=7.5, fontname="courier", color=(0.2, 0.2, 0.2))

    # Connective arrows
    page.draw_line(fitz.Point(140, 80), fitz.Point(185, 80), color=(0.3, 0.3, 0.3), width=1.5)
    page.draw_line(fitz.Point(295, 80), fitz.Point(340, 80), color=(0.3, 0.3, 0.3), width=1.5)

    pixmap = page.get_pixmap(dpi=150)
    img_bytes = pixmap.tobytes("png")
    doc.close()
    return img_bytes


def generate_benchmark_pdf(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    # Colors
    c_primary = (0.07, 0.12, 0.24)
    c_body = (0.18, 0.22, 0.28)
    c_source = (0.35, 0.40, 0.48)
    c_math = (0.05, 0.20, 0.55)
    c_line = (0.80, 0.84, 0.90)

    # -------------------------------------------------------------
    # PAGE 1: Academic Paper Header, Abstract, Deep Learning Math
    # -------------------------------------------------------------
    p1 = doc.new_page(width=595, height=842)  # A4

    # Running header
    p1.insert_text((50, 45), "arXiv:2409.12345v1 [cs.LG]  |  LayoutLingua Benchmark Suite", fontsize=8.5, fontname="helv", color=c_source)
    p1.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    # Title
    p1.insert_text((50, 85), "Multimodal Representation Learning in Neural Document Intelligence", fontsize=15, fontname="hebo", color=c_primary)

    # Authors
    p1.insert_text((50, 110), "Alan M. Turing (1),  Claude E. Shannon (2),  John von Neumann (3)", fontsize=10, fontname="heit", color=c_body)
    p1.insert_text((50, 125), "1 Department of Computer Science, Cambridge  |  2 Bell Laboratories  |  3 Institute for Advanced Study", fontsize=8, fontname="helv", color=c_source)

    # Abstract Box
    p1.draw_rect(fitz.Rect(50, 140, 545, 238), color=(0.75, 0.80, 0.88), fill=(0.97, 0.98, 1.0), width=0.8)
    p1.insert_text((65, 158), "Abstract", fontsize=11, fontname="hebo", color=c_primary)
    abstract_text = (
        "Document layout preservation remains one of the foundational challenges in neural machine translation. "
        "Modern technical documents intertwine prose typography, complex LaTeX formulas, non-Euclidean differential "
        "operators, and multi-domain reaction stoichiometry. In this paper, we present an end-to-end framework for "
        "decoupled semantic segmentation and geometric preservation, guaranteeing zero formula deformation while "
        "maintaining full typographic ink metrics across 48 world languages."
    )
    rect_abs = fitz.Rect(65, 166, 530, 232)
    p1.insert_textbox(rect_abs, abstract_text, fontsize=8.5, fontname="helv", color=c_body, lineheight=1.2)

    # Section 1
    p1.insert_text((50, 260), "1. Introduction and Mathematical Formulation", fontsize=12, fontname="hebo", color=c_primary)
    intro_p1 = (
        "Let a technical manuscript be formalized as a set of continuous spatial coordinates X in R^2 and a discrete "
        "alphabet sequence Y. The objective of layout-preserving translation is to identify the non-prose invariant "
        "operator manifold Phi(X) such that textual elements undergo linguistic translation without altering mathematical bounds."
    )
    p1.insert_textbox(fitz.Rect(50, 270, 545, 318), intro_p1, fontsize=9.0, fontname="helv", color=c_body, lineheight=1.25)

    # Equation 1: Loss function
    p1.insert_text((50, 335), "Equation 1 (Composite Structural Loss):", fontsize=9.5, fontname="hebo", color=c_primary)
    p1.draw_rect(fitz.Rect(50, 342, 545, 380), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p1.insert_text((70, 365), "L_total = (1/N) * sum_{i=1}^N ||y_i - y_hat_i||^2 + lambda * sum_{j=1}^M |theta_j|", fontsize=8.5, fontname="courier", color=c_math)
    p1.insert_text((510, 365), "(1)", fontsize=9.5, fontname="helv", color=c_source)
    p1.insert_text((50, 390), "[Source: Goodfellow, Bengio, Courville. Deep Learning. MIT Press, 2016, Chapter 6, p. 172]", fontsize=8, fontname="heit", color=c_source)

    # Equation 2: Scaled Dot-Product Attention
    p1.insert_text((50, 415), "Equation 2 (Scaled Dot-Product Self-Attention):", fontsize=9.5, fontname="hebo", color=c_primary)
    p1.draw_rect(fitz.Rect(50, 422, 545, 460), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p1.insert_text((70, 445), "Attention(Q, K, V) = softmax( (Q * K^T) / sqrt(d_k) ) * V", fontsize=9.0, fontname="courier", color=c_math)
    p1.insert_text((510, 445), "(2)", fontsize=9.5, fontname="helv", color=c_source)
    p1.insert_text((50, 470), "[Source: Vaswani et al. 'Attention Is All You Need', NeurIPS 2017, Section 3.2.1]", fontsize=8, fontname="heit", color=c_source)

    # Diagram / Figure 1
    p1.insert_text((50, 495), "2. Architectural Layout Routing", fontsize=12, fontname="hebo", color=c_primary)
    img_bytes = create_sample_diagram()
    p1.insert_image(fitz.Rect(65, 508, 530, 630), stream=img_bytes)
    p1.insert_text((70, 644), "Figure 1: Multimodal cross-attention architecture separating semantic text from formula coordinate vectors.", fontsize=8.5, fontname="heit", color=c_source)

    # Footer p1
    p1.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p1.insert_text((290, 815), "1", fontsize=9, fontname="helv", color=c_source)

    # -------------------------------------------------------------
    # PAGE 2: Physics (Maxwell, Stokes, Relativity) & Chemistry Kinetics
    # -------------------------------------------------------------
    p2 = doc.new_page(width=595, height=842)

    p2.insert_text((50, 45), "arXiv:2409.12345v1 [cs.LG]  |  LayoutLingua Benchmark Suite", fontsize=8.5, fontname="helv", color=c_source)
    p2.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    p2.insert_text((50, 80), "3. Physics & Electrodynamic Operators", fontsize=12, fontname="hebo", color=c_primary)
    phys_p = (
        "Electromagnetic wave propagation and vector flux models require differential operators and line integrals "
        "that must never be confused with natural language punctuation or word dividers."
    )
    p2.insert_textbox(fitz.Rect(50, 88, 545, 120), phys_p, fontsize=9.5, fontname="helv", color=c_body, lineheight=1.25)

    # Maxwell's Equations
    p2.insert_text((50, 135), "Equation 3 (Maxwell's Differential Electrodynamic System):", fontsize=9.5, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 142, 545, 195), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p2.insert_text((70, 162), "div E = rho / epsilon_0,              div B = 0", fontsize=9.0, fontname="courier", color=c_math)
    p2.insert_text((70, 182), "curl E = - dB / dt,                   curl B = mu_0 ( J + epsilon_0 * dE/dt )", fontsize=8.5, fontname="courier", color=c_math)
    p2.insert_text((505, 172), "(3)", fontsize=9.5, fontname="helv", color=c_source)
    p2.insert_text((50, 205), "[Source: Griffiths, D. J. Introduction to Electrodynamics, 4th ed. Cambridge University Press, 2017, p. 338]", fontsize=8, fontname="heit", color=c_source)

    # Stokes' Theorem
    p2.insert_text((50, 228), "Equation 4 (Stokes' Theorem & Surface Circulation):", fontsize=9.5, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 235, 545, 275), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p2.insert_text((75, 258), "iint_S (curl F) * dS = oint_C F * dr", fontsize=10.5, fontname="courier", color=c_math)
    p2.insert_text((495, 258), "(4)", fontsize=9.5, fontname="helv", color=c_source)
    p2.insert_text((50, 285), "[Source: Stewart, J. Calculus: Early Transcendentals, 8th ed. Cengage Learning, 2015, Theorem 16.8, p. 1130]", fontsize=8, fontname="heit", color=c_source)

    # Relativistic Energy
    p2.insert_text((50, 308), "Equation 5 (Relativistic Energy-Momentum Invariant):", fontsize=9.5, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 315, 545, 355), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p2.insert_text((75, 338), "E^2 = (p * c)^2 + (m_0 * c^2)^2", fontsize=10.5, fontname="courier", color=c_math)
    p2.insert_text((495, 338), "(5)", fontsize=9.5, fontname="helv", color=c_source)
    p2.insert_text((50, 365), "[Source: Einstein, A. 'Zur Elektrodynamik bewegter Korper', Annalen der Physik, 17(10), 891-921, 1905]", fontsize=8, fontname="heit", color=c_source)

    # Section 4: Chemistry
    p2.insert_text((50, 395), "4. Chemical Kinetics & Reversible Reaction Equilibria", fontsize=12, fontname="hebo", color=c_primary)
    chem_p = (
        "Chemical reactions feature stoichiometry numbers, state phases, and equilibrium arrows that must remain "
        "coupled during document translation. Inversion of reactant-product orders alters physical meaning."
    )
    p2.insert_textbox(fitz.Rect(50, 403, 545, 435), chem_p, fontsize=9.5, fontname="helv", color=c_body, lineheight=1.25)

    # Haber-Bosch Reaction
    p2.insert_text((50, 448), "Reaction 6 (Haber-Bosch Ammonia Synthesis Equilibrium):", fontsize=9.5, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 455, 545, 495), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p2.insert_text((75, 478), "N2 (g) + 3 H2 (g) <===> 2 NH3 (g),    Delta H^o = -92.4 kJ/mol", fontsize=10.5, fontname="courier", color=c_math)
    p2.insert_text((495, 478), "(6)", fontsize=9.5, fontname="helv", color=c_source)
    p2.insert_text((50, 505), "[Source: Atkins, P., & de Paula, J. Physical Chemistry, 10th ed. Oxford University Press, 2014, Chapter 6]", fontsize=8, fontname="heit", color=c_source)

    # Michaelis-Menten Kinetics
    p2.insert_text((50, 528), "Equation 7 (Michaelis-Menten Enzyme Catalysis Velocity):", fontsize=9.5, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 535, 545, 575), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    p2.insert_text((75, 558), "v_0 = (V_max * [S]) / (K_m + [S])", fontsize=10.5, fontname="courier", color=c_math)
    p2.insert_text((495, 558), "(7)", fontsize=9.5, fontname="helv", color=c_source)
    p2.insert_text((50, 585), "[Source: Michaelis, L., & Menten, M. L. 'Die Kinetik der Invertinwirkung', Biochem. Z., 49, 333-369, 1913]", fontsize=8, fontname="heit", color=c_source)

    # Footer p2
    p2.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p2.insert_text((290, 815), "2", fontsize=9, fontname="helv", color=c_source)

    # -------------------------------------------------------------
    # PAGE 3: Scientific Benchmark Table & Full Reference Citations
    # -------------------------------------------------------------
    p3 = doc.new_page(width=595, height=842)

    p3.insert_text((50, 45), "arXiv:2409.12345v1 [cs.LG]  |  LayoutLingua Benchmark Suite", fontsize=8.5, fontname="helv", color=c_source)
    p3.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    p3.insert_text((50, 80), "5. Experimental Evaluation & Benchmark Data", fontsize=12, fontname="hebo", color=c_primary)
    exp_p = (
        "We evaluate the preservation engine across three scientific corpora. Bounding box coordinates, table borders, "
        "and numerical units are strictly isolated to prevent translation bleeding into data columns."
    )
    p3.insert_textbox(fitz.Rect(50, 88, 545, 120), exp_p, fontsize=9.5, fontname="helv", color=c_body, lineheight=1.25)

    # Table 1
    p3.insert_text((50, 135), "Table 1: Quantitative benchmark results across scientific document domains.", fontsize=9, fontname="hebo", color=c_primary)
    table_top = 145
    col_x = [50, 130, 260, 340, 430, 545]
    row_h = 24

    # Table header
    p3.draw_rect(fitz.Rect(col_x[0], table_top, col_x[-1], table_top + row_h), color=c_primary, fill=(0.12, 0.22, 0.38))
    headers = ["Model Code", "Scientific Domain", "BLEU-4", "Formula IoU", "Latency / Page"]
    for i, h in enumerate(headers):
        p3.insert_text((col_x[i] + 6, table_top + 16), h, fontsize=8.5, fontname="hebo", color=(1, 1, 1))

    # Table rows
    rows_data = [
        ("LL-1.0.0-PRO", "Theoretical Physics (arXiv)", "44.82", "99.7%", "1.12 s"),
        ("LL-1.0.0-PRO", "Organic Reaction Kinetics", "41.35", "99.4%", "1.18 s"),
        ("LL-1.0.0-PRO", "Differential Geometry", "45.10", "99.8%", "1.09 s"),
        ("Baseline-PDF", "Theoretical Physics (arXiv)", "28.40", "64.2%", "3.45 s"),
        ("Baseline-PDF", "Organic Reaction Kinetics", "25.10", "58.1%", "3.80 s"),
    ]

    for r_idx, row in enumerate(rows_data):
        y0 = table_top + (r_idx + 1) * row_h
        y1 = y0 + row_h
        bg_col = (0.97, 0.98, 1.0) if r_idx % 2 == 0 else (1, 1, 1)
        p3.draw_rect(fitz.Rect(col_x[0], y0, col_x[-1], y1), color=c_line, fill=bg_col, width=0.5)
        for c_idx, val in enumerate(row):
            font = "courier" if c_idx in (0, 2, 3, 4) else "helv"
            p3.insert_text((col_x[c_idx] + 6, y0 + 16), val, fontsize=8.5, fontname=font, color=c_body)

    table_bottom = table_top + (len(rows_data) + 1) * row_h
    p3.insert_text((50, table_bottom + 15), "[Data Source: LayoutLingua Benchmarks v1.0.0, evaluated against PyMuPDF 1.25 & BabelDOC Ground Truth]", fontsize=7.5, fontname="heit", color=c_source)

    # Section 6: Full References & Bibliography
    p3.insert_text((50, table_bottom + 45), "6. References and Source Literature", fontsize=12, fontname="hebo", color=c_primary)
    refs = [
        "[1] I. Goodfellow, Y. Bengio, and A. Courville, Deep Learning. Cambridge, MA: MIT Press, 2016. https://www.deeplearningbook.org/",
        "[2] A. Vaswani et al., 'Attention Is All You Need', in Advances in Neural Information Processing Systems (NeurIPS), 2017, pp. 5998-6008.",
        "[3] D. J. Griffiths, Introduction to Electrodynamics, 4th ed. Cambridge: Cambridge University Press, 2017. doi:10.1017/9781108420419.",
        "[4] J. Stewart, Calculus: Early Transcendentals, 8th ed. Boston: Cengage Learning, 2015, ch. 16, pp. 1125-1138.",
        "[5] A. Einstein, 'Zur Elektrodynamik bewegter Korper', Annalen der Physik, vol. 322, no. 10, pp. 891-921, 1905. doi:10.1002/andp.19053221004.",
        "[6] P. Atkins and J. de Paula, Atkins' Physical Chemistry, 10th ed. Oxford: Oxford University Press, 2014, ch. 6, pp. 225-260.",
        "[7] L. Michaelis and M. L. Menten, 'Die Kinetik der Invertinwirkung', Biochemische Zeitschrift, vol. 49, pp. 333-369, 1913.",
    ]

    ref_y = table_bottom + 65
    for ref in refs:
        p3.insert_textbox(fitz.Rect(50, ref_y, 545, ref_y + 24), ref, fontsize=8, fontname="helv", color=c_body, lineheight=1.15)
        ref_y += 26

    # Footer p3
    p3.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p3.insert_text((290, 815), "3", fontsize=9, fontname="helv", color=c_source)

    doc.save(str(output_path))
    doc.close()
    print(f"[SUCCESS] Scientific benchmark document created: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "examples" / "sample_scientific_document.pdf"
    generate_benchmark_pdf(target)
