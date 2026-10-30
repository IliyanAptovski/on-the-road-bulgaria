from pathlib import Path

from app.services.destination_import import normalize_record, read_destination_file


def test_normalize_canonical_location_record():
    record = normalize_record(
        {
            "id": "mountain_waterfall",
            "name": "Планински водопад",
            "municipality": "Лъки",
            "settlement": "с. Пример",
            "coordinates": {"lat": 41.9, "lng": 24.8},
            "categories": {"primary": "nature_adventure", "tags": ["waterfall"]},
            "constraints": {"estimated_visit_time_minutes": 90, "entry_fee_bgn": 0, "requires_guide": False},
            "authentic_data": {
                "summary": "Описание",
                "hidden_fact_archive": "Факт",
                "source": "Местен архив",
            },
        }
    )

    assert record["slug"] == "mountain-waterfall"
    assert record["latitude"] == 41.9
    assert record["longitude"] == 24.8
    assert record["description"] == "Описание"
    assert record["historical_context"] == "Факт"
    assert record["categories"] == ["nature_adventure"]
    assert record["tags"] == ["waterfall"]
    assert record["estimated_visit_minutes"] == 90
    assert record["estimated_cost_eur"] == 0
    assert record["information"]["settlement"] == "с. Пример"
    assert record["information"]["requires_guide"] is False
    assert record["information"]["source_note"] == "Местен архив"


def test_canonical_locations_file_is_read_as_destination_records():
    path = Path(__file__).parents[1] / "app" / "data" / "locationsData.json"
    records = read_destination_file(path)

    assert len(records) == 266
    assert all(record["slug"] for record in records)
    assert all(record["latitude"] and record["longitude"] for record in records)
