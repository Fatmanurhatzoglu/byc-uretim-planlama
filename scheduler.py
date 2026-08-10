"""Üretim çizelgeleme ve dar boğaz analizi motoru."""



from __future__ import annotations



from dataclasses import dataclass, field

from datetime import datetime, timedelta

from typing import Dict, List, Optional, Tuple



from config import (

    GUN_ADLARI_TR,

    HAFTA_SONU,

    MAKINE_OZEL_GUNLER,

    ONCELIK_SIRASI,

    TUM_MAKINELER,

    VARSAYILAN_KAPASITELER,

)

from rota_utils import kapasiteyi_bol, paralel_adimlar





def gun_adi_tr(dt: datetime) -> str:

    return GUN_ADLARI_TR.get(dt.strftime("%A"), dt.strftime("%A"))





def tarih_etiketi(dt: datetime) -> str:

    return f"{dt.strftime('%d.%m.%Y')} ({gun_adi_tr(dt)})"





def is_gunu_mu(dt: datetime) -> bool:

    return dt.strftime("%A") not in HAFTA_SONU





def makine_gunu_uygun_mu(

    makine: str, dt: datetime, takvim_kapali: Optional[dict[str, set[str]]] = None

) -> bool:

    tarih_str = dt.strftime("%d.%m.%Y")

    if takvim_kapali:

        kapali = takvim_kapali.get(tarih_str, set())

        if "*" in kapali or makine in kapali:

            return False



    ozel = MAKINE_OZEL_GUNLER.get(makine)

    if ozel is None:

        return is_gunu_mu(dt)

    return dt.weekday() in ozel





def sonraki_uygun_gun(

    baslangic: datetime,

    ofset: int,

    makine: str,

    takvim_kapali: Optional[dict[str, set[str]]] = None,

) -> datetime:

    """Ofset iş günü ileride, makine kurallarına uygun ilk günü döndürür."""

    gecerli = baslangic

    eklenen = 0

    while eklenen < ofset:

        gecerli += timedelta(days=1)

        if makine_gunu_uygun_mu(makine, gecerli, takvim_kapali):

            eklenen += 1

    while not makine_gunu_uygun_mu(makine, gecerli, takvim_kapali):

        gecerli += timedelta(days=1)

    return gecerli





@dataclass

class PlanKaydi:

    makine: str

    musteri: str

    urun: str

    adet: int

    hiz: str

    yuk: str

    doluluk: str

    tag: str

    siparis_id: str

    oncelik: str = "Normal"

    islem_sira: int = 1

    rota_toplam: int = 1

    tarih: str = ""

    sevk_hedef: str = ""





@dataclass

class CizelgelemeSonucu:

    gunluk_takvim: Dict[str, List[PlanKaydi]] = field(default_factory=dict)

    istasyon_yukleri: Dict[str, Dict[str, int]] = field(default_factory=dict)

    dar_bogaz_sayisi: int = 0

    uyarilar: List[str] = field(default_factory=list)





