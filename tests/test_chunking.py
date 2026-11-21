from personal_vault.chunking import MAX_CHARS, chunk_markdown, find_links

LONG = "w" * (MAX_CHARS // 2 + 1)


def test_splits_at_headings_and_keeps_heading_path():
    text = f"{LONG}\n# A\n{LONG}\n## B\n{LONG}\n# C\n{LONG}\n"
    chunks = chunk_markdown(text, "note.md", "h")
    assert [(chunk.heading, chunk.line, chunk.text) for chunk in chunks] == [
        ("", 1, LONG),
        ("A", 3, LONG),
        ("A > B", 5, LONG),
        ("C", 7, LONG),
    ]
    assert [chunk.index for chunk in chunks] == [0, 1, 2, 3]


def test_sections_that_fit_together_are_merged_and_keep_their_heading_lines():
    chunks = chunk_markdown("intro\n# A\nbody a\n## B\nbody b\n", "note.md", "h")
    assert [(chunk.heading, chunk.line, chunk.text) for chunk in chunks] == [
        ("", 1, "intro\n\n# A\nbody a\n\n## B\nbody b"),
    ]


def test_short_section_joins_the_long_one_before_it():
    chunks = chunk_markdown(f"# A\n{LONG}\n# B\ntail\n", "note.md", "h")
    assert [(chunk.heading, chunk.text) for chunk in chunks] == [("A", f"{LONG}\n\n# B\ntail")]


def test_merging_never_exceeds_max_chars():
    full = "w" * (MAX_CHARS - 5)
    chunks = chunk_markdown(f"# A\n{full}\n# B\ntail\n", "note.md", "h")
    assert [chunk.text for chunk in chunks] == [full, "tail"]


def test_links_are_note_names_without_alias_heading_folder_or_extension():
    text = "see [[TLS Handshake|tls]], [[8_network/DNS#Records]], [[#local]] and [guide](../docs/My%20Guide.md#top)\n"
    text += "not a note: [site](https://example.com/README.md), again [[tls handshake]]\n"
    assert find_links(text) == ["tls handshake", "dns", "my guide"]
    assert chunk_markdown(text, "note.md", "h")[0].links == ["tls handshake", "dns", "my guide"]


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
