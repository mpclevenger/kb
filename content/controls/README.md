# Content files: controls and risks

These YAML files hold the controls and risks for TRAC, one file per topic (for example `change-management.yaml`). Each is plain text you can open in any editor. They are the place to update controls and risks in bulk; the site is where people read them and where drafts are approved.

## The loop

Edit the file, then check and sync with `.\trac.ps1 check` and `.\trac.ps1 sync` (add `-DryRun` to preview, `-Publish` in single-approver mode). How a sync decides what to do (new, unchanged, in progress, edited in the site, update), and what `--force` and the export do, is explained once in `content/README.md`.

Controls and risks are matched by title. A changed entry becomes a proposed change ("Updated from content/controls/..."), and a control's risks, platforms and links follow the file. The export keeps the comment block at the top of the file but not comments written inside it.

**Renaming a title creates a new control or risk.** The old one stays on the site; retire it in the site.

## What is in a file

The comment block at the top of each file explains every field in one line. In short:

- `topic`: the topic name, exactly as on the site.
- `risks`: each has a title, a plain statement, an owner role, a stage (or a theme) and `covered_by`, the controls that reduce it, with `coverage` (full or partial) and a one-line `why`.
- `controls`: each has a short `ref` (used only inside the file so risks can point at it), a title, why it exists, when it applies, nature, method, frequency, its level (key, non-key, compensating or supporting; most important first, see levels.yaml), owner, performer and reviewer roles, stage or theme, categories, optional platforms, criteria (what good looks like), steps and optional references.

You never type a control ID. The site assigns it (for example MC-01) when the control is created.

The four levels:
- `key`: relied on to address the risk, tested by auditors.
- `non-key`: matters, but is not relied on alone.
- `compensating`: covers for a control that is missing or not working, usually for a limited time.
- `supporting`: helps other controls work (documentation, baselines, tuning).

### Changing the levels (`levels.yaml`)

The levels live in one small file, `content/controls/levels.yaml`, listed most important first. Each entry has a `key` (what controls point at), a `label` (what readers see) and `open`:

- **To add a level**, add another entry in the place you want it to rank. Pages sort controls in this order.
- **To show a level by default**, set `open: true`. Levels with `open: false` are folded under a "More controls" box on library, platform and topic pages.
- **To rename a level** for readers, change its `label`. Leave `key` alone.
- The first level is also the one listed on the "Key controls for SOX in-scope apps" page.
- The old `key_control` and `scope` fields are gone. A file that still has them fails the check and says to use `level`.

`.\trac.ps1 check` also checks `levels.yaml` and names the problem (a repeated key, a missing label, or a missing `open`).

Two YAML habits to know:
- `yes` and `no` mean true and false. Write `sox_only: true`.
- Indentation matters. Use spaces, never tabs, and keep list dashes lined up.

## Add a control

1. Open the topic's file. Copy an existing entry under `controls:` and paste it at the end.
2. Give it a new, unique `ref` and change the fields.
3. To cover a risk with it, add a line under that risk's `covered_by:` with the `ref`, a coverage and a reason.
4. Run the check below.

## Check your changes before syncing

`.\trac.ps1 check` (`check_content`; `check_controls` for these files alone) reads every file and changes nothing. It prints a plain-word message naming the file and the field for each problem (for example an unknown category, an unknown stage or a mistyped value) and stops with an error. A platform the site doesn't have is a warning, and that platform is skipped. Topics and platforms must already exist, so run `seed_topics` and `seed_platforms` first (`setup_trac` does).