class UretimCizelgeleyici:

    MAX_GUN_ARAMA = 60



    def __init__(

        self,

        varsayilan_kapasiteler: Optional[dict] = None,

        baslangic_tarihi: Optional[datetime] = None,

        takvim_kapali: Optional[dict[str, set[str]]] = None,

    ):

        self.varsayilan_kapasiteler = varsayilan_kapasiteler or dict(

            VARSAYILAN_KAPASITELER

        )

        self.takvim_kapali = takvim_kapali or {}

        self.baslangic = baslangic_tarihi or datetime.now().replace(

            hour=0, minute=0, second=0, microsecond=0

        )

        self.istasyon_yukleri: Dict[str, Dict[str, int]] = {}

        self.gunluk_takvim: Dict[str, List[PlanKaydi]] = {}

        self.dar_bogaz_sayisi = 0

        self.uyarilar: List[str] = []



    def _gun_yuku(self, gun_str: str, makine: str) -> int:

        if gun_str not in self.istasyon_yukleri:

            self.istasyon_yukleri[gun_str] = {m: 0 for m in TUM_MAKINELER}

        # Eski / bilinmeyen makine anahtarı için güvenli varsayılan

        if makine not in self.istasyon_yukleri[gun_str]:

            self.istasyon_yukleri[gun_str][makine] = 0

        return self.istasyon_yukleri[gun_str][makine]



    def _gun_yuku_artir(self, gun_str: str, makine: str, adet: int) -> None:

        if gun_str not in self.istasyon_yukleri:

            self.istasyon_yukleri[gun_str] = {m: 0 for m in TUM_MAKINELER}

        if makine not in self.istasyon_yukleri[gun_str]:

            self.istasyon_yukleri[gun_str][makine] = 0

        self.istasyon_yukleri[gun_str][makine] += adet



    # Sorun / uyarı etiketleri (UI tag kodları)

    SORUN_ETIKETLERI = frozenset({"sevk_gecikti", "kapasite", "DarBogaz"})



    def _durum_etiketi(

        self,

        doluluk: float,

        gec_kaldi: bool,

        kapasite_nedenli: bool = False,

    ) -> Tuple[str, str]:

        """Dönüş: (görünen etiket, tag kodu).



        - sevk_gecikti: sevk tarihi aşıldı, kapasite beklemeyi neden değil

        - kapasite: sevk gecikti ve dolu gün beklenmesi bunu tetikledi

        - yogun: doluluk yüksek ama sevk hâlâ tutuyor

        """

        if gec_kaldi:

            if kapasite_nedenli or doluluk > 100:

                return "Kapasite yetersiz", "kapasite"

            return "Sevk gecikti", "sevk_gecikti"

        if doluluk > 100:

            return "Kapasite yetersiz", "kapasite"

        if doluluk >= 85:

            return "Yoğun", "yogun"

        return "Normal", "normal"



    def _siparisleri_sirala(self, siparisler: list) -> list:

        def anahtar(sip: dict):

            try:

                hedef = datetime.strptime(sip["bitis"], "%d.%m.%Y")

            except (ValueError, KeyError):

                hedef = datetime.max

            oncelik = ONCELIK_SIRASI.get(sip.get("oncelik", "Normal"), 1)

            return (oncelik, hedef, sip.get("id", ""))



        return sorted(

            [s for s in siparisler if s.get("durum") != "Tamamlandı"],

            key=anahtar,

        )



    def _kalan_adet(self, sip: dict) -> int:

        return max(

            0,

            int(sip["adet"]) - int(sip.get("hazir_adet", "0")),

        )



    def _istasyon_hizi(self, sip: dict, makine: str) -> int:

        kap = sip.get("istasyon_kapasiteleri", {})

        # Eski "Rodaj" anahtarı → Rodaj 1/2 fallback

        if makine not in kap and makine in ("Rodaj 1", "Rodaj 2") and "Rodaj" in kap:

            return int(kap.get("Rodaj", self.varsayilan_kapasiteler.get(makine, 500)))

        return int(

            kap.get(makine, self.varsayilan_kapasiteler.get(makine, 500))

        )



    def _gun_planla(

        self,

        makine: str,

        kalan: int,

        ofset: int,

        sip: dict,

        sevk_hedef: datetime,

        hiz: int,

        islem_sira: int = 1,

        rota_toplam: int = 1,

    ) -> int:

        """Kalan adeti günlere dağıtır. Biten ofseti döndürür."""

        # Dolu gün atlaması, henüz sevk öncesi bir güne denk gelirse gecikmeyi kapasiteye bağla

        kapasite_nedenli = False

        while kalan > 0 and ofset <= self.MAX_GUN_ARAMA:

            hedef_gun = sonraki_uygun_gun(self.baslangic, ofset, makine, self.takvim_kapali)

            gun_str = tarih_etiketi(hedef_gun)

            mevcut = self._gun_yuku(gun_str, makine)

            bos_kapasite = max(0, hiz - mevcut)



            if bos_kapasite <= 0:

                if sevk_hedef != datetime.max and hedef_gun.date() <= sevk_hedef.date():

                    kapasite_nedenli = True

                ofset += 1

                continue



            planlanan = min(kalan, bos_kapasite)

            self._gun_yuku_artir(gun_str, makine, planlanan)



            yeni_toplam = self._gun_yuku(gun_str, makine)

            doluluk = round((yeni_toplam / hiz) * 100, 1) if hiz else 100

            gec_kaldi = (

                sevk_hedef != datetime.max and hedef_gun.date() > sevk_hedef.date()

            )

            durum, tag = self._durum_etiketi(doluluk, gec_kaldi, kapasite_nedenli)



            if tag in self.SORUN_ETIKETLERI:

                self.dar_bogaz_sayisi += 1

                if tag == "kapasite":

                    self.uyarilar.append(

                        f"{sip['musteri']} / {sip['urun']} — {makine}: "

                        f"kapasite yetersiz, sevk ({sevk_hedef.strftime('%d.%m.%Y')}) kaçıyor."

                    )

                elif tag == "sevk_gecikti":

                    self.uyarilar.append(

                        f"{sip['musteri']} / {sip['urun']} — {makine} "

                        f"sevk tarihini ({sevk_hedef.strftime('%d.%m.%Y')}) aşıyor."

                    )



            if gun_str not in self.gunluk_takvim:

                self.gunluk_takvim[gun_str] = []



            self.gunluk_takvim[gun_str].append(

                PlanKaydi(

                    makine=makine,

                    musteri=sip["musteri"],

                    urun=sip["urun"],

                    adet=planlanan,

                    hiz=f"{hiz} ad/gün",

                    yuk=durum,

                    doluluk=f"%{doluluk}",

                    tag=tag,

                    siparis_id=str(sip.get("id", "")),

                    oncelik=sip.get("oncelik", "Normal"),

                    islem_sira=islem_sira,

                    rota_toplam=rota_toplam,

                    tarih=gun_str.split()[0],

                    sevk_hedef=sevk_hedef.strftime("%d.%m.%Y") if sevk_hedef != datetime.max else "",

                )

            )



            kalan -= planlanan

            if kalan > 0:

                ofset += 1



        if kalan > 0:

            self.uyarilar.append(

                f"{sip['musteri']} / {sip['urun']} — {makine} için "

                f"{kalan} adet {self.MAX_GUN_ARAMA} gün içinde planlanamadı."

            )



        return ofset + 1



    def _paralel_adim_planla(

        self,

        makineler: list[str],

        kalan: int,

        ofset: int,

        sip: dict,

        sevk_hedef: datetime,

        islem_sira: int,

        rota_toplam: int,

    ) -> int:

        """Paralel grup: adedi günlük hızlara orantılı böl; aynı ofsetten planla.



        Sonraki işlem, gruptaki en geç biten makinenin ofsetinden devam eder.

        """

        if len(makineler) == 1:

            m = makineler[0]

            hiz = self._istasyon_hizi(sip, m)

            return self._gun_planla(

                m, kalan, ofset, sip, sevk_hedef, hiz,

                islem_sira=islem_sira, rota_toplam=rota_toplam,

            )



        hizlar = [self._istasyon_hizi(sip, m) for m in makineler]

        paylar = kapasiteyi_bol(kalan, hizlar)

        bitisler: list[int] = []

        for makine, pay, hiz in zip(makineler, paylar, hizlar):

            if pay <= 0:

                continue

            # Hepsi aynı takvim ofsetinden başlar → aynı günlerde paralel çalışır

            bitis = self._gun_planla(

                makine, pay, ofset, sip, sevk_hedef, hiz,

                islem_sira=islem_sira, rota_toplam=rota_toplam,

            )

            bitisler.append(bitis)

        return max(bitisler) if bitisler else ofset + 1



    def calistir(self, siparisler: list) -> CizelgelemeSonucu:

        self.istasyon_yukleri = {}

        self.gunluk_takvim = {}

        self.dar_bogaz_sayisi = 0

        self.uyarilar = []



        for sip in self._siparisleri_sirala(siparisler):

            # Paralel gruplar (Rodaj 1+2) tek işlem adımı; eski "Rodaj" genişletilir

            adimlar = paralel_adimlar(sip.get("rotalar", ""))

            if not adimlar:

                continue



            kalan_toplam = self._kalan_adet(sip)

            if kalan_toplam <= 0:

                continue



            try:

                sevk_hedef = datetime.strptime(sip["bitis"], "%d.%m.%Y")

            except ValueError:

                sevk_hedef = datetime.max



            ofset = 1

            rota_toplam = len(adimlar)

            for sira_no, makineler in enumerate(adimlar, start=1):

                ofset = self._paralel_adim_planla(

                    makineler, kalan_toplam, ofset, sip, sevk_hedef,

                    islem_sira=sira_no, rota_toplam=rota_toplam,

                )



        return CizelgelemeSonucu(

            gunluk_takvim=self.gunluk_takvim,

            istasyon_yukleri=self.istasyon_yukleri,

            dar_bogaz_sayisi=self.dar_bogaz_sayisi,

            uyarilar=self.uyarilar,

        )



    @staticmethod

    def gun_sirala(gun_str: str) -> datetime:

        return datetime.strptime(gun_str.split()[0], "%d.%m.%Y")



    def gun_ozeti(self, gun_str: str) -> Dict[str, float]:

        """Seçilen gün için istasyon bazlı doluluk yüzdeleri."""

        yukler = self.istasyon_yukleri.get(gun_str, {})

        ozet = {}

        for makine, yuk in yukler.items():

            if yuk <= 0:

                continue

            kap = self.varsayilan_kapasiteler.get(makine, 500)

            ozet[makine] = min(100.0, round((yuk / kap) * 100, 1))

        return ozet


