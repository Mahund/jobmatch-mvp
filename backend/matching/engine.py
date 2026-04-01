"""
Step 4: Matching engine.
Takes a user profile and scores all listings using hard filters + specialty signal.
Returns ranked matches and writes them to the matches table.
"""
from dataclasses import dataclass
from db.supabase_client import get_client


@dataclass
class Profile:
    user_id: str
    specialty: str
    years_experience: int
    region: str
    accepted_contracts: list[str]      # e.g. ["full-time", "part-time"]
    preferred_schedule: str | None
    min_salary: int | None
    licensure_held: list[str]          # e.g. ["Enfermera Universitaria", "RN"]


SPECIALTY_TIERS = {
    "exact": 1.0,
    "related": 0.6,
    "general": 0.3,
    "none": 0.0,
}

# Groups of specialties considered "related" to each other
SPECIALTY_GROUPS = [
    {"UCI", "UTI", "Cuidados Intensivos", "UPC"},
    {"Urgencias", "Emergencias", "Urgencia", "Prehospitalario"},
    {"Neonatología", "Pediatría", "UCIN"},
    {"Pabellón", "Anestesia", "Arsenalero", "Pabellón Quirúrgico"},
    {"Oncología", "Radioterapia", "Quimioterapia"},
    {"Domiciliaria", "Domiciliario", "Visitas Domiciliarias", "Cuidado Domiciliario"},
    {"Salud Ocupacional", "Higiene Industrial", "Medicina del Trabajo"},
    {"Médico Quirúrgico", "Hospitalización", "Cuidados Medios"},
    {"Diálisis", "Nefrología"},
    {"Maternidad", "Ginecología", "Obstétrica"},
    {"Coronaria", "Cardiología"},
]


def _specialty_tier(user_specialty: str, listing_specialty: str | None) -> str:
    if not listing_specialty:
        return "general"

    u = user_specialty.strip().lower()
    l = listing_specialty.strip().lower()

    if u == l:
        return "exact"

    for group in SPECIALTY_GROUPS:
        lower_group = {s.lower() for s in group}
        if u in lower_group and l in lower_group:
            return "related"

    return "general"


def _passes_hard_filters(listing: dict, profile: Profile) -> tuple[bool, str | None]:
    """Returns (passes, reason_if_failed)."""

    # Region filter
    if listing.get("region") and profile.region:
        if profile.region.lower() not in listing["region"].lower():
            return False, f"region mismatch: {listing['region']}"

    # Years of experience
    required = listing.get("years_experience", 0) or 0
    if profile.years_experience < required:
        return False, f"experience: {profile.years_experience} < {required} required"

    # Contract type
    if profile.accepted_contracts and listing.get("contract_type"):
        if listing["contract_type"] not in profile.accepted_contracts + ["unknown"]:
            return False, f"contract type: {listing['contract_type']} not in {profile.accepted_contracts}"

    return True, None


def _score(listing: dict, profile: Profile) -> tuple[float, str]:
    tier = _specialty_tier(profile.specialty, listing.get("specialty"))
    score = SPECIALTY_TIERS[tier]
    return round(score, 4), tier


def run_matching(profile: Profile, write_results: bool = True) -> list[dict]:
    """
    Score all listings against profile. Optionally writes to matches table.
    Returns list of match dicts sorted by score descending.
    """
    db = get_client()
    listings = db.table("listings").select("*").eq("extraction_status", "ok").execute().data

    matches = []
    for listing in listings:
        passes, reason = _passes_hard_filters(listing, profile)
        if not passes:
            continue

        score, tier = _score(listing, profile)
        matches.append({
            "listing_hash": listing["url_hash"],
            "user_id": profile.user_id,
            "score": score,
            "filter_passed": True,
            "specialty_tier": tier,
            "is_new": True,
            # for return value only (not written to DB):
            "_listing": listing,
        })

    matches.sort(key=lambda m: m["score"], reverse=True)

    if write_results and matches:
        rows = [{k: v for k, v in m.items() if not k.startswith("_")} for m in matches]
        db.table("matches").upsert(rows, on_conflict="listing_hash,user_id").execute()

    return matches


def rematch(user_id: str) -> list[dict]:
    """Re-run matching for a user, reading their profile from DB."""
    db = get_client()
    result = db.table("profiles").select("*").eq("user_id", user_id).limit(1).execute()
    if not result.data:
        raise ValueError(f"No profile found for user_id={user_id}")

    row = result.data[0]
    profile = Profile(
        user_id=user_id,
        specialty=row.get("specialty", ""),
        years_experience=row.get("years_experience", 0),
        region=row.get("region", ""),
        accepted_contracts=row.get("accepted_contracts") or [],
        preferred_schedule=row.get("preferred_schedule"),
        min_salary=row.get("min_salary"),
        licensure_held=row.get("licensure_held") or [],
    )
    return run_matching(profile)
