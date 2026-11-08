"""検査に渡すスタックごとの値（stack profile の qa と course-spec の qa を合わせたもの）。

`edu-creator check` が環境変数 EDU_CREATOR_QA_JSON に入れて検査を起動する。
値が無いまま黙って既定値で動くと、別のスタックの教材を別の規則で検査して緑になるので、無ければ止める。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV = "EDU_CREATOR_QA_JSON"

_raw = os.environ.get(ENV)
if not _raw:
    raise SystemExit(f"{ENV} が無い。検査は `edu-creator check` から動かす")

CONFIG: dict = json.loads(_raw)


def _manifest_root_files() -> frozenset[str]:
    rel = CONFIG.get("real_root_files_manifest")
    if not rel:
        return frozenset()
    manifest = Path(CONFIG["repo_root"]) / rel
    entries = json.loads(manifest.read_text(encoding="utf-8"))["entries"]
    return frozenset(
        e["path"]
        for e in entries
        if e.get("category") == "写経" and "path" in e and "/" not in e["path"]
    )


CODE_LANGS: frozenset[str] = frozenset(CONFIG["code_langs"])
REAL_PREFIXES: tuple[str, ...] = tuple(CONFIG["real_prefixes"])
REAL_ROOT_FILES: frozenset[str] = frozenset(CONFIG.get("real_root_files", [])) | _manifest_root_files()
CROSSREF_IGNORE: frozenset[str] = frozenset(CONFIG.get("crossref_ignore", []))
GUI_SERVICES: tuple[str, ...] = tuple(CONFIG.get("gui_services", []))
