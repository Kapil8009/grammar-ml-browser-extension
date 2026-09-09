from backend.app.core.preprocessing import TextPreprocessor


def test_prepare_and_rebuild_preserves_outer_and_sentence_whitespace() -> None:
    prepared = TextPreprocessor().prepare("  I has a cat.\n\nIt are nice!  ")

    assert prepared.segments == ("I has a cat.", "It are nice!")
    assert prepared.separators == ("\n\n",)
    assert prepared.rebuild(["I have a cat.", "It is nice!"]) == (
        "  I have a cat.\n\nIt is nice!  "
    )


def test_long_input_is_chunked_and_reassembled() -> None:
    prepared = TextPreprocessor(max_segment_chars=8).prepare("one two three four")

    assert len(prepared.segments) == 3
    assert prepared.rebuild(list(prepared.segments)) == "one two three four"
