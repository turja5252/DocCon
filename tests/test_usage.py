# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json
from pathlib import Path

from doccon import usage


def test_filed_transmittals_add_up_across_pcs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(usage, "usage_dir", lambda: tmp_path)
    monkeypatch.setenv("COMPUTERNAME", "Sarah Laptop")
    usage.record_transmittal(cover="CT-2026-Tanzim-1", job="2026-Tanzim", kind="client")
    usage.record_transmittal(cover="", job="2026-Tanzim", kind="client")
    usage.record_transmittal(cover="ST-2026-Tanzim-2", job="2026-Tanzim", kind="shop")
    other = tmp_path / "usage-Tanzim.jsonl"
    other.write_text(
        json.dumps({"at": "2026-10-13T12:00:00", "cover": "FT-2026-Tanzim-1", "job": "2026-Tanzim", "kind": "field"})
        + "\nnot json\n"
        + json.dumps({"at": "2026-10-13T12:01:00", "cover": ""})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "usage-Sarah Laptop (conflicted copy).jsonl").write_text(
        json.dumps({"cover": "CT-2026-Tanzim-9"}) + "\n",
        encoding="utf-8",
    )
    assert usage.transmittal_count() == 3
    lines = [json.loads(line) for line in (tmp_path / "usage-Sarah-Laptop.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [line["cover"] for line in lines] == ["CT-2026-Tanzim-1", "ST-2026-Tanzim-2"]
