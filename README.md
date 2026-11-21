# personal-vault

A Claude Code plugin that answers questions from local folders of notes: an Obsidian vault or any tree of `.md` and `.txt` files.

Notes are embedded by a model you host and stored on your machine. Claude reads the matching chunks and answers with `path:line` citations.

## Requirements

The plugin installs none of these; both must be on your machine before the first `index`.

| Needed | Install | Check |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | `brew install uv` | `uv --version` |
| An OpenAI-compatible embedding server with a model | [Ollama](https://ollama.com), then `ollama pull bge-m3` | `curl localhost:11434/api/version` |

The embedding server must be running whenever you index or ask: the question is embedded with the same model as the notes. If something is missing, the command stops and prints what to install.

Any other OpenAI-compatible server works (HF TEI, vLLM, LM Studio, OpenAI): pass `host=` and `model=` to `index`.

Nothing else is needed: the vector store (Qdrant) runs inside the plugin's Python process, on files in `~/.personal-vault/`. The first command takes a few seconds longer while `uv` installs the Python dependencies.

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

### `vaults`

```
/personal-vault:vaults
/personal-vault:vaults default=notes
/personal-vault:vaults remove=notes
```

Lists every vault with its path, model, chunk count, index size and last index time; changes the default; or deletes a vault's index after asking. Removing a vault never touches the notes.

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
