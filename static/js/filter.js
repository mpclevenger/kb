/*
 * Filter-as-you-type for the technology cards on Home.
 *   [data-filter-input]  the search box
 *   [data-filter-group]  a group of cards    [data-filter-card]  a card (its name is the first link)
 *   [data-filter-item]   one technology chip [data-filter-empty] shown when nothing matches
 * A card whose name matches shows all its technologies; otherwise only matching ones.
 */
(function () {
  "use strict";
  var input = document.querySelector("[data-filter-input]");
  if (!input) return;

  function filter() {
    var query = input.value.trim().toLowerCase();
    var anyShown = false;
    document.querySelectorAll("[data-filter-group]").forEach(function (group) {
      var groupShown = false;
      group.querySelectorAll("[data-filter-card]").forEach(function (card) {
        var nameMatches = card.querySelector("a").textContent.toLowerCase().indexOf(query) !== -1;
        var shown = nameMatches;
        card.querySelectorAll("[data-filter-item]").forEach(function (item) {
          var match = nameMatches || item.textContent.toLowerCase().indexOf(query) !== -1;
          item.hidden = !match;
          shown = shown || match;
        });
        card.hidden = !shown;
        groupShown = groupShown || shown;
      });
      group.hidden = !groupShown;
      anyShown = anyShown || groupShown;
    });
    document.querySelector("[data-filter-empty]").hidden = anyShown;
  }

  input.addEventListener("input", filter);
})();
