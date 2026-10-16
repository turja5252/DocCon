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
    monkeypatch.setenv("USERNAME", "SarahChan")
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
    (tmp_path / "usage-Sarah-Laptop.jsonl").open("a", encoding="utf-8").write(
        json.dumps({"event": "jira", "job": "2026-050", "operator": "SarahChan"})
        + "\n"
        + json.dumps({"event": "eddi", "job": "2026-050", "operator": "SarahChan"})
        + "\n"
        + json.dumps(
            {"event": "jira", "job": "2026-Tanzim", "operator": "TanzimNasir", "cover": "CT-2026-Tanzim-8", "kind": "client"}
        )
        + "\n"
    )
    assert usage.transmittal_count() == 2
    assert usage.usage_counts() == {"ct": 1, "st": 1, "ft": 0, "jira": 1, "eddi": 1}
    assert usage.usage_summary() == "CT 1\nST 1\nFT 0\nJira updates 1\nEDDI creations 1"
    lines = [json.loads(line) for line in (tmp_path / "usage-Sarah-Laptop.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [line["cover"] for line in lines[:2]] == ["CT-2026-Tanzim-1", "ST-2026-Tanzim-2"]
    assert lines[0]["operator"] == "SarahChan"
