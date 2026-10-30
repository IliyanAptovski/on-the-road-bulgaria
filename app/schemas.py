from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def validate_http_url(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must begin with http:// or https://")
    return value


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.split("@")[-1] or any(ch.isspace() for ch in value):
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(ORMModel):
    id: int
    email: str
    is_admin: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


class PreferenceUpdate(BaseModel):
    interests: list[str] = Field(default_factory=list, max_length=20)
    interest_weights: dict[str, float] = Field(default_factory=dict)
    preferred_transport: Literal["car", "walking", "train"] = "car"
    budget_eur: float | None = Field(default=None, ge=0, le=100000)
    trip_duration_minutes: int | None = Field(default=None, ge=30, le=10080)
    prefers_lesser_known: bool = False

    @field_validator("interest_weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= weight <= 1 for weight in value.values()):
            raise ValueError("Interest weights must be between 0 and 1")
        if len(value) > 20:
            raise ValueError("At most 20 interest weights are allowed")
        return value



_CYRILLIC_TO_LATIN = str.maketrans({
    "а": "a",  "б": "b",  "в": "v",  "г": "g",  "д": "d",  "е": "e",  "ж": "zh",
    "з": "z",  "и": "i",  "й": "y",  "к": "k",  "л": "l",  "м": "m",  "н": "n",
    "о": "o",  "п": "p",  "р": "r",  "с": "s",  "т": "t",  "у": "u",  "ф": "f",
    "х": "h",  "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "a",  "ь": "y",
    "ю": "yu", "я": "ya",
    "А": "A",  "Б": "B",  "В": "V",  "Г": "G",  "Д": "D",  "Е": "E",  "Ж": "Zh",
    "З": "Z",  "И": "I",  "Й": "Y",  "К": "K",  "Л": "L",  "М": "M",  "Н": "N",
    "О": "O",  "П": "P",  "Р": "R",  "С": "S",  "Т": "T",  "У": "U",  "Ф": "F",
    "Х": "H",  "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Sht", "Ъ": "A",  "Ь": "Y",
    "Ю": "Yu", "Я": "Ya",
})


def slugify(value: str) -> str:
    value = value.translate(_CYRILLIC_TO_LATIN).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "destination"

class DestinationCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=2, max_length=240)
    region: str | None = Field(default=None, max_length=120)
    municipality: str | None = Field(default=None, max_length=120)
    description: str = Field(default="", max_length=10000)
    historical_context: str | None = Field(default=None, max_length=10000)
    categories: list[str] = Field(default_factory=list, max_length=30)
    tags: list[str] = Field(default_factory=list, max_length=50)
    latitude: float = Field(ge=41.0, le=44.3)
    longitude: float = Field(ge=22.3, le=28.7)
    google_place_id: str | None = Field(default=None, max_length=256)
    estimated_visit_minutes: int = Field(default=60, ge=5, le=1440)
    estimated_cost_eur: float | None = Field(default=None, ge=0, le=100000)
    opening_hours: dict[str, Any] | None = None
    website: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=60)
    seasonal_months: list[int] | None = Field(default=None, max_length=12)
    verification_status: Literal["unverified", "reviewed", "verified", "conflicting"] = "unverified"
    source_url: str | None = Field(default=None, max_length=500)
    information: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def fill_slug_from_name(cls, data):
        if isinstance(data, dict) and not data.get("slug"):
            name = data.get("name") or ""
            data = {**data, "slug": slugify(name)}
        return data

    @field_validator("website", "source_url")
    @classmethod
    def validate_external_urls(cls, value: str | None) -> str | None:
        return validate_http_url(value)

    @field_validator("seasonal_months")
    @classmethod
    def validate_months(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(month < 1 or month > 12 for month in value):
            raise ValueError("Seasonal months must be between 1 and 12")
        return value


class DestinationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=240)
    region: str | None = None
    municipality: str | None = None
    description: str | None = Field(default=None, max_length=10000)
    historical_context: str | None = Field(default=None, max_length=10000)
    categories: list[str] | None = None
    tags: list[str] | None = None
    latitude: float | None = Field(default=None, ge=41.0, le=44.3)
    longitude: float | None = Field(default=None, ge=22.3, le=28.7)
    google_place_id: str | None = Field(default=None, max_length=256)
    estimated_visit_minutes: int | None = Field(default=None, ge=5, le=1440)
    estimated_cost_eur: float | None = Field(default=None, ge=0, le=100000)
    opening_hours: dict[str, Any] | None = None
    website: str | None = None
    phone: str | None = None
    seasonal_months: list[int] | None = None
    verification_status: Literal["unverified", "reviewed", "verified", "conflicting"] | None = None
    source_url: str | None = None
    information: dict[str, Any] | None = None

    @field_validator("website", "source_url")
    @classmethod
    def validate_external_urls(cls, value: str | None) -> str | None:
        return validate_http_url(value)


