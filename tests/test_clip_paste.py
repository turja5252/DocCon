# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Paste PDF: the clipboard is read in the child helper, never in the GUI process."""
from __future__ import annotations

import subprocess
from pathlib import Path

import doccon.clip_paste as clip_paste
from doccon.clip_paste import (
    NO_PDF_ON_CLIPBOARD,
    RESULT_PREFIX,
    clipboard_pdfs,
    format_paste_result,
    parse_paste_output,
    paste_argv,
    paste_result_path,
)
from doccon.drop_host import run_paste
from doccon.drop_pdfs import DropSource

SRC = Path(__file__).resolve().parents[1] / "src" / "doccon"


def test_paste_argv_runs_the_child_helper_not_the_gui(tmp_path: Path) -> None:
    argv = paste_argv(tmp_path)
    assert "-m" in argv
    assert "doccon.drop_host" in argv
    assert "--paste" in argv
    assert str(tmp_path) in argv


def test_frozen_paste_argv_reuses_the_exe_without_opening_a_second_gui(
    tmp_path: Path, monkeypatch
) -> None:
    """Sarah's laptop runs Elite DocCon.exe. `-m doccon.drop_host` is ignored and
    a second console window opens; --paste must be a flag on the same exe."""
    monkeypatch.setattr(clip_paste.sys, "frozen", True, raising=False)
    monkeypatch.setattr(clip_paste.sys, "executable", r"C:\DocCon\Elite DocCon.exe")
    result = tmp_path / "out.json"
    argv = paste_argv(tmp_path, result=result)
    assert argv[0].endswith("Elite DocCon.exe")
    assert "-m" not in argv
    assert "doccon.drop_host" not in argv
    assert argv[1] == "--paste"
    assert "--inbox" in argv
    assert "--result" in argv
    assert str(result) in argv


def test_frozen_entry_dispatches_paste_before_tk() -> None:
    text = (SRC.parent / "doccon" / "__main__.py").read_text(encoding="utf-8")
    paste_at = text.find("--paste")
    gui_at = text.find("from doccon.gui")
    assert 0 <= paste_at < gui_at


def test_result_line_round_trips(tmp_path: Path) -> None:
    one = tmp_path / "2026-Tanzim-1-1 REV A.pdf"
    two = tmp_path / "2026-Tanzim-1-2 REV 0.pdf"
    line = format_paste_result([one, two])
    assert line.startswith(RESULT_PREFIX)
    assert parse_paste_output(f"noise\n{line}\n") == [one, two]


def test_parse_ignores_junk_and_empty_output() -> None:
    assert parse_paste_output("") == []
    assert parse_paste_output("some warning\n") == []
    assert parse_paste_output(f"{RESULT_PREFIX}not-json") == []


def test_cf_hdrop_paths_are_staged_for_pairing(tmp_path: Path, monkeypatch, capsys) -> None:
    """Stubbed CF_HDROP file paths become staged PDFs the parent can pair."""
    source = tmp_path / "outlook"
    source.mkdir()
    pdf = source / "2026-Tanzim-1-1 REV A.pdf"
    pdf.write_bytes(b"%PDF-1.7\nstub\n")
    inbox = tmp_path / "inbox"

    monkeypatch.setattr(
        "doccon.clip_read.read_clipboard_sources",
        lambda *_a, **_k: [DropSource(name=pdf.name, path=pdf, data=None)],
    )
    assert run_paste(inbox) == 0
    staged = parse_paste_output(capsys.readouterr().out)
    assert len(staged) == 1
    assert staged[0].parent == inbox
    assert staged[0].read_bytes().startswith(b"%PDF")


def test_repaste_same_name_overwrites_inbox(tmp_path: Path, monkeypatch, capsys) -> None:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(
        "doccon.clip_read.read_clipboard_sources",
        lambda *_a, **_k: [DropSource(name="scan0042.pdf", data=b"%PDF-old")],
    )
    assert run_paste(inbox) == 0
    first = parse_paste_output(capsys.readouterr().out)
    assert first[0].name == "scan0042.pdf"
    monkeypatch.setattr(
        "doccon.clip_read.read_clipboard_sources",
        lambda *_a, **_k: [DropSource(name="scan0042.pdf", data=b"%PDF-new")],
    )
    assert run_paste(inbox) == 0
    second = parse_paste_output(capsys.readouterr().out)
    assert second[0] == first[0]
    assert second[0].name == "scan0042.pdf"
    assert second[0].read_bytes() == b"%PDF-new"
    assert sorted(path.name for path in inbox.glob("scan0042*.pdf")) == ["scan0042.pdf"]


