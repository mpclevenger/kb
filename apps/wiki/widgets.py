"""The rich-text editor box used on the guide and FAQ forms."""

from django import forms


class RichTextWidget(forms.Textarea):
    template_name = "wiki/widgets/richtext.html"

    class Media:
        css = {"all": ("vendor/jodit/jodit.min.css",)}
        js = ("vendor/jodit/jodit.min.js", "js/trac-editor.js")

    def __init__(self, attrs=None):
        defaults = {"data-trac-editor": "", "rows": 16}
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)
