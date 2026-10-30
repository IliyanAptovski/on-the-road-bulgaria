# on-the-road-backend-frontend-
This is the demo of the project.

Start the development server with:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/ in a browser.

uvicorn app.main:app --host 127.0.0.1 --port 8001
Open http://127.0.0.1:8001/ in a browser.

## Province filter

The Explore toolbar includes an област selector. It filters destinations by the existing `region` field and automatically recalculates the map viewport around the selected province's destinations.

## Folder-based historical archive

Editors can place PDFs in `app/data/archive/pdfs/` and rebuild the searchable JSON index:

```bash
python scripts/build_archive.py
```

The script extracts text with PyMuPDF and writes one JSON record per PDF to `app/data/archive/index/`. Optional metadata can be added beside a PDF using the same filename with a `.json` extension, for example `book.json` beside `book.pdf`:

```json
{"title":"История на селото", "author":"Иван Иванов", "publication_year":1928, "description":"Кратко описание на източника", "copyright_status":"public_domain"}
```

Archive search combines these folder records with the existing reviewed OCR records. Folder results show a short explanation and passage, and the `Отвори PDF` button opens the original PDF in a modal viewer.
