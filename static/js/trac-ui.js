/*
 * Small behaviors shared by every page. Each block is switched on by a data attribute in the HTML:
 *   [data-section-toolbar]  Expand/Collapse all buttons for section cards (shown when there are 3 or more cards)
 *   [data-confirm]          a form that asks "OK?" before it submits
 *   (no attribute)          links to a heading inside a closed section card (#id) open that card first
 *   [data-comment-box]      the comment box: fills the section list from the page's h2 headings and the page name
 *   [data-platform-toggle]  category pages: a platform pill shows or hides that platform's specifics
 *                           ([data-platform-content]) and keeps the choice in the page address
 *   pre.mermaid             diagrams: Mermaid (body[data-mermaid-src]) is loaded only on pages that have one;
 *                           a box whose label starts with a section heading shows that section beside the diagram
 *   (no attribute)          printing: opens every section card while printing, then restores them
 */
(function () {
  function cards() {
    return Array.prototype.slice.call(document.querySelectorAll("details.section-card"));
  }

  // [data-section-toolbar] with buttons [data-sections="expand|collapse"]
  function setAll(open) {
    cards().forEach(function (d) { d.open = open; });
  }

  document.querySelectorAll("[data-section-toolbar]").forEach(function (bar) {
    if (cards().length < 3) return;
    bar.hidden = false;
    bar.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-sections]");
      if (button) setAll(button.getAttribute("data-sections") === "expand");
    });
  });

  // Links such as /guides/initiative-lifecycle/#stage-2-build-and-configure: open the card holding the target
  function openTarget() {
    var id = decodeURIComponent(window.location.hash.slice(1));
    var target = id && document.getElementById(id);
    var card = target && target.closest("details.section-card");
    if (card && !card.open) {
      card.open = true;
      target.scrollIntoView();
    }
  }
  openTarget();
  window.addEventListener("hashchange", openTarget);
  document.addEventListener("click", function (event) {
    var link = event.target.closest('a[href^="#"]');
    if (link) setTimeout(openTarget, 0); // same-hash clicks don't fire hashchange
  });

  // [data-confirm="message"] on a <form>
  document.addEventListener("submit", function (event) {
    var message = event.target.getAttribute("data-confirm");
    if (message && !confirm(message)) event.preventDefault();
  });

  // [data-comment-box]: the select gets one option per h2 on the page; the hidden "label" input gets the page name
  var box = document.querySelector("[data-comment-box]");
  if (box) {
    var select = box.querySelector("select");
    document.querySelectorAll("main h2").forEach(function (heading) {
      if (box.contains(heading)) return;
      var option = new Option(heading.textContent.trim());
      select.insertBefore(option, select.lastElementChild);
    });
    var h1 = document.querySelector("h1");
    box.querySelector("input[name=label]").value = h1 ? h1.textContent.trim() : document.title;
  }

  // Diagram boxes whose label starts with a section card's heading (e.g. "Stage 2: Build and configure — ...")
  // become buttons: choosing one shows that section beside the diagram (below it on narrow screens), without
  // leaving the spot. Nothing to write in the diagram: the label is enough. The cards below stay as they are.
  function linkDiagramBoxes() {
    var headings = cards().map(function (d) { return d.querySelector("summary [id]"); }).filter(Boolean);
    document.querySelectorAll("pre.mermaid").forEach(function (diagram) {
      var links = [];
      diagram.querySelectorAll("g.node").forEach(function (node) {
        var label = node.textContent.replace(/\s+/g, " ").trim();
        var heading = headings.filter(function (h) {
          var title = h.textContent.replace(/\s+/g, " ").trim();
          return title && label.indexOf(title) === 0;
        })[0];
        if (heading) links.push({ node: node, heading: heading });
      });
      if (!links.length) return;

      var explorer = document.createElement("div");
      explorer.className = "diagram-explorer";
      diagram.parentNode.insertBefore(explorer, diagram);
      explorer.appendChild(diagram);
      var panel = document.createElement("div");
      panel.className = "diagram-panel";
      panel.setAttribute("aria-live", "polite");
      panel.innerHTML = '<p class="diagram-panel-hint">Select a box in the diagram to see its details here.</p>';
      explorer.appendChild(panel);

      function show(link) {
        links.forEach(function (l) { l.node.classList.toggle("is-active", l === link); l.node.setAttribute("aria-pressed", l === link); });
        var title = document.createElement("h3");
        title.className = "diagram-panel-title";
        title.textContent = link.heading.textContent.trim();
        var body = link.heading.closest("details.section-card").querySelector(".section-card-body").cloneNode(true);
        body.className = "diagram-panel-body library-body";
        body.querySelectorAll("[id]").forEach(function (el) { el.removeAttribute("id"); });
        panel.replaceChildren(title, body);
        if (explorer.offsetWidth < 900) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }

      links.forEach(function (link) {
        var node = link.node;
        node.classList.add("diagram-link");
        node.setAttribute("role", "button");
        node.setAttribute("tabindex", "0");
        node.setAttribute("aria-pressed", "false");
        node.setAttribute("aria-label", "Show " + link.heading.textContent.trim());
        node.addEventListener("click", function () { show(link); });
        node.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(link); }
        });
      });
    });
  }

  // pre.mermaid: load Mermaid only when the page has a diagram, then draw every diagram with TRAC's colors.
  // Closed section cards are opened while drawing (a hidden diagram has no size) and closed again.
  var diagrams = document.querySelectorAll("pre.mermaid");
  if (diagrams.length && document.body.dataset.mermaidSrc) {
    var script = document.createElement("script");
    script.src = document.body.dataset.mermaidSrc;
    script.onload = function () {
      var css = getComputedStyle(document.documentElement);
      function token(name) { return css.getPropertyValue(name).trim(); }
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        fontFamily: getComputedStyle(document.body).fontFamily,
        flowchart: { htmlLabels: true, padding: 12, nodeSpacing: 30, rankSpacing: 36 },
        themeVariables: {
          fontSize: "16px",
          background: token("--trac-paper"),
          primaryColor: token("--trac-mist-soft"),
          primaryBorderColor: token("--trac-blue"),
          primaryTextColor: token("--trac-ink"),
          secondaryColor: token("--trac-mist"),
          secondaryBorderColor: token("--trac-blue"),
          secondaryTextColor: token("--trac-ink"),
          tertiaryColor: token("--trac-pill-bg"),
          tertiaryBorderColor: token("--trac-border"),
          tertiaryTextColor: token("--trac-ink"),
          lineColor: token("--trac-slate"),
          textColor: token("--trac-ink"),
          noteBkgColor: token("--trac-warning-tint"),
          noteBorderColor: token("--trac-warning-edge"),
          noteTextColor: token("--trac-ink"),
          edgeLabelBackground: token("--trac-paper"),
          clusterBkg: token("--trac-pill-bg"),
          clusterBorder: token("--trac-border")
        }
      });
      var closed = cards().filter(function (d) { return !d.open && d.querySelector("pre.mermaid"); });
      closed.forEach(function (d) { d.open = true; });
      window.mermaid.run({ querySelector: "pre.mermaid" }).finally(function () {
        closed.forEach(function (d) { d.open = false; });
        linkDiagramBoxes();
        document.documentElement.setAttribute("data-diagrams", "ready");
      });
    };
    document.head.appendChild(script);
  }

  // Print: collapsed section cards are opened for the printout and closed again afterwards
  var restore = [];
  window.addEventListener("beforeprint", function () {
    restore = cards().filter(function (d) { return !d.open; });
    restore.forEach(function (d) { d.open = true; });
  });
  window.addEventListener("afterprint", function () {
    restore.forEach(function (d) { d.open = false; });
    restore = [];
  });
  // [data-platform-toggle="<slug>"]: switch a platform's specifics on or off without reloading.
  // The link still works without scripts: its address has the platform switched the other way.
  document.addEventListener("click", function (event) {
    var pill = event.target.closest("[data-platform-toggle]");
    if (!pill) return;
    event.preventDefault();
    var slug = pill.getAttribute("data-platform-toggle");
    var on = pill.getAttribute("aria-pressed") !== "true";
    pill.setAttribute("aria-pressed", on ? "true" : "false");
    document.querySelectorAll('[data-platform-content="' + slug + '"]').forEach(function (el) { el.hidden = !on; });
    var params = new URLSearchParams(window.location.search);
    var chosen = params.getAll("platform").filter(function (s) { return s !== slug; });
    if (on) chosen.push(slug);
    params.delete("platform");
    chosen.forEach(function (s) { params.append("platform", s); });
    var query = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : "") + window.location.hash);
  });

})();
