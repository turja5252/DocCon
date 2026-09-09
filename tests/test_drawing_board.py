# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import tkinter as tk

import pytest

from doccon.drawing_board import DrawingBoard
from doccon.match import MatchedRow
from doccon.register import DrawingRow


def _row(*, key: str = "P2024-1", drawing_id: str = "2026-Tanzim-1-1") -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary=f"{drawing_id} Drawing",
            drawing_id=drawing_id,
            title="Drawing",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="A",
            purpose="Info",
            parent_summary="Drawing Package",
        ),
        pdf=None,
        confidence="Missing",
    )


def test_now_next_and_pack() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        assert board.pending_rows() == []
        assert board.selected_keys() == ("P2024-1",)
        board._blocks["P2024-1"].nexts["outgoing_rev"].set("0")
        board._blocks["P2024-1"].nexts["purpose"].set("Approval")
        board._blocks["P2024-1"].nexts["client_document_number"].set("CNRL-T-101")
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.outgoing_rev == "0"
        assert pending[0].drawing.purpose == "Approval"
        assert pending[0].drawing.client_document_number == "CNRL-T-101"
        packed = board.selected_rows()
        assert packed[0].drawing.outgoing_rev == "0"
        board._blocks["P2024-1"].include.set(False)
        assert board.selected_rows() == []
        assert board.pending_rows()
        board._blocks["P2024-1"].include.set(True)
        board._blocks["P2024-1"].nexts["outgoing_rev"].set("A")
        board._blocks["P2024-1"].nexts["purpose"].set("Info")
        board._blocks["P2024-1"].status_next.set("IFI")
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.status == "IFI"
        assert pending[0].drawing.outgoing_rev == "A"
    finally:
        root.destroy()


def test_batch_applies_to_pack_only() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        board._blocks["P2024-2"].include.set(False)
        count = board.apply_next_to_pack(status="In Progress", fields={"outgoing_rev": "0", "purpose": "Approval"})
        assert count == 1
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.key == "P2024-1"
        assert pending[0].drawing.status == "In Progress"
        assert pending[0].drawing.outgoing_rev == "0"
        assert board._blocks["P2024-2"].status_next.get() == "To Do"
        board.set_pack(True)
        assert board.selected_keys() == ("P2024-1", "P2024-2")
        assert board.apply_next_to_pack() == 0
    finally:
        root.destroy()
