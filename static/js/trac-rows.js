/*
 * Repeatable rows for forms. Markup contract:
 *
 *   [data-rows-editor]           wraps one editor and its hidden JSON input ([data-rows-output])
 *   [data-rows-wrap]             holds one list, its <template> row, and an add button
 *   [data-list]                  the list; data-shape="strings" | "objects", data-noun="step",
 *                                data-name="items" when nested inside an object row
 *                                A "strings" row may hold a checkbox [data-field="sox_only"]; when it is
 *                                ticked the row serializes as {"text", "sox_only": true}.
 *   [data-row]                   a row; [data-field="x"] inputs hold its values; [data-tools]
 *                                receives the up, down and remove buttons
 *   [data-action="add"]          adds a row from the wrap's <template>
 *
 * On submit each editor writes its rows as JSON into its hidden input.
 */
(function () {
  "use strict";

  function ownRow(el) {
    return el.closest("[data-row]");
  }

  function rowsOf(list) {
    return Array.prototype.filter.call(list.children, function (el) {
      return el.hasAttribute("data-row");
    });
  }

  function serialize(list) {
    var shape = list.getAttribute("data-shape");
    return rowsOf(list).map(function (row) {
      if (shape === "strings") {
        var input = row.querySelector("[data-field='value']");
        var text = input ? input.value.trim() : "";
        var flag = row.querySelector("[data-field='sox_only']");
        return flag && flag.checked ? { text: text, sox_only: true } : text;
      }
      var out = {};
      row.querySelectorAll("[data-field]").forEach(function (el) {
        if (ownRow(el) === row) out[el.getAttribute("data-field")] = el.value.trim();
      });
      row.querySelectorAll("[data-list][data-name]").forEach(function (nested) {
        if (ownRow(nested.parentElement) === row) out[nested.getAttribute("data-name")] = serialize(nested);
      });
      return out;
    });
  }

  function tool(label, text, action) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-sm btn-outline-secondary";
    b.setAttribute("data-action", action);
    b.setAttribute("aria-label", label);
    b.textContent = text;
    return b;
  }

  function refresh(list) {
    var noun = list.getAttribute("data-noun") || "row";
    var rows = rowsOf(list);
    rows.forEach(function (row, i) {
      var tools = row.querySelector("[data-tools]");
      if (!tools || ownRow(tools) !== row) return;
      tools.textContent = "";
      var up = tool("Move " + noun + " " + (i + 1) + " up", "Up", "up");
      var down = tool("Move " + noun + " " + (i + 1) + " down", "Down", "down");
      up.disabled = i === 0;
      down.disabled = i === rows.length - 1;
      tools.appendChild(up);
      tools.appendChild(down);
      tools.appendChild(tool("Remove " + noun + " " + (i + 1), "Remove", "remove"));
    });
  }

  function fill(list, data) {
    var shape = list.getAttribute("data-shape");
    var wrap = list.closest("[data-rows-wrap]");
    var template = wrap.querySelector(":scope > template");
    var entries = Array.isArray(data) && data.length ? data : [shape === "strings" ? "" : {}];
    entries.forEach(function (entry) {
      var row = template.content.firstElementChild.cloneNode(true);
      list.appendChild(row);
      if (shape === "strings") {
        var isObject = entry && typeof entry === "object";
        var text = isObject ? entry.text : entry;
        row.querySelector("[data-field='value']").value = typeof text === "string" ? text : "";
        var flag = row.querySelector("[data-field='sox_only']");
        if (flag) flag.checked = Boolean(isObject && entry.sox_only === true);
      } else {
        entry = entry && typeof entry === "object" ? entry : {};
        row.querySelectorAll("[data-field]").forEach(function (el) {
          if (ownRow(el) === row && typeof entry[el.getAttribute("data-field")] === "string") {
            el.value = entry[el.getAttribute("data-field")];
          }
        });
        row.querySelectorAll("[data-list][data-name]").forEach(function (nested) {
          if (ownRow(nested.parentElement) === row) fill(nested, entry[nested.getAttribute("data-name")]);
        });
      }
    });
    refresh(list);
  }

  function init(editor) {
    var output = editor.querySelector("[data-rows-output]");
    var list = editor.querySelector("[data-rows-wrap] > [data-list]");
    var data = [];
    try {
      data = JSON.parse(output.value || "[]");
    } catch (e) {
      data = [];
    }
    fill(list, data);
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-action]");
    if (!button) return;
    var action = button.getAttribute("data-action");
    if (action === "add") {
      var list = button.closest("[data-rows-wrap]").querySelector(":scope > [data-list]");
      fill(list, [list.getAttribute("data-shape") === "strings" ? "" : {}]);
      var last = rowsOf(list).pop();
      var first = last && last.querySelector("input, textarea, select");
      if (first) first.focus();
      return;
    }
    var row = ownRow(button);
    var parent = row && row.parentElement;
    if (!row || !parent) return;
    if (action === "remove") {
      row.remove();
    } else if (action === "up" && row.previousElementSibling) {
      parent.insertBefore(row, row.previousElementSibling);
    } else if (action === "down" && row.nextElementSibling) {
      parent.insertBefore(row.nextElementSibling, row);
    }
    refresh(parent);
    var again = action === "remove" ? null : row.querySelector("[data-tools] [data-action='" + action + "']:not(:disabled)");
    if (again && ownRow(again) === row) again.focus();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && event.target.matches("input") && event.target.closest("[data-rows-editor]")) {
      event.preventDefault();
    }
  });

  document.addEventListener("submit", function (event) {
    event.target.querySelectorAll("[data-rows-editor]").forEach(function (editor) {
      var list = editor.querySelector("[data-rows-wrap] > [data-list]");
      editor.querySelector("[data-rows-output]").value = JSON.stringify(serialize(list));
    });
  });

  document.querySelectorAll("[data-rows-editor]").forEach(init);
})();
