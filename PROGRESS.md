# Progress log

Newest first. Append a dated entry when a decision is locked, a test runs, or the next step changes.

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