def test_paste_several_keep_original_filenames(tmp_path: Path, monkeypatch, capsys) -> None:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(
        "doccon.clip_read.read_clipboard_sources",
        lambda *_a, **_k: [
            DropSource(name="2025-124-1-TL REV 0.pdf", data=b"%PDF-one"),
            DropSource(name="Elite Integrity CF Tank Loading Point.pdf", data=b"%PDF-two"),
        ],
    )
    assert run_paste(inbox) == 0
    staged = parse_paste_output(capsys.readouterr().out)
    assert [path.name for path in staged] == [
        "2025-124-1-TL REV 0.pdf",
        "Elite Integrity CF Tank Loading Point.pdf",
    ]
    assert staged[0].read_bytes() == b"%PDF-one"
    assert staged[1].read_bytes() == b"%PDF-two"


def test_empty_clipboard_gives_the_operator_a_message(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("doccon.clip_read.read_clipboard_sources", lambda *_a, **_k: [])
    assert run_paste(tmp_path / "inbox") == 0
    assert parse_paste_output(capsys.readouterr().out) == []
    assert "Copy" in NO_PDF_ON_CLIPBOARD
    assert "Paste PDF" in NO_PDF_ON_CLIPBOARD
    assert "one or more" in NO_PDF_ON_CLIPBOARD


def test_child_crash_does_not_raise_into_the_parent(tmp_path: Path, monkeypatch, capsys) -> None:
    def boom(*_a, **_k) -> list[DropSource]:
        raise OSError("simulated native fault")

    monkeypatch.setattr("doccon.clip_read.read_clipboard_sources", boom)
    assert run_paste(tmp_path / "inbox") == 0
    assert parse_paste_output(capsys.readouterr().out) == []


def test_clipboard_pdfs_survives_a_dead_helper(tmp_path: Path, monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("helper missing")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(clip_paste.os, "name", "nt")
    assert clipboard_pdfs(tmp_path) == []


def test_clipboard_pdfs_drops_paths_the_helper_did_not_write(tmp_path: Path, monkeypatch) -> None:
    real = tmp_path / "real.pdf"
    real.write_bytes(b"%PDF-1.4\n")
    ghost = tmp_path / "ghost.pdf"

    class Done:
        returncode = 0
        stdout = format_paste_result([real, ghost])
        stderr = ""

    monkeypatch.setattr(clip_paste.os, "name", "nt")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Done())
    assert clipboard_pdfs(tmp_path) == [real]


def test_clipboard_pdfs_reads_result_file_when_stdout_empty(tmp_path: Path, monkeypatch) -> None:
    """Frozen noconsole exe cannot print; the child writes --result instead."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    pdf = inbox / "scan0042.pdf"
    pdf.write_bytes(b"%PDF-1.4\nstub\n")

    class Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **_kwargs):
        assert "--result" in argv
        dest = Path(argv[argv.index("--result") + 1])
        dest.write_text(format_paste_result([pdf]) + "\n", encoding="utf-8")
        return Done()

    monkeypatch.setattr(clip_paste.os, "name", "nt")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert clipboard_pdfs(inbox) == [pdf]
    leftovers = list(inbox.glob(".doccon-paste-*.json"))
    assert leftovers == [], "parent must delete the sidecar after reading it"


def test_run_paste_writes_the_result_sidecar(tmp_path: Path, monkeypatch, capsys) -> None:
    pdf = tmp_path / "outlook" / "a.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"%PDF-1.4\nstub\n")
    inbox = tmp_path / "inbox"
    result = tmp_path / "paste.json"
    monkeypatch.setattr(
        "doccon.clip_read.read_clipboard_sources",
        lambda *_a, **_k: [DropSource(name=pdf.name, path=pdf, data=None)],
    )
    assert run_paste(inbox, result=result) == 0
    staged = parse_paste_output(capsys.readouterr().out)
    assert staged
    assert parse_paste_output(result.read_text(encoding="utf-8")) == staged


def test_paste_result_path_is_not_a_pdf(tmp_path: Path) -> None:
    path = paste_result_path(tmp_path, token="9")
    assert path.name.startswith(".doccon-paste-")
    assert not path.name.casefold().endswith(".pdf")


def _imported_modules(text: str) -> set[str]:
    found: set[str] = set()
    for line in text.splitlines():
        token = line.strip()
        if token.startswith(("from doccon.", "import ")):
            found.add(token.split()[1])
    return found


def test_gui_never_imports_the_filecontents_extract() -> None:
    """clip_read / win_drop hold the COM surface. gui.py must not pull them in."""
    gui = (SRC / "gui.py").read_text(encoding="utf-8")
    gui_imports = _imported_modules(gui)
    assert "doccon.clip_read" not in gui_imports
    assert "doccon.win_drop" not in gui_imports
    assert "extract_drop_sources" not in gui
    assert "from doccon.clip_paste import" in gui

    parent_imports = _imported_modules((SRC / "clip_paste.py").read_text(encoding="utf-8"))
    assert "doccon.win_drop" not in parent_imports
    assert "doccon.clip_read" not in parent_imports
    assert "ctypes" not in parent_imports

    child = (SRC / "clip_read.py").read_text(encoding="utf-8")
    assert "extract_drop_sources" in child
    assert "OleGetClipboard" in child
    assert "paste_dataobject_into_folder" in child
    assert "paste_dataobject_into_folder" not in gui


def test_needs_folder_paste_only_when_names_have_no_bytes() -> None:
    from doccon.clip_read import needs_folder_paste

    assert needs_folder_paste([]) is False
    assert needs_folder_paste([DropSource(name="a.pdf", data=b"%PDF")]) is False
    assert needs_folder_paste([DropSource(name="a.pdf", path=Path("a.pdf"))]) is False
    assert needs_folder_paste([DropSource(name="a.pdf"), DropSource(name="b.pdf")]) is True
    assert needs_folder_paste(
        [DropSource(name="a.pdf", data=b"%PDF"), DropSource(name="b.pdf")]
    ) is True


def test_merge_folder_paths_fills_missing_by_name(tmp_path: Path) -> None:
    from doccon.clip_read import merge_folder_paths

    one = tmp_path / "a.pdf"
    two = tmp_path / "b.pdf"
    one.write_bytes(b"%PDF-a")
    two.write_bytes(b"%PDF-b")
    merged = merge_folder_paths(
        [DropSource(name="a.pdf"), DropSource(name="b.pdf")],
        [one, two],
    )
    assert [item.path for item in merged] == [one, two]


def test_empty_filecontents_uses_explorer_folder_paste(tmp_path: Path, monkeypatch, capsys) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    one = inbox / "2025-124-1-TL REV 0.pdf"
    two = inbox / "Elite Integrity CF Tank Loading Point.pdf"

    def fake_read(_dest=None):
        return [
            DropSource(name="2025-124-1-TL REV 0.pdf"),
            DropSource(name="Elite Integrity CF Tank Loading Point.pdf"),
        ]

    def fake_paste(folder: Path) -> list[Path]:
        dest = Path(folder)
        left = dest / one.name
        right = dest / two.name
        left.write_bytes(b"%PDF-one")
        right.write_bytes(b"%PDF-two")
        return [left, right]

    monkeypatch.setattr("doccon.clip_read.read_clipboard_sources", fake_read)
    monkeypatch.setattr("doccon.clip_read.paste_clipboard_into_folder", fake_paste)
    assert run_paste(inbox) == 0
    staged = parse_paste_output(capsys.readouterr().out)
    assert [path.name for path in staged] == [one.name, two.name]
    assert staged[0].read_bytes() == b"%PDF-one"
    assert staged[1].read_bytes() == b"%PDF-two"

