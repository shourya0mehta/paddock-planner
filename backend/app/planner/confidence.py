"""How much to trust each number.

The forage estimate is a model output, and it fails in known ways: under
tree canopy the satellite sees leaves, not grass; where shrubs dominate,
the herbaceous number under-counts what goats will actually browse; and an
annual product cannot know what was eaten last month. Every strip carries a
grade and the reasons, so the rancher sees the doubt next to the number.
"""

from __future__ import annotations

from dataclasses import dataclass

from .strips import Strip

TREE_FLAG_PCT = 30.0  # RAP's own guidance: herbaceous estimates degrade above ~30% tree cover


@dataclass
class Confidence:
    grade: str  # "high" | "medium" | "low"
    reasons: list[str]


def grade_strip(s: Strip, species: str, source: str) -> Confidence:
    reasons: list[str] = []
    score = 2  # high

    if s.frac_treed >= 0.5 or s.tree_cover_pct >= TREE_FLAG_PCT:
        score -= 2
        reasons.append(f"{s.tree_cover_pct:.0f}% tree cover: satellite sees canopy, not grass")
    elif s.frac_treed >= 0.2 or s.tree_cover_pct >= 15:
        score -= 1
        reasons.append(f"{s.tree_cover_pct:.0f}% tree cover on part of the strip")

    if s.shrub_cover_pct >= 25:
        if species == "goats":
            reasons.append(
                f"{s.shrub_cover_pct:.0f}% shrub: real browse for goats, not counted in the herbaceous number"
            )
        else:
            score -= 1
            reasons.append(f"{s.shrub_cover_pct:.0f}% shrub cover: less of this strip is grass than the acres suggest")

    if s.parts > 1:
        score -= 1
        reasons.append(f"cut into {s.parts} separate pieces by the pasture shape; check water access for each")

    if source == "synthetic":
        reasons.append("synthetic demo surface, graded as if it were real so the UI can be exercised")

    grade = {2: "high", 1: "medium"}.get(max(score, 0), "low")
    return Confidence(grade=grade, reasons=reasons)


def pasture_notes(source_meta: dict, species: str) -> list[str]:
    notes = list(source_meta.get("notes", []))
    if species == "goats":
        notes.append("Goats browse shrubs and low branches; herbaceous forage under-counts what they will eat.")
    if source_meta.get("year") is not None:
        notes.append(
            "Annual production says how much grew last season, not what is standing today. "
            "Pair it with grazing records to get standing crop."
        )
    return notes
