"""One first-brew marker per coffee, however many bags or brew methods it takes.

The reported case: India Ratnagiri was brewed on 9/6 as a pour over and on 9/10 as an
espresso. Both showed a first-brew marker, because the pre-tick counted brews per
template and the espresso recipe was new even though the bean was not.
"""
from app.models.brew import Brew
from app.services import analytics_service, brew_service, template_service


def _brew(client, day, method="Pour Over", first=False, score=None,
          bean="India Ratnagiri Thermal-Shock", roaster="Onyx"):
    resp = client.post("/api/v1/brews/", json={
        "brew_date": day, "roaster": roaster, "bean_name": bean,
        "bean_amount_grams": 18.0, "water_amount_ml": 300.0,
        "brew_method": method, "is_first_brew": first,
    })
    assert resp.status_code == 201, resp.text
    brew = resp.json()
    if score is not None:
        r = client.post(f"/api/v1/brews/{brew['id']}/rating", json={"overall_score": score})
        assert r.status_code in (200, 201), r.text
    return brew


def test_only_the_earliest_flagged_brew_counts(client, db):
    early = _brew(client, "2026-09-06", "Pour Over", first=True)
    late = _brew(client, "2026-09-10", "Espresso", first=True)

    counted = brew_service.effective_first_brew_ids(db)
    assert early["id"] in counted
    assert late["id"] not in counted, "a second method shouldn't earn another first brew"


def test_a_genuinely_different_coffee_keeps_its_own_first(client, db):
    india = _brew(client, "2026-09-06", first=True)
    monarch = _brew(client, "2026-09-07", first=True, bean="Monarch")
    counted = brew_service.effective_first_brew_ids(db)
    assert {india["id"], monarch["id"]} <= counted


def test_the_superseded_brew_rejoins_the_averages(client, db):
    """Its rating was being dropped from the stats for a marker it shouldn't have."""
    _brew(client, "2026-09-06", "Pour Over", first=True, score=4.0)
    _brew(client, "2026-09-10", "Espresso", first=True, score=8.0)
    _brew(client, "2026-09-12", "Pour Over", score=6.0)

    summary = analytics_service.get_summary(db)
    # Only the 9/6 brew is excluded, so the average is over 8.0 and 6.0.
    assert summary["excluded_brews"] == 1
    assert summary["average_score"] == 7.0


def test_the_pretick_follows_the_bean_not_the_template(client, db):
    """The cause: brew_counts was keyed by template, so a second recipe looked new."""
    pour = client.post("/api/v1/templates/", json={
        "name": "India — Pour Over", "roaster": "Onyx",
        "bean_name": "India Ratnagiri Thermal-Shock", "brew_method": "Pour Over",
    }).json()
    espresso = client.post("/api/v1/templates/", json={
        "name": "India — Espresso", "roaster": "Onyx",
        "bean_name": "India Ratnagiri Thermal-Shock", "brew_method": "Espresso",
    }).json()

    # Nothing brewed yet: both recipes are a genuine first.
    counts = template_service.brew_counts(db)
    assert counts[pour["id"]] == 0 and counts[espresso["id"]] == 0

    _brew(client, "2026-09-06", "Pour Over")

    # The bean has now been brewed, so neither recipe pre-ticks — including the
    # espresso one, which used to because it had no brews of its own.
    counts = template_service.brew_counts(db)
    assert counts[pour["id"]] == 1
    assert counts[espresso["id"]] == 1, "a new method for a brewed bean is not a first brew"


def test_brew_history_gives_the_flags_their_own_column(client):
    """The icon shared the score cell, which wrapped E and T onto two lines."""
    _brew(client, "2026-09-06", first=True, score=8.0)
    page = client.get("/brews")
    assert page.status_code == 200
    assert 'class="brew-flags"' in page.text
    # The marker renders, and the score cell that follows holds only E / T.
    assert "🎯" in page.text
    flags_cell = page.text.split('class="brew-flags"')[1].split("</td>")[0]
    assert "badge-score" not in flags_cell


def test_a_superseded_marker_is_not_drawn(client):
    _brew(client, "2026-09-06", "Pour Over", first=True)
    _brew(client, "2026-09-10", "Espresso", first=True)
    page = client.get("/brews")
    assert page.text.count("🎯") == 1, "only the earliest flagged brew shows the marker"