class DestinationOut(ORMModel):
    id: int
    slug: str
    name: str
    region: str | None
    municipality: str | None
    description: str
    historical_context: str | None
    categories: list[str]
    tags: list[str]
    latitude: float
    longitude: float
    google_place_id: str | None
    estimated_visit_minutes: int
    estimated_cost_eur: float | None
    opening_hours: dict[str, Any] | None
    website: str | None
    phone: str | None
    seasonal_months: list[int] | None
    verification_status: str
    source_url: str | None
    information: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def add_information_fallback(cls, value: Any) -> Any:
        info = getattr(value, "information", None) if not isinstance(value, dict) else value.get("information")
        if info:
            return value
        read = (lambda key, default=None: getattr(value, key, default)) if not isinstance(value, dict) else value.get
        categories = read("categories", []) or []
        tags = read("tags", []) or []
        terms = " ".join(str(x) for x in categories + tags).casefold()
        outdoor = any(term in terms for term in ("природа", "планина", "пещера", "hiking", "nature"))
        generated = {
            "summary": read("description", ""),
            "highlights": [read("historical_context")] if read("historical_context") else [],
            "good_for": ["природа и разходки"] if outdoor else ["история и култура"],
            "consider_if": ["Искаш да провериш актуалните условия преди посещение."],
            "practical": {"visit_minutes": read("estimated_visit_minutes", 60), "cost_eur": read("estimated_cost_eur"), "opening_hours": read("opening_hours"), "access": "Провери достъпа предварително."},
            "experience": {"terrain": "На открито" if outdoor else "Градска/закрита среда"},
            "decision": {"best_for": "Подходяща спирка според интересите ти", "difficulty": "Лесно"},
        }
        if isinstance(value, dict):
            return {**value, "information": generated}
        setattr(value, "information", generated)
        return value


class RecommendationRequest(BaseModel):
    interests: list[str] = Field(default_factory=list, max_length=20)
    interest_weights: dict[str, float] = Field(default_factory=dict)
    latitude: float | None = Field(default=None, ge=41.0, le=44.3)
    longitude: float | None = Field(default=None, ge=22.3, le=28.7)
    radius_km: float | None = Field(default=None, gt=0, le=1000)
    budget_eur: float | None = Field(default=None, ge=0, le=100000)
    travel_date: datetime | None = None
    prefers_lesser_known: bool = False
    include_unverified: bool = True
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class RecommendationItem(BaseModel):
    destination: DestinationOut
    score: float = Field(ge=0, le=1)
    reasons: list[str]


class PlannerRequest(BaseModel):
    start_latitude: float = Field(ge=41.0, le=44.3)
    start_longitude: float = Field(ge=22.3, le=28.7)
    available_time_minutes: int = Field(default=180, ge=30, le=1440)
    transport_mode: Literal["car", "walking", "train"] = "car"
    travel_date: datetime | None = None
    budget_eur: float | None = Field(default=None, ge=0, le=100000)
    interests: list[str] = Field(default_factory=list, max_length=20)
    interest_weights: dict[str, float] = Field(default_factory=dict)
    radius_km: float | None = Field(default=None, gt=0, le=1000)
    max_destinations: int = Field(default=4, ge=1, le=12)
    include_unverified: bool = True
    return_to_start: bool = False
    selected_destination_ids: list[int] = Field(default_factory=list, max_length=9)
    remember_interests: bool = False

    @field_validator("selected_destination_ids")
    @classmethod
    def validate_selected_destination_ids(cls, value: list[int]) -> list[int]:
        if any(destination_id <= 0 for destination_id in value):
            raise ValueError("Destination IDs must be positive integers")
        if len(set(value)) != len(value):
            raise ValueError("A destination may only be selected once")
        return value

    @field_validator("interest_weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= weight <= 1 for weight in value.values()):
            raise ValueError("Interest weights must be between 0 and 1")
        return value


class PlannedStop(BaseModel):
    order: int
    destination: DestinationOut
    distance_from_previous_km: float
    travel_minutes_from_previous: int
    visit_minutes: int
    estimated_cost_eur: float | None
    recommendation_score: float


class PlannerOut(BaseModel):
    transport_mode: str
    available_time_minutes: int
    estimated_total_minutes: int
    estimated_total_cost_eur: float | None
    total_route_distance_km: float
    returns_to_start: bool
    route_is_estimate: bool = True
    route_provider: str = "estimated_fallback"
    google_maps_url: str | None = None
    route_polyline: str | None = None
    warnings: list[str]
    stops: list[PlannedStop]


class ItineraryOut(ORMModel):
    id: int
    title: str
    request_parameters: dict
    destination_ids: list
    proposed_order: list
    estimated_total_minutes: int
    created_at: datetime


class SourceOut(ORMModel):
    id: int
    title: str
    author: str | None
    publication_year: int | None
    publisher: str | None
    edition: str | None
    language: str
    copyright_status: str
    bibliographic_reference: str | None
    source_url: str | None
    original_filename: str
    processing_status: str
    created_at: datetime


class SourcePageOut(ORMModel):
    id: int
    source_id: int
    page_number: int
    raw_ocr_text: str | None
    normalized_text: str | None
    ocr_engine: str | None
    ocr_engine_version: str | None
    ocr_language: str
    ocr_confidence: float | None
    processing_status: str
    review_status: str
    verification_status: str
    processing_error: str | None


class ReviewTextRequest(BaseModel):
    normalized_text: str = Field(min_length=1, max_length=100000)
    verification_status: Literal["unverified", "verified", "conflicting"] = "unverified"
    mark_reviewed: bool = True


class PageDestinationLinkRequest(BaseModel):
    destination_id: int
    excerpt: str | None = Field(default=None, max_length=2000)
    review_status: Literal["needs_review", "verified"] = "needs_review"


class SourceReferenceStatusUpdate(BaseModel):
    review_status: Literal["needs_review", "verified", "rejected"]


class SearchResult(BaseModel):
    source_id: int
    source_title: str
    author: str | None
    publication_year: int | None
    page_id: int
    page_number: int
    passage: str
    review_status: str
    verification_status: str
    copyright_status: str
    source_url: str | None = None
    bibliographic_reference: str | None = None
    description: str | None = None
    pdf_url: str | None = None
