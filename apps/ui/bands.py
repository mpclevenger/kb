"""Builds the coloured heading band at the top of every page."""

def make_band(crumbs, title="", summary="", icon=None, section=None, action=None, stages=None, active_stage=None):
    """The `band` every page with a band puts in its context (drawn by components/page_band.html).

    crumbs        [(label, url or None), ...]; the last one has no url
    title         page title shown in the band; leave empty when the page shows its own title
    summary       a sentence or two under the title
    icon          topic icon name, next to the title (or next to the crumbs when there is no title)
    section       wiki section key, shown as a colored pill above the title
    action        (label, url) for a button beside the title
    stages        lifecycle strip stages (dicts with name and optional url); active_stage is a stage name
    """
    return {
        "crumbs": crumbs,
        "title": title,
        "summary": summary,
        "icon": icon,
        "section": section,
        "action": action,
        "stages": stages or [],
        "active_stage": active_stage,
    }
