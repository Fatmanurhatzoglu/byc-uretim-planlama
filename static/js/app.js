/* BYC v7.0 — Web Arayüz */

let siparisler = [], cizelge = null, kapasiteChart = null, ganttInstance = null, varsayilanKap = {};
let varsayilanFire = {};
const ROL = typeof KULLANICI_ROL !== 'undefined' ? KULLANICI_ROL : 'admin';

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

async function api(url, opts = {}) {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json', ...opts.headers }, ...opts });
  if (res.status === 401) { window.location.href = '/login'; throw new Error('Oturum süresi doldu'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.hata || 'Hata oluştu');
    err.data = data;
    err.detay = data.detay;
    throw err;
  }
  return data;
}

function toast(msg, type = '') {
  const el = $('#toast');
  el.textContent = msg; el.className = `toast ${type}`;
  setTimeout(() => el.classList.add('hidden'), 3500);
  setTimeout(() => el.classList.remove('hidden'), 10);
}

function bugunTarih() {
  const d = new Date();
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
}

function durumBadge(d) {
  const m = { Beklemede:'badge-beklemede', Üretimde:'badge-uretimde', Durduruldu:'badge-durduruldu', Tamamlandı:'badge-tamamlandi' };
  return `<span class="badge ${m[d]||''}">${d}</span>`;
}
function oncelikBadge(o) {
  const m = { Acil:'badge-acil', Normal:'badge-normal', Düşük:'badge-dusuk' };
  return `<span class="badge ${m[o]||'badge-normal'}">${o}</span>`;
}
function tagClass(t) {
  return {
    normal: 'tag-normal', Normal: 'tag-normal',
    yogun: 'tag-yogun', Kritik: 'tag-yogun',
    sevk_gecikti: 'tag-sevk', kapasite: 'tag-kapasite', DarBogaz: 'tag-sevk',
  }[t] || '';
}
function tagLabel(t) {
  return {
    normal: 'Normal', Normal: 'Normal',
    yogun: 'Yoğun', Kritik: 'Yoğun',
    sevk_gecikti: 'Sevk gecikti', kapasite: 'Kapasite yetersiz', DarBogaz: 'Sevk gecikti',
  }[t] || t || '';
}
function isSorunTag(t) {
  return t === 'sevk_gecikti' || t === 'kapasite' || t === 'DarBogaz';
}
function isYogunTag(t) {
  return t === 'yogun' || t === 'Kritik';
}
function dolulukFillClass(p) { return p > 100 ? 'fill-red' : p >= 85 ? 'fill-yellow' : 'fill-green'; }

// Rol kontrolü
if (ROL === 'saha') window.location.href = '/mobile';
$$('.admin-only').forEach(el => { if (ROL !== 'admin') el.style.display = 'none'; });

const PAGE_TITLES = { dashboard:'Fabrika Pano', siparisler:'Siparişler', 'plaka-stok':'Plaka Stok',
  cizelgeleme:'Çizelgeleme',
  'ai-kesim':'AI Kesim Öneri', gantt:'Gantt Şeması',
  simulasyon:'Kapasite Simülasyonu', log:'İşlem Geçmişi', ayarlar:'Ayarlar' };

$$('.nav-item').forEach(btn => btn.addEventListener('click', () => {
  const p = btn.dataset.page;
  $$('.nav-item').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  $$('.page').forEach(x => x.classList.remove('active'));
  $(`#page-${p}`).classList.add('active');
  $('#pageTitle').textContent = PAGE_TITLES[p] || '';
  $('#sidebar').classList.remove('open');
  if (p === 'gantt' && cizelge) renderGantt();
  if (p === 'log') loadLog();
  if (p === 'ai-kesim') loadAiKesim(false);
  if (p === 'plaka-stok') loadPlakaStok();
}));

$('#menuToggle')?.addEventListener('click', () => $('#sidebar').classList.toggle('open'));

// KPI
async function loadKPI() {
  const k = await api('/api/kpi');
  $('#kpiToplam').textContent = k.toplam;
  $('#kpiUretimde').textContent = k.uretimde;
  $('#kpiTamamlanan').textContent = k.tamamlanan;
  $('#kpiAcil').textContent = k.acil;
  $('#kpiKalan').textContent = k.kalan_adet;
  if ($('#kpiPlaka')) $('#kpiPlaka').textContent = k.plaka_toplam ?? 0;
  const kart = $('#kpiPlakaKart');
  if (kart) {
    kart.classList.toggle('danger', (k.plaka_dusuk_adet || 0) > 0);
    kart.classList.toggle('warning', (k.plaka_dusuk_adet || 0) > 0);
  }
  const uy = $('#plakaUyariKutu');
  if (uy) {
    const dusuk = k.plaka_dusuk || [];
    const esik = k.plaka_uyari_esik || 10;
    if (dusuk.length) {
      uy.classList.remove('hidden');
      uy.innerHTML = `<strong>⚠ Düşük plaka stoku (≤${esik})</strong>`
        + dusuk.map(d => `<div>• ${escHtml(d.cam_turu)} ${d.kalinlik} mm · ${d.boy}×${d.en} — <strong style="color:#b91c1c">${d.adet}</strong> adet</div>`).join('')
        + `<div style="margin-top:6px"><button type="button" class="btn btn-sm btn-outline" id="btnGitPlakaStok">Plaka Stok →</button></div>`;
      $('#btnGitPlakaStok')?.addEventListener('click', () => gotoPage('plaka-stok'));
    } else {
      uy.classList.add('hidden');
      uy.innerHTML = '';
    }
  }
}

function updateDarBogazBadge() {
  const el = $('#darBogazBadge');
  if (!cizelge) { el.textContent = 'Henüz çizelgeleme yok'; el.title = ''; el.classList.remove('alert'); return; }
  const n = cizelge.dar_bogaz_sayisi || 0;
  const es = cizelge.etiket_sayilari || {};
  const parts = [];
  if (es.sevk_gecikti) parts.push(`${es.sevk_gecikti} sevk gecikti`);
  if (es.kapasite) parts.push(`${es.kapasite} kapasite`);
  if (es.yogun) parts.push(`${es.yogun} yoğun`);
  if (n) {
    el.textContent = parts.length ? `⚠ ${n} sorun · ${parts.join(', ')}` : `⚠ ${n} sorun`;
    el.title = 'Sevk gecikti = hedef tarih aşıldı · Kapasite = dolu gün yüzünden kaydı · Yoğun = yüksek doluluk';
  } else if (es.yogun) {
    el.textContent = `✅ Sorun yok · ${es.yogun} yoğun`;
    el.title = 'Yoğun: doluluk ≥ %85, sevk hâlâ tutuyor';
  } else {
    el.textContent = '✅ Sevk / kapasite OK';
    el.title = '';
  }
  el.classList.toggle('alert', n > 0);
}

function renderKapasiteChart(gun) {
  const ctx = $('#chartKapasite');
  if (!gun?.doluluk_ozet) { kapasiteChart?.destroy(); return; }
  const labels = Object.keys(gun.doluluk_ozet), values = Object.values(gun.doluluk_ozet);
  const colors = values.map(v => v > 100 ? '#ef4444' : v >= 85 ? '#f59e0b' : '#10b981');
  kapasiteChart?.destroy();
  kapasiteChart = new Chart(ctx, { type:'bar', data:{ labels, datasets:[{ data:values, backgroundColor:colors, borderRadius:6 }] },
    options:{ responsive:true, plugins:{ legend:{ display:false } }, scales:{ y:{ beginAtZero:true, max:120 } } } });
}

function gotoSiparisler() {
  gotoPage('siparisler');
}

function filtreleriTemizle() {
  if ($('#aramaInput')) $('#aramaInput').value = '';
  if ($('#filtreDurum')) $('#filtreDurum').value = '';
}

