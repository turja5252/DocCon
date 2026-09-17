# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.drop_pdfs import (
    MSG_SKIP,
    NOT_EMAIL_DROPPED,
    NOT_PDF,
    DropSource,
    apply_board_drop,
    apply_row_drop,
    copy_into_dropped,
    dropped_dir,
    dropped_pdf_filename,
    ingest_sources,
    pick_pdf_for_row,
    rename_email_dropped_pdf,
    resolve_drop_row_key,
    write_pdf_bytes_into_dropped,
)
from doccon.match import (
    EMAIL_DROPPED_LABEL,
    EMAIL_DROPPED_SUFFIX,
    LocatedPdf,
    MatchedRow,
    apply_located_pdfs,
    attach_pdfs,
    keep_located_pdfs,
    pair_pdf,
    pdf_address_text,
    pdf_address_tip,
    pdf_is_email_dropped,
)
from doccon.pack_state import PACK_DIR, ClientPack, load_client_pack, save_client_pack
from doccon.register import DrawingRow
from doccon.win_drop import parse_file_group_descriptor_w


def _row(
    *,
    key: str,
    drawing_id: str,
    title: str = "",
    job_number: str = "2026-Tanzim",
) -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary=f"{drawing_id} {title}".strip(),
            drawing_id=drawing_id,
            title=title,
            status="To Do",
            job_number=job_number,
            outgoing_rev="",
            purpose="",
            parent_summary="Drawing Package",
        ),
        pdf=None,
        confidence="Missing",
    )


def test_copy_into_dropped_then_pair_row(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    src = tmp_path / "Downloads" / "2026-Tanzim-1-1 REV 0.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF-fake")
    copied = copy_into_dropped(job, src)
    assert copied.parent == dropped_dir(job)
    assert copied.parent.parent == job / PACK_DIR
    assert copied.name == "2026-Tanzim-1-1 REV 0.pdf"
    assert copied.read_bytes() == b"%PDF-fake"
    assert src.is_file()
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1", title="Drawing-1")
    paired, leftover = apply_row_drop(row, [copied], "2026-Tanzim")
    assert leftover == []
    assert paired.confidence == "High"
    assert paired.pdf is not None and paired.pdf.path == copied
    assert "Current PDF" not in copied.parts
    assert pdf_is_email_dropped(paired)
    assert pdf_address_text(paired) == f"{copied.name}{EMAIL_DROPPED_SUFFIX}"
    assert pdf_address_text(paired).startswith(copied.name)
    assert pdf_address_tip(paired) == f"{copied.name}{EMAIL_DROPPED_SUFFIX}\n{copied}"
    restored = apply_located_pdfs([row], {row.drawing.key: str(copied)})
    assert restored[0].pdf is not None and restored[0].pdf.path == copied
    assert pdf_is_email_dropped(restored[0])
    assert pdf_address_text(restored[0]) == f"{copied.name}{EMAIL_DROPPED_SUFFIX}"
    assert copied.is_file()
    assert src.is_file()


def test_board_drop_matches_filename_leftover_unmatched(tmp_path: Path) -> None:
    job = tmp_path / "job"
    stwd = write_pdf_bytes_into_dropped(job, "2026-075-STWD REV 0.pdf", b"%PDF-stwd")
    leftover_src = write_pdf_bytes_into_dropped(job, "unrelated-notes.pdf", b"%PDF-other")
    rows = [
        _row(key="P2024-1", drawing_id="2026-075-1-STWD", title="SPIRAL", job_number="2026-075"),
        _row(key="P2024-2", drawing_id="2026-075-1-ZZZ", title="MISSING", job_number="2026-075"),
    ]
    updated, leftover = apply_board_drop(rows, [stwd, leftover_src], "2026-075")
    assert updated[0].drawing.key == "P2024-1"
    assert updated[0].confidence == "High"
    assert updated[0].pdf is not None and updated[0].pdf.path == stwd
    assert pdf_is_email_dropped(updated[0])
    assert pdf_address_text(updated[0]) == f"{stwd.name}{EMAIL_DROPPED_SUFFIX}"
    assert updated[1].confidence == "Missing"
    assert updated[1].pdf is None
    assert leftover == [leftover_src]


