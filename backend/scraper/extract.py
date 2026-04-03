"""
Step 3: Claude extraction pipeline.
Downloads raw HTML from Supabase Storage, extracts structured fields via Claude,
and writes to the listings table.
"""
import json
import os
from bs4 import BeautifulSoup
import anthropic

EXTRACT_TOOL = {
    "name": "save_listing",
    "description": "Save structured data extracted from a nursing job listing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "city": {"type": "string"},
            "region": {"type": "string"},
            "contract_type": {
                "type": "string",
                "enum": ["full-time", "part-time", "per diem", "contract", "temporary", "unknown"]
            },
            "schedule": {"type": "string"},
            "salary_raw": {"type": "string"},
            "min_education": {"type": "string"},
            "years_experience": {"type": "integer"},
            "specialty": {"type": "string"},
            "licensure": {"type": "array", "items": {"type": "string"}},
            "responsibilities": {"type": "array", "items": {"type": "string"}},
            "ehr_software": {"type": "array", "items": {"type": "string"}},
            "modality": {
                "type": "string",
                "enum": ["presencial", "remoto", "híbrido", "domiciliario", "unknown"]
            },
            "seniority": {
                "type": "string",
                "enum": ["junior", "mid", "senior", "unknown"]
            },
            "summary": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "published_date": {
                "type": "string",
                "description": (
                    "Publication date in ISO 8601 format (YYYY-MM-DD). "
                    "Convert relative phrases like 'Publicado hace 3 días' to an absolute date "
                    "based on today's date. Return null if no publication date is found."
                )
            }
        },
        "required": [
            "title", "company", "city", "region", "contract_type",
            "years_experience", "specialty", "licensure", "responsibilities",
            "ehr_software", "modality", "seniority", "summary", "confidence"
        ]
    }
}

SYSTEM_PROMPT = (
    "Extract structured fields from a Chilean nursing job listing. "
    "Only state what is explicitly written; use null or [] for missing fields. "
    "Text in Spanish except enum values. Max 6 responsibilities. "
    "For published_date, convert relative phrases like 'hace 3 días' to YYYY-MM-DD using today's date. "
    "Return null for published_date if no publication date is present."
)


def _soup_to_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "meta", "link"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:3000]


def html_to_text(html: str) -> str:
    """Strip HTML to clean readable text for the LLM."""
    soup = BeautifulSoup(html, "lxml")
    return _soup_to_text(soup)


_REQUEST_PARAMS = {
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 512,
    "system": SYSTEM_PROMPT,
    "tools": [EXTRACT_TOOL],
    "tool_choice": {"type": "tool", "name": "save_listing"},
}


def _get_batches_api(client):
    """Return the batches API handle for SDK variants.

    Newer SDKs expose `client.messages.batches`, while older releases may
    expose `client.beta.messages.batches`.
    """
    messages = getattr(client, "messages", None)
    if messages is not None and hasattr(messages, "batches"):
        return messages.batches

    beta = getattr(client, "beta", None)
    beta_messages = getattr(beta, "messages", None) if beta is not None else None
    if beta_messages is not None and hasattr(beta_messages, "batches"):
        return beta_messages.batches

    raise RuntimeError(
        "Installed anthropic SDK does not support Message Batches. "
        "Upgrade anthropic (recommended >=0.39.0)."
    )


def build_batch_request_from_soup(custom_id: str, soup: BeautifulSoup) -> dict:
    """Build one batch request entry reusing an already-parsed BeautifulSoup object.

    Note: the soup is mutated (tags decomposed) by this call and should not be reused afterward.
    """
    text = _soup_to_text(soup)
    return {
        "custom_id": custom_id,
        "params": {
            **_REQUEST_PARAMS,
            "messages": [{"role": "user", "content": f"Extract the structured data from this job listing:\n\n{text}"}],
        },
    }


def build_batch_request(custom_id: str, html: str) -> dict:
    """Build one batch request entry for a listing."""
    soup = BeautifulSoup(html, "lxml")
    return build_batch_request_from_soup(custom_id, soup)


def submit_batch(requests: list[dict]) -> str:
    """Submit a list of batch requests. Returns the batch ID."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    batches_api = _get_batches_api(client)
    batch = batches_api.create(requests=requests)
    return batch.id


def poll_batch(batch_id: str, poll_interval: int = 60) -> None:
    """Block until the batch reaches 'ended' status."""
    import time as _time
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    batches_api = _get_batches_api(client)
    while True:
        batch = batches_api.retrieve(batch_id)
        counts = batch.request_counts
        print(f"  Batch {batch_id}: {batch.processing_status} "
              f"(done={counts.succeeded + counts.errored + counts.expired + counts.canceled}, "
              f"processing={counts.processing})")
        if batch.processing_status == "ended":
            return
        _time.sleep(poll_interval)


def iter_batch_results(batch_id: str):
    """Yield (custom_id, fields_or_None) for each result in the batch."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    batches_api = _get_batches_api(client)
    for result in batches_api.results(batch_id):
        if result.result.type != "succeeded":
            yield result.custom_id, None
            continue
        for block in result.result.message.content:
            if block.type == "tool_use" and block.name == "save_listing":
                yield result.custom_id, block.input
                break
        else:
            yield result.custom_id, None
