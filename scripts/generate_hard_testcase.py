"""Generate an authentic, hardcore mathematical academic PDF testcase for LayoutLingua.

Features:
1. 100% Full Academic English (IEEE Transactions style).
2. Genuine Typeset Mathematical Formulas (using Matplotlib Mathtext vector/PNG rendering):
   - Multi-variable Gaussian distribution with fraction powers and determinants
   - Euler-Lagrange field equations with partial derivatives and summation
   - Einstein-Jacobian Stress-Energy tensor with Ricci scalar and cosmological constant
   - SVD spectral expansion with singular values and orthogonal vectors
   - Piecewise function with limits and radicals
   - Cauchy residue theorem with contour integration
   - Taylor series expansion with integral remainder
3. Real Mathematical Unicode Glyphs in Running Text:
   - Sets, vectors, and manifolds: ℝ⁴, ℂ, Σ*, ⊂, ∩, ∪, ∈, ∉, ∀, ∃
   - Greek parameter symbols: α, β, γ, δ, ε, λ, κ, μ, π, σ, τ, Ω, Φ, ψ
   - Operators and norms: ‖·‖₂, ‖·‖_F, ∇, ∂_μ, ≤, ≥, ≠, ∞, ∫, ∮, ∑, ·, ×, √
   - Subscripts and superscripts: ², ³, ⁴, ⁻¹, ⁻², ᵢ, ⱼ, ₀, ₁, ₂
   - Formal Q.E.D. symbol: ∎
4. Multi-Column Reading Order Integrity (2-column layout with spanning header).
5. Complex Hierarchical Table with merged super-headers, sub-headers, zebra rows.
6. Algorithm 1 with 15 numbered steps and mathematical symbol indentation.
7. Multi-panel figure with comprehensive diagnostic caption.
8. Running headers, running footers, footnotes, and IEEE bibliography.
"""

from pathlib import Path
import os
import io
import pymupdf
import matplotlib.pyplot as plt

CAMBRIA_PATH = "C:/Windows/Fonts/cambria.ttc"
CAMBRIA_BOLD_PATH = "C:/Windows/Fonts/cambriab.ttf"
CAMBRIA_ITALIC_PATH = "C:/Windows/Fonts/cambriai.ttf"

def setup_page_fonts(page):
    """Register Cambria font family on the PyMuPDF page for complete Unicode math support."""
    page.insert_font(fontname="cambria", fontfile=CAMBRIA_PATH)
    page.insert_font(fontname="cambria-bold", fontfile=CAMBRIA_BOLD_PATH)
    page.insert_font(fontname="cambria-italic", fontfile=CAMBRIA_ITALIC_PATH)

def render_math_to_png(latex_formula: str, fontsize: int = 22, dpi: int = 300) -> bytes:
    """Render a LaTeX formula string to transparent PNG bytes using Matplotlib."""
    plt.rcParams["mathtext.fontset"] = "cm"
    fig, ax = plt.subplots(figsize=(8.0, 1.5), dpi=dpi)
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    formula_text = f"${latex_formula}$"
    ax.text(0.5, 0.5, formula_text, fontsize=fontsize, ha="center", va="center", color="#111827")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(fig)
    return buf.getvalue()

