import os
import sys
import json
import time
import re
from statistics import mode
from pathlib import Path

import fitz
import numpy as np

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
                heuristic_result = self._extract_with_advanced_heuristics(pdf_path)
                if self._validate_result(heuristic_result):
                    self._log_time("Heuristic extraction")
                    return heuristic_result

            if self._time_left() > 1.0:
                fallback_result = self._extract_with_regex_fallback(pdf_path)
                if self._validate_result(fallback_result):
                    self._log_time("Regex fallback extraction")
                    return fallback_result

            return {"title": "Untitled Document", "outline": []}
        except Exception as exc:
            print(f"[Error] Exception processing {pdf_path}: {exc}")
            return {"title": "Error in Processing", "outline": []}

    def _extract_with_toc(self, pdf_path):
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        outline = []
        for level, title, page in toc:
            title_clean = re.sub(r'\s+', ' ', title).strip(' .,;:')
            if not title_clean or len(title_clean) < 3 or len(title_clean) > 150:
                continue
            lvl = "H1" if level == 1 else "H2" if level == 2 else "H3"
            outline.append({"level": lvl, "text": title_clean, "page": page})
        doc.close()
        if not outline:
            return None
        document_title = outline[0]["text"]
        if len(document_title) > 100:
            document_title = "Untitled Document"
        return {"title": document_title, "outline": outline}

    def _extract_with_advanced_heuristics(self, pdf_path):
        doc = fitz.open(pdf_path)
        block_list = []
        page_height = doc[0].rect.height if len(doc) else 842
        font_sizes = []
        font_scores = {}
        for page_num in range(min(50, len(doc))):
            if self._time_left() < 0.5:
                break
            page = doc[page_num]
            blocks = page.get_text("dict")
            for block in blocks.get("blocks", []):
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        txt = span["text"].strip()
                        fs = span["size"]
                        flags = span["flags"]
                        bbox = span["bbox"]
                        is_bold = bool(flags & 2**4)
                        if txt and 2 < len(txt) < 200 and not self._is_artifact(txt):
                            zone = self._block_zone(bbox, page_height)
                            confidence = self._heading_confidence(txt, fs, is_bold, zone)
                            block_list.append({
                                "text": txt, "page": page_num + 1, "font_size": fs, "is_bold": is_bold,
                                "y0": bbox[1], "zone": zone, "confidence": confidence
                            })
                            font_sizes.append(fs)
                            font_scores.setdefault(fs, 0)
                            font_scores[fs] += confidence
        doc.close()
        body_font_candidates = self._dominant_fonts(font_scores)
        headings = []
        seen = set()
        for blk in sorted(block_list, key=lambda b: (b["page"], b["y0"])):
            if blk["text"] in seen: continue
            lvl = self._heading_level(blk, body_font_candidates)
            if lvl:
                headings.append({"level": lvl, "text": blk["text"], "page": blk["page"]})
                seen.add(blk["text"])
            if self._time_left() < 0.2:
                break
        headings = self._clean_headings(headings)
        title_candidates = [b for b in block_list if b["page"] <= 3 and b["confidence"] >= 2.0 and b["zone"] == "body"]
        if title_candidates:
            title_candidates.sort(key=lambda x: (-x["font_size"], x["page"], x["y0"]))
            title = title_candidates[0]["text"]
        elif headings:
            title = headings[0]["text"]
        else:
            title = "Untitled Document"
        return {"title": title, "outline": headings}

    def _dominant_fonts(self, font_scores):
        if not font_scores: return [12]
        top = sorted(font_scores.items(), key=lambda kv: -kv[1])[:2]
        return [sz for sz, _ in top if sz >= 4]

    def _heading_confidence(self, text, fs, is_bold, zone):
        confidence = 0
        if fs > 18: confidence += 1.6
        if fs > 15: confidence += 1.0
        if is_bold: confidence += 0.8
        if zone == "header": confidence -= 0.8
        if zone == "footer": confidence -= 1.1
        if re.match(r"^(\d+\.|\d+\.\d+|[IVXLC]+\.)", text): confidence += 0.8
        if re.match(r"^[A-Z\s]{5,}$", text): confidence += 0.4
        if re.match(r"^(section|chapter|appendix)\s+\w+", text, re.I): confidence += 0.7
        if len(text.split()) <= 10: confidence += 0.3
        return confidence

    def _block_zone(self, bbox, page_height):
        if bbox[1] < 0.13 * page_height:
            return "header"
        if bbox[3] > 0.89 * page_height:
            return "footer"
        return "body"

    def _heading_level(self, blk, body_fonts):
        fs = blk["font_size"]
        text = blk["text"]
        is_bold = blk["is_bold"]
        if fs >= max(body_fonts, default=12) + 6:
            return "H1"
        if fs >= max(body_fonts, default=12) + 3:
            return "H2"
        if is_bold and fs >= min(body_fonts, default=10) + 1:
            return "H2"
        if re.match(r"^(\d+\.\d+\s+[A-Z])", text): return "H3"
        if is_bold or re.match(r"^[IVXLC]+\.?\s", text): return "H3"
        return None

    def _is_artifact(self, text):
        if re.match(r'^\d+$', text): return True
        if re.match(r'^\s*page \d+', text, re.I): return True
        artifacts = ['copyright', 'all rights reserved', 'page', 'doi:', 'table of contents', 'abstract', 'official use']
        return any(a in text.lower() for a in artifacts) or re.search(r'(http|www\.|@)', text)

    def _clean_headings(self, headings):
        unique = []
        seen = set()
        for h in headings:
            t = re.sub(r'\s+', ' ', h["text"]).strip('.,;:')
            if t and t not in seen and 2 < len(t) < 160:
                h2 = h.copy()
                h2["text"] = t
                unique.append(h2)
                seen.add(t)
        return unique

    def _extract_with_regex_fallback(self, pdf_path):
        doc = fitz.open(pdf_path)
        all_text = ''
        for page_num in range(min(50, len(doc))):
            page = doc[page_num]
            all_text += f"[PAGE_{page_num + 1}]{page.get_text()}"
        doc.close()
        headings = []
        for m in re.finditer(r'\[PAGE_(\d+)\].*?(\d+\.\d*\s+[^\n]{5,80})', all_text, re.MULTILINE):
            page_num = int(m.group(1))
            text = m.group(2).strip()
            level = "H3" if text.count('.') > 1 else "H2"
            headings.append({"level": level, "text": text, "page": page_num})
        for m in re.finditer(r'\[PAGE_(\d+)\].*?((Section|Chapter|Part)\s+\d+[^\n]{0,50})', all_text, re.I | re.MULTILINE):
            page_num = int(m.group(1))
            text = m.group(2).strip()
            headings.append({"level": "H1", "text": text, "page": page_num})
        title_match = re.search(r'\[PAGE_1\].*?([A-Z][^\n]{10,100})', all_text)
        title = title_match.group(1).strip() if title_match else "Untitled Document"
        return {"title": title, "outline": headings[:20]}

    def _validate_result(self, result):
        return (
            result and isinstance(result, dict)
            and "outline" in result
            and isinstance(result["outline"], list)
            and 1 <= len(result["outline"]) <= 100
        )

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
