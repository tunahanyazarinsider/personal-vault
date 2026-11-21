import pytest

from personal_vault.config import Registry, derive_name
from personal_vault.models import PersonalVaultError


@pytest.fixture
def registry(tmp_path):
    return Registry.load(tmp_path / "config.json")


def test_new_vault_needs_a_path(registry):
    with pytest.raises(PersonalVaultError, match="pass path="):
        registry.prepare("second", None)


def test_name_is_derived_from_folder(tmp_path, registry):
    folder = tmp_path / "Obsidian Second Vault"
    folder.mkdir()
    assert registry.prepare(None, str(folder)).name == "obsidian-second-vault"
    assert derive_name(tmp_path / "Kişisel Notlar") == "kisisel-notlar"


def test_registered_name_with_another_path_is_rejected(tmp_path, registry):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    registry.prepare("notes", str(tmp_path / "a"))
    with pytest.raises(PersonalVaultError, match="already points to"):
        registry.prepare("notes", str(tmp_path / "b"))
    assert registry.prepare("notes", None).path == str((tmp_path / "a").resolve())


def test_resolve_picks_single_vault_then_requires_default(tmp_path, registry):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    registry.prepare("a", str(tmp_path / "a"))
    assert registry.resolve(None).name == "a"

    registry.prepare("b", str(tmp_path / "b"))
    with pytest.raises(PersonalVaultError, match="none is the default"):
        registry.resolve(None)

    registry.default = "b"
    assert registry.resolve(None).name == "b"


def test_registry_round_trips_through_disk(tmp_path, registry):
    (tmp_path / "a").mkdir()
    vault = registry.prepare("a", str(tmp_path / "a"))
    vault.exclude = ["*draft*"]
    registry.default = "a"
    registry.save()

    loaded = Registry.load(tmp_path / "config.json")
    assert loaded.default == "a"
    assert loaded.vaults["a"].exclude == ["*draft*"]


def test_invalid_name_is_rejected(tmp_path, registry):
    (tmp_path / "a").mkdir()
    with pytest.raises(PersonalVaultError, match="invalid vault name"):
        registry.prepare("My Notes", str(tmp_path / "a"))
