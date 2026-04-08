"""Lightweight validation and heuristic repair for agent JSON outputs (no extra model calls by default)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# Phrases that indicate templated slide relations or copied bridge text
GENERIC_RELATION_SUBSTRINGS = (
    "extends the prior discussion",
    "carrying forward the ideas",
    "builds on slide",
    "continues the previous discussion",
    "this slide follows from the last one",
    "anchored in",
    "slide extends",
)

# Meta / system language that must not appear in committed style profiles
STYLE_META_SUBSTRINGS = (
    "offline",
    "fallback",
    "verify when online",
    "when api is available",
    "re-run with",
    "openai",
    "billing enabled",
    "cannot infer",
    "excerpt-based",
)


def looks_like_placeholder_title(title: str, slide_number: int) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if re.match(r"^slide\s*\d+\s*$", t, re.I):
        return True
    if t.lower() == f"slide {slide_number}".lower():
        return True
    return False


def infer_title_from_page_text(page_text: str, slide_number: int) -> str:
    """Prefer first substantial non-boilerplate line from PDF extract."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    for line in lines[:12]:
        if looks_like_placeholder_title(line, slide_number):
            continue
        if len(line) < 4:
            continue
        # drop pure page numbers / lone bullets
        if re.match(r"^[\d•\-–]+$", line):
            continue
        return line[:120]
    # Semantic fallback — not "Slide N"
    snippet = " ".join(lines[:2])[:80].strip()
    if snippet:
        return snippet + ("…" if len(snippet) >= 80 else "")
    return f"Section {slide_number}"


def is_generic_relation(rel: str) -> bool:
    s = (rel or "").strip()
    if not s:
        return True
    low = s.lower()
    if low.startswith("n/a"):
        return False
    if len(s) < 28:
        return True
    return any(bad in low for bad in GENERIC_RELATION_SUBSTRINGS)


def repair_relation_to_previous(
    rel: str,
    slide_number: int,
    prior: Optional[Dict[str, Any]],
    slide: Dict[str, Any],
) -> str:
    if slide_number <= 1:
        return "N/A (first slide)"
    if prior and not is_generic_relation(rel):
        return rel
    prev_title = (prior or {}).get("title_guess") or "the previous material"
    prev_concepts = (prior or {}).get("key_concepts") or (prior or {}).get("carryover_concepts") or []
    adds = slide.get("what_this_slide_adds") or slide.get("summary") or ""
    kc = slide.get("key_concepts") or []
    new_bit = ", ".join(kc[:2]) if kc else (adds[:140] + "…" if len(adds) > 140 else adds)
    prev_hook = prev_concepts[0] if prev_concepts else prev_title[:60]
    return (
        f"After establishing «{prev_hook}», this step brings in {new_bit or 'the next layer of the argument'} "
        f"so the lecture can move from setup to the specific point on this slide."
    )


def strip_meta_from_style_field(text: str) -> str:
    s = (text or "").strip()
    low = s.lower()
    for m in STYLE_META_SUBSTRINGS:
        if m in low:
            return (
                "Conversational, example-driven teaching voice inferred from transcript excerpts "
                "(see evidence_phrases)."
            )
    return s


def clean_speaker_profile(sp: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(sp)
    for key in ("tone", "pacing", "audience_assumption"):
        if key in out and isinstance(out[key], str):
            out[key] = strip_meta_from_style_field(out[key])
    npref = out.get("narration_preferences")
    if isinstance(npref, dict):
        oth = npref.get("other")
        if isinstance(oth, str) and any(m in oth.lower() for m in STYLE_META_SUBSTRINGS):
            npref = {**npref, "other": "Prefer explanation and paraphrase over reading slides verbatim."}
            out["narration_preferences"] = npref
    return out


def narration_echoes_relation_field(narration: str, relation: str) -> bool:
    """Detect accidental paste of relation_to_previous into spoken script."""
    n = (narration or "").lower()
    r = (relation or "").strip()
    if len(r) < 40:
        return False
    chunk = r[: min(60, len(r))].lower()
    return chunk in n and "n/a" not in chunk


def narration_too_much_bullet_overlap(narration: str, bullets: Sequence[str], summary: str) -> bool:
    """Heuristic: narration is mostly concatenated slide lines."""
    n = narration or ""
    if len(n) < 80:
        return False
    joined = " ".join(b for b in bullets if b)[:400].lower()
    if len(joined) < 40:
        return False
    # count how many bullet fragments appear verbatim in narration
    hits = 0
    for b in bullets:
        b = b.strip()
        if len(b) < 25:
            continue
        if b.lower() in n.lower():
            hits += 1
    return hits >= 3


def opening_signature(text: str, max_words: int = 7) -> str:
    words = re.split(r"\s+", (text or "").strip())
    if not words:
        return ""
    return " ".join(words[:max_words]).lower()


def dedupe_opening_list(signatures: List[str], current: str) -> List[str]:
    """Keep recent distinct openings for anti-repetition prompts."""
    cur = opening_signature(current)
    out = [s for s in signatures if s and s != cur]
    return out[-8:]
