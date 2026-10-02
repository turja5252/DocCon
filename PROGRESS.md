# Progress log

Newest first. Append a dated entry when a decision is locked, a test runs, or the next step changes.

## 2026-10-01 — Shop addresses in Settings (1.94)

Settings has **Shop transmittal TO / CC** beside **Field transmittal TO / CC**. Both are this PC only. Shop cover uses the shop list when the ST letter and the saved pack are empty. Pick… on Shop uses that list. Client saved addresses stay the client list. **Elite DocCon.exe** is **1.94**.

## 2026-10-01 — Fast on every PC (1.93)

Load paints the drawing list when Jira returns. The Dropbox folder hunt, PDF names, the letter, and the PEP finish after that. PDF matching reads filenames and does not stat the file. The shared WPS library is scanned after the job's own PDFs. Next editors are created for the first screen; the rest of the list stays labels until it is scrolled into view. The exe asks Windows for per-monitor DPI so a 125% or 150% laptop is not a stretched bitmap, and the Pack box has a dark border. **Elite DocCon.exe** was rebuilt as **1.93** on 2026-10-01. Close every old DocCon and open that file. Load `2026-Tanzim`. Do not Confirm 075.

## 2026-10-01 — Return shortcuts on the calendar (1.92)

Tanzim: the Urgent / 7 days / 14 days buttons take space on the console. They belong on the Expected return calendar, with N/A.

**Built.** That row is Date issued and Expected return only. Open the Expected return calendar for Urgent same day, Urgent +1, 7 days, 14 days, No return, and N/A. Same actions as before. Drawing-row calendars are unchanged. Source is **1.92**. The exe is still **1.87**.

## 2026-10-01 — Popups follow the console screen (1.91)

Tanzim: message boxes and the other windows always opened on the main monitor, even when DocCon was on the other screen.

**Built.** Settings, Create new Jira Issue, the EDDI prompt, Rename, and Preview open centered on the console. Windows message boxes and file pickers use a tiny owner on that same screen, so they open there too. Source is **1.91**. The exe is still **1.87**.

## 2026-10-01 — Submitted to Client For on the filter row (1.90)

Tanzim: a pack is never every drawing, so **Pack all** is not needed. **Submitted to Client For** should be a visible dropdown, and a pick should land on the packed rows.

**Built.** Pack all is off the Filter row. Submitted to Client For (Approval / Info / Planned / NA) sits beside Set packed to. A pick stamps packed Next and turns it yellow. Blank restores that Next to Now. A Pack tick uses the current pick; a blank pick does not wipe a typed Next. Jira is still written only on Create transmittal or Update Jira. Source is **1.90**. The exe is still **1.87**.

## 2026-10-01 — Load stays clickable (1.89)

Sarah’s exe sat there and ignored clicks. Load was waiting on her Dropbox: walking PDFs, and opening the transmittal book and the PEP on the window thread. Online-only files make that take minutes, and the window either ignores clicks or Windows marks it not responding.

**Built.** The drawing list paints when Jira returns. PDF matching, the letter, and the PEP finish after that, off the window thread. A book that already has the job name is not opened on Load. The list paints two rows at a time so a long pack does not freeze the window. Source is **1.89**. The exe she used is still **1.87**.

## 2026-10-01 — Elite DocCon 1.87 exe

**Exe rebuilt 2026-10-01** — `Elite DocCon.exe` is **1.87**. Close every old DocCon; double-click that file. Load `2026-Tanzim`. Do not Confirm 075.

Includes the parent-job book, No return on IFI/IFC, the Non Jira group, Field TO/CC defaults, the Shop folder pick, red delete buttons, green Add PDF…, Paste PDF from email, button borders and hover, and the mouse wheel leaving dropdowns alone.

## 2026-10-01 — Delete and add buttons (1.84)

Clear, Cancel Next, and Remove are red. Add PDF… is green. Restart to **1.84**.

## 2026-10-01 — Shop folder pick (1.83)

Tanzim: shop drawings go in `1.0 Current IFC Drawings`, and each file can land in the root or in a subfolder (`1.0.1 MID Sheets`, `1.0.6 BOM`, …). The transmittal form is still saved in the job Doc Con folder. The email attaches only that form.

**Built.** Shop rows, including Non Jira, show a folder pick. Default is **Root**. Create transmittal copies each packed PDF there, replaces an older rev of the same drawing, and copies `ST-{job}-{n}.pdf` into `Transmittals` under that shop folder. The Doc Con copy in `3.2 Shop Transmittals` stays. No zip. If the engineer has not created the `1.0` job folder, Create transmittal writes nothing. **Locate shop folder…** remembers the folder on this PC.

Tests: find the shop folder, child job subfolder, rev replace, form in Transmittals — **29 passed** with confirm, pack, and settings.

Source is **1.83**. Frozen exe is still **1.77**.

## 2026-10-01 — Field transmittal TO / CC defaults (1.82)

Tanzim: Field TO and CC are not the client list. Settings should let the operator add field-transmittal addresses, and those are the defaults.

**Built.** Settings **Field transmittal TO / CC** is stored on this PC (LOCALAPPDATA), not Dropbox. Add to TO / Add to CC. When Field is selected, those addresses fill the cover if the FT letter and the saved pack TO/CC are empty. A filled letter or pack still wins. Pick… on Field offers that list. Client saved addresses are unchanged.

Source is **1.82**. Frozen exe is still **1.77**.

## 2026-10-01 — Non Jira group on the drawing list (1.81)

Tanzim: a file with no Jira issue should be a row in the drawing table, in its own group, like EDDI 1–9. Only the letter fields are editable. Locate, Open, and Preview stay on the row.

**Built.** Header **Non Jira** sits after groups 1–9. The row is packed. Document number, description, outgoing rev, and the letter status edit in the row. The other Next fields stay blank. **Add PDF…** browses a file in with no drawing selected. **Include with pack** moves a New PDFs file into the group. **Remove** drops the Non Jira row that is clicked. Create transmittal prints packed Non Jira lines after the drawings and zips those PDFs. Jira and the EDDI snapshot are unchanged. **Packed only** keeps the header when one of those rows is packed.

Tests: Non Jira row group, disabled Jira fields, pack JSON — **13 passed** with confirm.

Source is **1.81**. Frozen exe is still **1.77**. Restart DocCon from source to see it. Do not Confirm 075.

## 2026-10-01 — With this pack, no Jira issue (1.80)

Tanzim: some files are pasted or browsed and still go on the transmittal, with no Jira issue and no EDDI line. Locate… only exists on a drawing row, so there was no browse for those files.

**Built.** **With this pack** sits under New PDFs once a job is loaded. **Add PDF…** opens the file picker in the job folder and does not need a selected row. **Include with pack** takes the PDF picked in New PDFs. Each item has a document number (from the filename), a rev when the name has `REV n`, a description, and the letter status (Client / Shop / Field default **INFORMATION**). Create transmittal prints those lines after the packed drawings and adds the PDFs to the zip. Jira and EDDI are unchanged. A pack can be only these files. They save in `client-pack.json`. Success clears the list and deletes an email-dropped copy. A Dropbox file is not copied into `dropped/`.

Tests: filename rev, letter status, pack JSON, and zip order — **20 passed** with pack state and confirm.

Source is **1.80**. Frozen exe is still **1.77**.

## 2026-09-30 — No return date for IFI / IFC (1.79)

Tanzim: a send for Info (status IFI or IFC) does not expect a document back. There needs to be an explicit no-return choice, and IFI/IFC should set that automatically.

**Built.** **No return** beside the Expected return presets stamps packed Next Return Request Date to N/A and sets the letter to N/A. A calendar day still overwrites it. The Expected return calendar’s own N/A still restores Now. **Set packed to IFI or IFC**, a pack tick while that is selected, or picking IFI/IFC on a row, stamps that row’s Return Request Date to N/A. Confirm writes Jira `null` for that date and for Due Date. Blank and N/A are the same when Jira had no date, so an empty row does not turn yellow.

Tests: No return stamp, IFC/IFI pack tick, and Jira null for the cleared dates — passed with the board, register, gui, and client-log suites (**145 passed**, 2 skipped).

Source is **1.79**. Frozen exe is still **1.77**.

## 2026-09-30 — Child Job Number files the parent transmittal book (1.78)

Tanzim: Jira Job Number `2026-077-1` already opens Dropbox folder `2026-077`, but Create transmittal still asked for `CT-2026-077-1.xlsm`. The book in `3.1.1 Out` is `CT-2026-077.xlsm`.

**Built.** Lookup tries the typed name, then the parent (`2026-077-1`, then `2026-077`) for CT, ST, FT, and the live EDDI form. Exact child book still wins. The opened book’s job cell is left as `2026-077`, and the cover is `CT-2026-077-n`. A blank template is not renamed to `CT-2026-077-1` when the parent book is already there. Dated EDDI snapshot uses the live form’s name (`EDDI-2026-077-{date}`).

Tests: parent-book lookup, job-cell keep, EDDI parent form, confirm, and book adopt — **43 passed**.

No exe yet. Source is **1.78**. Frozen `Elite DocCon.exe` is still **1.77**.

## 2026-09-30 — Packed only stacks rows (1.77)

Tanzim: Packed only left drawings in their original holes, so a handful of ticks looked sparse. Hidden unpacked rows (and empty EDDI groups) now collapse; the remaining packed rows stack like a normal filter. Same for the text Find filter.

Tests: packed-only hide/stack/intersect plus frozen-row sync, board, and gui — **115 passed, 1 skipped (Tk).**

**Exe rebuilt 2026-09-30** — `Elite DocCon.exe` is **1.77**. Close every old DocCon; double-click that file. Load `2026-Tanzim`. Do not Confirm 075.

## 2026-09-18 — Preview box grabs Description (1.76)

Tanzim: Databook-style preview, but as a **window** next to **Open**, not a pane on the console. Draw a box to fill **Next Description** (yellow). Native PDF text first; OCR only if the box is empty. Do not auto-read title blocks on Load. Restore point: git branch `backup/1.75-before-preview` at `78e987c`.

**Built.** PyMuPDF preview dialog (zoom, pan, box). Confirm / Update Jira still write Jira.

Tests: **412 passed, 1 skipped (Tk).** Ruff clean on the touched files.

**Exe rebuilt 2026-09-18** — `Elite DocCon.exe` is **1.76**. Close every old DocCon; double-click that file. Load `2026-Tanzim`. Do not Confirm 075.

## 2026-09-17 — Locate… starts in the loaded job folder (1.75)

Tanzim: first Locate PDF after Load should be the Dropbox job folder DocCon matched, then remember the folder he browses. Every new Load resets to that job’s folder — not the last PC-wide locate dir from the previous job.

**Exe rebuilt 2026-09-17** — `Elite DocCon.exe` is **1.75**. Close every old DocCon; double-click that file. Load `2026-Tanzim`. Do not Confirm 075.

## 2026-09-17 — Set packed to is Jira Status (1.74)

Tanzim: outgoing revs are never the same across a pack, so Set packed to should not stamp rev. Pick **OFA** (or IFI, …) then whatever is packed gets yellow Next Status — same as Date issued / Expected return. Blank restores packed Status to Now. Pack-tick with blank does not wipe. Bump packed still steps each Outgoing Rev. Jira is not written until Create transmittal / Update Jira.

**Exe rebuilt 2026-09-17** — `Elite DocCon.exe` is **1.74**. Close every old DocCon; double-click that file. Load `2026-Tanzim`. Do not Confirm 075.

## 2026-09-17 — Create transmittal / Create EDDI (1.73)

Tanzim: navy Confirm… / EDDI… / Update Jira… should name what they create. **Create transmittal** and **Create EDDI**; **Update Jira…** stays. Same commands. No exe.

## 2026-09-17 — Date issued and Expected return visible (1.72)

Tanzim: 1.71 hid the two cover dates by parking them on Cover with TO/CC. They are back on a slim row under the navy bar (Urgent presets, Locate PEP, Save with them). Cover stays FROM / TO / CC / project. Batch Next still starts hidden. No exe.

## 2026-09-17 — Ergonomic chrome, Cover, and hidden Batch Next (1.71)

Tanzim: happy with the engine; wants vertical space for the drawing list. Navy title + Job/Load/Confirm are one row. Cover holds Date issued / Expected return / PEP; TO/CC/PROJECT are two lines; the how-to paragraph is gone. **Batch Next** (Apply to Pack + field boxes) starts hidden behind **Batch Next…**. Pack all / none, Cancel Next, Bump packed, Set packed stay on the Filter row. No exe.

Tests: **402 passed, 2 skipped (Tk).**

Load `2026-Tanzim`. Do not Confirm 075.

## 2026-09-17 — Leftover drag hint off the navy bar (1.70)

Tanzim: console still said **Drop a PDF on a drawing row**. Drag never came back (1.60). That teal leftover next to **Paste PDF** is gone. Ingest stays Copy then Paste PDF / Ctrl+V, or the watched folder. No exe.

## 2026-09-17 — Create waits for the new row (1.69)

Tanzim: 1.68 Create worked but the new Sub-task was missing after reload (Jira JQL lag). The load meter now stays up through **Creating on Jira…**, **Created {id} ({key})**, **Fetching from Jira…**. Fetch GETs the new issue by key and merges it into the pack if search is late. Navy button is compact two-line **Create new Jira Issue**. No exe.

Tests: **402 passed, 1 skipped (Tk).**

Load `2026-Tanzim`. Do not Confirm 075.

## 2026-09-17 — New issue… creates a Jira Sub-task (1.68)

Operator agreed the dialog: Parent, EDDI, JIRA ID, Description. Job Number and Project Lead copy from the epic.

