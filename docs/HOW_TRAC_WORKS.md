# How TRAC works

A plain-English tour for the person who owns TRAC. You do not need to read code. This page tells you what each part is for, where it lives, and what happens when someone uses the site. For day-to-day jobs (editing content, roles, going live) see [MAINTAINING.md](../MAINTAINING.md).

## What TRAC is, in three sentences

TRAC is Tech Risk's website of guidance: guides, FAQs, control patterns, risks and Library pages (each category with switchable platform specifics) that anyone in the firm can read and comment on. Only Tech Risk can write it, and every change must be approved by a second Tech Risk person before it becomes official. Every old version and every approval step is kept, so you can always show who changed what and when.

## The building blocks

TRAC is built with **Django**, a popular toolkit for making websites in Python. These are the words you will hear, each with where it sits in TRAC.

| Word | What it means | In TRAC this is... | Folder |
|---|---|---|---|
| **Django** | The toolkit TRAC is built on. It handles web requests, the database and sign-in so we do not write those from scratch. | The engine under everything. | (installed, not in our folders) |
| **App** | One self-contained section of the site, with its own pages, tables and tests. | `wiki` (guides and FAQ), `rcm` (controls and risks), `platforms`, `topics`, `review` (comments), `manage`, `accounts` (sign-in), `core` (drafts and approvals), `ui` (look and feel). | `apps/<name>/` |
| **Model** | A database table, described in code: what is stored and what each field is. | A guide page (`Page`, `PageVersion`), a control (`Control`, `ControlVersion`), a visitor comment (`Feedback`), the audit log (`AuditEvent`). | `apps/<name>/models.py` |
| **View** | The code behind one page: it receives the request, gathers the data and picks the template. | The function that finds a guide and shows it (`page` in `apps/wiki/views_read.py`). | `apps/<name>/views*.py` |
| **Template** | The page's HTML with blanks to fill in, such as the title and body. | `wiki/page.html`, which draws a guide. Shared pieces (pills, cards, the heading band) are in `templates/components/`. | `apps/<name>/templates/` and `templates/` |
| **URL list** | The address book: it says which view answers which web address. | `/guides/<name>/` goes to the guide view. | `apps/<name>/urls.py`, and `config/urls.py` at the top |
| **Migration** | A saved instruction for changing the database layout (add a table or column) in a safe, repeatable order. | Files like `apps/core/migrations/0002_content_sync.py`. They run automatically on release. Never edit one by hand. | `apps/<name>/migrations/` |
| **Management command** | A task you run from the command line instead of a web page. | `check_content`, `sync_content`, `export_content`, `load_demo`, `setup_trac`. | `apps/<name>/management/commands/` |
| **Test** | A small program that checks one thing still works, such as "a read-only user cannot edit". | Hundreds of checks. Run them before and after any change. | `apps/<name>/tests/` |
| **Static files** | Files sent to the browser unchanged: styling (CSS), small scripts (JS), fonts. | `trac.css` holds the colors and shared pieces; `trac-ui.js` handles clicks like Expand all. | `static/` |
| **Settings** | The switches that control how the site runs. | `config/settings/base.py` (shared), `dev.py` (your computer), `prod.py` (live), `test.py` (tests). Secrets such as `SECRET_KEY` and `DATABASE_URL` come from the environment, never from the code. | `config/settings/` |

## Folder map

| Folder | What is in it |
|---|---|
| `apps/accounts` | Who you are: sign-in, roles, and the one permissions table (`permissions.py`). |
| `apps/core` | The draft, review and publish engine, the audit log, history pages and the content-sync rules. |
| `apps/wiki` | Guides, best practices, FAQs and visitor comments. |
| `apps/rcm` | Controls, risks, drivers, evidence rules and the explorer. |
| `apps/platforms` | Platforms, technology categories and their guidance. |
| `apps/topics` | Topics, lifecycle stages and themes. |
| `apps/review` | The comment box, My comments and the Review queue. |
| `apps/manage` | Tech Risk screens for topics, platforms and aspect questions. |
| `apps/ui` | Shared look and feel, template tags and the component gallery (`/ui/gallery/`). |
| `content/` | The guides (Markdown), controls and risks (YAML), the platform list and category and platform guidance (YAML), and the risk engine's copied files plus `drivers/drivers.json` (TRAC's own details for each driver), as plain files you can edit. |
| `templates/` | Page pieces shared by every app (`base.html`, `components/`). |
| `static/` | CSS, JavaScript and bundled libraries and fonts. |
| `config/` | Settings, the top-level URL list and the web entry point. |
| `docs/` | This page. |
| `trac.ps1` | The PowerShell helper for everyday jobs (`.\trac.ps1 help`). |

