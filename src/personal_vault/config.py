import json
import os
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path

from personal_vault.models import PersonalVaultError, VaultConfig

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "bge-m3"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def home_dir() -> Path:
    return Path(os.environ.get("PERSONAL_VAULT_HOME", Path.home() / ".personal-vault"))


def derive_name(folder: Path) -> str:
    ascii_name = unicodedata.normalize("NFKD", folder.name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:64]


class Registry:
    def __init__(self, file: Path, vaults: dict[str, VaultConfig], default: str | None):
        self.file = file
        self.vaults = vaults
        self.default = default

    @classmethod
    def load(cls, file: Path) -> "Registry":
        if not file.exists():
            return cls(file, {}, None)
        data = json.loads(file.read_text())
        vaults = {name: VaultConfig(**values) for name, values in data.get("vaults", {}).items()}
        return cls(file, vaults, data.get("default"))

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "default": self.default,
            "vaults": {name: asdict(vault) for name, vault in self.vaults.items()},
        }
        temporary = self.file.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        temporary.replace(self.file)

    def resolve(self, name: str | None) -> VaultConfig:
        if name is not None:
            if name not in self.vaults:
                raise PersonalVaultError(f"no vault named '{name}'. {self._known()}")
            return self.vaults[name]
        if self.default is not None and self.default in self.vaults:
            return self.vaults[self.default]
        if len(self.vaults) == 1:
            return next(iter(self.vaults.values()))
        if not self.vaults:
            raise PersonalVaultError("no vault indexed yet. Run /personal-vault:index path=<folder>")
        raise PersonalVaultError(f"several vaults and none is the default; pass vault=<name>. {self._known()}")

    def prepare(self, name: str | None, path: str | None) -> VaultConfig:
        folder = Path(path).expanduser().resolve() if path else None
        if folder is not None and not folder.is_dir():
            raise PersonalVaultError(f"not a folder: {folder}")
        if name is None and folder is None:
            return self.resolve(None)
        if name is None:
            name = derive_name(folder)
            if not NAME_PATTERN.match(name):
                raise PersonalVaultError(f"cannot derive a vault name from '{folder.name}'; pass name=<name>")
        elif not NAME_PATTERN.match(name):
            raise PersonalVaultError(f"invalid vault name '{name}': use lowercase letters, digits, '-' and '_'")

        existing = self.vaults.get(name)
        if existing is not None:
            if folder is not None and Path(existing.path) != folder:
                raise PersonalVaultError(
                    f"vault '{name}' already points to {existing.path}; pick another name= for {folder}"
                )
            return existing
        if folder is None:
            raise PersonalVaultError(f"vault '{name}' does not exist yet; pass path=<folder> to create it")
        vault = VaultConfig(name=name, path=str(folder), host=DEFAULT_HOST, model=DEFAULT_MODEL)
        self.vaults[name] = vault
        return vault

    def _known(self) -> str:
        names = ", ".join(sorted(self.vaults)) or "none"
        return f"Known vaults: {names}"