**Built.** Navy identity row **New issue…** (after Locate job folder…, Brand, disabled until Load). Dialog Create writes `POST /rest/api/3/issue` as a Sub-task (`10013`) under the picked Task. EDDI 1–9 by option id (createmeta). Generic (0) is not offered. JIRA ID preflight same as Confirm (no blank, no inner space). Description may be blank. Then the pack reloads. Not transmittal Confirm. No exe.

Load `2026-Tanzim`. Do not Confirm 075.

Tests: **398 passed, 1 skipped (Tk).** Ruff clean on the touched files.

## 2026-09-17 — Create Jira Sub-task from the console (locked, not built)

Operator agreed: Parent, EDDI, JIRA ID, Description.

**Lock.** With a job loaded, create is always a **Sub-task** (`issuetype` `10013`) under an existing **Task** that is a child of the loaded job **Project** (the epic). Do not create a Task or a Project. **POST `/rest/api/3/issue` immediately** (needs a key for pairing) — not a yellow Next, not transmittal Confirm. Then reload the pack.

**Operator types/picks:** Parent Task (Tasks under that Project; Job Number search is fallback if there is no Project); EDDI Status 1–9 only (not Generic `0`); JIRA ID; Description (may be blank). Same summary compose as the board (ID + space + description; preflight rejects a blank or internal-whitespace ID).

**Copied, not asked:** Jira project `P2024`; Job Number `customfield_10300` from the epic (abort if the epic has none); Project Lead / Sponsor `customfield_10071` from the epic (account ids; omit if empty — do not use the `P2024` software project lead). Reporter stays Jira’s default.

Rev, dates, Client Doc No., and labels stay off the create dialog. Sandbox `2026-Tanzim` only. Do not Confirm 075. Console stays **1.67**. Not built.

## 2026-09-17 — Investigate creating a Jira issue from the console (not built)

Operator: there may be a need to create the Jira issue from DocCon. Always a **Sub-task**. Always a **parent Task** on the same Job Number. Jira will not create the issue without some essentials.

**Live read** (GET only, Tanzim token, `P2024`, dummy job `2026-Tanzim`). No issue was created. Console stays **1.67**.

**Today.** DocCon never `POST /rest/api/3/issue`. Load searches; Confirm `PUT`s fields and `POST`s transitions. `DrawingRow` keeps `parent_summary`, not the parent key. Tanzim’s token **does** have `CREATE_ISSUES`.

**Types in P2024.** Only three: Task `10012`, Sub-task `10013`, Project `10014`. Create is always `issuetype.id = 10013`.

**Sub-task createmeta required (no default):** `project` (always `P2024` on Load), `parent` (existing Task key), `summary` (JIRA ID + Description), **EDDI Status** `customfield_10289` (one option, write by id). **Reporter** is required but Jira defaults it. Issue Type is on the create screen; send `10013` anyway.

**Job Number lock:** copy `customfield_10300` from the job **Project** (the epic), not typed, not from the parent Task. Jira does not require it on Sub-task create; DocCon still writes it so Load finds the new Sub-task. If the Project has no Job Number, abort create.

**Project Lead / Sponsor** `customfield_10071` (People, multi). Required to **create the Project/epic**, not required on Sub-task (or Task) create. Live template already copies it down: Tanzim on `2026-Tanzim` Project → Drawing Package → dummy drawing; Anton Vo on `2026-075` / `2026-096` Project → package Task. **Lock:** copy the same people from the epic onto the new Sub-task (account ids), same as Job Number. Do not use the Jira software project lead for `P2024` (that is Tanzim for the whole site). If the epic has no Lead, omit it — Sub-task create still succeeds. Labels are optional. Outgoing Rev / purpose / dates / Client Doc No. are optional.

**EDDI option ids** (Sub-task create and editmeta on `P2024-15578` match): Generic `10231`; 1–9 `10166`–`10174`. Generic (0) would create then vanish from the board (`visible_pack_rows`). Do not offer 0.

**Parent Tasks on `2026-Tanzim` (all Job Number `2026-Tanzim`, all EDDI Generic, so none appear on the board):** Drawing Package `P2024-15577` (Drafting), QC Package, Engineering Package, Databook Package, Document Transmittals (`DocCon`), Burn Programs, Project Completion Activities. Dummy drawings sit under Drawing Package. A parent picker cannot use the pack list — it must search Tasks. 2026-08-21: drawings do not go under Document Transmittals.

**Parent list — two hunts, same list on live jobs.** There is no Epic type in `P2024` (only Project / Task / Sub-task). The job card is issuetype **Project** (hierarchy 1), one per Job Number on Tanzim / 075 / 096 / 049. Method A: `issuetype = Task AND Job Number ~ job`. Method B (Load already walks this): that one Project, then `issuetype = Task AND parent = {Project key}`. On those four jobs the Task keys matched 7/7, 7/7, 1/1, 7/7. Direct children of the Project were Tasks only (no stray Sub-tasks). `2026-096` has a single Task (Manway Package), not the seven-pack template. `2026-049-1` / `-2` have no Project of their own. Method B still finds a Task if Job Number was never copied onto it; Method A would miss that. If Load has no Project (`MISSING_JIRA_PROJECT`), Method B cannot run. If two Project issues share a Job Number, do not silent-pick (same as Locate job folder). Preferred picker: Tasks that are children of the loaded job Project. Fallback: Tasks with this Job Number. Do not Confirm 075 (read only).

**Create writes Jira immediately** (needs an issue key for pairing). Not a Next edit. Sandbox only: `2026-Tanzim`. Do not Confirm 075. Do not create parent Tasks in this flow.

Dialog lock (2026-09-17): operator picks Parent + EDDI + JIRA ID / Description. See the lock entry above. Labels still not copied unless asked.

## 2026-09-17 — Rename… for email-dropped PDFs only (1.67)

Sarah: email attachments sometimes need a different client filename. Tanzim: no rename if the source PDF is on Dropbox (**Locate…**).

**Lock built.** **Rename…** next to Locate / Open only when the pair is an **email dropped** copy in `{job}/3.0 Doc Con/DocCon/dropped/`. Dialog pre-fills `{JIRA ID} REV {Outgoing Rev}.pdf` from Next (else Now); **Use drawing name** restores that. Renames the staged copy only. Yellow **email dropped** stays. Confirm zip uses the new name. `REV n` in the new name stamps Next Outgoing Rev (does not reset other Next). Locate / hunt / Current PDF: the button is not shown; the Dropbox file is not renamed. Cancel Next does not undo a rename. Do not auto-file into Current PDF. Do not rewrite Jira.

**Exe rebuilt 2026-09-17** — `Elite DocCon.exe` is **1.67**. Sarah: close every old DocCon, double-click that file. Load `2026-Tanzim`. Paste a PDF — **Rename…** appears; Locate a Current PDF — it does not. Do not Confirm 075.

Tests: **391 passed, 2 skipped (Tk).** Ruff clean on the touched files.

## 2026-09-17 — Rename PDF is only for email-dropped copies (locked, not built)

Sarah: sometimes an email attachment must go out under a different name. Tanzim: no renaming feature if the source PDF is on Dropbox (**Locate…**).

**Lock.** **Rename…** (not built yet) exists only when the paired file is an **email dropped** copy in `{job}/3.0 Doc Con/DocCon/dropped/`. Locate… / hunt / a Current PDF pair: no Rename…, no rename of the Dropbox file. Pairing stays on the Jira issue key. After a rename, the PDF cell keeps **email dropped** yellow under the new filename; Confirm zip uses that name; `REV n` in the new name stamps Next Outgoing Rev the same as Paste. Do not auto-file into `2.0 Drafting/Current PDF`. Do not rewrite Jira. Cancel Next does not undo a rename.

Not built. Console stays **1.66**. Do not Confirm 075.

## 2026-09-16 — Frozen Paste PDF opened a second DocCon (1.66)

Operator on Sarah’s laptop (1.65 exe): Paste PDF opened another suite window; closing it said nothing copied. Same Copy works on Tanzim’s PC from source.

**Cause.** Helper argv was `[Elite DocCon.exe, -m, doccon.drop_host, --paste]`. The frozen bootloader ignores `-m`. `__main__.py` always imported the GUI, so the child was a second console. Closing it made the parent’s `subprocess.run` return empty stdout → **No PDF on the clipboard**. Windowed (`console=False`) exe also cannot print to the parent’s pipe.

**Fix.** `--paste` is handled before Tk. Frozen spawn is the same exe with `--paste --inbox --result` (never `-m`). Child writes a sidecar JSON because noconsole stdout is empty. `PYINSTALLER_RESET_ENVIRONMENT=1` so the nested onefile unpacks its own `_MEI`. Source still uses `python -m doccon.drop_host --paste`. Drag is not back.

Console is **1.66**. Rebuild `Elite DocCon.exe` for Sarah. Load `2026-Tanzim`. Do not Confirm 075.

Tests: **385 passed, 2 skipped (Tk).** Ruff clean on the touched files.

## 2026-09-16 — Focused row tint + filename rev + no Outlook hunt button + Date issued today (1.65)

Operator: highlighted row needs a tint; pairing should guess Outgoing Rev from the filename; **PDF from Outlook** does not work — get rid of it; Date issued should not start at N/A; Expected return needs same-day / +1 / 7 / 14 presets.

**Focus.** `FOCUS_BG` is a pale teal wash (`#D5EFEB`), not the gray `BORDER` fill. ACCENT rules stay. A focused Next cell takes the same wash behind the ACCENT border. Dirty Next and **email dropped** stay `PENDING_BG` amber. The band still does not paint into a Next cell.

**Rev.** Paste PDF, Assign, Locate…, and a watched-folder pair stamp Next Outgoing Rev from `… REV n` / `(Rev n)` in the filename (first token: `ITP-… REV 0 Signed.pdf` → `0`). Yellow when it differs from Jira Now. No REV in the name leaves Next alone. Load hunt does not mass-dirty matched rows. Nothing writes Jira until Confirm.

**PDF from Outlook button gone.** Paste PDF / Ctrl+V stays. Watched folder stays. Settings **Import from Outlook…** (GAL/Contacts) stays. Drag is not back.

**Cover dates.** Date issued is **today** on open, Load, and Cancel Next (not restored from `client-pack.json`). Expected return still starts **N/A**. Presets beside Expected return: **Urgent same day**, **Urgent +1**, **7 days**, **14 days** (calendar days from Date issued, or today if Date issued is blank/N/A). Pack-tick with today stamps packed Next Submission Date. N/A on a cover date still restores that packed Next to Now.

Console is **1.65**. Close every old DocCon. Sarah runs the new `Elite DocCon.exe`. Load `2026-Tanzim`. Do not Confirm 075.

Tests: **382 passed.** Ruff clean on the touched files.

## 2026-09-16 — Paste PDF uses Explorer's folder paste when FileContents is empty (1.64)

Operator: Paste PDF still **No PDF on the clipboard** on 1.63 (single file and several). Same Copy **does** paste into a Windows folder. Log `15:25:19` `version=1.63`: `names=1` `2025-124-1-TL REV 0.pdf`, `FileContents index=0 GetData hr=0x0 GetDataHere hr=0x0 tymed=4 bytes=0`, `ok=0`. Clipboard is not empty. Outlook returns an empty IStream; Explorer writes the files with `IFileOperation::CopyItems` / the folder `IDropTarget`.

**Fix.** When FileContents has names but no bytes, the paste child pastes that IDataObject into the inbox the same way Explorer pastes into a folder, then stages those PDFs. Empty ISTREAM is not a successful GetData — later tymed (HGLOBAL) still run. Drag is not back. Re-paste overwrite of leftover names stays.

Console is **1.64** (source). **Operator confirmed 2026-09-16 15:34 — “Bingo!!!”** Paste of Outlook Copy now lands. Drag is still later. Do not Confirm 075. No exe.

Tests: **384 passed, 2 skipped (Tk).** Ruff clean on the touched files.

## 2026-09-16 — 1.62 hold-mediums emptied every Outlook FileContents stream (1.63)

Operator on 1.62: Paste PDF dialog **No PDF on the clipboard**. Log is not an empty clipboard. Session `version=1.62` at 15:14:47. Six Paste PDF clicks 15:15:03–15:15:47. First two: `names=2` `2025-124-1-TL REV 0.pdf,Elite Integrity CF Tank Loading Point.pdf` then `FileContents miss index=0 tried=[0, -1]`, `FileContents index=1 GetData hr=0x0 tymed=4 bytes=0`, `extract … names=2 hdrop=0 ok=0`, `paste helper pdfs=0`. Then four single-file pastes: `names=1` the TL PDF, `ok=0`. 1.61 at 14:59 had the same two names and `ok=1`.

**Cause.** 1.62 held FILEGROUPDESCRIPTOR and every FileContents STGMEDIUM, then read. Outlook’s clipboard IStream is already empty by then. Empty GetData (`hr=0`, tymed=ISTREAM, 0 bytes) skipped GetDataHere because a medium had been returned.

**Fix.** Release the descriptor after parsing names. GetData + read + release each FileContents index immediately. Empty GetData still tries GetDataHere. Never fall back to lindex 0 for a later file. Drag is not back. Re-paste overwrite of leftover inbox / `dropped` names stays.

Console is **1.63** (source). Close every old DocCon, launch from source, Load `2026-Tanzim`. Copy one Outlook PDF, Paste PDF; then Copy several, Paste PDF. Both names, no `-N`. Do not Confirm 075. No exe. No drag.

Tests: **379 passed, 1 skipped (Tk).** Ruff clean on `win_drop.py` and `test_win_drop.py`. Sequential get-read-release, empty GetData still uses GetDataHere, descriptor released before FileContents. Never fall back to lindex 0.

