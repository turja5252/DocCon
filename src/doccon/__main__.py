# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import os
import sys


def _wants_paste(argv: list[str]) -> bool:
    return "--paste" in argv


if __name__ == "__main__":
    # Frozen Elite DocCon.exe has no `python -m`. Paste PDF re-launches this exe
    # with --paste; handle that before Tk or a second console window opens.
    if _wants_paste(sys.argv[1:]):
        from doccon.drop_host import main as helper_main

        raise SystemExit(helper_main(sys.argv[1:]))

    from doccon.diag import log, log_session_start

    log_session_start(step="session")
    log("INFO", "session", f"pid={os.getpid()} launching gui (before Tk)")
    from doccon.gui import main

    raise SystemExit(main())
