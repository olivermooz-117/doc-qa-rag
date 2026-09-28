import pytest

from ingest import chunk_text


def test_chunk_text_returns_empty_list_for_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_splits_long_text():
    text = "a" * 2000

    chunks = chunk_text(
        text,
        chunk_size=800,
        overlap=150,
    )

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)


def test_chunk_text_respects_chunk_size():
    text = "a" * 2000

    chunks = chunk_text(
        text,
        chunk_size=800,
        overlap=150,
    )

    assert all(len(chunk) <= 800 for chunk in chunks)


def test_chunk_text_has_overlap():
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_text(
        text,
        chunk_size=10,
        overlap=3,
    )

    assert len(chunks) > 1

    for previous, current in zip(chunks, chunks[1:]):
        assert current[:3] == previous[-3:]


def test_chunk_text_rejects_invalid_chunk_size():
    with pytest.raises(ValueError):
        chunk_text(
            "some text",
            chunk_size=0,
            overlap=0,
        )


def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text(
            "some text",
            chunk_size=100,
            overlap=100,
        )


def test_chunk_text_rejects_negative_overlap():
    with pytest.raises(ValueError):
        chunk_text(
            "some text",
            chunk_size=100,
            overlap=-1,
        )