## 2026-09-16 — Paste of several Outlook attachments stages every file, original names (1.62)

Operator: Copy several Outlook PDFs, Paste PDF, still only the first file, and leftover copies pile up as `…-21.pdf`. The 1.61 log still had `names=2` then `ok=1` / `FileContents miss index=1 tried=[1, 2]`. The 1-based lindex guess was wrong. Outlook's clipboard IDataObject drops later FileContents once the first STGMEDIUM (and often the FILEGROUPDESCRIPTOR) is released; later indices often answer GetDataHere, not GetData.

**FileContents.** Hold the descriptor medium and every FileContents medium until GetData has been called for all indices, then GetDataHere (CreateStreamOnHGlobal / TYMED_ISTREAM) for misses, then read bytes, then ReleaseStgMedium. Never fall back to lindex 0 for a later file. COM vtable walks skip fake test pointers (`pdataobj=1`). Index>0 logs GetData/GetDataHere hr, tymed, and byte length. Drag is not back; clipboard stays in `python -m doccon.drop_host --paste`.

**Names.** Re-paste of the same Outlook filename overwrites our leftover inbox and `DocCon/dropped` copy. `unique_dest` numbering (`scan0042-2.pdf`) is only when two files in the same batch share a name. Explorer originals outside those folders stay. Not filed into Current PDF.

Console is **1.62** (source). Close every old DocCon, launch from source, Load `2026-Tanzim`, Copy several Outlook PDFs, Paste PDF. Both should appear in New PDFs under the original names (no `-N`). Do not Confirm 075. No exe. No drag.

Tests: **377 passed, 2 skipped (Tk).** Ruff clean on the touched files.

## 2026-09-16 — Second Outlook Copy file was on the clipboard; we did not read it (1.61)

Operator: right-click Copy of several attachments still pastes only the first. The log showed Outlook did put both names on the clipboard (`names=2` `2025-124-1-TL REV 0.pdf,Elite Integrity CF Tank Loading Point.pdf`) and we only staged one (`ok=1`). Not an Outlook Copy limit on that gesture — FileContents for descriptor index 1 returned empty. 1.60 stopped falling back to index 0 (that duplicated file 1) but never successfully read file 2.

**Fix.** Later FileContents also try Outlook's 1-based lindex (descriptor 1 → lindex 2), Seek(0) on the IStream before Read (the second stream is often already at EOF), and still never fall back to lindex 0. Misses log `FileContents miss index=…`.

Console is **1.61** (source). Load `2026-Tanzim`, Copy several Outlook PDFs, Paste PDF. Do not Confirm 075. No exe.

Tests: **369 passed, 2 skipped (Tk).** Ruff clean on `win_drop.py` and `test_win_drop.py`.

## 2026-09-16 — Paste several Outlook PDFs, Drop PDFs overlay gone (1.60)

Operator: drag is too complicated; he likes **Paste PDF**. Ask: Copy multiple Outlook attachments, Paste, they appear, Assign one by one; the floating Drop PDFs overlay (Outlook/Explorer drag) has to go.

**Multi paste parks, single paste still pairs.** One file on the clipboard keeps 1.56: selected row → filename → New PDFs. Two or more skip pairing entirely and wait in **New PDFs** for **Assign to selected row**. Assign uses the clicked row (or a lone Pack tick), never the first of several packed rows. PDF from Outlook with several files does the same.

**Overlay gone.** The teal Drop PDFs dock, `DropBridge` / `drop_host` spawn, and GUI OLE `hdrop_ole` / `HdropHost` attach are removed. Clipboard paste still runs `python -m doccon.drop_host --paste`. Watched folder (Downloads / Desktop / inbox) stays.

**FileContents index bug.** Reading attachment 1+ used to fall back to lindex 0, so every later Outlook name got the first file's bytes. Index 1+ is that index only.

Console is **1.60** (source). Load `2026-Tanzim`, Copy several Outlook PDFs, Paste PDF, Assign. Do not Confirm 075. No exe.

Tests: **369 passed, 1 skipped (Tk).** Ruff clean on the touched files.

## 2026-09-16 — Drag onto the row, and PDF from Outlook no longer freezes (1.59)

Operator: *"why cant I simply drag and drop a pdf file onto the row?"* then Explorer still showed no-entry; *"it is hanging"* was a 33 s freeze on **PDF from Outlook**. The previous session died mid-edit on a usage limit; this finishes both.

**Explorer no-entry was a mechanism conflict, not Outlook.** `WM_DROPFILES` never fires `DragEnter`, so Tk child widgets (every Now label, every Next box) show no-entry even when the canvas has `DragAcceptFiles`. An OLE target on a window also wins over the legacy path, so a helper overlay or a refusing `IDropTarget` made the whole board refuse. Two helper bugs made it worse: `os.kill(pid, 0)` treated `PermissionError` as "parent gone" and the child exited ~0.3 s after every spawn (burning all five restarts), and `DefWindowProcW` had no ctypes argtypes so dock messages overflowed on x64.

**Fix.** The GUI process registers an OLE **CF_HDROP-only** target on the toplevel (`hdrop_ole.py`) — copy cursor, live row highlight (the 1.57 band machinery), hit-test on frozen Pack/JIRA ID and the scrolling pane. It never asks for FileGroupDescriptorW / FileContents / IStream. Outlook streams stay in the `drop_host` child, docked over the Drop PDFs strip only. A drop on a row beats a filename that matches a different row. `DragAcceptFiles` is the fallback and is never left on a window OLE now owns. Paste PDF stays, quieter.

**PDF from Outlook freeze.** The hunt ran on the Tk thread. Speculative COM probes of members Outlook objects do not have (`MailItem.FileName`, `Explorer.CurrentItem` / `.PreviewPane`) cost ~0.6 s each and stacked to 33 s. The hunt now runs on a worker thread, shows **Looking in Outlook…** on the existing load meter, caps at 20 s and kills the PowerShell helper, and a second click does not stack another hunt. The live PowerShell walk is Class-guarded, cheapest probe first (attachment well → selection → inspectors), and those speculative members are gone.

**Tests no longer write the production log.** `DOCCON_LOG_DIR` + autouse fixture send pytest (and the paste/drop_host children it spawns) to `tmp_path`.

Tests: `test_hdrop_ole.py`, `test_drop_onto_row.py`, Outlook timeout + off-thread hunt, `parent_alive` fail-open, DefWindowProc argtypes. **362 passed, 1 skipped (Tk).** Console is **1.59** (source). Load `2026-Tanzim`, drag a PDF from Explorer onto a row. Do not Confirm 075. No exe.

## 2026-09-16 — The email-dropped address names the PDF (1.58)

Operator: *"also it says email dropped…, it should show the pdf name to confirm I got the right opne"*. The yellow **email dropped** text proved the bypass had happened but replaced the only place the filename was shown, so after a paste or a drop he could not tell *which* PDF had paired.

**Form chosen: `scan0042.pdf — email dropped`, filename first.** The 1.45 wording and the 1.45 yellow (`PENDING_BG` fill + `Pending.TLabel`) are both kept — yellow is still the locked bypass signal, and this is not a Jira Next edit. The filename **leads** because the PDF column is 176 px by the 1.31/1.36 layout and the cell clips from the right: whatever the column cannot fit is taken off the marker, never off the name the operator recognises. That is deliberate degradation rather than a fallback — a long name like `2026-Tanzim-1-14 … REV 0.pdf` shows as the filename in yellow with the marker trimmed, which is exactly the readable end state, and the column is **not** widened to make room. Only the leaf filename is shown; the `{job}/3.0 Doc Con/DocCon/dropped/` prefix is noise on every dropped row.

**Hover carries the rest.** The PDF cell already had the 1.02 clipped-label tip, so `pdf_address_tip()` feeds it instead of the raw label text: the full `filename — email dropped` line plus the staged path on a second line. No new tooltip machinery. A normal job-folder pair hovers exactly as before (its filename), so nothing changed for matched rows.

Locate…, Open, the 1.46 deletion rules, and the 1.55 issue-key pairing are untouched — this is a render change in `match.pdf_address_text` and the board's PDF cell only. A real job / Current PDF outside `dropped` still restores the plain filename and clears the yellow; a Locate… of a file still inside `dropped` stays yellow and now names that file. The 1.57 focus band still yields to the yellow on a dropped row.

Tests: `test_drawing_board.py` gains the filename-before-marker contract (long name, marker at the tail, `PDF_COL_PX` unchanged, tip has the wording + staged path) and a Locate-inside-`dropped` case that keeps the yellow and shows the new filename; `test_drop_pdfs.py` and `test_paste_pairs_selected_row.py` now assert the composed address and the plain-filename cases. **344 pass, 2 skipped (Tk).** Ruff clean on the touched files (the 8 pre-existing findings in `jira_client.py` / `secrets.py` / `theme.py` / `tools/` are untouched).

Console is **1.58** (source). Load `2026-Tanzim`, paste or drop a PDF, read the row. Do not Confirm 075. No exe.

## 2026-09-16 — The focused row is visible before the paste (1.57)

1.56 made **Paste PDF / Ctrl+V** pair onto `explicit_focus_key()` — the row the operator clicked — but nothing on the board said which row that was. He clicked, pasted, and only the status line afterwards told him whether it had landed on the right drawing. The target is now banded, so he can see it **before** he pastes.

**What the band is.** The focused drawing's Now labels (JIRA ID, Description, Status, Match, PDF address, and every Now field) take `Focus.TLabel`, background **BORDER `#D9E2EC`**, and the block's top and bottom 1px rules go **ACCENT `#0F766E`** teal. Both are already in `theme.py`; no new accent was invented. Deliberately **not** amber: `PENDING_BG` stays the only yellow on the board, so a dirty Next and an **email dropped** address are still the exception they were. The band never reaches into a Next cell — those keep their own white / amber — and email dropped outranks the band on the PDF cell, so a bypass pair cannot be washed out by focus.

**Frozen vs scrolling split.** No overlay, no canvas rectangle, no second frozen-row sync. The band is painted on the real widgets in each grid: `drawing_label` lives in `_freeze_inner` (Pack / JIRA ID) and the rest in `_inner`, and each block's four 1px rules bracket it in **both** panes. A sideways scroll carries it for free because it is the row's own colour, not something drawn at a canvas coordinate — the 1.47 pinning and paint slicing are untouched.

**Cost.** `_set_focus` repaints exactly two rows, the one the band left and the one it entered, and `_style_row_focus` returns immediately when the block is already in that state. Nothing walks the list on a click, and Load still paints incrementally.

**Second fault, found while wiring this up.** `_apply_next_to_block` called `_set_focus(block.key)`, so a **batch stamp, a cover-date Pack tick, or a Load restore of saved Next counterfeited an operator click.** Two live consequences: Pack-ticking five rows with Expected return set left `explicit_focus_key()` pointing at the fifth, walking straight past the 1.56 "several packed rows is not a selection" guard; and a Load that restored `client-pack.json` Next edits left the **last restored row** as the paste target. Programmatic stamping no longer moves the cursor — the band and `explicit_focus_key()` now mean exactly what the docstring says, the row the operator pointed at. The 1.56 routing order (selected row → filename → New PDFs strip), the staging, and the deletion rules are unchanged.

Tests: 8 new in `test_drawing_board.py` (click bands and the row it left clears, band covers the frozen **and** scrolling pane, a Pack tick that really does stamp a cover date still bands nothing, batch apply bands nothing, a dirty Next stays yellow on a banded row, email dropped keeps its amber on a banded row, Load repaint clears stale focus, and the 1.34 single-click / double-click / Escape gestures are unchanged) plus 1 in `test_theme.py` (band is palette, never the amber; focused match styles). **342 pass, 2 skipped (Tk)** at the time 1.57 landed. Ruff reports 5 findings, all on lines this change did not touch (`jira_client` ×2, `secrets`, `theme.apply_theme` ×2).

Console was **1.57** (source) for this slice. Load `2026-Tanzim`, click a drawing row, confirm the band, then Paste PDF. Do not Confirm 075. No exe.

## 2026-09-16 — Paste pairs onto the selected row, no Assign step (1.56)

Operator on 1.53 Paste PDF: *"kinna works….i paste pdf then assign it to a marked row…."* Paste worked, but it made him do a second **Assign to selected row**. He asked for: pair it straight onto the row he has selected.

**Why it went to the New PDFs strip — the paste was triggering the watcher on itself.** `clip_paste` stages the pasted PDF into `%LOCALAPPDATA%\…\DocCon\inbox`, and 1.53 put that same inbox in `watch_inbox.watched_dirs()`. So paste paired the row, and ~1.5 s later the watcher scanned the inbox, saw a PDF it had never catalogued, treated it as a fresh arrival, failed the filename match on an Outlook name like `scan0042.pdf`, and parked it in **New PDFs** — the operator's own file, handed back to him as if it still needed a row. The paste path itself was never the problem; it already preferred the focused row. `_claim_inbox_paths` now marks everything we stage as already seen, for **Paste PDF** and **PDF from Outlook** both. A genuine walk-in file in the same folder still fires.

**Second fault, found by the new tests.** `DrawingBoard.focused_row()` falls back to `selected_rows()[0]` — the **first Pack-ticked row** — when nothing is clicked, and `include` defaults on when a row is painted. For a positional drop that fallback is harmless, but it meant a paste with no click could silently pair onto row 1 of a 30-row packed list. New `explicit_focus_key()` returns only the row the operator actually clicked, and `_paste_target_key()` accepts that, or a **single** Pack tick (unambiguous), and otherwise nothing. "First of several packed rows" is a guess, and a wrong silent pair is worse than falling through.

