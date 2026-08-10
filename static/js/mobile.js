async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  if (res.status === 401) { window.location.href = '/login'; return; }
  return res.json();
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3000);
}

async function init() {
  const kpi = await api('/api/kpi');
  document.getElementById('mobKpi').innerHTML = `
    <div class="mob-kpi-item"><span>Aktif</span><strong>${kpi.aktif}</strong></div>
    <div class="mob-kpi-item warning"><span>Üretimde</span><strong>${kpi.uretimde}</strong></div>
    <div class="mob-kpi-item danger"><span>Acil</span><strong>${kpi.acil}</strong></div>
    <div class="mob-kpi-item"><span>Kalan</span><strong>${kpi.kalan_adet}</strong></div>`;

  const cizelge = await api('/api/cizelgeleme/son');
  const bugun = new Date();
  const bugunStr = `${String(bugun.getDate()).padStart(2,'0')}.${String(bugun.getMonth()+1).padStart(2,'0')}.${bugun.getFullYear()}`;
  const bugunGun = cizelge.gunler?.find(g => g.gun.startsWith(bugunStr));
  const isler = document.getElementById('bugunIsler');
  if (bugunGun?.kayitlar?.length) {
    isler.innerHTML = bugunGun.kayitlar.map(k =>
      `<div class="mob-card-item"><strong>${k.makine}</strong><span>${k.musteri} — ${k.urun}</span><span>${k.adet} adet</span></div>`).join('');
  } else {
    isler.innerHTML = '<p class="mob-hint">Bugün için plan yok. Ofiste çizelgeleme çalıştırılmalı.</p>';
  }

  loadSiparisler();
}

async function loadSiparisler() {
  const siparisler = await api('/api/siparisler');
  const arama = document.getElementById('mobAra').value?.toLowerCase() || '';
  const el = document.getElementById('mobSiparisler');
  el.innerHTML = siparisler.filter(s => s.durum !== 'Tamamlandı' && (!arama || `${s.musteri} ${s.urun}`.toLowerCase().includes(arama)))
    .map(s => {
      const kalan = Math.max(0, parseInt(s.adet) - parseInt(s.hazir_adet||0));
      return `<div class="mob-card-item" onclick="location.href='/sevk/${s.id}'">
        <strong>${s.musteri}</strong><span>${s.urun} — Kalan: ${kalan}</span>
        <span class="mob-badge">${s.oncelik||'Normal'}</span></div>`;
    }).join('') || '<p class="mob-hint">Aktif sipariş yok</p>';
}

document.getElementById('mobAra')?.addEventListener('input', loadSiparisler);

// QR okuyucu
if (typeof Html5Qrcode !== 'undefined') {
  const scanner = new Html5Qrcode('qrReader');
  scanner.start({ facingMode: 'environment' }, { fps: 5, qrbox: 200 },
    url => { if (url.includes('/sevk/')) window.location.href = url; },
    () => {}
  ).catch(() => {
    document.getElementById('qrReader').innerHTML = '<p class="mob-hint">Kamera erişimi yok. Sipariş listesinden seçin.</p>';
  });
}

init();
