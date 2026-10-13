"""
Heuristic candidate-profile builder: section-header and keyword
matching over extracted resume text. Not an AI extraction — this is
what app/ai/providers/heuristic_provider.py wraps as the default (and
test-time) AI Gateway provider (extraction_method="heuristic_v1").
When AI_PROVIDER is configured to a real provider, AnthropicProvider
is used instead and this file isn't touched — see app/ai/gateway.py.
"""
import re

# Section headers we recognize, mapped to the CandidateProfile field
# they populate. Matched case-insensitively at the start of a line.
_SECTION_HEADERS: dict[str, tuple[str, ...]] = {
    "education": ("education", "academic background", "qualifications"),
    "projects": ("projects", "academic projects", "personal projects"),
    "internships": ("internship", "internships"),
    "experience": ("experience", "work experience", "professional experience"),
    "certifications": ("certifications", "certificates", "licenses"),
    "achievements": ("achievements", "awards", "accomplishments"),
    "skills": ("skills", "technical skills", "core competencies"),
}

# Small curated lists, intersected case-insensitively against the
# whole document. Not exhaustive by design — this is a placeholder.
_PROGRAMMING_LANGUAGES = (
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go", "Rust",
    "Kotlin", "Swift", "Ruby", "PHP", "Scala", "R", "MATLAB", "SQL",
)
_TECHNOLOGIES = (
    "React", "Angular", "Vue", "Next.js", "Node.js", "Django", "Flask", "FastAPI",
    "Spring", "Express", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker",
    "Kubernetes", "AWS", "GCP", "Azure", "TensorFlow", "PyTorch", "Git", "GraphQL",
    "REST", "Kafka", "Terraform",
)


def _find_section_lines(lines: list[str], header_variants: tuple[str, ...]) -> list[str]:
    """Returns the lines following any of header_variants, up to the
    next recognized section header or end of document."""
    all_header_words = {h for variants in _SECTION_HEADERS.values() for h in variants}

    start = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower().rstrip(":")
        if stripped in header_variants:
            start = i + 1
            break
    if start is None:
        return []

    collected = []
    for line in lines[start:]:
        stripped = line.strip().lower().rstrip(":")
        if stripped in all_header_words:
            break
        if line.strip():
            collected.append(line.strip())
    return collected


def build_candidate_profile(text: str) -> dict:
    lines = text.splitlines()

    profile = {
        field: _find_section_lines(lines, variants)
        for field, variants in _SECTION_HEADERS.items()
    }

    # "skills" section, if present, is usually comma/bullet separated
    # rather than one item per line — split it further.
    if profile["skills"]:
        flat = []
        for line in profile["skills"]:
            parts = re.split(r"[,•·|]", line)
            flat.extend(p.strip() for p in parts if p.strip())
        profile["skills"] = flat

    text_lower = text.lower()
    profile["programming_languages"] = [
        lang for lang in _PROGRAMMING_LANGUAGES
        if re.search(rf"\b{re.escape(lang.lower())}\b", text_lower)
    ]
    profile["technologies"] = [
        tech for tech in _TECHNOLOGIES
        if re.search(rf"\b{re.escape(tech.lower())}\b", text_lower)
    ]

    return profile
