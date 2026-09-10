# -*- coding: utf-8 -*-
"""
paper.py — محرّك بناء ورقة الأسئلة (A4)
=======================================
هذا الملف مشترك بين نسخة الحاسبة (CustomTkinter) ونسخة الموبايل (Flet).
يبني ورقة الامتحان بصيغة HTML/CSS مضبوطة على قياس A4، ثم تُحوَّل إلى PDF.

ليش HTML مو ReportLab؟
  لأن نص الأسئلة يحتوي تشكيل (أُحِبُّ قِرَاءَةَ القِصَصِ) و ReportLab + arabic_reshaper
  يكسر التشكيل ويفصل الحروف. المتصفح (Edge/Chrome) يشكّل العربي بشكل مثالي 100%
  ويطبع A4 بدقة، وهو موجود بكل جهاز ويندوز.

لا يحتاج أي مكتبة خارجية — بايثون قياسي فقط.
"""

import os
import json
import shutil
import tempfile
import subprocess
import webbrowser

# ---------------------------------------------------------------- النموذج

ARABIC_LETTERS = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط", "ي",
                  "ك", "ل", "م", "ن", "س", "ع", "ف", "ص", "ق", "ر"]

SEPARATORS = {
    "dots":   "نقاط متقطعة  ( • • • • )",
    "stars":  "نجوم  ( ✵ ✵ ✵ ✵ )",
    "line":   "خط متصل  ( ———— )",
    "double": "خط مزدوج  ( ═══ )",
    "none":   "بدون فاصل",
}

SPACING = {
    "compact": "متقاربة (تكدر تحشر أسئلة أكثر)",
    "normal":  "عادية",
    "wide":    "متباعدة (فراغ للإجابة)",
    "xwide":   "واسعة جداً (فراغ كبير)",
}

FONTS = {
    "traditional": "خط النسخ التقليدي (Traditional Arabic)",
    "amiri":       "خط أميري (Amiri)",
    "simplified":  "خط بسيط (Simplified Arabic)",
    "arial":       "خط عريض واضح (Arial)",
}

_FONT_STACK = {
    "traditional": "'Traditional Arabic','Sakkal Majalla','Amiri','Scheherazade New',serif",
    "amiri":       "'Amiri','Scheherazade New','Traditional Arabic',serif",
    "simplified":  "'Simplified Arabic','Arabic Typesetting','Traditional Arabic',serif",
    "arial":       "'Arial','Tahoma','Segoe UI',sans-serif",
}


def new_branch():
    return {"text": "", "mark": ""}


def new_question():
    return {"title": "", "total": "", "text": "", "lines": 0,
            "branches": [new_branch(), new_branch()]}


def new_paper():
    """يرجّع نموذج فارغ بالقيم الافتراضية."""
    return {
        "school": "",
        "title": "",
        "grade": "",
        "subject": "",
        "year": "",
        "code_time": "",
        "date": "",
        "teacher": "",
        "note": "",
        "basmala": True,
        "signature": False,
        "wish": "مع تمنياتنا لكم بالنجاح والتوفيق",
        "separator": "dots",
        "gap": "wide",
        "font": "traditional",
        "size": 15,
        "questions": [new_question()],
    }