## Four journeys

### (a) Someone opens a guide page

1. The browser asks for `/guides/oversight-levels/`.
2. `apps/accounts/middleware.py` works out who the visitor is and which roles they hold.
3. `config/urls.py` sends anything starting `/guides/` to `apps/wiki/urls.py`, which names the view `page` in `apps/wiki/views_read.py`.
4. The view checks the visitor may read (`can_view`), then asks `apps/core/detail.py` which version to show. Visitors get the published version; drafts show only to Tech Risk and the person who wrote them.
5. The text is cleaned by `apps/wiki/richtext.py` (unsafe formatting removed, heading links added, each main heading turned into a card).
6. The view hands the data to `apps/wiki/templates/wiki/page.html`, which uses the shared pieces in `templates/components/` and the styles in `static/css/`. The browser shows the page.

### (b) Tech Risk edits a page and it is approved

A page's text is never overwritten. Each edit creates a new numbered **version**, and each version moves through four states: **draft**, **in review**, **approved**, **published**.

1. On the guide, Tech Risk clicks **Edit** (`/guides/edit/page/<name>/`, handled by `page_edit` in `apps/wiki/views_edit.py`, form in `apps/wiki/forms.py`).
2. Saving calls `propose_change` in `apps/core/versioning.py`. That makes version N+1 as a **draft**. Readers still see the old published version. Only the author can edit or discard the draft, and only one open draft can exist per page.
3. **Submit for review** (`apps/core/workflow.py`, address `/workflow/.../submit/`) moves it to **in review**. The text is now locked.
4. A different Tech Risk person opens it in the **Review queue** and clicks **Approve and publish**. The rule that the approver cannot be the author lives in `apps/core/workflow_rules.py`. (Single-approver mode, `ALLOW_SELF_APPROVAL`, relaxes it for one person.) They can **Reject** with a comment instead.
5. That button approves and publishes in one step: the new version becomes what readers see, and the old one stays in history.
6. Every step writes a permanent line to the audit log (`apps/core/audit.py`, `AuditEvent`). The **View history** link shows them (Tech Risk and auditors only).
7. Retiring a page works the same way: **Retire** with a reason, then a second person approves.

### (c) A content file is synced

Files in `content/guides/*.md`, `content/controls/*.yaml`, `content/platforms/` and the risk engine copies in `content/engine/` (the guidance for each category and platform) are an easy way to write many things at once. The site is still where approval happens.

1. You edit a file, for example `content/guides/oversight-levels.md`.
2. `.\trac.ps1 check` runs `check_content`: it reads every file and reports mistakes in plain words (`apps/wiki/guide_checks.py`, `apps/rcm/control_files.py`, `apps/platforms/guidance_files.py`).
3. `.\trac.ps1 sync` runs `sync_content --user <you>`. It runs the guide sync (`apps/wiki/guide_sync.py`), then the risk engine sync (`apps/rcm/engine_files.py`, drivers before controls because TRAC risks link to drivers), then the controls sync (`apps/rcm/control_files.py`), then the platform guidance sync (`apps/platforms/guidance_files.py`). The list of platforms itself (`content/platforms/catalog.yaml`) is loaded earlier by `seed_platforms`, because guidance files refer to platforms by name.
4. For each item, `apps/core/content_sync.py` decides one thing: **new** (becomes a draft), **unchanged** (left alone), **in progress** (a change is already open in the site, so skipped), **edited in the site** (someone changed it in the site since the last sync, so skipped to protect their work), or **update** (becomes a new draft version). The rule uses a small record (`ContentSync`) of which version last matched the file.
5. The result is a draft that waits for a second person. `-Publish` (`--publish`) approves and publishes straight away, but only in single-approver mode.
6. If someone edited in the site, run `.\trac.ps1 export` first. It writes the site's text back into the files so nothing is lost. `--force` replaces the site's version with the file's.

### (d) A visitor leaves a comment and it reaches the Review queue

