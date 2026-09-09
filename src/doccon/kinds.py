# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

from pathlib import Path

CLIENT = "client"
SHOP = "shop"
FIELD = "field"

LABELS = {
    CLIENT: "Client Transmittal",
    SHOP: "Shop Transmittal",
    FIELD: "Field Transmittal",
}

PREFIX = {
    CLIENT: "CT",
    SHOP: "ST",
    FIELD: "FT",
}

BOOK_DIR = {
    CLIENT: Path("3.0 Doc Con") / "3.1 Client Transmittals" / "3.1.1 Out",
    SHOP: Path("3.0 Doc Con") / "3.2 Shop Transmittals",
    FIELD: Path("3.0 Doc Con") / "3.3 Field Transmittals",
}

JOB_CELL = {
    CLIENT: "A12",
    SHOP: "I4",
    FIELD: "I6",
}
