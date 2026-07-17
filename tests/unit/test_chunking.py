from app.services.ingestion.chunking import recursive_character_chunk


def test_recursive_chunk_produces_nonempty_chunks():
    text = "\n\n".join([f"Paragraph {i} with some content about policy details." for i in range(20)])
    chunks = recursive_character_chunk(text, chunk_size_tokens=50, overlap_tokens=10)
    assert len(chunks) > 1
    assert all(c.text.strip() for c in chunks)


def test_recursive_chunk_handles_short_text():
    chunks = recursive_character_chunk("Just one short paragraph.")
    assert len(chunks) == 1
    assert "short paragraph" in chunks[0].text


def test_recursive_chunk_empty_text_returns_no_chunks():
    assert recursive_character_chunk("") == []


def test_parent_text_includes_surrounding_context():
    paragraphs = [f"Paragraph number {i}." for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = recursive_character_chunk(text, chunk_size_tokens=10, overlap_tokens=2)
    # parent_text should be at least as long as the chunk's own text for any chunk
    assert all(len(c.parent_text) >= len(c.text) for c in chunks)
