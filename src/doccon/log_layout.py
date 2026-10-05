# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Cover and document-list cells for CT / ST / FT Excel letters."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from doccon.kinds import CLIENT, FIELD, SHOP


@dataclass(frozen=True)
class BookLayout:
    kind: str
    number_cell: str
    pages_cell: str
    job_cell: str
    from_cell: str
    to_cell: str
    cc_cell: str
    project_cell: str
    customer_cell: str
    site_cell: str
    issued_cell: str
    expected_cell: str
    doc_start_row: int
    page1_last_row: int
    page2_last_row: int
    page3_last_row: int
    notes_row: int
    doc_no_col: int
    rev_col: int
    desc_col: int
    status_col: int
    notes_col: int
    hide_page2: str
    hide_page3: str
    reset_hide: str
    reset_cells: tuple[str, ...]
    statuses: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        data = asdict(self)
        data["reset_cells"] = list(self.reset_cells)
        data["statuses"] = list(self.statuses)
        return data

    def pages_needed(self, line_count: int) -> int:
        if line_count <= 0:
            return 1
        page1 = self.page1_last_row - self.doc_start_row + 1
        page2 = self.page2_last_row - self.doc_start_row + 1
        page3 = self.page3_last_row - self.doc_start_row + 1
        if line_count <= page1:
            return 1
        if line_count <= page2:
            return 2
        if line_count <= page3:
            return 3
        raise ValueError(f"This {self.kind} transmittal holds {page3} documents (3 pages). This pack has {line_count}.")


CLIENT_LAYOUT = BookLayout(
    kind=CLIENT,
    number_cell="A2",
    pages_cell="A3",
    job_cell="A12",
    from_cell="C4",
    to_cell="C6",
    cc_cell="C8",
    project_cell="A10",
    customer_cell="",
    site_cell="",
    issued_cell="C12",
    expected_cell="D12",
    doc_start_row=15,
    page1_last_row=32,
    page2_last_row=62,
    page3_last_row=94,
    notes_row=95,
    doc_no_col=1,
    rev_col=2,
    desc_col=3,
    status_col=4,
    notes_col=5,
    hide_page2="33:62",
    hide_page3="63:94",
    reset_hide="33:94",
    reset_cells=("C12", "D12", "E12"),
    statuses=("APPROVAL", "CONSTRUCTION", "INFORMATION", "REVIEW", "AS-BUILT"),
)

SHOP_LAYOUT = BookLayout(
    kind=SHOP,
    number_cell="C2",
    pages_cell="D2",
    job_cell="I4",
    from_cell="A6",
    to_cell="",
    cc_cell="",
    project_cell="",
    customer_cell="J4",
    site_cell="J6",
    issued_cell="I6",
    expected_cell="",
    doc_start_row=9,
    page1_last_row=32,
    page2_last_row=62,
    page3_last_row=88,
    notes_row=89,
    doc_no_col=1,
    rev_col=7,
    desc_col=9,
    status_col=10,
    notes_col=11,
    hide_page2="33:62",
    hide_page3="63:88",
    reset_hide="33:88",
    reset_cells=("I6",),
    statuses=("IFC", "IFI", "IFU", "PURCHASING ONLY"),
)

FIELD_LAYOUT = BookLayout(
    kind=FIELD,
    number_cell="C2",
    pages_cell="D2",
    job_cell="I6",
    from_cell="A8",
    to_cell="I4",
    cc_cell="",
    project_cell="",
    customer_cell="J6",
    site_cell="J8",
    issued_cell="I8",
    expected_cell="",
    doc_start_row=10,
    page1_last_row=32,
    page2_last_row=62,
    page3_last_row=85,
    notes_row=86,
    doc_no_col=1,
    rev_col=7,
    desc_col=9,
    status_col=10,
    notes_col=11,
    hide_page2="33:62",
    hide_page3="63:85",
    reset_hide="33:85",
    reset_cells=("I8",),
    statuses=("IFC", "IFI"),
)

LAYOUTS = {
    CLIENT: CLIENT_LAYOUT,
    SHOP: SHOP_LAYOUT,
    FIELD: FIELD_LAYOUT,
}


def layout_for(kind: str) -> BookLayout:
    try:
        return LAYOUTS[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown transmittal kind {kind!r}.") from exc
