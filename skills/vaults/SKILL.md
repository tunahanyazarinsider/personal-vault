---
name: vaults
description: List the personal-vault note indexes, remove one, or change the default. Use when the user runs /personal-vault:vaults, or asks which vaults exist, how big an index is, to delete a vault's index, or to switch the default vault.
argument-hint: "[remove=<name>] [default=<name>]"
---

Arguments from the user: `$ARGUMENTS`

## 1. Check uv

Run `command -v uv`. If it prints nothing, tell the user "`uv` is not installed. Install it with `brew install uv` (or see https://docs.astral.sh/uv/)" and stop.

## 2. Parse

Known keys: `remove=<name>` and `default=<name>`. Anything else is an error: name the word and stop. No arguments means list.

## 3. Run

List:

```bash
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" personal-vault vaults
```

Show the vaults as a table: name (mark the default), path, model, chunks, store size, last indexed.

Change the default:

```bash
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" personal-vault vaults --default "<name>"
```

Remove. This deletes the index and cannot be undone; building it again means embedding every note again. First run the list, show the user that vault's path, chunk count and size, and ask them to confirm. Only on a yes:

```bash
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}" personal-vault vaults --remove "<name>"
```

The notes folder itself is never touched; say so in the report.

On `error:`, show the message as printed.
