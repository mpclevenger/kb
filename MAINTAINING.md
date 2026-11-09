# Maintaining TRAC

This guide is for whoever looks after TRAC day to day. It is written for someone comfortable with the site and a little bit of code, not a full-time developer. New to how the pieces fit? Read [docs/HOW_TRAC_WORKS.md](docs/HOW_TRAC_WORKS.md) first.

Most upkeep happens **in the site itself**, with no code. Part 1 covers that. Part 2 covers the few things that need a small file change, and Part 3 says how to check nothing broke.

---

## Part 1: Updating content in the site (no code)

Everything below needs the **Tech Risk** role. Every change is a proposal: you save a draft, submit it, and a *second* Tech Risk person approves and publishes it. You can't approve your own change, unless single-approver mode is on (see "Before SSO is set up"). Nobody outside Tech Risk sees a draft until it's published.

| I want to… | Where |
|---|---|
| Add or edit a guide or best practice | Best practices and guides → **New page**, or **Edit** on the page |
| Add or edit an FAQ | Best practices and guides → FAQ → **New question** |
| Add or edit a control or risk | Risks and controls → **New control / New risk**, or open the item → **Edit** |
| Change a risk driver, or see the engine's risks | Drivers and engine risks come from the risk engine's files, not the site. See "Refresh from the risk engine" in Part 2 |
| Add or edit an evidence rule | Risks and controls → **Evidence rules** |
| Write the guidance for a category or platform | Open the category or platform page → **Edit guidance** |
| Add a platform, or put it in another category | Manage → Platforms |
| Add a topic, or change its stages and themes | Manage → Topics |
| Change the "risk area" questions used on platform pages | Manage → Aspect questions |
| See the key controls for SOX in-scope apps | Open `/rcm/sox/` (linked from the Library). It lists every published key control; set a control's **Level** to the first level in `content/controls/levels.yaml` (Key) and it appears there |
| Change the control levels (add one, rename one, choose which are shown by default) | Edit `content/controls/levels.yaml`: to add a level, add an entry; to show a level by default, set `open: true`. Then run the check |
| Retire a guide, FAQ, control, risk or driver | Open it → **Retire**, give a reason. A second Tech Risk member approves it in the usual way |
| Retire an evidence rule | Risks and controls → Evidence rules → **Retire** on its row |
| Hide a topic or platform without deleting it | Manage → switch it to inactive |
| Answer a comment someone left | Review queue |
| See who changed what | **View history** on any page, or Manage → Recent changes |

Tips:
- Pasting from Word is fine. The editor tidies the formatting, and the site removes anything unsafe when the page is shown.
- A page can hold up to 200,000 characters. If you hit that, split it into two pages.
- Each main heading (Heading 2 in the editor) becomes a collapsible card. Pages with five or more of them open with every card closed, so readers see a list first.
- Published versions are never overwritten. Every edit creates a new version, so you can always see what it said before.

---

## Part 2: Small changes that need a file edit

### Who gets which role (AD groups)

Roles come from AD groups. The mapping is one setting on the hosting platform, `SSO_GROUP_ROLE_MAP`. Nothing in the code needs to change.

Format: `group:role` pairs separated by commas.

```
SSO_GROUP_ROLE_MAP=grp-techrisk:tech_risk,grp-internal-audit:auditor,grp-control-owners:control_owner
```

The four role names, spelled exactly like this: `tech_risk`, `auditor`, `control_owner`, `read_only`. What each may do is in the README ("Roles").

Good to know:
- Anyone signed in whose groups aren't in the map gets **read only**.
- A misspelled role name is ignored without any error, so check the spelling.
- One group can appear more than once to give it two roles.
- `AUTH_MODE=sso` turns on group-based sign-in. `AUTH_MODE=open` is the interim setup described in "Before SSO is set up" below. Site security and the sign-in setup are owned by the team member responsible for it; check with them before changing either setting.
- `TECH_RISK_USERS` (sso mode) lists usernames that always get Tech Risk, for example `TECH_RISK_USERS=jdoe,asmith`. Use the username exactly as the SSO user header sends it; capitals don't matter. Those people get Tech Risk even if no AD group maps to it.