function escHtml(t) {
  return String(t ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}

function formatRota(rotalar) {
  if (!rotalar) return '-';
  const adimlar = String(rotalar).split(',').map(x => x.trim()).filter(Boolean);
  if (!adimlar.length) return '-';
  return adimlar.map((m, i) => `<span class="rota-adim"><span class="rota-no">${i+1}</span>${escHtml(m)}</span>`).join('<span class="rota-ok">→</span>');
}

function gotoPage(page) {
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  $$('.page').forEach(p => p.classList.remove('active'));
  $(`#page-${page}`)?.classList.add('active');
  $('#pageTitle').textContent = PAGE_TITLES[page] || '';
  $('#sidebar').classList.remove('open');
}

// Siparişler
async function loadSiparisler() {
  siparisler = await api('/api/siparisler');
  renderSiparisTablo();
  await loadKPI();
}

function renderSiparisTablo(vurguId = null) {
  const arama = ($('#aramaInput')?.value || '').toLowerCase();
  const filtre = $('#filtreDurum')?.value || '';
  const tbody = $('#siparisBody');
  const bosMesaj = $('#siparisBosMesaj');
  if (!tbody) return;

  tbody.innerHTML = '';
  const filtrelenmis = siparisler.filter(s => {
    if (filtre && s.durum !== filtre) return false;
    return !arama || `${s.musteri} ${s.urun} ${s.olcu||''}`.toLowerCase().includes(arama);
  });

  if ($('#siparisSayac')) {
    $('#siparisSayac').textContent = filtrelenmis.length === siparisler.length
      ? `${siparisler.length} sipariş`
      : `${filtrelenmis.length} / ${siparisler.length} sipariş`;
  }

  if (filtrelenmis.length === 0) {
    bosMesaj?.classList.remove('hidden');
    if (bosMesaj) {
      bosMesaj.textContent = siparisler.length === 0
        ? 'Henüz sipariş yok. "+ Yeni Sipariş" butonuna tıklayın.'
        : 'Filtreye uygun sipariş bulunamadı. "Filtreyi Temizle" butonuna tıklayın.';
    }
    return;
  }
  bosMesaj?.classList.add('hidden');

  filtrelenmis.forEach(s => {
    const kalan = Math.max(0, parseInt(s.adet) - parseInt(s.hazir_adet||0));
    const tr = document.createElement('tr');
    if (vurguId && s.id === vurguId) tr.classList.add('row-vurgu');
    tr.style.cursor = 'pointer';
    tr.title = 'Düzenlemek için çift tıklayın';
    tr.addEventListener('dblclick', () => editSiparis(s.id));
    tr.innerHTML = `<td><strong>${escHtml(s.musteri)}</strong></td><td>${escHtml(s.urun)}</td><td>${escHtml(s.olcu||'-')}</td>
      <td class="rota-cell">${formatRota(s.rotalar)}</td>
      <td>${asamaBadge(s)}</td>
      <td>${s.adet}</td><td>${s.hazir_adet||0}</td><td>${kalan}</td>
      <td>${oncelikBadge(s.oncelik||'Normal')}</td><td>${durumBadge(s.durum)}</td><td>${escHtml(s.bitis)}</td>
      <td class="islem-hucre">
        <button type="button" class="btn btn-sm btn-outline" data-asama="${escHtml(s.id)}">Aşama</button>
        <button type="button" class="btn btn-sm btn-outline" data-etiket="${escHtml(s.id)}">İş Emri</button>
        <button type="button" class="btn btn-sm btn-outline" data-pdf="${escHtml(s.id)}">PDF</button>
        ${ROL !== 'saha' ? `<button type="button" class="btn btn-sm btn-primary" data-edit="${escHtml(s.id)}">Düzenle</button>
        <button type="button" class="btn btn-sm btn-success" data-sevk="${escHtml(s.id)}">Sevk</button>
        ${ROL==='admin'||ROL==='ofis'?`<button type="button" class="btn btn-sm btn-danger" data-del="${escHtml(s.id)}">Sil</button>`:''}` : ''}
      </td>`;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll('[data-asama]').forEach(btn => btn.onclick = () => openAsamaModal(btn.dataset.asama));
  tbody.querySelectorAll('[data-etiket]').forEach(btn => btn.onclick = () => {
    window.open(`/siparis/${encodeURIComponent(btn.dataset.etiket)}/is-emri?print=1`, '_blank');
  });
  tbody.querySelectorAll('[data-pdf]').forEach(btn => btn.onclick = () => {
    window.open(`/api/siparisler/${encodeURIComponent(btn.dataset.pdf)}/pdf`, '_blank');
  });
  tbody.querySelectorAll('[data-edit]').forEach(btn => btn.onclick = () => editSiparis(btn.dataset.edit));
  tbody.querySelectorAll('[data-sevk]').forEach(btn => btn.onclick = () => openSevk(btn.dataset.sevk));
  tbody.querySelectorAll('[data-del]').forEach(btn => btn.onclick = () => deleteSiparis(btn.dataset.del));
}

function asamaBadge(s) {
  const ist = s.aktif_istasyon || 'Başlamadı';
  const stok = s.aktif_stok || 0;
  let cls = '';
  if (ist === 'Başlamadı') cls = 'bekliyor';
  else if (ist === 'Sevk bekliyor') cls = 'sevk';
  const stokHtml = stok > 0 ? ` <span class="asama-stok">· ${stok}</span>` : '';
  return `<span class="asama-badge ${cls}">${escHtml(ist)}${stokHtml}</span>`;
}

$('#aramaInput')?.addEventListener('input', () => renderSiparisTablo());
$('#filtreDurum')?.addEventListener('change', () => renderSiparisTablo());
$('#btnFiltreTemizle')?.addEventListener('click', () => { filtreleriTemizle(); renderSiparisTablo(); toast('Filtre temizlendi'); });

function acYeniSiparis() {
  gotoSiparisler();
  openSiparisModal();
}

$('#btnYeniSiparis')?.addEventListener('click', acYeniSiparis);
$('#btnYeniSiparisUst')?.addEventListener('click', acYeniSiparis);

// Modal — istasyon adlarında boşluk/Türkçe karakter güvenli id
function makineSlug(m) {
  return String(m).replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_ğüşıöçĞÜŞİÖÇ]/g, '');
}

/** Eski 'Rodaj' → Rodaj 1 + Rodaj 2 (form checkbox eşlemesi) */
function genisletRotaSecim(list) {
  const out = [];
  (list || []).forEach(m => {
    if (m === 'Rodaj') {
      ['Rodaj 1', 'Rodaj 2'].forEach(y => { if (!out.includes(y)) out.push(y); });
    } else if (!out.includes(m)) {
      out.push(m);
    }
  });
  return out;
}

/**
 * Fire matematik adımları (arka plan): Rodaj 1+2 birlikte seçildiyse fire bir kez (max %).
 * Form UI'da her makine yine ayrı satır/etiketle gösterilir — birleşik "Rodaj" yok.
 */
function fireAdimlari(rotalar) {
  const adimlar = [];
  let i = 0;
  const rodajGrup = new Set(['Rodaj 1', 'Rodaj 2']);
  while (i < rotalar.length) {
    const m = rotalar[i];
    if (rodajGrup.has(m)) {
      const uye = [];
      while (i < rotalar.length && rodajGrup.has(rotalar[i])) {
        if (!uye.includes(rotalar[i])) uye.push(rotalar[i]);
        i++;
      }
      adimlar.push(uye);
    } else {
      adimlar.push([m]);
      i++;
    }
  }
  return adimlar;
}

function mapEskiKap(obj) {
  const o = { ...(obj || {}) };
  if (o.Rodaj !== undefined) {
    if (o['Rodaj 1'] === undefined) o['Rodaj 1'] = o.Rodaj;
    if (o['Rodaj 2'] === undefined) o['Rodaj 2'] = o.Rodaj;
    delete o.Rodaj;
  }
  return o;
}

function buildRotaGrid(secili=[], kap={}, fireSip={}) {
  const grid = $('#rotaGrid');
  if (!grid) return;
  grid.innerHTML = '';
  // Her makine ayrı satır (Rodaj 1 ≠ Rodaj 2). Checkbox'lar birbirine bağlı değil.
  MAKINELER.forEach(m => {
    const slug = makineSlug(m);
    const checked = secili.includes(m);
    const hiz = kap[m] ?? varsayilanKap[m] ?? 500;
    const fireVal = (fireSip[m] !== undefined && fireSip[m] !== null && fireSip[m] !== '')
      ? fireSip[m]
      : (varsayilanFire[m] ?? 10);

    const d = document.createElement('div');
    d.className = 'rota-item' + (checked ? ' aktif' : '');
    d.dataset.makine = m;
    d.innerHTML = `
      <input type="checkbox" class="sip-rota-cb" id="sip_rota_${slug}" ${checked ? 'checked' : ''}>
      <label for="sip_rota_${slug}">${escHtml(m)}</label>
      <div class="rota-field">
        <small>Hız/gün</small>
        <input type="number" class="sip-kap" id="sip_kap_${slug}" value="${hiz}" min="1" inputmode="numeric">
      </div>
      <div class="rota-field">
        <small>Fire %</small>
        <input type="number" class="sip-fire" id="sip_fire_${slug}" value="${fireVal}" min="0" max="80" step="0.1" inputmode="decimal">
      </div>`;
    grid.appendChild(d);

    const cb = d.querySelector('.sip-rota-cb');
    const numKap = d.querySelector('.sip-kap');
    const numFire = d.querySelector('.sip-fire');

    const syncAktif = () => {
      d.classList.toggle('aktif', cb.checked);
    };
    // Yalnızca bu satırın checkbox'ı — Rodaj kardeşini otomatik işaretleme yok
    cb.addEventListener('change', syncAktif);

    // Hız/Fire her zaman yazılabilir; yazınca yalnız bu istasyon seçilir
    const aktiflestir = () => {
      if (!cb.checked) {
        cb.checked = true;
        syncAktif();
      }
    };
    [numKap, numFire].forEach(el => {
      el.addEventListener('pointerdown', aktiflestir);
      el.addEventListener('focus', aktiflestir);
      el.addEventListener('input', aktiflestir);
    });
    numFire.addEventListener('input', guncelleFireOnizleme);
    numKap.addEventListener('input', guncelleFireOnizleme);
    cb.addEventListener('change', guncelleFireOnizleme);
  });
  guncelleFireOnizleme();
}

/** Sipariş formunda fire dahil kesim adedini anlık göster */
function guncelleFireOnizleme() {
  const el = $('#fireOnizleme');
  if (!el) return;
  const net = parseInt($('#fAdet')?.value, 10) || 0;
  const hazir = parseInt($('#fHazir')?.value, 10) || 0;
  const kalan = Math.max(0, net - hazir);
  const { rotalar, fireOranlari } = getSeciliRota();
  if (!rotalar.length || kalan <= 0) {
    el.textContent = kalan <= 0
      ? 'Net kalan yok — fire hesabı yapılamaz.'
      : 'İstasyon seçin; fire dahil kesim burada görünür.';
    guncellePlakaOnizleme(0);
    return;
  }
  // fire.py: Rodaj 1+2 birlikteyse fire bir kez (max); etiketlerde makine adları ayrı kalır
  let mevcut = kalan;
  const adimMetin = [];
  const adimlar = fireAdimlari(rotalar);
  for (let i = adimlar.length - 1; i >= 0; i--) {
    const grup = adimlar[i];
    let pct = 0;
    const etiketler = [];
    grup.forEach(ist => {
      let p = parseFloat(fireOranlari[ist] ?? 0);
      if (!Number.isFinite(p)) p = 0;
      p = Math.max(0, Math.min(80, p));
      pct = Math.max(pct, p);
      etiketler.push(`${ist} %${p}`);
    });
    pct = Math.max(0, Math.min(80, pct));
    const verim = Math.max(0.01, 1 - pct / 100);
    const once = mevcut / verim;
    adimMetin.unshift(etiketler.join(', '));
    mevcut = once;
  }
  const kes = Math.ceil(mevcut);
  const fireAdet = Math.max(0, kes - kalan);
  el.innerHTML = `Net kalan <strong>${kalan}</strong> → fire dahil kesilecek <strong style="color:#1d4ed8">${kes}</strong> (+${fireAdet}) · ${escHtml(adimMetin.join(' → '))}`;
  guncellePlakaOnizleme(kes);
}

/** 3210×2250 — kenar boşluk + rodaj + optimize yerleşim şeması */
let _plakaTimer = null;
function guncellePlakaOnizleme(kesimAdet) {
  const el = $('#plakaOnizleme');
  const sema = $('#plakaSema');
  if (!el) return;
  const boy = parseFloat(String($('#fBoy')?.value || '').replace(',', '.'));
  const en = parseFloat(String($('#fEn')?.value || '').replace(',', '.'));
  if (!Number.isFinite(boy) || !Number.isFinite(en) || boy <= 0 || en <= 0) {
    el.textContent = 'Boy / en girince optimize kesim şeması burada görünür (kenar boşluk 20 mm, rodaj her kenara).';
    if (sema) sema.innerHTML = '';
    return;
  }
  clearTimeout(_plakaTimer);
  _plakaTimer = setTimeout(async () => {
    try {
      const kes = Number.isFinite(kesimAdet) ? kesimAdet : (
        Math.max(0, (parseInt($('#fAdet')?.value, 10) || 0) - (parseInt($('#fHazir')?.value, 10) || 0))
      );
      const oz = await api('/api/plaka-hesap', {
        method: 'POST',
        body: JSON.stringify({
          boy: $('#fBoy').value,
          en: $('#fEn').value,
          kalinlik: $('#fKalinlik')?.value,
          cam_turu: $('#fCamTuru')?.value,
          rodaj_pay_mm: $('#fRodajPay')?.value || 0,
          kenar_bosluk_mm: $('#fKenarBosluk')?.value || 20,
          plaka_boy: window._seciliPlaka?.boy || 3210,
          plaka_en: window._seciliPlaka?.en || 2250,
          adet: $('#fAdet')?.value || 0,
          hazir_adet: $('#fHazir')?.value || 0,
          kesim_adet: kes,
          svg: true,
        }),
      });
      if (oz.hata && !oz.plaka_basi) {
        el.innerHTML = escHtml(oz.hata);
        if (sema) sema.innerHTML = '';
        return;
      }
      const ekstra = oz.ekstra_serit ? ` · fire şerit +${oz.ekstra_serit}` : '';
      el.innerHTML = `Kullanılabilir <strong>${oz.kullanilabilir_boy}×${oz.kullanilabilir_en}</strong> `
        + `(plaka − 2×${oz.kenar_bosluk} kenar) · Kesim <strong>${oz.kesim_boy}×${oz.kesim_en}</strong> `
        + `(ölçü + 2×${oz.rodaj_mm} rodaj) · `
        + `<strong style="color:#15803d">${oz.plaka_basi}</strong> adet/plaka (${escHtml(oz.yon)}${ekstra}) · `
        + `verim %${oz.verim_yuzde}`
        + (oz.kesilecek_adet
          ? ` · fire dahil ${oz.kesilecek_adet} → <strong style="color:#1d4ed8">${oz.plaka_ihtiyac} plaka</strong>`
          : '')
        + `. <span style="opacity:.8">Sarı kesik çizgi = kenar boşluğu · mavi=düz · yeşil=döndürülmüş</span>`;
      if (sema) sema.innerHTML = oz.svg || '';
    } catch (err) {
      el.textContent = err.message || 'Plaka hesabı yapılamadı';
      if (sema) sema.innerHTML = '';
    }
  }, 280);
}

function guncelleKesimPlaniUI(sip) {
  const kutu = $('#kesimPlaniKutu');
  if (!kutu) return;
  const id = $('#fId')?.value;
  if (id) kutu.classList.remove('hidden');
  else kutu.classList.add('hidden');
  const d = sip?.uretim_detay || {};
  const ad = d.kesim_plani_orijinal || (d.kesim_plani_dosya ? 'Yüklü plan' : '');
  const adEl = $('#kesimPlaniAd');
  if (adEl) adEl.textContent = ad || '';
  const indir = $('#btnKesimPlaniIndir');
  const sil = $('#btnKesimPlaniSil');
  if (d.kesim_plani_dosya && id) {
    indir?.classList.remove('hidden');
    sil?.classList.remove('hidden');
    if (indir) indir.href = `/api/siparisler/${encodeURIComponent(id)}/kesim-plani`;
  } else {
    indir?.classList.add('hidden');
    sil?.classList.add('hidden');
  }
}

function getSeciliRota() {
  const rotalar = [];
  const kapasiteler = {};
  const fireOranlari = {};
  MAKINELER.forEach(m => {
    const slug = makineSlug(m);
    const cb = document.getElementById(`sip_rota_${slug}`);
    const num = document.getElementById(`sip_kap_${slug}`);
    const fire = document.getElementById(`sip_fire_${slug}`);
    if (cb && cb.checked) {
      rotalar.push(m);
      const v = parseInt(num?.value, 10);
      kapasiteler[m] = Number.isFinite(v) && v > 0 ? v : 500;
      const f = parseFloat(String(fire?.value ?? '').replace(',', '.'));
      fireOranlari[m] = Number.isFinite(f) && f >= 0 ? f : 0;
    }
  });
  return { rotalar, kapasiteler, fireOranlari };
}

function setSelectValue(sel, value, fallback) {
  if (!sel) return;
  const v = value || fallback;
  const opts = [...sel.options].map(o => o.value || o.textContent);
  if (opts.includes(v)) sel.value = v;
  else sel.value = fallback;
}

function openSiparisModal(sip=null) {
  const modal = $('#siparisModal');
  if (!modal) return;
  $('#modalBaslik').textContent = sip ? 'Sipariş Düzenle' : 'Yeni Sipariş';
  $('#fId').value = sip?.id || '';
  $('#fMusteri').value = sip?.musteri || '';
  $('#fUrun').value = sip?.urun || '';
  $('#fOlcu').value = sip?.olcu || '';
  $('#fAdet').value = sip?.adet ?? '';
  $('#fHazir').value = sip?.hazir_adet ?? '0';
  $('#fBitis').value = sip?.bitis || bugunTarih();
  setSelectValue($('#fOncelik'), sip?.oncelik, 'Normal');
  setSelectValue($('#fDurum'), sip?.durum, 'Beklemede');

  const d = sip?.uretim_detay || {};
  $('#fBoy').value = d.boy || '';
  $('#fEn').value = d.en || '';
  $('#fCap').value = d.cap || '';
  $('#fKalinlik').value = d.kalinlik || '';
  $('#fKoseR').value = d.kose_radiusu || '';
  $('#fKoseT').value = d.kose_kirma || '';
  $('#fDelik').value = d.delik_capi || '';
  $('#fCamTuru').value = d.cam_turu || '';
  $('#fRodajTuru').value = d.rodaj_turu || '';
  $('#fRodajPay').value = d.rodaj_pay_mm ?? '0';
  $('#fKenarBosluk').value = d.kenar_bosluk_mm ?? '20';
  $('#fKaplamaTuru').value = d.kaplama_turu || '';
  $('#fTolerans').value = d.tolerans || '±0.3 mm';
  $('#fFirmaSipNo').value = d.firma_siparis_no || '';
  $('#fAciklama').value = d.aciklama || '';
  $('#fMusteriProb').value = d.musteri_problemleri || '';
  // Ölçü metninden doldur (boy/en boşsa)
  if ((!d.boy || !d.en) && sip?.olcu) {
    const p = String(sip.olcu).split(/[xX×*]/).map(x => x.trim()).filter(Boolean);
    if (p[0] && !$('#fBoy').value) $('#fBoy').value = p[0];
    if (p[1] && !$('#fEn').value) $('#fEn').value = p[1];
    if (p[2] && !$('#fKalinlik').value) $('#fKalinlik').value = p[2];
  }

  const secili = sip
    ? genisletRotaSecim(String(sip.rotalar || '').split(',').map(x => x.trim()).filter(Boolean))
    : [];
  buildRotaGrid(
    secili,
    mapEskiKap(sip?.istasyon_kapasiteleri || {}),
    mapEskiKap(sip?.fire_oranlari || {}),
  );

  modal.classList.remove('hidden');
  window._seciliPlaka = (d.plaka_boy && d.plaka_en)
    ? { boy: d.plaka_boy, en: d.plaka_en, stok_id: d.plaka_stok_id }
    : null;
  loadPlakaStokSecenekleri(d.plaka_stok_id);
  guncelleFireOnizleme();
  guncelleKesimPlaniUI(sip);
  setTimeout(() => $('#fMusteri')?.focus(), 50);
}

$('#modalKapat')?.addEventListener('click', () => $('#siparisModal').classList.add('hidden'));
$('#siparisModal')?.addEventListener('click', (e) => {
  if (e.target === $('#siparisModal')) $('#siparisModal').classList.add('hidden');
});
$('#fAdet')?.addEventListener('input', guncelleFireOnizleme);
$('#fHazir')?.addEventListener('input', guncelleFireOnizleme);
['fBoy', 'fEn', 'fRodajPay', 'fKenarBosluk', 'fKalinlik', 'fCamTuru'].forEach(id => {
  $(`#${id}`)?.addEventListener('input', guncelleFireOnizleme);
});

$('#btnKesimPlaniYukle')?.addEventListener('click', async () => {
  const id = $('#fId')?.value;
  if (!id) { toast('Önce siparişi kaydedin, sonra plan yükleyin', 'error'); return; }
  const file = $('#fKesimPlani')?.files?.[0];
  if (!file) { toast('Dosya seçin (DXF / DWG / PDF / PNG)', 'error'); return; }
  try {
    const fd = new FormData();
    fd.append('dosya', file);
    const res = await fetch(`/api/siparisler/${encodeURIComponent(id)}/kesim-plani`, {
      method: 'POST',
      body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.hata || 'Yükleme başarısız');
    toast(data.mesaj || 'Yüklendi', 'success');
    const s = siparisler.find(x => String(x.id) === String(id));
    if (s && data.siparis) Object.assign(s, data.siparis);
    guncelleKesimPlaniUI(data.siparis || s);
    if ($('#fKesimPlani')) $('#fKesimPlani').value = '';
  } catch (err) { toast(err.message, 'error'); }
});

$('#btnKesimPlaniSil')?.addEventListener('click', async () => {
  const id = $('#fId')?.value;
  if (!id || !confirm('Yüklü kesim planı silinsin mi?')) return;
  try {
    await api(`/api/siparisler/${encodeURIComponent(id)}/kesim-plani`, { method: 'DELETE' });
    toast('Plan silindi', 'success');
    const s = siparisler.find(x => String(x.id) === String(id));
    if (s?.uretim_detay) {
      delete s.uretim_detay.kesim_plani_dosya;
      delete s.uretim_detay.kesim_plani_orijinal;
    }
    guncelleKesimPlaniUI(s);
  } catch (err) { toast(err.message, 'error'); }
});

$('#btnRotaTum')?.addEventListener('click', () => {
  document.querySelectorAll('#rotaGrid .rota-item').forEach(item => {
    const cb = item.querySelector('.sip-rota-cb');
    if (cb) cb.checked = true;
    item.classList.add('aktif');
  });
});
$('#btnRotaTemizle')?.addEventListener('click', () => {
  document.querySelectorAll('#rotaGrid .rota-item').forEach(item => {
    const cb = item.querySelector('.sip-rota-cb');
    if (cb) cb.checked = false;
    item.classList.remove('aktif');
  });
});

window.editSiparis = (id) => {
  const s = siparisler.find(x => String(x.id) === String(id));
  if (!s) { toast('Sipariş bulunamadı — listeyi yenileyin', 'error'); return; }
  gotoSiparisler();
  openSiparisModal(s);
};

$('#siparisForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  e.stopPropagation();

  const musteri = $('#fMusteri').value.trim();
  const urun = $('#fUrun').value.trim();
  const adet = String($('#fAdet').value).trim();
  const hazir = String($('#fHazir').value || '0').trim();
  const bitis = $('#fBitis').value.trim();

  if (!musteri || !urun) { toast('Müşteri ve ürün kodu zorunlu', 'error'); return; }
  if (!/^\d+$/.test(adet) || parseInt(adet, 10) <= 0) {
    toast('Toplam adet pozitif sayı olmalı', 'error'); return;
  }
  if (!/^\d+$/.test(hazir)) { toast('Sevk edilen adet sayı olmalı', 'error'); return; }
  if (parseInt(hazir, 10) > parseInt(adet, 10)) {
    toast('Sevk edilen, toplam adetten büyük olamaz', 'error'); return;
  }
  if (!/^\d{2}\.\d{2}\.\d{4}$/.test(bitis)) {
    toast('Sevk tarihi GG.AA.YYYY formatında olmalı (ör. 15.08.2026)', 'error'); return;
  }

  const { rotalar, kapasiteler, fireOranlari } = getSeciliRota();
  if (!rotalar.length) {
    toast('En az bir proses istasyonu seçin (örn. Kesim)', 'error');
    return;
  }

  const mevcutId = $('#fId')?.value;
  const mevcutSip = mevcutId ? siparisler.find(x => String(x.id) === String(mevcutId)) : null;
  const mevcutDetay = mevcutSip?.uretim_detay || {};

  const uretim_detay = {
    boy: ($('#fBoy')?.value || '').trim(),
    en: ($('#fEn')?.value || '').trim(),
    cap: ($('#fCap')?.value || '').trim(),
    kalinlik: ($('#fKalinlik')?.value || '').trim(),
    kose_radiusu: ($('#fKoseR')?.value || '').trim(),
    kose_kirma: ($('#fKoseT')?.value || '').trim(),
    delik_capi: ($('#fDelik')?.value || '').trim(),
    cam_turu: ($('#fCamTuru')?.value || '').trim(),
    rodaj_turu: ($('#fRodajTuru')?.value || '').trim(),
    rodaj_pay_mm: ($('#fRodajPay')?.value || '').trim() || '0',
    kenar_bosluk_mm: ($('#fKenarBosluk')?.value || '').trim() || '20',
    plaka_boy: window._seciliPlaka?.boy || mevcutDetay.plaka_boy || 3210,
    plaka_en: window._seciliPlaka?.en || mevcutDetay.plaka_en || 2250,
    plaka_stok_id: window._seciliPlaka?.stok_id || $('#fPlakaStok')?.value || mevcutDetay.plaka_stok_id || '',
    kaplama_turu: ($('#fKaplamaTuru')?.value || '').trim(),
    tolerans: ($('#fTolerans')?.value || '').trim() || '±0.3 mm',
    firma_siparis_no: ($('#fFirmaSipNo')?.value || '').trim(),
    aciklama: ($('#fAciklama')?.value || '').trim(),
    musteri_problemleri: ($('#fMusteriProb')?.value || '').trim(),
  };
  if (mevcutDetay.kesim_plani_dosya) {
    uretim_detay.kesim_plani_dosya = mevcutDetay.kesim_plani_dosya;
    uretim_detay.kesim_plani_orijinal = mevcutDetay.kesim_plani_orijinal || '';
  }
  if (mevcutDetay.plaka_dusum) uretim_detay.plaka_dusum = mevcutDetay.plaka_dusum;

  let olcu = $('#fOlcu').value.trim();
  if (!olcu && (uretim_detay.boy || uretim_detay.en)) {
    olcu = [uretim_detay.boy, uretim_detay.en, uretim_detay.kalinlik].filter(Boolean).join('x');
  }

  const veri = {
    musteri,
    urun: urun.toUpperCase(),
    olcu,
    adet,
    hazir_adet: hazir,
    bitis,
    oncelik: $('#fOncelik').value || 'Normal',
    durum: $('#fDurum').value || 'Beklemede',
    rotalar: rotalar.join(', '),
    istasyon_kapasiteleri: kapasiteler,
    fire_oranlari: fireOranlari,
    uretim_detay,
  };

  const btn = e.submitter || $('#siparisForm button[type=submit]');
  if (btn) { btn.disabled = true; btn.textContent = 'Kaydediliyor...'; }

  try {
    const id = $('#fId').value;
    let kaydedilen;
    if (id) {
      kaydedilen = await api(`/api/siparisler/${encodeURIComponent(id)}`, {
        method: 'PUT', body: JSON.stringify(veri),
      });
    } else {
      kaydedilen = await api('/api/siparisler', {
        method: 'POST', body: JSON.stringify(veri),
      });
    }
    $('#siparisModal').classList.add('hidden');
    filtreleriTemizle();
    gotoSiparisler();
    toast(id ? 'Sipariş güncellendi' : 'Sipariş eklendi', 'success');
    await loadSiparisler();
    renderSiparisTablo(kaydedilen?.id);
    // AI sayfası açık değilken sadece önbelleği temizle; açılınca taze hesaplanır
    const aiBody = $('#aiSiraBody');
    if (aiBody) aiBody.innerHTML = '';
    const aiKpi = $('#aiKpi');
    if (aiKpi) aiKpi.innerHTML = '';
    const aiGun = $('#aiGunlukPlan');
    if (aiGun) aiGun.innerHTML = '';
  } catch (err) {
    toast(err.message || 'Kayıt başarısız', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '💾 Kaydet'; }
  }
});

window.deleteSiparis = async id => {
  if (!confirm('Bu siparişi silmek istediğinize emin misiniz?')) return;
  try {
    await api(`/api/siparisler/${encodeURIComponent(id)}`, { method: 'DELETE' });
    toast('Sipariş silindi', 'success');
    await loadSiparisler();
  } catch (err) { toast(err.message, 'error'); }
};

window.openSevk = id => {
  $('#sevkId').value = id;
  $('#sevkAdet').value = '';
  $('#sevkModal').classList.remove('hidden');
};
$('#sevkKapat')?.addEventListener('click', () => $('#sevkModal').classList.add('hidden'));
$('#btnSevkOnay')?.addEventListener('click', async () => {
  try {
    const adet = parseInt($('#sevkAdet').value, 10);
    if (!adet || adet <= 0) { toast('Geçerli sevk adedi girin', 'error'); return; }
    await api(`/api/siparisler/${encodeURIComponent($('#sevkId').value)}/sevk`, {
      method: 'POST', body: JSON.stringify({ adet }),
    });
    $('#sevkModal').classList.add('hidden');
    toast('Sevk işlendi', 'success');
    await loadSiparisler();
  } catch (err) { toast(err.message, 'error'); }
});

// ── Üretim aşamaları (WIP) ──
function syncAsamaNedenVisibility() {
  const fire = $('#asamaTur')?.value === 'fire';
  if ($('#asamaNedenGrup')) $('#asamaNedenGrup').style.display = fire ? '' : 'none';
}

function fillAsamaNedenSelect() {
  const sel = $('#asamaNeden');
  if (!sel) return;
  const list = (typeof FIRE_NEDENLERI !== 'undefined' && FIRE_NEDENLERI.length)
    ? FIRE_NEDENLERI
    : ['Çatlak', 'Çizik', 'Ölçü hatası', 'Diğer'];
  sel.innerHTML = list.map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('');
}

function renderAsamaPanel(ozet) {
  $('#asamaSiparisId').value = ozet.siparis_id;
  $('#asamaBaslik').textContent = `Aşama · ${ozet.musteri} / ${ozet.urun}`;
  $('#asamaOzetSatir').textContent =
    `Sipariş ${ozet.adet} adet · Sevk ${ozet.hazir_adet} · Aktif: ${ozet.aktif_istasyon}` +
    (ozet.aktif_stok ? ` (${ozet.aktif_stok} stok)` : '') +
    ` · Durum: ${ozet.durum}`;

  const body = $('#asamaBody');
  body.innerHTML = '';
  (ozet.asamalar || []).forEach(a => {
    const aktif = a.istasyon === ozet.aktif_istasyon && a.stok > 0;
    const tr = document.createElement('tr');
    if (aktif) tr.classList.add('asama-aktif-row');
    tr.innerHTML = `
      <td>${a.sira}</td>
      <td><strong>${escHtml(a.istasyon)}</strong></td>
      <td>${a.gelen}</td>
      <td>${a.cikan}</td>
      <td style="color:#b45309;font-weight:600">${a.fire}</td>
      <td class="asama-stok">${a.stok}</td>
      <td>
        <button type="button" class="btn btn-sm btn-outline" data-hizli-ist="${escHtml(a.istasyon)}" data-hizli-tur="giris">+Giriş</button>
        <button type="button" class="btn btn-sm btn-success" data-hizli-ist="${escHtml(a.istasyon)}" data-hizli-tur="cikis">Çıktı</button>
        <button type="button" class="btn btn-sm btn-danger" data-hizli-ist="${escHtml(a.istasyon)}" data-hizli-tur="fire">Fire</button>
      </td>`;
    body.appendChild(tr);
  });

  body.querySelectorAll('[data-hizli-ist]').forEach(btn => {
    btn.onclick = () => {
      $('#asamaIstasyon').value = btn.dataset.hizliIst;
      $('#asamaTur').value = btn.dataset.hizliTur;
      syncAsamaNedenVisibility();
      $('#asamaAdet').focus();
      $('#asamaAdet').select();
    };
  });

  const istSel = $('#asamaIstasyon');
  const onceki = istSel.value;
  istSel.innerHTML = (ozet.rotalar || []).map(m =>
    `<option value="${escHtml(m)}">${escHtml(m)}</option>`
  ).join('');
  if (onceki && [...istSel.options].some(o => o.value === onceki)) istSel.value = onceki;
  else if (ozet.aktif_istasyon && ozet.rotalar.includes(ozet.aktif_istasyon)) {
    istSel.value = ozet.aktif_istasyon;
  }

  const hb = $('#asamaHareketBody');
  hb.innerHTML = '';
  (ozet.hareketler || []).forEach(h => {
    const turCls = `asama-tur-${h.tur}`;
    const turLabel = h.tur === 'giris' ? 'Giriş' : h.tur === 'cikis' ? 'Çıktı' : 'Fire';
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${escHtml(h.zaman)}</td><td>${escHtml(h.istasyon)}</td>
      <td class="${turCls}">${turLabel}</td><td>${h.adet}</td>
      <td>${escHtml(h.neden || '-')}</td><td>${escHtml(h.not_metin || '-')}</td>
      <td>${escHtml(h.kullanici || '-')}</td>`;
    hb.appendChild(tr);
  });
  if (!(ozet.hareketler || []).length) {
    hb.innerHTML = '<tr><td colspan="7" style="color:#64748b">Henüz hareket yok. İlk istasyona Giriş kaydedin.</td></tr>';
  }
}

window.openAsamaModal = async (id) => {
  try {
    $('#asamaBaslik').textContent = 'Aşama yükleniyor…';
    $('#asamaModal').classList.remove('hidden');
    fillAsamaNedenSelect();
    syncAsamaNedenVisibility();
    const ozet = await api(`/api/siparisler/${encodeURIComponent(id)}/asama`);
    renderAsamaPanel(ozet);
  } catch (err) {
    $('#asamaModal').classList.add('hidden');
    toast(err.message || 'Aşama yüklenemedi', 'error');
  }
};

$('#asamaKapat')?.addEventListener('click', () => $('#asamaModal').classList.add('hidden'));
$('#asamaModal')?.addEventListener('click', (e) => {
  if (e.target === $('#asamaModal')) $('#asamaModal').classList.add('hidden');
});
$('#asamaTur')?.addEventListener('change', syncAsamaNedenVisibility);

$('#btnAsamaKaydet')?.addEventListener('click', async () => {
  const id = $('#asamaSiparisId').value;
  const tur = $('#asamaTur').value;
  const payload = {
    istasyon: $('#asamaIstasyon').value,
    tur,
    adet: parseInt($('#asamaAdet').value, 10),
    neden: tur === 'fire' ? $('#asamaNeden').value : '',
    not: ($('#asamaNot').value || '').trim(),
    sonraki_aktar: true,
  };
  if (!payload.istasyon) { toast('İstasyon seçin', 'error'); return; }
  if (!payload.adet || payload.adet <= 0) { toast('Geçerli adet girin', 'error'); return; }
  try {
    const ozet = await api(`/api/siparisler/${encodeURIComponent(id)}/asama`, {
      method: 'POST', body: JSON.stringify(payload),
    });
    toast('Hareket kaydedildi', 'success');
    $('#asamaNot').value = '';
    renderAsamaPanel(ozet);
    // Listeyi arka planda yenile; modal kilitlenmesin
    loadSiparisler().catch(() => {});
  } catch (err) {
    toast(err.message || 'Kayıt başarısız', 'error');
  }
});

// Excel & PDF
$('#btnExcelDisari')?.addEventListener('click', () => window.open('/api/excel/disari'));
$('#excelInput')?.addEventListener('change', async e => {
  const f=e.target.files[0]; if(!f) return;
  const fd=new FormData(); fd.append('dosya',f);
  try { const r=await fetch('/api/excel/iceri',{method:'POST',body:fd}); const d=await r.json();
    if(!r.ok) throw new Error(d.hata); toast(d.mesaj,'success'); await loadSiparisler();
  } catch(err){ toast(err.message,'error'); } e.target.value='';
});
$('#btnPdfRapor')?.addEventListener('click', () => window.open('/api/rapor/pdf'));

// Çizelgeleme
async function runCizelgeleme() {
  try {
    toast('Çizelgeleme çalışıyor...');
    cizelge = await api('/api/cizelgeleme',{method:'POST'});
    renderGunListesi(); updateDarBogazBadge(); loadBildirimler();
    if(cizelge.gunler.length){ selectGun(0); renderKapasiteChart(cizelge.gunler[0]); }
    toast(cizelge.dar_bogaz_sayisi?`${cizelge.dar_bogaz_sayisi} sorun (sevk/kapasite)!`:'Tamamlandı — işlem sırası açılıyor', cizelge.dar_bogaz_sayisi?'error':'success');
    gotoPage('gantt');
    setTimeout(() => renderGantt(), 80);
  } catch(err){ toast(err.message,'error'); }
}
$('#btnCizelgele')?.addEventListener('click', runCizelgeleme);

function renderGunListesi() {
  const ul=$('#gunListesi'); ul.innerHTML='';
  if(!cizelge?.gunler?.length){ ul.innerHTML='<li style="padding:12px;color:#64748b">Plan yok</li>'; return; }
  cizelge.gunler.forEach((g,i) => {
    const li=document.createElement('li');
    li.innerHTML=`${g.gun}<div class="meta">${g.is_sayisi} iş${g.dar_bogaz?`, ${g.dar_bogaz} sorun`:''}</div>`;
    li.onclick=()=>selectGun(i); ul.appendChild(li);
  });
}

function selectGun(index) {
  $$('#gunListesi li').forEach((li,i)=>li.classList.toggle('active',i===index));
  const gun=cizelge.gunler[index]; if(!gun) return;
  $('#secilenGunBaslik').textContent=gun.gun;
  $('#dolulukBarlari').innerHTML='';
  Object.entries(gun.doluluk_ozet).sort((a,b)=>b[1]-a[1]).forEach(([m,pct]) => {
    $('#dolulukBarlari').innerHTML+=`<div class="doluluk-bar"><div class="doluluk-bar-label"><span>${m}</span><span>%${pct}</span></div>
      <div class="doluluk-track"><div class="doluluk-fill ${dolulukFillClass(pct)}" style="width:${Math.min(100,pct)}%"></div></div></div>`;
  });
  $('#gunDetayBody').innerHTML='';
  gun.kayitlar.forEach(k => { $('#gunDetayBody').innerHTML+=`<tr>
    <td><span class="rota-no">${k.islem_sira||'-'}</span> / ${k.rota_toplam||'-'}</td>
    <td>${k.makine}</td><td>${k.musteri}</td><td>${k.urun}</td>
    <td>${k.adet}</td><td class="${tagClass(k.tag)}" title="${escHtml(tagLabel(k.tag))}">${escHtml(k.yuk || tagLabel(k.tag))}</td><td>${k.doluluk}</td></tr>`; });
  renderKapasiteChart(gun);
  const uy=$('#uyariListesi');
  if(cizelge.uyarilar?.length){ uy.classList.remove('hidden'); uy.innerHTML='⚠ '+cizelge.uyarilar.join('<br>⚠ '); }
  else uy.classList.add('hidden');
}

// Gantt + İşlem Sırası
function renderGantt() {
  const empty = $('#ganttEmpty');
  const panel = $('#islemSirasiPanel');
  const list = $('#islemSirasiList');
  const timelineWrap = $('#ganttTimelineWrap');
  const timeline = $('#ganttTimeline');
  const grupluEl = $('#ganttMakineGruplu');
  const frappeEl = $('#ganttChart');

  if (!cizelge || !(cizelge.islem_sirasi?.length || cizelge.gantt?.length)) {
    empty?.classList.remove('hidden');
    panel?.classList.add('hidden');
    timelineWrap?.classList.add('hidden');
    grupluEl?.classList.add('hidden');
    frappeEl?.classList.add('hidden');
    return;
  }

  empty?.classList.add('hidden');

  // 1) Sipariş bazlı işlem sırası kartları
  const siralar = cizelge.islem_sirasi || [];
  if (siralar.length && panel && list) {
    panel.classList.remove('hidden');
    list.innerHTML = siralar.map(sip => {
      const adimlarHtml = sip.adimlar.map((a, idx) => {
        const tarih = (a.tarihler || []).join(', ') || '-';
        const ok = idx < sip.adimlar.length - 1 ? '<span class="flow-ok">→</span>' : '';
        return `<div class="flow-step tag-${(a.tag||'normal').toLowerCase()}" title="${escHtml(tagLabel(a.tag))}">
          <div class="flow-no">${a.sira}</div>
          <div class="flow-body">
            <strong>${escHtml(a.makine)}</strong>
            <span>${escHtml(tarih)}</span>
            <small>${a.adet} adet${a.tag && a.tag !== 'normal' && a.tag !== 'Normal' ? ` · ${escHtml(tagLabel(a.tag))}` : ''}</small>
          </div>
        </div>${ok}`;
      }).join('');
      return `<div class="islem-kart">
        <div class="islem-kart-baslik">
          <div><strong>${escHtml(sip.musteri)}</strong> — ${escHtml(sip.urun)}</div>
          <div class="islem-meta">${oncelikBadge(sip.oncelik||'Normal')} Sevk: ${escHtml(sip.sevk_hedef||'-')}</div>
        </div>
        <div class="flow-row">${adimlarHtml}</div>
        <div class="islem-rota-metin">${escHtml(sip.rota_metin)}</div>
      </div>`;
    }).join('');
  } else {
    panel?.classList.add('hidden');
  }

  // 2) Basit zaman çizelgesi (güvenilir HTML Gantt)
  if (timeline && timelineWrap && cizelge.gantt?.length) {
    timelineWrap.classList.remove('hidden');
    renderTimelineGantt(timeline, cizelge.gantt);
  }

  // 3) Makine özeti
  if (grupluEl) {
    const gruplar = cizelge.gantt_gruplu || {};
    grupluEl.classList.remove('hidden');
    grupluEl.innerHTML = '<h4 class="section-title">Makine Özeti</h4>' +
      Object.entries(gruplar).map(([makine, gorevler]) => {
        const dar = gorevler.filter(g => isSorunTag(g.tag) || g.custom_class === 'gantt-red' || g.custom_class === 'gantt-orange').length;
        const yogun = gorevler.filter(g => isYogunTag(g.tag) || g.custom_class === 'gantt-yellow').length;
        const ekstra = [];
        if (dar) ekstra.push(`${dar} sorun`);
        if (yogun) ekstra.push(`${yogun} yoğun`);
        return `<div class="makine-gantt-row"><strong>${escHtml(makine)}</strong> — ${gorevler.length} iş${ekstra.length ? ` <span style="color:#ef4444">(${ekstra.join(', ')})</span>` : ''}</div>`;
      }).join('');
  }

  // 4) Frappe Gantt (opsiyonel — hata olursa sessizce geç)
  if (frappeEl && typeof Gantt !== 'undefined' && cizelge.gantt?.length) {
    try {
      frappeEl.classList.remove('hidden');
      frappeEl.innerHTML = '';
      const tasks = cizelge.gantt.map(t => ({
        id: t.id, name: t.name, start: t.start, end: t.end,
        progress: t.progress || 100, custom_class: t.custom_class || 'gantt-green',
      }));
      ganttInstance = new Gantt(frappeEl, tasks, { view_mode: 'Day', bar_height: 22, padding: 16 });
    } catch (e) {
      frappeEl.classList.add('hidden');
      console.warn('Frappe Gantt yüklenemedi, timeline kullanılıyor.', e);
    }
  }
}

function renderTimelineGantt(container, ganttTasks) {
  const dates = [...new Set(ganttTasks.map(t => t.start || t.tarih).filter(Boolean))].sort();
  if (!dates.length) {
    container.innerHTML = '<p class="hint">Tarih verisi yok.</p>';
    return;
  }

  // Sipariş satırları grupla
  const bySiparis = {};
  ganttTasks.forEach(t => {
    const key = t.siparis_id || `${t.musteri}|${t.urun}`;
    if (!bySiparis[key]) bySiparis[key] = { musteri: t.musteri, urun: t.urun, items: [] };
    bySiparis[key].items.push(t);
  });

  let html = `<div class="tl-header"><div class="tl-label">Sipariş / İşlem</div><div class="tl-days">${dates.map(d => {
    const tr = d.includes('-') ? d.split('-').reverse().join('.') : d;
    return `<div class="tl-day">${tr}</div>`;
  }).join('')}</div></div>`;

  Object.values(bySiparis).forEach(sip => {
    const items = sip.items.sort((a, b) => (a.islem_sira || 0) - (b.islem_sira || 0) || String(a.start).localeCompare(String(b.start)));
    html += `<div class="tl-row"><div class="tl-label"><strong>${escHtml(sip.musteri||'')}</strong><br><small>${escHtml(sip.urun||'')}</small></div><div class="tl-days">`;
    dates.forEach(d => {
      const gunIs = items.filter(t => (t.start === d) || (t.tarih && t.tarih.split('.').reverse().join('-') === d) || t.tarih === d);
      if (!gunIs.length) {
        html += '<div class="tl-cell"></div>';
        return;
      }
      html += `<div class="tl-cell">${gunIs.map(t => {
        const cls = isSorunTag(t.tag) || t.custom_class === 'gantt-red' || t.custom_class === 'gantt-orange'
          ? (t.tag === 'kapasite' || t.custom_class === 'gantt-orange' ? 'tl-bar orange' : 'tl-bar red')
          : isYogunTag(t.tag) || t.custom_class === 'gantt-yellow' ? 'tl-bar yellow' : 'tl-bar green';
        return `<div class="${cls}" title="${escHtml(t.makine)} — ${t.adet} adet · ${escHtml(tagLabel(t.tag) || t.durum || '')}">${t.islem_sira||''}. ${escHtml(t.makine)}</div>`;
      }).join('')}</div>`;
    });
    html += '</div></div>';
  });

  container.innerHTML = html;
}

// Simülasyon
$('#btnSimulasyon')?.addEventListener('click', async () => {
  try {
    const sonuc = await api('/api/simulasyon',{method:'POST',body:JSON.stringify({
      hizli_test:true, musteri:$('#simMusteri').value, urun:$('#simUrun').value,
      adet:parseInt($('#simAdet').value), bitis:$('#simBitis').value||bugunTarih(),
      oncelik:$('#simOncelik').value, rotalar:$('#simRota').value })});
    const el=$('#simSonuc'); el.classList.remove('hidden');
    el.innerHTML=`<h4>Sonuç ${sonuc.simulasyon?'(Simülasyon — kaydedilmedi)':''}</h4>
      <p>Sorun: <strong>${sonuc.dar_bogaz_sayisi}</strong> | Planlanan gün: <strong>${sonuc.gunler.length}</strong></p>
      ${(() => {
        const es = sonuc.etiket_sayilari || {};
        const det = [];
        if (es.sevk_gecikti) det.push(`${es.sevk_gecikti} sevk gecikti`);
        if (es.kapasite) det.push(`${es.kapasite} kapasite yetersiz`);
        if (es.yogun) det.push(`${es.yogun} yoğun`);
        return det.length ? `<p class="hint">${det.join(' · ')}</p>` : '';
      })()}
      ${sonuc.uyarilar?.length?`<p style="color:#92400e">⚠ ${sonuc.uyarilar.join('<br>⚠ ')}</p>`:'<p style="color:#166534">✅ Kapasite / sevk yeterli görünüyor.</p>'}`;
  } catch(err){ toast(err.message,'error'); }
});

// Log
async function loadLog() {
  const logs = await api('/api/log');
  $('#logBody').innerHTML = logs.map(l =>
    `<tr><td>${l.zaman?.replace('T',' ')}</td><td>${l.kullanici}</td><td>${l.islem}</td><td>${l.detay||''}</td></tr>`).join('');
}

// Bildirimler
async function loadBildirimler() {
  const list = await api('/api/bildirimler?okunmamis=1');
  const sayac = $('#bildirimSayac');
  if(list.length){ sayac.textContent=list.length; sayac.classList.remove('hidden'); }
  else sayac.classList.add('hidden');
}

$('#btnBildirim')?.addEventListener('click', async () => {
  const list = await api('/api/bildirimler');
  const panel = $('#bildirimPanel');
  panel.innerHTML = list.length ? list.map(b =>
    `<div class="bildirim-item ${b.okundu?'':'unread'}"><strong>${b.baslik}</strong><p>${b.mesaj}</p><small>${b.olusturma?.replace('T',' ')}</small></div>`).join('')
    : '<p style="padding:12px">Bildirim yok</p>';
  panel.innerHTML += '<button class="btn btn-sm btn-outline" id="btnOkuTumu" style="margin:8px">Tümünü Okundu İşaretle</button>';
  panel.classList.toggle('hidden');
  $('#btnOkuTumu')?.addEventListener('click', async () => {
    await api('/api/bildirimler/oku-tumu',{method:'POST'}); panel.classList.add('hidden'); loadBildirimler();
  });
});

// Ayarlar
async function loadAyarlar() {
  const ayar = await api('/api/ayarlar');
  varsayilanKap = ayar.varsayilan_kapasiteler || {};
  // Yeni sipariş formu için başlangıç fire önerisi (Ayarlar'da UI yok)
  varsayilanFire = ayar.fire_oranlari || {};
  const bolum = ayar.bolum_kapasiteleri || {};
  $('#ayarGrid').innerHTML = MAKINELER.map(m =>
    `<div class="ayar-item"><label>${m} <small style="color:#64748b">(sipariş varsayılan hızı)</small></label>
     <input type="number" id="ayar_${m}" value="${varsayilanKap[m]||500}" min="1"></div>`).join('');
  if ($('#bolumKesimKap')) $('#bolumKesimKap').value = bolum.Kesim || 1500;
  if ($('#aiBolumKap')) $('#aiBolumKap').value = bolum.Kesim || 1500;
  if(ROL==='admin') loadYedekler();
}

$('#btnBolumKaydet')?.addEventListener('click', async () => {
  const kap = parseInt($('#bolumKesimKap').value) || 1500;
  try {
    await api('/api/ayarlar', { method:'PUT', body: JSON.stringify({ bolum_kapasiteleri: { Kesim: kap } }) });
    if ($('#aiBolumKap')) $('#aiBolumKap').value = kap;
    toast('Kesim bölüm kapasitesi kaydedildi: ' + kap, 'success');
  } catch (err) { toast(err.message, 'error'); }
});

// ── Firebase senkron ───────────────────────────────────────
function syncDurumYaz(d) {
  const chip = $('#btnSyncDurum');
  const label = $('#syncLabel');
  const ozet = $('#syncAyarOzet');
  if (!chip || !label) return;
  chip.classList.remove('online', 'offline', 'error', 'pending');
  const bek = d.bekleyen || 0;
  let cls = 'offline';
  let txt = 'Çevrimdışı';
  if (!d.firebase_enabled) {
    cls = 'error'; txt = 'Sync kapalı';
  } else if (!d.credentials) {
    cls = 'error'; txt = 'Anahtar yok';
  } else if (d.son_hata || d.init_hata) {
    cls = 'error'; txt = bek ? `Hata · ${bek} bekliyor` : 'Sync hata';
  } else if (!d.online) {
    cls = 'offline'; txt = bek ? `Çevrimdışı · ${bek}` : 'Çevrimdışı';
  } else if (bek > 0) {
    cls = 'pending'; txt = `${bek} bekliyor`;
  } else {
    cls = 'online'; txt = 'Senkron';
  }
  chip.classList.add(cls);
  label.textContent = txt;
  chip.title = d.son_mesaj || d.son_hata || d.init_hata || txt;
  if (ozet) {
    ozet.innerHTML = [
      `<div><strong>Yol:</strong> ${escHtml(d.path || 'byc/v1')}</div>`,
      `<div><strong>İnternet:</strong> ${d.online ? 'Var' : 'Yok'}</div>`,
      `<div><strong>Firebase anahtar:</strong> ${d.credentials ? 'Tamam' : 'Eksik (FIREBASE_KURULUM.md)'}</div>`,
      `<div><strong>Hazır:</strong> ${d.hazir ? 'Evet' : 'Hayır'}${d.init_hata ? ` — ${escHtml(d.init_hata)}` : ''}</div>`,
      `<div><strong>Bekleyen:</strong> ${bek} · Hatalı: ${d.hatali || 0}</div>`,
      `<div><strong>Son seed:</strong> ${escHtml(d.son_seed || '—')}</div>`,
      `<div><strong>Son sync:</strong> ${escHtml(d.son_sync || '—')}</div>`,
      `<div><strong>Mesaj:</strong> ${escHtml(d.son_mesaj || d.son_hata || '—')}</div>`,
    ].join('');
  }
}

async function loadSyncDurum() {
  try {
    const d = await api('/api/sync/durum');
    syncDurumYaz(d);
  } catch (_) { /* login dışı */ }
}

async function syncSimdi(forceQueue) {
  try {
    toast(forceQueue ? 'Yerel kayıtlar kuyruğa alınıyor…' : 'Senkron başlıyor…');
    const d = await api('/api/sync/now', {
      method: 'POST',
      body: JSON.stringify({ force_queue_all: !!forceQueue }),
    });
    syncDurumYaz(d);
    toast(d.mesaj || (d.ok ? 'Senkron tamam' : 'Senkron hatası'), d.ok ? 'success' : 'error');
    if (d.ok && d.online) await loadSiparisler();
  } catch (err) {
    toast(err.message, 'error');
  }
}

$('#btnSyncDurum')?.addEventListener('click', () => syncSimdi(false));
$('#btnSyncNow')?.addEventListener('click', () => syncSimdi(false));
$('#btnSyncQueueAll')?.addEventListener('click', () => syncSimdi(true));
$('#btnSyncSeed')?.addEventListener('click', async () => {
  if (!confirm('Tüm yerel sipariş ve aşama hareketleri Firebase byc/v1 altına yazılsın mı?\n(Mobil/web bu yolu kullanacak)')) return;
  try {
    toast('Firebase temiz aktarım başlıyor…');
    const d = await api('/api/sync/seed', { method: 'POST', body: '{}' });
    syncDurumYaz({ ...(await api('/api/sync/durum')), son_mesaj: d.mesaj });
    toast(d.mesaj || 'Aktarım tamam', d.ok ? 'success' : 'error');
  } catch (err) {
    toast(err.message, 'error');
  }
});
setInterval(loadSyncDurum, 20000);

// ── AI Kesim Öneri ─────────────────────────────────────────
async function loadAiKesim(zorla = true) {
  // Her açılışta yeniden hesapla — fire oranı değişince eski sayılar kalmasın
  await runAiKesim();
}

async function runAiKesim() {
  try {
    toast('AI kesim önerisi hesaplanıyor...');
    const plan = await api('/api/ai/kesim-oneri', {
      method: 'POST',
      body: JSON.stringify({
        bolum_kapasite: parseInt($('#aiBolumKap')?.value) || 1500,
        gun_sayisi: parseInt($('#aiGunSayisi')?.value) || 15,
      }),
    });
    renderAiKesim(plan);
    window._sonAiPlan = plan;
    toast('Kesim önerisi hazır', 'success');
  } catch (err) { toast(err.message, 'error'); }
}

function renderAiKesim(plan) {
  const kut = $('#aiOneriKutu');
  if (kut) {
    kut.classList.remove('hidden');
    kut.innerHTML = (plan.ai_oneriler || []).map(o => `<div class="ai-line">💡 ${escHtml(o)}</div>`).join('');
  }

  const kpi = $('#aiKpi');
  if (kpi) {
    const o = plan.ozet || {};
    kpi.innerHTML = `
      <div class="kpi-card"><span class="kpi-label">Cam Sayısı</span><span class="kpi-value">${o.cam_sayisi||0}</span></div>
      <div class="kpi-card"><span class="kpi-label">Net İhtiyaç</span><span class="kpi-value">${o.toplam_net||0}</span></div>
      <div class="kpi-card warning"><span class="kpi-label">Fire Adedi</span><span class="kpi-value">+${o.toplam_fire||0}</span></div>
      <div class="kpi-card danger"><span class="kpi-label">Kesilecek Toplam</span><span class="kpi-value">${o.toplam_kesim_hedef||0}</span></div>
      <div class="kpi-card"><span class="kpi-label">Bölüm Kapasite</span><span class="kpi-value">${plan.bolum_kapasite}</span></div>`;
  }

  const pKpi = $('#aiPlakaKpi');
  if (pKpi) {
    const po = plan.plaka_ozet || {};
    pKpi.innerHTML = `
      <div class="kpi-card"><span class="kpi-label">Plaka Boyutu</span><span class="kpi-value" style="font-size:18px">${escHtml(po.standart||'3210×2250')}</span></div>
      <div class="kpi-card warning"><span class="kpi-label">Düşülecek Plaka</span><span class="kpi-value">${po.toplam_plaka_ihtiyac||0}</span></div>
      <div class="kpi-card ${po.eksik_olcu?'danger':''}"><span class="kpi-label">Ölçüsü Eksik</span><span class="kpi-value">${po.eksik_olcu||0}</span></div>`;
  }

  const tbody = $('#aiSiraBody');
  if (tbody) {
    tbody.innerHTML = (plan.sira || []).map(c => {
      const p = c.plaka || {};
      const plakaHucre = !p.olcu_var
        ? '<span style="color:#94a3b8">ölçü yok</span>'
        : (p.plaka_basi
          ? `<strong>${p.plaka_basi}</strong> <small>(${escHtml(p.yon||'')}, R${p.rodaj_mm||0})</small>`
          : `<span style="color:#b91c1c">${escHtml(p.hata||'sığmaz')}</span>`);
      const iht = p.plaka_ihtiyac != null ? p.plaka_ihtiyac : '-';
      const stokRenk = p.stok_yeterli === false ? '#b91c1c' : '#15803d';
      const stokTxt = p.olcu_var
        ? `<span style="color:${stokRenk};font-weight:600">${p.stok_adet??0}</span>${p.once_dusuldu?` <small>(-${p.once_dusuldu}✓)</small>`:''}`
        : '-';
      return `
      <tr>
        <td><span class="rota-no">${c.sira}</span></td>
        <td><strong>${escHtml(c.musteri)}</strong></td>
        <td>${escHtml(c.urun)}</td>
        <td>${c.net_kalan}</td>
        <td style="color:#b45309;font-weight:600">+${c.fire_adet}</td>
        <td><strong style="color:#1d4ed8">${c.kesilmesi_gereken}</strong></td>
        <td style="font-size:11px;color:#475569">${escHtml(c.fire_pct_ozet || '-')}</td>
        <td style="font-size:12px">${plakaHucre}</td>
        <td><strong>${iht}</strong></td>
        <td>${stokTxt}</td>
        <td><button type="button" class="btn btn-sm btn-outline" data-sema="${escHtml(String(c.siparis_id))}">Şema</button></td>
        <td>${c.cam_gunluk_hiz}</td>
        <td>${c.tahmini_gun}</td>
        <td>${oncelikBadge(c.oncelik)}</td>
        <td style="font-size:12px;color:#475569">${escHtml(c.fire_ozet)} · ${escHtml(c.neden)}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="15">Kesimde bekleyen sipariş yok</td></tr>';
    tbody.querySelectorAll('[data-sema]').forEach(btn => {
      btn.onclick = () => openKesimSema(btn.dataset.sema);
    });
  }

  const gunDiv = $('#aiGunlukPlan');
  if (gunDiv) {
    gunDiv.innerHTML = (plan.gunler || []).map(g => `
      <div class="ai-gun-kart">
        <div class="ai-gun-baslik">
          <strong>${escHtml(g.tarih)}</strong>
          <span>Bölüm: ${g.kullanilan} / ${g.bolum_kapasite} · Kalan kapasite: ${g.kalan_kapasite}</span>
        </div>
        <div class="doluluk-track" style="margin:8px 0 12px">
          <div class="doluluk-fill ${g.kullanilan/g.bolum_kapasite>0.95?'fill-red':g.kullanilan/g.bolum_kapasite>0.7?'fill-yellow':'fill-green'}"
               style="width:${Math.min(100, Math.round(100*g.kullanilan/g.bolum_kapasite))}%"></div>
        </div>
        <table class="data-table"><thead><tr>
          <th>Sıra</th><th>Cam</th><th>Bugün Kes</th><th>Net</th><th>Fire</th><th>Cam Hızı</th><th>Hedef Kalan</th>
        </tr></thead><tbody>
          ${(g.satirlar||[]).map(s => `<tr>
            <td>${s.sira}</td>
            <td><strong>${escHtml(s.musteri)}</strong> — ${escHtml(s.urun)}</td>
            <td><strong>${s.adet}</strong></td>
            <td>${s.net_kalan}</td>
            <td>+${s.fire_adet}</td>
            <td>${s.cam_gunluk_hiz}/gün</td>
            <td>${s.kalan_sonra}</td>
          </tr>`).join('')}
        </tbody></table>
      </div>`).join('') || '<p class="hint">Dağıtılacak iş yok.</p>';

    if (plan.tamamlanamayan?.length) {
      gunDiv.innerHTML += `<div class="uyari-kutu" style="margin-top:12px">
        <strong>Tamamlanamayan camlar</strong>
        ${plan.tamamlanamayan.map(t => `<div>• ${escHtml(t.musteri)} / ${escHtml(t.urun)} — kalan kesim ${t.kalan_kesim}: ${escHtml(t.oneri)}</div>`).join('')}
      </div>`;
    }
  }
}

$('#btnAiKesim')?.addEventListener('click', runAiKesim);

async function openKesimSema(siparisId) {
  const modal = $('#kesimSemaModal');
  if (!modal) return;
  try {
    const oz = await api(`/api/siparisler/${encodeURIComponent(siparisId)}/kesim-sema`);
    const sip = siparisler.find(x => String(x.id) === String(siparisId));
    $('#kesimSemaBaslik').textContent = `Kesim Şeması — ${sip?.musteri || ''} / ${sip?.urun || siparisId}`;
    const ekstra = oz.ekstra_serit ? ` · fire şerit +${oz.ekstra_serit}` : '';
    $('#kesimSemaOzet').innerHTML = oz.olcu_var
      ? `Kenar boşluk <strong>${oz.kenar_bosluk} mm</strong> · kullanılabilir ${oz.kullanilabilir_boy}×${oz.kullanilabilir_en} · `
        + `kesim ${oz.kesim_boy}×${oz.kesim_en} (rodaj ${oz.rodaj_mm}) · `
        + `<strong>${oz.plaka_basi}</strong> adet/plaka (${escHtml(oz.yon)}${ekstra}) · verim %${oz.verim_yuzde}`
        + (oz.hata ? ` · <span style="color:#b91c1c">${escHtml(oz.hata)}</span>` : '')
      : 'Boy/en eksik — şema çizilemedi.';
    $('#kesimSemaSvg').innerHTML = oz.svg || '<p class="hint">Şema yok</p>';
    const cad = $('#kesimSemaCadIndir');
    if (oz.kesim_plani_dosya) {
      cad?.classList.remove('hidden');
      if (cad) cad.href = `/api/siparisler/${encodeURIComponent(siparisId)}/kesim-plani`;
    } else {
      cad?.classList.add('hidden');
    }
    modal.classList.remove('hidden');
  } catch (err) {
    toast(err.message || 'Şema yüklenemedi', 'error');
  }
}
$('#kesimSemaKapat')?.addEventListener('click', () => $('#kesimSemaModal')?.classList.add('hidden'));
$('#kesimSemaModal')?.addEventListener('click', (e) => {
  if (e.target === $('#kesimSemaModal')) $('#kesimSemaModal').classList.add('hidden');
});
$('#btnKesimSemaYazdir')?.addEventListener('click', () => {
  const svg = $('#kesimSemaSvg')?.innerHTML || '';
  const ozet = $('#kesimSemaOzet')?.innerHTML || '';
  const baslik = $('#kesimSemaBaslik')?.textContent || 'Kesim Şeması';
  const w = window.open('', '_blank', 'width=900,height=700');
  if (!w) { toast('Pop-up engellendi', 'error'); return; }
  w.document.write(`<!DOCTYPE html><html><head><title>${escHtml(baslik)}</title>
    <style>body{font-family:Segoe UI,Arial;padding:16px;color:#0f172a}
    h1{font-size:18px;margin:0 0 8px} .ozet{margin-bottom:12px;font-size:13px}
    @media print{button{display:none}}</style></head><body>
    <h1>${escHtml(baslik)}</h1><div class="ozet">${ozet}</div>${svg}
    <p style="margin-top:16px;font-size:11px;color:#64748b">BYC Üretim Planlama — kenar boşluk + rodaj optimize yerleşim</p>
    <script>window.onload=()=>window.print()<\/script></body></html>`);
  w.document.close();
});

$('#btnPlakaDus')?.addEventListener('click', async () => {
  const po = window._sonAiPlan?.plaka_ozet?.toplam_plaka_ihtiyac;
  const msg = (po != null)
    ? `AI planına göre yaklaşık ${po} plaka stoktan düşülecek.\n\nCam türü + kalınlık eşleşmeli. Devam?`
    : 'Kesimde bekleyen siparişler için plaka stoktan düşülecek. Devam?';
  if (!confirm(msg)) return;
  try {
    const sonuc = await api('/api/ai/plaka-dus', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    toast(sonuc.mesaj || 'Stok güncellendi', 'success');
    if (sonuc.hatalar?.length) toast(sonuc.hatalar.join(' · '), 'error');
    await runAiKesim();
  } catch (err) {
    const detay = err.detay || err.data?.detay;
    toast(detay ? `${err.message}\n${(detay || []).join('\n')}` : (err.message || 'Düşüm başarısız'), 'error');
  }
});

async function loadYedekler() {
  const list = await api('/api/yedek');
  $('#yedekListesi').innerHTML = list.map(y =>
    `<div class="yedek-item">${y.dosya} — ${y.tarih} (${y.boyut_kb} KB)
    <button class="btn btn-sm btn-outline" onclick="geriYukle('${y.dosya}')">Geri Yükle</button></div>`).join('') || '<p>Yedek yok</p>';
}

window.geriYukle = async dosya => {
  if(!confirm('Mevcut veriler yedeklenip geri yüklenecek. Emin misiniz?')) return;
  await api('/api/yedek/geri-yukle',{method:'POST',body:JSON.stringify({dosya})});
  toast('Geri yüklendi','success'); location.reload();
};

$('#btnAyarKaydet')?.addEventListener('click', async () => {
  const kap={}; MAKINELER.forEach(m=>{kap[m]=parseInt($(`#ayar_${m}`).value)||500;});
  try { await api('/api/ayarlar',{method:'PUT',body:JSON.stringify({varsayilan_kapasiteler:kap})}); toast('Kaydedildi','success'); }
  catch(err){ toast(err.message,'error'); }
});

$('#btnSifreDegistir')?.addEventListener('click', async () => {
  const s=$('#yeniSifre').value; if(!s||s.length<4){ toast('En az 4 karakter','error'); return; }
  await api('/api/sifre-degistir',{method:'POST',body:JSON.stringify({yeni_sifre:s})});
  toast('Şifre değiştirildi','success'); $('#yeniSifre').value='';
});

$('#btnYedekAl')?.addEventListener('click', async () => {
  const r=await api('/api/yedek',{method:'POST'}); toast(r.mesaj,'success'); loadYedekler();
});

$('#btnTumunuSil')?.addEventListener('click', async () => {
  if(!confirm('TÜM siparişler silinecek!')) return;
  await api('/api/siparisler/tumunu-sil',{method:'DELETE'}); toast('Silindi','success'); await loadSiparisler();
});

// ── Plaka stok ──
let _plakaStokListe = [];

async function loadPlakaStokSecenekleri(seciliId) {
  const sel = $('#fPlakaStok');
  if (!sel) return;
  try {
    const data = await api('/api/plaka-stok');
    _plakaStokListe = data.liste || [];
    const esik = (data.ozet || {}).uyari_esik || 10;
    sel.innerHTML = '<option value="">— Plaka seçin (ölçü stoktan gelir) —</option>'
      + _plakaStokListe.map(r => {
        const dusuk = Number(r.adet) <= esik ? ' ⚠' : '';
        return `<option value="${r.id}">${escHtml(r.cam_turu)} · ${r.kalinlik} mm · ${r.boy}×${r.en} · stok ${r.adet}${dusuk}</option>`;
      }).join('');
    if (seciliId) sel.value = String(seciliId);
  } catch (_) { /* sessiz */ }
}

$('#fPlakaStok')?.addEventListener('change', () => {
  const id = $('#fPlakaStok')?.value;
  const r = _plakaStokListe.find(x => String(x.id) === String(id));
  if (!r) return;
  if ($('#fCamTuru')) $('#fCamTuru').value = r.cam_turu || '';
  if ($('#fKalinlik')) $('#fKalinlik').value = r.kalinlik ?? '';
  // Plaka ölçüsü ayrı alanlarda tutulur; parça boy/en kullanıcıdan
  window._seciliPlaka = { boy: r.boy, en: r.en, stok_id: r.id };
  guncelleFireOnizleme();
  toast(`Plaka seçildi: ${r.boy}×${r.en}`, 'success');
});

async function loadPlakaStok() {
  try {
    const data = await api('/api/plaka-stok');
    const o = data.ozet || {};
    const esik = o.uyari_esik || 10;
    if ($('#plakaOzet')) {
      $('#plakaOzet').textContent = `${o.toplam_adet || 0} plaka · ${o.m2 || 0} m² · ${o.satir || 0} kalem`;
    }
    const uy = $('#plakaDusukUyari');
    if (uy) {
      const dusuk = o.dusuk_stok || [];
      if (dusuk.length) {
        uy.classList.remove('hidden');
        uy.innerHTML = `<strong>Düşük stok (≤${esik})</strong>: `
          + dusuk.map(d => `${escHtml(d.cam_turu)} ${d.kalinlik}mm ${d.boy}×${d.en}=${d.adet}`).join(' · ');
      } else {
        uy.classList.add('hidden');
        uy.innerHTML = '';
      }
    }
    const tbody = $('#plakaBody');
    if (!tbody) return;
    const liste = data.liste || [];
    if (!liste.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="color:#64748b">Henüz plaka stoğu yok. Yukarıdan ekleyin.</td></tr>';
    } else {
      tbody.innerHTML = liste.map(r => {
        const m2 = ((Number(r.boy) / 1000) * (Number(r.en) / 1000) * Number(r.adet || 0)).toFixed(1);
        const dusuk = Number(r.adet) <= esik;
        return `<tr style="${dusuk ? 'background:#fef2f2' : ''}">
          <td><strong>${escHtml(r.cam_turu)}</strong></td>
          <td>${r.kalinlik} mm</td>
          <td>${r.boy}</td><td>${r.en}</td>
          <td style="font-weight:700;color:${dusuk ? '#b91c1c' : '#1d4ed8'}">${r.adet}${dusuk ? ' ⚠' : ''}</td>
          <td>${m2}</td>
          <td>${escHtml(r.not_metin || '-')}</td>
          <td style="font-size:11px;color:#64748b">${escHtml((r.guncelleme || '').replace('T', ' '))}</td>
          <td class="islem-hucre">
            <button type="button" class="btn btn-sm btn-outline" data-pl-duz="${r.id}">Adet</button>
            <button type="button" class="btn btn-sm btn-danger" data-pl-sil="${r.id}">Sil</button>
          </td>
        </tr>`;
      }).join('');
      tbody.querySelectorAll('[data-pl-duz]').forEach(btn => {
        btn.onclick = async () => {
          const id = btn.dataset.plDuz;
          const yeni = prompt('Yeni stok adedi:', '');
          if (yeni === null || yeni === '') return;
          try {
            await api(`/api/plaka-stok/${id}`, { method: 'PUT', body: JSON.stringify({ adet: parseInt(yeni, 10) }) });
            toast('Stok güncellendi', 'success');
            loadPlakaStok();
          } catch (e) { toast(e.message, 'error'); }
        };
      });
      tbody.querySelectorAll('[data-pl-sil]').forEach(btn => {
        btn.onclick = async () => {
          if (!confirm('Bu plaka kalemi silinsin mi?')) return;
          try {
            await api(`/api/plaka-stok/${btn.dataset.plSil}`, { method: 'DELETE' });
            toast('Silindi', 'success');
            loadPlakaStok();
          } catch (e) { toast(e.message, 'error'); }
        };
      });
    }
    await loadPlakaHareket();
  } catch (err) {
    toast(err.message || 'Plaka stok yüklenemedi', 'error');
  }
}

async function loadPlakaHareket() {
  const tbody = $('#plakaHareketBody');
  if (!tbody) return;
  try {
    const data = await api('/api/plaka-hareket?limit=80');
    const liste = data.liste || [];
    if (!liste.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="color:#64748b">Henüz hareket yok.</td></tr>';
      return;
    }
    tbody.innerHTML = liste.map(h => {
      const turRenk = h.tur === 'dusum' ? '#b91c1c' : (h.tur === 'iade' ? '#15803d' : '#334155');
      const geriBtn = (h.tur === 'dusum' && !h.geri_alindi)
        ? `<button type="button" class="btn btn-sm btn-outline" data-geri="${h.id}">Geri al</button>`
        : (h.geri_alindi ? '<span style="color:#94a3b8;font-size:11px">geri alındı</span>' : '');
      return `<tr>
        <td style="font-size:11px">${escHtml((h.zaman || '').replace('T', ' '))}</td>
        <td style="color:${turRenk};font-weight:600">${escHtml(h.tur)}</td>
        <td><strong>${h.adet}</strong></td>
        <td>${escHtml(h.cam_turu)} ${h.kalinlik} mm</td>
        <td>${h.boy}×${h.en}</td>
        <td style="font-size:11px">${escHtml(h.siparis_id || '-')}</td>
        <td>${escHtml(h.kullanici || '-')}</td>
        <td style="font-size:11px">${escHtml(h.neden || '-')}</td>
        <td>${geriBtn}</td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('[data-geri]').forEach(btn => {
      btn.onclick = async () => {
        if (!confirm('Bu düşüm stoğa iade edilsin mi?')) return;
        try {
          const r = await api(`/api/plaka-hareket/${btn.dataset.geri}/geri-al`, { method: 'POST', body: '{}' });
          toast(r.mesaj || 'Geri alındı', 'success');
          loadPlakaStok();
        } catch (e) { toast(e.message, 'error'); }
      };
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9">${escHtml(err.message)}</td></tr>`;
  }
}

$('#btnPlakaEkle')?.addEventListener('click', async () => {
  try {
    await api('/api/plaka-stok', {
      method: 'POST',
      body: JSON.stringify({
        cam_turu: $('#plCamTuru')?.value,
        kalinlik: $('#plKalinlik')?.value,
        boy: $('#plBoy')?.value || 3210,
        en: $('#plEn')?.value || 2250,
        adet: $('#plAdet')?.value,
        not_metin: $('#plNot')?.value,
      }),
    });
    toast('Stoğa eklendi', 'success');
    if ($('#plAdet')) $('#plAdet').value = '1';
    if ($('#plNot')) $('#plNot').value = '';
    loadPlakaStok();
  } catch (err) {
    toast(err.message, 'error');
  }
});

// Init
async function init() {
  try {
    $('#simBitis').value = bugunTarih();
    await loadAyarlar(); await loadSiparisler(); await loadBildirimler(); await loadKPI();
    await loadSyncDurum();
    cizelge = await api('/api/cizelgeleme/son');
    if(cizelge.gunler?.length){ renderGunListesi(); updateDarBogazBadge(); }
  } catch(err) { if(!window.location.pathname.includes('login')) toast(err.message,'error'); }
}
init();