#!/usr/bin/env python3
"""Generate a comprehensive 5-page scientific benchmark PDF for LayoutLingua stress testing.

Features included:
1. Academic paper metadata (title, abstract, authors, DOI, keywords, classifications).
2. Two-column complex academic layout (Page 1).
3. Advanced deep learning & quantum physics mathematics:
   - Full Transformer Multi-Head scaled dot-product attention.
   - Composite elastic loss with multi-norm regularization.
   - Quantum covariance density matrix with bracket geometry.
   - Dirac relativistic equation & Einstein field equations.
4. Electrodynamics, surface circulation & differential geometry:
   - Maxwell's differential equations & covariant field tensors.
   - Stokes' theorem & Gauss-Ostrogradsky divergence theorem.
5. Chemical thermodynamics & enzyme kinetics:
   - Multi-phase reversible equilibria (Haber-Bosch & Contact Process).
   - Michaelis-Menten kinetics with competitive & allosteric Hill inhibition.
6. Formal Algorithmic Pseudocode box (Algorithm 1) with line numbers & indentation.
7. Two scientific figures:
   - Multimodal vector architecture diagram.
   - High-resolution dual-axis empirical convergence plot (Loss + BLEU-4).
8. Multi-column structured benchmark evaluation table (Table 1).
9. Full academic literature citations (10 peer-reviewed sources).

Usage:
    python scripts/generate_sample_pdf.py
    # Output: examples/sample_scientific_document.pdf
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def render_latex(formula: str, fontsize: int = 12, figsize: tuple[float, float] = (6.0, 0.65)) -> bytes:
    """Render LaTeX mathematical expression into high-DPI transparent PNG bytes."""
    fig = plt.figure(figsize=figsize, dpi=300)
    fig.text(0.5, 0.5, formula, fontsize=fontsize, ha="center", va="center", color="#0c1a30")
    plt.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", transparent=True)
    plt.close(fig)
    return buf.getvalue()


def render_matrix_equation() -> bytes:
    """Render a clean 3x3 quantum covariance matrix with brackets."""
    fig = plt.figure(figsize=(4.5, 1.1), dpi=300)
    fig.text(0.12, 0.50, r"$\mathbf{\Sigma}_{\mathrm{quantum}} =$", ha="center", va="center", fontsize=13, color="#0c1a30")
    fig.text(0.30, 0.50, r"$\left[\right.$", ha="center", va="center", fontsize=32, color="#0c1a30")
    fig.text(0.56, 0.76, r"$\sigma_{xx}^2 \qquad\quad \sigma_{xy} \qquad\quad \sigma_{xz} \qquad\quad \frac{i\hbar}{2}$", ha="center", va="center", fontsize=10.5, color="#0c1a30")
    fig.text(0.56, 0.50, r"$\sigma_{yx} \qquad\quad \sigma_{yy}^2 \qquad\quad \sigma_{yz} \qquad\quad 0$", ha="center", va="center", fontsize=10.5, color="#0c1a30")
    fig.text(0.56, 0.24, r"$\sigma_{zx} \qquad\quad \sigma_{zy} \qquad\quad \sigma_{zz}^2 \qquad\quad -\frac{i\hbar}{2}$", ha="center", va="center", fontsize=10.5, color="#0c1a30")
    fig.text(0.82, 0.50, r"$\left.\right]$", ha="center", va="center", fontsize=32, color="#0c1a30")
    plt.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", transparent=True)
    plt.close(fig)
    return buf.getvalue()


def render_piecewise_equation() -> bytes:
    """Render a piecewise loss equation with curly brace."""
    fig = plt.figure(figsize=(4.8, 1.1), dpi=300)
    fig.text(0.12, 0.50, r"$\mathcal{L}_{\mathrm{elastic}}(\mathbf{x}) =$", ha="center", va="center", fontsize=13, color="#0c1a30")
    fig.text(0.30, 0.50, r"$\left\{\right.$", ha="center", va="center", fontsize=34, color="#0c1a30")
    fig.text(0.65, 0.72, r"$\frac{1}{2}\|\mathbf{x} - \hat{\mathbf{x}}\|_2^2 + \lambda_1 \|\theta\|_1 \qquad \mathrm{if}\ \|\mathbf{x} - \hat{\mathbf{x}}\|_1 \leq \delta$", ha="center", va="center", fontsize=10.5, color="#0c1a30")
    fig.text(0.65, 0.28, r"$\delta \|\mathbf{x} - \hat{\mathbf{x}}\|_1 - \frac{1}{2}\delta^2 + \lambda_2 \|\theta\|_2^2 \qquad \mathrm{otherwise}$", ha="center", va="center", fontsize=10.5, color="#0c1a30")
    plt.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", transparent=True)
    plt.close(fig)
    return buf.getvalue()


def create_sample_diagram() -> bytes:
    """Create a clean 2D vector architecture diagram in PNG format."""
    doc = fitz.open()
    page = doc.new_page(width=480, height=130)

    # Background rect
    page.draw_rect(fitz.Rect(0, 0, 480, 130), color=(0.85, 0.90, 0.95), fill=(0.96, 0.98, 1.0))

    # Boxes for Encoder -> Attention -> Decoder
    boxes = [
        (fitz.Rect(20, 25, 150, 105), "Input Embeddings\n[Batch, Seq, D]", (0.12, 0.44, 0.85)),
        (fitz.Rect(175, 25, 305, 105), "Multi-Head Attention\nSoftmax(Q K^T / √d)", (0.05, 0.60, 0.45)),
        (fitz.Rect(330, 25, 460, 105), "Feed-Forward Network\nReLU(W1 x + b1) W2", (0.80, 0.35, 0.15)),
    ]

    for rect, text, stroke in boxes:
        page.draw_rect(rect, color=stroke, fill=(1, 1, 1), width=1.5)
        lines = text.split("\n")
        page.insert_text(fitz.Point(rect.x0 + 10, rect.y0 + 32), lines[0], fontsize=9, fontname="helv", color=stroke)
        if len(lines) > 1:
            page.insert_text(fitz.Point(rect.x0 + 10, rect.y0 + 52), lines[1], fontsize=7.5, fontname="courier", color=(0.2, 0.2, 0.2))

    # Connective arrows
    page.draw_line(fitz.Point(150, 65), fitz.Point(175, 65), color=(0.3, 0.3, 0.3), width=1.5)
    page.draw_line(fitz.Point(305, 65), fitz.Point(330, 65), color=(0.3, 0.3, 0.3), width=1.5)

    pixmap = page.get_pixmap(dpi=150)
    img_bytes = pixmap.tobytes("png")
    doc.close()
    return img_bytes


def create_scientific_plot() -> bytes:
    """Generate a dual-axis scientific plot showing optimization convergence & BLEU."""
    fig, ax1 = plt.subplots(figsize=(6.2, 2.2), dpi=250)
    epochs = np.arange(1, 21)
    loss = 2.4 * np.exp(-epochs / 4.5) + 0.12 + 0.02 * np.sin(epochs)
    bleu = 48.5 / (1.0 + np.exp(-(epochs - 6) / 2.5))

    ax1.set_xlabel("Optimization Epochs", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax1.set_ylabel("Composite Loss", color="#0284C7", fontsize=8.5, fontweight="bold")
    l1 = ax1.plot(epochs, loss, "o-", color="#0284C7", linewidth=1.6, markersize=3.5, label="Loss (Train)")
    ax1.tick_params(axis="y", labelcolor="#0284C7", labelsize=7.5)
    ax1.tick_params(axis="x", labelsize=7.5)
    ax1.grid(True, linestyle="--", alpha=0.35)

    ax2 = ax1.twinx()
    ax2.set_ylabel("Preservation BLEU-4", color="#059669", fontsize=8.5, fontweight="bold")
    l2 = ax2.plot(epochs, bleu, "s--", color="#059669", linewidth=1.6, markersize=3.5, label="BLEU-4 (Val)")
    ax2.tick_params(axis="y", labelcolor="#059669", labelsize=7.5)

    lines = l1 + l2
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="center right", fontsize=7.5, framealpha=0.92)

    plt.title("Empirical Convergence & Geometric Bounding Fidelity", fontsize=9.5, fontweight="bold", color="#0F172A", pad=6)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=250, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def generate_benchmark_pdf(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    # Typography & Palette Tokens
    c_primary = (0.07, 0.12, 0.24)
    c_body = (0.18, 0.22, 0.28)
    c_source = (0.35, 0.40, 0.48)
    c_line = (0.80, 0.84, 0.90)

    header_text = "arXiv:2409.12345v2 [cs.CV, cs.CL]  |  LayoutLingua Stress-Test Benchmark"

    # =========================================================================
    # PAGE 1: Academic Paper Header, Abstract, 2-Column Section 1, Footnotes
    # =========================================================================
    p1 = doc.new_page(width=595, height=842)  # A4
    p1.insert_text((50, 45), header_text, fontsize=8.5, fontname="helv", color=c_source)
    p1.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    # Title
    p1.insert_text((50, 80), "High-Fidelity Document Layout Preservation in Multimodal Neural Machine Translation", fontsize=12.5, fontname="hebo", color=c_primary)

    # Authors & Affiliations
    p1.insert_text((50, 102), "Alan M. Turing (1)*,  Claude E. Shannon (2)†,  John von Neumann (3),  Ada Lovelace (4)", fontsize=9.5, fontname="heit", color=c_body)
    p1.insert_text((50, 116), "1 Department of Computer Science, Cambridge  |  2 Bell Laboratories  |  3 Institute for Advanced Study  |  4 Oxford University", fontsize=7.5, fontname="helv", color=c_source)

    # Abstract Callout Box
    p1.draw_rect(fitz.Rect(50, 130, 545, 230), color=(0.75, 0.80, 0.88), fill=(0.97, 0.98, 1.0), width=0.8)
    p1.insert_text((65, 148), "Abstract", fontsize=10.5, fontname="hebo", color=c_primary)
    abs_text = (
        "Preserving document layout geometry remains the central bottleneck in technical document translation. "
        "Modern scientific publications tightly interleave typography, multi-line LaTeX equations, matrix operators, "
        "and multi-domain reaction stoichiometry. In this benchmark manuscript, we formulate an end-to-end framework for "
        "decoupled semantic layout decomposition, guaranteeing zero formula deformation, column-isolation fidelity, and full "
        "typographic ink metric calibration across 48 world languages under extreme geometric deformation stress."
    )
    p1.insert_textbox(fitz.Rect(65, 154, 530, 212), abs_text, fontsize=8.2, fontname="helv", color=c_body, lineheight=1.2)
    p1.insert_text((65, 222), "Keywords: Document Intelligence, Layout Preservation, Machine Translation, LaTeX Parsing, Non-Euclidean Manifold", fontsize=7.2, fontname="heit", color=c_source)

    # Section 1 Header (Full Width)
    p1.insert_text((50, 252), "1. Introduction and Geometric Manifold Formulation", fontsize=11.5, fontname="hebo", color=c_primary)

    # TWO-COLUMN LAYOUT CHALLENGE (Column 1: x 50..285, Column 2: x 310..545)
    col1_rect = fitz.Rect(50, 264, 285, 740)
    col2_rect = fitz.Rect(310, 264, 545, 740)

    col1_text = (
        "Document intelligence requires formalizing a technical document as a continuous two-dimensional manifold "
        "X in R^2 coupled with a discrete categorical alphabet Y. In conventional translation systems, PDF layout "
        "structure is obliterated: text spans are extracted as an undifferentiated stream, fed to a sequence-to-sequence "
        "model, and dumped into plain text without preserving spatial bounds.\n\n"
        "By contrast, high-fidelity layout preservation treats every character and formula block as an invariant topological "
        "entity with bounding coordinates B_i = [x_min, y_min, x_max, y_max]. The fundamental objective of linguistic routing "
        "is to determine an operator Phi(X) such that natural language text undergoes semantic translation without causing "
        "bounding collision with non-prose math symbols.\n\n"
        "When handling multi-column academic publications, reading order disambiguation presents a notorious challenge. "
        "A naive horizontal scan merges text across adjacent columns, causing semantic garbling. The topological parser "
        "constructs a directed acyclic graph over connected components to establish strictly vertical column flows before "
        "sentence boundary detection is attempted."
    )
    col2_text = (
        "Furthermore, scientific typography includes inline mathematical variables such as alpha, beta, and gamma, "
        "as well as tensor subscripts and functional norms ||W||_F^2 that must never be translated as linguistic tokens. "
        "Consider an arbitrary loss parameter theta in Theta with objective function J(theta). If an engine mistranslates "
        "the objective gradient nabla_theta as a vernacular word, the entire mathematical proof collapses.\n\n"
        "To prevent translation bleeding into data grids, we define an exclusion mask over coordinate subspaces where "
        "differential operators, matrix brackets, and stoichiometric indices reside. These bounding subspaces are excised from "
        "the prose translation queue and substituted with grammar-preserving placeholders {{LL_F_xxx}}.\n\n"
        "In subsequent sections, we establish quantitative bounds for deep neural attention, evaluate electrodynamic tensor "
        "systems, and demonstrate zero-distortion translation across 48 supported global languages."
    )

    p1.insert_textbox(col1_rect, col1_text, fontsize=8.4, fontname="helv", color=c_body, lineheight=1.22)
    p1.insert_textbox(col2_rect, col2_text, fontsize=8.4, fontname="helv", color=c_body, lineheight=1.22)

    # Footnotes at bottom
    p1.draw_line((50, 755), (200, 755), color=c_line, width=0.6)
    p1.insert_text((50, 768), "* Corresponding author: alan@cambridge.ac.uk", fontsize=7, fontname="helv", color=c_source)
    p1.insert_text((50, 778), "† Work performed while visiting the Institute for Advanced Study, Princeton.", fontsize=7, fontname="helv", color=c_source)

    # Page 1 Footer
    p1.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p1.insert_text((290, 815), "1", fontsize=9, fontname="helv", color=c_source)

    # =========================================================================
    # PAGE 2: Deep Learning Mathematics, Giant Matrices & Piecewise Equations
    # =========================================================================
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 45), header_text, fontsize=8.5, fontname="helv", color=c_source)
    p2.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    p2.insert_text((50, 75), "2. Deep Learning Mathematics & Quantum Formulation", fontsize=11.5, fontname="hebo", color=c_primary)
    dl_p = (
        "Neural document translation integrates scaled attention mechanisms, elastic penalty manifolds, and multi-dimensional "
        "state matrices. All algebraic expressions below are verified for exact symbol retention."
    )
    p2.insert_textbox(fitz.Rect(50, 83, 545, 110), dl_p, fontsize=8.5, fontname="helv", color=c_body, lineheight=1.2)

    # Equation 1: Loss function
    p2.insert_text((50, 118), "Equation 1 (Composite Structural Loss Function with L1/L2 Norms):", fontsize=9, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 126, 545, 168), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq1_img = render_latex(r"$\mathcal{L}_{\mathrm{total}}(\theta) = \frac{1}{N} \sum_{i=1}^N \|y_i - \hat{y}_i\|_2^2 + \lambda_1 \sum_{j=1}^M |\theta_j| + \frac{\lambda_2}{2} \|\theta\|_2^2$", fontsize=11.5, figsize=(6.2, 0.65))
    p2.insert_image(fitz.Rect(65, 129, 490, 165), stream=eq1_img)
    p2.insert_text((505, 149), "(1)", fontsize=9, fontname="helv", color=c_source)
    p2.insert_text((50, 178), "[Source: Goodfellow, Bengio, Courville. Deep Learning. MIT Press, 2016, Chapter 6, p. 172]", fontsize=7.5, fontname="heit", color=c_source)

    # Equation 2: Multi-Head Scaled Dot-Product Attention
    p2.insert_text((50, 195), "Equation 2 (Transformer Multi-Head Scaled Dot-Product Attention):", fontsize=9, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 203, 545, 245), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq2_img = render_latex(r"$\mathrm{MultiHead}(Q, K, V) = \mathrm{Concat}(\mathrm{head}_1, \dots, \mathrm{head}_h) W^O, \quad \mathrm{head}_i = \mathrm{Attention}(Q W_i^Q, K W_i^K, V W_i^V)$", fontsize=10.5, figsize=(6.5, 0.65))
    p2.insert_image(fitz.Rect(65, 206, 490, 242), stream=eq2_img)
    p2.insert_text((505, 226), "(2)", fontsize=9, fontname="helv", color=c_source)
    p2.insert_text((50, 255), "[Source: Vaswani et al. 'Attention Is All You Need', NeurIPS 2017, Section 3.2.1]", fontsize=7.5, fontname="heit", color=c_source)

    # Equation 3: Quantum State Covariance Matrix
    p2.insert_text((50, 272), "Equation 3 (Quantum State Covariance Density Matrix):", fontsize=9, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 280, 545, 342), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq3_img = render_matrix_equation()
    p2.insert_image(fitz.Rect(130, 283, 465, 339), stream=eq3_img)
    p2.insert_text((505, 313), "(3)", fontsize=9, fontname="helv", color=c_source)
    p2.insert_text((50, 352), "[Source: Nielsen, M. A., & Chuang, I. L. Quantum Computation and Quantum Information, Cambridge University Press, 2010]", fontsize=7.5, fontname="heit", color=c_source)

    # Equation 4: Piecewise Elastic Loss Function
    p2.insert_text((50, 369), "Equation 4 (Piecewise Non-Euclidean Bounding Penalty):", fontsize=9, fontname="hebo", color=c_primary)
    p2.draw_rect(fitz.Rect(50, 377, 545, 439), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq4_img = render_piecewise_equation()
    p2.insert_image(fitz.Rect(95, 380, 500, 436), stream=eq4_img)
    p2.insert_text((505, 410), "(4)", fontsize=9, fontname="helv", color=c_source)
    p2.insert_text((50, 449), "[Source: Huber, P. J. Robust Statistics. John Wiley & Sons, 2004, Chapter 3, p. 43]", fontsize=7.5, fontname="heit", color=c_source)

    # Diagram / Figure 1
    p2.insert_text((50, 472), "3. Neural Bounding Box Router", fontsize=11.5, fontname="hebo", color=c_primary)
    img_bytes = create_sample_diagram()
    p2.insert_image(fitz.Rect(65, 484, 530, 606), stream=img_bytes)
    p2.insert_text((70, 618), "Figure 1: Multimodal cross-attention architecture separating semantic text from formula coordinate vectors.", fontsize=8, fontname="heit", color=c_source)

    # Page 2 Footer
    p2.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p2.insert_text((290, 815), "2", fontsize=9, fontname="helv", color=c_source)

    # =========================================================================
    # PAGE 3: Physics & Electrodynamics, Chemistry Kinetics & Reversible Laws
    # =========================================================================
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text((50, 45), header_text, fontsize=8.5, fontname="helv", color=c_source)
    p3.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    p3.insert_text((50, 75), "4. Electrodynamics, Differential Forms & Chemical Kinetics", fontsize=11.5, fontname="hebo", color=c_primary)
    phys_p = (
        "Field equations and reversible reaction stoichiometry contain operators, flux integrals, and physical phases "
        "that must never be confused with punctuation or word dividers."
    )
    p3.insert_textbox(fitz.Rect(50, 83, 545, 110), phys_p, fontsize=8.5, fontname="helv", color=c_body, lineheight=1.2)

    # Equation 5: Maxwell Equations
    p3.insert_text((50, 118), "Equation 5 (Maxwell's Differential Electrodynamic System & Covariant Tensors):", fontsize=9, fontname="hebo", color=c_primary)
    p3.draw_rect(fitz.Rect(50, 126, 545, 178), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq5_img = render_latex(r"$\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}, \quad \nabla \cdot \mathbf{B} = 0, \qquad \nabla \times \mathbf{E} = -\frac{\partial \mathbf{B}}{\partial t}, \quad \nabla \times \mathbf{B} = \mu_0 \mathbf{J} + \mu_0 \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t}$", fontsize=10, figsize=(6.8, 0.75))
    p3.insert_image(fitz.Rect(60, 129, 495, 175), stream=eq5_img)
    p3.insert_text((505, 154), "(5)", fontsize=9, fontname="helv", color=c_source)
    p3.insert_text((50, 188), "[Source: Griffiths, D. J. Introduction to Electrodynamics, 4th ed. Cambridge University Press, 2017, p. 338]", fontsize=7.5, fontname="heit", color=c_source)

    # Equation 6: Stokes' Theorem & Gauss Divergence
    p3.insert_text((50, 205), "Equation 6 (Stokes' Circulation & Gauss-Ostrogradsky Divergence Theorems):", fontsize=9, fontname="hebo", color=c_primary)
    p3.draw_rect(fitz.Rect(50, 213, 545, 255), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq6_img = render_latex(r"$\iint_S (\nabla \times \mathbf{F}) \cdot d\mathbf{S} = \oint_{\partial S} \mathbf{F} \cdot d\mathbf{r}, \qquad \iiint_V (\nabla \cdot \mathbf{E})\, dV = \oiint_{\partial V} \mathbf{E} \cdot d\mathbf{A}$", fontsize=10.5, figsize=(6.5, 0.65))
    p3.insert_image(fitz.Rect(65, 216, 490, 252), stream=eq6_img)
    p3.insert_text((505, 236), "(6)", fontsize=9, fontname="helv", color=c_source)
    p3.insert_text((50, 265), "[Source: Stewart, J. Calculus: Early Transcendentals, 8th ed. Cengage Learning, 2015, Theorem 16.8, p. 1130]", fontsize=7.5, fontname="heit", color=c_source)

    # Equation 7: Dirac & Einstein Field Equations
    p3.insert_text((50, 282), "Equation 7 (Dirac Relativistic Spinor & Einstein General Relativity Field Equations):", fontsize=9, fontname="hebo", color=c_primary)
    p3.draw_rect(fitz.Rect(50, 290, 545, 332), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq7_img = render_latex(r"$(i \gamma^\mu \partial_\mu - m)\psi = 0, \qquad R_{\mu\nu} - \frac{1}{2} R g_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4} T_{\mu\nu}$", fontsize=10.5, figsize=(6.5, 0.65))
    p3.insert_image(fitz.Rect(65, 293, 490, 329), stream=eq7_img)
    p3.insert_text((505, 313), "(7)", fontsize=9, fontname="helv", color=c_source)
    p3.insert_text((50, 342), "[Source: Dirac, P. A. M. Proc. R. Soc. Lond. A 117, 610-624 (1928); Einstein, A. Annalen der Physik 49, 769-822 (1916)]", fontsize=7.5, fontname="heit", color=c_source)

    # Section: Chemistry
    p3.insert_text((50, 365), "5. Chemical Thermodynamics & Reversible Kinetics", fontsize=11.5, fontname="hebo", color=c_primary)
    chem_p = (
        "Chemical reaction mechanisms contain molecular phases, equilibrium symbols, and thermodynamic enthalpy metrics. "
        "Inversion of reactant-product order or loss of subscripts destroys scientific validity."
    )
    p3.insert_textbox(fitz.Rect(50, 373, 545, 400), chem_p, fontsize=8.5, fontname="helv", color=c_body, lineheight=1.2)

    # Reaction 8: Haber-Bosch & Contact Catalysis
    p3.insert_text((50, 408), "Reaction 8 (Industrial Catalytic Gas Phase Synthesis & Enthalpy):", fontsize=9, fontname="hebo", color=c_primary)
    p3.draw_rect(fitz.Rect(50, 416, 545, 458), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq8_img = render_latex(r"$\mathrm{N}_2\mathrm{(g)} + 3\,\mathrm{H}_2\mathrm{(g)} \ \ \longleftrightarrow\ \ 2\,\mathrm{NH}_3\mathrm{(g)}, \quad \Delta H_{298\mathrm{K}}^\circ = -92.4\ \mathrm{kJ/mol}, \ \Delta G^\circ = -33.0\ \mathrm{kJ/mol}$", fontsize=10, figsize=(6.8, 0.65))
    p3.insert_image(fitz.Rect(60, 419, 495, 455), stream=eq8_img)
    p3.insert_text((505, 439), "(8)", fontsize=9, fontname="helv", color=c_source)
    p3.insert_text((50, 468), "[Source: Atkins, P., & de Paula, J. Physical Chemistry, 10th ed. Oxford University Press, 2014, Chapter 6]", fontsize=7.5, fontname="heit", color=c_source)

    # Equation 9: Michaelis-Menten with Inhibition & Hill Equation
    p3.insert_text((50, 485), "Equation 9 (Enzyme Catalysis with Competitive & Allosteric Hill Inhibition):", fontsize=9, fontname="hebo", color=c_primary)
    p3.draw_rect(fitz.Rect(50, 493, 545, 535), color=c_line, fill=(0.98, 0.99, 1.0), width=0.5)
    eq9_img = render_latex(r"$v_0 = \frac{V_{\max} [S]}{K_m \left(1 + \frac{[I]}{K_i}\right) + [S]}, \qquad \theta = \frac{[L]^n}{K_d + [L]^n}$", fontsize=11, figsize=(5.5, 0.65))
    p3.insert_image(fitz.Rect(65, 496, 490, 532), stream=eq9_img)
    p3.insert_text((505, 516), "(9)", fontsize=9, fontname="helv", color=c_source)
    p3.insert_text((50, 545), "[Source: Michaelis, L., & Menten, M. L. Biochem. Z., 49, 333-369, 1913; Hill, A. V. J. Physiol., 40, iv-vii, 1910]", fontsize=7.5, fontname="heit", color=c_source)

    # Page 3 Footer
    p3.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p3.insert_text((290, 815), "3", fontsize=9, fontname="helv", color=c_source)

    # =========================================================================
    # PAGE 4: Algorithmic Pseudocode & Dual Scientific Plots
    # =========================================================================
    p4 = doc.new_page(width=595, height=842)
    p4.insert_text((50, 45), header_text, fontsize=8.5, fontname="helv", color=c_source)
    p4.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    p4.insert_text((50, 75), "6. Algorithmic Geometry Decomposition & Spatial Routing", fontsize=11.5, fontname="hebo", color=c_primary)

    # Formal Algorithm Box (Algorithm 1)
    algo_top = 95
    p4.draw_rect(fitz.Rect(50, algo_top, 545, algo_top + 215), color=c_primary, fill=(0.99, 0.99, 1.0), width=1.0)
    p4.draw_line((50, algo_top + 22), (545, algo_top + 22), color=c_primary, width=0.8)
    p4.insert_text((58, algo_top + 15), "Algorithm 1: Decoupled Semantic Layout Decomposition & Boundary Synthesis", fontsize=8.5, fontname="hebo", color=c_primary)

    algo_lines = [
        ("1:", "Input: Raw document layout stream D = {B_1, ..., B_K}, target language code L_target", True),
        ("2:", "Output: Synthesized translated document stream D_trans with identical geometric manifolds", True),
        ("3:", "Initialize active non-prose coordinate mask M_geom <- empty_mask()", False),
        ("4:", "for each bounding block B_i in D do:", False),
        ("5:", "    if is_formula_or_symbol(B_i) or is_table_cell(B_i) then", False),
        ("6:", "        token_id <- register_token(B_i.coordinates, B_i.ink_bbox)", False),
        ("7:", "        M_geom.append(token_id);  B_i.text <- format_placeholder(token_id)", False),
        ("8:", "    else:", False),
        ("9:", "        B_i.prose_spans <- normalize_unicode_diacritics(B_i.text, L_target)", False),
        ("10:", "translated_blocks <- dispatch_neural_translator(D.prose_spans, target=L_target)", False),
        ("11:", "synthesize_page_geometry(translated_blocks, M_geom, strict_lineheight_floor=1.10)", False),
        ("12:", "return D_trans", False),
    ]

    for idx, (num, line, bold) in enumerate(algo_lines):
        y = algo_top + 38 + idx * 14
        font = "hebo" if bold else "courier"
        p4.insert_text((60, y), num, fontsize=7.5, fontname="helv", color=c_source)
        p4.insert_text((82, y), line, fontsize=8.0, fontname=font, color=c_body)

    # Scientific Plot (Figure 2)
    p4.insert_text((50, 335), "7. Empirical Convergence & Dual-Metric Dynamics", fontsize=11.5, fontname="hebo", color=c_primary)
    plot_p = (
        "We trace the optimization landscape across 20 training epochs. The multi-task loss converges exponentially "
        "while linguistic preservation BLEU-4 reaches a stable plateau above 48.0 points."
    )
    p4.insert_textbox(fitz.Rect(50, 345, 545, 375), plot_p, fontsize=8.5, fontname="helv", color=c_body, lineheight=1.2)

    plot_bytes = create_scientific_plot()
    p4.insert_image(fitz.Rect(50, 385, 545, 595), stream=plot_bytes)
    p4.insert_text((70, 608), "Figure 2: Empirical convergence dynamics: dual-axis tracking of training loss and geometric BLEU-4 validation scores.", fontsize=8, fontname="heit", color=c_source)

    # Page 4 Footer
    p4.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p4.insert_text((290, 815), "4", fontsize=9, fontname="helv", color=c_source)

    # =========================================================================
    # PAGE 5: Scientific Benchmark Table & Full Reference Citations
    # =========================================================================
    p5 = doc.new_page(width=595, height=842)
    p5.insert_text((50, 45), header_text, fontsize=8.5, fontname="helv", color=c_source)
    p5.draw_line((50, 52), (545, 52), color=c_line, width=0.8)

    p5.insert_text((50, 75), "8. Quantitative Benchmark Across 48 World Languages", fontsize=11.5, fontname="hebo", color=c_primary)
    exp_p = (
        "We evaluate preservation fidelity against baseline models across five rigorous scientific corpora. "
        "Bounding box coordinates, table borders, and numerical units are strictly isolated to prevent translation bleeding into data columns."
    )
    p5.insert_textbox(fitz.Rect(50, 83, 545, 115), exp_p, fontsize=8.5, fontname="helv", color=c_body, lineheight=1.2)

    # Table 1: Multi-Column Benchmark Data
    p5.insert_text((50, 126), "Table 1: Quantitative benchmark results across scientific document domains and layout models.", fontsize=8.5, fontname="hebo", color=c_primary)
    table_top = 135
    col_x = [50, 135, 255, 335, 420, 545]
    row_h = 22

    # Table header
    p5.draw_rect(fitz.Rect(col_x[0], table_top, col_x[-1], table_top + row_h), color=c_primary, fill=(0.12, 0.22, 0.38))
    headers = ["Model Architecture", "Scientific Domain", "BLEU-4", "Formula IoU", "Latency / Page"]
    for i, h in enumerate(headers):
        p5.insert_text((col_x[i] + 6, table_top + 15), h, fontsize=8, fontname="hebo", color=(1, 1, 1))

    # Table rows
    rows_data = [
        ("LL-1.0.0-PRO", "Theoretical Physics (arXiv)", "44.82", "99.8%", "1.12 s"),
        ("LL-1.0.0-PRO", "Organic Reaction Kinetics", "41.35", "99.6%", "1.18 s"),
        ("LL-1.0.0-PRO", "Differential Geometry", "45.10", "99.9%", "1.09 s"),
        ("LL-1.0.0-PRO", "Biochemical Thermodynamics", "43.20", "99.5%", "1.15 s"),
        ("BabelDOC-Hybrid", "Theoretical Physics (arXiv)", "38.60", "91.2%", "2.40 s"),
        ("BabelDOC-Hybrid", "Organic Reaction Kinetics", "36.40", "88.7%", "2.65 s"),
        ("Baseline-PDF", "Theoretical Physics (arXiv)", "28.40", "64.2%", "3.45 s"),
        ("Baseline-PDF", "Organic Reaction Kinetics", "25.10", "58.1%", "3.80 s"),
    ]

    for r_idx, row in enumerate(rows_data):
        y0 = table_top + (r_idx + 1) * row_h
        y1 = y0 + row_h
        bg_col = (0.97, 0.98, 1.0) if r_idx % 2 == 0 else (1, 1, 1)
        p5.draw_rect(fitz.Rect(col_x[0], y0, col_x[-1], y1), color=c_line, fill=bg_col, width=0.5)
        for c_idx, val in enumerate(row):
            font = "courier" if c_idx in (0, 2, 3, 4) else "helv"
            p5.insert_text((col_x[c_idx] + 6, y0 + 15), val, fontsize=8, fontname=font, color=c_body)

    table_bottom = table_top + (len(rows_data) + 1) * row_h
    p5.insert_text((50, table_bottom + 12), "[Data Source: LayoutLingua Benchmarks v1.0.0, evaluated against PyMuPDF 1.25 & BabelDOC Ground Truth]", fontsize=7, fontname="heit", color=c_source)

    # Section 8: Literature Citations & Full References (10 References)
    p5.insert_text((50, table_bottom + 35), "9. References and Source Literature", fontsize=11.5, fontname="hebo", color=c_primary)
    refs = [
        "[1] I. Goodfellow, Y. Bengio, and A. Courville, Deep Learning. Cambridge, MA: MIT Press, 2016.",
        "[2] A. Vaswani et al., 'Attention Is All You Need', in Advances in Neural Information Processing Systems (NeurIPS), 2017, pp. 5998-6008.",
        "[3] D. J. Griffiths, Introduction to Electrodynamics, 4th ed. Cambridge: Cambridge University Press, 2017.",
        "[4] J. Stewart, Calculus: Early Transcendentals, 8th ed. Boston: Cengage Learning, 2015.",
        "[5] A. Einstein, 'Zur Elektrodynamik bewegter Korper', Annalen der Physik, vol. 322, no. 10, pp. 891-921, 1905.",
        "[6] P. Atkins and J. de Paula, Atkins' Physical Chemistry, 10th ed. Oxford: Oxford University Press, 2014.",
        "[7] L. Michaelis and M. L. Menten, 'Die Kinetik der Invertinwirkung', Biochemische Zeitschrift, vol. 49, pp. 333-369, 1913.",
        "[8] K. He, X. Zhang, S. Ren, and J. Sun, 'Deep Residual Learning for Image Recognition', in IEEE CVPR, 2016, pp. 770-778.",
        "[9] J. Devlin et al., 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding', NAACL-HLT, 2019.",
        "[10] H. Touvron et al., 'LLaMA: Open and Efficient Foundation Language Models', arXiv preprint arXiv:2302.13971, 2023.",
    ]

    ref_y = table_bottom + 52
    for ref in refs:
        p5.insert_textbox(fitz.Rect(50, ref_y, 545, ref_y + 20), ref, fontsize=7.5, fontname="helv", color=c_body, lineheight=1.1)
        ref_y += 21

    # Page 5 Footer
    p5.draw_line((50, 800), (545, 800), color=c_line, width=0.5)
    p5.insert_text((290, 815), "5", fontsize=9, fontname="helv", color=c_source)

    doc.save(str(output_path), deflate=True, garbage=4)
    doc.close()
    print(f"[SUCCESS] 5-Page scientific benchmark document created: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "examples" / "sample_scientific_document.pdf"
    generate_benchmark_pdf(target)
