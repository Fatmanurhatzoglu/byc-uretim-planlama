/* BYC İstasyon ekranı — fabrika noktası giriş/çıkış/fire (+ Kesim plaka) */

const LS_KEY = 'byc_istasyon_makine';
let seciliMakine = localStorage.getItem(LS_KEY) || '';
if (seciliMakine === 'Rodaj') {
  seciliMakine = 'Rodaj 1';
  localStorage.setItem(LS_KEY, seciliMakine);
}
let seciliSiparisId = '';
let seciliTur = 'cikis';
let liste = [];
let qrScanner = null;
let sonPlaka = null;

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

/** Eski tekil 'Rodaj' → Rodaj 1 + Rodaj 2 (Çin Rodajı korunur) */
function makineListesi() {
  const src = Array.isArray(MAKINELER) ? MAKINELER : [];
  const out = [];
  src.forEach((m) => {
    if (m === 'Rodaj') {
      ['Rodaj 1', 'Rodaj 2'].forEach((y) => { if (!out.includes(y)) out.push(y); });
    } else if (!out.includes(m)) {
      out.push(m);
    }
  });
  return out;
}

function isKesim() {
  return seciliMakine === 'Kesim';
}

function toast(msg, ms = 3200) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), ms);
}

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401) { location.href = '/login'; throw new Error('Oturum yok'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.hata || 'Hata');
  return data;
}

function goster(ekran) {
  ['ekranMakine', 'ekranListe', 'ekranIslem'].forEach((id) => {
    $(`#${id}`)?.classList.toggle('hidden', id !== ekran);
  });
}

function renderMakineGrid() {
  const grid = $('#makineGrid');
  if (!grid) return;
  const makineler = makineListesi();
  grid.innerHTML = makineler.map((m) =>
    `<button type="button" class="makine-btn" data-m="${esc(m)}">${esc(m)}</button>`
  ).join('');
  grid.querySelectorAll('.makine-btn').forEach((btn) => {
    btn.onclick = () => makineSec(btn.dataset.m);
  });
}

