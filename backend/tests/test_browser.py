"""Telegram deal browser: /deals menu, one card per search with Next / Prev / Skip, seen tracking, /price."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import DzPrice, Listing, Search, SearchListing, Settings
from app.notify import browser, poller, telegram


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _paris(hours_ago: float) -> str:
    return (datetime.utcnow() - timedelta(hours=hours_ago) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")


class Phone:
    """Fake Telegram: records what was sent, edited, deleted and answered."""

    def __init__(self, monkeypatch):
        self.sent, self.edited, self.deleted, self.answers, self.buttons = [], [], [], [], []
        monkeypatch.setattr(telegram, "send_message", self.send)
        monkeypatch.setattr(telegram, "edit_card", self.edit)
        monkeypatch.setattr(telegram, "delete_message", lambda s, mid: self.deleted.append(mid) or {"ok": True})
        monkeypatch.setattr(telegram, "answer_callback", lambda t, i, text="": self.answers.append(text) or {"ok": True})
        monkeypatch.setattr(telegram, "edit_buttons", lambda s, mid, b: self.buttons.append(b) or {"ok": True})

    def send(self, settings, text, photo_url=None, buttons=None, reply_to=None):
        self.sent.append({"text": text, "buttons": buttons or []})
        return {"ok": True, "result": {"message_id": 100 + len(self.sent)}}

    def edit(self, settings, message_id, text, photo, buttons, is_photo):
        self.edited.append({"id": message_id, "text": text, "buttons": buttons})
        return {"ok": True}

    def last(self):
        return (self.edited or self.sent)[-1]


def _world(db):
    settings = Settings(id=1, telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="1", llm_api_key="k")
    laptops = Search(name="pc portable", cpu="")
    cards = Search(name="cartes", gpu="")
    db.add_all([settings, laptops, cards])
    db.commit()

    def ad(search, subject, dz, price=220.0, hours=2.0, ship="yes"):
        listing = Listing(subject=subject, price_eur=price, url=f"https://lbc/{subject}", first_publication_date=_paris(hours),
                          specs={"cpu": "i5-13420h", "ram_gb": 16}, dz_price_median_dzd=dz, dz_price_low_dzd=dz * 0.9,
                          dz_price_high_dzd=dz * 1.1, dz_confidence="medium", images=[], ship_ok=ship)
        db.add(listing)
        db.commit()
        db.add(SearchListing(search_id=search.id, listing_id=listing.id))
        db.commit()
        return listing

    ads = {
        "best": ad(laptops, "Best laptop", 160_000),
        "ok": ad(laptops, "Okay laptop", 110_000),
        "loss": ad(laptops, "Losing laptop", 40_000),
        "old": ad(laptops, "Old laptop", 160_000, hours=24 * 15),
        "pickup": ad(laptops, "Pickup laptop", 160_000, ship="no"),
    }
    return settings, laptops, cards, ads


def _tap(db, settings, data, message_id=500):
    poller._handle_callback(db, settings, {"id": "q", "data": data, "message": {"message_id": message_id, "chat": {"id": 1}}})


def test_deals_opens_a_menu_with_good_and_unseen_counts_per_search(monkeypatch):
    db = _db()
    settings, laptops, cards, ads = _world(db)
    phone = Phone(monkeypatch)
    poller._handle_message(db, settings, {"chat": {"id": 1}, "text": "/deals"})
    menu = phone.sent[-1]
    assert "pc portable" in menu["text"] and "cartes" in menu["text"]
    assert "2 good (2 new)" in menu["text"]  # best + okay; the losing, old and pickup-only ads are not good deals
    targets = [b[1] for b in menu["buttons"]]
    assert f"cb:o:{laptops.id}:g" in targets and f"cb:o:{cards.id}:g" in targets and "cb:o:0:g" in targets


def test_one_card_moves_with_next_prev_and_skip(monkeypatch):
    db = _db()
    settings, laptops, _, ads = _world(db)
    phone = Phone(monkeypatch)

    _tap(db, settings, f"o:{laptops.id}:g")
    assert "Best laptop" in phone.last()["text"] and "1/2" in phone.last()["text"] and "🆕" in phone.last()["text"]
    assert ads["best"].tg_seen_at is not None
    assert "Open ad" in [b[0] for b in phone.last()["buttons"]]

    _tap(db, settings, f"n:{laptops.id}:{ads['best'].id}:g")
    assert "Okay laptop" in phone.last()["text"] and phone.last()["id"] == 500  # same message, edited in place
    _tap(db, settings, f"n:{laptops.id}:{ads['ok'].id}:g")
    assert phone.answers[-1] == "That was the last one"
    _tap(db, settings, f"b:{laptops.id}:{ads['ok'].id}:g")
    assert "Best laptop" in phone.last()["text"] and "🆕" not in phone.last()["text"]  # seen now

    _tap(db, settings, f"k:{laptops.id}:{ads['best'].id}:g")
    assert ads["best"].pipeline_status == "skipped" and phone.answers[-1] == "Skipped"
    assert "Okay laptop" in phone.last()["text"] and "1/1" in phone.last()["text"]  # the skipped ad left the list

    _tap(db, settings, f"c:{laptops.id}:{ads['ok'].id}:g")
    assert ads["ok"].pipeline_status == "contacted" and "📨 Contacted ✓" in [b[0] for b in phone.last()["buttons"]]
    _tap(db, settings, f"c:{laptops.id}:{ads['ok'].id}:g")
    assert ads["ok"].pipeline_status == ""  # a second tap removes the mark


def test_losing_ads_are_hidden_until_asked(monkeypatch):
    db = _db()
    settings, laptops, cards, ads = _world(db)
    phone = Phone(monkeypatch)
    _tap(db, settings, f"o:{cards.id}:g")
    assert "no deal with a profit" in phone.last()["text"]

    for name in ("best", "ok"):
        ads[name].pipeline_status = "skipped"
    db.commit()
    _tap(db, settings, f"o:{laptops.id}:g")
    assert "1 losing" in phone.last()["text"] and "1 pickup-only" in phone.last()["text"]
    assert f"cb:o:{laptops.id}:a" in [b[1] for b in phone.last()["buttons"]]
    _tap(db, settings, f"o:{laptops.id}:a")
    assert "Losing laptop" in phone.last()["text"]


def test_menu_counts_only_what_you_have_not_seen(monkeypatch):
    db = _db()
    settings, laptops, _, ads = _world(db)
    phone = Phone(monkeypatch)
    _tap(db, settings, f"o:{laptops.id}:g")  # shows the best one
    _tap(db, settings, "m")
    assert "2 good (1 new)" in phone.last()["text"]
    _tap(db, settings, f"o:{laptops.id}:g")
    assert "Okay laptop" in phone.last()["text"]  # opens at the first deal you have not seen


def test_alert_buttons_show_what_you_did_and_can_be_undone(monkeypatch):
    db = _db()
    settings, _, _, ads = _world(db)
    phone = Phone(monkeypatch)
    _tap(db, settings, f"p:s:{ads['best'].id}")
    assert phone.answers[-1] == "Skipped ⏭" and ads["best"].pipeline_status == "skipped"
    assert "⏭ Skipped · Undo" in [b[0] for b in phone.buttons[-1]]
    _tap(db, settings, f"u:{ads['best'].id}")
    assert ads["best"].pipeline_status == "" and "⏭ Skip" in [b[0] for b in phone.buttons[-1]]


def test_price_command_sets_your_own_price_and_reprices_ads(monkeypatch):
    db = _db()
    settings = Settings(id=1, telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="1", llm_api_key="k")
    search = Search(name="cards", gpu="rtx 3070", kind="gpu")
    card = Listing(subject="MSI RTX 3070 Gaming", price_eur=250.0, url="u", images=[], specs={"gpu": "RTX 3070"})
    db.add_all([settings, search, card])
    db.commit()
    db.add(SearchListing(search_id=search.id, listing_id=card.id))
    db.commit()
    phone = Phone(monkeypatch)
    poller._handle_message(db, settings, {"chat": {"id": 1}, "text": "/price rtx 3070 88000"})
    row = db.query(DzPrice).filter(DzPrice.cache_key == "gpu|rtx 3070|").one()
    assert row.manual and row.median_dzd == 88000 and "88 000 DA" in phone.sent[-1]["text"]
    assert card.dz_price_median_dzd == 88000
    poller._handle_message(db, settings, {"chat": {"id": 1}, "text": "/price something 5"})
    assert "Usage" in phone.sent[-1]["text"] or "could not tell" in phone.sent[-1]["text"] or "looks wrong" in phone.sent[-1]["text"]


def test_card_buttons_fit_telegram_limit():
    listing = Listing(id=123456789, url="u", pipeline_status="")
    for _, target in browser._card_buttons(listing, 987654, "g"):
        assert len(target.removeprefix("cb:")) <= 64