1. Most pages show a **Comment on this page** box. `templates/base.html` includes `apps/review/templates/review/comment_box.html`; `apps/review/context_processors.py` hides it on forms and Manage pages.
2. The visitor picks a section and writes a comment. The form posts to `/review/comment/`, handled by `comment` in `apps/review/views.py`.
3. That calls `leave_feedback` in `apps/wiki/feedback.py`, which saves a `Feedback` row (table defined in `apps/wiki/models.py`) with the page address, section, text and author. Empty comments and off-site addresses are refused.
4. Tech Risk opens **Review queue** (`/review/`, view `queue`, template `apps/review/templates/review/queue.html`), which lists comments by status next to items waiting for approval.
5. A Tech Risk person replies and sets a status (`respond` in `apps/wiki/feedback.py`). Declining requires a reason.
6. The visitor sees the reply under **My comments** (`/review/my-comments/`).

## The risk engine and drivers

The risk engine, a separate system owned by the Tech Risk lead, is the master list of risk drivers (RD01 to RD67) and of its own risks. TRAC does not invent or number drivers: you copy the engine's `driver_mapping.yaml` and risk files into `content/engine/`, and `sync_engine` (part of `sync_content`) imports them. Each engine driver becomes a TRAC driver with the engine's id, so it has versions, approvals and history like other content (`apps/rcm/engine_files.py`). The engine's risks are shown as a read-only copy under Risks and controls → Engine risks, each linked to the drivers that feed its likelihood and impact; they have no drafts because the engine owns them. What TRAC adds is in one file, `content/drivers/drivers.json`: a title, category, owner role, leading and lagging indicators, and the TRAC risks a driver relates to. Scoring rules are shown as text and never run, and framework mappings are never shown.

## Who can do what, and how sign-in works

One table decides what each role may do: `ROLES_ALLOWED` in `apps/accounts/permissions.py`.

The README ("Roles") has the table in plain words: Tech Risk can propose, approve (never their own change, unless single-approver mode is on), manage and see history; auditors can read, comment and see history; control owners and read-only users can read and comment.

To change a rule, edit that table and run the tests. The test `apps/core/tests/test_url_access.py` lists every page against every role.

**Before SSO** (`AUTH_MODE=open`): nobody signs in. Every visitor is treated as the role in `OPEN_MODE_ROLE`, which should be `read_only` on a shared site, so they can read and comment. You sign in with a password through **Tech Risk sign-in** in the footer. Single-approver mode lets you approve your own changes for now. All of this is handled by `apps/accounts/middleware.py`.

**After SSO** (`AUTH_MODE=sso`): the company's login passes each person's username and AD groups to TRAC with every request. `SSO_GROUP_ROLE_MAP` turns groups into roles (for example `grp-techrisk:tech_risk`). People whose groups map to nothing become read only. A request with no username is treated as signed out. `TECH_RISK_USERS` keeps named people as Tech Risk even without a group. Turn single-approver mode off at this point.

## How to explain TRAC to someone else

Read these aloud:

- TRAC is Tech Risk's guidance website: guides, control patterns, risks and Library pages, all in one place.
- Everyone in the firm can read it and leave a comment on any page; only Tech Risk can write it.
- Every change is a new version that a second Tech Risk person approves, so the published text is always reviewed and nothing is overwritten.
- Every version and approval is logged, so we can show an auditor who changed what, when, and who approved it.
- Content lives in plain files as well as in the site, and one command checks and loads it, so updating many pages is quick and safe.

## If something breaks

1. **Run the tests**: `.\trac.ps1 test`. Every line should end in dots and the last line should say `passed`.
2. **Read the failing test's name.** It is written as a sentence, for example `test_a_site_edit_blocks_the_update_until_exported_or_forced`, and the path before it (such as `apps/wiki/tests/test_sync_guides.py`) tells you which part of the site is affected. Send both to whoever supports TRAC.
3. **Find the logs.** On your computer, messages appear in the window where `.\trac.ps1 run` is running. On the live site, TRAC writes its log to the hosting platform's log screen (it prints to the console).
4. **Check the content files** with `.\trac.ps1 check` if a sync misbehaves. It names the file and the line to fix.
5. **Roll back a content change.** Nothing published is ever overwritten, so nothing is lost.
   - In the site: open the page, choose **View history**, open the older version, copy its text into a new edit, then submit and approve it. Or choose **Retire**, give a reason, and have a second person approve.
   - In a content file: put the old wording back, run `.\trac.ps1 check`, then `.\trac.ps1 sync`. It becomes a new draft to approve.
6. **Never edit the database directly.** It bypasses the approvals and the audit log, and the history will no longer match what is on the site. Make every change through the site or the content files.
