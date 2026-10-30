from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
import re
import json
from pathlib import Path
from app.db import get_db
from app.dependencies import require_admin
from app.models import Destination, Event, User
from app.schemas import DestinationCreate, DestinationOut, DestinationUpdate
from app.services.recommender import haversine_km

router = APIRouter(prefix="/api", tags=["destinations"])
admin_router = APIRouter(prefix="/api/admin", tags=["administration"])

_LATIN_TO_CYRILLIC = str.maketrans({
    "a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "j": "ж", "z": "з", "i": "и", "y": "й", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "r": "р", "s": "с", "t": "т", "u": "у", "f": "ф", "h": "х", "c": "ц", "q": "ч", "w": "ш", "x": "ъ"
})
_CYRILLIC_TO_LATIN = str.maketrans({
    "а":"a", "б":"b", "в":"v", "г":"g", "д":"d", "е":"e", "ж":"zh", "з":"z", "и":"i", "й":"y", "к":"k", "л":"l", "м":"m", "н":"n", "о":"o", "п":"p", "р":"r", "с":"s", "т":"t", "у":"u", "ф":"f", "х":"h", "ц":"ts", "ч":"ch", "ш":"sh", "щ":"sht", "ъ":"a", "ь":"y", "ю":"yu", "я":"ya"
})
_SEARCH_ALIASES = {"history": "история", "nature": "природа", "museum": "музей", "culture": "култура", "wine": "вино", "food": "храна", "sofia": "софия", "plovdiv": "пловдив", "rila": "рила", "veliko tarnovo": "велико търново"}
_PROVINCE_CODES = {"Благоевград": "BLG", "Бургас": "BGS", "Варна": "VAR", "Велико Търново": "VTR", "Видин": "VID", "Враца": "VRC", "Габрово": "GAB", "Добрич": "DOB", "Кърджали": "KRZ", "Кюстендил": "KNL", "Ловеч": "LOV", "Монтана": "MON", "Пазарджик": "PAZ", "Перник": "PER", "Плевен": "PVN", "Пловдив": "PDV", "Разград": "RAZ", "Русе": "RSE", "Силистра": "SLS", "Сливен": "SLV", "Смолян": "SML", "София-град": "SOF", "София област": "SFO", "Стара Загора": "SZR", "Търговище": "TGV", "Хасково": "HKV", "Шумен": "SHU", "Ямбол": "JAM"}
_GEOJSON_PATH = Path(__file__).resolve().parents[2] / "static2" / "bulgaria.geojson"
try:
    _PROVINCE_FEATURES = {feature.get("properties", {}).get("nuts3"): feature for feature in json.loads(_GEOJSON_PATH.read_text(encoding="utf-8")).get("features", [])}
except (OSError, json.JSONDecodeError):
    _PROVINCE_FEATURES = {}


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    for index, (x2, y2) in enumerate(ring):
        x1, y1 = ring[index - 1]
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses and longitude < (x2 - x1) * (latitude - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _point_in_province(longitude: float, latitude: float, province: str) -> bool:
    feature = _PROVINCE_FEATURES.get(_PROVINCE_CODES.get(province))
    if not feature or not feature.get("geometry"):
        return False
    geometry = feature["geometry"]
    polygons = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        polygons = [polygons]
    return any(_point_in_ring(longitude, latitude, polygon[0]) and not any(_point_in_ring(longitude, latitude, hole) for hole in polygon[1:]) for polygon in polygons)

def _search_terms(value: str) -> set[str]:
    value = re.sub(r"\s+", " ", value.casefold().strip())
    terms = {value}
    if value in _SEARCH_ALIASES:
        terms.add(_SEARCH_ALIASES[value])
    if re.fullmatch(r"[a-z\s-]+", value):
        terms.add(value.translate(_LATIN_TO_CYRILLIC))
    else:
        terms.add(value.translate(_CYRILLIC_TO_LATIN))
    return terms


@router.get("/destinations", response_model=list[DestinationOut])
def list_destinations(
    q: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=80),
    province: str | None = Query(default=None, max_length=80),
    region: str | None = Query(default=None, max_length=120),
    latitude: float | None = Query(default=None, ge=41, le=44.3),
    longitude: float | None = Query(default=None, ge=22.3, le=28.7),
    radius_km: float | None = Query(default=None, gt=0, le=1000),
    verified_only: bool = False,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude and longitude must be supplied together")
    query = db.query(Destination)
    if q:
        terms = _search_terms(q)
        conditions = []
        for term_value in terms:
            term = f"%{term_value}%"
            conditions.extend((Destination.name.ilike(term), Destination.description.ilike(term), Destination.historical_context.ilike(term), Destination.region.ilike(term)))
        query = query.filter(or_(*conditions))
    if region:
        query = query.filter(Destination.region.ilike(f"%{region.strip()}%"))
    if verified_only:
        query = query.filter(Destination.verification_status == "verified")
    results = query.order_by(Destination.name).all()
    if category:
        cat = category.casefold().strip()
        results = [d for d in results if any(cat in str(x).casefold() for x in (d.categories or []) + (d.tags or []))]
    if province:
        results = [d for d in results if _point_in_province(d.longitude, d.latitude, province.strip())]
    if radius_km is not None and latitude is not None and longitude is not None:
        results = [d for d in results if haversine_km(latitude, longitude, d.latitude, d.longitude) <= radius_km]
    return results[offset:offset + limit]


@router.get("/destinations/{destination_id}", response_model=DestinationOut)
def destination_details(destination_id: int, db: Session = Depends(get_db)):
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    return destination


@router.get("/destinations/by-slug/{slug}", response_model=DestinationOut)
def destination_by_slug(slug: str, db: Session = Depends(get_db)):
    destination = db.query(Destination).filter_by(slug=slug).first()
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    return destination


@router.get("/events")
def list_events(
    q: str | None = Query(default=None, max_length=160),
    region: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if q:
        query = query.filter(or_(Event.name.ilike(f"%{q}%"), Event.description.ilike(f"%{q}%")))
    events = query.order_by(Event.start_date.asc().nullslast()).limit(100).all()
    if region:
        events = [event for event in events if event.destination and event.destination.region and region.casefold() in event.destination.region.casefold()]
    return [{"id": e.id, "name": e.name, "description": e.description, "destination_id": e.destination_id, "start_date": e.start_date, "end_date": e.end_date, "source_url": e.source_url, "verification_status": e.verification_status} for e in events]


@admin_router.post("/destinations", response_model=DestinationOut, status_code=201)
def create_destination(payload: DestinationCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Destination).filter_by(slug=payload.slug).first():
        raise HTTPException(status_code=409, detail="A destination with this slug already exists")
    destination = Destination(**payload.model_dump())
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return destination


@admin_router.patch("/destinations/{destination_id}", response_model=DestinationOut)
def update_destination(destination_id: int, payload: DestinationUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    destination = db.get(Destination, destination_id)
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(destination, key, value)
    db.commit()
    db.refresh(destination)
    return destination