**Order for a paste, locked:** selected row wins outright → else filename match against the loaded rows → else the New PDFs strip. A selected row is never overridden by a filename that matches a different row. Staging, **email dropped** yellow, and the 1.45/1.46 deletion rules are unchanged; pairing is still keyed by Jira issue key, so the 1.55 JIRA ID Next is untouched.

**Feedback names the row.** Success reads `Paired scan0042.pdf onto 2026-Tanzim-1-7.` — filename and JIRA ID, so he can see it landed right without hunting. Nothing selected and nothing matched reads `some-invoice.pdf did not match a row — select a drawing row, then Paste PDF.` plus one info box; the file still waits in New PDFs.

**Watched folder deliberately does not honour the selection.** A PDF appearing in Downloads is not an explicit gesture the way Ctrl+V is — it can arrive from any app, at any moment, including while the operator is mid-edit on an unrelated row. Letting it claim whatever is selected would silently attach the wrong drawing. Filename matching still leads there, and unmatched files wait in New PDFs for a deliberate Assign.

Tests: new `test_paste_pairs_selected_row.py` (8) — selected row pairs with no strip entry, selected row beats a filename matching a different row, no selection pairs by filename, several packed rows are not a selection, a lone Pack tick is, unmatched parks with the "select a row first" message, status names JIRA ID + filename, watcher does not re-report paste staging but still reports a walk-in, and watched folder still leads with the filename match. **333 pass, 2 skipped (Tk).** Ruff clean.

Console is **1.56** (source). Load `2026-Tanzim`, click the drawing row, Copy the Outlook attachment, **Paste PDF**. Do not Confirm 075. No exe.

## 2026-09-16 — JIRA ID is an editable Next, same as Description (1.55)

Sarah asked to fix a wrong drawing number on the console instead of opening Jira. **JIRA ID** (the frozen column beside Pack) now has the same Now/Next pair as Description: plain **Entry, no ▼**; single-click selects the row, **double-click** edits in the cell, Enter / click-outside commits and leaves, Escape restores Now and leaves. Dirty turns the same yellow, right-click restores Now for that field alone (1.22), and **Cancel Next** puts it back with everything else (1.33).

**One summary write.** JIRA ID and Description are two halves of the single Jira `summary` field, so Confirm composes `{effective ID} {effective description}` (Next when dirty, else Now), joined by one space, with no trailing space when the description is empty — one `summary` PUT per issue. There is no path that writes `summary` twice, so a Description edit can no longer clobber an ID edit or the reverse.

**Validation stays light.** The Confirm **preflight** rejects only an ID Next that is blank/whitespace or that has whitespace inside it, naming the issue key, so Confirm aborts having written nothing. No Elite pattern is enforced and no numbering scheme is invented. An ID that is already multi-word in Jira (`CWB Certificate`) is only checked when the operator actually changes it, so editing that row's description still works.

**PDF pairing and the printed ID.** Pairing is keyed by Jira issue key, never by ID text, so a Locate…'d or email-dropped PDF stays paired across an ID edit (no silent drop, no re-hunt). The transmittal letter and the EDDI snapshot already read the latest Next values, so both print the **effective** ID.

Persistence rides the existing `next_edits` path: `drawing_id` is saved in `{job}/3.0 Doc Con/DocCon/client-pack.json` keyed by issue key, with the same ~1 s debounce, auto-save before another Load and on close, and restore on Load. Pack ticks and cover Date issued / Expected return still come back off / N/A.

Tests: new coverage in `test_register.py`, `test_jira_client.py`, `test_drawing_board.py`, `test_pack_state.py`, `test_gui.py` (widget kind and edit gestures, yellow/restore/Cancel Next, composed summary each way, no trailing space, preflight abort with no write, JSON round-trip, PDF stays paired, letter + EDDI print the effective ID). 316 pass, 2 skipped (Tk). Ruff clean.

Console is **1.55** (source). Load `2026-Tanzim`, double-click a JIRA ID, Confirm there. Do not Confirm 075. No exe.

## 2026-09-16 — EDDI Status 400 on Confirm: comma in the option label (1.54)

Sarah's Confirm aborted with `Jira HTTP 400 … {"customfield_10289":"Option value 'Procedures - EDDI' is not valid"}`.

**Root cause.** `register.eddi_field` built the EDDI Status payload with `(value).replace(",", ";").split(";")`. EDDI group 5 is named **`5 - QC - WO, ITP, NDE Records, Procedures - EDDI`** — the commas are part of one option name, not separators. That one label went out as **four** options (`5 - QC - WO`, `ITP`, `NDE Records`, `Procedures - EDDI`); Jira rejected the last fragment it read. Every group-5 row failed; groups without a comma in the name were fine, which is why this only showed up now. The label came from the hardcoded Elite `EDDI_VALUES` list on the board picker, not from Jira. Nothing was half-written — Confirm's Jira write is rolled back and no tab is filed — but the message named an option nobody had picked.

**Fix (1.54).** EDDI Status options are separated by `;` only. Load now reads each issue's **own** `editmeta` `allowedValues` for `customfield_10289` (one GET per Jira **issue type**, in parallel — multi-checkbox contexts are per project / issue type, so a Sub-task context does not speak for a Task) and writes the chosen option **by option id** (`[{"id": "…"}]`), which is context-safe; label is the fallback only when Jira sends no id. Resolving a label ignores case, dash character (`-` `–` `—` `−`), and doubled/stray whitespace, so the Elite convenience labels still match Jira's wording. The board ▼ offers only that row's own options (rows with no context keep the Elite list); the Batch EDDI box offers only options **every** listed issue has. An option that genuinely is not on that issue's context is caught in the Confirm **preflight** — `P2024-…: EDDI Status "…" is not an option on that issue in Jira. That issue allows: … Nothing was written.` — so nothing is written and no tab is filed. The Load multi-status fixer offers only that issue's real options (still groups 1–9, still no Generic), writes by id, and Skip still leaves Jira unchanged.

Tests: 33 new/extended assertions across `test_register.py`, `test_jira_client.py`, `test_drawing_board.py`, `test_gui.py` (id payload, case/dash/whitespace resolve, preflight abort with no write, one editmeta per issue type, per-row picker, fixer options). 307 pass, 2 skipped (Tk unavailable on those runs). No ruff findings from this change.

Console is **1.54** (source). Close every old DocCon, launch `python -m doccon`, Load `2026-Tanzim`, retry the pack that failed. Do not Confirm 075. No exe.

## 2026-09-16 — Diagnosed 1.44-1.52, then no-OLE ingest (1.53)

**Diagnosis first, and it was two concrete faults, not a tuning problem.**

