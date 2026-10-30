"""Load destination JSON files and upsert them into the database."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Destination
from app.schemas import DestinationCreate
from app.seed import grouped_information

BGN_PER_EUR = 1.95583


def read_destination_file(path: Path, locations_path: Path | None = None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("destinations", payload.get("locations", payload)) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("JSON must contain an array or a {\"destinations\": [...]} / {\"locations\": [...]} object")
    locations_path = locations_path or path.parent / "locations.json"
    if locations_path.exists() and not locations_path.is_file():
        raise ValueError(f"Locations path is not a file: {locations_path}")
    locations = read_locations_file(locations_path) if locations_path.is_file() else {}
    normalized: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for record in records:
        item = normalize_record(record, locations=locations)
        # The canonical id becomes the slug. If a source is accidentally
        # repeated, keep the first editorial record instead of importing it
        # twice and showing duplicate places in the UI.
        if item["slug"] in seen_slugs:
            continue
        seen_slugs.add(item["slug"])
        normalized.append(item)
    return normalized


def read_locations_file(path: Path) -> dict[str, dict[str, Any]]:
    """Read optional coordinates and Google Place IDs keyed by destination slug."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("locations", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("Locations JSON must contain an array or a {\"locations\": [...]} object")

    locations: dict[str, dict[str, Any]] = {}
    for location in records:
        if not isinstance(location, dict) or not location.get("slug"):
            raise ValueError("Every location must be an object with a slug")
        slug = str(location["slug"])
        if slug in locations:
            raise ValueError(f"Duplicate location slug: {slug}")
        locations[slug] = dict(location)
    return locations


def normalize_record(record: dict[str, Any], *, locations: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Every destination must be a JSON object")
    item = dict(record)
    coordinates = item.get("coordinates") if isinstance(item.get("coordinates"), dict) else {}
    categories = item.get("categories")
    constraints = item.get("constraints") if isinstance(item.get("constraints"), dict) else {}
    authentic_data = item.get("authentic_data") if isinstance(item.get("authentic_data"), dict) else {}

    # locationsData.json is the canonical editorial format. Flatten its nested
    # fields into the legacy database/API contract used by the rest of the app.
    item["latitude"] = item.get("latitude", coordinates.get("lat"))
    item["longitude"] = item.get("longitude", coordinates.get("lng"))
    item["description"] = item.get("description") or authentic_data.get("summary", "")
    item["historical_context"] = item.get("historical_context") or authentic_data.get("hidden_fact_archive")
    item["region"] = item.get("region") or item.get("municipality")
    item["estimated_visit_minutes"] = item.get(
        "estimated_visit_minutes",
        constraints.get("estimated_visit_time_minutes", 60),
    )
    if item.get("estimated_cost_eur") is None and constraints.get("entry_fee_bgn") is not None:
        item["estimated_cost_eur"] = round(float(constraints["entry_fee_bgn"]) / BGN_PER_EUR, 2)

    if isinstance(categories, dict):
        primary = categories.get("primary")
        category_values = [primary] if primary else []
        category_tags = categories.get("tags") or []
        item["categories"] = category_values
        item["tags"] = list(dict.fromkeys([*category_tags, *(item.get("tags") or [])]))

    # Keep canonical-only editorial fields available to future UI/API clients
    # without adding a migration for every new content attribute.
    item["information"] = {
        **(item.get("information") or {}),
        "canonical_id": item.get("id"),
        "settlement": item.get("settlement"),
        "canonical_categories": categories if isinstance(categories, dict) else None,
        "constraints": constraints,
        "authentic_data": authentic_data,
    }
    if "requires_guide" in constraints:
        item["information"]["requires_guide"] = bool(constraints["requires_guide"])
    if authentic_data.get("source"):
        item["information"]["source_note"] = authentic_data["source"]

    # Allow simple imports to use title instead of name and let the backend
    # generate the grouped information contract when it is omitted.
    item["name"] = item.get("name") or item.get("title")
    item["slug"] = make_slug(item.get("slug") or item.get("id") or item.get("name", ""))
    # Coordinates may live in the sibling locations.json file so content JSON
    # files can remain focused on editorial information.
    location = (locations or {}).get(item["slug"], {})
    for key in ("latitude", "longitude", "google_place_id"):
        if item.get(key) is None and location.get(key) is not None:
            item[key] = location[key]
    item.setdefault("categories", [])
    item.setdefault("tags", [])
    item.setdefault("description", "")
    item.setdefault("estimated_visit_minutes", 60)
    item.setdefault("verification_status", "unverified")
    item.setdefault("source_url", None)
    item.setdefault("estimated_cost_eur", None)
    generated_information = grouped_information(item)
    item["information"] = {**generated_information, **(item.get("information") or {})}
    try:
        return DestinationCreate.model_validate(item).model_dump()
    except ValueError as exc:
        if "latitude" in str(exc) or "longitude" in str(exc):
            raise ValueError(
                f"Destination '{item.get('slug')}' has no complete coordinates. "
                "Add it to locations.json or provide latitude and longitude in the destination JSON."
            ) from exc
        raise


_CYRILLIC_TO_LATIN = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sht", "ъ": "a", "ь": "y", "ю": "yu", "я": "ya",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L",
    "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S",
    "Т": "T", "У": "U", "Ф": "F", "Х": "H", "Ц": "Ts", "Ч": "Ch",
    "Ш": "Sh", "Щ": "Sht", "Ъ": "A", "Ь": "Y", "Ю": "Yu", "Я": "Ya",
})


def make_slug(value: str) -> str:
    text = (value or "").translate(_CYRILLIC_TO_LATIN).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "destination"


def upsert_destinations(db: Session, records: list[dict[str, Any]]) -> tuple[int, int]:
    created = updated = 0
    for record in records:
        existing = db.query(Destination).filter_by(slug=record["slug"]).first()
        if existing is None:
            db.add(Destination(**record))
            created += 1
            continue
        for key, value in record.items():
            setattr(existing, key, value)
        updated += 1
    db.commit()
    return created, updated
