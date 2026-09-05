"""Herd demand: how many pounds of dry matter walk off the pasture each day.

Everything is expressed through animal units so cattle, sheep and goats share
one formula. One animal unit (AU) is a 1,000 lb animal, and the standard
planning intake is 2.6% of body weight in dry matter per day, i.e. 26 lb
DM/AU/day. These are the NRCS numbers ranchers already use; the point of
this module is to be boring and checkable, not clever.
"""

from __future__ import annotations

from dataclasses import dataclass

INTAKE_FRACTION_OF_BW = 0.026  # lb DM per lb body weight per day
LB_PER_AU = 1000.0

SPECIES_DEFAULT_WEIGHT_LB = {
    "cattle": 1200.0,  # mature cow, no calf
    "sheep": 150.0,
    "goats": 120.0,
}


@dataclass(frozen=True)
class Herd:
    species: str
    head: int
    avg_weight_lb: float | None = None

    def __post_init__(self):
        if self.species not in SPECIES_DEFAULT_WEIGHT_LB:
            raise ValueError(f"unknown species {self.species!r}")
        if self.head <= 0:
            raise ValueError("head must be positive")
        if self.avg_weight_lb is not None and self.avg_weight_lb <= 0:
            raise ValueError("avg_weight_lb must be positive")

    @property
    def weight_lb(self) -> float:
        return self.avg_weight_lb or SPECIES_DEFAULT_WEIGHT_LB[self.species]

    @property
    def au_per_head(self) -> float:
        return self.weight_lb / LB_PER_AU

    @property
    def animal_units(self) -> float:
        return self.head * self.au_per_head

    @property
    def demand_lb_per_day(self) -> float:
        """Dry-matter intake for the whole herd per day."""
        return self.head * self.weight_lb * INTAKE_FRACTION_OF_BW


def grazing_days(forage_lb: float, utilization: float, herd: Herd) -> float:
    """Days the herd can stay if it may remove `utilization` of the forage.

    Utilisation is the fraction of standing forage the animals are allowed to
    take; 0.5 is the "take half, leave half" rule of thumb. Trampling and
    fouling are folded into that number, which is how ranchers use it.
    """
    if not 0.0 < utilization <= 1.0:
        raise ValueError("utilization must be in (0, 1]")
    return (forage_lb * utilization) / herd.demand_lb_per_day
