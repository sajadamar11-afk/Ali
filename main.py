# -*- coding: utf-8 -*-
"""
صانع النماذج الامتحانية — نسخة الموبايل (بايثون / Flet)
ملف الدخول: main.py  |  المحرك: paper.py + word_export.py (نفس المجلد)
=======================================================
نفس المحرك (paper.py) بالضبط، بس الواجهة مصممة للشاشة الطولية.

تشغيل على الحاسبة للتجربة:
    pip install flet
    flet run main.py

نشر على الموبايل (PWA على GitHub Pages):
    flet build web
    ثم ارفع محتوى مجلد build/web إلى الريبو → Settings → Pages
    وافتح الرابط بالموبايل → "إضافة إلى الشاشة الرئيسية"

بناء APK لأندرويد:
    flet build apk
"""

import os
import sys
import json

import flet as ft

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper
import word_export

Icons = getattr(ft, "Icons", None) or ft.icons
Colors = getattr(ft, "Colors", None) or ft.colors

# ============================================================
#  طبقة توافق مع كل إصدارات Flet (القديمة والجديدة)
#  كل دالة هنا تجرّب الواجهة الجديدة وترجع للقديمة إذا ما اشتغلت.
# ============================================================

def PAD(left=0, top=0, right=0, bottom=0):
    """حشوة تشتغل بأي إصدار — ترجع رقم إذا الصنف غير متوفر."""
    for maker in (
        lambda: ft.Padding(left, top, right, bottom),
        lambda: ft.padding.only(left=left, top=top, right=right, bottom=bottom),
    ):
        try:
            return maker()
        except Exception:
            continue
    return max(left, top, right, bottom)


def OPT(key, text=None):
    """خيار قائمة منسدلة — ft.DropdownOption الجديد أو ft.dropdown.Option القديم."""
    for maker in (
        lambda: ft.DropdownOption(key=key, text=text if text is not None else key),
        lambda: ft.dropdown.Option(key, text) if text is not None
        else ft.dropdown.Option(key),
    ):
        try:
            return maker()
        except Exception:
            continue
    return key


def SAFE(cls, **kw):
    """ينشئ عنصراً ويشيل أي وسيط غير مدعوم بهذا الإصدار بدل ما يطيح."""
    kw = {k: v for k, v in kw.items() if v is not None}
    while True:
        try:
            return cls(**kw)
        except TypeError as e:
            msg = str(e)
            dropped = None
            for k in list(kw):
                if ("'%s'" % k) in msg or ('"%s"' % k) in msg:
                    dropped = k
                    break
            if dropped is None:
                raise
            kw.pop(dropped)


def TXT(value, **kw):
    return SAFE(ft.Text, value=value, **kw)


def OPACITY(op, color):
    try:
        return Colors.with_opacity(op, color)
    except Exception:
        return color


def BORDER_TOP(color="#dfe3e8", w=1):
    try:
        return ft.border.only(top=ft.BorderSide(w, color))
    except Exception:
        return None


BLUE = "#1e4d8c"
RED = "#c62828"
GREEN = "#2e7d32"
STORE_KEY = "exam_maker.project"


# ------------------------------------------------ فتح/تنزيل الملفات
# بايثون داخل المتصفح ممكن يشتغل بمعزل (worker) وما يوصل لـ window/document.
# لذلك نجرّب كل الطرق بالترتيب ونسجّل نتيجة كل وحدة حتى نعرف شنو نجح.

LOG = []          # سجل آخر محاولة — يُعرض للمستخدم عند الفشل


def _try(name, fn):
    try:
        r = fn()
        LOG.append("✅ %s" % name)
        return True, r
    except Exception as e:
        LOG.append("❌ %s → %s: %s" % (name, type(e).__name__, str(e)[:90]))
        return False, None


def _blob_url(data, mime):
    """ينشئ رابط blob من نص أو bytes."""
    import js
    if isinstance(data, str):
        payload = data
    else:
        payload = js.Uint8Array.new(len(data))
        for i, b in enumerate(data):
            payload[i] = b
    parts = js.Array.new()
    parts.push(payload)
    try:
        from pyodide.ffi import to_js
        opts = to_js({"type": mime}, dict_converter=js.Object.fromEntries)
        blob = js.Blob.new(parts, opts)
    except Exception:
        blob = js.Blob.new(parts)
    return js.URL.createObjectURL(blob)