1. **`drop_host` never ran a single time.** `_run_overlay` declares `WNDCLASSW` with `("hCursor", wintypes.HCURSOR)`, and `ctypes.wintypes` has **no `HCURSOR`**. Every spawn raised `AttributeError` at class-definition time, before `CreateWindowExW`, and `main()` swallowed it into `crash …` and returned 1. Verified by spawning the helper directly: `{'op': 'log', 'level': 'WARN', 'msg': "module 'ctypes.wintypes' has no attribute 'HCURSOR'"}`, exit code 1. The log held **1660 HCURSOR crashes**, **0** `dock hwnd=` lines and **0** `overlay loop` lines — the IDropTarget window was never created in any version, so Windows had nothing to drop onto. That is the no-entry cursor, 100% reproducible.
2. **The operator was reading the wrong log.** Store Python (`WindowsApps\PythonSoftwareFoundation.Python.3.13`) virtualizes `%LOCALAPPDATA%` writes into `…\Packages\…\LocalCache\Local\`. The documented path held only two `version=1.43 frozen exe` lines, so 1.44-1.52 looked silent. Sessions 1.45-1.52 were all there in the redirected file. Two stale 1.50/1.51 consoles were still live, respawning the dying helper forever and rotating 2 MB of log every few minutes.

**Fixes.** `wintypes.HANDLE` for `hIcon`/`hCursor` — helper now reaches `RegisterDragDrop hwnd=0x41cfc hr=0 (child)`, `dock created … topmost=1 transparent=0 visible=1`, `overlay loop`. Crash lines carry type + file:line. Restart loop capped at 5 (`drop_host gave up …`). `real_log_path()` follows the redirect, is logged at session start, and **Open log folder** opens the folder the log is actually in.

**No-OLE ingest is now the supported route; OLE drag is best-effort only.**

- **Paste PDF (primary).** Outlook → right-click attachment → **Copy**; on the console **Paste PDF** (button on the navy bar and on the Drop PDFs strip) or **Ctrl+V**. `clip_paste` (parent, stdlib only) runs `python -m doccon.drop_host --paste`; that child calls `OleGetClipboard` + the existing `extract_drop_sources` (CF_HDROP, FileGroupDescriptorW+FileContents, FileName), stages into the inbox and prints a JSON line. The GUI imports neither `clip_read` nor `win_drop`, so a native fault lands in the child. Then the usual ingest: `DocCon/dropped/`, pair, **email dropped** yellow (1.45), delete per 1.46. Empty clipboard is an operator message, not an error. Verified end-to-end against a real clipboard.
- **Watched folder (always works).** `watch_inbox` polls `Downloads`, `Desktop`, and `%LOCALAPPDATA%\…\DocCon\inbox` on a 1.5 s Tk timer — pure `os.scandir`/mtime, no COM, no child, **never Dropbox**, only while a job is loaded, ignoring anything older than session start and anything still being written. New PDFs match by filename against the loaded rows and auto-pair; the rest wait in a **New PDFs** strip for *Assign to selected row*. Drag the attachment to your Desktop and DocCon picks it up.

**Locate… / Open unchanged. 1.47 Load non-hang unchanged. EDDI still matched-PDFs-only.** Tests: `test_clip_paste.py` (8) and `test_watch_inbox.py` (9) new, plus regression guards that every `wintypes.*` name in `drop_host` really exists and that dock/HRESULT are logged. 291 pass; `test_confirm.py::test_confirm_rolls_back_jira_if_file_fails` and `test_jira_client.py::test_apply_jira_updates_rolls_back_on_later_failure` fail on a pre-existing callback-arity drift in `confirm.py` (already in `lastfailed` before this change, untouched here).

Console is **1.53** (source). Close every old DocCon, launch `python -m doccon`, Load `2026-Tanzim`, then Copy an Outlook PDF and **Paste PDF**, or drag it to the Desktop. Do not Confirm 075. No exe.

## 2026-09-16 — PDF from Outlook + Drop PDFs dock is the OLE HWND (1.52)

1.51 **PDF from Outlook** only walked `ActiveExplorer().Selection` mail items, so an open Inspector, attachment-well pick, or unfocused Explorer looked like “Outlook has no PDF attachment.” **1.52** harvests Explorer selection **and** `AttachmentSelection`, every Inspector (`CurrentItem` + well), and preview if Outlook exposes it; `.pdf` is case-insensitive. Empty harvest is operator-facing: select the **email** in Outlook (not Edge/Adobe), then the button — or drop onto **Drop PDFs**. Outlook closed stays a short error, no crash.

1.51 no-entry: the board overlay still was not `WindowFromPoint`, and QueryGetData on DragEnter can cancel Outlook’s drag. The teal **Drop PDFs** dock is now the only child `IDropTarget` HWND (topmost, visible, never `WS_EX_TRANSPARENT`). Helper spawn sets `PYTHONPATH=src` + repo cwd; spawn/death logs the error and status **drop helper not running**. DragEnter always sets `DROPEFFECT_COPY` (no FileContents probe). Parent `DragAcceptFiles` / `WM_DROPFILES` is on the dock + board surfaces (and their children) so Adobe/Explorer HDROP gets a copy cursor on the **board**. OLE stays out of the GUI process. Console is **1.52** (source). Load `2026-Tanzim`; drop on the strip or **PDF from Outlook**. Do not Confirm 075. No exe.

## 2026-09-16 — Outlook drop overlay actually accepts OLE (1.51)

1.50 showed a **no-entry** cursor on Outlook attachment drag. FileContents never becomes HDROP, so the parent `WM_DROPFILES` target rejects it. The child overlay was not under the cursor: hidden 40×40 at origin until geom, `STARTF_USESHOWWINDOW`+SW_HIDE on spawn, mouse-forward **hiding** the HWND on move (OLE then hit-tested Tk), and `WS_EX_TRANSPARENT` would skip `WindowFromPoint` / IDropTarget. **1.51:** helper starts as soon as the console is mapped (not skipped during Load paint). Overlay styles are never transparent-to-input (`overlay_ex_style` strips `WS_EX_TRANSPARENT`; layered/alpha still hit-tests). A visible always-on-top **Drop PDFs** dock (opaque HWND) plus a board overlay follow the console; OleInitialize before CreateWindow; geom on the command line; spawn without SW_HIDE. Logs `drop_host started`, bind port, overlay hwnd; restart if the helper dies. After a dock drop: last cursor, filename match, then selected row. Explorer HDROP on the parent still works. Isolation stays: no IStream in the GUI process. Console is **1.51** (source). Load `2026-Tanzim`; Outlook drag must show copy cursor and pair. Do not Confirm 075. No exe.

## 2026-09-16 — OLE FileContents out of the GUI process (1.50)

1.49 still died on an Outlook attachment drop: ctypes `IDropTarget.Drop` / FileContents / IStream ran **in the GUI process**. A native AV kills Python/Tk before `doccon.log` can flush (no 1.49 session line). Marshaling Tk via `after(0)` cannot catch that. **1.50:** the parent never OLE-registers. Explorer uses `DragAcceptFiles` + `WM_DROPFILES`. Outlook FileContents lives in `python -m doccon.drop_host` (transparent overlay following the toplevel). The child writes PDF bytes to `%LOCALAPPDATA%\EliteIntegrity\DocCon\inbox\`, then sends `{path, x, y}` over localhost JSONL. If the helper AVs, DocCon stays up, logs `drop_host died`, and restarts it. **PDF from Outlook** saves the selected message’s PDFs without OLE drop. Session log (version, source vs frozen, pid) is flushed at process start, before any drop install. Catch-all in the parent; no `os._exit`. Console is **1.50** (source). Load `2026-Tanzim`; Outlook drop must not close DocCon. Do not Confirm 075. No exe.

## 2026-09-16 — Drop must not kill the process (1.49)

Operator drag-drop of a PDF shut the console (hard crash, not a Tk dialog). `doccon.log` on this PC had no 1.48 drop hop (only 1.43 exe sessions). Likely site: OLE `IDropTarget.Drop` / FileContents on a non-Tk thread then Tk (`row_key_for_y`, pair, yellow), or ctypes x64 in POINTL / IStream / QueryGetData. **1.49:** Drop copies PDF bytes/paths only, then `widget.after(0, …)` to pair on the Tk thread. DragEnter/Over/Leave never call Tk synchronously. Exceptions log and return `DROPEFFECT_NONE` / `S_OK` (no `os._exit`). RevokeDragDrop is deferred until Drop returns. Explorer HDROP and Outlook FileContents share that marshal path. 1.47 Load (OLE once on toplevel + canvas) and 1.45–1.46 email-dropped yellow / delete staging copy stay. Console is **1.49** (source). Load `2026-Tanzim`; drop a PDF; window stays up. Do not Confirm 075. No exe.

## 2026-09-15 — Outlook attachment drop (1.48)

1.47 Load hang is gone (RegisterDragDrop once, timer paint). Outlook `FileGroupDescriptorW` + `FileContents` never hits `WM_DROPFILES`, so a toplevel-only target plus ctypes `POINTL` by-value on x64 made an email-attachment drag look like nothing. **1.48:** register `IDropTarget` once on the mapped toplevel plus the board canvas/inner (not per-row HWNDs), hit-test drop Y to the row, extract FileContents during Drop, copy cursor + row outline, log to `doccon.log`. Console is **1.48** (source). Load `2026-Tanzim`; drag an Outlook PDF onto a row. Do not Confirm 075.

## 2026-09-15 — Load hang after identities (1.47)

After Jira + Folder chips, Load froze on “painting pack items” (force-quit). **1.44–1.46 OLE drop** registered `IDropTarget` on every child HWND (`EnumChildWindows` of the Tk tree) during/after paint; frozen-row sync called `update_idletasks` (Configure loop); pack restore / `sweep_replaced_dropped_copies` did Dropbox `Path.resolve` / `is_file` on the Tk thread. **1.47:** RegisterDragDrop once on the toplevel (OLE walks parents); paint with `Painting N of M` on a timer slice; frozen sync capped and never `update_idletasks`; locate restore + dropped sweep on the Load worker. Console is **1.47** (source). Load `2026-Tanzim`; board must appear. Do not Confirm 075.

## 2026-09-15 — Dropped PDF staging, then delete (1.46)

Drop still **copies** into `{job}/3.0 Doc Con/DocCon/dropped/` (1.44) and shows **email dropped** yellow (1.45). Explorer originals are not deleted — only our `dropped\` copy. That copy is deleted when Hunt or Locate… pairs a real job/Current PDF (bypass clears), or when **Confirm…** succeeds for packed email-dropped rows (zip already has the bytes). Abort does not delete. Locate… of Downloads / Current PDF never deletes those files. Console is **1.46** (source). Do not Confirm 075.

## 2026-09-15 — Email-dropped PDF address (1.45)

A drag-drop pair (1.44 copy into `DocCon/dropped/`) shows **email dropped** on the PDF address, yellow like a dirty Next (bypass only — not a Jira Next edit, not the whole row, not Pack). Open still uses the dropped file; Confirm/zip can use that copy until replaced. Hunt or Locate… to a file **outside** `DocCon/dropped` restores the filename and clears yellow. Locate… of a file still in `dropped` stays yellow. `client-pack.json` `located_pdfs` stores `{path, email_dropped}` so Load restore keeps the label until a real job PDF replaces it. Console is **1.45** (source). Do not Confirm 075.

## 2026-09-15 — Drag-and-drop PDFs (1.44)

Sarah can drop a PDF from Explorer or an Outlook attachment onto a drawing row or the board. DocCon **copies first** into `{job}/3.0 Doc Con/DocCon/dropped/` (same folder as `client-pack.json`), then pairs that path. Locate… still browses. Does not rewrite Jira and does not file into `2.0 Drafting/Current PDF`. Row drop pairs that issue (several files: the one that clearly matches the JIRA ID, else the first PDF). Board / navy-bar drop uses the same filename match as the folder hunt; leftovers stay unmatched so she can drop them onto the right row. Outlook attachments use `FileGroupDescriptorW` + `FileContents` (no path). `.msg` is skipped. No job loaded → Load first. Open and EDDI still use the paired file; `located_pdfs` remembers the dropped path. Console is **1.44** (source). Do not Confirm 075.

## 2026-09-15 — 1.43 exe built

PyInstaller wrote `Elite DocCon.exe` in this folder (`Elite DocCon.spec`; no tokens). Window title **Elite DocCon  1.43**. Close any old DocCon; give Sarah this exe. Settings → **Open log folder** if Excel still fails. Do not Confirm 075.

## 2026-09-15 — Diagnostic log + hidden PowerShell; no hang (1.43)

Sarah’s Confirm black window **stayed on**. There is no `Read-Host` / `pause` / `cmd /k` in the Excel scripts. The window was **visible `powershell.exe`** (no `CREATE_NO_WINDOW`): Unblock-File, then the Excel COM script, then 32-bit PowerShell fallback. COM blocked inside `Workbooks.Open` / `CreateInstance` (dialog, Protected View, or a Dropbox Open hang in 1.40). `finally` / `Excel.Quit` never ran until Open returned, so the console sat there. Closing it killed the hop; a retry opened another window, then the Excel error.

**1.43:** hops go to `%LOCALAPPDATA%\EliteIntegrity\DocCon\doccon.log` (rotate ~2 MB + `.old`; not Dropbox). PowerShell / taskkill use `CREATE_NO_WINDOW`, `SW_HIDE`, `-WindowStyle Hidden`. Subprocess timeout kills that PowerShell **and** the dedicated Excel PID (PID snapshot; not every Excel.exe). Scripts write progress lines; `Quit` in `finally` even on error. GUI Excel errors point at the log. Settings **Open log folder**. Console is **1.43** (source). Do not Confirm 075.

## 2026-09-15 — Excel COM hardened for Sarah (1.41)

Sarah’s “can’t open Excel” dialog was the EDDI/File path dumping COM into **Could not update the EDDI snapshot in Excel.** (plus HRESULT / PowerShell stack), or **Excel took too long. Close Excel if it is stuck.** Root cause coded for: Click-to-Run / unregistered desktop Excel (`0x80080005` / `0x80040154`), attaching to an already-running Excel, Dropbox Open hang, Protected View / Zone.Identifier, RPC / file-in-use on Open, and WinError 32 when the dated PDF is already open.

DocCon now starts a dedicated Excel (`Activator.CreateInstance`, not GetActiveObject), copies the book to `%TEMP%\DocCon`, Unblock-File, retries Open 3× with backoff (Visible=True on the last try), tries 32-bit PowerShell if COM class factory fails, and maps failures to operator text (**Install or repair desktop Excel**, not Microsoft 365 web). Print-PDF failure after the `.xlsm` is written no longer fails the whole EDDI snapshot; a locked PDF uses `…-2.pdf` or tells her to close the reader. Console is **1.41** (source). Do not Confirm 075.

## 2026-09-11 — 1.40 exe built

PyInstaller wrote `Elite DocCon.exe` in this folder (`Elite DocCon.spec`; no tokens). `pytest -q`: 194 passed, 2 skipped (Tk). Double-click the exe or run from source. Do not Confirm 075.

## 2026-09-11 — Load fixer for multiple EDDI Status (1.40)

Jira EDDI Status is a multi-checkbox. If Load finds more than one option on an issue, DocCon prompts with **those issues only**. Pick one group 1–9 (Generic is not offered). **Update and reload** writes that single option (not a transmittal Confirm) and reloads the job. **Skip** leaves them unchanged and continues Load. Console is **1.40**.

## 2026-09-11 — EDDI snapshot skips Missing PDFs (1.39)

**EDDI…** and Confirm’s EDDI copy include only listed items that have a paired/matched PDF (Locate… or auto-match). Missing / no-file placeholders stay on the console. Generic and ungrouped still omitted; empty groups still hide. Live `EDDI-{job}.xlsm` unchanged. Console shipped with **1.40**.

## 2026-09-11 — Auto-save Next in client-pack.json (1.38)

Dirty Next edits persist in `{job}/3.0 Doc Con/DocCon/client-pack.json` (same file as Save; keyed by Jira issue key; no tokens). Auto-save before Load of another job (or the same again) and on window close. Next edits debounce (~1s). Load restores Next, Locate… PDF paths, and cover TO/CC/project. Pack stays off and cover Date issued / Expected return stay N/A (1.32) even if those were in the JSON. Stale keys are skipped. Empty JSON loads Now from Jira. Console shipped with **1.40**.

## 2026-09-11 — Load meter for the whole wait (1.37)

Load shows a visible slate/teal meter and a short status from the click: Jira fetch → job folder → PDFs → match → painting N of M. Indeterminate until the register is ready, then determinate while rows paint. Cover N/A + Pack off (1.32) still run after paint without looking like a hang. Error hides the meter. Console is **1.37**.

## 2026-09-11 — Slim board columns again (1.36)

1.31 defaults were still in code (Pack **48**, JIRA ID **180**, Description **240**, PDF **176**; other columns headline + ▼). Fat boards were LOCALAPPDATA `board_col_px` from before 1.30. **1.36** stores `board_layout_rev` 136 and ignores older saved widths once; sash drag saves again. Console shipped with **1.37**.

## 2026-09-11 — Scrollbar contrast (1.35)

Drawing-list horizontal and vertical scrollbars use a pale thumb (`#D9E2EC`) on a slate trough (`#486581`) so the slider is findable on navy chrome and the light board. Same `TScrollbar` / `Horizontal.TScrollbar` / `Vertical.TScrollbar` everywhere (board + Settings lists). Not neon. Console is **1.35**.

## 2026-09-11 — Double-click to edit Next text (1.34)

Text Next boxes (Description, Client Doc No., dates) do not take a caret on single-click. Double-click edits in the cell (no 1.02 full-wording window). Enter / click-outside / Escape still leave the editor (1.26). Pick-only lists still open on single-click. Outgoing / Incoming Rev stay readonly-looking until double-click; ▼ still picks. Console shipped with **1.35**.

## 2026-09-11 — Cancel Next undoes every Next (1.33)

**Cancel Next** restores every Next field on every listed row to Now (global 1.22 undo), clears yellow, and sets cover Date issued / Expected return to N/A so they do not re-stamp. Pack ticks stay. Does not write Jira. Console shipped with **1.35**.

## 2026-09-11 — Load cover dates N/A; Pack off (1.32)

Fresh Load sets Date issued and Expected return to **N/A** (not restored from `client-pack.json`) and leaves every Pack box off. Setting a cover date back to N/A (or blank) restores that packed Next date to Now. Stamp when they pick a real date stays 1.28/1.31. Letter: blank/N/A Expected return → N/A; blank/N/A Date issued → today. Console shipped with **1.35**.

## 2026-09-11 — Date issued stamps packed Submission Date (1.31)

Cover **Date issued** and packed Next **Submission Date** stay the same calendar day on this pack (letter vs Jira), same rule as Expected return → Return Request Date (1.28). One stamp helper: set Date issued, then Pack; changing Date issued re-stamps **all currently packed** rows. Blank Date issued does **not** wipe row Submission Dates. Unpacked rows are not stamped. Unticking Pack leaves the yellow Next (right-click restores Now). Confirm still writes packed Next Submission Date to Jira. Cover Date issued still goes on the letter. Console is **1.31**.

## 2026-09-11 — Slimmer drawing board columns (1.30)

Pack is a short checkbox column. The Now/Next **label** column is gone (Now values and Next editors stay: two-line row, yellow when dirty). Frozen Pack / JIRA ID still line up when Description wraps (1.17). Defaults: JIRA ID fits `2026-075-1-STWD` / `2026-Tanzim-1-1`; Description is a readable wrap (not half the window); PDF fits Locate… + Open; other fields are headline width plus ▼ padding. Cover stays a bottom strip. Console shipped with **1.31**.

## 2026-09-11 — Pick-only Next lists (1.29)

Submitted to Client For, Client Approval Status, Shop IFC Rev, Field IFC Rev, and EDDI Status are **dropdown only** (readonly Combobox, same as Status). Outgoing Rev and Incoming Rev stay typeable so Bump packed / Set packed to 0 from letters still work. Description / Client Doc No. stay Entry; dates stay calendar Entry. Apply to Pack sets a list value, not off-list typed text. Enter / click-outside still leave the editor (1.26). Right-click still restores Now. Console is **1.29**.

## 2026-09-11 — Expected return stamps packed Return Request Date (1.28)

Cover **Expected return** and packed Next **Return Request Date** stay the same calendar day on this pack (letter vs Jira). Set Expected return, then Pack — that date is copied onto that row’s Next Return Request Date (yellow; no Jira until Confirm). Changing Expected return re-stamps **all currently packed** rows. Blank / N/A Expected return → N/A on the letter and does **not** wipe row Return Request Dates. Unpacked rows are not stamped. Unticking Pack leaves the yellow Next (right-click restores Now). Client / Shop / Field share the same Expected return widget on the meta strip. Confirm still writes packed Next Return Request Date to Jira + `duedate`. Console shipped with **1.29**.

