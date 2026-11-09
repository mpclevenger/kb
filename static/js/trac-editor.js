(function () {
  "use strict";

  // Must match ALLOWED_TAGS in apps/wiki/richtext.py (a test compares the two). Anything else is
  // stripped when the page is saved, so allowing more tags here would only hide content.
  var CONTENT_TAGS = "p,br,h2,h3,h4,strong,em,ul,ol,li,a,blockquote,code,pre,hr,table,thead,tbody,tr,th,td";

  function toggleBlockquote(editor) {
    var node = editor.s.current();
    var el = node && (node.nodeType === 1 ? node : node.parentElement);
    var inQuote = el && el.closest("blockquote");
    editor.execCommand("formatBlock", false, inQuote ? "p" : "blockquote");
  }

  function toggleCode(editor) {
    var node = editor.s.current();
    var existing = node && (node.nodeType === 1 ? node : node.parentElement);
    existing = existing && existing.closest("code");
    if (existing) {
      editor.s.select(existing);
      var text = editor.editorDocument.createTextNode(existing.textContent);
      existing.replaceWith(text);
      editor.synchronizeValues();
      return;
    }
    editor.s.wrapInTag("code");
    editor.synchronizeValues();
  }

  // One toolbar for every screen width; "|" draws a divider.
  var BUTTONS = ["paragraph", "bold", "italic", "|", "ul", "ol", "|", "link", "table", "quote", "code", "hr", "|", "undo", "redo"];

  var OPTIONS = {
    toolbarAdaptive: false,
    toolbarSticky: false,
    height: 420,
    minHeight: 240,
    language: "en",
    enter: "p",
    spellcheck: true,
    showCharsCounter: false,
    showWordsCounter: false,
    showXPathInStatusbar: false,
    statusbar: false,
    disablePlugins: ["image", "image-processor", "image-properties", "file", "video", "media", "resize-handler", "drag-and-drop", "drag-and-drop-element", "font", "color", "class-span", "iframe", "xpath", "about", "print", "powered-by-jodit"],
    askBeforePasteHTML: false,
    askBeforePasteFromWord: false,
    processPasteHTML: true,
    processPasteFromWord: true,
    defaultActionOnPaste: "insert_clear_html",
    defaultActionOnPasteFromWord: "insert_clear_html",
    cleanHTML: {
      allowTags: CONTENT_TAGS,
      denyTags: "script,iframe,object,embed,style,img,svg",
      removeEmptyElements: true,
      fillEmptyParagraph: false,
      replaceNBSP: true,
      removeEventAttributes: true,
      safeJavaScriptLink: true,
      replaceOldTags: { i: "em", b: "strong" },
    },
    link: {
      followOnDblClick: false,
      processVideoLink: false,
      processPastedLink: false,
      openInNewTabCheckbox: false,
      noFollowCheckbox: false,
      modeClassName: false,
    },
    controls: {
      paragraph: {
        list: { p: "Normal", h2: "Heading 2", h3: "Heading 3", h4: "Heading 4" },
      },
    },
    extraButtons: [
      { name: "quote", tooltip: "Blockquote", iconURL: "", text: "❝", exec: toggleBlockquote },
      { name: "code", tooltip: "Code", iconURL: "", text: "</>", exec: toggleCode },
    ],
    buttons: BUTTONS,
    buttonsMD: BUTTONS,
    buttonsSM: BUTTONS,
    buttonsXS: BUTTONS,
  };

  function init(root) {
    if (typeof window.Jodit === "undefined") {
      return;
    }
    var scope = root && root.querySelectorAll ? root : document;
    var targets = Array.prototype.slice.call(scope.querySelectorAll("textarea[data-trac-editor]"));
    if (scope.matches && scope.matches("textarea[data-trac-editor]")) {
      targets.push(scope);
    }
    targets.forEach(function (el) {
      if (el.dataset.tracEditorReady === "1" || el.closest(".jodit-container")) {
        return;
      }
      var editor = window.Jodit.make(el, OPTIONS);
      el.dataset.tracEditorReady = "1";
      var form = el.form;
      if (form) {
        form.addEventListener("submit", function () {
          editor.synchronizeValues();
        });
      }
    });
  }

  function destroyDetached() {
    (window.Jodit && window.Jodit.instances ? Object.keys(window.Jodit.instances) : []).forEach(function (id) {
      var inst = window.Jodit.instances[id];
      if (inst && inst.container && !document.body.contains(inst.container)) {
        inst.destruct();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });
  document.addEventListener("htmx:afterSwap", function (event) {
    destroyDetached();
    init(event.detail && event.detail.target ? event.detail.target : document);
  });
})();
