# DocStructureX — Intelligent PDF Outline Extractor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [About DocStructureX](#about-docstructurex)  
- [Key Features](#key-features)  
- [How It Works](#how-it-works)  
- [Architecture & Components](#architecture--components)  
- [Installation & Setup](#installation--setup)  
- [Usage Guide](#usage-guide)  
- [Docker Integration](#docker-integration)  
- [Development & Contribution](#development--contribution)  
- [License](#license)  
- [Acknowledgments](#acknowledgments)

---

## About DocStructureX

DocStructureX is a production-ready PDF outline extraction tool developed as part of the Adobe India Hackathon 2025, Round 1A challenge “Connecting the Dots Through Docs.” It transforms raw PDFs into structured, hierarchical outlines comprising the document’s title and section headings (H1, H2, H3), enabling smarter document understanding and advanced interaction layers.

By bridging the semantic gap between PDF binaries and meaningful document sections, it paves the way for enhanced semantic search, personalized document reading experiences, and rich knowledge graphs.

---

## Key Features

- **Accurate Extraction:** Combines native PDF bookmarks (TOC), font and style heuristics, and regex fallback methods to reliably extract document outlines.
- **Optimized for Performance:** Designed to process PDFs of up to 50 pages within 10 seconds on CPU, adhering to strict runtime constraints.
- **Clean, Modular, and Robust:** Built with clear modularity, extensive error handling, and human-readable JSON output.
- **Docker-Ready:** Supports containerized deployments with AMD64 compatibility ensuring reproducible results across environments.
- **Offline and Lightweight:** No external internet calls; uses only open-source Python libraries with a minimal footprint.
- **Multilingual-Agnostic:** Unicode-safe regex and font-based methods ensure broad language support.
- **Human & Machine Friendly Output:** Generates structured JSON with heading levels and page numbers compatible with downstream tasks.

---

## How It Works

DocStructureX uses a **multi-step method to guarantee maximum accuracy and fallback resilience**:

1. **Step 1: Table of Contents (TOC) Extraction**  
   Extracts built-in PDF outline bookmarks using PyMuPDF’s native document API. This is the fastest and most precise if available.

2. **Step 2: Heuristic Font-Style Analysis**  
   If no TOC found, analyzes all text spans retrieving size, style, and page location metadata to detect headings and title candidates.

3. **Step 3: Regex-Based Fallback Parsing**  
   If heuristics fail, runs optimized regex patterns on plaintext extracted from the PDF, capturing numbered or chapter-based headings.

4. **Time-Aware Runtime Control**  
   Each step monitors execution time to ensure the entire extraction completes under 10 seconds for compliance with contest rules.

5. **Output**  
   Produces JSON files listing the document “title” and a sequential “outline” array with heading level (`H1`, `H2`, `H3`), text, and page number.

---

## Architecture & Components

- **Core Extraction Engine**  
  Implemented in `round1a_implementation.py`, relying primarily on PyMuPDF for PDF parsing and heuristic analysis.

- **TOC Extraction Module**  
  Native API access for PDF bookmarks.

- **Heuristic Extractor**  
  Font size & style detection combined with regex heading classifiers.

- **Regex Fallback Module**  
  Pattern matching for numbered headings and key markers on the raw text.

- **Runtime Manager**  
  Global timer enforcer preventing overruns.

- **Input/Output Handlers**  
  Processes multiple PDFs from an `input/` folder and writes per-file JSON outlines into an `output/` directory.

- **Dockerfile**  
  Contains all dependency management with a slim Debian-based Python 3.10 image, guaranteeing consistent Linux AMD64 execution.

---

## Installation & Setup

### 1. Clone the Repository

```

git clone https://github.com/yourusername/DocStructureX.git
cd DocStructureX

```

### 2. Python Virtual Environment (Recommended)

Create and activate a Python 3.10+ virtual environment:

```

python -m venv venv
source venv/bin/activate   \# Linux/macOS
venv\Scripts\activate      \# Windows

```

### 3. Install Dependencies

```

pip install --upgrade pip
pip install -r requirements.txt

```

> **Note:** The requirements are explicitly pinned to tested versions for stability.

---

## Usage Guide

### 1. Place PDFs

Copy your input PDFs into the `input/` directory at project root.

### 2. Run Extraction

```

python round1a_implementation.py

```

This will process all `.pdf` files in `input/` and generate `.json` outline files in the `output/` folder.

### 3. Check Output

Each JSON file contains:

```

{
"title": "Document Title",
"outline": [
{"level": "H1", "text": "Introduction", "page": 1},
{"level": "H2", "text": "Background", "page": 2},
{"level": "H3", "text": "Motivation", "page": 3}
]
}

```

---

## Docker Integration

DocStructureX is fully containerized for portability and reproducibility.

### Build Docker Image

```

docker build --platform linux/amd64 -t docstructurex:latest .

```

### Run Container

```

docker run --rm \
-v \$(pwd)/input:/app/input \
-v \$(pwd)/output:/app/output \
--network none \
docstructurex:latest

```

- Input PDFs are read from `/app/input`.
- Outputs are saved to `/app/output`.
- No internet/network access at runtime, following hackathon constraints.

---

## Development & Contribution

- The code follows modular design to facilitate easy enhancements or integration.
- Contributions are welcome by pull request—please respect existing code style and runtime constraints.
- For issues or feature requests, open GitHub Issues.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Uses [PyMuPDF](https://github.com/pymupdf/PyMuPDF) for fast and efficient PDF processing.
- Inspired by solutions discussed in Adobe India Hackathon 2025 and the community’s collaborative knowledge.
- Thanks to open-source maintainers ensuring accessible, powerful PDF and text processing tools.

---

*Built by Akash Kumar (Aryan) – Backend Developer and PDF Enthusiast*  
*Good luck and happy extracting! 🚀*
