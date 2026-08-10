"""BYC Üretim Planlama — Ana uygulama arayüzü."""

from __future__ import annotations

import random
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from config import (
    APP_TITLE,
    APP_VERSION,
    COLORS,
    DURUMLAR,
    TUM_MAKINELER,
    VARSAYILAN_KAPASITELER,
)
from scheduler import UretimCizelgeleyici
from storage import ayarlari_kaydet, ayarlari_yukle, siparisleri_kaydet, siparisleri_yukle

try:
    import customtkinter as ctk

    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False


def _font(size=10, weight="normal"):
    return ("Segoe UI", size, weight) if weight != "normal" else ("Segoe UI", size)


class ModernButton(tk.Button):
    """Tutarlı görünümlü düğme."""

    STYLES = {
        "primary": (COLORS["primary"], "#FFFFFF", COLORS["primary_hover"]),
        "success": (COLORS["success"], "#FFFFFF", "#059669"),
        "danger": (COLORS["danger"], "#FFFFFF", "#DC2626"),
        "dark": (COLORS["header"], "#FFFFFF", "#1E293B"),
        "muted": (COLORS["muted"], "#FFFFFF", "#475569"),
    }

    def __init__(
        self,
        master,
        text="",
        command=None,
        style="primary",
        font=None,
        padx=12,
        pady=6,
        **kw,
    ):
        bg, fg, hover = self.STYLES.get(style, self.STYLES["primary"])
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground="#FFFFFF",
            font=font or _font(9, "bold"),
            relief="flat",
            cursor="hand2",
            padx=padx,
            pady=pady,
            bd=0,
            **kw,
        )
        self._hover = hover
        self._bg = bg
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


class KpiCard(tk.Frame):
    """Üst özet kartı."""

    def __init__(self, master, baslik, renk_bg="#FFFFFF", renk_fg=None, **kw):
        super().__init__(
            master,
            bg=renk_bg,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=16,
            pady=10,
            **kw,
        )
        self.lbl_baslik = tk.Label(
            self,
            text=baslik,
            font=_font(8),
            bg=renk_bg,
            fg=COLORS["text_secondary"],
        )
        self.lbl_baslik.pack(anchor="w")
        self.lbl_deger = tk.Label(
            self,
            text="0",
            font=_font(18, "bold"),
            bg=renk_bg,
            fg=renk_fg or COLORS["text"],
        )
        self.lbl_deger.pack(anchor="w", pady=(2, 0))

    def guncelle(self, deger, alt_metin=None):
        self.lbl_deger.config(text=str(deger))
        if alt_metin:
            self.lbl_baslik.config(text=alt_metin)


class BYCPlanlamaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1680x980")
        self.minsize(1280, 720)
        self.configure(bg=COLORS["bg"])

        self.planlanan_isler: list = []
        self.gunluk_takvim: dict = {}
        self.cizelge_sonucu = None
        self.secili_is_id = None
        self.secilen_rota_sirasi: list = []
        self.chk_vars: dict = {}
        self.ent_ist_kapasiteler: dict = {}

        ayarlar = ayarlari_yukle()
        self.varsayilan_kapasiteler = ayarlar.get(
            "varsayilan_kapasiteler", dict(VARSAYILAN_KAPASITELER)
        )

        self._stil_ayarla()
        self._arayuz_olustur()
        self._verileri_yukle()
        self._durum_guncelle("Hazır")

    def _stil_ayarla(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure(
            "TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
            tabmargins=[8, 8, 0, 0],
        )
        self.style.configure(
            "TNotebook.Tab",
            font=_font(10, "bold"),
            padding=[20, 10],
            background=COLORS["tab_inactive"],
            foreground=COLORS["text"],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["header"])],
            foreground=[("selected", "#FFFFFF")],
        )
        self.style.configure(
            "Treeview",
            font=_font(9),
            rowheight=32,
            background=COLORS["card"],
            fieldbackground=COLORS["card"],
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            font=_font(10, "bold"),
            background=COLORS["header"],
            foreground="#FFFFFF",
            relief="flat",
        )
        self.style.map("Treeview.Heading", background=[("active", COLORS["primary"])])
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=COLORS["border"],
            background=COLORS["success"],
            thickness=14,
        )
        self.style.configure(
            "Warning.Horizontal.TProgressbar",
            troughcolor=COLORS["border"],
            background=COLORS["warning"],
            thickness=14,
        )
        self.style.configure(
            "Danger.Horizontal.TProgressbar",
            troughcolor=COLORS["border"],
            background=COLORS["danger"],
            thickness=14,
        )

    def _arayuz_olustur(self):
        self._header_olustur()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))

        self.tab_siparis = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.tab_analiz = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.tab_pano = tk.Frame(self.notebook, bg=COLORS["bg"])

        self.notebook.add(self.tab_siparis, text="  📝 Sipariş Yönetimi  ")
        self.notebook.add(self.tab_analiz, text="  📊 Çizelgeleme & Dar Boğaz  ")
        self.notebook.add(self.tab_pano, text="  ⚙️ Pano & Ayarlar  ")

        self._siparis_sekmesi()
        self._analiz_sekmesi()
        self._pano_sekmesi()
        self._status_bar()

    def _header_olustur(self):
        header = tk.Frame(self, bg=COLORS["header"], height=72)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        sol = tk.Frame(header, bg=COLORS["header"])
        sol.pack(side=tk.LEFT, padx=24, pady=14)

        tk.Label(
            sol,
            text="BYC Dinamik Üretim Planlama",
            font=_font(17, "bold"),
            fg="#FFFFFF",
            bg=COLORS["header"],
        ).pack(anchor="w")
        tk.Label(
            sol,
            text="Sipariş havuzu · istasyon hızları · dar boğaz analizi",
            font=_font(9),
            fg=COLORS["header_sub"],
            bg=COLORS["header"],
        ).pack(anchor="w")

        sag = tk.Frame(header, bg=COLORS["header"])
        sag.pack(side=tk.RIGHT, padx=24, pady=14)
        tk.Label(
            sag,
            text=f"v{APP_VERSION}",
            font=_font(9, "bold"),
            fg=COLORS["header_sub"],
            bg="#1E293B",
            padx=10,
            pady=4,
        ).pack()

    def _status_bar(self):
        bar = tk.Frame(self, bg=COLORS["header"], height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        self.lbl_durum = tk.Label(
            bar,
            text="",
            font=_font(8),
            fg=COLORS["header_sub"],
            bg=COLORS["header"],
            anchor="w",
            padx=16,
        )
        self.lbl_durum.pack(fill=tk.X)

    def _durum_guncelle(self, mesaj: str):
        zaman = datetime.now().strftime("%H:%M:%S")
        self.lbl_durum.config(text=f"  {zaman}  ·  {mesaj}")

    def _siparis_sekmesi(self):
        kpi_frame = tk.Frame(self.tab_siparis, bg=COLORS["bg"])
        kpi_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.kpi_toplam = KpiCard(kpi_frame, "Toplam Sipariş")
        self.kpi_toplam.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self.kpi_uretimde = KpiCard(
            kpi_frame, "Üretimde", COLORS["warning_bg"], COLORS["warning_fg"]
        )
        self.kpi_uretimde.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self.kpi_tamamlanan = KpiCard(
            kpi_frame, "Tamamlanan", COLORS["success_bg"], COLORS["success_fg"]
        )
        self.kpi_tamamlanan.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self.kpi_acil = KpiCard(
            kpi_frame, "Acil Sipariş", COLORS["danger_bg"], COLORS["danger_fg"]
        )
        self.kpi_acil.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        govde = tk.Frame(self.tab_siparis, bg=COLORS["bg"])
        govde.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._form_paneli(govde)
        self._tablo_paneli(govde)

    def _form_paneli(self, parent):
        cerceve = tk.LabelFrame(
            parent,
            text="  Sipariş Bilgileri & İstasyon Hızları  ",
            font=_font(10, "bold"),
            bg=COLORS["card"],
            fg=COLORS["text"],
            padx=12,
            pady=10,
            labelanchor="n",
        )
        cerceve.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 6), pady=4)

        canvas = tk.Canvas(cerceve, bg=COLORS["card"], highlightthickness=0, width=420)
        scroll = ttk.Scrollbar(cerceve, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=COLORS["card"])
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        satir = 0
        for etiket, attr in [
            ("Müşteri / Firma:", "ent_musteri"),
            ("Ürün Kodu:", "ent_urun"),
            ("Ölçü (mm):", "ent_olcu"),
            ("Toplam Adet:", "ent_adet"),
            ("Sevk Edilen Adet:", "ent_hazir_adet"),
            ("Sevk Hedefi (GG.AA.YYYY):", "ent_sevk_hedefi"),
        ]:
            tk.Label(form, text=etiket, font=_font(9, "bold"), bg=COLORS["card"]).grid(
                row=satir, column=0, sticky="w", pady=5, padx=(0, 8)
            )
            entry = ttk.Entry(form, width=34)
            entry.grid(row=satir, column=1, pady=5, sticky="w")
            setattr(self, attr, entry)
            satir += 1

        self.ent_hazir_adet.insert(0, "0")
        self.ent_sevk_hedefi.insert(0, datetime.now().strftime("%d.%m.%Y"))

        tk.Label(form, text="Öncelik:", font=_font(9, "bold"), bg=COLORS["card"]).grid(
            row=satir, column=0, sticky="w", pady=5
        )
        self.cmb_oncelik = ttk.Combobox(
            form, values=["Acil", "Normal", "Düşük"], width=31, state="readonly"
        )
        self.cmb_oncelik.set("Normal")
        self.cmb_oncelik.grid(row=satir, column=1, pady=5, sticky="w")
        satir += 1

        tk.Label(form, text="Durum:", font=_font(9, "bold"), bg=COLORS["card"]).grid(
            row=satir, column=0, sticky="w", pady=5
        )
        self.cmb_durum = ttk.Combobox(
            form, values=DURUMLAR, width=31, state="readonly"
        )
        self.cmb_durum.set("Beklemede")
        self.cmb_durum.grid(row=satir, column=1, pady=5, sticky="w")
        satir += 1

        # Parçalı sevk
        sevk_frame = tk.LabelFrame(
            form,
            text="  📦 Hızlı Parçalı Sevk  ",
            font=_font(8, "bold"),
            bg="#F8FAFC",
            fg=COLORS["success"],
            padx=8,
            pady=6,
        )
        sevk_frame.grid(row=satir, column=0, columnspan=2, sticky="ew", pady=8)
        satir += 1

        self.ent_parcali_sevk = ttk.Entry(sevk_frame, width=10)
        self.ent_parcali_sevk.pack(side=tk.LEFT, padx=4)
        ModernButton(
            sevk_frame, text="Sevk Et", style="success", command=self.parcali_sevk_yap
        ).pack(side=tk.LEFT, padx=4)

        tk.Label(
            form,
            text="Proses Rotası — Günlük Hız (Adet/Gün):",
            font=_font(9, "bold"),
            bg=COLORS["card"],
            fg=COLORS["accent_orange"],
        ).grid(row=satir, column=0, columnspan=2, sticky="w", pady=(10, 4))
        satir += 1

        rota_frame = tk.Frame(
            form, bg="#F8FAFC", padx=8, pady=8,
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        rota_frame.grid(row=satir, column=0, columnspan=2, sticky="ew")
        satir += 1

        r, c = 0, 0
        for m in TUM_MAKINELER:
            self.chk_vars[m] = tk.BooleanVar()
            tk.Checkbutton(
                rota_frame,
                text=m,
                variable=self.chk_vars[m],
                bg="#F8FAFC",
                activebackground="#F8FAFC",
                font=_font(8, "bold"),
                command=self.rota_tiklama_tetikleyici,
                width=14,
                anchor="w",
            ).grid(row=r, column=c, sticky="w", padx=2, pady=3)

            ent = ttk.Entry(rota_frame, width=7, font=_font(8))
            ent.insert(0, str(self.varsayilan_kapasiteler.get(m, 500)))
            ent.grid(row=r, column=c + 1, sticky="w", padx=(0, 12), pady=3)
            self.ent_ist_kapasiteler[m] = ent

            c += 2
            if c > 3:
                c = 0
                r += 1

        btn_rota = tk.Frame(form, bg=COLORS["card"])
        btn_rota.grid(row=satir, column=0, columnspan=2, pady=4, sticky="w")
        satir += 1
        ModernButton(btn_rota, text="Tümünü Seç", style="muted", command=self.tum_rotalari_sec).pack(
            side=tk.LEFT, padx=2
        )
        ModernButton(
            btn_rota, text="Temizle", style="muted", command=self.tum_rotalari_temizle
        ).pack(side=tk.LEFT, padx=2)

        self.lbl_canli_rota = tk.Label(
            form,
            text="Seçilen Rota: Boş",
            font=_font(8, "italic"),
            fg=COLORS["danger"],
            bg=COLORS["card"],
            wraplength=380,
            justify="left",
        )
        self.lbl_canli_rota.grid(row=satir, column=0, columnspan=2, pady=4, sticky="w")
        satir += 1

        btn_frame = tk.Frame(form, bg=COLORS["card"])
        btn_frame.grid(row=satir, column=0, columnspan=2, pady=12, sticky="ew")
        ModernButton(
            btn_frame, text="💾 Kaydet / Güncelle", style="success",
            command=self.siparis_ekle_guncelle,
        ).pack(side=tk.LEFT, padx=3, fill=tk.X, expand=True)
        ModernButton(
            btn_frame, text="🗑 Sil", style="danger", command=self.siparis_sil
        ).pack(side=tk.LEFT, padx=3, fill=tk.X, expand=True)
        ModernButton(
            btn_frame, text="Temizle", style="muted", command=self.formu_temizle
        ).pack(side=tk.LEFT, padx=3)

    def _tablo_paneli(self, parent):
        sag = tk.Frame(parent, bg=COLORS["bg"])
        sag.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=4)

        arama = tk.Frame(sag, bg=COLORS["card"], padx=10, pady=8,
                         highlightbackground=COLORS["border"], highlightthickness=1)
        arama.pack(fill=tk.X, pady=(0, 8))

        tk.Label(arama, text="🔍", bg=COLORS["card"], font=_font(11)).pack(side=tk.LEFT)
        self.ent_arama = ttk.Entry(arama, width=22)
        self.ent_arama.pack(side=tk.LEFT, padx=6)
        self.ent_arama.bind("<KeyRelease>", lambda e: self.tabloyu_doldur())

        tk.Label(arama, text="Durum:", font=_font(9, "bold"), bg=COLORS["card"]).pack(
            side=tk.LEFT, padx=(12, 4)
        )
        self.cmb_filtre_durum = ttk.Combobox(
            arama,
            values=["Tümü"] + DURUMLAR,
            width=12,
            state="readonly",
        )
        self.cmb_filtre_durum.set("Tümü")
        self.cmb_filtre_durum.pack(side=tk.LEFT)
        self.cmb_filtre_durum.bind("<<ComboboxSelected>>", lambda e: self.tabloyu_doldur())

        tree_frame = tk.Frame(sag, bg=COLORS["card"],
                              highlightbackground=COLORS["border"], highlightthickness=1)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "bitis", "musteri", "urun", "olcu", "rotalar", "adet", "hazir", "kalan", "oncelik", "durum")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        basliklar = {
            "id": ("ID", 70), "bitis": ("Sevk", 90), "musteri": ("Müşteri", 110),
            "urun": ("Ürün", 90), "olcu": ("Ölçü", 80), "rotalar": ("Rota", 160),
            "adet": ("Toplam", 60), "hazir": ("Sevk", 55), "kalan": ("Kalan", 55),
            "oncelik": ("Öncelik", 65), "durum": ("Durum", 85),
        }
        for col, (text, w) in basliklar.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="center")

        for durum, bg, fg in [
            ("Beklemede", "#FFFFFF", COLORS["text"]),
            ("Üretimde", COLORS["warning_bg"], COLORS["warning_fg"]),
            ("Durduruldu", COLORS["danger_bg"], COLORS["danger_fg"]),
            ("Tamamlandı", COLORS["success_bg"], COLORS["success_fg"]),
        ]:
            self.tree.tag_configure(durum, background=bg, foreground=fg)
        self.tree.tag_configure("Acil", background="#FEE2E2")

        self.tree.bind("<<TreeviewSelect>>", self.tablodan_is_sec)
        self.tree.bind("<Double-1>", lambda e: self.notebook.select(self.tab_siparis))

        alt = tk.Frame(sag, bg=COLORS["bg"])
        alt.pack(fill=tk.X, pady=(8, 0))
        ModernButton(alt, text="📥 Excel'den Al", style="primary", command=self.dosyadan_siparis_aktar).pack(
            side=tk.LEFT, padx=3
        )
        ModernButton(
            alt, text="📤 Excel'e Aktar", style="dark", command=self.siparis_listesi_excel_aktar
        ).pack(side=tk.LEFT, padx=3)
        ModernButton(
            alt, text="⚠ Havuzu Sıfırla", style="danger", command=self.listeyi_sifirla
        ).pack(side=tk.RIGHT, padx=3)

    def _analiz_sekmesi(self):
        ust = tk.Frame(self.tab_analiz, bg=COLORS["bg"])
        ust.pack(fill=tk.X, padx=8, pady=10)

        ModernButton(
            ust,
            text="⚡ Akıllı Gün Dağıtımını Çalıştır",
            style="primary",
            command=self.akilli_gun_dagitimi_yap,
            font=_font(11, "bold"),
            padx=18,
            pady=8,
        ).pack(side=tk.LEFT)
        ModernButton(
            ust,
            text="📑 Çizelgeyi Excel'e Aktar",
            style="dark",
            command=self.gunluk_cizelge_excel_aktar,
        ).pack(side=tk.LEFT, padx=10)

        self.lbl_dar_bogaz_kpi = tk.Label(
            ust,
            text="🚨 Dar Boğaz: 0",
            font=_font(10, "bold"),
            bg=COLORS["danger_bg"],
            fg=COLORS["danger_fg"],
            padx=16,
            pady=8,
            highlightbackground=COLORS["danger"],
            highlightthickness=1,
        )
        self.lbl_dar_bogaz_kpi.pack(side=tk.RIGHT)

        govde = tk.Frame(self.tab_analiz, bg=COLORS["bg"])
        govde.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        gun_frame = tk.LabelFrame(
            govde, text="  Planlanan Günler  ", font=_font(10, "bold"),
            bg=COLORS["card"], fg=COLORS["text"], padx=8, pady=8,
        )
        gun_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        self.list_gunler = tk.Listbox(
            gun_frame, width=30, font=_font(10), bd=0,
            highlightthickness=1, highlightcolor=COLORS["primary"],
            selectbackground=COLORS["header"], selectforeground="#FFFFFF",
            activestyle="none",
        )
        self.list_gunler.pack(fill=tk.BOTH, expand=True)
        self.list_gunler.bind("<<ListboxSelect>>", self.gunluk_plan_goster)

        sag = tk.Frame(govde, bg=COLORS["bg"])
        sag.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        doluluk_frame = tk.LabelFrame(
            sag, text="  Günlük İstasyon Doluluk Özeti  ", font=_font(10, "bold"),
            bg=COLORS["card"], fg=COLORS["text"], padx=10, pady=8,
        )
        doluluk_frame.pack(fill=tk.X, pady=(0, 8))
        self.frame_doluluk = tk.Frame(doluluk_frame, bg=COLORS["card"])
        self.frame_doluluk.pack(fill=tk.X)

        detay_frame = tk.LabelFrame(
            sag, text="  Gün Detayı — İş Listesi  ", font=_font(10, "bold"),
            bg=COLORS["card"], fg=COLORS["text"], padx=8, pady=8,
        )
        detay_frame.pack(fill=tk.BOTH, expand=True)

        takvim_cols = ("makine", "musteri", "urun", "adet", "hiz", "yuk", "doluluk", "oncelik")
        self.tree_takvim = ttk.Treeview(detay_frame, columns=takvim_cols, show="headings")
        self.tree_takvim.pack(fill=tk.BOTH, expand=True)

        for col, text in [
            ("makine", "İstasyon"), ("musteri", "Müşteri"), ("urun", "Ürün"),
            ("adet", "Adet"), ("hiz", "Hız"), ("yuk", "Durum"),
            ("doluluk", "Doluluk"), ("oncelik", "Öncelik"),
        ]:
            self.tree_takvim.heading(col, text=text)
            self.tree_takvim.column(col, width=110, anchor="center")

        for tag, bg, fg in [
            ("normal", "#F0FDF4", "#166534"),
            ("Normal", "#F0FDF4", "#166534"),
            ("yogun", COLORS["warning_bg"], COLORS["warning_fg"]),
            ("Kritik", COLORS["warning_bg"], COLORS["warning_fg"]),
            ("sevk_gecikti", COLORS["danger_bg"], COLORS["danger_fg"]),
            ("kapasite", "#FFF7ED", "#C2410C"),
            ("DarBogaz", COLORS["danger_bg"], COLORS["danger_fg"]),
        ]:
            self.tree_takvim.tag_configure(tag, background=bg, foreground=fg)

        self.lbl_uyarilar = tk.Label(
            sag, text="", font=_font(8), fg=COLORS["danger"],
            bg=COLORS["bg"], wraplength=900, justify="left",
        )
        self.lbl_uyarilar.pack(fill=tk.X, pady=(6, 0))

    def _pano_sekmesi(self):
        pano = tk.Frame(self.tab_pano, bg=COLORS["bg"])
        pano.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        tk.Label(
            pano, text="Fabrika Özet Pano", font=_font(16, "bold"),
            bg=COLORS["bg"], fg=COLORS["text"],
        ).pack(anchor="w", pady=(0, 12))

        ozet_frame = tk.Frame(pano, bg=COLORS["bg"])
        ozet_frame.pack(fill=tk.X, pady=(0, 16))

        self.pano_kartlar = {}
        for baslik, key in [
            ("Toplam Kalan Adet", "kalan"),
            ("Aktif Sipariş", "aktif"),
            ("Ortalama Doluluk", "doluluk"),
            ("Planlanan Gün", "gun"),
        ]:
            kart = KpiCard(ozet_frame, baslik)
            kart.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
            self.pano_kartlar[key] = kart

        ModernButton(
            pano, text="🔄 Panoyu Yenile", style="primary", command=self.pano_yenile
        ).pack(anchor="w", pady=(0, 16))

        ayar_frame = tk.LabelFrame(
            pano, text="  Varsayılan İstasyon Kapasiteleri (Adet/Gün)  ",
            font=_font(10, "bold"), bg=COLORS["card"], fg=COLORS["text"],
            padx=12, pady=12,
        )
        ayar_frame.pack(fill=tk.BOTH, expand=True)

        self.ent_varsayilan_kap: dict = {}
        grid = tk.Frame(ayar_frame, bg=COLORS["card"])
        grid.pack(fill=tk.BOTH, expand=True)

        for i, m in enumerate(TUM_MAKINELER):
            r, c = divmod(i, 3)
            tk.Label(grid, text=m, font=_font(9), bg=COLORS["card"]).grid(
                row=r, column=c * 2, sticky="w", padx=(0, 6), pady=4
            )
            ent = ttk.Entry(grid, width=8)
            ent.insert(0, str(self.varsayilan_kapasiteler.get(m, 500)))
            ent.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 20), pady=4)
            self.ent_varsayilan_kap[m] = ent

        ModernButton(
            ayar_frame, text="💾 Ayarları Kaydet", style="success",
            command=self.ayarlari_kaydet_ui,
        ).pack(pady=(12, 0))

    # ── İş mantığı ──────────────────────────────────────────────

    def _verileri_yukle(self):
        self.planlanan_isler = siparisleri_yukle()
        self.tabloyu_doldur()

    def _kaydet(self):
        siparisleri_kaydet(self.planlanan_isler)
        self._durum_guncelle("Veriler kaydedildi")

    def rota_tiklama_tetikleyici(self):
        self.secilen_rota_sirasi = [m for m in TUM_MAKINELER if self.chk_vars[m].get()]
        self.canli_rota_etiketini_guncelle()

    def canli_rota_etiketini_guncelle(self):
        if self.secilen_rota_sirasi:
            self.lbl_canli_rota.config(
                text="Seçilen Rota: " + "  →  ".join(self.secilen_rota_sirasi),
                fg=COLORS["success"],
            )
        else:
            self.lbl_canli_rota.config(
                text="Seçilen Rota: Boş — en az bir istasyon seçin",
                fg=COLORS["danger"],
            )

    def tum_rotalari_sec(self):
        for m in TUM_MAKINELER:
            self.chk_vars[m].set(True)
        self.rota_tiklama_tetikleyici()

    def tum_rotalari_temizle(self):
        for m in TUM_MAKINELER:
            self.chk_vars[m].set(False)
        self.rota_tiklama_tetikleyici()

    def kpi_guncelle(self):
        toplam = len(self.planlanan_isler)
        uretimde = sum(1 for x in self.planlanan_isler if x.get("durum") == "Üretimde")
        tamamlanan = sum(1 for x in self.planlanan_isler if x.get("durum") == "Tamamlandı")
        acil = sum(1 for x in self.planlanan_isler if x.get("oncelik") == "Acil" and x.get("durum") != "Tamamlandı")

        self.kpi_toplam.guncelle(toplam)
        self.kpi_uretimde.guncelle(uretimde)
        self.kpi_tamamlanan.guncelle(tamamlanan)
        self.kpi_acil.guncelle(acil)

    def tablodan_is_sec(self, _event=None):
        secim = self.tree.selection()
        if not secim:
            return
        vals = self.tree.item(secim[0], "values")
        self.secili_is_id = vals[0]
        sip = next((x for x in self.planlanan_isler if str(x["id"]) == str(self.secili_is_id)), None)
        if not sip:
            return

        alanlar = [
            ("ent_musteri", "musteri"), ("ent_urun", "urun"), ("ent_olcu", "olcu"),
            ("ent_adet", "adet"), ("ent_hazir_adet", "hazir_adet"), ("ent_sevk_hedefi", "bitis"),
        ]
        for ent_adi, anahtar in alanlar:
            ent = getattr(self, ent_adi)
            ent.delete(0, tk.END)
            ent.insert(0, sip.get(anahtar, ""))

        self.cmb_durum.set(sip.get("durum", "Beklemede"))
        self.cmb_oncelik.set(sip.get("oncelik", "Normal"))

        self.secilen_rota_sirasi = [
            x.strip() for x in sip.get("rotalar", "").split(",") if x.strip()
        ]
        kap_dict = sip.get("istasyon_kapasiteleri", {})
        for m in TUM_MAKINELER:
            self.chk_vars[m].set(m in self.secilen_rota_sirasi)
            self.ent_ist_kapasiteler[m].delete(0, tk.END)
            self.ent_ist_kapasiteler[m].insert(
                0, str(kap_dict.get(m, self.varsayilan_kapasiteler.get(m, 500)))
            )
        self.canli_rota_etiketini_guncelle()

    def siparis_ekle_guncelle(self):
        m = self.ent_musteri.get().strip()
        u = self.ent_urun.get().strip().upper()
        olcu = self.ent_olcu.get().strip()
        a = self.ent_adet.get().strip()
        h_a = self.ent_hazir_adet.get().strip()
        hedef = self.ent_sevk_hedefi.get().strip()

        if not m or not u or not a.isdigit() or not h_a.isdigit():
            messagebox.showerror("Hata", "Firma adı, ürün kodu ve sayısal adet alanları zorunludur.")
            return
        try:
            datetime.strptime(hedef, "%d.%m.%Y")
        except ValueError:
            messagebox.showerror("Tarih Hatası", "Sevk tarihi GG.AA.YYYY formatında olmalıdır.")
            return
        if not self.secilen_rota_sirasi:
            messagebox.showwarning("Rota Eksik", "En az bir proses istasyonu seçin.")
            return

        istasyon_kap = {}
        for makine in self.secilen_rota_sirasi:
            val = self.ent_ist_kapasiteler[makine].get().strip()
            if not val.isdigit() or int(val) <= 0:
                messagebox.showerror("Kapasite Hatası", f"{makine} için geçerli bir adet/gün girin.")
                return
            istasyon_kap[makine] = int(val)

        veri = {
            "musteri": m, "urun": u, "olcu": olcu, "adet": a,
            "istasyon_kapasiteleri": istasyon_kap,
            "hazir_adet": h_a, "bitis": hedef,
            "durum": self.cmb_durum.get(),
            "oncelik": self.cmb_oncelik.get(),
            "rotalar": ", ".join(self.secilen_rota_sirasi),
        }

        if self.secili_is_id:
            sip = next((x for x in self.planlanan_isler if str(x["id"]) == str(self.secili_is_id)), None)
            if sip:
                sip.update(veri)
        else:
            yeni_id = datetime.now().strftime("%d%m%Y%H%M%S") + str(random.randint(100, 999))
            veri["id"] = yeni_id
            self.planlanan_isler.append(veri)

        self._kaydet()
        self.tabloyu_doldur()
        self.formu_temizle()
        messagebox.showinfo("Başarılı", "Sipariş kaydedildi.")

    def parcali_sevk_yap(self):
        if not self.secili_is_id:
            messagebox.showwarning("Seçim Yok", "Tablodan bir sipariş seçin.")
            return
        giris = self.ent_parcali_sevk.get().strip()
        if not giris.isdigit() or int(giris) <= 0:
            messagebox.showerror("Hata", "Geçerli bir sevk adedi girin.")
            return

        adet = int(giris)
        sip = next((x for x in self.planlanan_isler if str(x["id"]) == str(self.secili_is_id)), None)
        if not sip:
            return

        toplam = int(sip["adet"])
        mevcut = int(sip.get("hazir_adet", "0"))
        kalan = max(0, toplam - mevcut)
        if adet > kalan:
            messagebox.showerror("Aşım", f"En fazla {kalan} adet sevk edilebilir.")
            return

        yeni = mevcut + adet
        sip["hazir_adet"] = str(yeni)
        sip["durum"] = "Tamamlandı" if yeni >= toplam else "Üretimde"

        self._kaydet()
        self.tabloyu_doldur()
        self.ent_hazir_adet.delete(0, tk.END)
        self.ent_hazir_adet.insert(0, str(yeni))
        self.cmb_durum.set(sip["durum"])
        self.ent_parcali_sevk.delete(0, tk.END)
        messagebox.showinfo("Sevk", f"{adet} adet sevk edildi. Toplam: {yeni} / Kalan: {toplam - yeni}")

    def siparis_sil(self):
        if not self.secili_is_id:
            messagebox.showwarning("Seçim Yok", "Silinecek siparişi tablodan seçin.")
            return
        if messagebox.askyesno("Onay", "Seçili sipariş silinsin mi?"):
            self.planlanan_isler = [x for x in self.planlanan_isler if str(x["id"]) != str(self.secili_is_id)]
            self._kaydet()
            self.tabloyu_doldur()
            self.formu_temizle()

    def listeyi_sifirla(self):
        if messagebox.askyesno("Onay", "Tüm sipariş havuzu silinsin mi?"):
            self.planlanan_isler = []
            self._kaydet()
            self.tabloyu_doldur()

    def formu_temizle(self):
        self.secili_is_id = None
        for ent in [self.ent_musteri, self.ent_urun, self.ent_olcu, self.ent_adet,
                    self.ent_parcali_sevk]:
            ent.delete(0, tk.END)
        self.ent_hazir_adet.delete(0, tk.END)
        self.ent_hazir_adet.insert(0, "0")
        self.ent_sevk_hedefi.delete(0, tk.END)
        self.ent_sevk_hedefi.insert(0, datetime.now().strftime("%d.%m.%Y"))
        self.cmb_durum.set("Beklemede")
        self.cmb_oncelik.set("Normal")
        for m in TUM_MAKINELER:
            self.chk_vars[m].set(False)
            self.ent_ist_kapasiteler[m].delete(0, tk.END)
            self.ent_ist_kapasiteler[m].insert(0, str(self.varsayilan_kapasiteler.get(m, 500)))
        self.canli_rota_etiketini_guncelle()

    def tabloyu_doldur(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        arama = self.ent_arama.get().strip().lower() if hasattr(self, "ent_arama") else ""
        filtre = self.cmb_filtre_durum.get() if hasattr(self, "cmb_filtre_durum") else "Tümü"

        for sip in self.planlanan_isler:
            durum = sip.get("durum", "Beklemede")
            if filtre != "Tümü" and durum != filtre:
                continue
            metin = f"{sip['musteri']} {sip['urun']} {sip.get('olcu', '')}".lower()
            if arama and arama not in metin:
                continue

            tot = int(sip["adet"])
            hzr = int(sip.get("hazir_adet", "0"))
            tag = ("Acil",) if sip.get("oncelik") == "Acil" and durum != "Tamamlandı" else (durum,)

            self.tree.insert(
                "", tk.END,
                values=(
                    sip["id"], sip.get("bitis", ""), sip["musteri"], sip["urun"],
                    sip.get("olcu", "-"), sip.get("rotalar", ""), tot, hzr,
                    max(0, tot - hzr), sip.get("oncelik", "Normal"), durum,
                ),
                tags=tag,
            )
        self.kpi_guncelle()

    def akilli_gun_dagitimi_yap(self):
        cizelgeleyici = UretimCizelgeleyici(self.varsayilan_kapasiteler)
        sonuc = cizelgeleyici.calistir(self.planlanan_isler)
        self.cizelge_sonucu = sonuc
        self.gunluk_takvim = sonuc.gunluk_takvim

        self.list_gunler.delete(0, tk.END)
        for g in sorted(self.gunluk_takvim.keys(), key=UretimCizelgeleyici.gun_sirala):
            kayit_sayisi = len(self.gunluk_takvim[g])
            dar = sum(
                1
                for k in self.gunluk_takvim[g]
                if k.tag in ("sevk_gecikti", "kapasite", "DarBogaz")
            )
            etiket = f"{g}  ({kayit_sayisi} iş" + (f", {dar} sorun)" if dar else ")")
            self.list_gunler.insert(tk.END, etiket)

        self.lbl_dar_bogaz_kpi.config(text=f"⚠ Sorun: {sonuc.dar_bogaz_sayisi}")
        if sonuc.uyarilar:
            self.lbl_uyarilar.config(text="⚠ " + " | ".join(sonuc.uyarilar[:5]))
        else:
            self.lbl_uyarilar.config(text="")

        self.notebook.select(self.tab_analiz)
        self.pano_yenile()
        self._durum_guncelle(f"Çizelgeleme tamamlandı — {sonuc.dar_bogaz_sayisi} sorun")

        if sonuc.dar_bogaz_sayisi:
            messagebox.showwarning(
                "Çizelge Uyarısı",
                f"{sonuc.dar_bogaz_sayisi} işlemde sevk gecikmesi veya kapasite yetersizliği tespit edildi.",
            )
        else:
            messagebox.showinfo("Başarılı", "Çizelgeleme tamamlandı. Sevk/kapasite sorunu yok.")

    def _doluluk_cubuklari_goster(self, gun_str: str):
        for w in self.frame_doluluk.winfo_children():
            w.destroy()
        if not self.cizelge_sonucu:
            return

        ozet = self.cizelge_sonucu.gun_ozeti(gun_str)
        if not ozet:
            tk.Label(
                self.frame_doluluk, text="Bu gün için yük yok.",
                bg=COLORS["card"], fg=COLORS["text_secondary"],
            ).pack(anchor="w")
            return

        for makine, yuzde in sorted(ozet.items(), key=lambda x: -x[1]):
            satir = tk.Frame(self.frame_doluluk, bg=COLORS["card"])
            satir.pack(fill=tk.X, pady=2)
            tk.Label(satir, text=makine, width=18, anchor="w", font=_font(8, "bold"),
                     bg=COLORS["card"]).pack(side=tk.LEFT)
            stil = (
                "Danger.Horizontal.TProgressbar" if yuzde >= 100
                else "Warning.Horizontal.TProgressbar" if yuzde >= 85
                else "Horizontal.TProgressbar"
            )
            pb = ttk.Progressbar(satir, length=280, mode="determinate", style=stil)
            pb["value"] = min(100, yuzde)
            pb.pack(side=tk.LEFT, padx=6)
            tk.Label(satir, text=f"%{yuzde}", width=6, font=_font(8, "bold"),
                     bg=COLORS["card"]).pack(side=tk.LEFT)

    def gunluk_plan_goster(self, _event=None):
        for row in self.tree_takvim.get_children():
            self.tree_takvim.delete(row)

        secim = self.list_gunler.curselection()
        if not secim:
            return

        satir = self.list_gunler.get(secim[0])
        gun_str = satir.split("  (")[0]

        for kayit in self.gunluk_takvim.get(gun_str, []):
            self.tree_takvim.insert(
                "", tk.END,
                values=(
                    kayit.makine, kayit.musteri, kayit.urun, kayit.adet,
                    kayit.hiz, kayit.yuk, kayit.doluluk, kayit.oncelik,
                ),
                tags=(kayit.tag,),
            )
        self._doluluk_cubuklari_goster(gun_str)

    def pano_yenile(self):
        kalan_toplam = sum(
            max(0, int(s["adet"]) - int(s.get("hazir_adet", "0")))
            for s in self.planlanan_isler if s.get("durum") != "Tamamlandı"
        )
        aktif = sum(1 for s in self.planlanan_isler if s.get("durum") in ("Beklemede", "Üretimde"))
        gun_sayisi = len(self.gunluk_takvim)

        ort_doluluk = 0.0
        if self.cizelge_sonucu and self.cizelge_sonucu.istasyon_yukleri:
            tum = []
            for gun, yukler in self.cizelge_sonucu.istasyon_yukleri.items():
                for m, y in yukler.items():
                    if y > 0:
                        kap = self.varsayilan_kapasiteler.get(m, 500)
                        tum.append(min(100, (y / kap) * 100))
            ort_doluluk = round(sum(tum) / len(tum), 1) if tum else 0

        self.pano_kartlar["kalan"].guncelle(kalan_toplam)
        self.pano_kartlar["aktif"].guncelle(aktif)
        self.pano_kartlar["doluluk"].guncelle(f"%{ort_doluluk}")
        self.pano_kartlar["gun"].guncelle(gun_sayisi)

    def ayarlari_kaydet_ui(self):
        yeni = {}
        for m, ent in self.ent_varsayilan_kap.items():
            val = ent.get().strip()
            if not val.isdigit() or int(val) <= 0:
                messagebox.showerror("Hata", f"{m} için geçerli kapasite girin.")
                return
            yeni[m] = int(val)
        self.varsayilan_kapasiteler = yeni
        ayarlari_kaydet({"varsayilan_kapasiteler": yeni})
        for m in TUM_MAKINELER:
            if m in self.ent_ist_kapasiteler:
                if not self.chk_vars[m].get():
                    self.ent_ist_kapasiteler[m].delete(0, tk.END)
                    self.ent_ist_kapasiteler[m].insert(0, str(yeni.get(m, 500)))
        messagebox.showinfo("Ayarlar", "Varsayılan kapasiteler kaydedildi.")
        self._durum_guncelle("Ayarlar güncellendi")

    def gunluk_cizelge_excel_aktar(self):
        if not self.gunluk_takvim:
            messagebox.showwarning("Uyarı", "Önce çizelgeleme çalıştırın.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        rows = []
        for gun, kayitlar in self.gunluk_takvim.items():
            for k in kayitlar:
                rows.append({
                    "Tarih": gun, "İstasyon": k.makine, "Müşteri": k.musteri,
                    "Ürün": k.urun, "Adet": k.adet, "Hız": k.hiz,
                    "Durum": k.yuk, "Doluluk": k.doluluk, "Öncelik": k.oncelik,
                })
        pd.DataFrame(rows).to_excel(path, index=False)
        messagebox.showinfo("Başarılı", "Çizelge Excel'e aktarıldı.")

    def dosyadan_siparis_aktar(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if not path:
            return
        try:
            df = pd.read_excel(path)
            ts = datetime.now().strftime("%d%m%Y%H%M%S")
            for idx, r in df.iterrows():
                self.planlanan_isler.append({
                    "id": f"{ts}{idx:04d}",
                    "musteri": str(r.get("Müşteri", "Bilinmeyen")),
                    "urun": str(r.get("Ürün Kodu", "GENEL")).upper(),
                    "olcu": str(r.get("Ölçü", "-")),
                    "adet": str(r.get("Adet", 100)),
                    "istasyon_kapasiteleri": dict(self.varsayilan_kapasiteler),
                    "hazir_adet": str(r.get("Sevk Edilen", 0)),
                    "bitis": str(r.get("Sevk Hedefi", datetime.now().strftime("%d.%m.%Y"))),
                    "durum": str(r.get("Durum", "Beklemede")),
                    "oncelik": str(r.get("Öncelik", "Normal")),
                    "rotalar": str(r.get("Rota", "Kesim, Rodaj 1, Rodaj 2, Isıl Temper")),
                })
            self._kaydet()
            self.tabloyu_doldur()
            messagebox.showinfo("Başarılı", f"{len(df)} sipariş aktarıldı.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def siparis_listesi_excel_aktar(self):
        if not self.planlanan_isler:
            messagebox.showwarning("Uyarı", "Aktarılacak sipariş yok.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            pd.DataFrame(self.planlanan_isler).to_excel(path, index=False)
            messagebox.showinfo("Başarılı", "Sipariş listesi aktarıldı.")


def main():
    if CTK_AVAILABLE:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
    app = BYCPlanlamaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