### Change what a role is allowed to do

All rules live in one table at the top of `apps/accounts/permissions.py` (`ROLES_ALLOWED`). The workflow rules (who can submit, approve, reject or withdraw a draft) live in `apps/core/workflow_rules.py`. Change the table and run the tests (Part 3). The test `apps/core/tests/test_url_access.py` lists which pages each role should reach. If you change a rule on purpose, update that list too.

### Links to the other apps (TRUST, Risk, Initiatives)

Set `TRUST_URL`, `RISK_URL` and `INITIATIVES_URL` on the hosting platform. An empty value hides the link.

### Initiative lifecycle guide and the tracker

The initiative tracker links to each stage of the **Initiative lifecycle** guide, for example `/guides/initiative-lifecycle/#stage-2-build-and-configure`. The part after `#` comes from the stage heading. If you rename a stage heading, that stage's link changes. Update the link in the tracker too (Lifecycle and guidance → Edit → TRAC link). Editing anything else on the page is safe. In the starter content this guide is `content/guides/initiative-lifecycle.md`: keep the `## Stage N: ...` and `#### Item N: ...` headings and numbers as they are.

Each checklist item has its own link too: `#stage-<stage>-item-<n>`, for example `/guides/initiative-lifecycle/#stage-3-item-2`. It comes from a **Heading 4** that starts with "Item 2" inside the "Stage 3" section. Keep the item numbers in the same order as the tracker's checklist. If you add an item, add it at the end of that stage's list so the other numbers don't shift. (In `initiative-lifecycle.md`, the `#### Item N` lines are the source the tests use to check every item link.) The **Oversight levels** guide uses the same level names as the tracker (Enhanced, Standard, Light); keep them the same in both apps.

### Diagrams in guides

