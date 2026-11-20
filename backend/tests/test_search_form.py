from app.extraction import cpu_db, specs as specs_mod
from app.models import Search
from app.scheduler import INTERVAL_HOURS
from app.search.query_generator import generate_queries


def test_queries_come_only_from_inputs_and_fix_category():
    s = Search(name="x", keyword="gaming beast", location="Paris", category="", brand="Lenovo", cpu_family="intel", ram_min=16, condition="good")
    texts = [q.text for q in generate_queries(s)]
    assert texts == ["Lenovo intel 16go bon état", "Lenovo intel 16go"]
    assert generate_queries(s)[0].params == {"category": "15"}


def test_empty_form_falls_back_to_pc_portable():
    assert [q.text for q in generate_queries(Search(name="x"))] == ["pc portable"]


def test_vendor_terms_and_matching():
    for value, term in {"intel": "intel", "ryzen": "ryzen", "snapdragon": "snapdragon"}.items():
        assert generate_queries(Search(name="x", cpu_family=value))[0].text == term
    assert cpu_db.vendor_of("i7") == "intel"
    assert cpu_db.vendor_of("ryzen5") == "ryzen"
    assert cpu_db.vendor_of("apple_m") == "apple"
    assert cpu_db.vendor_of("snapdragon") == "snapdragon"


def test_snapdragon_extraction():
    sp, _, _ = specs_mod.extract_specs("Surface Laptop Snapdragon X Elite 16Go 512Go", "")
    assert cpu_db.family_of(sp["cpu"]) == "snapdragon"


def test_intervals():
    assert [INTERVAL_HOURS[k] for k in ("1h", "6h", "12h", "daily")] == [1, 6, 12, 24]