## 2026-09-11 — Text Next double-click stays in the cell (1.27)

Double-click Description Next, Client Doc No., or any other plain-text Next box no longer opens the 1.02 “full wording” copy window. Edit in the cell (Windows word/all select). Hover tips on clipped **Now** labels stay. Date ▾ calendars and Status/rev/EDDI Combobox lists are unchanged. Console is **1.27**.

## 2026-09-11 — Next Enter leaves the editor; column is JIRA ID (1.26)

Enter / Return / keypad Return and a click outside the active Next box commit the value (same dirty/yellow path as today) and take the caret out of the field. They do **not** move to the cell below. Escape restores that field’s Now (same as 1.22 right-click) and leaves the editor. A Combobox dropdown click is not “outside” until the list closes; picking an option still sets the value. Tab still moves to the next control. The frozen identity column heading is **JIRA ID** (operator spelling); Description is unchanged. Internal `drawing_id` stays. Console is **1.26**.

## 2026-09-11 — Next widgets match the field type (1.25)

Next boxes no longer all look like Comboboxes. **Dropdown** (editable Combobox): Status, Submitted to Client For, Client Approval Status, EDDI Status, and all Rev fields (Outgoing / Incoming / Shop IFC / Field IFC). **Calendar**: Submission Date, Return Request Date, Return Date, Shop/Field IFC Date (Entry + ▾, not a fake date list). **Plain text** (Entry, no ▼): Description and Client Doc No. Right-click restore Now (1.22) and yellow dirty (1.13) work on Entry and Combobox. Description wrap still lines up frozen Pack/Now/Drawing (1.17). Packed only / Bump packed / Set packed (1.23) and Open (1.20) stay.

Rev **Now** is still the value Load already fetched from Jira (`customfield_10280` / `10283` / `10285` / `10287`). Confirm still writes the typed string as today (`{"value": …}`). The ▼ list for an option-schema rev field is Jira editmeta `allowedValues` (plus Now if it is missing from that list). If Jira defines the field as text, or editmeta is missing, the board keeps the editable Elite convenience list (0, A, B, …) — not Jira-enforced. Console is **1.25**.

## 2026-09-11 — Import Outlook addresses into Settings (1.24)

Settings **Import from Outlook…** copies email addresses from desktop Outlook COM into this-PC saved TO/CC (LOCALAPPDATA, not Dropbox). Prefers the `eliteintegrityservices.com` account / `doc.control@…` when that profile is present; otherwise the signed-in default (same rule as Confirm mail). Reads the Global Address List when available, plus Contacts (client addresses included). Merge is unique and does not wipe. Skip empty, malformed, and noreply. If Outlook is missing or COM fails, a short “open Outlook” error — no send. Console is **1.24**. Tests stub the COM lister.

## 2026-09-11 — Bump packed revs, stamp one rev, Packed only (1.23)

Packed drawings can have different outgoing revs. **Bump packed** (Batch Next, Outgoing Rev strip) sets each packed Next Outgoing Rev to the step after that row’s Now: letters A→B→C (case kept), numbers 0→1→2. Blank Now becomes **0** (Elite IFC / numeric jobs). **Set packed to…** stamps one rev onto all packed Next boxes; **0 is allowed from A/B/C**. Unpacked rows are not changed. Neither writes Jira; yellow/dirty like a typed Next; right-click still restores Now. Zero packed: short note, no crash. **Packed only** (filter bar) shows packed rows only and hides EDDI headers with no visible packed row; off restores the full list. Does not auto-enable on Pack. Combines with the text filter (packed ∩ match). Bump/stamp still apply to the Pack set, not only what is on screen. Console is **1.23**.

## 2026-09-11 — Right-click Next restores Now (1.22)

Right-click a Next box (yellow dirty cell or the widget) copies that field’s Now value back. Dirty/yellow clears when it matches. Combobox, date, and EDDI Status restore the Now option/date, not leftover typed text. One field only — not the whole row. Does not write Jira. Native Cut/Copy/Paste menu is replaced so Undo means restore Now; Ctrl+V still pastes. Console is **1.22**.

## 2026-09-11 — EDDI snapshot group headers (1.21)

Dated EDDI copies merge each printed group title **A:M** (horizontal and vertical center, orange fill kept) so PDF fit-to-width no longer clips `1.` or the left of `CONSTRUCTION / INSTALLATION`. Rows 3–4 category headers are merged/centered in their form ranges (`A3:A4` … `L3:M3`). Empty EDDI Status groups are hidden (header, Column1 junk, unused slots) and not printed. A stranded page break in that hidden region (live form: after row 49) is dropped so page 1 is not blank. Live `EDDI-{job}.xlsm` is unchanged. Console is **1.21**.

## 2026-09-11 — Open the matched PDF from the row (1.20)

**Open** sits beside each row **Locate…** (same cluster; Locate stays after a match). Click opens the paired drawing PDF in the Windows default reader (`os.startfile`). No PDF disables Open; a missing file is a short error. Does not rewrite Jira, print, or restore top-bar Locate PDF…. Console is **1.20**.

## 2026-09-11 — Job identity on Load; shared Dropbox folder (1.19)

After Load, the navy bar shows **Jira** (Atlassian blue `#4C9AFF`) = the job Project issue summary/key, and **Folder** (Elite teal `#2DD4BF`) = the Dropbox job root. Missing either uses a warning pink. Job Number stays the Jira grouping key; several Job Numbers may share one folder (`2026-049-1` → `2026-049`). Hunt prefers an exact folder, then a parent-job folder; equal matches are left unmatched. **Locate job folder…** picks the job root; the Job Number → path map is LOCALAPPDATA. Names may differ; that is expected. Console is **1.19**.

## 2026-09-11 — EDDI snapshot fills the simple form (1.18)

**EDDI…** and Confirm copy `EDDI-{job}.xlsm` to a dated `EDDI-{job}-{date}.xlsm` in `3.0 Doc Con`, fill sheet **Project** groups 1–9 from the board’s Next values (every listed item, not only Pack), and print `EDDI-{job}-{date}.pdf`. The live EDDI book is left unchanged. Excel fills and prints a local copy (not the Dropbox path). Skip Generic and ungrouped. Console is **1.18**.

## 2026-09-11 — Frozen columns follow wrapped row height (1.17)

When Drawing or Description wraps, Pack / Now / Drawing on the locked pane use the same row height as the scrolling cells, so the row stays lined up. Console is **1.17**.

## 2026-09-11 — EDDI workbook opens; PDF print from a local copy (1.16)

EDDI snapshot was writing empty cells as invalid Excel `inlineStr`, using tabloid paper and `fitToHeight=0`. Excel sat on a repair/printer dialog until the 90s timeout: “Wrote …xlsx, but could not print the EDDI PDF.” Blank cells are omitted, paper is Letter, and Excel prints a local copy (not the Dropbox path). Console is **1.16**.

## 2026-09-11 — Top-bar Locate PDF removed (1.15)

The navy bar no longer has **Locate PDF…** next to Load. Pairing a file is only **Locate…** on the drawing row. **Locate PEP…** is unchanged (cover TO / CC / project). Console is **1.15**.

## 2026-09-11 — Freeze Pack / Drawing on sideways scroll (1.14)

Pack, Now/Next, and Drawing stay pinned on the left when the list scrolls sideways. Description and the rest of the fields still move. Console is **1.14**.

## 2026-09-11 — Next edits turn yellow (1.13)

A Next box turns yellow as soon as it differs from Now (typing, dropdown, calendar, or Apply to Pack). It goes back to white when it matches again, including Cancel Next. Console is **1.13**.

## 2026-09-11 — Themed load bar (1.12)

Load no longer uses the Windows ttk progress bar. A slim teal strip sits in the navy header (indeterminate while Jira/PDFs run, then fills as drawings paint). Console is **1.12**.

## 2026-09-11 — Headings one line; Drawing / Description wrap (1.11)

Default column widths fit each heading on one line (headings do not wrap). Now Drawing and Description text wrap inside the column; the Next description box stays a single line. Console is **1.11**.

## 2026-09-11 — Due Date off the console (1.10)

Controllers do not edit Jira Due Date. That column is gone from the board and Batch Next. Confirm still writes `duedate` when they enter a new Return Request Date (same value). EDDI snapshot still shows the Jira due date. Console is **1.10**.

## 2026-09-11 — Column drag no longer relayouts the list (1.09)

Dragging a heading sash was relaying out every drawing on every mouse move, so large jobs felt stuck. The heading tracks the mouse; the data columns apply once on release. Console is **1.09**.

## 2026-09-11 — Filter + header sash moves the data column (1.08)

Filter box above the drawing list matches as you type against **drawing ID** and **description** (and the Jira issue key). Hidden rows keep Pack ticks and Next edits. Pack all / none apply only to what the filter is showing. Header sash still sets shared pixel widths; body labels no longer stretch the column past the heading. Console is **1.08**.

## 2026-09-11 — Large jobs finish after Missing PDF (1.07)

2025-106 hung after the missing-PDF count because each drawing was a nest of frames and wrap, then Dropbox Excel ran on the same turn. Rows are a simple grid again (header still resizes). Cover/PEP load after the list is on screen. Console is **1.07**.

## 2026-09-11 — Load no longer hangs mid-list (1.06)

1.05 drew each row on a live canvas, so Tk relaid out every previous drawing after each one. **2025-106** stopped around Drawing 73 of 148. Rows are built off-screen in batches, then shown once. Console is **1.06**.

## 2026-09-11 — Faster Load; draw item by item (1.05)

Load no longer freezes the window after Jira returns. Jira fetch and the Dropbox PDF scan run together. The register is then drawn one drawing at a time (status **Drawing n of N**) with a progress bar. PDF walk skips Void / Old Procedures / Old PDF folders instead of listing every file. Console is **1.05**.

## 2026-09-11 — Due Date labelled as Jira

The board (and EDDI snapshot) header is **Due Date (Jira)** so it is not mixed up with Submission Date or cover Expected return. Same `duedate` field. Console is **1.04**.

## 2026-09-11 — Aligned resizable board columns (1.04)

Header and body share the same pixel widths, with a vertical border and a drag sash on each header. Double-click a sash to reset that column. Widths stay in LOCALAPPDATA `settings.json` (`board_col_px`), not Dropbox. Console is **1.04**.

## 2026-09-11 — Now/Next pair marked with two lines (1.03)

Each drawing is bounded by a thin full-width line above Now and another below Next, so the two rows read as one item. Console is **1.03**.

## 2026-09-11 — Long Drawing / Description text (1.02)

Now no longer cuts Description at 48 characters. That column is wider; hover shows the rest, double-click opens the full wording to copy. Console is **1.02**.

## 2026-09-11 — Excel File shows the real error (1.01)

Confirm no longer always says “close the workbook.” Excel COM writes the real message/HRESULT to a fail file so Sarah’s dialog can show it. Logo restore from the jobs-template is skipped if that template cannot open (does not abort the CT file). DocCon no longer sets Excel `Interactive = false` on a shared Excel instance. Console is **1.01**.

## 2026-09-11 — Locate browses; does not open the PDF

**Locate…** always opens the file picker to pair or replace a PDF. Double-click the PDF name to open the file. **Elite DocCon.exe** rebuilt. Console is **1.00**.

## 2026-09-11 — Locate stays; picker remembers the folder

**Locate…** stays on the row after a PDF is matched, so Sarah can pick a different file. The dialog opens in the last folder used on this PC (LOCALAPPDATA `settings.json`, not Dropbox). **Elite DocCon.exe** rebuilt. Console is **0.99**.

## 2026-09-11 — Elite DocCon.exe rebuilt (0.98)

One-file exe at the project root. Includes typeable date cells, calendar on the current screen, and looser Jira ID/description split. Token still saves in Windows Credential Manager on that PC. Do not Confirm 075.

## 2026-09-11 — Calendar follows the current screen

The date popup is placed next to the date box using the app window’s current screen position. It no longer opens on the monitor where DocCon first launched. Console is **0.98**.

## 2026-09-11 — Type dates; dropdown opens the calendar

Date boxes stay editable. The side dropdown (cover ▾, or the combobox arrow on the board) opens the calendar. Clicking the text no longer steals the cell.

Jira summary: the drawing ID is the leading code (`2026-075-ITP-1-1`). Any wording after that is the description. No description is allowed. Console is **0.97**.

## 2026-09-10 — Confirm Jira write works without project admin

Jira PUT no longer sends `notifyUsers=false`. That flag needs project admin and blocked Sarah (HTTP 403). Watchers may get a Jira email when Confirm writes fields. Console is **0.96**.

## 2026-09-10 — Elite DocCon.exe in the project root

One-file Windows exe at `Elite DocCon.exe`. Rebuild with `Build DocCon.exe.bat`. Token still goes to Windows Credential Manager on that PC. Console is **0.95**.

## 2026-09-10 — EDDI snapshot matches the console fields

The dated EDDI list has the same register columns as the board: Drawing, Description, Status, Due Date, Client Doc No., Outgoing Rev, Submitted to Client For, Submission Date, Return Request Date, Incoming Rev, Client Approval Status, Return Date, Shop/Field IFC rev and dates, EDDI Status. Still no location, client name, Include in Databook, or Comments. Console is **0.95**.

## 2026-09-10 — EDDI is a full job snapshot

EDDI lists every item on the board (latest Next values), not only packed drawings. Confirm still prints it. **EDDI…** prints the same snapshot without filing a transmittal, writing Jira, or opening Outlook. Generic stays omitted. Console is **0.94**.

