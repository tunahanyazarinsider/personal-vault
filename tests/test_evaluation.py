import json

import pytest

from personal_vault.chunking import chunk_markdown
from personal_vault.evaluation import Case, evaluate, load_cases
from personal_vault.models import PersonalVaultError


def add(store, embedder, path, text):
    chunks = chunk_markdown(text, path, "h")
    store.upsert(chunks, embedder.embed_documents([chunk.text for chunk in chunks]))


def test_rank_is_the_position_of_the_expected_note(embedder, store):
    add(store, embedder, "a.md", "alpha\n")
    add(store, embedder, "b.md", "beta\n")

    results = evaluate([Case("alpha", "a.md"), Case("alpha", "missing.md")], embedder, store, 1)

    assert [(result.rank, result.top_path) for result in results] == [(1, "a.md"), (0, "a.md")]


def test_load_cases_rejects_a_wrong_shape(tmp_path):
    file = tmp_path / "questions.json"
    file.write_text(json.dumps([{"question": "q", "path": "a.md"}]))
    assert load_cases(file) == [Case("q", "a.md")]

    file.write_text(json.dumps([{"question": "q"}]))
    with pytest.raises(PersonalVaultError):
        load_cases(file)