A diagram is a ```` ```mermaid ```` block of plain text in a guide file (format and rules: "Diagrams" in `content/README.md`). The site draws it with the Mermaid library in `static/vendor/mermaid/` (loaded only on pages that have a diagram). To update Mermaid, replace `mermaid.min.js` and its `LICENSE` with the files from the new release and run the tests, which include a browser check.

### Content files (guides, controls and risks)

Guides are Markdown files in `content/guides/`; controls and risks are YAML files in `content/controls/`; the platform list and the guidance for each category and platform are YAML files in `content/platforms/`. Formats and the full rules for how a sync behaves are in `content/README.md` and `content/controls/README.md`. The loop:

1. Edit a file.
2. `.\trac.ps1 check` (runs `check_content`: plain-word messages, changes nothing).
3. `.\trac.ps1 sync -DryRun`, then `.\trac.ps1 sync` (runs `sync_content --user <you>`). New items become drafts and changed items become proposed updates. Add `-Publish` to approve straight away; that works only in single-approver mode (`ALLOW_SELF_APPROVAL`).
4. If someone edited in the site, run `.\trac.ps1 export` (`export_content`) first so their edit comes into the files. Otherwise the sync skips that item and says so; `--force` replaces the site's version.

Also available one part at a time: `check_engine`, `sync_engine`, `check_guides`, `check_controls`, `check_platforms`, `sync_guides`, `sync_controls`, `sync_platforms`, `export_guides`, `export_controls`, `export_platforms`. If `$env:TRAC_USER` is not set, `sync` asks for your username.

The topics are in `apps/topics/management/commands/seed_topics.py`. The platforms and risk-area questions are in `content/platforms/catalog.yaml` (read by `seed_platforms`). Both only add what a site does not have yet, so once the site is live edit topics, platforms and questions in the site (Part 1).

### Refresh from the risk engine

The risk engine is the master list of risk drivers (RD01, RD02 ...) and of its own risks. TRAC keeps copies of the engine's files in `content/engine/` and shows them; it never changes them. Only the sample files ship with TRAC, so the first job is to replace them with the real ones.

1. Copy the engine's `driver_mapping.yaml` over `content/engine/driver_mapping.yaml`.
2. Copy the engine's `config/risks/*.yaml` over the files in `content/engine/risks/`. Delete any file there that the engine no longer has.
3. `.\trac.ps1 check`. It names the file and the risk for any mistake (for example a driver id that is not in the mapping).
4. `.\trac.ps1 sync -Publish`. New drivers become drafts (or publish at once with `-Publish` in single-approver mode), changed ones become proposed updates, and the engine's risks are replaced by the new copy.

Drivers cannot be added or edited in the site. TRAC's own details for a driver (title, category, owner role, leading and lagging indicators, and the TRAC risks it relates to) are written in one file, `content/drivers/drivers.json`. Edit it with any text editor, run check, then sync. The sync adds an empty entry for every new engine driver and never deletes one. An empty title shows as the id (RD01); an empty owner role shows as "Not assigned yet". The pages are Risks and controls → **Engine risks** and each driver's page. Details are in `content/README.md` and `content/engine/README.md`.

### Wording and labels

| I want to change… | Edit |
|---|---|
| Guide section names (Build your controls, Run your controls…) | `Section` in `apps/wiki/models.py` (change only the text in quotes, not the short key) |
| The one-line description under each section card | `SECTION_HINTS` in `apps/wiki/views_read.py` |
| Top menu items | `PRIMARY_NAV` in `apps/ui/templatetags/trac_ui.py` |
| The starting list of platforms and risk-area questions (new sites) | `content/platforms/catalog.yaml` (commented; run `.\trac.ps1 check` after) |
| Guidance for a category or platform, in bulk | `content/platforms/categories/<category>.yaml` and `content/platforms/<platform>.yaml` (format in `content/README.md`; bullets are lines starting with `- `) |
| Category names (Database, Identity…) | `Category` in `apps/platforms/categories.py` (text in quotes only) |

### How things look

Each kind of label, card or header is drawn in **one** template in `templates/components/`. Change that one file and every page follows. For example:

| Piece | Template |
|---|---|
| Platform pill (e.g. "GitHub Enterprise Server") | `platform_chip.html` |
| Status and coverage badges | `badge.html` |
| Section and type pills | `type_pill.html` |
| Category pill | `category_pill.html` |
| Page header band and breadcrumbs | `page_band.html`, `breadcrumbs.html` |
| Colored note boxes | `callout.html` |

Colors live in the CSS files in `static/css/`. Each file starts with a comment saying what belongs in it:
- `trac.css`: the main colors (top of the file, under `:root`), category colors (`.category-…`), and the shared pieces above
- `library.css`: guide section colors (`.library-section-…`)
- `topics.css`: topic pages and lifecycle colors
- `guidance.css`: Library, category and platform pages

After changing a color, run the tests. One test checks that every text color is readable on its background and names the one that isn't.

To see every shared piece on one page, open `/ui/gallery/`. A test fails if a new shared piece is added without a sample there.

### Code layout

The folder map is in [docs/HOW_TRAC_WORKS.md](docs/HOW_TRAC_WORKS.md).

Shared template tags are in two files: `apps/ui/templatetags/trac_ui.py` (layout pieces) and `apps/ui/templatetags/trac_labels.py` (pills, badges, chips). Each file lists its contents at the top.

---

## Part 3: Checking nothing broke

From the project folder in PowerShell:

```powershell
.\trac.ps1 test
```

Every line should end in dots and the last line should say `passed`. If something fails, the output names the test and the file. The tests also check that:
- each role can reach only what it should
- colors stay readable (contrast)
- pages don't get slower as content grows

`.\trac.ps1 demo` fills a demo database with published demo content (see the README). Run the site locally with `.\trac.ps1 run`. The component gallery at `/ui/gallery/` shows every shared piece of the page (pills, badges, cards) in one place, which is a quick way to check a styling change. If something fails and you are not sure why, see "If something breaks" in docs/HOW_TRAC_WORKS.md.

## Going live (first time only)

Work through these in order. Steps 1 to 3 are for whoever deploys and secures the site. For a quick start with one admin, use "Going live tomorrow (one admin)" below instead.

1. **Settings on the hosting platform:** `DJANGO_SETTINGS_MODULE=config.settings.prod`, a long random `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (the site's address), `SSO_GROUP_ROLE_MAP` with the real AD groups, and the `TRUST_URL`, `RISK_URL` and `INITIATIVES_URL` links. See the README for the full list.
2. **Deploy.** Database changes run on their own at each release. Check that the platform also runs `python manage.py collectstatic --noinput` while building; without it the site has no styling.
3. **Sign-in.** Before anyone outside the build team gets the link, either set `AUTH_MODE=sso`, or stay on `AUTH_MODE=open` with `OPEN_MODE_ROLE=read_only` (visitors only read and comment; see below). Never leave `OPEN_MODE_ROLE=tech_risk` on a shared site: `python manage.py check` warns with `trac.W002`. With SSO, make sure `ALLOW_SELF_APPROVAL` is `false` or not set. The security owner also decides on HTTPS redirect, HSTS and the `/admin/` page (`python manage.py check --deploy` lists them).
4. **Two Tech Risk people sign in once.** Changes need a second person to approve them (or use single-approver mode, below).
5. **Load the starting content:** `python manage.py setup_trac --user <your username>`. It adds topics, platforms, the starter guides and sample evidence rules. Guides and rules arrive as drafts.
6. **Review and approve the drafts** in Best practices and guides and Risks and controls → Evidence rules. Fill in anything marked "to be confirmed", such as where evidence is kept and for how long.
7. **Add your own content:** controls and risks; the risk engine's real files (see "Refresh from the risk engine"); drivers.json details; guidance for each category and platform; and your existing guides (paste them into New page).
8. **Give the tracker its links** to the Initiative lifecycle guide (see Part 2).
9. **Try it as each role** (Tech Risk, auditor, control owner, read only) with a test account in each AD group.

### Going live tomorrow (one admin)

Set these on the hosting platform (names exactly as written; replace the values in angle brackets):

```
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<long random text>
DATABASE_URL=<Postgres connection string>
ALLOWED_HOSTS=<site host name>
CSRF_TRUSTED_ORIGINS=https://<site host name>
AUTH_MODE=open
OPEN_MODE_ROLE=read_only
ALLOW_SELF_APPROVAL=true
```

Then, from the project folder in PowerShell (with `DATABASE_URL` and the settings above set in the same window):

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py setup_trac --user <your username>
```

1. `createsuperuser` makes your account (pick your own username and a strong password). Don't start the username with `open-`; that prefix is reserved for visitors.
2. `setup_trac --user` loads the starting content as drafts from your account.
3. Open the site, scroll to the footer and click **Tech Risk sign-in**. Sign in with the account from step 1.
4. Approve the drafts (Best practices and guides, and Risks and controls → Evidence rules). With `ALLOW_SELF_APPROVAL=true` you can approve your own changes.
5. Share the link. Everyone else reads and comments; you answer comments in the Review queue.

The site must be served over HTTPS, because your password and session cookie travel over it. The platform normally does this; check the address starts with `https://`. There is no limit on wrong password attempts yet.

## Running TRAC on the platform (Kubernetes)

The platform team supplies the image; we run our code on it. What the platform needs from us is in the project folder:

- `requirements.txt`: the Python packages to install (Python 3.12, see `.python-version`).
- `Procfile`: `web: sh docker/start.sh`, the one command that starts TRAC.

The database is a separate Postgres server, not inside the pod. The guides, controls and platform guidance come from the `content/` folder that is deployed with the code.

(`Dockerfile` is a reference image for testing on your own machine, or if the platform ever asks us for one. It isn't needed when the platform supplies the image.)

### Updating content

1. Edit the files in `content/` (see "Content files" in Part 2). Optional but quicker: run `.\trac.ps1 check` on your machine first.
2. Deploy the new version of the code the usual way for the platform.
3. When the pod starts, it checks the files and publishes the changes on its own. The pod log shows each step, for example "Writing a runbook: published an update".

Edit content **only in the files**, not in the site's editor. The files are the source of truth, and an edit made in the site would not flow back into them. (`export` writes inside the pod and is lost when it is replaced.)

If the check finds a mistake, the pod still starts with the previous content and the log says what to fix (lines starting with `!!`).

### What the pod does each time it starts

`docker/start.sh`, in order: prepares the styling files if the image doesn't have them yet; updates the database; creates the admin account the first time; adds any new topics and platforms; checks the content files; if they pass, syncs them into the site (published straight away when `ALLOW_SELF_APPROVAL=true`, otherwise as proposed updates to approve); then starts the web server on port 8000. Sample evidence rules arrive as drafts to fill in and approve.

### Settings

Set these on the pod; put `SECRET_KEY`, `DATABASE_URL` and `TRAC_ADMIN_PASSWORD` in a Kubernetes Secret.

| Setting | Value |
|---|---|
| `SECRET_KEY` | Long random text |
| `DATABASE_URL` | Postgres connection string |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | The site's host name (`https://<host>` for the second) |
| `AUTH_MODE`, `OPEN_MODE_ROLE` | `open` and `read_only` until SSO is set up |
| `ALLOW_SELF_APPROVAL` | `true` while you are the only admin, so changes publish on start-up |
| `TRAC_ADMIN_USER` | Your admin username. The start-up sync runs as this account |
| `TRAC_ADMIN_PASSWORD` | Needed only for the first start, to create the account. You can remove it afterwards |
| `WEB_WORKERS` | Optional, default 3 |

### Kubernetes notes for whoever runs the cluster

- Run **one replica**. Start-up updates the database and syncs content, so two pods starting together could clash.
- Health check: `GET /health/` returns 200. Give the first start a few minutes before the probe gives up (start-up probe), because the first sync loads everything.
- The site expects HTTPS in front of it (the ingress) and reads `X-Forwarded-Proto`.
- TRAC listens on port 8000 (or `PORT` if the platform sets it).

A minimal example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trac
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels: {app: trac}
  template:
    metadata:
      labels: {app: trac}
    spec:
      containers:
        - name: trac
          image: <the platform's image with TRAC deployed>
          ports: [{containerPort: 8000}]
          envFrom:
            - secretRef: {name: trac-secrets}      # SECRET_KEY, DATABASE_URL, TRAC_ADMIN_PASSWORD
            - configMapRef: {name: trac-settings}  # everything else in the table above
          startupProbe:
            httpGet: {path: /health/, port: 8000}
            periodSeconds: 10
            failureThreshold: 30
          readinessProbe:
            httpGet: {path: /health/, port: 8000}
```

## Before SSO is set up

Until real sign-in is ready, TRAC runs in `open` mode with one admin (you) and everyone else read only.

- **Visitors** (`AUTH_MODE=open`, `OPEN_MODE_ROLE=read_only`): nobody signs in. Everyone who opens the link can read every guide and page and leave comments. They can't edit anything and can't pick a role. The top bar shows **Read only** and **Add your name**; adding a name is optional and only puts it next to their comments (`/accounts/login/`).
- **You (the admin):** create your account once with `python manage.py createsuperuser`. A superuser always has the Tech Risk role. Then click **Tech Risk sign-in** in the footer (`/accounts/staff/`) and sign in with your username and password. **Sign out** in the top bar returns the browser to a normal visitor. Only Tech Risk accounts can sign in on that page. To add a second admin, run `createsuperuser` again.
- **`OPEN_MODE_ROLE`**: the role every visitor has (default `read_only`). Leave it as `read_only` on a shared site. While it is anything else, `python manage.py check` prints warning `trac.W002`. For local work only, `config.settings.dev` sets it to `tech_risk` so you can edit without signing in.
- **`ALLOW_SELF_APPROVAL=true`**: single-approver mode. One Tech Risk person can approve or reject their own proposal. The rule is in one place, `apps/core/workflow_rules.py`. While it is on, `python manage.py check` prints warning `trac.W001`. Turn it off once a second Tech Risk approver has access.
- **Over HTTPS only:** serve the site over HTTPS, because the password page sends your password to the site.

When SSO is ready, set `AUTH_MODE=sso`. The footer link and the password page go away. Everyone whose groups map to no role is read only. List yourself in `TECH_RISK_USERS` (your username as the SSO header sends it) to keep Tech Risk even without an AD group, and map the real groups in `SSO_GROUP_ROLE_MAP`.
