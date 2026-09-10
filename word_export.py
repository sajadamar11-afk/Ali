# -*- coding: utf-8 -*-
"""
word_export.py — تصدير ورقة الأسئلة إلى Word (.docx) قابل للتعديل
==================================================================
يبني ملف docx حقيقي (WordprocessingML) بمكتبات بايثون القياسية فقط —
بدون python-docx وبدون أي تنصيب.

الناتج ملف Word نظيف: نصوص عربية RTL، قياس A4، إطار للصفحة، جداول بلا حدود
للترويسة، وتباعد يتبع نفس إعداد "التباعد بين الأسئلة" الموجود بالبرنامج.
كلشي قابل للتعديل داخل Word عادي.
"""

import os
import zipfile

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# --------------------------------------------------- قياسات (تويپ: 1مم = 56.7)
MM = 56.7
PAGE_W, PAGE_H = 11906, 16838          # A4
MARGIN = 624                           # ~11 مم
USABLE = PAGE_W - MARGIN * 2

GAP_AFTER = {"compact": 110, "normal": 400, "wide": 740, "xwide": 1130}
GAP_BRANCH = {"compact": 60, "normal": 115, "wide": 200, "xwide": 285}
GAP_LINE = {"compact": 115, "normal": 230, "wide": 340, "xwide": 450}
SEP_STYLE = {"dots": "dotted", "line": "single", "double": "double",
             "stars": None, "none": None}


def esc(t):
    return (str(t if t is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# --------------------------------------------------- عناصر بناء
def run(text, bold=False, size=None, under=False, italic=False, color=None):
    rpr = "<w:rtl/>"
    if bold:
        rpr += "<w:b/><w:bCs/>"
    if italic:
        rpr += "<w:i/><w:iCs/>"
    if under:
        rpr += '<w:u w:val="single"/>'
    if color:
        rpr += '<w:color w:val="%s"/>' % color
    if size:
        rpr += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size)
    out = []
    for i, line in enumerate(str(text or "").split("\n")):
        if i:
            out.append("<w:br/>")
        out.append('<w:t xml:space="preserve">%s</w:t>' % esc(line))
    return "<w:r><w:rPr>%s</w:rPr>%s</w:r>" % (rpr, "".join(out))


def para(runs="", align="right", after=0, before=0, indent=0,
         border=None, line=None, keep=False):
    p = ["<w:pPr><w:bidi/>"]
    if keep:
        p.append("<w:keepNext/><w:keepLines/>")
    if border:
        p.append('<w:pBdr><w:bottom w:val="%s" w:sz="%d" w:space="1" '
                 'w:color="%s"/></w:pBdr>' % border)
    sp = '<w:spacing w:before="%d" w:after="%d"' % (before, after)
    if line:
        sp += ' w:line="%d" w:lineRule="auto"' % line
    p.append(sp + "/>")
    if indent:
        p.append('<w:ind w:left="%d" w:right="%d"/>' % (indent, indent))
    p.append('<w:jc w:val="%s"/></w:pPr>' % align)
    return "<w:p>%s%s</w:p>" % ("".join(p), runs)


def cell(width, body, align="right"):
    if not body:
        body = para("")
    return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>'
            '<w:vAlign w:val="top"/></w:tcPr>%s</w:tc>' % (width, body))


def table(widths, cells):
    """جدول بلا حدود، اتجاه من اليمين لليسار."""
    borders = ("<w:tblBorders>" + "".join(
        '<w:%s w:val="none" w:sz="0" w:space="0" w:color="auto"/>' % s
        for s in ("top", "left", "bottom", "right", "insideH", "insideV")
    ) + "</w:tblBorders>")
    grid = "".join('<w:gridCol w:w="%d"/>' % w for w in widths)
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:bidiVisual/>%s'
        '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="40" w:type="dxa"/>'
        '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="40" w:type="dxa"/>'
        '</w:tblCellMar><w:tblLayout w:type="fixed"/></w:tblPr>'
        '<w:tblGrid>%s</w:tblGrid><w:tr>%s</w:tr></w:tbl>'
        % (sum(widths), borders, grid, "".join(cells)))


def hr(before=60, after=60):
    return para("", after=after, before=before,
                border=("single", 8, "000000"))


