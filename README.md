# personal-vault

A Claude Code plugin that answers questions from local folders of notes: an Obsidian vault or any tree of `.md` and `.txt` files.

Notes are embedded by a model you host and stored on your machine. Claude reads the matching chunks and answers with `path:line` citations.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- An OpenAI-compatible embedding server, running whenever you index or ask. With [Ollama](https://ollama.com): `ollama pull bge-m3`

Nothing else: the vector store (Qdrant) runs inside the plugin's Python process, on files in `~/.personal-vault/`.

## Install

```
/plugin marketplace add <path or git URL of this repo>
/plugin install personal-vault@personal-vault
```

## Use

```
/personal-vault:index path=~/notes name=notes default=true
/personal-vault:index name=notes
/personal-vault:ask what did I write about TLS termination?
/personal-vault:ask vault=notes replicas=3 nerede ayarlı?
```

### `index`

| Parameter | Default | Meaning |
|---|---|---|
| `path` | required for a new vault | Folder to index |
| `name` | derived from the folder name | Vault name |
| `default` | `false` | Make this vault the default |
| `host` | `http://localhost:11434` | Embedding server: Ollama, HF TEI, vLLM, LM Studio, OpenAI |
| `model` | `bge-m3` | Embedding model; pick a multilingual one for mixed-language notes |
| `query_prefix` | empty | Text before every question, for models that need one (e5: `query: `) |
| `doc_prefix` | empty | Text before every chunk (e5: `passage: `) |
| `exclude` | empty | Comma-separated globs on the relative path; replaces the stored list |
| `store` | empty | Qdrant server URL; empty uses the embedded store |
| `rebuild` | `false` | Embed everything again |

Settings are remembered per vault. Set `PERSONAL_VAULT_API_KEY` if the server needs a bearer token.

### `ask`

`vault=<name>` first, then the question. Without `vault`, the default vault is used; with a single vault, that one.

## How indexing works

- Walks the folder recursively, skipping directories that start with a dot (`.obsidian`, `.git`, `.trash`).
- Splits each note at headings, then into chunks of at most 1500 characters. The note title and heading path are embedded with each chunk.
- Each file's content hash is stored with its chunks. Unchanged files are skipped, changed files have all old chunks replaced, renamed files keep their vectors, deleted or newly excluded files are removed.
- Changing the model, the document prefix or the chunker rebuilds the index, because the old vectors are not comparable.

Paths matching `*password*`, `*passwd*`, `*secret*`, `*credential*`, `*şifre*`, `*sifre*` or `*.env*` are never indexed.

## Privacy

The index holds the text of your notes and lives in `~/.personal-vault/` (override with `PERSONAL_VAULT_HOME`), outside this repo. With a local embedding server nothing leaves your machine at index time; a non-local `host` receives your note text, and the CLI warns. At question time the matching chunks go to Claude, like any file Claude Code reads.

## Limits

- Dense search only; the `ask` skill adds a plain text search for exact identifiers.
- The embedded store compares every vector on each query and is meant for one person's notes. For more than ~20,000 chunks, run a Qdrant server and pass `store=`.
- One process at a time per vault in embedded mode.

## Development

```
uv run pytest
uv run personal-vault --help
```

Design notes: [plan/design.md](plan/design.md).
