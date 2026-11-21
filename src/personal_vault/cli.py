import argparse
import os
import shutil
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from personal_vault.chunking import CHUNKER_VERSION
from personal_vault.config import Registry, home_dir
from personal_vault.embedders import OpenAICompatibleEmbedder
from personal_vault.evaluation import evaluate, load_cases
from personal_vault.indexing import index_vault
from personal_vault.loaders import TextLoader
from personal_vault.models import PersonalVaultError, VaultConfig
from personal_vault.search import LINKED_LIMIT, link_sources, search
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
    find.add_argument("--linked", type=int, default=LINKED_LIMIT, help="extra chunks from notes linked with the hits")
    find.set_defaults(handler=run_search)

    check = commands.add_parser("eval", help="measure how often the expected note is among the hits")
    check.add_argument("--file", required=True, help='JSON list of {"question": "...", "path": "..."}')
    check.add_argument("--vault", help="vault name; default the default vault")
    check.add_argument("-k", type=int, default=8, help="number of chunks")
    check.set_defaults(handler=run_eval)

    vaults = commands.add_parser("vaults", help="list vaults, remove one, or change the default")
    vaults.add_argument("--remove", metavar="NAME", help="delete a vault's index and registration")
    vaults.add_argument("--default", metavar="NAME", help="make a vault the default")
    vaults.set_defaults(handler=run_vaults)
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
    vault.chunks = store.count()
    vault.indexed_at = datetime.now().isoformat(sep=" ", timespec="minutes")
    registry.save()

    default = registry.resolve(None).name if registry.vaults else ""
    print(f"vault: {vault.name}{' (default)' if default == vault.name else ''}")
    print(f"path: {vault.path}")
    print(f"model: {vault.model} ({dimension} dimensions) at {vault.host}")
    print(
        f"files: {report.files} supported, {report.embedded} embedded ({report.chunks} chunks), "
        f"{report.unchanged} unchanged, {report.empty} empty, {report.moved} moved, {report.removed} removed"
    )
    print(f"index: {vault.chunks} chunks")
    print(f"rebuilt: {'yes' if rebuild else 'no'}")


def run_search(args: argparse.Namespace) -> None:
    vault, store = open_indexed(args.vault)
    found = search(args.question, make_embedder(vault), store, args.k, args.linked)
    print(f"vault: {vault.name} ({vault.path})\n")
    for hit in found.hits:
        print(f"### {hit.path}:{hit.line}  score={hit.score:.3f}  {hit.heading}\n{hit.text}\n")
    if found.linked:
        print("## Linked notes\n")
    for hit in found.linked:
        sources = ", ".join(link_sources(hit, found.hits))
        print(f"### {hit.path}:{hit.line}  score={hit.score:.3f}  {hit.heading}\nlinked with: {sources}\n{hit.text}\n")


def run_eval(args: argparse.Namespace) -> None:
    cases = load_cases(Path(args.file).expanduser())
    vault, store = open_indexed(args.vault)
    indexed = store.file_hashes()
    for case in cases:
        if case.path not in indexed:
            print(f"warning: {case.path} is not in the index", file=sys.stderr)
    results = evaluate(cases, make_embedder(vault), store, args.k)
    found = [result for result in results if result.rank]
    print(f"vault: {vault.name}")
    print(f"questions: {len(results)}")
    print(f"found in top {args.k}: {len(found)}/{len(results)} ({100 * len(found) / len(results):.0f}%)")
    with_linked = [result for result in results if result.rank or result.in_linked]
    print(f"found with linked notes: {len(with_linked)}/{len(results)}")
    print(f"first hit: {sum(1 for result in found if result.rank == 1)}/{len(results)}")
    print(f"mean reciprocal rank: {sum(1 / result.rank for result in found) / len(results):.2f}")
    for result in results:
        if not result.rank:
            print(f"missed: {result.case.question}\n  expected {result.case.path}\n  top hit  {result.top_path}")


def run_vaults(args: argparse.Namespace) -> None:
    registry = Registry.load(home_dir() / "config.json")
    if args.remove is not None:
        vault = registry.resolve(args.remove)
        if vault.store:
            open_store(vault).drop()
        else:
            shutil.rmtree(index_folder(vault.name), ignore_errors=True)
        del registry.vaults[vault.name]
        if registry.default == vault.name:
            registry.default = None
        registry.save()
        print(f"removed vault '{vault.name}'; the notes in {vault.path} were not touched")
    if args.default is not None:
        registry.default = registry.resolve(args.default).name
        registry.save()
        print(f"default vault: {registry.default}")
    if args.remove is None and args.default is None:
        print_vaults(registry)


def print_vaults(registry: Registry) -> None:
    if not registry.vaults:
        print("no vaults yet. Create one with /personal-vault:index path=<folder>")
        return
    default = registry.default if registry.default in registry.vaults else None
    if default is None and len(registry.vaults) == 1:
        default = next(iter(registry.vaults))
    for name in sorted(registry.vaults):
        vault = registry.vaults[name]
        print(f"{name}{' (default)' if name == default else ''}")
        print(f"  path: {vault.path}")
        print(f"  model: {vault.model} at {vault.host}")
        print(f"  store: {vault.store or 'embedded, ' + folder_size(index_folder(name))}")
        print(f"  chunks: {vault.chunks or 'unknown'}")
        print(f"  indexed: {vault.indexed_at or 'unknown'}")
        if vault.exclude:
            print(f"  exclude: {', '.join(vault.exclude)}")


def folder_size(folder: Path) -> str:
    total = sum(file.stat().st_size for file in folder.rglob("*") if file.is_file()) if folder.is_dir() else 0
    return f"{total / 1_000_000:.0f} MB"


def index_folder(name: str) -> Path:
    return home_dir() / "index" / name


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
    return QdrantStore.open(vault.name, vault.store, index_folder(vault.name))


def open_indexed(name: str | None) -> tuple[VaultConfig, QdrantStore]:
    vault = Registry.load(home_dir() / "config.json").resolve(name)
    store = open_store(vault)
    if not vault.signature or not store.exists():
        raise PersonalVaultError(
            f"vault '{vault.name}' has no complete index; run /personal-vault:index name={vault.name}"
        )
    return vault, store


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