# --------------------------------------------------- المستند
def _body(d):
    from paper import ARABIC_LETTERS, _has_content

    sz = int(d.get("size", 15)) * 2          # نصف نقطة
    small = max(sz - 4, 14)
    gap = d.get("gap", "wide")
    if gap not in GAP_AFTER:
        gap = "wide"
    after_q = GAP_AFTER[gap]
    after_b = GAP_BRANCH[gap]
    after_l = GAP_LINE[gap]

    out = []

    # ---- الترويسة (3 خانات)
    w3 = USABLE // 3
    right = ""
    if d.get("school"):
        right = (para(run("المدرسة", size=small), after=20)
                 + para(run(d["school"], bold=True, size=sz)))
    mid = ""
    if d.get("basmala", True):
        mid += para(run("بسم الله الرحمن الرحيم", size=small), "center", after=40)
    if d.get("title"):
        mid += para(run(d["title"], bold=True, size=sz + 2), "center", after=40)
    if d.get("year"):
        mid += para(run(d["year"], size=sz), "center")
    left = ""
    for lbl, key in (("الصف", "grade"), ("المادة", "subject"),
                     ("التاريخ", "date"), ("الزمن", "code_time")):
        if d.get(key):
            left += para(run("%s: %s" % (lbl, d[key]), size=small), "left", after=30)

    out.append(table([w3, USABLE - 2 * w3, w3],
                     [cell(w3, right), cell(USABLE - 2 * w3, mid),
                      cell(w3, left, "left")]))
    out.append(hr(120, 60))

    if d.get("note"):
        out.append(para(run(d["note"], bold=True, size=sz, under=True),
                        "center", after=60))
        out.append(hr(0, 200))

    # ---- الأسئلة
    qs = [q for q in d.get("questions", []) if _has_content(q)]
    wm = 1900
    wq = USABLE - wm
    for i, q in enumerate(qs):
        head = "السؤال /%d" % (i + 1)
        if (q.get("title") or "").strip():
            head += "     ((%s))" % q["title"].strip()
        mark = ""
        if str(q.get("total", "")).strip():
            mark = "(%s درجة)" % str(q["total"]).strip()

        out.append(table(
            [wq, wm],
            [cell(wq, para(run(head, bold=True, size=sz), after=0)),
             cell(wm, para(run(mark, size=small), "left"), "left")]))

        if (q.get("text") or "").strip():
            out.append(para(run(q["text"], size=sz), after=60,
                            indent=int(3 * MM), line=340))

        n = 0
        for b in q.get("branches", []) or []:
            if not (b.get("text") or "").strip():
                continue
            lab = ARABIC_LETTERS[n] if n < len(ARABIC_LETTERS) else str(n + 1)
            n += 1
            txt = "%s) %s" % (lab, b["text"].strip())
            if str(b.get("mark", "")).strip():
                txt += "      (%s)" % str(b["mark"]).strip()
            out.append(para(run(txt, size=sz), after=after_b,
                            indent=int(7 * MM), line=340))

        for _ in range(int(q.get("lines", 0) or 0)):
            out.append(para("", after=after_l, indent=int(7 * MM),
                            border=("dotted", 6, "555555")))

        # ---- الفاصل
        if i < len(qs) - 1:
            kind = d.get("separator", "dots")
            style = SEP_STYLE.get(kind)
            if kind == "stars":
                out.append(para(run("✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵", size=small,
                                    color="555555"), "center",
                                before=after_q // 2, after=after_q // 2))
            elif style:
                out.append(para("", before=after_q // 2, after=after_q // 2,
                                border=(style, 8, "333333")))
            else:
                out.append(para("", after=after_q))
        else:
            out.append(para("", after=after_q))

    # ---- التذييل
    out.append(hr(60, 80))
    wf = USABLE // 2
    out.append(table(
        [wf, USABLE - wf],
        [cell(wf, para(run(("مدرس المادة: %s" % d["teacher"])
                           if d.get("teacher") else "", size=small))),
         cell(USABLE - wf, para(run(d.get("wish", ""), size=small, italic=True),
                                "left"), "left")]))

    if d.get("signature"):
        out.append(para("", after=200))
        out.append(para(run("توقيع إدارة المدرسة", size=small), "left",
                        before=400, border=("single", 6, "000000")))

    out.append(para(""))          # فقرة ختامية إلزامية بعد الجدول

    # ---- إعدادات الصفحة
    out.append(
        '<w:sectPr><w:pgSz w:w="%d" w:h="%d"/>'
        '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
        'w:header="0" w:footer="0" w:gutter="0"/>'
        '<w:pgBorders w:offsetFrom="page">%s</w:pgBorders>'
        '<w:bidi/><w:rtlGutter/></w:sectPr>'
        % (PAGE_W, PAGE_H, MARGIN, MARGIN, MARGIN, MARGIN,
           "".join('<w:%s w:val="single" w:sz="12" w:space="20" w:color="000000"/>'
                   % s for s in ("top", "left", "bottom", "right"))))

    return "".join(out)


_FONT_CS = {
    "traditional": "Traditional Arabic",
    "amiri": "Amiri",
    "simplified": "Simplified Arabic",
    "arial": "Arial",
}


def _styles(d):
    f = _FONT_CS.get(d.get("font", "traditional"), "Traditional Arabic")
    sz = int(d.get("size", 15)) * 2
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles %s><w:docDefaults><w:rPrDefault><w:rPr>'
        '<w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s"/>'
        '<w:sz w:val="%d"/><w:szCs w:val="%d"/><w:lang w:bidi="ar-IQ"/>'
        '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
        '<w:bidi/><w:jc w:val="right"/>'
        '<w:spacing w:after="0" w:line="276" w:lineRule="auto"/>'
        '</w:pPr></w:pPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>'
        % (NS, f, f, f, sz, sz))


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>')

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>')

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>')


def build_docx_bytes(d):
    """يرجّع محتوى ملف .docx كـ bytes."""
    import io
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document %s><w:body>%s</w:body></w:document>' % (NS, _body(d)))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        z.writestr("word/styles.xml", _styles(d))
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def export_docx(d, out_path):
    """يحفظ ملف Word. يرجّع (True, المسار) أو (False, الخطأ)."""
    try:
        data = build_docx_bytes(d)
        with open(out_path, "wb") as f:
            f.write(data)
        return True, os.path.abspath(out_path)
    except Exception as e:
        return False, str(e)
