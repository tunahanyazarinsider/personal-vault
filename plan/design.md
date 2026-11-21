# personal-vault: design

Status: agreed 2026-11-21.

A Claude Code plugin that answers questions from local folders of notes. Notes are embedded with a model the user hosts and stored on the user's machine.

## Commands

```
/personal-vault:index path=~/Desktop/ObsidianSecondVault name=second default=true
/personal-vault:index name=second
/personal-vault:index name=second model=qwen3-embedding host=http://localhost:11434
/personal-vault:ask TLS nerede bitiyor?
/personal-vault:ask vault=second TLS nerede bitiyor?
```

The user writes `key=value`. The skill turns it into `--flag` arguments for the CLI.

### `index` parameters

| Parameter | Default | Meaning |
|---|---|---|
| `path` | required for a new vault | Folder to index |
| `name` | derived from the folder name | Vault name: lowercase letters, digits, `-`, `_` |
| `default` | `false` | `true` makes this vault the default |
| `host` | `http://localhost:11434` | OpenAI-compatible embedding server |
| `model` | `bge-m3` | Embedding model |
| `query_prefix` | empty | Text put before every question (e5: `query: `) |
| `doc_prefix` | empty | Text put before every chunk (e5: `passage: `) |
| `exclude` | empty | Comma-separated globs; replaces the stored list. Password and secret patterns are always excluded |
| `store` | empty (embedded) | Qdrant server URL; empty means embedded mode |
| `rebuild` | `false` | `true` drops the collection and embeds everything again |

`host`, `model`, prefixes, `exclude` and `store` are remembered per vault.

### `ask` parameters

| Parameter | Default | Meaning |
|---|---|---|
| `vault` | the default vault | Vault to search |
| rest of the text | required | The question |

### `vaults`

```
/personal-vault:vaults
/personal-vault:vaults default=second
/personal-vault:vaults remove=second
```

Lists vaults (path, model, chunks, index size, last indexed), changes the default, or deletes a vault's index and registration after the user confirms. The notes folder is never touched. One skill instead of three: all are small registry operations.

### Missing requirements

No session-start hook. Each skill checks `uv` before calling the CLI. The CLI names the fix when the embedding server is unreachable or the model is missing (`ollama pull <model>`). Nothing is printed when everything is in place.

### Parsing rules

- Only known keys are parameters: `path`, `name`, `default`, `host`, `model`, `query_prefix`, `doc_prefix`, `exclude`, `store`, `rebuild`, `vault`. Anything else is part of the question.
- In `ask`, parameters come first. After the first word that is not a known `key=value`, the rest is the question verbatim, so `replicas=3` inside a question stays in the question.
- Paths with spaces are quoted: `path="~/Desktop/My Vault"`.

### Vault resolution

- `path` is required only when the name is new. For a registered name the path comes from the registry.
- A registered name given a different `path` is an error, never a silent overwrite.
- Neither `path` nor `name`: the same rule as `ask` picks the vault.
- Exactly one vault registered: it is used when `vault` is not given.
- Several vaults and none is the default: the command fails and lists the vault names.

## Retrieval model

Bi-encoder: the same model embeds chunks and questions separately, compared by cosine similarity. Some models need different prefixes for questions and documents; a missing prefix degrades search silently, so prefixes are per-vault settings. `bge-m3` needs none.

No reranker (cross-encoder) in the first version. Claude reads the 8 hits and discards the irrelevant ones. The OpenAI-compatible API has no rerank endpoint.

## What must be running

| Part | Running? |
|---|---|
| Embedding server | Yes, for both indexing and asking: the question is embedded with the same model |
| Qdrant | No in embedded mode: `qdrant-client` runs the store inside the Python process on files on disk. Yes if `store` points to a server |
| Docker | No |

An unreachable embedding server gives a clear error naming the URL.

## Code layout

