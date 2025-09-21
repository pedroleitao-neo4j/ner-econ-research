import os
import csv
import argparse
import re
from tqdm import tqdm
import pymupdf

import spacy


class PDFParser:
    def __init__(
        self,
        pdf_dir: str,
        output_csv: str,
        min_chars: int = 160,
        max_chars: int = 800,
        max_sents: int = 5,
        min_words: int = 5,
    ):
        self.pdf_dir = pdf_dir
        self.output_csv = output_csv
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.max_sents = max_sents
        self.min_words = min_words

        # Build a lean spaCy pipeline focused on sentence boundaries only
        self.nlp = spacy.blank("en")
        if "sentencizer" not in self.nlp.pipe_names:
            self.nlp.add_pipe("sentencizer")

    def _normalize_ws(self, text: str) -> str:
        # collapse whitespace, keep single spaces, drop stray hyphen+space artifacts
        text = re.sub(r"\s+", " ", text.strip())
        # fix spaces before punctuation
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        return text

    def is_heading(self, block_text: str) -> bool:
        """
        Heuristic to determine if a text block is likely a heading.
        """
        t = block_text.strip()

        # Patterns like "Box 1", "Annex 1:", "Figure 1", "Figure A", "Chart 1"
        if re.match(r"^(Box|Annex|Figure|Chart)\s+(\d+|[A-Z])", t, re.IGNORECASE):
            return True

        # Starts with a number (e.g., "1. Introduction")
        if t and t[0].isdigit():
            # common section patterns: 1, 1., 1.1, 1.1.1, etc.
            if re.match(r"^\d+([.)]|\.\d+)*\s+\S", t):
                return True

        # Short lines without terminal punctuation
        if len(t.split()) < 8 and not t.endswith((".", ":", ";", "?", "!")):
            return True

        # High ratio of Title/UPPER words and short overall length
        doc = self.nlp.make_doc(t)  # faster than full nlp
        tokens = [tok for tok in doc if tok.is_alpha]
        if len(doc) < 10 and tokens:
            uppish = sum(1 for tok in tokens if tok.text.isupper() or tok.text.istitle())
            if uppish / max(1, len(tokens)) > 0.7:
                return True

        return False

    def _chunk_sentences(self, text: str):
        """
        Split text into sentence-based chunks using spaCy, then pack sentences
        into chunks constrained by min_chars, max_chars, max_sents.
        """
        # Early exit for very small text
        cleaned = self._normalize_ws(text)
        if not cleaned or len(cleaned.split()) < self.min_words:
            return []

        doc = self.nlp(cleaned)
        chunks = []
        buf = []
        buf_chars = 0
        buf_sents = 0

        def flush(force=False):
            nonlocal buf, buf_chars, buf_sents
            if not buf:
                return
            candidate = " ".join(buf).strip()
            # If forced flush or meets minimum, emit
            if force or len(candidate) >= self.min_chars or buf_sents >= self.max_sents:
                chunks.append(candidate)
                buf = []
                buf_chars = 0
                buf_sents = 0

        for sent in doc.sents:
            s = sent.text.strip()
            if not s:
                continue

            # If adding this sentence would exceed limits, flush first
            if (
                (buf_chars + len(s) + 1 > self.max_chars)
                or (buf_sents + 1 > self.max_sents)
            ):
                flush(force=True)

            buf.append(s)
            buf_chars += len(s) + 1
            buf_sents += 1

        # Final flush: if the remainder is too small, try to merge it back
        if buf:
            candidate = " ".join(buf).strip()
            if chunks and len(candidate) < self.min_chars:
                # merge remainder into previous if it doesn't break max_chars too hard
                prev = chunks.pop()
                merged = f"{prev} {candidate}"
                if len(merged) <= self.max_chars * 1.5:  # allow slight overflow
                    chunks.append(merged)
                else:
                    chunks.append(prev)
                    chunks.append(candidate)
            else:
                chunks.append(candidate)

        # Drop any tiny fragments that escaped earlier checks
        chunks = [c for c in chunks if len(c.split()) >= self.min_words]
        return chunks

    def parse_pdfs(self):
        headers = [
            "file",
            "page",
            "chunk_ix",
            "title",
            "author",
            "modDate",
            "creationDate",
            "subject",
            "textBlock",
        ]
        os.makedirs(os.path.dirname(self.output_csv) or ".", exist_ok=True)

        pdf_files = [f for f in os.listdir(self.pdf_dir) if f.lower().endswith(".pdf")]
        pdf_files.sort()

        with open(self.output_csv, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for filename in tqdm(pdf_files, desc="Parsing PDFs"):
                filepath = os.path.join(self.pdf_dir, filename)
                try:
                    doc = pymupdf.open(filepath)
                    metadata = getattr(doc, "metadata", {}) or {}

                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)

                        # Use block-level extraction; preserve order by y, x
                        # block tuple: (x0, y0, x1, y1, "text", block_no, block_type, ...)
                        blocks = page.get_text("blocks")
                        blocks.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))

                        # Filter to text blocks and pre-clean
                        candidate_texts = []
                        for blk in blocks:
                            if len(blk) < 5:
                                continue
                            text = blk[4]
                            if not text:
                                continue
                            # Don't replace newlines here, but join blocks with spaces later.
                            # Sentences can be broken by newlines that pymupdf preserves.
                            # Let's join blocks and then normalize whitespace.
                            candidate_texts.append(text)

                        # Join all candidate texts from the page into one string
                        full_page_text = " ".join(candidate_texts)

                        # Process the full page text with spaCy to get sentence chunks
                        chunks = self._chunk_sentences(full_page_text)

                        for chunk_ix, ch in enumerate(chunks):
                            writer.writerow(
                                {
                                    "file": filename,
                                    "page": page_num + 1,
                                    "chunk_ix": chunk_ix,
                                    "title": metadata.get("title", ""),
                                    "author": metadata.get("author", ""),
                                    "modDate": metadata.get("modDate", ""),
                                    "creationDate": metadata.get("creationDate", ""),
                                    "subject": metadata.get("subject", ""),
                                    "textBlock": ch,
                                }
                            )

                    doc.close()
                except Exception as e:
                    print(f"Could not process {filename}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Parse PDFs from a directory, sentence-chunk with spaCy, and save to a CSV."
    )
    parser.add_argument("--pdf_dir", type=str, required=True, help="Directory containing PDF files.")
    parser.add_argument(
        "--output_csv", type=str, default="pdf_text_blocks.csv", help="Path to the output CSV file."
    )
    parser.add_argument("--min_chars", type=int, default=160, help="Minimum characters per chunk.")
    parser.add_argument("--max_chars", type=int, default=500, help="Maximum characters per chunk.")
    parser.add_argument("--max_sents", type=int, default=5, help="Maximum sentences per chunk.")
    parser.add_argument("--min_words", type=int, default=5, help="Minimum words per chunk.")

    args = parser.parse_args()

    pdf_parser = PDFParser(
        args.pdf_dir,
        args.output_csv,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        max_sents=args.max_sents,
        min_words=args.min_words,
    )
    pdf_parser.parse_pdfs()
    print(f"Processing complete. Output saved to {args.output_csv}")


if __name__ == "__main__":
    main()
