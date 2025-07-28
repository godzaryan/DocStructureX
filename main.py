#!/usr/bin/env python3

import os
import sys
import json
import fitz
import re
from statistics import mode
from pathlib import Path
import time

class DocStructureXExtractor:
    def __init__(self, max_runtime=10.0):
        self.max_runtime = max_runtime
        self.start_time = None

    def extract_outline(self, pdf_path):
        self.start_time = time.time()
        try:
            toc_result = self._extract_with_toc(pdf_path)
            if self._validate_result(toc_result):
                self._log_time("TOC extraction")
                return toc_result
            if self._time_left() > 5.0:
                heuristic_result = self._extract_with_pymupdf(pdf_path)
                if self._validate_result(heuristic_result):
                    self._log_time("Heuristic extraction")
                    return heuristic_result
            if self._time_left() > 1.0:
                fallback_result = self._extract_with_regex_fallback(pdf_path)
                if self._validate_result(fallback_result):
                    self._log_time("Regex fallback extraction")
                    return fallback_result
            print(f"[Warning] No valid outline extracted for {pdf_path}! Returning empty.")
            return {"title": "Untitled Document", "outline": []}
        except Exception as exc:
            print(f"[Error] Exception processing {pdf_path}: {exc}")
            return {"title": "Error in Processing", "outline": []}

    def _extract_with_toc(self, pdf_path):
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        if not toc:
            doc.close()
            return None
        outline = []
        for level, title, page in toc:
            title_clean = re.sub(r'\s+', ' ', title).strip(' .,;:')
            if not title_clean or len(title_clean) < 3 or len(title_clean) > 150:
                continue
            lvl = "H1" if level == 1 else "H2" if level == 2 else "H3"
            outline.append({
                "level": lvl,
                "text": title_clean,
                "page": page
            })
        doc.close()
        if not outline:
            return None
        document_title = outline[0]["text"]
        if len(document_title) > 100:
            document_title = "Untitled Document"
        return {"title": document_title, "outline": outline}

    def _extract_with_pymupdf(self, pdf_path):
        doc = fitz.open(pdf_path)
        all_blocks = []
        for page_num in range(min(50, len(doc))):
            page = doc[page_num]
            blocks = page.get_text("dict")
            for block in blocks.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text and len(text) > 2:
                                all_blocks.append({
                                    "text": text,
                                    "page": page_num + 1,
                                    "font_size": span["size"],
                                    "font_flags": span["flags"],
                                    "bbox": span["bbox"]
                                })
            if self._time_left() < 0.5:
                print(f"[Warning] Time limit approaching during text extraction on page {page_num+1}")
                break
        doc.close()
        font_sizes = [b["font_size"] for b in all_blocks if b["font_size"] > 0]
        try:
            body_font = mode(font_sizes) if font_sizes else 12
        except:
            body_font = 12
        title = self._extract_title(all_blocks, body_font)
        headings = self._extract_headings_multilayer(all_blocks, body_font)
        return {"title": title, "outline": headings}

    def _extract_title(self, blocks, body_font_size):
        first_pages = [b for b in blocks if b["page"] <= 3]
        candidates = [b for b in first_pages if (b["font_size"] > body_font_size + 2 and 5 < len(b["text"]) < 200)]
        if candidates:
            candidates.sort(key=lambda x: (x["page"], x["bbox"][1]))
            return candidates[0]["text"]
        for b in first_pages:
            if len(b["text"]) > 10:
                return b["text"]
        return "Untitled Document"

    def _extract_headings_multilayer(self, blocks, body_font_size):
        headings = []
        seen = set()
        for block in blocks:
            text = block["text"].strip()
            if text in seen or len(text) < 3 or len(text) > 150 or self._is_artifact(text):
                continue
            level = self._heading_level(block, body_font_size)
            if level:
                headings.append({
                    "level": level,
                    "text": text,
                    "page": block["page"]
                })
                seen.add(text)
            if self._time_left() < 0.2:
                print("[Warning] Early stopping heading extraction due to time")
                break
        headings.sort(key=lambda x: (x["page"], x["text"]))
        return self._clean_headings(headings)

    def _heading_level(self, block, body_font_size):
        text = block["text"]
        size_diff = block["font_size"] - body_font_size
        is_bold = bool(block["font_flags"] & 2**4)
        numbered = re.match(r'^(\d+\.?\s+|\d+\.\d+\.?\s+|[IVXLC]+\.?\s+)', text)
        chapter = re.match(r'^(Chapter|Section|Part)\s+\d+', text, re.IGNORECASE)
        if size_diff >= 6:
            return "H1"
        if size_diff >= 4 or (size_diff >= 2 and is_bold):
            return "H2" if size_diff >= 4 else "H3"
        if is_bold and (numbered or chapter):
            return "H2"
        if numbered and size_diff >= 1:
            return "H3"
        if re.match(r'^\d+\.\s+[A-Z]', text):
            return "H2"
        if re.match(r'^\d+\.\d+\s+[A-Z]', text):
            return "H3"
        return None

    def _is_artifact(self, text):
        if re.match(r'^\d+$', text) or re.match(r'^Page \d+', text, re.IGNORECASE):
            return True
        if any(artifact in text.lower() for artifact in ['copyright', 'all rights reserved', 'page', 'table of contents']):
            return True
        if re.search(r'(http|www\.|@)', text):
            return True
        return False

    def _clean_headings(self, headings):
        cleaned = []
        seen = set()
        for h in headings:
            text = re.sub(r'\s+', ' ', h["text"]).strip('.,;:')
            if text and text not in seen and len(text) >= 3:
                h["text"] = text
                cleaned.append(h)
                seen.add(text)
        return cleaned

    def _extract_with_regex_fallback(self, pdf_path):
        doc = fitz.open(pdf_path)
        all_text = ""
        for page_num in range(min(50, len(doc))):
            page = doc[page_num]
            all_text += f"[PAGE_{page_num + 1}]" + page.get_text()
        doc.close()
        headings = []
        for m in re.finditer(r'\[PAGE_(\d+)\].*?(\d+\.\d*\s+[A-Z][^\n]{5,80})', all_text, re.MULTILINE):
            page_num = int(m.group(1))
            text = m.group(2).strip()
            level = "H3" if text.count('.') > 1 else "H2"
            headings.append({"level": level, "text": text, "page": page_num})
        for m in re.finditer(r'\[PAGE_(\d+)\].*?((Chapter|Section)\s+\d+[^\n]{0,50})', all_text, re.IGNORECASE | re.MULTILINE):
            page_num = int(m.group(1))
            text = m.group(2).strip()
            headings.append({"level": "H1", "text": text, "page": page_num})
        title_match = re.search(r'\[PAGE_1\].*?([A-Z][^\n]{10,100})', all_text)
        title = title_match.group(1).strip() if title_match else "Untitled Document"
        return {"title": title, "outline": headings[:20]}

    def _validate_result(self, result):
        if not result or not isinstance(result, dict):
            return False
        if "outline" not in result or not isinstance(result["outline"], list):
            return False
        count = len(result["outline"])
        return 1 <= count <= 100

    def _time_left(self):
        elapsed = time.time() - self.start_time if self.start_time else 0
        return self.max_runtime - elapsed

    def _log_time(self, step_name):
        elapsed = time.time() - self.start_time
        print(f"[Info] {step_name} completed in {elapsed:.2f} seconds (max allowed: {self.max_runtime}s)")

def process_directory(input_dir, output_dir):
    extractor = DocStructureXExtractor()
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    for pdf_file in sorted(input_path.glob("*.pdf")):
        print(f"[Process] Processing: {pdf_file.name}")
        result = extractor.extract_outline(str(pdf_file))
        output_file = output_path / f"{pdf_file.stem}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[Process] Saved output: {output_file}")

if __name__ == "__main__":
    input_dir = "input"
    output_dir = "output"
    if not os.path.exists(input_dir):
        print(f"[Error] Input directory '{input_dir}' not found!")
        sys.exit(1)
    process_directory(input_dir, output_dir)
    print("[Done] Processing complete!")
