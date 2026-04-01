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
    "description": "Save the structured data extracted from a nursing job listing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Exact job title"},
            "company": {"type": "string", "description": "Employer / clinic / hospital name"},
            "city": {"type": "string", "description": "City where the job is located"},
            "region": {"type": "string", "description": "Region/province (e.g. Región Metropolitana, Biobío)"},
            "contract_type": {
                "type": "string",
                "enum": ["full-time", "part-time", "per diem", "contract", "temporary", "unknown"],
                "description": "Employment contract type"
            },
            "schedule": {"type": "string", "description": "Work schedule details (e.g. turno noche, 3x2, diurno)"},
            "salary_raw": {"type": "string", "description": "Salary as stated in the listing, verbatim"},
            "min_education": {"type": "string", "description": "Minimum required education (e.g. Técnico en Enfermería, Enfermera Universitaria)"},
            "years_experience": {"type": "integer", "description": "Minimum years of experience required (0 if not stated)"},
            "specialty": {"type": "string", "description": "Nursing specialty or department (e.g. UCI, Neonatología, Urgencias, Salud Ocupacional, Domiciliaria)"},
            "licensure": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required certifications or licences (e.g. RN, TENS, matrícula SIS)"
            },
            "responsibilities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key responsibilities listed in the posting (max 6 bullet points)"
            },
            "ehr_software": {
                "type": "array",
                "items": {"type": "string"},
                "description": "EHR or clinical software mentioned (e.g. SIDRA, OMEGA, SAP)"
            },
            "modality": {
                "type": "string",
                "enum": ["presencial", "remoto", "híbrido", "domiciliario", "unknown"],
                "description": "Work modality"
            },
            "seniority": {
                "type": "string",
                "enum": ["junior", "mid", "senior", "unknown"],
                "description": "Seniority level inferred from listing"
            },
            "summary": {"type": "string", "description": "One-sentence plain-language summary of the role"},
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in extraction quality (0–1). Use <0.6 if listing is vague or incomplete."
            }
        },
        "required": [
            "title", "company", "city", "region", "contract_type",
            "years_experience", "specialty", "licensure", "responsibilities",
            "ehr_software", "modality", "seniority", "summary", "confidence"
        ]
    }
}

SYSTEM_PROMPT = """You are a clinical recruitment data extractor specializing in Chilean nursing jobs.
Extract structured information from the HTML of a job listing page.
Be precise: only state what is explicitly written. If a field is not mentioned, use null or an empty list.
All text output should be in Spanish (matching the listing language) except enum values.
"""


def html_to_text(html: str) -> str:
    """Strip HTML to clean readable text for the LLM."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "meta", "link"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Truncate to ~6000 chars to stay within token limits
    return text[:6000]


def extract_listing(html: str) -> dict | None:
    """
    Call Claude to extract structured fields from listing HTML.
    Returns a dict matching the listings table schema, or None on failure.
    Retries up to 3 times with backoff on rate limit errors.
    """
    import time as _time
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    text = html_to_text(html)

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "save_listing"},
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract the structured data from this job listing:\n\n{text}"
                    }
                ]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "save_listing":
                    return block.input
            return None
        except anthropic.RateLimitError:
            if attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"    Rate limit — waiting {wait}s before retry...")
                _time.sleep(wait)
            else:
                raise