## 2026-09-10 — Cover from the letter; slimmer EDDI list

Load reads TO, CC, and project description from the existing CT/ST/FT TRANSMITTAL sheet when those cells are already filled (Sarah’s books). PEP is only the fallback for blank cells. **Locate PEP…** still overwrites the cover. EDDI pack list drops Description, client name, location/tag, Include in Databook, and Comments. Columns are Document, Client Doc No., Rev, Submitted for, Submission Date, under the same EDDI group headings. Console is **0.93**.

## 2026-09-10 — EDDI pack list, not the template book

Confirm no longer fills `EDDI-*.xlsm`. It builds a dated pack list in `3.0 Doc Con` (`EDDI-{job}-{date}.xlsx` + PDF) from this pack’s Next values: EDDI group headings, then only those items. Dummy template rows are not copied. Not attached to Outlook. Console is **0.92**.

## 2026-09-10 — Zip drawings, not the transmittal form

Outlook attachments are the transmittal PDF plus `{CT|ST|FT}-{job}-{n}.zip` of the packed drawing PDFs. The transmittal form PDF is not in the zip. EDDI PDF is not in the zip or the mail. Console is **0.91**.

## 2026-09-10 — Saved TO / CC addresses

Settings keeps a list of email addresses on this PC (LOCALAPPDATA, not Dropbox). Cover TO and CC have **Pick…** to add one to the box (semicolon, unique). Addresses only. Console is **0.90**.

## 2026-09-10 — EDDI write-then-print on Confirm

Confirm copies packed Next values onto matching rows in `{job}/3.0 Doc Con/EDDI-{job}.xlsm` (sheet **Project**), stamps the job and Date issued, and prints `EDDI-{job}-{date}.pdf` beside the book (same Excel print as the CT cover). Template `EDDI-202X-XXX.xlsm` is renamed on Load. The EDDI PDF is an audit copy — not attached to Outlook. A failed EDDI snapshot does not roll back Jira or the transmittal tab. Console is **0.89**.

## 2026-09-10 — Cancel Next

**Cancel Next** on the pack bar throws away typed Next values and copies Now back. Jira is not written. Pack ticks stay. Console is **0.88**.

## 2026-09-10 — Bundle headings drop “- EDDI”

Group headers on the pack are `4 - Engineering`, not `4 - Engineering - EDDI`. Jira still stores the full EDDI Status option. Console is **0.87**.

## 2026-09-10 — Shop and Field Confirm

Shop and Field Confirm write the **ST** and **FT** Excel letters (not the CT form). Number is `C2`; job is `I4` (shop) / `I6` (field); document list uses A/G/I/J/K. Console TO/CC stay empty on Shop/Field (not the PEP client list). Outlook still opens a draft; empty TO is allowed. Folder copy after send stays later. Agent must not write any Dropbox job folder except `2026-Tanzim`. Console is **0.86**.

## 2026-09-10 — Shop/Field Confirm: same path, empty TO/CC for now

Shop and Field will reuse Client Confirm (same board, Jira writeback, File + PDF + Outlook draft). They use `ST-{job}.xlsm` / `FT-{job}.xlsm`, not the CT book. Cover TO/CC are **not** the PEP client list and **do not go to the client**. Recipients come later as an explicit list. Until then the console TO and CC boxes stay **empty** when Shop or Field is selected (Client PEP defaults stay on Client). Confirm must not require a TO address for ST/FT. Folder copy after send (shop IFC/ITP/MID/BOM; field into `8.0`) stays later. Do not File/Confirm 075.

## 2026-09-10 — Shared WPS/PQR library

Weld procedures live in the person Dropbox folder `4.4 QC / 4.4.1 WPS&PQR` (files like `EIS-1 (Rev 4).pdf`), not under the job. Auto-match scans that library on each Dropbox person root, skips VOIDS / Old Procedures / Original WPS, and only attaches a hit when a pack row matches (unused library PDFs are not extras). Job-folder Quality/Engineering scans are unchanged. Console is **0.85**.

## 2026-09-10 — Extra PDF folders; attach PDFs; frozen headings

Auto-match also looks in `1.0 Engineering` (MR), `4.0 Quality/4.3` (ITP & WO), `4.7` (weld summary), and `4.4.1` (weld procedures). Skip Void. Confirm attaches the transmittal PDF and each drawing PDF in Outlook — no zip. Pack/Drawing/Description and the other column headings stay visible while the list scrolls. Console is **0.84**.

## 2026-09-10 — Locate missing PDF; skip Generic; Pack tick

Missing PDF shows **Locate…** on the row (and **Locate PDF…** on the bar). That pairs the file for the zip; it does not rewrite the Jira summary. Located paths are kept in `client-pack.json`. EDDI **0 Generic** is not listed. Pack select is a teal tick, not the clam checkbox cross. Console is **0.83**.

## 2026-09-10 — Load every Jira issue for the Job Number

Load no longer filters to Sub-task + label Drafting. It searches Job Number on the project (excluding issue type Project) and also walks children of the job Project so EDDI items without the field still appear. The pack is grouped by EDDI Status (0–9, Ungrouped last) with a full-width header between groups. Console is **0.82**.

## 2026-09-09 — EDDI PDF snapshot parked

Built 2026-09-10: Confirm writes Next values into the EDDI `.xlsm` then prints a dated PDF in `3.0 Doc Con`. Not attached to Outlook.

## 2026-09-09 — Cover dates open the calendar on click

Date issued and Expected return have no Today / Calendar… / N/A buttons. Click the box. Expected return’s calendar still has **N/A**. Console is **0.81**.

## 2026-09-09 — Excel File no longer dies on merged D12

Resetting TRANSMITTAL after File used `ClearContents` on D12. That cell is merged with E12 (Expected return), so Excel aborted after the numbered tab was copied. Clear now uses the merge area. Console is **0.80**.

## 2026-09-09 — Confirm preflight: abort writes nothing

Confirm checks every Jira status hop and the file/PDF zip first. If a hop is blocked or the book/PDFs are not ready, it stops and does not write Jira or create a tab. Jira is written only after that check; if a later Jira write or Excel file fails, already-written Jira is rolled back. Console is **0.79**.

## 2026-09-09 — Batch Next has no Description editor

Batch Next (Pack all / Apply to Pack) sets Status and the Jira fields only. Description stays on each drawing row, not on the pack bar. Console is **0.78**.

## 2026-09-09 — Click a date cell for the calendar

Every date field opens the calendar on a single click: pack Next (Due Date, Submission Date, Return Request Date, Return Date, Shop/Field IFC Date), Batch Next, and cover Date issued / Expected return. Typing YYYY-MM-DD still works if you tab into the cell. Console is **0.77**.

## 2026-09-09 — Pack fields + sideways scroll

Pack Now/Next includes Status, Due Date, Client Doc No., Outgoing Rev, Submitted to Client For, Submission Date, Return Request Date, Incoming Rev, Client Approval Status, Return Date, Shop IFC Rev/Date, Field IFC Rev/Date, EDDI Status. The drawing table and Batch Next have a horizontal scrollbar (Shift+wheel also pans). Dates are YYYY-MM-DD; double-click opens the calendar. Cover Date issued / Expected return stay on the Excel letter. Console is **0.76**.

## 2026-09-09 — Client Document Number column label

Board and Batch Next show **Client Doc No.** (Jira field remains Client Document Number).

## 2026-09-09 — Cover FROM column was crushed

TO/CC Text boxes defaulted to 80 characters wide, so FROM showed as “FRC” and only the letter d from doc.control. Cover columns now keep a minimum width. Console is **0.75**.

## 2026-09-09 — Console theme

DocCon uses a navy chrome bar, teal Confirm, light cards, and Segoe UI instead of stock tkinter gray. Settings and the calendar use the same look. Console is **0.74**.

## 2026-09-09 — Client Document Number on the pack

Jira **Client Document Number** (`customfield_10279`) is a Now/Next field on packed drawings (free text, not a dropdown). Confirm writes it to Jira. It does not replace Elite Drawing on the Excel log. Console is **0.73**.

## 2026-09-09 — Cover strip at the bottom

Cover (FROM / TO / CC / Project) is a horizontal strip under the drawing list, not a right-hand column. The board keeps full width. Console is **0.72**.

## 2026-09-09 — Drawing vs Title columns left split

Board still shows **Drawing** (summary first token) and **Title** (remainder). Combining them into one Summary column is deferred.

## 2026-09-09 — TO and CC are email addresses only

Console TO/CC (and the Outlook/Excel cover lines) keep email addresses, not names or roles from the PEP. Type more CCs as `name@company.com; other@company.com`. PEP still supplies defaults from D50/D51 and any emails in the PM/PE cells. A saved pack that only had names falls back to those PEP emails. Console is **0.71**.

## 2026-09-09 — Confirm writes the Save draft

**Confirm…** writes `client-pack.json` (TO/CC/project, dates, Pack ticks) before Jira/file/mail. If that write fails, Confirm stops. Saves again when Confirm finishes.

## 2026-09-09 — Save button label

The Dropbox draft control is **Save** (not Save pack). Same `client-pack.json`.

## 2026-09-09 — Version 0.70

Prerelease console is **0.70** (window title and pyproject). Not 0.1.0.

## 2026-09-09 — Batch Next on the list; calendar dates

**Batch Next** at the top of the drawing list: Pack all / none, then dropdowns for Status and the Jira fields. **Apply to Pack** writes those Next values onto Pack-ticked rows only; blank batch boxes are skipped. Date issued and Expected return have **Today** and **Calendar…**. Expected also has **N/A**. Confirm is still the one send click.

## 2026-09-08 — One Confirm button: Jira + file + Outlook draft

Open the console, edit Next, tick Pack, **Confirm…**. That writes changed Jira fields/status on packed drawings, files the CT log and cover PDF, zips the pack, opens Outlook. Operator still clicks Send. Save to Jira is gone. Save pack is only the Dropbox draft (TO/CC).

## 2026-09-08 — One pack action: File and email

Fill, File, and Email draft are one confirm. **File and email…** writes TRANSMITTAL, files the numbered tab + cover PDF, zips `CT-{job}-{n}.zip`, opens Outlook from this PC. Operator still clicks Send. Save to Jira stays its own button. Excel Add Page / File Transmittal still work by hand.

## 2026-09-08 — Status is a Next dropdown; Save uses workflow transitions

Status cannot be PATCHed. Next Status sits under Now. **Save to Jira…** GETs allowed transitions and POSTs the hop whose destination matches the chosen status. Dummy To Do drawings cannot jump to IFI/IFC/OFA (workflow condition); In Progress, Done, Back from Client, etc. can. Does not auto-walk the workflow.

## 2026-09-08 — Jira fields on each drawing row (Now / Next)

No side panel. Each drawing is two rows: **Now** (current Jira, read-only) and **Next** (dropdowns for Outgoing Rev, Purpose, Incoming Rev, Client stamp, Shop/Field IFC). Tick **Pack** for Fill / File / Email. **Save to Jira…** writes only Next values that differ from Now. Pack ticks restore from `client-pack.json`.

## 2026-09-08 — Email draft from this PC’s Outlook

**Email draft…** zips cover PDF (if filed) + matched drawing PDFs to `3.1.1 Out` as `CT-{job}-{n}.zip`, then opens Outlook from the signed-in account on this machine. Does not Send As doc.control. Does not auto-send. Cover FROM on the Excel letter is unchanged.

## 2026-09-08 — Last-record fields edit on the console, Save to Jira

Select drawing row(s). Right pane **Jira**: Outgoing Rev, Purpose, Incoming Rev, Client stamp, Shop/Field IFC Rev. **Save to Jira…** confirms then PATCHes those option fields. Blank values are skipped (not cleared). Status is not transitioned. Does not send mail.

## 2026-09-08 — Cover TO/CC/project on the console

Right-hand Cover pane: FROM is read-only (`doc.control@…`). TO, CC, and project description are editable. Defaults come from the PEP; **Save pack** (and leaving a field) writes `{job}/3.0 Doc Con/DocCon/client-pack.json`. Fill/File uses the console lines, not a second Jira file.

## 2026-09-08 — Console TO/CC/project; pack file in the job folder

PEP still fills the defaults. Operator can change TO, CC, and project description on the console for this send (FROM stays doc.control). Those edits do not rewrite `7.0 Sales`. Draft progress lives at `{job}/3.0 Doc Con/DocCon/client-pack.json` so Dropbox shares it with Sarah. Jira site/token stay in LOCALAPPDATA / Credential Manager, not in that file.

## 2026-09-08 — Mail is Sarah’s Outlook, not Tanzim’s

`doc.control@…` lives on Sarah’s PC. DocCon will not Send As from Tanzim’s mailbox and will not open Outlook by itself. Confirm send (later, on her machine) writes the zip in `3.1.1 Out` and opens a draft in the DocCon Outlook profile for her to send. Fill/File/Jira can be tested here without mail.

## 2026-09-08 — Excel Unprotect must not prompt

Fill/File was calling `Unprotect()` with no password. Excel COM shows the password box for that; DisplayAlerts does not hide it. Unlock now uses only the template lock (same as the CT VBA). Do not Unprotect from the Review tab.

## 2026-09-08 — Client pack: folder zip and Outlook attach

Same bundle both places. Cover PDF (`CT-{job}-{n}.pdf`) plus the matched Current PDF files for the selected rows. Zip lands in `3.1.1 Out` as `CT-{job}-{n}.zip`. Outlook FROM the DocCon mailbox, TO/CC from PEP, those files attached. Confirm still required; does not auto-send. Shop/Field stay folder-copy (IFC), not this zip. Email body/subject wording not locked.

