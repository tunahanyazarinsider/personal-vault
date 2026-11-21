import json
from dataclasses import dataclass
from pathlib import Path

from personal_vault.embedders import Embedder
from personal_vault.models import PersonalVaultError
from personal_vault.search import search
from personal_vault.stores import Store


@dataclass
class Case:
    question: str
    path: str


@dataclass
class CaseResult:
    case: Case
    rank: int
    top_path: str


def load_cases(file: Path) -> list[Case]:
    try:
        rows = json.loads(file.read_text())
    except (OSError, ValueError) as error:
        raise PersonalVaultError(f"cannot read the questions file {file}: {error}") from error
    if not isinstance(rows, list) or not rows:
        raise PersonalVaultError(f"{file} must hold a non-empty JSON list")
    cases = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("question"), str) or not isinstance(row.get("path"), str):
            raise PersonalVaultError(f'{file}: every entry must look like {{"question": "...", "path": "..."}}')
        cases.append(Case(question=row["question"], path=row["path"]))
    return cases


def evaluate(cases: list[Case], embedder: Embedder, store: Store, limit: int) -> list[CaseResult]:
    results = []
    for case in cases:
        paths = [hit.path for hit in search(case.question, embedder, store, limit)]
        rank = paths.index(case.path) + 1 if case.path in paths else 0
        results.append(CaseResult(case=case, rank=rank, top_path=paths[0] if paths else ""))
    return results