def deliver(page, data, mime, filename, download=False):
    """
    يوصّل الملف للمستخدم بأي طريقة متاحة.
    يرجّع (نجح؟, وصف).
    """
    del LOG[:]

    # 1) رابط blob + فتحه عن طريق Flet نفسه (يشتغل حتى لو ما نوصل لـ window)
    ok, url = _try("blob + launch_url", lambda: _blob_url(data, mime))
    if ok and url:
        ok2, _ = _try("launch_url", lambda: page.launch_url(url))
        if ok2:
            return True, "انفتح بتبويب جديد"

        # 2) رابط تنزيل بعنصر <a>
        def _anchor():
            import js
            a = js.document.createElement("a")
            a.href = url
            if download:
                a.download = filename
            a.target = "_blank"
            js.document.body.appendChild(a)
            a.click()
            js.document.body.removeChild(a)
            return True
        ok3, _ = _try("anchor click", _anchor)
        if ok3:
            return True, "تم التنزيل"

        # 3) window.open مباشرة
        def _winopen():
            import js
            js.window.open(url, "_blank")
            return True
        ok4, _ = _try("window.open", _winopen)
        if ok4:
            return True, "انفتح بتبويب جديد"

    # 4) data URL عبر Flet
    def _dataurl():
        import base64
        raw = data.encode("utf-8") if isinstance(data, str) else data
        b64 = base64.b64encode(raw).decode("ascii")
        page.launch_url("data:%s;base64,%s" % (mime, b64))
        return True
    ok5, _ = _try("data URL", _dataurl)
    if ok5:
        return True, "انفتح بتبويب جديد"

    # 5) سطح مكتب
    def _desktop():
        import webbrowser
        folder = os.path.join(os.path.expanduser("~"), "exam_maker")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        mode, payload = ("w", data) if isinstance(data, str) else ("wb", data)
        with open(path, mode, **({"encoding": "utf-8"} if mode == "w" else {})) as f:
            f.write(payload)
        if not download:
            webbrowser.open("file:///" + os.path.abspath(path).replace("\\", "/"))
        return path
    ok6, path = _try("حفظ محلي", _desktop)
    if ok6:
        return True, str(path)

    return False, "\n".join(LOG)


def show_report(page, title, body):
    """نافذة تعرض تفاصيل ما صار (للتشخيص عند الفشل)."""
    dlg = SAFE(
        ft.AlertDialog,
        title=TXT(title, rtl=True, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            [TXT(body, size=12, selectable=True)],
            scroll=ft.ScrollMode.AUTO, height=300, width=340, tight=True),
        actions=[ft.TextButton("تمام", on_click=lambda e: _close(page, dlg))],
    )
    try:
        page.open(dlg)
    except Exception:
        page.dialog = dlg
        dlg.open = True
        page.update()


def _close(page, dlg):
    try:
        page.close(dlg)
    except Exception:
        dlg.open = False
        page.update()


def toast(page, msg):
    sb = SAFE(ft.SnackBar, content=TXT(msg, rtl=True), duration=2500)
    try:
        page.open(sb)               # Flet الحديث
    except Exception:
        page.snack_bar = sb
        page.snack_bar.open = True
        page.update()


# ------------------------------------------------ عناصر مساعدة
def tf(label, hint="", value="", multiline=False, lines=3, width=None):
    return SAFE(
        ft.TextField,
        label=label, hint_text=hint, value=value or "",
        multiline=multiline, min_lines=lines if multiline else 1,
        max_lines=lines + 4 if multiline else 1,
        text_align=ft.TextAlign.RIGHT, rtl=True, dense=True, width=width,
        border_radius=10, text_size=14,
    )


