from app.core.complexity_classifier import ComplexitySignals, classify


def test_popular_overrides_all():
    signals = ComplexitySignals(citation_count=600)
    level, justification = classify(signals, popular_citation_threshold=500)
    assert level == "Popular"
    assert "600" in justification


def test_below_threshold_not_popular():
    # Regression test: this citation count used to cross the old
    # hardcoded 100 threshold and get tagged "Popular" -- it must not
    # cross the new default-500 threshold.
    signals = ComplexitySignals(citation_count=150)
    level, _ = classify(signals, popular_citation_threshold=500)
    assert level != "Popular"


def test_popular_threshold_is_configurable():
    signals = ComplexitySignals(citation_count=750)
    below_1000, _ = classify(signals, popular_citation_threshold=1000)
    above_500, _ = classify(signals, popular_citation_threshold=500)
    assert below_1000 != "Popular"
    assert above_500 == "Popular"


def test_high_requires_two_criteria():
    signals = ComplexitySignals(multi_hop_reasoning=True, adversarial_or_red_teaming=True)
    level, _ = classify(signals, popular_citation_threshold=500)
    assert level == "High"


def test_default_low():
    signals = ComplexitySignals()
    level, _ = classify(signals, popular_citation_threshold=500)
    assert level == "Low"