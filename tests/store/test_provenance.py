import json
import re
import subprocess

from daiff.store.provenance import (
    REQUIRED_TAGS,
    build_tags,
    code_commit,
    compute_run_id,
    sha256_file,
)


def test_compute_run_id_is_deterministic_order_free_and_12_hex():
    a = compute_run_id("c" * 64, "abc", ["h1", "h2"])
    assert a == compute_run_id("c" * 64, "abc", ["h2", "h1"])
    assert re.fullmatch(r"[0-9a-f]{12}", a)
    assert a != compute_run_id("c" * 64, "abd", ["h1", "h2"])


def test_build_tags_is_portable_and_timestamp_free(tmp_path):
    f = tmp_path / "raw" / "dem.tif"
    f.parent.mkdir()
    f.write_bytes(b"x")
    tags = build_tags(
        run_id="r" * 12,
        config_hash="c" * 64,
        code_commit="abc",
        model_id="n/a",
        inputs=[f],
        data_root=tmp_path,
        data_versions={"synthetic": "seed=42"},
        year=None,
        t0=2019,
    )
    assert set(REQUIRED_TAGS) <= tags.keys()
    assert json.loads(tags["DAIFF_INPUTS"]) == [{"path": "raw/dem.tif", "sha256": sha256_file(f)}]
    assert tags["DAIFF_YEAR"] == "n/a" and tags["DAIFF_T0"] == "2019"
    assert not any(re.search(r"\d{4}-\d{2}-\d{2}T\d{2}", v) for v in tags.values())


def test_code_commit_reports_clean_dirty_and_unknown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (repo / "f.txt").write_text("1")
    subprocess.run([*git, "add", "f.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
    clean = code_commit(repo)
    assert re.fullmatch(r"[0-9a-f]{40}", clean)
    (repo / "f.txt").write_text("2")
    assert code_commit(repo) == clean + "-dirty"
    assert code_commit(tmp_path / "not_a_repo") == "unknown"
