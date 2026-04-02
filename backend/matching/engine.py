"""
Step 4: Matching engine.
Takes a user profile and scores all listings using hard filters + specialty signal.
Returns ranked matches and writes them to the matches table.
"""
from dataclasses import dataclass
import unicodedata
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
}

# Keyword groups: canonical group name → substrings to match in listing specialty (lowercase)
SPECIALTY_KEYWORD_GROUPS: dict[str, list[str]] = {
    "urgencias":        ["urgencia", "emergencia", "prehospital", "rescate", "ambulancia", "paramédic", "paramedic"],
    "uci":              ["uci", "uti", "paciente crítico", "paciente critico", "intensivo", "upc"],
    "neonatología":     ["neonato", "neonatolog", "ucin"],
    "pediatría":        ["pediatr"],
    "pabellón":         ["pabellón", "pabellon", "anestesia", "arsenal", "quirúrgic", "quirurgic"],
    "oncología":        ["oncolog", "quimioterapia", "radioterapia", "cáncer", "cancer"],
    "domiciliaria":     ["domicili"],
    "salud_ocupacional":["ocupacional", "higiene industrial"],
    "hospitalización":  ["hospitaliz", "médico quirúrgico", "medico quirurgico", "cuidados medios", "hmq"],
    "diálisis":         ["diálisis", "dialisis", "hemodiálisis", "hemodialisis"],
    "maternidad":       ["maternidad", "ginecolog", "obstétric", "obstetric"],
    "coronaria":        ["coronaria", "cardiolog", "hemodinam", "cateterismo"],
    "adulto_mayor":     ["adulto mayor", "larga estadía", "larga estadia", "larga estancia", "gerontolog"],
    "aps":              ["atención primaria", "atencion primaria", "cesfam", "salud familiar"],
}

# Groups considered clinically related (sharing skills/context)
RELATED_GROUP_PAIRS: set[frozenset] = {
    frozenset(["urgencias", "uci"]),
    frozenset(["urgencias", "pabellón"]),
    frozenset(["uci", "coronaria"]),
    frozenset(["uci", "neonatología"]),
    frozenset(["uci", "pabellón"]),
    frozenset(["oncología", "hospitalización"]),
    frozenset(["maternidad", "neonatología"]),
    frozenset(["domiciliaria", "adulto_mayor"]),
}


def _get_specialty_group(specialty: str) -> str | None:
    s = specialty.lower().strip()
    for group, keywords in SPECIALTY_KEYWORD_GROUPS.items():
        if any(kw in s for kw in keywords):
            return group
    return None


def _specialty_tier(user_specialty: str, listing_specialty: str | None) -> str:
    if not listing_specialty:
        return "general"

    u_group = _get_specialty_group(user_specialty)
    l_group = _get_specialty_group(listing_specialty)

    if u_group and l_group:
        if u_group == l_group:
            return "exact"
        if frozenset([u_group, l_group]) in RELATED_GROUP_PAIRS:
            return "related"

    return "general"


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def _is_enfermeria_role(title: str | None) -> bool:
    normalized_title = _normalize_text(title)
    if not normalized_title:
        return False

    if "enfermer" not in normalized_title:
        return False

    excluded_markers = [
        "tens",
        "tecnico",
        "tecnica",
        "auxiliar",
        "paramedic",
        "kinesiolog",
        "estudiante",
        "intern",
    ]
    return not any(marker in normalized_title for marker in excluded_markers)


def _passes_hard_filters(listing: dict, profile: Profile) -> tuple[bool, str | None]:
    """Returns (passes, reason_if_failed)."""

    # Enforce professional Enfermeria roles only.
    if not _is_enfermeria_role(listing.get("title")):
        return False, "non-enfermeria role"

    # Region filter
    if listing.get("region") and profile.region:
        if profile.region.lower() not in listing["region"].lower():
            return False, f"region mismatch: {listing['region']}"

    # Years of experience
    required = int(listing.get("years_experience") or 0)
    if profile.years_experience < required:
        return False, f"experience: {profile.years_experience} < {required} required"

    # Contract type — "unknown" and "contract" pass (extraction ambiguity; contract ≈ plazo fijo)
    PASSTHROUGH_CONTRACTS = {"unknown", "contract"}
    if profile.accepted_contracts and listing.get("contract_type"):
        if listing["contract_type"] not in set(profile.accepted_contracts) | PASSTHROUGH_CONTRACTS:
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

    if write_results:
        db.table("matches").delete().eq("user_id", profile.user_id).execute()

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
