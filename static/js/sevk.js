document.getElementById('btnSevk').addEventListener('click', async () => {
  const adet = parseInt(document.getElementById('sevkAdet').value);
  if (!adet || adet <= 0) { toast('Geçerli adet girin'); return; }
  try {
    const res = await fetch(`/api/siparisler/${SIPARIS_ID}/sevk`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ adet }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.hata);
    document.getElementById('sevkEdilen').textContent = data.hazir_adet;
    const kalan = Math.max(0, parseInt(data.adet) - parseInt(data.hazir_adet));
    document.getElementById('sevkKalan').textContent = kalan;
    document.getElementById('sevkAdet').value = '';
    toast(`✅ ${adet} adet sevk edildi`);
  } catch (e) { toast(e.message); }
});

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3000);
}
