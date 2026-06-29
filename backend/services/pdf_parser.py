"""
Claura — pdf_parser.py
Extracts text from PDF and chunks it into individual clauses
using NEC4/JCT-aware splitting logic.
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

# Clause number patterns common in NEC4 and JCT
CLAUSE_PATTERNS = [
    r"^\d+\.\d+(\.\d+)?\s",           # 1.1, 2.3.1
    r"^Clause\s+\d+",                  # Clause 14
    r"^(SECTION|PART|SCHEDULE)\s+\d+", # SECTION 6
    r"^[A-Z][A-Z\s]{4,}\n",           # ALL CAPS HEADINGS
    r"^Z\d+\s",                        # Z1, Z2 — NEC4 Z clauses
    r"^X\d+\s",                        # X1, X18 — NEC4 X clauses
]

COMBINED_PATTERN = re.compile(
    "|".join(f"({p})" for p in CLAUSE_PATTERNS),
    re.MULTILINE
)

MIN_CLAUSE_LENGTH = 80    # characters — skip very short fragments
MAX_CLAUSE_LENGTH = 1200  # characters — truncate very long clauses


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc  = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        logger.info("Extracted %d characters from PDF", len(text))
        return text
    except ImportError:
        logger.error("PyMuPDF not installed. Install with: pip install pymupdf")
        raise
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise


def chunk_into_clauses(text: str) -> List[str]:
    """
    Split contract text into individual clause chunks.
    Uses NEC4/JCT-aware patterns to find clause boundaries.
    """
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Find clause boundaries
    boundaries = [0]
    for match in COMBINED_PATTERN.finditer(text):
        boundaries.append(match.start())
    boundaries.append(len(text))

    chunks = []
    for i in range(len(boundaries) - 1):
        chunk = text[boundaries[i]:boundaries[i+1]].strip()

        # Skip too short
        if len(chunk) < MIN_CLAUSE_LENGTH:
            continue

        # Truncate too long
        if len(chunk) > MAX_CLAUSE_LENGTH:
            chunk = chunk[:MAX_CLAUSE_LENGTH]

        chunks.append(chunk)

    # If no clause boundaries found — fall back to paragraph splitting
    if not chunks:
        logger.warning("No clause patterns found — falling back to paragraph split")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = [
            p[:MAX_CLAUSE_LENGTH]
            for p in paragraphs
            if len(p) >= MIN_CLAUSE_LENGTH
        ]

    logger.info("Chunked into %d clauses", len(chunks))
    return chunks


def parse_contract(file_bytes: bytes) -> List[str]:
    """
    Full pipeline: PDF bytes → list of clause strings.
    Entry point called by the upload route.
    """
    text   = extract_text_from_pdf(file_bytes)
    chunks = chunk_into_clauses(text)
    return chunks
