import argparse
import os
import sys
import urllib.parse
from pathlib import Path

from personal_vault.chunking import CHUNKER_VERSION
from personal_vault.config import Registry, home_dir
from personal_vault.embedders import OpenAICompatibleEmbedder
from personal_vault.indexing import index_vault
from personal_vault.loaders import TextLoader
from personal_vault.models import PersonalVaultError, VaultConfig
from personal_vault.search import search
from personal_vault.stores import QdrantStore

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except PersonalVaultError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="personal-vault")
    commands = parser.add_subparsers(dest="command", required=True)

    index = commands.add_parser("index", help="embed new and changed notes, drop deleted ones")
    index.add_argument("--path", help="folder to index; required for a new vault")
    index.add_argument("--name", help="vault name; default derived from the folder name")
    index.add_argument("--default", action="store_true", help="make this vault the default")
    index.add_argument("--host", help="OpenAI-compatible embedding server")
    index.add_argument("--model", help="embedding model")
    index.add_argument("--query-prefix", help="text put before every question")
    index.add_argument("--doc-prefix", help="text put before every chunk")
    index.add_argument("--exclude", help="comma-separated globs; replaces the stored list")
    index.add_argument("--store", help="Qdrant server URL; empty means embedded mode")
    index.add_argument("--rebuild", action="store_true", help="drop the index and embed everything again")
    index.set_defaults(handler=run_index)

    find = commands.add_parser("search", help="print the chunks closest to a question")
    find.add_argument("question")
    find.add_argument("--vault", help="vault name; default the default vault")
    find.add_argument("-k", type=int, default=8, help="number of chunks")
    find.set_defaults(handler=run_search)
    return parser


def run_index(args: argparse.Namespace) -> None:
    registry = Registry.load(home_dir() / "config.json")
    vault = registry.prepare(args.name, args.path)
    apply_overrides(vault, args)
    if args.default:
        registry.default = vault.name
    warn_if_remote(vault.host)

    embedder = make_embedder(vault)
    store = open_store(vault)
    dimension = len(embedder.embed_documents(["dimension probe"])[0])
    signature = f"{vault.model}|{dimension}|chunker-{CHUNKER_VERSION}|{vault.doc_prefix}"
    rebuild = args.rebuild or not store.exists() or vault.signature != signature
    if rebuild:
        if vault.signature and vault.signature != signature:
            print(f"index settings changed ({vault.signature} -> {signature}); rebuilding", file=sys.stderr)
        vault.signature = ""
        registry.save()
        store.reset(dimension)

    report = index_vault(
        root=_existing_folder(vault),
        loaders={extension: loader for loader in [TextLoader()] for extension in loader.extensions},
        embedder=embedder,
        store=store,
        exclude=vault.exclude,
        progress=print_progress,
    )
    vault.signature = signature
    registry.save()

    default = registry.resolve(None).name if registry.vaults else ""
    print(f"vault: {vault.name}{' (default)' if default == vault.name else ''}")
    print(f"path: {vault.path}")
    print(f"model: {vault.model} ({dimension} dimensions) at {vault.host}")
    print(
        f"files: {report.files} supported, {report.embedded} embedded ({report.chunks} chunks), "
        f"{report.unchanged} unchanged, {report.moved} moved, {report.removed} removed"
    )
    print(f"rebuilt: {'yes' if rebuild else 'no'}")


def run_search(args: argparse.Namespace) -> None:
    registry = Registry.load(home_dir() / "config.json")
    vault = registry.resolve(args.vault)
    store = open_store(vault)
    if not vault.signature or not store.exists():
        raise PersonalVaultError(
            f"vault '{vault.name}' has no complete index; run /personal-vault:index name={vault.name}"
        )
    hits = search(args.question, make_embedder(vault), store, args.k)
    print(f"vault: {vault.name} ({vault.path})\n")
    for hit in hits:
        print(f"### {hit.path}:{hit.line}  score={hit.score:.3f}  {hit.heading}\n{hit.text}\n")


def apply_overrides(vault: VaultConfig, args: argparse.Namespace) -> None:
    if args.host is not None:
        vault.host = args.host
    if args.model is not None:
        vault.model = args.model
    if args.query_prefix is not None:
        vault.query_prefix = args.query_prefix
    if args.doc_prefix is not None:
        vault.doc_prefix = args.doc_prefix
    if args.exclude is not None:
        vault.exclude = [pattern.strip() for pattern in args.exclude.split(",") if pattern.strip()]
    if args.store is not None:
        vault.store = args.store


def make_embedder(vault: VaultConfig) -> OpenAICompatibleEmbedder:
    return OpenAICompatibleEmbedder(
        host=vault.host,
        model=vault.model,
        query_prefix=vault.query_prefix,
        doc_prefix=vault.doc_prefix,
        api_key=os.environ.get("PERSONAL_VAULT_API_KEY"),
    )


def open_store(vault: VaultConfig) -> QdrantStore:
    return QdrantStore.open(vault.name, vault.store, home_dir() / "index" / vault.name)


def warn_if_remote(host: str) -> None:
    if urllib.parse.urlparse(host).hostname not in LOCAL_HOSTS:
        print(f"warning: {host} is not local; note text will be sent to it", file=sys.stderr)


def print_progress(done: int, total: int) -> None:
    if done % 100 == 0 or done == total:
        print(f"  {done}/{total} files", file=sys.stderr, flush=True)


def _existing_folder(vault: VaultConfig) -> Path:
    folder = Path(vault.path)
    if not folder.is_dir():
        raise PersonalVaultError(f"vault '{vault.name}' points to {folder}, which no longer exists")
    return folder
