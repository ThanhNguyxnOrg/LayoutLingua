# Contributing to LayoutLingua

Thank you for your interest in contributing to **LayoutLingua**! We welcome contributions from developers, researchers, and technical writers to build the world's most robust academic and technical PDF translation engine.

---

## 1. Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to security@layoutlingua.org or project maintainers.

---

## 2. Development Setup

### 2.1. Prerequisites

- **Python**: Version 3.10 to 3.12 (CPython recommended)
- **Node.js**: Version 18.0 or newer (LTS recommended)
- **Rust & Cargo**: Version 1.75+ (required only if building native Tauri desktop binaries)
- **Git**: Git 2.30+

### 2.2. Setting Up the Python Core Engine

```bash
# Clone the repository
git clone https://github.com/ThanhNguyxnOrg/LayoutLingua.git
cd LayoutLingua

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install package in editable mode with development test dependencies
pip install -e ".[dev]"
```

### 2.3. Setting Up the Desktop UI (Tauri + React 19)

```bash
cd desktop

# Install frontend dependencies
npm install

# Start Vite local development server
npm run dev
```

The desktop web application will be accessible at `http://localhost:5173`.

---

## 3. Running Tests & Quality Verification

Before submitting any code changes, ensure all tests pass cleanly:

```bash
# Run complete test suite (245 tests)
pytest tests/ -v

# Run a specific test slice
pytest tests/test_slice4c_protection.py -v
pytest tests/test_slice4b_fitting_and_metrics.py -v
```

---

## 4. Coding Standards & Architectural Guidelines

### 4.1. Deep Modules & Seam Discipline

LayoutLingua follows the **Deep Module philosophy** (see [ARCHITECTURE.md](ARCHITECTURE.md)):
- **Small Interfaces**: Expose minimal, clear method signatures to callers.
- **Deep Implementations**: Encapsulate layout heuristics, coordinate conversions, and font metrics internally.
- **Fail-Closed Safety**: When encountering corrupted PDF structures or unresolvable bounding boxes, fall back cleanly to pristine source pages rather than emitting corrupted visual artifacts.

### 4.2. Language & Documentation Standards

- **100% English Requirement**: All commit messages, pull request titles, code comments, docstrings, variable names, and documentation files must be written in clear, concise English.
- **Type Annotations**: All Python functions must include complete PEP 484 type hints.
- **Documentation Integrity**: Preserve all existing architectural docstrings and comments unrelated to your changes.

---

## 5. Commit & Pull Request Conventions

We strictly follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(typesetting): add support for CJK font fallback in multi-column layouts
fix(formula): resolve bounding box overlap on nested fraction denominators
docs(architecture): document cluster-level clearance exclusion zones
test(tables): add regression test for borderless academic tables
```

### 5.1. Autonomous CI/CD & Review Workflow

- Pull requests are verified automatically by GitHub Actions across **Ubuntu**, **Windows**, and **macOS** test matrices.
- Dependabot dependency updates and standard non-breaking PRs are automatically merged via **`ThanhNguyxnAgent`** once all CI tests pass.
- Critical architectural changes (labeled `needs-review`, `critical`, or `breaking-change`) automatically pause auto-merge and request review from **`@ThanhNguyxnOrg/core`** (`@RealThanhNguyxn`, `@ThanhNguyxn07`).

---

## 6. Reporting Issues & Proposing Features

- **Bug Reports**: Please include the exact PDF page number, warning log output (using the **"Copy log"** button in the Quality Checks tab), operating system, and reproduction steps.
- **Feature Requests**: Outline the motivation, expected layout behavior, and trade-offs before opening an implementation pull request.
