"""
Heuristic URL prioritization before crawl.

Scores links by source quality, topical relevance, and freshness hints.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _score_one(url: str, university_name: str) -> float:
    u = (url or "").strip().lower()
    if not u:
        return -1.0

    score = 0.0

    # Source quality: educational and institutional domains preferred.
    if ".edu" in u or ".ac." in u:
        score += 2.0
    if any(host in u for host in ("scholar.google.com", "linkedin.com", "researchgate.net")):
        score += 1.0

    # Relevance to supervisor discovery.
    if any(k in u for k in ("faculty", "professor", "research", "lab", "department", "people")):
        score += 2.0
    if "admission" in u or "tuition" in u:
        score -= 0.75

    # University name match boosts relevance.
    uni = (university_name or "").strip().lower()
    if uni and uni.replace(" ", "") in u.replace("-", "").replace("_", "").replace("/", ""):
        score += 1.0

    # Freshness hints: prefer current/next year pages if year appears.
    now = datetime.now(timezone.utc).year
    if str(now) in u:
        score += 0.75
    if str(now + 1) in u:
        score += 0.5
    if str(now - 1) in u:
        score += 0.25

    return score


def prioritize_seed_urls(seed_urls: list[str], university_name: str) -> list[str]:
    ranked = []
    for idx, url in enumerate(seed_urls or []):
        ranked.append((_score_one(url, university_name), idx, url))
    # Stable tie-break by original index.
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, _, u in ranked if u]
