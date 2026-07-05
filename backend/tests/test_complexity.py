from app.core.complexity_classifier import ComplexitySignals, classify


def test_popular_overrides_all():
    signals = ComplexitySignals(citation_count=150)
    level, justification = classify(signals)
    assert level == "Popular"
    assert "150" in justification


def test_high_requires_two_criteria():
    signals = ComplexitySignals(multi_hop_reasoning=True, adversarial_or_red_teaming=True)
    level, _ = classify(signals)
    assert level == "High"


def test_default_low():
    signals = ComplexitySignals()
    level, _ = classify(signals)
    assert level == "Low"