function esc(t) {
  return String(t ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}

function ceilDiv(a, b) {
  if (!b || b <= 0 || !a || a <= 0) return 0;
  return Math.ceil(a / b);
}

async function makineSec(m) {
  seciliMakine = m;
  localStorage.setItem(LS_KEY, m);
  $('#hdrMakine').textContent = m;
  $('#aktifMakineBaslik').textContent = m;
  seciliTur = isKesim() ? 'kesim' : 'cikis';
  syncTurUi();
  goster('ekranListe');
  await yukleListe();
  baslatQr();
}

async function yukleListe() {
  if (!seciliMakine) return;
  try {
    liste = await api(`/api/istasyon/${encodeURIComponent(seciliMakine)}/siparisler`);
    cizListe($('#istAra')?.value || '');
  } catch (e) {
    toast(e.message);
  }
}

function cizListe(q) {
  const el = $('#istSiparisList');
  if (!el) return;
  const qq = String(q || '').toLowerCase().trim();
  const rows = liste.filter((s) => {
    if (!qq) return true;
    return `${s.musteri} ${s.urun} ${s.olcu || ''}`.toLowerCase().includes(qq);
  });
  if (!rows.length) {
    el.innerHTML = '<p class="mob-hint">Bu makinede bekleyen sipariş yok.</p>';
    return;
  }
  el.innerHTML = rows.map((s) => `
    <div class="mob-card-item ${s.istasyon_stok > 0 ? 'ist-card-aktif' : ''}" data-id="${esc(s.id)}">
      <strong>${esc(s.musteri)}</strong>
      <span>${esc(s.urun)} · ${esc(s.olcu || '-')}</span>
      <span class="stok-pill">${esc(seciliMakine)} stok: ${s.istasyon_stok}</span>
      <span style="display:block;font-size:12px;margin-top:4px;color:#64748b">
        Aktif: ${esc(s.aktif_istasyon)} · Gelen ${s.istasyon_gelen} / Çıkan ${s.istasyon_cikan} / Fire ${s.istasyon_fire}
      </span>
    </div>`).join('');
  el.querySelectorAll('[data-id]').forEach((card) => {
    card.onclick = () => siparisAc(card.dataset.id);
  });
}

function kesimSonucKutuGoster(ozet) {
  const el = $('#kesimSonucKutu');
  if (!el) return;
  if (!isKesim() || !ozet) {
    el.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  const msg = ozet.mesaj || (
    `${ozet.parca_adet || '?'} adet cam kesildi` +
    (ozet.olcu ? ` (ölçü ${ozet.olcu})` : '') +
    `. ${ozet.tuketilen_plaka != null ? ozet.tuketilen_plaka : '?'} plaka stoktan düşüldü.` +
    (ozet.iade_plaka ? ` ${ozet.iade_plaka} plaka stoğa iade.` : '')
  );
  el.classList.remove('hidden');
  el.innerHTML = `
    <div class="kesim-sonuc-baslik">Son kesim kaydı</div>
    <p class="kesim-sonuc-metin">${esc(msg)}</p>
    ${ozet.zaman ? `<p class="mob-hint" style="margin:6px 0 0">${esc(ozet.zaman)}${ozet.kullanici ? ` · ${esc(ozet.kullanici)}` : ''}</p>` : ''}
  `;
}

function guncelleKesimHesap() {
  if (!isKesim()) return;
  const basi = parseInt(sonPlaka?.plaka_basi, 10) || 0;
  const parca = parseInt($('#istParcaAdet')?.value, 10) || 0;
  const alinan = parseInt($('#istPlakaAdet')?.value, 10) || 0;
  const tuket = ceilDiv(parca, basi);
  const iade = Math.max(0, alinan - tuket);
  if ($('#kesimTuketilen')) $('#kesimTuketilen').textContent = String(tuket);
  if ($('#kesimIade')) $('#kesimIade').textContent = String(iade);

  const kalan = sonPlaka?.kalan_kesilecek;
  const uyari = $('#kesimIhtiyacUyari');
  if (uyari) {
    if (kalan != null && parca > kalan) {
      uyari.classList.remove('hidden');
      uyari.textContent = `Kalan ihtiyaç ${kalan}; ${parca} fazla — kayıt reddedilir.`;
    } else {
      uyari.classList.add('hidden');
      uyari.textContent = '';
    }
  }
}

function cizKesimPlaka(plaka) {
  const el = $('#kesimPlakaKart');
  if (!el) return;
  sonPlaka = plaka || null;
  if (!isKesim()) {
    el.classList.add('hidden');
    el.innerHTML = '';
    kesimSonucKutuGoster(null);
    return;
  }
  if (!plaka) {
    el.classList.remove('hidden');
    el.innerHTML = '<p class="mob-hint">Plaka bilgisi yok — ofisten cam / ölçü girin.</p>';
    kesimSonucKutuGoster(null);
    return;
  }
  const stokTxt = plaka.stok_adet == null
    ? 'eşleşen stok yok'
    : `${plaka.stok_adet}`;
  const olcu = plaka.siparis_olcu || '—';
  const kalan = plaka.kalan_kesilecek != null ? plaka.kalan_kesilecek : '—';
  const basi = plaka.plaka_basi || '—';
  const gerekli = plaka.gerekli_plaka != null
    ? plaka.gerekli_plaka
    : (plaka.plaka_ihtiyac != null ? plaka.plaka_ihtiyac : '—');
  el.classList.remove('hidden');
  el.innerHTML = `
    <div class="kesim-plaka-baslik">Kesim ihtiyacı</div>
    <div class="kesim-plaka-grid">
      <div><span>Sipariş ölçü</span><strong>${esc(olcu)}</strong></div>
      <div><span>Kalan kesilecek</span><strong>${esc(kalan)}</strong></div>
      <div><span>1 plakadan çıkan</span><strong>${esc(basi)}</strong></div>
      <div><span>Gerekli plaka</span><strong>${esc(gerekli)}</strong></div>
      <div><span>Stokta kalan plaka</span><strong>${esc(stokTxt)}</strong></div>
      <div><span>Cam / kalınlık</span><strong>${esc(plaka.cam_turu || '—')}${plaka.kalinlik ? ` / ${plaka.kalinlik} mm` : ''}</strong></div>
    </div>
    ${plaka.hata ? `<p class="mob-hint" style="color:#b91c1c">${esc(plaka.hata)}</p>` : ''}
  `;

  kesimSonucKutuGoster(plaka.son_kesim || null);

  // Varsayılan: kalan ihtiyaç kadar parça, gerekli plaka kadar raftan alınan
  const defParca = Math.max(0, parseInt(plaka.kalan_kesilecek, 10) || 0);
  const defPlaka = Math.max(
    0,
    parseInt(plaka.gerekli_plaka, 10)
      || parseInt(plaka.plaka_ihtiyac, 10)
      || 0
  );
  if ($('#istParcaAdet') && !($('#istParcaAdet').dataset.touched === '1')) {
    $('#istParcaAdet').value = String(defParca);
  }
  if ($('#istPlakaAdet') && !($('#istPlakaAdet').dataset.touched === '1')) {
    $('#istPlakaAdet').value = String(defPlaka > 0 ? defPlaka : (defParca > 0 ? 1 : 0));
  }
  guncelleKesimHesap();
}

async function siparisAc(id) {
  seciliSiparisId = id;
  try {
    const ozet = await api(`/api/siparisler/${encodeURIComponent(id)}/asama`);
    if (!(ozet.rotalar || []).includes(seciliMakine)) {
      toast('Bu siparişin rotasında seçili makine yok');
      return;
    }
    const ist = (ozet.asamalar || []).find((a) => a.istasyon === seciliMakine) || {
      stok: 0, gelen: 0, cikan: 0, fire: 0,
    };
    $('#sipMusteri').textContent = ozet.musteri || '';
    $('#sipUrun').textContent = `${ozet.urun || ''} · Toplam ${ozet.adet}`;
    $('#sipStok').textContent = ist.stok;
    $('#sipGelen').textContent = ist.gelen;
    $('#sipCikan').textContent = ist.cikan;
    $('#sipFire').textContent = ist.fire;
    $('#sipAktif').textContent = `Aktif aşama: ${ozet.aktif_istasyon}` +
      (ozet.aktif_stok ? ` (${ozet.aktif_stok} stok)` : '');
    if ($('#istPlakaAdet')) $('#istPlakaAdet').dataset.touched = '';
    if ($('#istParcaAdet')) $('#istParcaAdet').dataset.touched = '';
    cizKesimPlaka(ozet.plaka);
    syncTurUi();
    goster('ekranIslem');
    durdurQr();
  } catch (e) {
    toast(e.message);
  }
}

function syncTurUi() {
  const kesimModu = isKesim();
  $('#turBtnsNormal')?.classList.toggle('hidden', kesimModu);
  $('#turBtnsKesim')?.classList.toggle('hidden', !kesimModu);

  if (kesimModu && seciliTur !== 'fire' && seciliTur !== 'kesim') {
    seciliTur = 'kesim';
  }
  if (!kesimModu && seciliTur === 'kesim') {
    seciliTur = 'cikis';
  }

  const kapsayici = kesimModu ? '#turBtnsKesim' : '#turBtnsNormal';
  $$(`${kapsayici} .tur-btn`).forEach((b) => {
    b.classList.toggle('aktif', b.dataset.tur === seciliTur);
  });

  const fire = seciliTur === 'fire';
  const kesimKayit = kesimModu && !fire;
  $('#adetGrupNormal')?.classList.toggle('hidden', kesimKayit);
  $('#adetGrupKesim')?.classList.toggle('hidden', !kesimKayit);
  $('#istNedenGrup')?.classList.toggle('hidden', !fire);
  $('#aktarSatir')?.classList.toggle('hidden', fire);
  if (!kesimKayit) {
    $('#kesimSonucKutu')?.classList.toggle('hidden', !kesimModu || !$('#kesimSonucKutu')?.innerHTML);
  }
  if (fire) {
    $('#lblAdet').textContent = kesimModu ? 'Fire parça adedi' : 'Adet';
  } else if (!kesimModu) {
    $('#lblAdet').textContent = seciliTur === 'giris' ? 'Giriş adedi' : 'Çıkan adet';
  }
}

async function kaydet() {
  if (!seciliSiparisId || !seciliMakine) { toast('Sipariş/makine eksik'); return; }

  const kesimKayit = isKesim() && seciliTur !== 'fire';
  let payload;

  if (kesimKayit) {
    const plaka_adet = parseInt($('#istPlakaAdet')?.value, 10);
    const parca_adet = parseInt($('#istParcaAdet')?.value, 10);
    if (!plaka_adet || plaka_adet <= 0) { toast('Geçerli raftan alınan plaka girin'); return; }
    if (!parca_adet || parca_adet <= 0) { toast('Geçerli kesilen parça adedi girin'); return; }

    const kalan = sonPlaka?.kalan_kesilecek;
    if (kalan != null && parca_adet > kalan) {
      toast(`Kalan ihtiyaç ${kalan} parça; ${parca_adet} kesilemez.`);
      return;
    }

    const basi = parseInt(sonPlaka?.plaka_basi, 10) || 0;
    const tuket = ceilDiv(parca_adet, basi);
    if (basi > 0 && plaka_adet < tuket) {
      toast(`${parca_adet} parça için en az ${tuket} plaka gerekir (raftan alınan ${plaka_adet}).`);
      return;
    }

    if (sonPlaka && sonPlaka.stok_adet != null && plaka_adet > sonPlaka.stok_adet) {
      const ok = confirm(
        `Stokta görünene göre ${sonPlaka.stok_adet} plaka var; siz ${plaka_adet} yazdınız.\n` +
        `Kayıt stok yetersizse reddedilir. Yine de denensin mi?`
      );
      if (!ok) return;
    }
    payload = {
      istasyon: 'Kesim',
      tur: 'kesim',
      plaka_adet,
      parca_adet,
      not: ($('#istNot')?.value || '').trim(),
      sonraki_aktar: $('#istAktar')?.checked !== false,
    };
  } else {
    const adet = parseInt($('#istAdet')?.value, 10);
    if (!adet || adet <= 0) { toast('Geçerli adet girin'); return; }
    payload = {
      istasyon: seciliMakine,
      tur: seciliTur,
      adet,
      neden: seciliTur === 'fire' ? ($('#istNeden')?.value || '') : '',
      not: ($('#istNot')?.value || '').trim(),
      sonraki_aktar: $('#istAktar')?.checked !== false,
    };
  }

  try {
    const uyariTur = kesimKayit ? 'giris' : seciliTur;
    const onKontrol = await api(`/api/siparisler/${encodeURIComponent(seciliSiparisId)}/asama/uyari`, {
      method: 'POST',
      body: JSON.stringify({ istasyon: seciliMakine, tur: uyariTur }),
    });
    if (onKontrol.uyari) {
      const ok = confirm(`Sıra uyarısı:\n${onKontrol.uyari}\n\nYine de kaydedilsin mi?`);
      if (!ok) return;
    }

    const ozet = await api(`/api/siparisler/${encodeURIComponent(seciliSiparisId)}/asama`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    let msg = 'Kaydedildi';
    const pd = ozet.plaka_dusum || ozet.son_kesim;
    if (pd) {
      msg = pd.mesaj || (
        `${pd.parca_adet} adet cam kesildi` +
        (pd.olcu ? ` (ölçü ${pd.olcu})` : '') +
        `. ${pd.dusulen != null ? pd.dusulen : pd.tuketilen_plaka} plaka stoktan düşüldü.` +
        ((pd.iade || pd.iade_plaka) ? ` ${pd.iade || pd.iade_plaka} plaka stoğa iade.` : '')
      );
    }
    if (ozet.uyari) msg += ` — uyarı: ${ozet.uyari}`;
    toast(msg, 5200);
    $('#istNot').value = '';
    await siparisAc(seciliSiparisId);
    await yukleListe();
  } catch (e) {
    toast(e.message, 4500);
  }
}

function parseSiparisIdFromQr(text) {
  const t = String(text || '').trim();
  const m = t.match(/\/sevk\/([^/?#]+)/i);
  if (m) return decodeURIComponent(m[1]);
  if (/^\d+$/.test(t) || t.length > 8) return t;
  return null;
}

function baslatQr() {
  if (typeof Html5Qrcode === 'undefined') return;
  const el = $('#qrReader');
  if (!el) return;
  durdurQr();
  try {
    qrScanner = new Html5Qrcode('qrReader');
    qrScanner.start(
      { facingMode: 'environment' },
      { fps: 8, qrbox: { width: 220, height: 220 } },
      async (decoded) => {
        const id = parseSiparisIdFromQr(decoded);
        if (!id) { toast('QR’dan sipariş okunamadı'); return; }
        await siparisAc(id);
      },
      () => {}
    ).catch(() => {
      el.innerHTML = '<p class="mob-hint">Kamera açılamadı. Listeden seçin.</p>';
    });
  } catch (_) {
    el.innerHTML = '<p class="mob-hint">QR desteklenmiyor. Listeden seçin.</p>';
  }
}

function durdurQr() {
  if (qrScanner) {
    try { qrScanner.stop().catch(() => {}); } catch (_) {}
    qrScanner = null;
  }
}

function init() {
  $('#istNeden').innerHTML = (FIRE_NEDENLERI || []).map(
    (n) => `<option value="${esc(n)}">${esc(n)}</option>`
  ).join('');

  $$('.tur-btn').forEach((b) => {
    b.onclick = () => { seciliTur = b.dataset.tur; syncTurUi(); };
  });

  ['istPlakaAdet', 'istParcaAdet'].forEach((id) => {
    $(`#${id}`)?.addEventListener('input', (e) => {
      e.target.dataset.touched = '1';
      guncelleKesimHesap();
    });
  });

  syncTurUi();

  $('#btnKaydet')?.addEventListener('click', kaydet);
  $('#istAra')?.addEventListener('input', (e) => cizListe(e.target.value));
  $('#btnMakineDegistir')?.addEventListener('click', () => {
    durdurQr();
    localStorage.removeItem(LS_KEY);
    seciliMakine = '';
    $('#hdrMakine').textContent = 'Makine seçin';
    goster('ekranMakine');
  });
  $('#btnListeyeDon')?.addEventListener('click', async () => {
    goster('ekranListe');
    await yukleListe();
    baslatQr();
  });

  renderMakineGrid();

  const makineler = makineListesi();
  const params = new URLSearchParams(location.search);
  const qMakine = params.get('makine');
  if (qMakine && makineler.includes(qMakine)) {
    makineSec(qMakine);
  } else if (seciliMakine && makineler.includes(seciliMakine)) {
    makineSec(seciliMakine);
  } else {
    goster('ekranMakine');
  }
}

init();
