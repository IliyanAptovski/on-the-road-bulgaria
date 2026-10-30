"""Build searchable JSON metadata from PDFs placed in app/data/archive/pdfs."""
from pathlib import Path
import json
import fitz

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "app" / "data" / "archive" / "pdfs"
INDEX_DIR = ROOT / "app" / "data" / "archive" / "index"


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        sidecar_path = pdf_path.with_suffix(".json")
        metadata = json.loads(sidecar_path.read_text(encoding="utf-8")) if sidecar_path.exists() else {}
        with fitz.open(pdf_path) as document:
            text = "\n".join(page.get_text("text") for page in document).strip()
        record = {
            "title": metadata.get("title") or pdf_path.stem.replace("_", " "),
            "author": metadata.get("author"),
            "publication_year": metadata.get("publication_year"),
            "description": metadata.get("description") or text[:240],
            "copyright_status": metadata.get("copyright_status", "unknown"),
            "bibliographic_reference": metadata.get("bibliographic_reference"),
            "pdf_filename": pdf_path.name,
            "page_number": 1,
            "text": text,
        }
        (INDEX_DIR / f"{pdf_path.stem}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        count += 1
    print(f"Indexed {count} PDF(s) from {PDF_DIR}")


if __name__ == "__main__":
    main()
