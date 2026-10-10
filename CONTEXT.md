# LayoutLingua Domain Context

LayoutLingua preserves academic and technical PDF visual geometry (formulas, tables, styles, coordinates) while translating prose into target languages.

## Language

**Pixel Mask**:
A 2D NumPy integer array at pixmap resolution mapping each pixel coordinate to a layout region class ID.
_Avoid_: Bounding box grid, raster layout map

**Layout Region**:
A detected spatial segment on a page classified into text, title, figure, table, formula, or abandon.
_Avoid_: BBox, block, visual chunk

**Reading Order**:
The logical linear sequence in which human readers traverse layout regions across columns and spanning blocks.
_Avoid_: Traversal index, stream sequence, sort order

**Spatial DAG**:
A directed acyclic graph where nodes represent layout boxes and directed edges enforce human reading precedence based on 2D spatial layout geometry.
_Avoid_: Reading tree, layout graph, precedence tree

**Gutter**:
The vertical whitespace channel separating columns of text in multi-column or borderless table layouts.
_Avoid_: Column gap, white stripe, margin

**Formula Segment**:
An un-translatable equation or math glyph group replaced with an invariant placeholder token like `{vN}` during MT.
_Avoid_: Math block, variable token, formula tag

**Fail-Closed Preservation**:
The invariant design rule where corrupted or untranslatable segments fall back to the original source text rather than outputting broken layouts or lost formulas.
_Avoid_: Safe fallback, silent drop, partial error

**Tabular Row Isolation**:
The structural preservation rule where lines in borderless tables or itemized lists with significant horizontal back-jumps and vertical steps are separated into independent lines rather than merged into a single word-wrapped paragraph.
_Avoid_: Paragraph merge, word reflow, row smearing

**Client RPC Pool**:
A resilient collection of translation endpoints utilizing browser extension and client RPC protocols to prevent HTTP 429 rate-limiting and IP blocks during heavy batch processing.
_Avoid_: Web scraping, mobile HTML endpoint, single-provider dependency

**Legacy Font Normalization**:
The automated conversion of 8-bit legacy font encodings (VNI Windows, TCVN3) without Unicode CMaps into standard Unicode characters before MT processing and typography rendering.
_Avoid_: Custom charset hack, raw encoding fallback, manual text fix

**Document Outline Translation**:
The automated extraction, translation, and re-application of PDF hierarchical bookmarks (`doc.get_toc()`), enabling reader navigation sidebars to reflect the target language.
_Avoid_: Bookmark scraping, metadata copy, outline clone

**Fraction-Aware Line Clustering**:
A 2D spatial line-grouping algorithm that tolerates vertical fraction spans ($y_{\text{num}} \dots y_{\text{den}}$) and binds numerators, fraction bars, and denominators into their parent baseline sequence without splitting denominators onto subsequent lines.
_Avoid_: Plain text line sorting, strict baseline slicing, naive y-binning

