"""Checks that pasted text is cleaned safely and heading links are stable."""

import time

import pytest
from django import forms
from django.template import Context, Template

from apps.wiki.richtext import MAX_BODY_LENGTH, RichTextField, add_heading_anchors, clean_html
from apps.wiki.widgets import RichTextWidget

WORD_SNIPPET = """<html xmlns:o="urn:schemas-microsoft-com:office:office">
<head><style>p.MsoNormal {mso-style-parent:""; margin:0in;}</style></head>
<body lang=EN-US style='tab-interval:.5in'>
<!--[if gte mso 9]><xml><o:OfficeDocumentSettings></o:OfficeDocumentSettings></xml><![endif]-->
<h1 class=MsoTitle><span style='font-family:"Calibri Light";mso-ascii-font-family:Calibri'>Access Review</span></h1>
<p class=MsoNormal style='margin-bottom:0in;mso-margin-top-alt:auto'><span style='font-size:11.0pt;font-family:"Calibri",sans-serif'>Reviews are <b style='mso-bidi-font-weight:normal'>quarterly</b>.<o:p></o:p></span></p>
<p class=MsoNormal><span style='mso-spacerun:yes'>&nbsp;</span><o:p>&nbsp;</o:p></p>
<p class=MsoListParagraph style='text-indent:-.25in;mso-list:l0 level1 lfo1'>
<span style='font-family:Symbol'>&middot;&nbsp;&nbsp;</span>Export users</p>
<table class=MsoTableGrid border=1 cellspacing=0 style='border-collapse:collapse;mso-yfti-tbllook:1184'>
<tr style='mso-yfti-irow:0'><td width=200 valign=top style='width:150pt;mso-border-alt:solid windowtext .5pt'><p class=MsoNormal>Owner<o:p></o:p></p></td>
<td colspan=2 style='padding:0in'><p class=MsoNormal><i>Quarterly</i></p></td></tr>
</table>
</body></html>"""


def test_removes_dangerous_content():
    html = (
        '<p onclick="x()">Hi</p><script>alert(1)</script><style>p{}</style>'
        '<iframe src="http://evil"></iframe><img src="a.png" onerror="x()">'
        '<a href="javascript:alert(1)">bad</a><a href="JaVaScRiPt:alert(1)">bad2</a>'
    )
    out = clean_html(html)
    for banned in ("script", "style", "iframe", "<img", "onclick", "onerror", "javascript", "alert"):
        assert banned.lower() not in out.lower()
    assert "<p>Hi</p>" in out
    assert "bad" in out


def test_keeps_allowlisted_structure():
    html = (
        "<h2>A</h2><h3>B</h3><h4>C</h4><p>x<br>y <strong>s</strong> <em>e</em> <code>c</code></p>"
        "<ul><li>one</li></ul><ol><li>two</li></ol><blockquote>q</blockquote><pre>pre</pre><hr>"
        '<table><thead><tr><th colspan="2">h</th></tr></thead><tbody><tr><td rowspan="2">d</td></tr></tbody></table>'
    )
    out = clean_html(html)
    for fragment in (
        "<h2>A</h2>", "<h3>B</h3>", "<h4>C</h4>", "<br>", "<strong>s</strong>", "<em>e</em>",
        "<code>c</code>", "<ul><li>one</li></ul>", "<ol><li>two</li></ol>", "<blockquote>q</blockquote>",
        "<pre>pre</pre>", "<hr>", '<th colspan="2">h</th>', '<td rowspan="2">d</td>', "<thead>", "<tbody>",
    ):
        assert fragment in out


def test_converts_h1_b_i():
    out = clean_html("<h1>T</h1><p><b>b</b> <i>i</i></p>")
    assert out == "<h2>T</h2><p><strong>b</strong> <em>i</em></p>"


def test_attributes_stripped_except_allowed():
    out = clean_html('<p class="x" style="color:red" id="y">t</p><td style="a:b" colspan="2">c</td>')
    assert '<p>t</p>' in out
    assert "style" not in out and "class" not in out and "id=" not in out


@pytest.mark.parametrize("href", ["https://example.com/a", "http://example.com", "mailto:a@example.com", "/wiki/page/", "../other/", "#frag"])
def test_links_allowed_and_get_rel(href):
    out = clean_html(f'<a href="{href}" target="_blank" onclick="x">l</a>')
    assert f'href="{href}"' in out
    assert 'rel="noopener noreferrer"' in out
    assert "target" not in out and "onclick" not in out


def test_disallowed_link_schemes_dropped():
    out = clean_html('<a href="data:text/html;base64,AAA">d</a><a href="ftp://x/y">f</a>')
    assert "data:" not in out and "ftp:" not in out


def test_empty_paragraphs_dropped_and_nbsp_collapsed():
    out = clean_html("<p>&nbsp;</p><p> </p><p><br></p><p>a&nbsp;&nbsp;&nbsp;b</p><p> </p>")
    assert out == "<p>a b</p>"


def test_empty_input():
    assert clean_html("") == ""
    assert clean_html("   ") == ""
    assert clean_html(None) == ""


def test_word_snippet_comes_out_clean():
    out = clean_html(WORD_SNIPPET)
    for artifact in ("mso", "MsoNormal", "o:p", "<span", "style", "class", "<!--", "xml", "Calibri", "<html", "<body"):
        assert artifact not in out
    assert "<h2>Access Review</h2>" in out
    assert "<p>Reviews are <strong>quarterly</strong>.</p>" in out
    assert "<ul><li>Export users</li></ul>" in out.replace("\n", "")
    assert "<table>" in out and "<td>" in out and '<td colspan="2">' in out
    assert "<em>Quarterly</em>" in out
    assert "<p></p>" not in out


