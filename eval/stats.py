"""
Uncertainty for small evaluation sets (Lesson 6: "use an appropriate interval or paired
comparison"). Standard library only.

    wilson(k, n)          95% Wilson score interval for a rate k/n (sound for small n and
                          for k = 0 or k = n, unlike the normal approximation)
    mcnemar_exact(b, c)   two-sided exact McNemar p for a paired comparison: b cases only
                          system A gets right, c cases only system B gets right. Cases both
                          get right or both get wrong carry no information about the difference.
"""
from __future__ import annotations

import math

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    denominator = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - half) / denominator), min(1.0, (centre + half) / denominator)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial test on the discordant pairs (p = 0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def fmt_interval(interval: tuple[float, float] | None) -> str:
    return "–" if interval is None else f"{interval[0]:.0%}–{interval[1]:.0%}"
