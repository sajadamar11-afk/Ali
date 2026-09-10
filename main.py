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

BLUE = "#1e4d8c"
RED = "#c62828"
GREEN = "#2e7d32"
STORE_KEY = "exam_maker.project"


# ------------------------------------------------ فتح الورقة للطباعة
def open_paper(page, html):
    """
    يفتح الورقة بنافذة/تبويب جديد حتى يطبعها المستخدم (Ctrl+P أو مشاركة ← طباعة).
    يجرب ثلاث طرق حسب البيئة (متصفح / سطح مكتب / موبايل).
    """
    # 1) داخل المتصفح (نسخة flet build web تشتغل على Pyodide)
    try:
        import js  # متوفر فقط داخل المتصفح
        blob = js.Blob.new([html], {"type": "text/html;charset=utf-8"})
        url = js.URL.createObjectURL(blob)
        js.window.open(url, "_blank")
        return True, ""
    except Exception:
        pass

    # 2) سطح مكتب / خادم محلي
    try:
        import webbrowser
        folder = os.path.join(os.path.expanduser("~"), "exam_maker")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "exam_paper.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        webbrowser.open("file:///" + os.path.abspath(path).replace("\\", "/"))
        return True, path
    except Exception as e:
        return False, str(e)


def save_file(page, filename, data: bytes):
    """ينزّل ملف على الجهاز (متصفح) أو يحفظه بمجلد المستخدم (سطح مكتب)."""
    # 1) داخل المتصفح
    try:
        import js
        from pyodide.ffi import to_js
        arr = js.Uint8Array.new(len(data))
        for i, b in enumerate(data):
            arr[i] = b
        blob = js.Blob.new([arr], {"type": "application/octet-stream"})
        url = js.URL.createObjectURL(blob)
        a = js.document.createElement("a")
        a.href = url
        a.download = filename
        js.document.body.appendChild(a)
        a.click()
        js.document.body.removeChild(a)
        return True, filename
    except Exception:
        pass

    # 2) سطح مكتب
    try:
        folder = os.path.join(os.path.expanduser("~"), "exam_maker")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        with open(path, "wb") as f:
            f.write(data)
        return True, path
    except Exception as e:
        return False, str(e)


def toast(page, msg):
    sb = ft.SnackBar(content=ft.Text(msg, rtl=True), duration=2500)
    try:
        page.open(sb)               # Flet الحديث
    except Exception:
        page.snack_bar = sb
        page.snack_bar.open = True
        page.update()


# ------------------------------------------------ عناصر مساعدة
def tf(label, hint="", value="", multiline=False, lines=3, width=None):
    return ft.TextField(
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

        self.no = ft.Text("السؤال /1", weight=ft.FontWeight.BOLD,
                          size=16, color=BLUE, rtl=True)
        self.title = tf("عنوان السؤال", "مثال: أقسام الكلام", data.get("title", ""))
        self.total = tf("درجة السؤال", "20", str(data.get("total", "") or ""), width=120)
        self.text = tf("نص السؤال", "اكتب نص السؤال هنا...",
                       data.get("text", ""), multiline=True, lines=3)
        self.lines = ft.Dropdown(
            label="أسطر إجابة", width=120, dense=True, text_size=13,
            value=str(data.get("lines", 0) or 0),
            options=[ft.dropdown.Option(str(i)) for i in (0, 1, 2, 3, 4, 5, 6, 8, 10)])

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
                    ft.Text("الفروع:", size=12, color=Colors.GREY, rtl=True),
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

        self.dd_sep = ft.Dropdown(
            label="شكل الفاصل", dense=True, text_size=13, value="dots",
            options=[ft.dropdown.Option(k, v) for k, v in paper.SEPARATORS.items()])
        self.dd_gap = ft.Dropdown(
            label="التباعد بين الأسئلة", dense=True, text_size=13, value="wide",
            options=[ft.dropdown.Option(k, v) for k, v in paper.SPACING.items()])
        self.dd_font = ft.Dropdown(
            label="خط الورقة", dense=True, text_size=13, value="traditional",
            options=[ft.dropdown.Option(k, v) for k, v in paper.FONTS.items()])
        self.dd_size = ft.Dropdown(
            label="الحجم", dense=True, text_size=13, value="15", width=95,
            options=[ft.dropdown.Option(str(i)) for i in range(11, 23)])

        self.qcol = ft.Column(spacing=10, tight=True)

        header = ft.Container(
            bgcolor=BLUE, padding=ft.padding.symmetric(14, 16),
            content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("صانع النماذج الامتحانية", color="#fff",
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
                        ft.Text("الترويسة الرسمية للامتحان", size=16,
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
                ft.Container(padding=ft.padding.symmetric(0, 12), content=self.qcol),
                ft.Container(
                    padding=12,
                    content=ft.ElevatedButton(
                        "+  إضافة سؤال رئيسي جديد", bgcolor=GREEN, color="#fff",
                        height=46, width=10000,
                        on_click=lambda e: self.add_question(update=True))),
                ft.Container(height=90),
            ])

        bottom = ft.Container(
            bgcolor=Colors.with_opacity(.96, "#ffffff"),
            padding=10, border=ft.border.only(top=ft.BorderSide(1, "#dfe3e8")),
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
        html = paper.build_html(self.collect())
        ok, info = open_paper(self.page, html)
        toast(self.page, "افتح قائمة المشاركة ← طباعة ← حفظ بصيغة PDF"
              if ok else "ما زبطت المعاينة: %s" % info)

    def do_word(self, e):
        d = self.collect()
        name = (d.get("title") or "ورقة الأسئلة").replace("/", "-") + ".docx"
        try:
            data = word_export.build_docx_bytes(d)
        except Exception as ex:
            toast(self.page, "ما زبط التصدير: %s" % ex)
            return
        ok, info = save_file(self.page, name, data)
        toast(self.page, "تم تنزيل ملف Word ✅  (%s)" % info if ok
              else "ما زبط الحفظ: %s" % info)

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
    ft.app(target=main)