## 2026-09-08 — Edit on the console, confirm writes Jira

Document controller updates last-record fields in DocCon, not in the Jira Excel export. Typing is local until they confirm; that confirm PATCHes the drawing sub-tasks. Does not send mail. Outlook stays a later confirm. Do not auto-bump rev.

## 2026-09-08 — Controller update columns are Jira fields

The spreadsheet a document controller uses to update transmittal data points is a Jira download/export. Those columns are the drawing custom fields (Outgoing Rev, purpose, Incoming Rev, approval, Shop/Field IFC, etc.). DocCon writes them back through Jira REST, not by round-tripping that export. The CT/ST/FT `.xlsm` books stay the transmittal log; they are not that export.

## 2026-09-01 — Original Excel workflow stays

The CT/ST/FT `.xlsm` books remain the log. DocCon does not replace them. **Fill TRANSMITTAL…** writes cover + rows on the working sheet only (no numbered tab, n stays put, Add Page / File Transmittal stay in Excel). **File Client Transmittal…** is the optional shortcut (archive tab + PDF). Close the CT book before either write.

## 2026-09-01 — File Client uses Excel for .xlsm

openpyxl save was dropping the Elite logo and Add Page / File Transmittal buttons (the “1” in the corner is the page-count cell under the missing logo). File Client now copies TRANSMITTAL through Excel, like the book’s own File Transmittal. Load no longer stamps a real .xlsm with openpyxl. If the logo/buttons are already gone, File restores them from the jobs-template CT book.

## 2026-09-01 — Locate PEP / File after Load

Locate PEP and File Client use the Job Number box plus the loaded job, and look up the Dropbox folder again if it was missed. They no longer treat “folder not found” as “you never loaded.”

## 2026-09-01 — CT cover fills from PEP; dates on the console

File Client writes FROM (`doc.control@…`), TO (PEP D50), CC (PEP D51 + Elite PM/PE names), and the project line (client / site / tank / PO / WO) from `7.0 Sales`. Date issued and Expected document return are console fields (return can be a date or text like N/A). If no usable PEP is in Sales, Locate PEP…. Blank C-109.5 and leftover template PEP PDFs are not auto-picked. Tanzim may use a copied 075 PEP.

## 2026-09-01 — PEP in 7.0 Sales is the cover source

Project Execution Plan lives in `7.0 Sales`. Same form as `C-109.5` Excel, issued as PDF (075 has Rev0–Rev2). Transmittal Recipients Main (`D50`) is the CT **TO** line; CC's (`D51`) plus Elite EM/PM/PE is **CC**. Also on that sheet: client, site, tank tag, PO — the project description line. On a real job: highest Rev whose filename is this Job Number. **`2026-Tanzim` has no real PEP** — a copied live PEP in that folder is the sandbox stand-in (do not require the filename to be 2026-Tanzim).

## 2026-09-01 — Auto-name CT/ST/FT books on Load

Load a job: if the books are still `CT-202X-XXX.xlsm` / `ST-20XX-XXX.xlsm` / `FT-20XX-XXX.xlsm`, DocCon renames them to `CT-{job}.xlsm` (and ST/FT) and stamps the Job Number into the placeholder cell. Already-named live books (`CT-2026-075.xlsm`) are left alone.

## 2026-09-01 — Client transmittal from the console

Radios: Client / Shop / Field. Only Client writes. Select drawing rows → File Client Transmittal… fills `TRANSMITTAL`, copies a numbered tab, bumps n, prints `CT-{job}-{n}.pdf` beside the book. Template `CT-202X-XXX.xlsm` is renamed to `CT-{job}.xlsm` on first file. Refuses a book whose A12 is another job (will not file Tanzim into 075). 27 tests passed. Shop/Field later.

## 2026-09-01 — Sandbox job `2026-Tanzim`

User created `2.1 Current Jobs\2026-Tanzim` from the jobs template. Live jobs stay untouched. Blank books still named `CT-202X-XXX.xlsm` / `ST-20XX-XXX.xlsm` / `FT-20XX-XXX.xlsm`; job cell still `202X-XXX`; Current PDF empty. Do not File Transmittal on 075.

## 2026-09-01 — Transmittal log is the Excel books

Live books on 2026-075 plus Document Control Templates QRG. Three independent counters:

- Client `3.1.1 Out/CT-{job}.xlsm` → `CT-{job}-{n}` (075 next is 11)
- Shop `3.2/ST-{job}.xlsm` → `ST-{job}-{n}` (075 next is 5)
- Field `3.3/FT-{job}.xlsm` → `FT-{job}-{n}` (075 next is 4)

Working sheet is always **TRANSMITTAL**. **Add Page** (`INSERT_PG`) only unhides overflow rows (max 3 print pages). **File Transmittal** (`counter`) copies that sheet to a tab named with the current number, clears the list, bumps n+1. Then print that tab to `{CT|ST|FT}-{job}-{n}.pdf`. Client also zips attachments into 3.1.1 Out; shop/field copy IFC files. Unused filed tab: `FILED IN ERROR, NOT USED YET` in the date cell so the number is reused.

## 2026-09-01 — Dropbox path remaps like Databook

Same rule as the Engine: keep everything after `Elite Integrity Serv Dropbox/<person>/`, attach it to this PC’s person folder. `2.0` vs `2.1 Current Jobs` both tried. Sarah’s path works on Tanzim’s PC and the other way around.

## 2026-09-01 — Manual Match PDF adopts filename on Jira

Select a row → Match PDF… → confirm. Summary first token becomes the PDF drawing ID (title kept). Local row turns High. Close and relaunch DocCon to use it.

## 2026-09-01 — PDF match from Current PDF folders

DocCon finds `{Job Number} …` under Current Jobs, scans `2.0 Drafting/**/Current PDF`, skips Void. Live: 2026-096 folder found (SK1 PDFs; Jira 1-1/1-2 still Missing). 2026-075 has 17 current PDFs. 15 tests passed.

## 2026-09-01 — Slice 1 live: job 2026-096

Sarah-path works. Loaded `2026-096` → 2 Drafting sub-tasks (`P2024-15630` `2026-096-1-1 Drawing-1`, `P2024-15631` `2026-096-1-2 Drawing-2`). Parent was `2026-096 Manway Package Drawing` (not always named “Drawing Package”). Outgoing Rev / purpose empty on those rows. No send yet.

## 2026-09-01 — Slice 1 running

Python tkinter console: Settings (Jira site/email/token in Credential Manager) + Load Job Number → drawing table. Run `python -m doccon`. Tests: 8 passed. No Outlook, PDFs, or writeback yet.

## 2026-09-01 — Develop in thin slices; settings only when needed

Do not build a giant Settings dump first. Slice 1 (when asked): Jira token in Settings + load one job’s drawings. Outlook account, PDF root, log, writeback UI wait for those slices.

## 2026-09-01 — Mobile is a later companion, not slice 1

Full match/OCR/Outlook-COM console on iPhone is a poor fit. A later thin app (pick job, see Jira rows, maybe confirm send via Graph) is possible after desktop + Graph mail. Do not start mobile now.

## 2026-09-01 — No extra Jira status; engineer emails Sarah

Engineer sends Sarah the list with details. Sarah runs DocCon. No custom status or include-field. Next process fact: where issued PDFs live. First code (when asked): Settings + Jira pull.

## 2026-09-01 — Outlook owns email login

DocCon does not collect the DocCon mailbox password. The workstation Outlook profile is already signed in (MFA/Modern Auth). Settings chooses that account. If Outlook is logged out, DocCon refuses send and asks to sign in there.

## 2026-09-01 — Send from DocCon mailbox

Outlook on the PC sends as the existing DocCon email account (shared mailbox / Send As), not the operator’s personal address. Confirm send still required.

## 2026-09-01 — DocCon is the trigger

Open DocCon → fetch Jira for that job → pick the bundle → Confirm send → update those Jira issues. Jira is not the start button. Include-checkbox optional as a hint only.

## 2026-09-01 — Bundles in DocCon, not Jira

Engineers send different subsets on different transmittals. Jira does not get a pack-ID or a new parent per combo. Checkbox = eligible. Each DocCon Confirm send is one bundle; only those ticks are cleared.

## 2026-09-01 — Token in Settings, not in code

DocCon Settings: operator pastes a new Jira API token (and email/site). Saved to Windows Credential Manager. Replace when it expires. Never Dropbox, git, or a coded constant.

## 2026-09-01 — DocCon is notified by pull, not webhook

Jira cannot reach the operator PC. DocCon tray/on-open JQL-polls drawings with Include in next transmittal set. Optional Jira Automation emails the person a `doccon://` link. No public webhook.

## 2026-09-01 — Mark drawings in place (field, not reparent)

User rejected moving drawings under Document Transmittals. Parent stays Drawing Package. Prefer custom field on the drawing: Include in next transmittal. Not a new IFC-style status. DocCon queues by Job Number + field. After send, clear the field.

## 2026-09-01 — Controller path (plain)

Engineer transitions drawing sub-tasks when those sheets should go out. That is the “include these” signal, not the send. Document controller opens the job’s Document Transmittals task and clicks into DocCon. DocCon loads that Job Number, shows last record, and highlights what the engineers just moved. Controller matches PDFs and confirms. Email does not leave on the Jira transition.

## 2026-09-01 — No custom field for Jira trigger

Do not create a new Jira field to start a transmittal. The Document Transmittals task is the button. Use a click, workflow transition, or Automation manual rule plus `doccon://job/<Job Number>`. Drawing custom fields stay last-record data.

## 2026-08-21 — Trigger flow mapped on canvas

Architecture canvas updated: Trigger tab (Jira start vs field data vs confirm send), dummy job tree, live field IDs.

## 2026-08-21 — Trigger from Jira is wanted

Start the pack from the job’s Document Transmittals task. Deep link (`doccon://job/<Job Number>`) and/or Dropbox inbox to the desktop app. Confirm send stays in DocCon. Jira field edits still do not email the client.

## 2026-08-21 — Jira changes do not trigger send

Register updates (Outgoing Rev, purpose, etc.) are data, not a start button. DocCon pulls on job open and diffs vs last pack. Person confirms. No webhook-to-email.

## 2026-08-21 — Remaining process details parked

User will explain later: PDF folder layout, log template, transmittal numbering, post-send writeback. Do not keep asking. Jira contract + last-record rule are enough to hold.

## 2026-08-21 — Ready-to-send is last record + engineer

Not a Jira status gate. DocCon fills Outgoing Rev / Submitted to Client For (and related stamps) **as the engineer says**, using the drawing’s **last record** (Outgoing Rev, Incoming Rev, Client Approval Status, Shop/Field IFC Rev).

DocCon should surface that last record on the register so the operator is not hunting history. Do not auto-pick the next rev.

**Next:** issued PDF folder layout, then log template / transmittal numbering.

## 2026-08-21 — Live Jira read succeeded

Read-only REST to `https://eliteintegrityservices.atlassian.net` as Tanzim Nasir. No writes. Token was not saved in this folder — revoke the chat-pasted token.

- Dummy Project `P2024-15553` (`2026-Tanzim Test`, Job Number `2026-Tanzim`) spawned the Elite template: Drawing Package, Document Transmittals (label DocCon), Databook, QC, etc.
- Drawing rows: Sub-tasks `P2024-15578` / `P2024-15579` under Drawing Package `P2024-15577`.
- Field map locked: Job Number `customfield_10300`, Outgoing Rev `customfield_10280`, Submitted to Client For `customfield_10281`, Incoming Rev `customfield_10283`, Client Approval Status `customfield_10284`, Shop/Field IFC revs, EDDI Status.
- Live drawing shape confirmed on job `2026-075` (status IFC, Outgoing Rev 0, purpose Info).

**Next:** decide what “ready to transmit” looks like on a drawing sub-task, then PDF folder + log.

## 2026-08-21 — Dummy issue identified

- `P2024-15553` — summary `2026-Tanzim Test`
- Connectivity test only; summary is not the production pattern (`2026-075-1-1 Drawing 1`).

**Still waiting:** Atlassian email + API token for `GET /rest/api/3/issue/P2024-15553`.

## 2026-08-21 — Jira site identified

- Cloud: https://eliteintegrityservices.atlassian.net
- Project key from board URL: `P2024` ([project list](https://eliteintegrityservices.atlassian.net/jira/core/projects/P2024/l))

**Still waiting:** dummy issue key + Atlassian email + API token for a read-only GET.

## 2026-08-21 — Project memory created

Put standing context in this folder so new Cursor chats load the DocCon plan:

- `.cursor/rules/doccon-project.mdc`
- `.cursor/rules/jira-register.mdc`
- `.cursor/rules/architecture.mdc`
- `AGENTS.md`

**Still waiting:** dummy Jira job + site URL + issue key + read-only token (or local env var) so we can `GET` one issue.

## 2026-08-21 — Planning session (morning chat)

Started automated transmittal design. Architecture canvas lives outside Dropbox:

`C:\Users\TanzimNasir\.cursor\projects\c-Users-TanzimNasir-Elite-Integrity-Serv-Dropbox-Tanzim-Nasir-2-7-Engineering-2-7-5-Software-Elite-DocCon-Suite\canvases\doccon-transmittal-architecture.canvas.tsx`

Locked:

- Jira stays the register; DocCon is match / log / send / audit
- One issue = one drawing (task or sub-task)
- Summary holds drawing number + title (`2026-075-1-1 Drawing 1`)
- Talk to Jira over REST, not the webpage
- No application code and no Dropbox job-file edits during planning
- User wants a live Jira read on a dummy ticket before more design

Not locked: revision field, document type field, ready-status, site URL, PDF folder layout, log format, transmittal numbering.
