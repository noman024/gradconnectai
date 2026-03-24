from datetime import date, datetime

from app.services.store import _iso_dhaka


def test_iso_dhaka_handles_date_without_crashing():
    assert _iso_dhaka(date(2026, 3, 24)) == "2026-03-24"


def test_iso_dhaka_converts_datetime_to_dhaka_timezone():
    iso = _iso_dhaka(datetime.fromisoformat("2026-03-24T00:00:00+00:00"))
    assert iso is not None
    assert iso.startswith("2026-03-24T06:00:00")
    assert iso.endswith("+06:00")