# ------------------------------------------------ بطاقة سؤال
class QCard:
    def __init__(self, app, data):
        self.app = app
        self.branches = []

        self.no = TXT("السؤال /1", weight=ft.FontWeight.BOLD,
                      size=16, color=BLUE, rtl=True)
        self.title = tf("عنوان السؤال", "مثال: أقسام الكلام", data.get("title", ""))
        self.total = tf("درجة السؤال", "20", str(data.get("total", "") or ""), width=120)
        self.text = tf("نص السؤال", "اكتب نص السؤال هنا...",
                       data.get("text", ""), multiline=True, lines=3)
        self.lines = SAFE(
            ft.Dropdown,
            label="أسطر إجابة", width=120, dense=True, text_size=13,
            value=str(data.get("lines", 0) or 0),
            options=[OPT(str(i)) for i in (0, 1, 2, 3, 4, 5, 6, 8, 10)])

        self.bcol = ft.Column(spacing=6, tight=True)

        self.view = ft.Card(
            elevation=2,
            content=ft.Container(
                padding=12, border_radius=12,
                content=ft.Column(spacing=8, tight=True, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        self.no,
                        ft.IconButton(Icons.DELETE_OUTLINE, icon_color=RED,
                                      tooltip="حذف السؤال",
                                      on_click=lambda e: self.app.del_question(self)),
                    ]),
                    self.title,
                    ft.Row(spacing=8, controls=[self.total, self.lines]),
                    self.text,
                    TXT("الفروع:", size=12, color=Colors.GREY, rtl=True),
                    self.bcol,
                    ft.TextButton("+ إضافة فرع", icon=Icons.ADD,
                                  on_click=lambda e: self.add_branch(update=True)),
                ]),
            ),
        )

        for b in data.get("branches", []) or []:
            self.add_branch(b.get("text", ""), b.get("mark", ""))
        if not self.branches:
            self.add_branch()

    def add_branch(self, text="", mark="", update=False):
        t = tf("نص الفرع", "اكتب نص الفرع هنا...", text)
        m = tf("الدرجة", "5", str(mark or ""), width=90)
        item = {}
        row = ft.Row(spacing=6, controls=[
            ft.Container(content=t, expand=True), m,
            ft.IconButton(Icons.CLOSE, icon_color=RED, icon_size=18,
                          on_click=lambda e: self.del_branch(item)),
        ])
        item.update({"row": row, "text": t, "mark": m})
        self.branches.append(item)
        self.bcol.controls.append(row)
        if update:
            self.bcol.update()

    def del_branch(self, item):
        if item in self.branches:
            self.branches.remove(item)
            self.bcol.controls.remove(item["row"])
            self.bcol.update()

    def collect(self):
        return {
            "title": (self.title.value or "").strip(),
            "total": (self.total.value or "").strip(),
            "text": self.text.value or "",
            "lines": int(self.lines.value or 0),
            "branches": [{"text": (b["text"].value or "").strip(),
                          "mark": (b["mark"].value or "").strip()}
                         for b in self.branches],
        }


