---
name: index
description: Create or refresh a personal-vault index of a notes folder so /personal-vault:ask can search it. Use when the user runs /personal-vault:index, or asks to index, re-index or refresh their vault or Obsidian notes.
argument-hint: "path=<folder> name=<name> default=true host=<url> model=<name> exclude=<glob,glob> rebuild=true"
---

Arguments from the user: `$ARGUMENTS`

## 1. Check uv

Run `command -v uv`. If it prints nothing, tell the user "`uv` is not installed. Install it with `brew install uv` (or see https://docs.astral.sh/uv/)" and stop.

## 2. Parse

The arguments are `key=value` pairs. Known keys and their CLI flags:

| Key | Flag | Notes |
|---|---|---|
| `path` | `--path` | Required only for a new vault. `~` is allowed |
| `name` | `--name` | Lowercase letters, digits, `-`, `_` |
| `default` | `--default` | Only `true` adds the flag; `false` adds nothing |
| `host` | `--host` | OpenAI-compatible embedding server |
| `model` | `--model` | Embedding model |
| `query_prefix` | `--query-prefix` | |
| `doc_prefix` | `--doc-prefix` | |
| `exclude` | `--exclude` | Comma-separated globs; replaces the stored list |
| `store` | `--store` | Qdrant server URL; empty means embedded |
| `rebuild` | `--rebuild` | Only `true` adds the flag |

A value may be quoted: `path="~/My Vault"`. A word that is not a known `key=value` is an error: tell the user which word and stop. Nothing at all is fine; the CLI then picks the default vault.

If the user changes `model`, `doc_prefix` or passes `rebuild=true` on an existing vault, say first that the whole vault is embedded again.

## 3. Run

Pass every value as its own quoted shell word:

```bash
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" personal-vault index --path "<path>" --name "<name>" ...
```

A first run over a large folder takes minutes: run it in the background and report when it finishes. Later runs embed only new and changed files.

## 4. Report

Show the summary lines as printed: vault, path, model, files embedded / unchanged / moved / removed, rebuilt.

On `error:`, show the message as printed; it says what is missing and the command that fixes it. If it names `ollama pull <model>`, offer to run it and do so only on the user's yes.
