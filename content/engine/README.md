# Risk engine files

These files are copies of files from the risk engine. The risk engine is the master list of risk drivers
(RD01, RD02 and so on) and of its own risks. TRAC reads the copies and shows them. Do not edit them here:
change the engine, then copy the files over.

| File | What it holds |
|---|---|
| `driver_mapping.yaml` | Every risk driver: its id, the engine's rule (trigger), the questionnaire fields and the rationale. |
| `risks/*.yaml` | The engine's risks, one file per risk category. Each says which drivers feed its likelihood and its impact, and how it is scored. |

The files that ship with TRAC are samples (the first line says so). Replace them with the real ones.

## How to refresh them

1. In the engine repository, copy `driver_mapping.yaml` over `content/engine/driver_mapping.yaml`.
2. Copy every file in the engine's `config/risks/` over the files in `content/engine/risks/`. Delete any file there that the engine no longer has.
3. Check: `.\trac.ps1 check` (or `python manage.py check_engine`). It names the file and the risk for any mistake, such as a driver id that is not in `driver_mapping.yaml`.
4. Load: `.\trac.ps1 sync -Publish` (or `python manage.py sync_engine --user your-username --publish`).

The sync does two things. The drivers become TRAC drivers (RD01 and so on) with versions, approvals and history, like other content. The engine's risks are replaced by the new copy in one step: they are not drafted or approved because the engine owns them.

## TRAC's own details for each driver

The engine does not know TRAC's wording, so each driver also has an entry in `content/drivers/drivers.json`. See `content/README.md`. The sync adds an empty entry for any new driver; it never deletes one.

Scoring rules are shown as text exactly as the engine wrote them. TRAC never runs them, and it does not show framework mappings.