def create_hardcore_math_testcase(output_path: str = "hard_testcase_layoutlingua.pdf") -> str:
    doc = pymupdf.open()
    page_w, page_h = 595.0, 842.0  # A4

    def draw_running_header_footer(page, page_num: int, total_pages: int = 4):
        setup_page_fonts(page)
        # Top running header
        page.insert_text(
            pymupdf.Point(50, 36),
            "IEEE TRANSACTIONS ON COMPUTATIONAL MATHEMATICS & DOCUMENT SYSTEMS, VOL. 42, NO. 2",
            fontsize=7.5,
            color=(0.35, 0.35, 0.35),
            fontname="cambria",
        )
        page.draw_line(pymupdf.Point(50, 42), pymupdf.Point(page_w - 50, 42), color=(0.75, 0.75, 0.75), width=0.6)

        # Bottom running footer
        page.draw_line(pymupdf.Point(50, page_h - 40), pymupdf.Point(page_w - 50, page_h - 40), color=(0.75, 0.75, 0.75), width=0.6)
        page.insert_text(
            pymupdf.Point(50, page_h - 28),
            "1549-7723/26 (C) 2026 IEEE. Personal use is permitted, but republication requires IEEE permission.",
            fontsize=6.5,
            color=(0.45, 0.45, 0.45),
            fontname="cambria",
        )
        page.insert_text(
            pymupdf.Point(page_w - 75, page_h - 28),
            f"Page {page_num} of {total_pages}",
            fontsize=7.5,
            color=(0.25, 0.25, 0.25),
            fontname="cambria",
        )

    # Pre-render all authentic math formulas (Matplotlib mathtext compatible)
    eq_euler = render_math_to_png(r"\frac{\partial \mathcal{L}}{\partial \phi} - \sum_{\mu=0}^3 \partial_\mu \left( \frac{\partial \mathcal{L}}{\partial(\partial_\mu \phi)} \right) = \kappa \cdot \nabla^2 \Phi(\mathbf{x}, t)")
    eq_distortion = render_math_to_png(r"\sup_{x \in \Omega} |\delta(B_i^*) - 1| \leq \frac{\alpha}{\gamma} \cdot \exp\left( \beta \int_{\Omega} \sqrt{\det(g_{ij})} \, d^n x \right)")
    eq_matrix = render_math_to_png(r"\mathbf{J}_{\mu\nu}(\mathbf{x}) = \frac{\partial^2 \Phi}{\partial x_\mu \partial x_\nu} + \frac{1}{2} g_{\mu\nu} R - \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4} T_{\mu\nu}")
    eq_svd = render_math_to_png(r"\mathbf{A} = \mathbf{U} \mathbf{\Sigma} \mathbf{V}^T = \sum_{r=1}^{\mathrm{rank}(\mathbf{A})} \sigma_r \, \mathbf{u}_r \mathbf{v}_r^T \quad (\sigma_1 \geq \sigma_2 \geq \dots > 0)")
    eq_cases = render_math_to_png(r"\psi_k(x) = \frac{\sin(\pi k x)}{\pi k x} \cdot \sqrt{1 - x^2} \quad (|x| < 1), \quad \lim_{\epsilon \to 0} \frac{e^{-\epsilon/x^2}}{\sqrt{2\pi\sigma^2}} = 0")
    eq_gaussian = render_math_to_png(r"\mathcal{N}(\mathbf{x}; \boldsymbol{\mu}, \mathbf{\Sigma}) = \frac{1}{(2\pi)^{d/2} |\mathbf{\Sigma}|^{1/2}} \exp\left( -\frac{1}{2} (\mathbf{x} - \boldsymbol{\mu})^T \mathbf{\Sigma}^{-1} (\mathbf{x} - \boldsymbol{\mu}) \right)")
    eq_cauchy = render_math_to_png(r"\oint_{\gamma} \frac{f(z)}{(z - z_0)^{m+1}} dz = \frac{2\pi i}{m!} f^{(m)}(z_0) = 2\pi i \sum_{k=1}^K \mathrm{Res}(f, z_k)")
    eq_taylor = render_math_to_png(r"f(x) = \sum_{n=0}^{N} \frac{f^{(n)}(a)}{n!} (x - a)^n + \frac{1}{N!} \int_{a}^{x} (x - t)^N f^{(N+1)}(t) \, dt")

    # =========================================================================
    # PAGE 1: Two-Column Academic Paper with Dense Typeset Formulas
    # =========================================================================
    p1 = doc.new_page(width=page_w, height=page_h)
    draw_running_header_footer(p1, 1)

    # Document Title (spans full width)
    p1.insert_textbox(
        pymupdf.Rect(50, 56, page_w - 50, 108),
        "Non-Euclidean Variational Mechanics and Differential Geometry for Multi-Manifold Field Theory",
        fontsize=16.0,
        fontname="cambria-bold",
        align=pymupdf.TEXT_ALIGN_CENTER,
    )

    # Authors & Affiliations
    p1.insert_textbox(
        pymupdf.Rect(50, 110, page_w - 50, 140),
        "Alexander Moreau(1), Kenji Tanaka(2), Elizabeth Mueller(3), and H. David Vance(1)*\n"
        "(1) Applied Mathematics Institute, Cambridge   (2) Department of Information Physics, Tokyo   (3) ETH Zurich",
        fontsize=8.5,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_CENTER,
    )

    # Abstract & Keywords Box
    abs_rect = pymupdf.Rect(55, 142, page_w - 55, 238)
    p1.draw_rect(abs_rect, color=(0.8, 0.82, 0.85), fill=(0.96, 0.97, 0.98), width=0.8)
    p1.insert_textbox(
        pymupdf.Rect(65, 146, page_w - 65, 234),
        "Abstract---Preserving spatial document typography, mathematical typesetting, and hierarchical table topology during cross-lingual neural translation remains a formidable open challenge. Traditional sequence-to-sequence architectures discard absolute coordinate manifolds (x, y, w, h) ∈ ℝ⁴, causing disastrous text-overflow and grid collapse. We present LayoutLingua, a geometry-aware transformer integrating non-isomorphic tensor decomposition with differential Hungarian bounding-box matching. Our benchmark across 14 language pairs demonstrates a 4.8x reduction in visual clipping while maintaining 99.2% mathematical equation consistency.\n\n"
        "Index Terms---Document AI, Layout-Aware NMT, Mathematical OCR, Differential Geometry, Tensor Splitting.",
        fontsize=7.3,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Two-Column Coordinates
    col_w = 238.0
    col1_l = 50.0
    col1_r = col1_l + col_w
    col2_l = page_w - 50.0 - col_w
    col2_r = col2_l + col_w
    body_top = 246.0
    body_bottom = page_h - 75.0

    # Column 1 Content: Introduction, Problem Formulation, and Definition 1
    c1_text = (
        "1. INTRODUCTION\n\n"
        "Scientific literature is inherently multi-modal. Unlike continuous unstructured prose, academic publications rely on spatial juxtaposition: definitions are anchored beside diagrams, and multi-line equations reference corresponding variables in subsequent paragraphs.\n\n"
        "When translated from source English S to high-expansion target languages (such as German or Vietnamese), text length frequently expands by +28% to +42%. Naive replacement of glyph streams results in overlapping blocks, severed column flows, and unreadable equations.\n\n"
        "2. PROBLEM FORMULATION & MANIFOLD TOPOLOGY\n\n"
        "Let a document page D = {B₁, B₂, ..., Bₙ} comprise N discrete visual bounding primitives where Bᵢ = (tᵢ, pᵢ, sᵢ), with text payload tᵢ ∈ Σ*, spatial polygon pᵢ = (xᵢ, yᵢ, wᵢ, hᵢ) ∈ ℝ⁴, and semantic class sᵢ ∈ {Header, Body, Formula, TableCell}.\n\n"
        "Definition 1 (Spatial Deformation Energy): For any adjacent pair of primitives (Bᵢ, Bⱼ), we define the bilateral deformation energy functional:\n\n"
        "    E(Bᵢ, Bⱼ) = α ‖pᵢ - pⱼ‖₂⁻² + β · IoU(pᵢ, pⱼ)\n\n"
        "where α, β > 0 denote the balance hyper-parameters and IoU(pᵢ, pⱼ) = Area(pᵢ ∩ pⱼ) / Area(pᵢ ∪ pⱼ). The global objective of layout-aware translation is finding a mapping Φ: D → D* maximizing semantic fidelity while maintaining the topological invariant constraint: Area(pᵢ* ∩ pⱼ*) = 0, ∀ i ≠ j."
    )
    p1.insert_textbox(
        pymupdf.Rect(col1_l, body_top, col1_r, body_bottom),
        c1_text,
        fontsize=7.8,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Column 2 Content: Section 3, Equations (1) and (2), and Formal Proof
    c2_text = (
        "3. MATHEMATICAL EQUATION PRESERVATION\n\n"
        "To prevent neural hallucination inside mathematical environments, we formulate the field Lagrangian L(ϕ, ∂_μ ϕ) as an unconstrained variational optimization over domain Ω ⊂ ℝᵈ:"
    )
    p1.insert_textbox(
        pymupdf.Rect(col2_l, body_top, col2_r, body_top + 48),
        c2_text,
        fontsize=7.8,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (1): Euler-Lagrange Field Equation
    eq1_box = pymupdf.Rect(col2_l, body_top + 50, col2_r, body_top + 106)
    p1.draw_rect(eq1_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p1.insert_image(pymupdf.Rect(col2_l + 4, body_top + 52, col2_r - 28, body_top + 104), stream=eq_euler, keep_proportion=True)
    p1.insert_text(pymupdf.Point(col2_r - 22, body_top + 80), "(1)", fontsize=8.5, fontname="cambria")

    c2_mid = (
        "where ∂_μ denotes the covariant four-derivative and κ > 0 represents the constitutive coupling coefficient.\n\n"
        "Theorem 1 (Bounded Metric Distortion): If the source Riemannian curvature tensor satisfies Rᵢⱼₖₗ ≤ M₀ for constant M₀ < ∞, then under the optimal transport map T*, the aspect ratio distortion δ(Bᵢ*) is strictly bounded by:"
    )
    p1.insert_textbox(
        pymupdf.Rect(col2_l, body_top + 112, col2_r, body_top + 190),
        c2_mid,
        fontsize=7.8,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (2): Metric Distortion
    eq2_box = pymupdf.Rect(col2_l, body_top + 194, col2_r, body_top + 248)
    p1.draw_rect(eq2_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p1.insert_image(pymupdf.Rect(col2_l + 4, body_top + 196, col2_r - 28, body_top + 246), stream=eq_distortion, keep_proportion=True)
    p1.insert_text(pymupdf.Point(col2_r - 22, body_top + 224), "(2)", fontsize=8.5, fontname="cambria")

    c2_end = (
        "Proof: Let u ∈ W¹ʼ²(Ω) denote the coordinate displacement field. By the Cauchy-Schwarz inequality over Sobolev space W¹ʼ²(Ω) and the Poincaré-Wirtinger inequality with optimal constant Cₚ = diam(Ω) / π, we have ‖∇u‖_L² ≥ Cₚ ‖u - ū‖_L². Integrating along geodesic paths on manifold M and substituting the field Lagrangian identity (1) establishes bound (2). Q.E.D. ∎\n\n"
        "Corollary 1.1: For any isotropic expansion factor λ ∈ [1.28, 1.42], the bounding box distortion satisfies supᵢ |δ(Bᵢ*) - 1| ≤ O(λ¹/ᵈ - 1)."
    )
    p1.insert_textbox(
        pymupdf.Rect(col2_l, body_top + 254, col2_r, body_bottom),
        c2_end,
        fontsize=7.8,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Footnote at bottom of Column 1
    p1.draw_line(pymupdf.Point(col1_l, page_h - 70), pymupdf.Point(col1_l + 90, page_h - 70), color=(0.4, 0.4, 0.4), width=0.5)
    p1.insert_textbox(
        pymupdf.Rect(col1_l, page_h - 68, col1_r, page_h - 44),
        "*Corresponding author: a.moreau@appliedmath.cam.ac.uk. Manuscript received October 12, 2026; revised January 14, 2027. Supported in part by the European Research Council (ERC) under Grant Agreement 942-MATH-GEO.",
        fontsize=6.5,
        fontname="cambria",
    )

    # =========================================================================
    # PAGE 2: Matrices, Spectral Decomposition & Hierarchical Data Table
    # =========================================================================
    p2 = doc.new_page(width=page_w, height=page_h)
    draw_running_header_footer(p2, 2)

    p2.insert_textbox(
        pymupdf.Rect(50, 52, page_w - 50, 104),
        "4. TENSOR ALGEBRA & MULTI-DIMENSIONAL CURVATURE OPERATORS\n\n"
        "Let J_μν(x) represent the coupled Einstein-Jacobian stress-energy tensor governing manifold geometric deformation under coordinate transformations:",
        fontsize=8.5,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (3): Stress-Energy Tensor
    eq3_box = pymupdf.Rect(50, 108, page_w - 50, 158)
    p2.draw_rect(eq3_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p2.insert_image(pymupdf.Rect(60, 110, page_w - 90, 156), stream=eq_matrix, keep_proportion=True)
    p2.insert_text(pymupdf.Point(page_w - 75, 136), "(3)", fontsize=8.5, fontname="cambria")

    p2.insert_textbox(
        pymupdf.Rect(50, 164, page_w - 50, 196),
        "Under the Singular Value Decomposition (SVD), any rectangular layout coupling matrix A ∈ ℝᵐˣⁿ factorizes into orthogonal singular subspaces:",
        fontsize=8.5,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (4): SVD Equation
    eq4_box = pymupdf.Rect(50, 200, page_w - 50, 246)
    p2.draw_rect(eq4_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p2.insert_image(pymupdf.Rect(60, 202, page_w - 90, 244), stream=eq_svd, keep_proportion=True)
    p2.insert_text(pymupdf.Point(page_w - 75, 226), "(4)", fontsize=8.5, fontname="cambria")

    # Table Title
    p2.insert_text(
        pymupdf.Point(50, 262),
        "TABLE I: QUANTITATIVE COMPONENT BREAKDOWN ACROSS MULTI-LEVEL STRUCTURAL BENCHMARKS",
        fontsize=8.0,
        fontname="cambria-bold",
    )

    # Complex Table Drawing (8 Columns with Merged Super-Headers)
    t_top = 270.0
    t_left = 50.0
    t_w = page_w - 100.0
    cols = [110.0, 75.0, 50.0, 50.0, 50.0, 50.0, 55.0, 55.0]  # Sum = 495
    t_rows = 11
    row_h = 18.0
    t_height = 36.0 + (t_rows - 2) * row_h
    p2.draw_rect(pymupdf.Rect(t_left, t_top, t_left + t_w, t_top + t_height), color=(0.2, 0.2, 0.2), width=0.8)

    # Super-Header Row
    p2.draw_rect(pymupdf.Rect(t_left, t_top, t_left + t_w, t_top + 18), fill=(0.90, 0.92, 0.95), width=0)
    p2.draw_line(pymupdf.Point(t_left, t_top + 18), pymupdf.Point(t_left + t_w, t_top + 18), color=(0.4, 0.4, 0.4), width=0.5)
    p2.draw_line(pymupdf.Point(t_left, t_top + 36), pymupdf.Point(t_left + t_w, t_top + 36), color=(0.2, 0.2, 0.2), width=0.8)

    p2.insert_text(pymupdf.Point(t_left + 15, t_top + 13), "Method / Architecture", fontsize=7.5, fontname="cambria-bold")
    p2.insert_text(pymupdf.Point(t_left + 120, t_top + 13), "Param (M)", fontsize=7.5, fontname="cambria-bold")
    p2.insert_text(pymupdf.Point(t_left + 215, t_top + 13), "Translation Quality", fontsize=7.5, fontname="cambria-bold")
    p2.insert_text(pymupdf.Point(t_left + 355, t_top + 13), "Layout Geometry Integrity", fontsize=7.5, fontname="cambria-bold")
    p2.insert_text(pymupdf.Point(t_left + 450, t_top + 13), "Speed", fontsize=7.5, fontname="cambria-bold")

    # Sub-Headers
    sub_headers = ["Model Baseline", "Backbone", "BLEU-4", "COMET", "chrF++", "IoU (%)", "Overlap", "Sec/p"]
    x_curr = t_left
    for idx, (sh, cw) in enumerate(zip(sub_headers, cols)):
        p2.insert_text(pymupdf.Point(x_curr + 4, t_top + 30), sh, fontsize=7.0, fontname="cambria-bold")
        if idx > 0:
            p2.draw_line(pymupdf.Point(x_curr, t_top + 18), pymupdf.Point(x_curr, t_top + t_height), color=(0.8, 0.8, 0.8), width=0.4)
        x_curr += cw

    # Table Body Rows
    table_data = [
        ["Standard MarianMT", "Transformer-Base", "31.2", "0.742", "56.4", "41.2%", "18.4%", "0.34s"],
        ["DeepL DocTranslator", "Proprietary", "38.7", "0.824", "64.1", "68.5%", "9.2%", "2.45s"],
        ["Google Cloud DocAPI", "Transformer-XXL", "39.1", "0.831", "65.0", "72.0%", "7.8%", "1.85s"],
        ["Nougat Academic", "Donut-BART", "33.5", "0.761", "58.9", "79.4%", "5.1%", "3.12s"],
        ["Marker Markdown", "Surya-OCR", "34.0", "0.778", "60.2", "81.0%", "4.5%", "2.90s"],
        ["LayoutLMv3 + NMT", "RoBERTa+T5", "37.4", "0.812", "63.5", "84.3%", "3.8%", "1.65s"],
        ["Ollama Llama-3.1-8B", "Local GGUF", "36.8", "0.805", "62.8", "76.4%", "6.2%", "4.20s"],
        ["Gemini 2.5 Flash", "Gemini-API", "41.5", "0.865", "67.9", "88.1%", "2.4%", "1.10s"],
        ["LayoutLingua (Ours)", "PyMuPDF+Tensor", "42.8", "0.884", "69.4", "96.7%", "0.3%", "0.48s"],
    ]

    for r_idx, row in enumerate(table_data):
        y_r = t_top + 36.0 + r_idx * row_h
        if r_idx % 2 == 1:
            p2.draw_rect(pymupdf.Rect(t_left, y_r, t_left + t_w, y_r + row_h), fill=(0.97, 0.97, 0.98), width=0)
        if r_idx == len(table_data) - 1:
            p2.draw_rect(pymupdf.Rect(t_left, y_r, t_left + t_w, y_r + row_h), fill=(0.91, 0.96, 0.93), width=0)

        p2.draw_line(pymupdf.Point(t_left, y_r + row_h), pymupdf.Point(t_left + t_w, y_r + row_h), color=(0.85, 0.85, 0.85), width=0.4)

        x_c = t_left
        for c_idx, (val, cw) in enumerate(zip(row, cols)):
            font = "cambria-bold" if r_idx == len(table_data) - 1 else "cambria"
            color = (0.05, 0.45, 0.25) if r_idx == len(table_data) - 1 else (0.15, 0.15, 0.15)
            p2.insert_text(pymupdf.Point(x_c + 4, y_r + 12), val, fontsize=7.2, fontname=font, color=color)
            x_c += cw

    # Post-Table Analytical & Mathematical Discussion
    p2.insert_textbox(
        pymupdf.Rect(50, t_top + t_height + 14, page_w - 50, page_h - 55),
        "Notice in Table I that standard neural machine translation engines fail dramatically on the IoU geometric metric (only 41.2% to 68.5%) because they lack the Riemannian coordinate invariance formalized in equations (3) and (4). By projecting onto principal singular vectors uᵣ vᵣᵀ, LayoutLingua bounds aspect ratio distortion strictly below 0.3% while attaining 42.8 BLEU-4.\n\n"
        "Lemma 2 (Singular Value Contraction & Spectral Gap): Let layout coupling matrix A ∈ ℝᵐˣⁿ have singular values σ₁ ≥ σ₂ ≥ ... ≥ σᵣ > 0 with condition number κ(A) = σ₁ / σᵣ. If the minimum spectral gap satisfies Δ = minᵢ≠ⱼ |σᵢ - σⱼ| ≥ ε₀ > 0, then the perturbed bounding box coordinates satisfy ‖pᵢ* - pᵢᵒʳⁱᵍ‖₂ ≤ (√2 ‖E‖_F) / Δ + O(‖E‖_F²), where ‖E‖_F denotes the Frobenius perturbation norm. Consequently, document topology is asymptotically invariant under coordinate rescaling.\n\n"
        "Complexity Analysis: The Hungarian bipartite matching runs in O(V² E) = O(N³) worst-case time, but with k-d tree spatial pruning over search radius r₀ = 3 · max(wᵢ, hᵢ), the average-case runtime drops to O(N log N). Across a standard 1,000-word academic paper (N ≈ 120 blocks), total relaxation latency is strictly below 480 ms on a single CPU core.",
        fontsize=7.8,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # =========================================================================
    # PAGE 3: Piecewise Functions, Probability & Algorithm Pseudocode
    # =========================================================================
    p3 = doc.new_page(width=page_w, height=page_h)
    draw_running_header_footer(p3, 3)

    p3.insert_textbox(
        pymupdf.Rect(50, 52, page_w - 50, 104),
        "5. PIECEWISE WAVELET KERNELS & STOCHASTIC FORMULATIONS\n\n"
        "To regularize boundary discontinuity across adjacent paragraphs, we define the non-smooth piecewise spatial window function ψₖ(x) with compact support supp(ψₖ) ⊂ [-1, 1] satisfying L² orthogonality ⟨ψₖ, ψₗ⟩ = δₖₗ:",
        fontsize=8.2,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (5): Piecewise Cases
    eq5_box = pymupdf.Rect(50, 108, page_w - 50, 158)
    p3.draw_rect(eq5_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p3.insert_image(pymupdf.Rect(60, 110, page_w - 90, 156), stream=eq_cases, keep_proportion=True)
    p3.insert_text(pymupdf.Point(page_w - 75, 136), "(5)", fontsize=8.5, fontname="cambria")

    p3.insert_textbox(
        pymupdf.Rect(50, 164, page_w - 50, 196),
        "Under Bayesian priors, stochastic coordinate perturbation follows a d-dimensional multivariate Gaussian probability density function N(x; μ, Σ) with positive-definite covariance matrix Σ ∈ S₊₊ᵈ and log-determinant ln|Σ|:",
        fontsize=8.0,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (6): Multivariate Gaussian
    eq6_box = pymupdf.Rect(50, 200, page_w - 50, 246)
    p3.draw_rect(eq6_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p3.insert_image(pymupdf.Rect(60, 202, page_w - 90, 244), stream=eq_gaussian, keep_proportion=True)
    p3.insert_text(pymupdf.Point(page_w - 75, 226), "(6)", fontsize=8.5, fontname="cambria")

    # Algorithm Box
    algo_rect = pymupdf.Rect(50, 256, page_w - 50, 482)
    p3.draw_rect(algo_rect, color=(0.3, 0.3, 0.3), fill=(0.99, 0.99, 0.99), width=0.8)
    p3.draw_line(pymupdf.Point(50, 274), pymupdf.Point(page_w - 50, 274), color=(0.3, 0.3, 0.3), width=0.8)
    p3.insert_text(pymupdf.Point(58, 269), "Algorithm 1: Dynamic Riemannian Geometry Relocation (DRGR)", fontsize=8.5, fontname="cambria-bold")

    algo_lines = [
        "Input : Source PDF Page D, Translation Model T, Boundary Margin τ > 0, Max Iterations Kₘₐₓ = 50",
        "Output: Typeset Translated Page D* with preserved mathematical blocks and minimal clipping error",
        " 1: Parse primitives P = {b₁, ..., bₙ} via PyMuPDF C-extension; extract font metrics and DPI;",
        " 2: Isolate frozen blocks F ⊂ P where type(bᵢ) ∈ {Formula, VectorGraphic, Signature};",
        " 3: For each mutable text block tⱼ in P \\ F do",
        " 4:    τⱼ ← QueryNeuralProvider(tⱼ, src='en', tgt='vi', preserve_formatting=True);",
        " 5:    Compute expanded bounding box Bⱼ* using font rasterization advance widths;",
        " 6: end for",
        " 7: Construct spring-electrical adjacency graph G = (V, E) where edge weights wᵢⱼ = exp(-dist(bᵢ, bⱼ));",
        " 8: Initialize epoch k ← 0; total overlap metric Ω(0) ← ∞;",
        " 9: while k < Kₘₐₓ and Ω(k) > 10⁻⁴ do",
        "10:    Compute repulsive force: F_rep(i) = ∑(j≠i) [(pᵢ - pⱼ) / ‖pᵢ - pⱼ‖³] · Area(bᵢ ∩ bⱼ);",
        "11:    Compute structural anchor pull: F_anc(i) = -κ · (pᵢ - pᵢᵒʳⁱᵍ);",
        "12:    Update coordinates: pᵢ ← pᵢ + η · (F_rep(i) + F_anc(i));",
        "13:    k ← k + 1; Recompute overlap metric Ω(k);",
        "14: end while",
        "15: Return synthesized document D* = {b₁*, ..., bₙ*};",
    ]

    for idx, l in enumerate(algo_lines):
        color = (0.1, 0.1, 0.1) if idx > 1 else (0.2, 0.2, 0.4)
        # Use cambria regular for lines containing math symbols to ensure full glyph coverage
        font = "cambria-bold" if idx in (0, 1, 7, 10, 15, 16) else "cambria"
        p3.insert_text(pymupdf.Point(58, 288 + idx * 12.0), l, fontsize=6.8, fontname=font, color=color)

    # Multi-Panel Diagram
    fig_top = 496.0
    fig_w = page_w - 100.0
    panel_w = (fig_w - 20) / 3

    p3.draw_rect(pymupdf.Rect(50, fig_top, 50 + panel_w, fig_top + 125), color=(0.7, 0.7, 0.7), fill=(0.95, 0.95, 0.97), width=0.5)
    p3.draw_line(pymupdf.Point(60, fig_top + 105), pymupdf.Point(50 + panel_w - 10, fig_top + 30), color=(0.8, 0.2, 0.2), width=1.5)
    p3.insert_text(pymupdf.Point(60, fig_top + 20), "(a) Source Expansion Ratio", fontsize=7.5, fontname="cambria-bold")

    p3.draw_rect(pymupdf.Rect(50 + panel_w + 10, fig_top, 50 + 2 * panel_w + 10, fig_top + 125), color=(0.7, 0.7, 0.7), fill=(0.95, 0.97, 0.95), width=0.5)
    for step in range(5):
        y_b = fig_top + 35 + step * 16
        p3.draw_rect(pymupdf.Rect(50 + panel_w + 25, y_b, 50 + 2 * panel_w - 10, y_b + 10), fill=(0.3, 0.6, 0.4), width=0)
    p3.insert_text(pymupdf.Point(50 + panel_w + 20, fig_top + 20), "(b) Hungarian Bipartite Match", fontsize=7.5, fontname="cambria-bold")

    p3.draw_rect(pymupdf.Rect(50 + 2 * panel_w + 20, fig_top, 50 + fig_w, fig_top + 125), color=(0.7, 0.7, 0.7), fill=(0.97, 0.95, 0.95), width=0.5)
    p3.draw_circle(pymupdf.Point(50 + 2 * panel_w + 20 + panel_w / 2, fig_top + 68), 30, color=(0.2, 0.4, 0.8), width=1.2)
    p3.insert_text(pymupdf.Point(50 + 2 * panel_w + 25, fig_top + 20), "(c) Pareto Frontier (BLEU vs IoU)", fontsize=7.2, fontname="cambria-bold")

    p3.insert_textbox(
        pymupdf.Rect(50, fig_top + 132, page_w - 50, fig_top + 175),
        "Fig. 1. Diagnostic convergence trajectory across 10,000 document iterations: (a) Text expansion histogram shows German and Vietnamese expanding +34% on average; (b) Hungarian matching converges in under 12 iterations; (c) Pareto frontier proves simultaneous optimization of semantic translation accuracy and bounding-box preservation.",
        fontsize=7.2,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # =========================================================================
    # PAGE 4: Contour Integrals, Taylor Series & Academic Bibliography
    # =========================================================================
    p4 = doc.new_page(width=page_w, height=page_h)
    draw_running_header_footer(p4, 4)

    p4.insert_textbox(
        pymupdf.Rect(50, 52, page_w - 50, 104),
        "6. COMPLEX CONTOUR INTEGRATION & ASYMPTOTIC EXPANSIONS\n\n"
        "Theorem 2 (Residue Formulation of Dislocation Poles): In the complex domain ℂ, the analytic continuation of layout energy poles is governed by the Cauchy Residue Theorem over closed contour γ = ∂Ω enclosing poles {z₁, ..., zₖ}:",
        fontsize=8.2,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (7): Cauchy Residue Theorem
    eq7_box = pymupdf.Rect(50, 108, page_w - 50, 158)
    p4.draw_rect(eq7_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p4.insert_image(pymupdf.Rect(60, 110, page_w - 90, 156), stream=eq_cauchy, keep_proportion=True)
    p4.insert_text(pymupdf.Point(page_w - 75, 136), "(7)", fontsize=8.5, fontname="cambria")

    p4.insert_textbox(
        pymupdf.Rect(50, 164, page_w - 50, 196),
        "Furthermore, polynomial approximation with integral remainder Rₙ(x) in the neighborhood of anchor pole a ∈ ℂ is given by the generalized Taylor Series where f ∈ Cᴺ⁺¹(Ω):",
        fontsize=8.0,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    # Typeset Equation (8): Taylor Series with Remainder
    eq8_box = pymupdf.Rect(50, 200, page_w - 50, 246)
    p4.draw_rect(eq8_box, color=(0.85, 0.85, 0.85), fill=(0.99, 0.99, 0.99), width=0.5)
    p4.insert_image(pymupdf.Rect(60, 202, page_w - 90, 244), stream=eq_taylor, keep_proportion=True)
    p4.insert_text(pymupdf.Point(page_w - 75, 226), "(8)", fontsize=8.5, fontname="cambria")

    p4.insert_text(pymupdf.Point(50, 260), "REFERENCES", fontsize=9.0, fontname="cambria-bold")
    p4.draw_line(pymupdf.Point(50, 265), pymupdf.Point(page_w - 50, 265), color=(0.4, 0.4, 0.4), width=0.6)

    references = [
        "[1] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, L. Kaiser, and I. Polosukhin, 'Attention is all you need,' in Advances in Neural Information Processing Systems (NeurIPS), vol. 30, pp. 5998-6008, Long Beach, CA, Dec. 2017.",
        "[2] D. E. Knuth, The TeXbook, Reading, MA, USA: Addison-Wesley Professional, 1984, ISBN: 0-201-13447-0.",
        "[3] Y. LeCun, L. Bottou, Y. Bengio, and P. Haffner, 'Gradient-based learning applied to document recognition,' Proceedings of the IEEE, vol. 86, no. 11, pp. 2278-2324, Nov. 1998, doi: 10.1109/5.726791.",
        "[4] H. T. Nguyen, V. Q. Tran, and D. L. Pham, 'Automatic multi-column layout analysis for scientific literature,' Journal of Computer Science & Cybernetics, vol. 38, no. 2, pp. 145-158, 2022.",
        "[5] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, 'BERT: Pre-training of deep bidirectional transformers for language understanding,' in Proc. NAACL-HLT, Minneapolis, MN, Jun. 2019, pp. 4171-4186.",
        "[6] K. Tanaka and E. Mueller-Schroedinger, 'Geometric invariant transforms on Riemannian manifolds,' Journal of Differential Equations & Topology, vol. 114, no. 3, pp. 450-478, Zurich, 2024.",
        "[7] PyMuPDF Contributors, 'High performance PDF rendering and document manipulation library,' Artifex Software, 2026. [Online]. Available: https://pymupdf.readthedocs.io/",
        "[8] L. Evans, Partial Differential Equations, 2nd ed., Graduate Studies in Mathematics, vol. 19, American Mathematical Society, Providence, RI, 2010.",
    ]

    ref_y = 275.0
    for ref in references:
        p4.insert_textbox(
            pymupdf.Rect(50, ref_y, page_w - 50, ref_y + 32),
            ref,
            fontsize=7.2,
            fontname="cambria",
            align=pymupdf.TEXT_ALIGN_JUSTIFY,
        )
        ref_y += 32.0

    # Authors biographies box
    bio_y = ref_y + 12
    p4.draw_rect(pymupdf.Rect(50, bio_y, page_w - 50, page_h - 55), color=(0.85, 0.85, 0.85), fill=(0.98, 0.98, 0.98), width=0.5)
    p4.insert_text(pymupdf.Point(60, bio_y + 16), "AUTHOR BIOGRAPHIES", fontsize=8.0, fontname="cambria-bold")

    bio_text = (
        "Alexander Moreau received the Ph.D. degree in Applied Mathematics from the University of Cambridge. His research spans Riemannian geometry, geometric deep learning, and invariant tensor analysis.\n\n"
        "Elizabeth Mueller is a Full Professor of Mathematics at ETH Zurich. She was elected an IEEE Fellow for foundational contributions to variational physics and topological manifold theory."
    )
    p4.insert_textbox(
        pymupdf.Rect(60, bio_y + 24, page_w - 60, page_h - 62),
        bio_text,
        fontsize=7.2,
        fontname="cambria",
        align=pymupdf.TEXT_ALIGN_JUSTIFY,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path

if __name__ == "__main__":
    out = create_hardcore_math_testcase("hard_testcase_layoutlingua.pdf")
    print(f"Generated hardcore testcase: {out}")
