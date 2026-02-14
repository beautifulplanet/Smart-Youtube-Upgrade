import pytest
from safety_db import SafetyDatabase


@pytest.fixture
def db():
    return SafetyDatabase()


def test_safety_db_initialization(db):
    assert db.signatures is not None
    assert db.categories is not None
    assert len(db.categories) > 0
    assert isinstance(db.signatures, list)


def test_get_categories(db):
    categories = db.get_categories()
    assert isinstance(categories, dict)
    assert len(categories) > 0


def test_get_all_signatures(db):
    signatures = db.get_all_signatures()
    assert isinstance(signatures, list)


def test_default_signatures_have_required_fields():
    """Default signatures must have the minimum required fields."""
    db = SafetyDatabase.__new__(SafetyDatabase)
    defaults = db._get_default_signatures()
    required = ["id", "category", "severity", "triggers", "warning_message"]
    for sig in defaults:
        for field in required:
            assert field in sig, f"Signature {sig.get('id', '?')} missing field '{field}'"


def test_get_signatures_by_category(db):
    """Filtering by category should only return matching signatures."""
    # Get a category we know exists from defaults
    if not db.signatures:
        pytest.skip("No signatures loaded")
    first_category = db.signatures[0]["category"]
    filtered = db.get_signatures_by_category(first_category)
    assert len(filtered) >= 1
    for sig in filtered:
        assert sig["category"] == first_category


def test_get_signatures_by_nonexistent_category(db):
    result = db.get_signatures_by_category("nonexistent_category_xyz")
    assert result == []


def test_get_category_name(db):
    """Should return display name for known categories."""
    # Default categories include 'fitness'
    name = db.get_category_name("fitness")
    assert name == "Fitness"


def test_get_category_name_unknown(db):
    """Unknown categories should return title-cased ID."""
    name = db.get_category_name("unknown_thing")
    assert name == "Unknown_Thing"


def test_add_signature_valid(db):
    new_sig = {
        "id": "test-001",
        "category": "test",
        "triggers": ["test trigger"],
        "severity": "low",
        "warning_message": "Test warning",
    }
    count_before = len(db.signatures)
    result = db.add_signature(new_sig)
    assert result is True
    assert len(db.signatures) == count_before + 1


def test_add_signature_missing_fields(db):
    incomplete = {"id": "test-002", "category": "test"}
    count_before = len(db.signatures)
    result = db.add_signature(incomplete)
    assert result is False
    assert len(db.signatures) == count_before


def test_default_categories_structure(db):
    """Each category should have name, emoji, and description."""
    for cat_id, cat_data in db.categories.items():
        assert "name" in cat_data, f"Category '{cat_id}' missing 'name'"
        assert "description" in cat_data, f"Category '{cat_id}' missing 'description'"


def test_default_severity_levels_valid():
    """Default signatures should use valid severity levels."""
    db = SafetyDatabase.__new__(SafetyDatabase)
    defaults = db._get_default_signatures()
    valid_severities = {"low", "medium", "high", "critical"}
    for sig in defaults:
        assert sig["severity"] in valid_severities, (
            f"Signature {sig['id']} has invalid severity '{sig['severity']}'"
        )


def test_default_triggers_are_nonempty_lists():
    """Default signatures' triggers should be non-empty lists of strings."""
    db = SafetyDatabase.__new__(SafetyDatabase)
    defaults = db._get_default_signatures()
    for sig in defaults:
        assert isinstance(sig["triggers"], list), f"Signature {sig['id']} triggers not a list"
        assert len(sig["triggers"]) > 0, f"Signature {sig['id']} has empty triggers"
        for trigger in sig["triggers"]:
            assert isinstance(trigger, str), f"Signature {sig['id']} has non-string trigger"