def test_non_pdf_rejected(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    note = tmp_path / "readme.txt"
    note.write_text("not a drawing", encoding="utf-8")
    pdfs, skipped = ingest_sources(job, [DropSource(name=note.name, path=note)])
    assert pdfs == []
    assert NOT_PDF in skipped
    assert not dropped_dir(job).exists() or not any(dropped_dir(job).iterdir())


def test_msg_not_paired_as_drawing(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    mail = tmp_path / "Engineer pack.msg"
    mail.write_bytes(b"MSG")
    pdfs, skipped = ingest_sources(job, [DropSource(name=mail.name, path=mail)])
    assert pdfs == []
    assert MSG_SKIP in skipped


def test_sources_from_paths_has_no_istream(tmp_path: Path) -> None:
    from doccon.drop_pdfs import sources_from_paths

    pdf = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
    pdf.write_bytes(b"%PDF")
    sources = sources_from_paths([pdf])
    assert len(sources) == 1
    assert sources[0].path == pdf
    assert sources[0].data is None
    assert "2026-075" not in sources[0].name


def test_ingest_of_a_dropped_path_does_not_clone_it(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    first = write_pdf_bytes_into_dropped(job, "scan0042.pdf", b"%PDF-1.4\nstub\n")
    pdfs, skipped = ingest_sources(job, [DropSource(name=first.name, path=first)])
    assert skipped == []
    assert pdfs == [first]
    clones = list(first.parent.glob("scan0042*.pdf"))
    assert clones == [first]


def test_repaste_same_name_overwrites_dropped(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    first = write_pdf_bytes_into_dropped(job, "scan0042.pdf", b"%PDF-old")
    second = write_pdf_bytes_into_dropped(job, "scan0042.pdf", b"%PDF-new")
    assert second == first
    assert second.name == "scan0042.pdf"
    assert second.read_bytes() == b"%PDF-new"
    assert list(second.parent.glob("scan0042*.pdf")) == [second]
    downloads = tmp_path / "Downloads" / "scan0042.pdf"
    downloads.parent.mkdir()
    downloads.write_bytes(b"%PDF-explorer")
    copied = copy_into_dropped(job, downloads)
    assert copied == first
    assert copied.read_bytes() == b"%PDF-explorer"
    assert downloads.is_file()
    assert "Current PDF" not in copied.parts
    assert list(copied.parent.glob("scan0042*.pdf")) == [copied]


def test_same_batch_two_files_same_name_still_uniques(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    pdfs, skipped = ingest_sources(
        job,
        [
            DropSource(name="scan0042.pdf", data=b"%PDF-a"),
            DropSource(name="scan0042.pdf", data=b"%PDF-b"),
        ],
    )
    assert skipped == []
    assert [path.name for path in pdfs] == ["scan0042.pdf", "scan0042-2.pdf"]
    assert pdfs[0].read_bytes() == b"%PDF-a"
    assert pdfs[1].read_bytes() == b"%PDF-b"


def test_outlook_style_filecontents_bytes_write_dropped(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    dest = write_pdf_bytes_into_dropped(
        job,
        "2026-Tanzim-1-1 REV 0.pdf",
        b"%PDF-1.4\n%FileContents",
    )
    assert dest.parent == job / PACK_DIR / "dropped"
    assert dest.parent.name == "dropped"
    assert dest.parent.parent.name == "DocCon"
    assert dest.read_bytes().startswith(b"%PDF")
    pdfs, skipped = ingest_sources(
        job,
        [DropSource(name="ITP-2026-Tanzim-1 REV 0.pdf", data=b"%PDF-outlook")],
    )
    assert skipped == []
    assert len(pdfs) == 1
    assert pdfs[0].parent == dest.parent
    assert pdfs[0].read_bytes() == b"%PDF-outlook"
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1")
    paired, leftover = apply_row_drop(row, pdfs, "2026-Tanzim")
    assert leftover == []
    assert paired.pdf is not None and paired.pdf.path == pdfs[0]
    assert pdf_is_email_dropped(paired)
    assert pdf_address_text(paired) == f"{pdfs[0].name}{EMAIL_DROPPED_SUFFIX}"


def test_row_drop_picks_matching_name_among_several(tmp_path: Path) -> None:
    job = tmp_path / "job"
    first = write_pdf_bytes_into_dropped(job, "other-sheet.pdf", b"%PDF-a")
    match = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-b")
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1")
    chosen = pick_pdf_for_row(row, [first, match], "2026-Tanzim")
    assert chosen == match
    paired, leftover = apply_row_drop(row, [first, match], "2026-Tanzim")
    assert paired.pdf is not None and paired.pdf.path == match
    assert leftover == [first]
    assert pdf_is_email_dropped(paired)
    assert pdf_address_text(paired) == f"{match.name}{EMAIL_DROPPED_SUFFIX}"


def test_hunt_match_is_not_email_dropped(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    current = job / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    current.mkdir(parents=True)
    real = current / "2026-Tanzim-1-1 REV 0.pdf"
    real.write_bytes(b"%PDF")
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1", title="Drawing-1")
    hunted, _orphans = attach_pdfs([row.drawing], job, "2026-Tanzim")
    assert hunted[0].pdf is not None and hunted[0].pdf.path == real
    assert hunted[0].confidence == "High"
    assert not pdf_is_email_dropped(hunted[0])
    assert pdf_address_text(hunted[0]) == real.name
    assert EMAIL_DROPPED_LABEL not in pdf_address_text(hunted[0])
    assert pdf_address_tip(hunted[0]) == real.name


def test_locate_outside_dropped_clears_bypass(tmp_path: Path) -> None:
    from doccon.drop_pdfs import replace_paired_pdf

    job = tmp_path / "2026-Tanzim"
    dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1")
    paired, _leftover = apply_row_drop(row, [dropped], "2026-Tanzim")
    assert pdf_is_email_dropped(paired)
    downloads = tmp_path / "Downloads" / "2026-Tanzim-1-1 REV 0.pdf"
    downloads.parent.mkdir()
    downloads.write_bytes(b"%PDF-real")
    located = replace_paired_pdf(paired, downloads)
    assert located.pdf is not None and located.pdf.path == downloads
    assert not pdf_is_email_dropped(located)
    assert pdf_address_text(located) == downloads.name
    assert EMAIL_DROPPED_LABEL not in pdf_address_text(located)
    assert not dropped.exists()
    assert downloads.is_file()
    still_in_dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-again")
    still_dropped = pair_pdf(paired, still_in_dropped)
    assert still_in_dropped.is_file()
    assert pdf_is_email_dropped(still_dropped)
    assert pdf_address_text(still_dropped) == f"{still_in_dropped.name}{EMAIL_DROPPED_SUFFIX}"


def test_hunt_replaces_email_drop_bypass(tmp_path: Path) -> None:
    from doccon.drop_pdfs import sweep_replaced_dropped_copies

    job = tmp_path / "2026-Tanzim"
    dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    current = job / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    current.mkdir(parents=True)
    real = current / "2026-Tanzim-1-1 REV 0.pdf"
    real.write_bytes(b"%PDF-hunt")
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1")
    hunted, _orphans = attach_pdfs([row.drawing], job, "2026-Tanzim")
    located = {row.drawing.key: LocatedPdf(path=str(dropped), email_dropped=True)}
    applied = apply_located_pdfs(hunted, located)
    assert applied[0].pdf is not None and applied[0].pdf.path == real
    assert not pdf_is_email_dropped(applied[0])
    assert pdf_address_text(applied[0]) == real.name
    kept = keep_located_pdfs(applied, located)
    assert row.drawing.key not in kept
    sweep_replaced_dropped_copies(applied, located)
    assert not dropped.exists()
    assert real.is_file()


def test_sweep_skips_path_resolve(tmp_path: Path, monkeypatch) -> None:
    from pathlib import Path as PathType

    from doccon.drop_pdfs import sweep_replaced_dropped_copies

    def _boom(self, *args, **kwargs):
        raise AssertionError("Path.resolve would hang on Dropbox during Load")

    monkeypatch.setattr(PathType, "resolve", _boom)
    job = tmp_path / "2026-Tanzim"
    dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    current = job / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    current.mkdir(parents=True)
    real = current / "2026-Tanzim-1-1 REV 0.pdf"
    real.write_bytes(b"%PDF-hunt")
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1")
    hunted, _orphans = attach_pdfs([row.drawing], job, "2026-Tanzim")
    located = {row.drawing.key: LocatedPdf(path=str(dropped), email_dropped=True)}
    sweep_replaced_dropped_copies(hunted, located)
    assert not dropped.exists()
    assert real.is_file()


def test_restore_email_dropped_from_pack_json(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    copied = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    row = _row(key="P2024-15578", drawing_id="2026-Tanzim-1-1")
    pack = ClientPack(
        job_number="2026-Tanzim",
        located_pdfs={row.drawing.key: LocatedPdf(path=str(copied), email_dropped=True)},
    )
    save_client_pack(job, pack)
    loaded = load_client_pack(job, "2026-Tanzim")
    assert loaded is not None
    restored = apply_located_pdfs([row], loaded.located_pdfs)
    assert restored[0].pdf is not None and restored[0].pdf.path == copied
    assert pdf_is_email_dropped(restored[0])
    assert pdf_address_text(restored[0]) == f"{copied.name}{EMAIL_DROPPED_SUFFIX}"
    kept = keep_located_pdfs(restored, loaded.located_pdfs)
    assert kept[row.drawing.key].email_dropped is True


def test_delete_dropped_copy_skips_downloads_and_current_pdf(tmp_path: Path) -> None:
    from doccon.drop_pdfs import delete_dropped_copy, delete_replaced_dropped_copy

    job = tmp_path / "2026-Tanzim"
    dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    downloads = tmp_path / "Downloads" / "2026-Tanzim-1-1 REV 0.pdf"
    downloads.parent.mkdir()
    downloads.write_bytes(b"%PDF-downloads")
    current = job / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    current.mkdir(parents=True)
    real = current / "2026-Tanzim-1-1 REV 0.pdf"
    real.write_bytes(b"%PDF-current")
    assert delete_dropped_copy(downloads) is False
    assert delete_dropped_copy(real) is False
    assert downloads.is_file()
    assert real.is_file()
    assert delete_replaced_dropped_copy(dropped, real) is True
    assert not dropped.exists()
    assert real.is_file()
    assert downloads.is_file()


def test_resolve_drop_row_key_hit_hover_then_selected() -> None:
    assert resolve_drop_row_key("P2024-15578", "P2024-15579", "P2024-1") == "P2024-15578"
    assert resolve_drop_row_key("", None, "P2024-15579") == "P2024-15579"
    assert resolve_drop_row_key(None, "", "P2024-1") == "P2024-1"
    assert resolve_drop_row_key("", None, "  ") is None
    assert "2026-075" not in (resolve_drop_row_key("P2024-15578") or "")


def test_parse_file_group_descriptor_w() -> None:
    name = "2026-Tanzim-1-1 REV 0.pdf"
    desc = bytearray(592)
    encoded = (name + "\0").encode("utf-16-le")
    desc[72 : 72 + len(encoded)] = encoded
    blob = (1).to_bytes(4, "little") + bytes(desc)
    assert parse_file_group_descriptor_w(blob) == [name]


def test_dropped_pdf_filename_uses_id_and_rev() -> None:
    assert dropped_pdf_filename("2026-Tanzim-1-1", "0") == "2026-Tanzim-1-1 REV 0.pdf"
    assert dropped_pdf_filename("2026-Tanzim-1-1", "") == "2026-Tanzim-1-1.pdf"
    assert dropped_pdf_filename("", "") == "drawing.pdf"
    cleaned = dropped_pdf_filename("foo:bar", "1")
    assert ":" not in cleaned
    assert cleaned.endswith(".pdf")


def test_rename_email_dropped_pdf_in_dropped_only(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    copied = write_pdf_bytes_into_dropped(job, "scan0042.pdf", b"%PDF-drop")
    dest, error = rename_email_dropped_pdf(copied, "2026-Tanzim-1-1 REV 0.pdf")
    assert error == ""
    assert dest is not None
    assert dest.name == "2026-Tanzim-1-1 REV 0.pdf"
    assert dest.parent == dropped_dir(job)
    assert dest.read_bytes() == b"%PDF-drop"
    assert not copied.exists()
    same, empty = rename_email_dropped_pdf(dest, "2026-Tanzim-1-1 REV 0.pdf")
    assert empty == ""
    assert same == dest


def test_rename_refuses_a_locate_current_pdf(tmp_path: Path) -> None:
    real = tmp_path / "2.0 Drafting" / "Current PDF" / "2026-Tanzim-1-1 REV 0.pdf"
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_bytes(b"%PDF-real")
    dest, error = rename_email_dropped_pdf(real, "other.pdf")
    assert dest is None
    assert error == NOT_EMAIL_DROPPED
    assert real.is_file()
    assert real.read_bytes() == b"%PDF-real"


def test_rename_collision_uses_a_numbered_name(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    first = write_pdf_bytes_into_dropped(job, "keep.pdf", b"%PDF-keep")
    second = write_pdf_bytes_into_dropped(job, "scan.pdf", b"%PDF-scan")
    dest, error = rename_email_dropped_pdf(second, "keep.pdf")
    assert error == ""
    assert dest is not None
    assert dest.name == "keep-2.pdf"
    assert first.read_bytes() == b"%PDF-keep"
    assert dest.read_bytes() == b"%PDF-scan"