def save_project(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    base = new_paper()
    base.update(data)
    for q in base["questions"]:
        q.setdefault("lines", 0)
        q.setdefault("branches", [])
    return base


# ---------------------------------------------------------------- HTML

def _esc(t):
    return (str(t or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _multiline(t):
    """يحوّل أسطر المستخدم إلى أسطر HTML."""
    t = _esc(t)
    return "<br>".join(t.split("\n"))


_CSS = """
@page { size: A4 portrait; margin: 10mm 9mm 8mm 9mm; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body{
  direction: rtl;
  text-align: right;
  color:#000;
  background:#fff;
  line-height: 1.9;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.sheet{ border:1.6px solid #000; padding:6mm 6mm 4mm 6mm; min-height: 272mm;
        display:flex; flex-direction:column; }
.head{ display:flex; align-items:flex-start; gap:4mm; }
.head .side{ width:33%; }
.head .mid{ width:34%; text-align:center; }
.head .lbl{ font-size:.82em; }
.head .big{ font-weight:700; }
.head .mid .bism{ font-size:.9em; margin-bottom:1mm; }
.head .mid .ttl{ font-weight:700; font-size:1.06em; }
.head .left{ text-align:left; direction:rtl; }
.head .left div{ white-space:nowrap; }
hr.rule{ border:none; border-top:1.2px solid #000; margin:2.5mm 0; }
.note{ text-align:center; font-weight:700; text-decoration:underline;
       text-underline-offset:3px; margin:1mm 0; }
.body{ flex:1 1 auto; padding-top:2mm; }
.q{ break-inside: avoid; page-break-inside: avoid; }
.qhead{ display:flex; justify-content:space-between; align-items:baseline;
        font-weight:700; }
.qhead .mark{ font-weight:400; font-size:.9em; white-space:nowrap; }
.qtext{ margin-right:6mm; }
.br{ margin-right:11mm; display:flex; justify-content:space-between;
     align-items:baseline; gap:4mm; }
.br .bt{ flex:1 1 auto; }
.br .bm{ font-size:.85em; white-space:nowrap; }
.dotline{ margin-right:11mm; border-bottom:1.3px dotted #444; height:1.05em; }
.sep{ height:0; }

/* ---- مستويات التباعد بين الأسئلة ---- */
.g-compact .q{ margin-bottom:2mm; }
.g-compact .qhead{ margin-bottom:1mm; }
.g-compact .br{ margin-top:1mm; }
.g-compact .dotline{ margin-top:2mm; }
.g-compact .sep{ margin:3mm 0; }

.g-normal .q{ margin-bottom:7mm; }
.g-normal .qhead{ margin-bottom:2mm; }
.g-normal .br{ margin-top:2mm; }
.g-normal .dotline{ margin-top:4mm; }
.g-normal .sep{ margin:5mm 0; }

.g-wide .q{ margin-bottom:13mm; }
.g-wide .qhead{ margin-bottom:3mm; }
.g-wide .br{ margin-top:3.5mm; }
.g-wide .dotline{ margin-top:6mm; }
.g-wide .sep{ margin:7mm 0; }

.g-xwide .q{ margin-bottom:20mm; }
.g-xwide .qhead{ margin-bottom:4mm; }
.g-xwide .br{ margin-top:5mm; }
.g-xwide .dotline{ margin-top:8mm; }
.g-xwide .sep{ margin:10mm 0; }
.sep.dots{   border-top:2px dotted #333; }
.sep.line{   border-top:1px solid #333; }
.sep.double{ border-top:3px double #333; }
.sep.stars{ border:none; text-align:center; height:auto; letter-spacing:.55em;
            color:#333; font-size:.8em; }
.foot{ margin-top:3mm; padding-top:2mm; border-top:1.2px solid #000;
       display:flex; justify-content:space-between; align-items:flex-end; }
.foot .w{ font-style:italic; }
.sig{ margin-top:6mm; text-align:left; }
.sig .box{ display:inline-block; border:1px solid #000; width:55mm; height:20mm;
           text-align:center; font-size:.8em; padding-top:1mm; }
@media screen{
  body{ background:#e9edf2; padding:14px; }
  .sheet{ background:#fff; max-width:210mm; margin:0 auto;
          box-shadow:0 6px 24px rgba(0,0,0,.18); }
}
"""


def _sep_html(kind):
    if kind == "none":
        return ""
    if kind == "stars":
        return '<div class="sep stars">✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵ ✵</div>'
    return '<div class="sep %s"></div>' % kind


def build_html(d, embed_font_link=True):
    """يبني ورقة الأسئلة كاملة كـ HTML جاهز للطباعة/التحويل."""
    stack = _FONT_STACK.get(d.get("font", "traditional"), _FONT_STACK["traditional"])
    size = d.get("size", 15)

    link = ""
    if embed_font_link:
        link = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
                '<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700'
                '&family=Scheherazade+New:wght@400;700&display=swap" rel="stylesheet">')

    # ---- الترويسة
    right = '<div class="side">'
    if d.get("school"):
        right += '<div class="lbl">المدرسة</div><div class="big">%s</div>' % _esc(d["school"])
    right += "</div>"

    mid = '<div class="mid">'
    if d.get("basmala", True):
        mid += '<div class="bism">بسم الله الرحمن الرحيم</div>'
    if d.get("title"):
        mid += '<div class="ttl">%s</div>' % _esc(d["title"])
    if d.get("year"):
        mid += '<div>%s</div>' % _esc(d["year"])
    mid += "</div>"

    left = '<div class="side left">'
    for lbl, key in (("الصف", "grade"), ("المادة", "subject"),
                     ("التاريخ", "date"), ("الزمن", "code_time")):
        if d.get(key):
            left += '<div><span class="lbl">%s:</span> %s</div>' % (lbl, _esc(d[key]))
    left += "</div>"

    html = ['<div class="sheet">',
            '<div class="head">', right, mid, left, '</div>',
            '<hr class="rule">']

    if d.get("note"):
        html.append('<div class="note">%s</div>' % _esc(d["note"]))
        html.append('<hr class="rule">')

    # ---- الأسئلة
    html.append('<div class="body">')
    qs = [q for q in d.get("questions", []) if _has_content(q)]
    for i, q in enumerate(qs):
        html.append('<div class="q">')
        ttl = _esc(q.get("title", "")).strip()
        head = 'السؤال /%d' % (i + 1)
        if ttl:
            head += '&nbsp;&nbsp;&nbsp;((%s))' % ttl
        mark = ''
        if str(q.get("total", "")).strip():
            mark = '<span class="mark">(%s درجة)</span>' % _esc(str(q["total"]).strip())
        html.append('<div class="qhead"><span>%s</span>%s</div>' % (head, mark))

        if q.get("text", "").strip():
            html.append('<div class="qtext">%s</div>' % _multiline(q["text"]))

        n = 0
        for b in q.get("branches", []):
            if not b.get("text", "").strip():
                continue
            lab = ARABIC_LETTERS[n] if n < len(ARABIC_LETTERS) else str(n + 1)
            n += 1
            bm = ''
            if str(b.get("mark", "")).strip():
                bm = '<span class="bm">(%s)</span>' % _esc(str(b["mark"]).strip())
            html.append('<div class="br"><span class="bt">%s) %s</span>%s</div>'
                        % (lab, _multiline(b["text"]), bm))

        for _ in range(int(q.get("lines", 0) or 0)):
            html.append('<div class="dotline"></div>')

        html.append('</div>')
        if i < len(qs) - 1:
            html.append(_sep_html(d.get("separator", "dots")))
    html.append('</div>')

    # ---- التذييل
    foot = '<div class="foot">'
    foot += '<div>%s</div>' % (
        ('مدرس المادة: %s' % _esc(d["teacher"])) if d.get("teacher") else '&nbsp;')
    foot += '<div class="w">%s</div>' % _esc(d.get("wish", ""))
    foot += '</div>'
    html.append(foot)

    if d.get("signature"):
        html.append('<div class="sig"><div class="box">توقيع إدارة المدرسة</div></div>')

    html.append('</div>')

    doc = (
        '<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s</title>%s<style>%s\nbody{font-family:%s; font-size:%spt;}</style>'
        '</head><body class="g-%s">%s</body></html>'
        % (_esc(d.get("title") or "ورقة أسئلة"), link, _CSS, stack, size,
           d.get("gap", "wide") if d.get("gap") in SPACING else "wide",
           "".join(html))
    )
    return doc


def _has_content(q):
    if q.get("title", "").strip() or q.get("text", "").strip():
        return True
    return any(b.get("text", "").strip() for b in q.get("branches", []))


# ---------------------------------------------------------------- PDF

_CHROME_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _find_browser():
    for p in _CHROME_PATHS:
        if os.path.exists(p):
            return p
    for name in ("msedge", "chrome", "chromium", "chromium-browser",
                 "google-chrome", "brave"):
        p = shutil.which(name)
        if p:
            return p
    return None


def write_html_temp(d, name="exam_paper.html"):
    """يكتب الـ HTML بملف مؤقت ويرجّع مساره."""
    folder = os.path.join(tempfile.gettempdir(), "exam_maker")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_html(d))
    return path


def export_pdf(d, out_pdf):
    """
    يصدّر PDF بقياس A4 عن طريق Edge/Chrome (بدون واجهة).
    يرجّع (True, مسار) عند النجاح أو (False, رسالة الخطأ).
    """
    br = _find_browser()
    if not br:
        return False, "ما لكيت متصفح Edge أو Chrome على الجهاز."

    html = write_html_temp(d)
    url = "file:///" + os.path.abspath(html).replace("\\", "/")
    out_pdf = os.path.abspath(out_pdf)

    base = ["--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=6000",
            "--print-to-pdf=" + out_pdf, url]

    for head in (["--headless=new"], ["--headless"]):
        try:
            r = subprocess.run([br] + head + base, timeout=90,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 800:
                return True, out_pdf
            err = (r.stderr or b"").decode("utf-8", "ignore")[-300:]
        except Exception as e:
            err = str(e)
    return False, "ما زبطت الطباعة الصامتة: %s" % err


def open_preview(d):
    """يفتح المعاينة بالمتصفح (Ctrl+P للطباعة أو الحفظ PDF)."""
    path = write_html_temp(d)
    webbrowser.open("file:///" + os.path.abspath(path).replace("\\", "/"))
    return path
