from personal_vault.chunking import MAX_CHARS, chunk_markdown


def test_splits_at_headings_and_keeps_heading_path():
    text = "intro\n# A\nbody a\n## B\nbody b\n# C\nbody c\n"
    chunks = chunk_markdown(text, "note.md", "h")
    assert [(chunk.heading, chunk.line, chunk.text) for chunk in chunks] == [
        ("", 1, "intro"),
        ("A", 3, "body a"),
        ("A > B", 5, "body b"),
        ("C", 7, "body c"),
    ]
    assert [chunk.index for chunk in chunks] == [0, 1, 2, 3]


def test_hash_inside_code_fence_is_not_a_heading():
    text = "# A\n```\n# comment\n```\n"
    chunks = chunk_markdown(text, "note.md", "h")
    assert len(chunks) == 1
    assert "# comment" in chunks[0].text


def test_long_text_is_cut_to_max_chars():
    text = "# A\n" + "x" * (MAX_CHARS * 2 + 10) + "\n" + "short line\n" * 400
    chunks = chunk_markdown(text, "note.md", "h")
    assert len(chunks) > 3
    assert all(len(chunk.text) <= MAX_CHARS for chunk in chunks)


def test_line_points_at_first_non_blank_line():
    chunks = chunk_markdown("# A\n\n\nfirst\n", "note.md", "h")
    assert chunks[0].line == 4


def test_heading_without_body_gives_no_chunk():
    assert chunk_markdown("# only heading\n\n", "note.md", "h") == []


def test_embedding_text_has_title_and_heading():
    chunk = chunk_markdown("# TLS\nhandshake\n", "8_network/ssl_tls.md", "h")[0]
    assert chunk.embedding_text() == "ssl_tls > TLS\nhandshake"
