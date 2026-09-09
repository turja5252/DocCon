# Elite DocCon Suite — agent briefing

Read this file and `PROGRESS.md` at the start of every session.

## What this is

Elite DocCon is a planned **document-control transmittal workstation**. Document controllers keep the drawing register in **Jira**, then today they manually match issued drawing PDFs, type a transmittal log, and email the pack to the client. DocCon should automate the matching, log, send, and Jira writeback. A person still confirms before anything leaves.

Jira remains the source of truth. DocCon is the execution layer, in the same product family as Elite Databook Engine (Python desktop, Dropbox job folders, Windows settings).

## Locked decisions

| Topic | Decision |
| --- | --- |
| Register | Jira. Do not build a second drawing tracker. |
| Identity | One drawing = a **Sub-task** (label `Drafting`) under the job’s Drawing Package task. Job itself is issue type **Project**. |
| Summary | Drawing ID + title, e.g. `2026-075-1-STWD SPIRAL STAIRWAY: INSIDE HANDRAIL DETAIL`. Job Number is `customfield_10300`. |
| Revision | **Outgoing Rev** `customfield_10280` — not in the summary. |
| Transmittal | A DocCon event. The **log** stays the job’s Excel books under `3.0 Doc Con`. **Confirm…** writes Next values to Jira, fills TRANSMITTAL, files the numbered tab + cover PDF, zips the pack, and opens an Outlook draft (one click). **Add Page** / **File Transmittal** still work in Excel. Cover FROM stays `doc.control@…`. **TO / CC** are email addresses only (PEP defaults, then the operator can type more with a semicolon). Project line defaults from the PEP. Console edits do not rewrite the Sales PEP. Pack progress is `{job}/3.0 Doc Con/DocCon/client-pack.json` on Dropbox so Sarah and Tanzim share it. Not LOCALAPPDATA, not the CT `.xlsm`. No tokens in that file. |
| Integration | HTTPS REST v3. No browser scrape, no Zapier as the core. |
| Send | Never auto-send. Confirm click required. Open the console, edit Next on packed drawings (including Client Document Number), click **Confirm…**. That PATCHes changed Jira fields, transitions status when the workflow allows, files the pack, and opens an Outlook draft. Typing does not write until they confirm. Exact field list per event still open. |
| Mail | **Confirm…** opens Outlook from whoever is signed in on this PC (Tanzim’s mailbox here, DocCon mailbox on Sarah’s). Does not Send As `doc.control` and does not auto-send. Cover TO/CC from the console. Zip of cover PDF + matched drawings lands in `3.1.1 Out` as `CT-{job}-{n}.zip` and is attached. Cover FROM on the Excel letter stays `doc.control@…`. |
| Secrets | API tokens in Windows Credential Manager, never Dropbox or git. **Settings screen in DocCon:** site, email, paste/replace token. No coding, no `.env`. |
| Jira site | Cloud: [eliteintegrityservices.atlassian.net](https://eliteintegrityservices.atlassian.net). Project `P2024`. |
| Trigger | **Sarah runs DocCon.** Engineer emails her the list and details for this pack. No new Jira status or include-field required. She opens the job in the console; DocCon fetches Jira; she picks the bundle from that list; Confirm send updates those issues. |

## Jira summary parse

Live example: `2026-075-1-STWD SPIRAL STAIRWAY: INSIDE HANDRAIL DETAIL`

- First token (`2026-075-1-STWD`) — drawing identity (match to PDF)
- `customfield_10300` Job Number (`2026-075`) — group a transmittal
- Remainder — title only
- Dummy template: `2026-Tanzim-1-1 Drawing-1`

## Next action

No extra Jira status or custom trigger field. Engineer emails Sarah the pack list; she runs DocCon.

**Next:** Close and relaunch DocCon. Load `2026-Tanzim`. Tick Pack, use Batch Next or edit a row, pick dates from the calendar, **Confirm…**. Do not run it against 075.

## Do not

- Write application code until the user asks
- Edit unrelated Dropbox job files
- Commit secrets
- Scrape Jira in a browser
- Auto-send email or mark Jira issues transmitted without a confirm step
