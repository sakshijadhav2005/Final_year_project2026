from app.services.guardrails import (
    confidence_badge,
    grounding_check,
    moderate_text,
    should_use_rag,
)


def test_confidence_badge() -> None:
    assert confidence_badge(0.9) == "high"
    assert confidence_badge(0.8) == "high"
    assert confidence_badge(0.7) == "medium"
    assert confidence_badge(0.55) == "medium"
    assert confidence_badge(0.5) == "low"
    assert confidence_badge(None) == "medium"


def test_moderate_text() -> None:
    safe = moderate_text("This is a wonderful event.")
    assert safe["pass"] is True
    assert not safe["hits"]

    unsafe = moderate_text("We should kill all the processes.")
    assert unsafe["pass"] is False
    assert "kill all" in unsafe["hits"]


def test_grounding_check_pass() -> None:
    transcript = "Welcome to the Python conference. Today we will discuss FastAPI and LangGraph."
    body = "Welcome to the Python conference! We will discuss FastAPI today."
    result = grounding_check(body, transcript)
    assert result["pass"] is True
    assert not result["unsupported"]


def test_grounding_check_fail() -> None:
    transcript = "Welcome to the Python conference."
    body = (
        "The fantastic event was completely sponsored by a major artificial intelligence corporation that provided excellent free hardware technology to all participating attendees. "
        "Welcome to the Python conference. "
        "The executive leadership team of the enterprise announced a revolutionary brand new product development line during today presentation. "
        "Everybody in the audience enthusiastically clapped at the absolutely amazing news about the spectacular future of advanced machine learning systems. "
        "This particular statement represents another incredibly verbose sentence that completely makes absolutely zero logical sense in this specific context whatsoever."
    )
    result = grounding_check(body, transcript)
    assert result["pass"] is False
    assert len(result["unsupported"]) >= 1


def test_should_use_rag() -> None:
    assert should_use_rag("word " * 1000, use_org_memory=False, threshold=500) is True
    assert should_use_rag("word " * 100, use_org_memory=False, threshold=500) is False
    assert should_use_rag("word " * 100, use_org_memory=True, threshold=500) is True
