from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vibecomfy.node_packs_git import find_installed_pack_ref


def _git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def test_find_installed_pack_ref_reads_explicit_install_roots_only(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "ComfyUI-KJNodes"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/kijai/ComfyUI-KJNodes.git"], cwd=pack_dir)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pack_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    ignored_root = tmp_path / "ignored"
    ignored_root.mkdir()
    ignored_pack = ignored_root / "ComfyUI-KJNodes"
    ignored_pack.mkdir()
    (ignored_pack / ".git").mkdir()

    match = find_installed_pack_ref(
        "ComfyUI-KJNodes",
        install_roots=[install_root],
        version_pin="deadbeef",
    )

    assert match is not None
    assert match.install_root == install_root
    assert match.pack_ref.slug == "ComfyUI-KJNodes"
    assert match.pack_ref.version == "deadbeef"
    assert match.pack_ref.commit == head
    assert match.pack_ref.url == "https://github.com/kijai/ComfyUI-KJNodes.git"
    assert match.pack_ref.path == str(pack_dir)


def test_find_installed_pack_ref_matches_aux_id(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "repo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "git@github.com:owner/repo.git"], cwd=pack_dir)

    match = find_installed_pack_ref(
        "",
        install_roots=[install_root],
        aux_id="owner/repo",
    )

    assert match is not None
    assert match.pack_ref.slug == "repo"
    assert match.pack_ref.url == "git@github.com:owner/repo.git"
    assert match.pack_ref.name == "repo"


# ---------------------------------------------------------------------------
# T5 — Installed-clone local lookup edge cases
# ---------------------------------------------------------------------------


def test_find_installed_pack_ref_raises_value_error_when_query_and_aux_id_empty(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()

    with pytest.raises(ValueError, match="query or aux_id is required"):
        find_installed_pack_ref("", install_roots=[install_root])


def test_find_installed_pack_ref_returns_none_when_no_match(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "OtherPack"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/kijai/ComfyUI-KJNodes.git"], cwd=pack_dir)

    match = find_installed_pack_ref("NonExistentPack", install_roots=[install_root])

    assert match is None


def test_find_installed_pack_ref_skips_nonexistent_install_root(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist"

    match = find_installed_pack_ref("SomePack", install_roots=[nonexistent])

    assert match is None


def test_find_installed_pack_ref_skips_missing_git_dir(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "NoGitPack"
    pack_dir.mkdir()
    (pack_dir / "README.md").write_text("not a git repo\n", encoding="utf-8")

    match = find_installed_pack_ref("NoGitPack", install_roots=[install_root])

    assert match is None


def test_find_installed_pack_ref_returns_none_for_no_origin(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "NoOrigin"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    # no remote origin added

    match = find_installed_pack_ref("NoOrigin", install_roots=[install_root])

    assert match is None


def test_find_installed_pack_ref_matches_by_dir_name(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "ComfyUI-Foo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/someuser/not-the-same-name.git"], cwd=pack_dir)

    # Query matches dir_name, not origin-derived slug
    match = find_installed_pack_ref("ComfyUI-Foo", install_roots=[install_root])

    assert match is not None
    assert match.pack_ref.slug == "not-the-same-name"
    assert match.pack_ref.name == "ComfyUI-Foo"


def test_find_installed_pack_ref_preserves_version_pin(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "MyPack"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/user/MyPack.git"], cwd=pack_dir)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pack_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    match = find_installed_pack_ref(
        "MyPack",
        install_roots=[install_root],
        version_pin="v1.0.0-pinned",
    )

    assert match is not None
    assert match.pack_ref.version == "v1.0.0-pinned"
    assert match.pack_ref.commit == head


def test_find_installed_pack_ref_empty_install_roots_returns_none(tmp_path: Path) -> None:
    match = find_installed_pack_ref("Anything", install_roots=[])

    assert match is None


def test_find_installed_pack_ref_aux_id_mismatch_returns_none(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "repo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/owner/repo.git"], cwd=pack_dir)

    # aux_id doesn't match the actual origin
    match = find_installed_pack_ref(
        "",
        install_roots=[install_root],
        aux_id="other-owner/other-repo",
    )

    assert match is None


def test_find_installed_pack_ref_first_matching_root_wins(tmp_path: Path) -> None:
    root_a = tmp_path / "root_a"
    root_a.mkdir()
    pack_a = root_a / "SharedName"
    pack_a.mkdir()
    _git(["git", "init"], cwd=pack_a)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_a)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_a)
    (pack_a / "README.md").write_text("a\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_a)
    _git(["git", "commit", "-m", "init"], cwd=pack_a)
    _git(["git", "remote", "add", "origin", "https://github.com/user/SharedName.git"], cwd=pack_a)
    head_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pack_a,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    root_b = tmp_path / "root_b"
    root_b.mkdir()
    pack_b = root_b / "SharedName"
    pack_b.mkdir()
    _git(["git", "init"], cwd=pack_b)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_b)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_b)
    (pack_b / "README.md").write_text("b\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_b)
    _git(["git", "commit", "-m", "init"], cwd=pack_b)
    _git(["git", "remote", "add", "origin", "https://github.com/user/SharedName.git"], cwd=pack_b)

    match = find_installed_pack_ref("SharedName", install_roots=[root_a, root_b])

    assert match is not None
    assert match.install_root == root_a
    assert match.pack_ref.commit == head_a
    assert match.pack_ref.path == str(pack_a)


def test_find_installed_pack_ref_origin_without_dot_git_suffix(tmp_path: Path) -> None:
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    pack_dir = install_root / "repo"
    pack_dir.mkdir()
    _git(["git", "init"], cwd=pack_dir)
    _git(["git", "config", "user.name", "Test User"], cwd=pack_dir)
    _git(["git", "config", "user.email", "test@example.com"], cwd=pack_dir)
    (pack_dir / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=pack_dir)
    _git(["git", "commit", "-m", "init"], cwd=pack_dir)
    _git(["git", "remote", "add", "origin", "https://github.com/owner/repo"], cwd=pack_dir)

    match = find_installed_pack_ref(
        "",
        install_roots=[install_root],
        aux_id="owner/repo",
    )

    assert match is not None
    assert match.pack_ref.slug == "repo"
    assert match.pack_ref.url == "https://github.com/owner/repo"
