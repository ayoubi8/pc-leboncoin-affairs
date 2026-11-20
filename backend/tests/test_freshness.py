from __future__ import annotations

from datetime import datetime, timedelta

from app.intelligence import freshness
from app.models import Listing
from app.scraping import leboncoin

NOW = datetime(2026, 11, 20, 12, 0, 0)  # UTC; Paris is UTC+1 in November


def _ad(hours_ago, **kw):
    published = NOW - timedelta(hours=hours_ago) + timedelta(hours=1)  # Paris local clock
    return Listing(subject="Laptop", first_publication_date=published.strftime("%Y-%m-%d %H:%M:%S"), **kw)


def test_paris_conversion_winter_and_summer():
    assert freshness.paris_to_utc(datetime(2026, 11, 20, 13, 0)) == datetime(2026, 11, 20, 12, 0)
    assert freshness.paris_to_utc(datetime(2026, 7, 1, 14, 0)) == datetime(2026, 7, 1, 12, 0)


def test_fresh_beats_old_and_sold_wording_hurts():
    fresh = freshness.compute(_ad(1), NOW)
    day = freshness.compute(_ad(30), NOW)
    old = freshness.compute(_ad(24 * 20), NOW)
    assert fresh["score"] > day["score"] > old["score"]
    assert abs(fresh["age_hours"] - 1) < 0.1
    sold = Listing(subject="PC vendu merci", first_publication_date=_ad(1).first_publication_date)
    assert freshness.compute(sold, NOW)["score"] < fresh["score"] - 30
    assert freshness.compute(sold, NOW)["flags"]


def test_recent_bump_keeps_an_old_ad_alive():
    old = _ad(24 * 10)
    bumped = _ad(24 * 10, index_date=(NOW - timedelta(hours=2) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))
    assert freshness.compute(bumped, NOW)["score"] > freshness.compute(old, NOW)["score"] + 20


def test_gone_ad_scores_zero():
    gone = _ad(1, gone_at=NOW)
    assert freshness.compute(gone, NOW)["score"] == 0


def test_classify_ad_page():
    assert leboncoin.classify_ad_page(404, "") == "gone"
    assert leboncoin.classify_ad_page(200, "<h1>Cette annonce n'est plus disponible</h1>") == "gone"
    page = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"ad":{"status":"active"}}}}</script>'
    assert leboncoin.classify_ad_page(200, page) == "active"
    assert leboncoin.classify_ad_page(403, "captcha-delivery") == "unknown"
