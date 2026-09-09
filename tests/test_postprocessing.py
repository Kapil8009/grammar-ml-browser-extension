from backend.app.core.postprocessing import DiffPostprocessor
from backend.app.schemas import EditKind


def test_diff_creates_offset_addressable_replacement() -> None:
    suggestions = DiffPostprocessor().suggestions("I has a apple.", "I have an apple.")

    assert [(item.original, item.replacement) for item in suggestions] == [
        ("has", "have"),
        ("a", "an"),
    ]
    assert suggestions[0].kind is EditKind.replacement
    assert (suggestions[0].start, suggestions[0].end) == (2, 5)


def test_diff_supports_insertions_and_deletions() -> None:
    insertions = DiffPostprocessor().suggestions("This works", "This really works")
    deletions = DiffPostprocessor().suggestions("This very works", "This works")

    assert insertions[0].kind is EditKind.insertion
    assert insertions[0].start == insertions[0].end == 5
    assert deletions[0].kind is EditKind.deletion
    assert deletions[0].original == "very"
