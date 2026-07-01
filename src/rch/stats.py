"""Small, dependency-free statistics helpers.

Only what the survey analyzer needs: descriptive stats, paired/independent
t statistics, Cohen's d, and a two-sided p-value from Student's t
distribution via the regularized incomplete beta function. Keeping this
pure-stdlib means the harness never fabricates a number it cannot compute.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def variance(values: list[float]) -> float:
    if len(values) < 2:
        return float("nan")
    m = mean(values)
    return sum((value - m) ** 2 for value in values) / (len(values) - 1)


def stdev(values: list[float]) -> float:
    var = variance(values)
    return math.sqrt(var) if var == var else float("nan")  # nan check


def _betacf(a: float, b: float, x: float) -> float:
    max_iterations = 300
    eps = 3.0e-12
    tiny = 1.0e-30
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(log_beta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    """Two-sided p-value for a t statistic with df degrees of freedom."""
    if df <= 0 or not math.isfinite(t):
        return float("nan")
    x = df / (df + t * t)
    return _betai(df / 2.0, 0.5, x)


@dataclass
class PairedResult:
    n: int
    pre_mean: float
    post_mean: float
    mean_diff: float
    sd_diff: float
    t: float
    df: int
    p_value: float
    cohens_d: float


def paired_test(pre: list[float], post: list[float]) -> PairedResult:
    """Paired-sample t-test with paired Cohen's d (mean diff / sd of diffs)."""
    diffs = [b - a for a, b in zip(pre, post)]
    n = len(diffs)
    md = mean(diffs)
    sd = stdev(diffs)
    if n < 2 or sd == 0 or not math.isfinite(sd):
        t = float("nan")
        p = float("nan")
        d = float("nan")
    else:
        se = sd / math.sqrt(n)
        t = md / se
        p = t_two_sided_p(t, n - 1)
        d = md / sd
    return PairedResult(
        n=n,
        pre_mean=mean(pre),
        post_mean=mean(post),
        mean_diff=md,
        sd_diff=sd,
        t=t,
        df=n - 1,
        p_value=p,
        cohens_d=d,
    )


def cohens_d_interpretation(d: float) -> str:
    if not math.isfinite(d):
        return "계산 불가"
    magnitude = abs(d)
    if magnitude < 0.2:
        return "무시 가능"
    if magnitude < 0.5:
        return "작음"
    if magnitude < 0.8:
        return "중간"
    return "큼"