def test_anchors_unique_and_stable():
    html = "<h2>Scope</h2><p>a</p><h3>Scope</h3><h2>Scope</h2><h2>Other &amp; More</h2>"
    first, toc = add_heading_anchors(html)
    second, toc_again = add_heading_anchors(html)
    assert first == second and toc == toc_again
    ids = [item["id"] for item in toc]
    assert ids == ["scope", "scope-2", "scope-3", "other-more"]
    assert len(set(ids)) == len(ids)
    assert '<h2 id="scope">Scope</h2>' in first
    assert '<h3 id="scope-2">Scope</h3>' in first


def test_toc_structure_and_scope():
    html = "<h2>One</h2><h3>Sub <em>item</em></h3><h4>Skip</h4><p>text</p>"
    out, toc = add_heading_anchors(html)
    assert toc == [
        {"level": 2, "id": "one", "text": "One"},
        {"level": 3, "id": "sub-item", "text": "Sub item"},
    ]
    assert '<h4 id="skip">Skip</h4>' in out  # h4 gets an id but stays out of the contents
    assert "<h3 id=\"sub-item\">Sub <em>item</em></h3>" in out


def test_anchors_replace_existing_id_and_keep_content():
    out, toc = add_heading_anchors('<h2 id="stale">Title</h2><p>a &amp; b <a href="/x?a=1&amp;b=2">l</a></p>')
    assert '<h2 id="title">Title</h2>' in out
    assert "a &amp; b" in out and 'href="/x?a=1&amp;b=2"' in out
    assert toc[0]["id"] == "title"


def test_anchors_empty_and_untitled():
    assert add_heading_anchors("") == ("", [])
    out, toc = add_heading_anchors("<h2></h2><h2></h2>")
    assert [t["id"] for t in toc] == ["section", "section-2"]


def test_form_field_cleans():
    class F(forms.Form):
        body = RichTextField()

    form = F({"body": '<h1>T</h1><script>x</script><p style="a:b">ok</p>'})
    assert form.is_valid()
    assert form.cleaned_data["body"] == "<h2>T</h2><p>ok</p>"


def test_form_field_required_and_blank_after_clean():
    class F(forms.Form):
        body = RichTextField()

    assert not F({"body": ""}).is_valid()
    optional = RichTextField(required=False)
    assert optional.clean("<p>&nbsp;</p>") == ""


def test_widget_renders_editor_hook():
    html = RichTextWidget().render("body", "<p>hi &amp; bye</p>")
    assert "data-trac-editor" in html
    assert 'name="body"' in html
    assert "&lt;p&gt;hi &amp;amp; bye&lt;/p&gt;" in html


def test_widget_media_includes_vendored_files():
    media = str(RichTextWidget().media)
    assert "vendor/jodit/jodit.min.css" in media
    assert "vendor/jodit/jodit.min.js" in media
    assert "js/trac-editor.js" in media
    assert "http" not in media.replace("/static/", "")


def test_widget_in_form_media():
    class F(forms.Form):
        body = RichTextField()

    assert "trac-editor.js" in str(F().media)
    assert Template("{{ form.media }}").render(Context({"form": F()})).count("<script") == 2


def test_word_numbered_list_becomes_ol():
    html = (
        "<p class=MsoListParagraphCxSpFirst style='mso-list:l1 level1 lfo2'><span style='mso-list:Ignore'>1.<span>&nbsp;&nbsp;</span></span>First</p>"
        "<p class=MsoListParagraphCxSpLast style='mso-list:l1 level1 lfo2'><span style='mso-list:Ignore'>2.<span>&nbsp;&nbsp;</span></span>Second</p>"
    )
    assert clean_html(html).replace("\n", "") == "<ol><li>First</li><li>Second</li></ol>"


def test_oversized_body_rejected_with_friendly_message():
    class F(forms.Form):
        body = RichTextField()

    form = F({"body": "<p>" + "x" * MAX_BODY_LENGTH + "</p>"})
    assert not form.is_valid()
    assert "too long" in form.errors["body"][0]
    assert str(MAX_BODY_LENGTH) in form.errors["body"][0]


def test_unclosed_word_list_paragraphs_clean_quickly():
    html = '<p class="MsoListParagraph">item ' * 3000
    started = time.perf_counter()
    out = clean_html(html)
    assert time.perf_counter() - started < 0.5
    assert out.count("<li>") == 3000
    unterminated_tags = "<p class=MsoListParagraph " * 3000
    started = time.perf_counter()
    clean_html(unterminated_tags)
    assert time.perf_counter() - started < 0.5


def test_protocol_relative_link_is_dropped_but_local_paths_stay():
    out = clean_html('<a href="//evil.example/x">bad</a><a href="/guides/">ok</a>')
    assert "evil.example" not in out
    assert 'href="/guides/"' in out
    assert "bad" in out


def test_items_under_a_stage_get_short_stable_ids():
    html = "<h4>Item 1 before any stage</h4><h2>Stage 2: Build</h2><h4>Item 3: Access</h4><h4>Notes</h4><h2>Other</h2><h4>Item 1</h4>"
    out, toc = add_heading_anchors(html)
    assert '<h4 id="stage-2-item-3">Item 3: Access</h4>' in out
    assert '<h4 id="item-1-before-any-stage">' in out and '<h4 id="notes">' in out
    assert '<h4 id="item-1">Item 1</h4>' in out  # only under a "Stage N" heading
    assert [entry["level"] for entry in toc] == [2, 2]
