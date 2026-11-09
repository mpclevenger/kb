/*
 * Small behaviors shared by every page. Each block is switched on by a data attribute in the HTML:
 *   [data-section-toolbar]  Expand/Collapse all buttons for section cards (shown when there are 3 or more cards)
 *   [data-confirm]          a form that asks "OK?" before it submits
 *   (no attribute)          links to a heading inside a closed section card (#id) open that card first
 *   [data-comment-box]      the comment box: fills the section list from the page's h2 headings and the page name
 *   pre.mermaid             diagrams: Mermaid (body[data-mermaid-src]) is loaded only on pages that have one
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
})();