# ------------------------------------------------ التطبيق
class MobileApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.cards = []

        page.title = "صانع النماذج الامتحانية"
        page.rtl = True
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0
        page.scroll = None

        self.f = {
            "school":    tf("اسم المدرسة", "ثانوية ... الأهلية للبنين"),
            "title":     tf("عنوان الامتحان", "أسئلة امتحان نهاية الكورس الأول"),
            "grade":     tf("الصف / المرحلة", "الأول متوسط"),
            "subject":   tf("المادة", "اللغة العربية"),
            "year":      tf("العام الدراسي / الدور", "للعام الدراسي 2025-2026"),
            "code_time": tf("الرمز / الوقت", "ساعتان"),
            "date":      tf("التاريخ", "21 / 1 / 2026"),
            "teacher":   tf("اسم مدرس المادة", "الأستاذ ..."),
            "note":      tf("ملاحظة عامة (أعلى الأسئلة)", "أجب عن خمسة أسئلة فقط"),
            "wish":      tf("عبارة التذييل", "مع تمنياتنا لكم بالنجاح والتوفيق"),
        }
        self.f["wish"].value = "مع تمنياتنا لكم بالنجاح والتوفيق"

        self.cb_sig = ft.Checkbox(label="خانة توقيع (إدارة المدرسة)", value=False)
        self.cb_bism = ft.Checkbox(label="إظهار البسملة", value=True)

        self.dd_sep = SAFE(
            ft.Dropdown,
            label="شكل الفاصل", dense=True, text_size=13, value="dots",
            options=[OPT(k, v) for k, v in paper.SEPARATORS.items()])
        self.dd_gap = SAFE(
            ft.Dropdown,
            label="التباعد بين الأسئلة", dense=True, text_size=13, value="wide",
            options=[OPT(k, v) for k, v in paper.SPACING.items()])
        self.dd_font = SAFE(
            ft.Dropdown,
            label="خط الورقة", dense=True, text_size=13, value="traditional",
            options=[OPT(k, v) for k, v in paper.FONTS.items()])
        self.dd_size = SAFE(
            ft.Dropdown,
            label="الحجم", dense=True, text_size=13, value="15", width=95,
            options=[OPT(str(i)) for i in range(11, 23)])

        self.qcol = ft.Column(spacing=10, tight=True)

        header = ft.Container(
            bgcolor=BLUE, padding=PAD(16, 14, 16, 14),
            content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                TXT("صانع النماذج الامتحانية", color="#fff",
                    size=18, weight=ft.FontWeight.BOLD, rtl=True),
                ft.IconButton(Icons.DARK_MODE, icon_color="#fff",
                              tooltip="تبديل المظهر", on_click=self.toggle_theme),
            ]))

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=12,
            controls=[
                ft.Container(
                    padding=12,
                    content=ft.Column(spacing=8, tight=True, controls=[
                        TXT("الترويسة الرسمية للامتحان", size=16,
                            weight=ft.FontWeight.BOLD, color=BLUE, rtl=True),
                        self.f["school"], self.f["title"],
                        ft.Row(spacing=8, controls=[
                            ft.Container(self.f["grade"], expand=True),
                            ft.Container(self.f["subject"], expand=True)]),
                        ft.Row(spacing=8, controls=[
                            ft.Container(self.f["year"], expand=True),
                            ft.Container(self.f["code_time"], expand=True)]),
                        ft.Row(spacing=8, controls=[
                            ft.Container(self.f["date"], expand=True),
                            ft.Container(self.f["teacher"], expand=True)]),
                        self.f["note"], self.f["wish"],
                        self.cb_bism, self.cb_sig,
                        ft.Divider(),
                        self.dd_gap,
                        ft.Row(spacing=8, controls=[
                            ft.Container(self.dd_sep, expand=True),
                            ft.Container(self.dd_font, expand=True)]),
                        self.dd_size,
                    ])),
                ft.Container(padding=PAD(12, 0, 12, 0), content=self.qcol),
                ft.Container(
                    padding=12,
                    content=ft.ElevatedButton(
                        "+  إضافة سؤال رئيسي جديد", bgcolor=GREEN, color="#fff",
                        height=46, expand=True,
                        on_click=lambda e: self.add_question(update=True))),
                ft.Container(height=90),
            ])

        bottom = ft.Container(
            bgcolor=OPACITY(.96, "#ffffff"),
            padding=10, border=BORDER_TOP(),
            content=ft.Row(spacing=8, controls=[
                ft.Container(expand=True, content=ft.ElevatedButton(
                    "🖨  معاينة وطباعة (PDF / A4)", bgcolor=BLUE, color="#fff",
                    height=48, on_click=self.do_print)),
                ft.ElevatedButton("Word", icon=Icons.DESCRIPTION_OUTLINED,
                                  bgcolor="#2b579a", color="#fff", height=48,
                                  on_click=self.do_word),
                ft.IconButton(Icons.SAVE_OUTLINED, tooltip="حفظ",
                              on_click=self.do_save),
                ft.IconButton(Icons.FOLDER_OPEN_OUTLINED, tooltip="استرجاع",
                              on_click=self.do_load),
            ]))

        page.add(ft.Column(spacing=0, expand=True,
                           controls=[header, body, bottom]))
        self.add_question()
        page.update()

    # -------------------------------------------- أفعال
    def toggle_theme(self, e):
        self.page.theme_mode = (ft.ThemeMode.DARK
                                if self.page.theme_mode == ft.ThemeMode.LIGHT
                                else ft.ThemeMode.LIGHT)
        self.page.update()

    def add_question(self, data=None, update=False):
        c = QCard(self, data or paper.new_question())
        self.cards.append(c)
        self.qcol.controls.append(c.view)
        self.renumber()
        if update:
            self.page.update()

    def del_question(self, card):
        if len(self.cards) == 1:
            toast(self.page, "لازم يبقى سؤال واحد على الأقل.")
            return
        self.cards.remove(card)
        self.qcol.controls.remove(card.view)
        self.renumber()
        self.page.update()

    def renumber(self):
        for i, c in enumerate(self.cards):
            c.no.value = "السؤال /%d" % (i + 1)

    def collect(self):
        d = paper.new_paper()
        for k, w in self.f.items():
            d[k] = (w.value or "").strip()
        d["signature"] = bool(self.cb_sig.value)
        d["basmala"] = bool(self.cb_bism.value)
        d["separator"] = self.dd_sep.value
        d["gap"] = self.dd_gap.value
        d["font"] = self.dd_font.value
        d["size"] = int(self.dd_size.value)
        d["questions"] = [c.collect() for c in self.cards]
        return d

    def apply(self, d):
        for k, w in self.f.items():
            w.value = d.get(k, "") or ""
        self.cb_sig.value = bool(d.get("signature"))
        self.cb_bism.value = bool(d.get("basmala", True))
        self.dd_sep.value = d.get("separator", "dots")
        self.dd_gap.value = d.get("gap", "wide")
        self.dd_font.value = d.get("font", "traditional")
        self.dd_size.value = str(d.get("size", 15))
        self.cards = []
        self.qcol.controls.clear()
        for q in d.get("questions") or [paper.new_question()]:
            self.add_question(q)
        self.page.update()

    def do_print(self, e):
        try:
            html = paper.build_html(self.collect())
        except Exception as ex:
            show_report(self.page, "خطأ ببناء الورقة", repr(ex))
            return
        ok, info = deliver(self.page, html, "text/html;charset=utf-8",
                           "exam_paper.html", download=False)
        if ok:
            toast(self.page, "افتح قائمة المشاركة ← طباعة ← حفظ بصيغة PDF")
        else:
            show_report(self.page, "ما كدرت أفتح الورقة", info)

    def do_word(self, e):
        d = self.collect()
        name = (d.get("title") or "ورقة الأسئلة").replace("/", "-") + ".docx"
        try:
            data = word_export.build_docx_bytes(d)
        except Exception as ex:
            show_report(self.page, "خطأ ببناء ملف Word", repr(ex))
            return
        ok, info = deliver(
            self.page, data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            name, download=True)
        if ok:
            toast(self.page, "تم تنزيل ملف Word ✅")
        else:
            show_report(self.page, "ما كدرت أنزّل ملف Word", info)

    def do_save(self, e):
        try:
            self.page.client_storage.set(
                STORE_KEY, json.dumps(self.collect(), ensure_ascii=False))
            toast(self.page, "تم حفظ المشروع بالجهاز ✅")
        except Exception as ex:
            toast(self.page, "ما زبط الحفظ: %s" % ex)

    def do_load(self, e):
        try:
            raw = self.page.client_storage.get(STORE_KEY)
            if not raw:
                toast(self.page, "ما اكو مشروع محفوظ.")
                return
            base = paper.new_paper()
            base.update(json.loads(raw))
            self.apply(base)
            toast(self.page, "تم استرجاع المشروع ✅")
        except Exception as ex:
            toast(self.page, "ما زبط الاسترجاع: %s" % ex)


def main(page: ft.Page):
    MobileApp(page)


if __name__ == "__main__":
    try:
        ft.run(main)          # Flet الحديث
    except AttributeError:
        ft.app(target=main)   # Flet الأقدم