```
personal-vault/
├── .claude-plugin/{plugin.json, marketplace.json}
├── skills/index/SKILL.md      key=value -> CLI flags, reports the result
├── skills/ask/SKILL.md        calls search, Claude writes the answer
├── skills/vaults/SKILL.md     list, remove, change default
├── src/personal_vault/
│   ├── cli.py                 argparse; builds the objects and wires them; index, search, vaults
│   ├── config.py              registry: register, resolve, default
│   ├── models.py              Chunk, Hit, VaultConfig, PersonalVaultError
│   ├── loaders.py             Loader protocol + TextLoader (.md, .txt)
│   ├── chunking.py            split at headings, CHUNKER_VERSION
│   ├── embedders.py           Embedder protocol + OpenAICompatibleEmbedder
│   ├── stores.py              Store protocol + QdrantStore
│   ├── indexing.py            scan, compare, apply
│   └── search.py              embed the question, return the closest chunks
├── tests/
├── pyproject.toml
└── README.md
```

`indexing.py` and `search.py` know only the protocols. `cli.py` builds the concrete objects. A new store or loader is a new class plus one line in `cli.py`. Tests use a fake embedder and Qdrant's in-memory mode.

The skill runs `uv run --project "${CLAUDE_PLUGIN_ROOT}" personal-vault ...`; `uv` installs dependencies on first use. Python 3.10, one dependency: `qdrant-client`. HTTP uses the standard library.

## Store: Qdrant

Embedded mode by default, server mode with `store=`. Same client, same calls. One collection per vault.

| Alternative | Why not first |
|---|---|
| pgvector | Every user would have to run Postgres |
| sqlite-vec | Not 1.0 yet, no server mode |
| LanceDB | Fine fit, but less familiar than Qdrant |

Limit: embedded mode scans every vector per query and warns above 20,000 points; one process at a time. The current vault is an estimated 13,000 chunks (not measured).

## Indexing

- Walks the folder recursively. Skips directories starting with a dot (`.obsidian`, `.git`, `.trash`).
- Splits at markdown headings, max 1500 characters per chunk. Each chunk is embedded with the note title and heading path in front.
- Point id is derived from `relative path + chunk number`.
- Payload: path, chunk number, line, heading, text, file hash.

### Change detection

At the start of a run the `path -> hash` table is read from the payloads (no vectors). Every file on disk is read and hashed. Content hash, not modification time: git checkout, sync tools and restores change the time without changing content.

| Case | Action |
|---|---|
| New file | Embed, insert |
| Same path, same hash | Skip |
| Same path, new hash | Embed new chunks, delete all old points of that path, insert new ones |
| File deleted | Delete its points |
| Moved or renamed (hash of a deleted path) | Copy its points to the new path, no new embedding |
| Excluded later | Delete its points |
| Run interrupted | Embedding happens before deletion; the next run picks up what is left |

### Full rebuild

The registry records an index signature: model, vector size, chunker version, document prefix. If it changes, the collection is rebuilt after a warning. A content hash alone would miss a chunker change. The signature is cleared before a rebuild and written after it finishes, so `ask` refuses a half-built index.

## Privacy

- The index stores note text, so it lives outside the repo in `~/.personal-vault/` (override: `PERSONAL_VAULT_HOME`).
- Paths matching `*password*`, `*passwd*`, `*secret*`, `*credential*`, `*şifre*`, `*sifre*`, `*.env*` are never indexed.
- With a local embedding server nothing leaves the machine at index time. A non-local `host` sends note text to that server; the CLI warns.
- `ask` sends the matching chunks to Claude, like any file Claude Code reads.
- `ask` treats note text as data: it never follows instructions written in a note and never prints a password, token or key found in one.

## `ask` behaviour

1. Embed the question, take the 8 closest chunks.
2. If the question names an exact identifier (service, table, ticket key, file name), also run a plain text search in the vault.
3. Read around a hit when the chunk is cut off.
4. Answer in the question's language, from the notes only, citing `path:line`. Say so when the notes do not answer it.

## Later

- Image and video loaders.
- Reranker as an optional second stage.
- A pgvector store adapter.
- Hybrid (dense + keyword) search inside the store.
