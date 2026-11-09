# TRAC: Tech Risk and Controls

TRAC is Tech Risk's guidance site. It holds generic, Tech Risk-owned guidance: topics with lifecycle stages, control patterns, risks, platforms and their services, and (as they are added) standards, guides and how-tos. Everyone in the firm can read it and comment on any page. Only Tech Risk writes it, and every change is approved by a second Tech Risk person before it becomes official.

Stack: Django 5.2, HTMX, Bootstrap 5, PostgreSQL. Python, HTML and CSS, with small vanilla JavaScript files. All front-end libraries and fonts are bundled in `static/vendor/`; nothing loads from the internet.

## How it is organized

`docs/HOW_TRAC_WORKS.md` explains the parts of TRAC, the folder map and how a page, an approval, a content sync and a comment travel through the code, in plain English. Start there.

## Roles

| Role | Read | Comment | Propose changes | Approve | Manage catalog | See history |
|---|---|---|---|---|---|---|
| Tech Risk | Yes | Yes | Yes | Yes (not their own) | Yes | Yes |
| Auditor | Yes | Yes | No | No | No | Yes |
| Control owner | Yes | Yes | No | No | No | No |
| Read only | Yes | Yes | No | No | No | No |

Drafts and items in review are visible only to Tech Risk and the person who proposed them. Published versions never change; every change creates a new version, and every status change is written to an append-only audit log.

## Getting started (Windows PowerShell)

`trac.ps1` runs the everyday jobs. If Windows says scripts are blocked, run `powershell -ExecutionPolicy Bypass -File .\trac.ps1 <verb>` instead.

```powershell
$env:DATABASE_URL = "postgres://user:pass@localhost:5432/trac"
.\trac.ps1 setup      # first time only: Python environment, install, database tables
.\trac.ps1 run        # start the site, then open http://127.0.0.1:8000/
```

Open the site once in your browser (local settings make every visitor a Tech Risk user called `open-visitor`), then load the starting content in a second PowerShell window (activate the environment with `.venv\Scripts\Activate.ps1`):

```powershell
python manage.py setup_trac --user open-visitor
```

`.\trac.ps1 help` lists every verb: `setup`, `run`, `test`, `check`, `sync`, `export`, `demo`. Content files and what `check`, `sync` and `export` do are explained in `MAINTAINING.md` and `content/README.md`.

`AUTH_MODE` defaults to `open`: every visitor is signed in automatically with the role in `OPEN_MODE_ROLE` (default `read_only`), and the owner signs in with a password from the footer link "Tech Risk sign-in". See MAINTAINING.md, "Before SSO is set up".

### A demo copy

To show TRAC to colleagues, point `DATABASE_URL` at a separate database with `demo` in its name, then run `.\trac.ps1 demo`. It adds two demo Tech Risk users and sample content, all published, and refuses to run on any other database. It is safe to run again and refuses in `sso` mode.

```powershell
$env:DATABASE_URL = "postgres://user:pass@localhost:5432/trac_demo"
.\trac.ps1 setup
.\trac.ps1 demo
.\trac.ps1 run
```

## Deploy

The platform installs `requirements.txt` and runs the `Procfile` (`web: sh docker/start.sh`). The start-up script prepares the styling files if needed, updates the database, syncs the content files and starts gunicorn on port 8000. Setup and Kubernetes notes are in `MAINTAINING.md` (\"Running TRAC on the platform\"). `Dockerfile` is a reference image for local testing. Set these environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY` | Required in production |
| `DATABASE_URL` | Postgres connection string |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | The site's host name |
| `AUTH_MODE` | `open` (visitors read and comment; the owner signs in with a password) or `sso` |
| `OPEN_MODE_ROLE` | In `open` mode, the role every visitor has: `read_only` (default), `control_owner`, `auditor` or `tech_risk`. Visitors cannot pick another. Warning `trac.W002` shows in `manage.py check` unless it is `read_only` |
| `TECH_RISK_USERS` | In `sso` mode, comma-separated usernames (as sent in the SSO user header, any capitals) that always get Tech Risk, on top of `SSO_GROUP_ROLE_MAP` |
| `ALLOW_SELF_APPROVAL` | `true` lets a proposer approve their own change (single-approver mode). Default `false`. Warning `trac.W001` shows in `manage.py check` while it is on |
| `SSO_*_HEADER` | Header names the SSO add-on sets (user, name, email, groups) |
| `SSO_GROUP_ROLE_MAP` | `group:role` pairs, for example `grp-techrisk:tech_risk,grp-audit:auditor` |
| `TRUST_URL`, `RISK_URL`, `INITIATIVES_URL` | Optional links in the app switcher |
| `TRAC_ADMIN_USER`, `TRAC_ADMIN_PASSWORD` | Container only: the admin account the start-up sync runs as; the password is needed only on the first start, to create it |

In `sso` mode, users whose groups map to no role get read-only access. A request without the user header is treated as signed out.

## Maintaining

`MAINTAINING.md` is the plain-language guide for updating content, roles (AD groups), wording, colors and shared components.

