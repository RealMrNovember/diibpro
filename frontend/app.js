/* DİİBPro — uygulama (masaüstü + mobil) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const view = $("#view");
const isDesktop = () => window.matchMedia("(min-width: 1024px)").matches;

let META = null, ME = null;
let pendingFiles = [], draft = null, draftImages = [];
let currentKind = "ithalat", currentEngine = "ocr";
let BIRIMLER = [];

const fmt = (n, d = 0) =>
  (n === null || n === undefined || isNaN(n)) ? "-" :
  Number(n).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });

const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");

function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (r.status === 401) { location.href = "/login"; throw new Error("Oturum gerekli"); }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}
const jpost = (p, b, m = "POST") => api(p, { method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });

async function loadMeta() {
  [META, ME] = await Promise.all([api("/api/meta"), api("/api/me")]);
  $("#belgeNo").innerHTML = `${META.belge.belge_no}<br>${META.belge.sure_sonu} bitiş`;
  $("#topFirma").textContent = ME.firma_kisa || ME.firma;
  const sf = $("#sideFirma"); if (sf) sf.textContent = ME.firma;
  const su = $("#sideUser"); if (su) su.textContent = `${ME.ad} · ${ME.eposta}`;
  if (ME.rol !== "admin") $$("[data-admin]").forEach(b => b.style.display = "none");
}

function kalanGun() {
  const end = new Date(META.belge.sure_sonu);
  return Math.ceil((end - new Date()) / 86400000);
}

/* ================================================================ PANEL */
async function renderPanel() {
  view.innerHTML = spinner();
  const [d, erp] = await Promise.all([api("/api/dashboard"), api("/api/erp/ozet")]);
  d.erp = erp;
  isDesktop() ? renderPanelDesktop(d) : renderPanelMobile(d);
}

function birimOzetHtml(e) {
  return `<div class="birim-ozet">
    <button class="bo" onclick="switchTab('muhasebe')"><span class="ico">🧾</span>
      <b>Muhasebe</b><small>Alacak $${fmt(e.acik_alacak)} · Borç $${fmt(e.acik_borc)}</small></button>
    <button class="bo" onclick="switchTab('uretim')"><span class="ico">🏭</span>
      <b>Üretim</b><small>${e.aktif_is_emri} aktif iş emri</small></button>
    <button class="bo" onclick="switchTab('kalite')"><span class="ico">🔬</span>
      <b>Kalite</b><small>Son 30 gün: ${e.kalite_son30_test} test, ${e.kalite_son30_red} red</small></button>
    <button class="bo" onclick="switchTab('depo')"><span class="ico">📦</span>
      <b>Depo</b><small>Stok ve hareketler</small></button>
  </div>`;
}

function kpisHtml(d) {
  const o = d.ozet, kg = kalanGun();
  return `<div class="kpis">
    <div class="kpi brand"><div class="v">%${fmt(o.oran_kg, 1)}</div><div class="l">Taahhüt gerçekleşme (kg)</div></div>
    <div class="kpi"><div class="v">${fmt(o.gerceklesen_kg)} kg</div><div class="l">Toplam ihracat / ${fmt(o.taahhut_kg)} kg taahhüt</div></div>
    <div class="kpi ok"><div class="v">$${fmt(o.gerceklesen_tutar)}</div><div class="l">İhracat tutarı ($${fmt(META.belge.ongorulen_ihracat_usd)} öngörü)</div></div>
    <div class="kpi ${kg < 60 ? "warn" : ""}"><div class="v">${kg < 0 ? "Süresi doldu" : kg + " gün"}</div><div class="l">${kg < 0 ? "Belge kapatma aşamasında" : "Belge süresi"} (${META.belge.sure_sonu})</div></div>
  </div>`;
}

function renderPanelDesktop(d) {
  const maxAy = Math.max(...d.aylik.map(a => a.kg), 1);
  const aylikBars = d.aylik.map(a => `
    <div class="vbar" title="${a.ay}: ${fmt(a.kg)} kg">
      <i style="height:${Math.max(4, 100 * a.kg / maxAy)}%"></i><span>${a.ay.slice(5)}</span>
    </div>`).join("");

  const mamulTable = d.mamuller.map(m => `
    <tr>
      <td><b>${esc(m.ad)}</b><br><small>${m.satir_kodu}</small></td>
      <td class="r">${fmt(m.taahhut_kg)}</td>
      <td class="r">${fmt(m.gerceklesen_kg)}</td>
      <td class="r">${fmt(m.kalan_kg)}</td>
      <td style="width:130px">
        <div class="bar"><i class="${m.oran >= 100 ? "full" : ""}" style="width:${Math.min(100, m.oran)}%"></i></div>
        <small>%${fmt(m.oran, 1)}</small>
      </td>
    </tr>`).join("");

  const hamTable = d.hammaddeler.filter(h => h.ithal_kg || h.sarf_kg).map(h => `
    <tr>
      <td><b>${esc(h.ad)}</b>${h.yerli ? " <small>(yerli)</small>" : ""}</td>
      <td class="r">${fmt(h.ithal_kg)}</td>
      <td class="r">${fmt(h.sarf_kg)}</td>
      <td class="r ${h.stok_kg < 0 ? "neg" : "pos"}">${fmt(h.stok_kg)}</td>
    </tr>`).join("");

  view.innerHTML = `
    ${kpisHtml(d)}
    ${birimOzetHtml(d.erp)}
    <div class="two-col">
      <div class="card">
        <h3>İhracat Taahhüdü (mamul bazında)</h3>
        <div class="scrollx"><table class="tbl">
          <thead><tr><th>Mamul</th><th class="r">Taahhüt kg</th><th class="r">Gerçekleşen</th><th class="r">Kalan</th><th>Oran</th></tr></thead>
          <tbody>${mamulTable}</tbody>
        </table></div>
      </div>
      <div>
        <div class="card">
          <h3>Aylık İhracat (kg)</h3>
          <div class="vbars">${aylikBars || "<p class='muted'>Kayıt yok</p>"}</div>
        </div>
        <div class="card">
          <h3>Hammadde Stok</h3>
          <div class="scrollx"><table class="tbl">
            <thead><tr><th>Hammadde</th><th class="r">İthal</th><th class="r">Sarf</th><th class="r">Stok kg</th></tr></thead>
            <tbody>${hamTable}</tbody>
          </table></div>
          <p class="muted mt8">Eksi stok: iç piyasadan karşılanan (eşdeğer eşya) kullanım.</p>
        </div>
      </div>
    </div>`;
}

function renderPanelMobile(d) {
  const mamulRows = d.mamuller.map(m => `
    <div class="row">
      <div class="name"><b>${esc(m.ad)}</b><small>${m.satir_kodu}</small>
        <div class="bar"><i class="${m.oran >= 100 ? "full" : ""}" style="width:${Math.min(100, m.oran)}%"></i></div>
      </div>
      <div class="num">${fmt(m.gerceklesen_kg)} / ${fmt(m.taahhut_kg)} kg<small>%${fmt(m.oran, 1)}</small></div>
    </div>`).join("");
  const hamRows = d.hammaddeler.filter(h => h.ithal_kg || h.sarf_kg).map(h => `
    <div class="row">
      <div class="name"><b>${esc(h.ad)}</b><small>ithal ${fmt(h.ithal_kg)} · sarf ${fmt(h.sarf_kg)}</small></div>
      <div class="num ${h.stok_kg < 0 ? "neg" : "pos"}">${fmt(h.stok_kg)} kg<small>stok</small></div>
    </div>`).join("");
  view.innerHTML = `
    ${kpisHtml(d)}
    ${birimOzetHtml(d.erp)}
    ${d.aylik.length ? `<div class="card"><h3>Aylık İhracat</h3>${d.aylik.map(a =>
      `<div class="row"><div class="name"><b>${a.ay}</b></div><div class="num">${fmt(a.kg)} kg</div></div>`).join("")}</div>` : ""}
    <div class="card"><h3>Taahhüt (mamul)</h3>${mamulRows}</div>
    <div class="card"><h3>Hammadde Stok</h3>${hamRows}</div>`;
}

/* ================================================================ YENİ KAYIT */
function spinner(txt = "Yükleniyor") {
  return `<div class="spinner on">${txt} <span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
}

function renderYeni() {
  draft = null; draftImages = []; pendingFiles = [];
  const aiOk = META.motorlar && META.motorlar.ai;
  const ocrOk = META.motorlar && META.motorlar.ocr;
  view.innerHTML = `
    <div class="page-head"><h2>Yeni Kayıt</h2><p>Belge fotoğrafı yükleyin; sistem okusun, siz onaylayın.</p></div>
    <div class="yeni-grid">
      <div>
        <div class="seg">
          <button id="segIth" class="${currentKind === "ithalat" ? "active" : ""}">📥 İthalat</button>
          <button id="segIhr" class="${currentKind === "ihracat" ? "active" : ""}">📤 İhracat</button>
        </div>
        <div class="drop" id="drop">
          <div class="big">📷</div>
          <p><b>${currentKind === "ithalat" ? "Gümrük beyannamesi / ithalat faturası" : "İhracat faturası / çıkış beyannamesi"}</b><br>
          fotoğraf çek veya dosya seç (JPG, PNG, PDF)</p>
        </div>
        <input type="file" id="fileInput" accept="image/*,application/pdf" capture="environment" multiple hidden>
        <div class="thumbs" id="thumbs"></div>
        <div class="card" style="padding:10px 14px">
          <h3>Okuma Motoru</h3>
          <label class="engine-opt"><input type="radio" name="engine" value="ocr" ${currentEngine === "ocr" ? "checked" : ""} ${ocrOk ? "" : "disabled"}>
            <span><b>OCR</b> — ücretsiz, yerel tarama${ocrOk ? "" : " (kurulu değil)"}</span></label>
          <label class="engine-opt"><input type="radio" name="engine" value="ai" ${currentEngine === "ai" ? "checked" : ""} ${aiOk ? "" : "disabled"}>
            <span><b>AI</b> — Claude ile okuma${aiOk ? "" : " (API anahtarı yok)"}</span></label>
        </div>
        <button class="primary" id="btnExtract" disabled>🔍 Oku ve Doldur</button>
        <div class="spinner" id="spin">Belge okunuyor <span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
      </div>
      <div id="formArea"></div>
    </div>`;

  $("#segIth").onclick = () => { currentKind = "ithalat"; renderYeni(); };
  $("#segIhr").onclick = () => { currentKind = "ihracat"; renderYeni(); };
  $("#drop").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = e => { pendingFiles.push(...e.target.files); e.target.value = ""; renderThumbs(); };
  $$('input[name="engine"]', view).forEach(r => r.onchange = () => { currentEngine = r.value; });
  $("#btnExtract").onclick = doExtract;
}

function renderThumbs() {
  const box = $("#thumbs");
  box.innerHTML = "";
  pendingFiles.forEach((f, i) => {
    const t = document.createElement("div");
    t.className = "t";
    if (f.type === "application/pdf") t.innerHTML = `<div class="pdf">PDF</div>`;
    else { const img = document.createElement("img"); img.src = URL.createObjectURL(f); t.appendChild(img); }
    const x = document.createElement("button");
    x.className = "x"; x.textContent = "✕";
    x.onclick = () => { pendingFiles.splice(i, 1); renderThumbs(); };
    t.appendChild(x);
    box.appendChild(t);
  });
  $("#btnExtract").disabled = pendingFiles.length === 0;
}

async function doExtract() {
  $("#btnExtract").disabled = true;
  $("#spin").classList.add("on");
  try {
    const fd = new FormData();
    fd.append("kind", currentKind);
    fd.append("engine", currentEngine);
    pendingFiles.forEach(f => fd.append("files", f));
    const res = await api("/api/extract", { method: "POST", body: fd });
    draft = res.draft;
    draftImages = res.image_paths;
    renderDraftForm();
    toast(`Belge ${res.engine === "ai" ? "AI" : "OCR"} ile okundu — kontrol edip kaydedin`);
  } catch (e) {
    toast("Hata: " + e.message, 5000);
    $("#btnExtract").disabled = false;
  } finally {
    $("#spin").classList.remove("on");
  }
}

function fieldHtml(id, label, value, type = "text") {
  return `<div class="field"><label>${label}</label>
    <input id="${id}" type="${type}" value="${esc(value)}" ${type === "number" ? 'step="any" inputmode="decimal"' : ""}></div>`;
}

function renderDraftForm() {
  const fa = $("#formArea");
  const d = draft;
  let note = d.guven_notu ? `<div class="note">⚠️ ${esc(d.guven_notu)}</div>` : "";
  if (d._ocr_text) {
    note += `<details class="rec"><summary><span>📄 OCR ham metni</span></summary>
      <div class="body"><pre class="ocrpre">${esc(d._ocr_text)}</pre></div></details>`;
  }

  if (currentKind === "ithalat") {
    const opts = META.hammaddeler.map(h => `<option value="${h.id}">${esc(h.ad)}</option>`).join("");
    const kalems = (d.kalemler || []).map((k, i) => `
      <div class="kalem" data-i="${i}">
        <div class="khead"><span>Kalem ${i + 1} — ${esc(k.aciklama)}</span>
          <button class="danger-link" onclick="delKalem(${i})">Sil</button></div>
        <div class="field"><label>Hammadde</label><select class="k-ham">${opts}</select></div>
        <div class="grid3">
          <div class="field"><label>Miktar (kg)</label><input class="k-kg mini" type="number" step="any" value="${k.miktar_kg || 0}"></div>
          <div class="field"><label>Birim Fiyat</label><input class="k-bf mini" type="number" step="any" value="${k.birim_fiyat || 0}"></div>
          <div class="field"><label>Tutar</label><input class="k-tut mini" type="number" step="any" value="${k.tutar || 0}"></div>
        </div>
      </div>`).join("");

    fa.innerHTML = `${note}
      <div class="card"><h3>İthalat Bilgileri</h3>
        <div class="grid2">
          ${fieldHtml("f_beyanname", "Beyanname No", d.beyanname_no)}
          ${fieldHtml("f_fatura", "Fatura No", d.fatura_no)}
          ${fieldHtml("f_tarih", "Tarih", d.tarih, "date")}
          ${fieldHtml("f_gumruk", "Gümrük", d.gumruk)}
          ${fieldHtml("f_satici", "Satıcı", d.satici)}
          ${fieldHtml("f_mense", "Menşe", d.mense)}
          ${fieldHtml("f_doviz", "Döviz", d.doviz)}
          ${fieldHtml("f_tutar", "Toplam Tutar", d.toplam_tutar, "number")}
          ${fieldHtml("f_kur", "Kur (TCMB)", d.kur, "number")}
        </div>
      </div>
      <div class="card"><h3>Kalemler (stoğa eklenecek)</h3>${kalems}
        <button class="ghost" onclick="addKalem()">＋ Kalem Ekle</button></div>
      <button class="primary" id="btnSave">💾 Kaydet — Stoğa İşle</button>`;

    (d.kalemler || []).forEach((k, i) => {
      const match = META.hammaddeler.find(h => h.ad === k.hammadde);
      if (match) $$(".k-ham", fa)[i].value = match.id;
    });
    $("#btnSave").onclick = saveIthalat;
  } else {
    const opts = META.mamuller.map(m => `<option value="${m.id}">${m.satir_kodu.split(".").pop()} — ${esc(m.ad)}</option>`).join("");
    const kalems = (d.kalemler || []).map((k, i) => `
      <div class="kalem" data-i="${i}">
        <div class="khead"><span>Kalem ${i + 1}</span>
          <button class="danger-link" onclick="delKalem(${i})">Sil</button></div>
        <div class="field"><label>Ürün Adı</label><input class="k-urun mini" style="text-align:left" value="${esc(k.urun_adi)}"></div>
        <div class="field"><label>DİİB Satır Kodu</label><select class="k-mamul">${opts}</select></div>
        <div class="grid3">
          <div class="field"><label>Miktar (kg)</label><input class="k-kg mini" type="number" step="any" value="${k.miktar_kg || 0}"></div>
          <div class="field"><label>Birim Fiyat</label><input class="k-bf mini" type="number" step="any" value="${k.birim_fiyat || 0}"></div>
          <div class="field"><label>Tutar</label><input class="k-tut mini" type="number" step="any" value="${k.tutar || 0}"></div>
        </div>
      </div>`).join("");

    fa.innerHTML = `${note}
      <div class="card"><h3>İhracat Bilgileri</h3>
        <div class="grid2">
          ${fieldHtml("f_fatura", "Fatura No", d.fatura_no)}
          ${fieldHtml("f_beyanname", "Beyanname No", d.beyanname_no)}
          ${fieldHtml("f_tarih", "Tarih", d.tarih, "date")}
          ${fieldHtml("f_musteri", "Müşteri", d.musteri)}
          ${fieldHtml("f_ulke", "Ülke", d.ulke)}
          ${fieldHtml("f_doviz", "Döviz", d.doviz)}
          ${fieldHtml("f_tutar", "Toplam Tutar", d.toplam_tutar, "number")}
        </div>
      </div>
      <div class="card"><h3>Kalemler (sarf düşülecek)</h3>${kalems}
        <button class="ghost" onclick="addKalem()">＋ Kalem Ekle</button></div>
      <button class="primary" id="btnSave">💾 Kaydet — Sarfı Düş</button>`;

    (d.kalemler || []).forEach((k, i) => {
      const match = META.mamuller.find(m => m.satir_kodu === k.satir_kodu);
      if (match) $$(".k-mamul", fa)[i].value = match.id;
    });
    $("#btnSave").onclick = saveIhracat;
  }
  fa.scrollIntoView({ behavior: "smooth" });
}

window.delKalem = i => { syncDraftFromForm(); draft.kalemler.splice(i, 1); renderDraftForm(); };
window.addKalem = () => {
  syncDraftFromForm();
  draft.kalemler.push(currentKind === "ithalat"
    ? { aciklama: "", hammadde: "", gtip: "", miktar_kg: 0, birim_fiyat: 0, tutar: 0 }
    : { urun_adi: "", satir_kodu: "", miktar_kg: 0, birim_fiyat: 0, tutar: 0 });
  renderDraftForm();
};

function syncDraftFromForm() {
  const fa = $("#formArea");
  if (!fa || !fa.innerHTML) return;
  const val = id => $("#" + id, fa)?.value ?? "";
  if (currentKind === "ithalat") {
    Object.assign(draft, {
      beyanname_no: val("f_beyanname"), fatura_no: val("f_fatura"), tarih: val("f_tarih"),
      gumruk: val("f_gumruk"), satici: val("f_satici"), mense: val("f_mense"),
      doviz: val("f_doviz"), toplam_tutar: +val("f_tutar") || 0, kur: +val("f_kur") || 0,
    });
    $$(".kalem", fa).forEach((el, i) => {
      const k = draft.kalemler[i];
      k._hammadde_id = +el.querySelector(".k-ham").value;
      k.miktar_kg = +el.querySelector(".k-kg").value || 0;
      k.birim_fiyat = +el.querySelector(".k-bf").value || 0;
      k.tutar = +el.querySelector(".k-tut").value || 0;
    });
  } else {
    Object.assign(draft, {
      fatura_no: val("f_fatura"), beyanname_no: val("f_beyanname"), tarih: val("f_tarih"),
      musteri: val("f_musteri"), ulke: val("f_ulke"), doviz: val("f_doviz"),
      toplam_tutar: +val("f_tutar") || 0,
    });
    $$(".kalem", fa).forEach((el, i) => {
      const k = draft.kalemler[i];
      k.urun_adi = el.querySelector(".k-urun").value;
      k._mamul_id = +el.querySelector(".k-mamul").value;
      k.miktar_kg = +el.querySelector(".k-kg").value || 0;
      k.birim_fiyat = +el.querySelector(".k-bf").value || 0;
      k.tutar = +el.querySelector(".k-tut").value || 0;
    });
  }
}

async function saveIthalat() {
  syncDraftFromForm();
  const body = {
    beyanname_no: draft.beyanname_no, fatura_no: draft.fatura_no, tarih: draft.tarih,
    gumruk: draft.gumruk, satici: draft.satici, mense: draft.mense, doviz: draft.doviz,
    tutar: draft.toplam_tutar, kur: draft.kur, image_paths: draftImages, kaynak: currentEngine,
    kalemler: draft.kalemler.filter(k => k.miktar_kg > 0).map(k => ({
      hammadde_id: k._hammadde_id, aciklama: k.aciklama || "",
      miktar_kg: k.miktar_kg, birim_fiyat: k.birim_fiyat, tutar: k.tutar,
    })),
  };
  if (!body.kalemler.length) return toast("Miktarı 0'dan büyük en az bir kalem gerekli");
  try {
    await jpost("/api/ithalat", body);
    toast("✅ İthalat kaydedildi, stok güncellendi");
    switchTab("ithalat");
  } catch (e) { toast("Hata: " + e.message, 5000); }
}

async function saveIhracat() {
  syncDraftFromForm();
  const body = {
    fatura_no: draft.fatura_no, beyanname_no: draft.beyanname_no, tarih: draft.tarih,
    musteri: draft.musteri, ulke: draft.ulke, doviz: draft.doviz,
    tutar: draft.toplam_tutar, image_paths: draftImages, kaynak: currentEngine,
    kalemler: draft.kalemler.filter(k => k.miktar_kg > 0).map(k => ({
      mamul_id: k._mamul_id, urun_adi: k.urun_adi || "",
      miktar_kg: k.miktar_kg, birim_fiyat: k.birim_fiyat, tutar: k.tutar,
    })),
  };
  if (!body.kalemler.length) return toast("Miktarı 0'dan büyük en az bir kalem gerekli");
  try {
    await jpost("/api/ihracat", body);
    toast("✅ İhracat kaydedildi, sarf düşüldü");
    switchTab("ihracat");
  } catch (e) { toast("Hata: " + e.message, 5000); }
}

/* ================================================================ VERİ TABLOSU (Excel benzeri)
   Özellikler: sütun sıralama (tıkla), sütun yerini sürükle-bırak ile değiştir,
   sütun göster/gizle — tercihler kullanıcı bazında localStorage'da saklanır. */
const TSTATE = {};

function tKey(key) { return `diibpro:tablo:${ME.eposta}:${key}`; }

function tState(key, cols) {
  if (!TSTATE[key]) {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(tKey(key)) || "{}"); } catch {}
    const defOrder = cols.map(c => c.id);
    const order = (saved.order || defOrder).filter(id => defOrder.includes(id));
    defOrder.forEach(id => { if (!order.includes(id)) order.push(id); });
    TSTATE[key] = { order, hidden: saved.hidden || [], sort: saved.sort || null };
  }
  return TSTATE[key];
}

function tSave(key) {
  const s = TSTATE[key];
  localStorage.setItem(tKey(key), JSON.stringify({ order: s.order, hidden: s.hidden, sort: s.sort }));
}

function tSortRows(rows, cols, sort) {
  if (!sort) return rows;
  const col = cols.find(c => c.id === sort.col);
  if (!col) return rows;
  const v = r => col.sortVal ? col.sortVal(r) : (r[col.id] ?? "");
  return [...rows].sort((a, b) => {
    const x = v(a), y = v(b);
    const c = (typeof x === "number" && typeof y === "number") ? x - y
      : String(x).localeCompare(String(y), "tr");
    return sort.dir === "desc" ? -c : c;
  });
}

function dataTable(key, cols, rowsData, { renderBox }) {
  const s = tState(key, cols);
  const visible = s.order.map(id => cols.find(c => c.id === id)).filter(c => c && !s.hidden.includes(c.id));
  const sorted = tSortRows(rowsData, cols, s.sort);

  const head = visible.map(c => `
    <th class="${c.num ? "r" : ""} th-sort" draggable="true" data-col="${c.id}">
      <span>${c.label}</span>${s.sort && s.sort.col === c.id ? (s.sort.dir === "desc" ? " ▼" : " ▲") : ""}
    </th>`).join("") + "<th class='islem-th'>İşlem</th>";

  const body = sorted.map(r => `
    <tr>${visible.map(c => `<td class="${c.num ? "r" : ""}">${c.render ? c.render(r) : esc(r[c.id])}</td>`).join("")}
    <td class="islem-td">${r._actions || ""}</td></tr>`).join("");

  const colMenu = cols.map(c => `
    <label class="colmenu-item"><input type="checkbox" data-col="${c.id}" ${s.hidden.includes(c.id) ? "" : "checked"}> ${c.label}</label>`).join("");

  const html = `
    <div class="dt-tools">
      <span class="muted">${sorted.length} kalem · sütun başlığına tıkla: sırala · sürükle: yer değiştir</span>
      <div class="dt-right">
        <button class="ghost slim" id="dt-csv-${key}">⬇ CSV</button>
        <div class="colmenu-wrap">
          <button class="ghost slim" id="dt-cols-${key}">⚙ Sütunlar</button>
          <div class="colmenu" id="dt-menu-${key}">${colMenu}
            <button class="linkbtn2" id="dt-reset-${key}">Varsayılana dön</button></div>
        </div>
      </div>
    </div>
    <div class="scrollx dt-wrap"><table class="tbl xls">
      <thead><tr>${head}</tr></thead><tbody>${body}</tbody>
    </table></div>`;

  const wire = () => {
    const box = renderBox();
    // sıralama
    $$(".th-sort", box).forEach(th => th.onclick = e => {
      if (th._dragging) return;
      const col = th.dataset.col;
      s.sort = (s.sort && s.sort.col === col && s.sort.dir === "asc")
        ? { col, dir: "desc" }
        : (s.sort && s.sort.col === col && s.sort.dir === "desc") ? null : { col, dir: "asc" };
      tSave(key); rerenderTable(key);
    });
    // sürükle-bırak sütun sırası
    let dragCol = null;
    $$(".th-sort", box).forEach(th => {
      th.ondragstart = e => { dragCol = th.dataset.col; th._dragging = true; e.dataTransfer.effectAllowed = "move"; };
      th.ondragend = () => setTimeout(() => { th._dragging = false; }, 50);
      th.ondragover = e => { e.preventDefault(); th.classList.add("dropzone"); };
      th.ondragleave = () => th.classList.remove("dropzone");
      th.ondrop = e => {
        e.preventDefault(); th.classList.remove("dropzone");
        const target = th.dataset.col;
        if (!dragCol || dragCol === target) return;
        const o = s.order;
        o.splice(o.indexOf(target) + (o.indexOf(dragCol) < o.indexOf(target) ? 1 : 0), 0,
                 o.splice(o.indexOf(dragCol), 1)[0]);
        tSave(key); rerenderTable(key);
      };
    });
    // sütun menüsü
    const menu = $(`#dt-menu-${key}`, box);
    $(`#dt-cols-${key}`, box).onclick = e => { e.stopPropagation(); menu.classList.toggle("open"); };
    document.addEventListener("click", () => menu && menu.classList.remove("open"), { once: true });
    menu.onclick = e => e.stopPropagation();
    $$(".colmenu-item input", menu).forEach(cb => cb.onchange = () => {
      const id = cb.dataset.col;
      s.hidden = cb.checked ? s.hidden.filter(x => x !== id) : [...s.hidden, id];
      tSave(key); rerenderTable(key);
    });
    $(`#dt-reset-${key}`, box).onclick = () => {
      localStorage.removeItem(tKey(key)); delete TSTATE[key]; rerenderTable(key);
    };
    // CSV
    $(`#dt-csv-${key}`, box).onclick = () => {
      const sep = ";";
      const lines = [visible.map(c => `"${c.label}"`).join(sep)];
      sorted.forEach(r => lines.push(visible.map(c => {
        const v = c.csv ? c.csv(r) : (r[c.id] ?? "");
        return `"${String(v).replace(/"/g, '""')}"`;
      }).join(sep)));
      const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${key}-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
    };
  };
  return { html, wire };
}

const TABLE_RERENDER = {};
function rerenderTable(key) { if (TABLE_RERENDER[key]) TABLE_RERENDER[key](); }

function buildKalemTable(key, cols, box, items) {
  const t = dataTable(key, cols, items, { renderBox: () => box });
  box.innerHTML = `<div class="card">${t.html}</div>`;
  TABLE_RERENDER[key] = () => buildKalemTable(key, cols, box, items);
  t.wire();
}

/* ================================================================ KAYIT LİSTELERİ */
const FILTERS = { ithalat: {}, ihracat: {} };

function filterBar(kind) {
  const f = FILTERS[kind];
  return `<div class="filterbar">
    <input id="flt_q" placeholder="🔍 Ara: beyanname, fatura, ${kind === "ithalat" ? "satıcı" : "müşteri"}…" value="${esc(f.q || "")}">
    <input id="flt_bas" type="date" value="${f.baslangic || ""}" title="Başlangıç">
    <input id="flt_bit" type="date" value="${f.bitis || ""}" title="Bitiş">
    <select id="flt_kaynak">
      <option value="">Tüm kaynaklar</option>
      <option value="excel-aktarim" ${f.kaynak === "excel-aktarim" ? "selected" : ""}>Arşiv (Excel)</option>
      <option value="ocr" ${f.kaynak === "ocr" ? "selected" : ""}>OCR</option>
      <option value="ai" ${f.kaynak === "ai" ? "selected" : ""}>AI</option>
      <option value="manuel" ${f.kaynak === "manuel" ? "selected" : ""}>Manuel</option>
    </select>
    <button class="ghost slim" id="flt_temizle">Temizle</button>
  </div>`;
}

function wireFilters(kind, reload) {
  const f = FILTERS[kind];
  const read = () => {
    f.q = $("#flt_q").value.trim();
    f.baslangic = $("#flt_bas").value;
    f.bitis = $("#flt_bit").value;
    f.kaynak = $("#flt_kaynak").value;
    reload();
  };
  let t;
  $("#flt_q").oninput = () => { clearTimeout(t); t = setTimeout(read, 350); };
  $("#flt_bas").onchange = read;
  $("#flt_bit").onchange = read;
  $("#flt_kaynak").onchange = read;
  $("#flt_temizle").onclick = () => { FILTERS[kind] = {}; reload(true); };
}

const kaynakBadge = k => k === "excel-aktarim" ? `<span class="badge b-arsiv">arşiv</span>`
  : k === "ocr" ? `<span class="badge b-ocr">OCR</span>`
  : k === "ai" ? `<span class="badge b-ai">AI</span>`
  : `<span class="badge">manuel</span>`;

function qs(kind) {
  const f = FILTERS[kind];
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.baslangic) p.set("baslangic", f.baslangic);
  if (f.bitis) p.set("bitis", f.bitis);
  if (f.kaynak) p.set("kaynak", f.kaynak);
  const s = p.toString();
  return s ? "?" + s : "";
}

async function renderIthalat(reset) {
  if (reset) FILTERS.ithalat = {};
  view.innerHTML = `
    <div class="page-head"><h2>İthalat Kayıtları</h2>
      <button class="primary slim" onclick="currentKind='ithalat';switchTab('yeni')">＋ Yeni İthalat</button></div>
    ${filterBar("ithalat")}
    <div id="listArea">${spinner()}</div>`;
  wireFilters("ithalat", () => loadIthalatList());
  await loadIthalatList();
}

const ITH_COLS = [
  { id: "urun", label: "Ürün İsmi", render: r => `<b>${esc(r.aciklama || r.hammadde_ad)}</b><br><small class="muted">${esc(r.hammadde_ad)}</small>`, sortVal: r => r.aciklama || r.hammadde_ad, csv: r => r.aciklama || r.hammadde_ad },
  { id: "beyanname_no", label: "Beyanname No", render: r => `${esc(r.beyanname_no || "—")} ${kaynakBadge(r.kaynak)}`, csv: r => r.beyanname_no },
  { id: "tarih", label: "Tarih" },
  { id: "firma", label: "Firma" },
  { id: "ulke", label: "Ülke" },
  { id: "diib_kodu", label: "DİİB Kodu", render: r => esc(r.diib_kodu || "—") },
  { id: "gtip", label: "GTİP" },
  { id: "kalem_no", label: "Kalem No", num: true },
  { id: "gumruk", label: "Gümrük", render: r => esc((r.gumruk || "").replace(" GÜMRÜK MÜDÜRLÜĞÜ", "")) },
  { id: "miktar_kg", label: "KG", num: true, render: r => `<b>${fmt(r.miktar_kg)}</b>`, csv: r => r.miktar_kg },
  { id: "birim_fiyat", label: "Birim Fiyat", num: true, render: r => fmt(r.birim_fiyat, 2), csv: r => r.birim_fiyat },
  { id: "tutar", label: "Tutar", num: true, render: r => `${fmt(r.tutar, 2)} ${r.doviz}`, csv: r => r.tutar },
];

async function loadIthalatList() {
  const box = $("#listArea");
  box.innerHTML = spinner();

  if (isDesktop()) {
    const items = await api("/api/ithalat/kalemler" + qs("ithalat"));
    items.forEach(r => {
      r._actions = `
        <button class="tico" title="Düzenle" onclick="editKalem('ithalat', ${r.kalem_id})">✏️</button>
        ${r.image_paths.length ? `<button class="tico" title="Belgeyi indir" onclick="dlBelge('${r.image_paths.join(",")}')">📎</button>` : ""}
        <button class="tico" title="Sil" onclick="delKalemRow('ithalat', ${r.kalem_id})">🗑️</button>`;
    });
    window._kalemRows = window._kalemRows || {};
    window._kalemRows.ithalat = items;
    buildKalemTable("ithalat", ITH_COLS, box, items);
    return;
  }
  {
    const items = await api("/api/ithalat" + qs("ithalat"));
    box.innerHTML = items.map(it => `
      <details class="rec">
        <summary><span>📥 ${esc(it.beyanname_no || "İthalat #" + it.id)} ${kaynakBadge(it.kaynak)}</span><small>${it.tarih || ""}</small></summary>
        <div class="body">
          <p class="muted">${esc(it.satici)} · ${esc(it.mense)} · ${esc(it.gumruk)}</p>
          <table>${it.kalemler.map(k => `<tr><td>${esc(k.hammadde_ad)}</td><td>${fmt(k.miktar_kg)} kg</td><td>${fmt(k.tutar, 2)} ${it.doviz}</td></tr>`).join("")}</table>
          ${it.image_paths.map(p => `<a href="/uploads/${p}" target="_blank" class="filelink">📎 ${p}</a>`).join("")}
          <button class="danger-link mt8" onclick="delIthalat(${it.id})">Kaydı Sil</button>
        </div>
      </details>`).join("") || "<p class='muted'>Kayıt bulunamadı</p>";
  }
}

async function renderIhracat(reset) {
  if (reset) FILTERS.ihracat = {};
  view.innerHTML = `
    <div class="page-head"><h2>İhracat Kayıtları</h2>
      <button class="primary slim" onclick="currentKind='ihracat';switchTab('yeni')">＋ Yeni İhracat</button></div>
    ${filterBar("ihracat")}
    <div id="listArea">${spinner()}</div>`;
  wireFilters("ihracat", () => loadIhracatList());
  await loadIhracatList();
}

const IHR_COLS = [
  { id: "urun", label: "Ürün İsmi", render: r => `<b>${esc(r.urun_adi || r.mamul_ad)}</b>`, sortVal: r => r.urun_adi || r.mamul_ad, csv: r => r.urun_adi || r.mamul_ad },
  { id: "fatura_no", label: "Fatura No", render: r => `${esc(r.fatura_no || "—")} ${kaynakBadge(r.kaynak)}`, csv: r => r.fatura_no },
  { id: "beyanname_no", label: "Beyanname No" },
  { id: "tarih", label: "Tarih" },
  { id: "firma", label: "Firma (Müşteri)" },
  { id: "ulke", label: "Ülke" },
  { id: "diib_kodu", label: "DİİB Kodu" },
  { id: "gtip", label: "GTİP" },
  { id: "kalem_no", label: "Kalem No", num: true },
  { id: "gumruk", label: "Gümrük", render: r => esc((r.gumruk || "").replace(" GÜMRÜK MÜDÜRLÜĞÜ", "")) },
  { id: "miktar_kg", label: "KG", num: true, render: r => `<b>${fmt(r.miktar_kg)}</b>`, csv: r => r.miktar_kg },
  { id: "birim_fiyat", label: "Birim Fiyat", num: true, render: r => fmt(r.birim_fiyat, 2), csv: r => r.birim_fiyat },
  { id: "tutar", label: "Tutar", num: true, render: r => `${fmt(r.tutar, 2)} ${r.doviz}`, csv: r => r.tutar },
  { id: "kapanis_tarihi", label: "Kapanış", render: r => esc(r.kapanis_tarihi || "AÇIK") },
];

async function loadIhracatList() {
  const box = $("#listArea");
  box.innerHTML = spinner();

  if (isDesktop()) {
    const items = await api("/api/ihracat/kalemler" + qs("ihracat"));
    items.forEach(r => {
      r._actions = `
        <button class="tico" title="Düzenle" onclick="editKalem('ihracat', ${r.kalem_id})">✏️</button>
        ${r.image_paths.length ? `<button class="tico" title="Belgeyi indir" onclick="dlBelge('${r.image_paths.join(",")}')">📎</button>` : ""}
        <button class="tico" title="Sil" onclick="delKalemRow('ihracat', ${r.kalem_id})">🗑️</button>`;
    });
    window._kalemRows = window._kalemRows || {};
    window._kalemRows.ihracat = items;
    buildKalemTable("ihracat", IHR_COLS, box, items);
    return;
  }
  {
    const items = await api("/api/ihracat" + qs("ihracat"));
    box.innerHTML = items.map(it => `
      <details class="rec">
        <summary><span>📤 ${esc(it.fatura_no || "İhracat #" + it.id)} ${kaynakBadge(it.kaynak)}</span><small>${it.tarih || ""} · ${esc(it.musteri)}</small></summary>
        <div class="body">
          <p class="muted">${esc(it.ulke)} · ${esc(it.beyanname_no)}</p>
          <table>${it.kalemler.map(k => `<tr><td>${esc(k.urun_adi || k.mamul_ad)}<br><small class="muted">${k.satir_kodu}</small></td><td>${fmt(k.miktar_kg)} kg</td></tr>`).join("")}</table>
          <div class="sarfbox"><b>Sarf:</b> ${it.sarf.map(s => `${esc(s.hammadde_ad)} ${fmt(s.kg, 1)}`).join(" · ") || "-"}</div>
          ${it.image_paths.map(p => `<a href="/uploads/${p}" target="_blank" class="filelink">📎 ${p}</a>`).join("")}
          <button class="danger-link mt8" onclick="delIhracat(${it.id})">Kaydı Sil</button>
        </div>
      </details>`).join("") || "<p class='muted'>Kayıt bulunamadı</p>";
  }
}

/* --- kalem düzenleme kutusu + işlemler --- */
function openModal(html) {
  let m = $("#modal");
  if (!m) {
    m = document.createElement("div");
    m.id = "modal"; m.className = "modal-back";
    document.body.appendChild(m);
    m.onclick = e => { if (e.target === m) closeModal(); };
  }
  m.innerHTML = `<div class="modal-card">${html}</div>`;
  m.classList.add("open");
}
window.closeModal = () => { const m = $("#modal"); if (m) m.classList.remove("open"); };

window.dlBelge = paths => {
  paths.split(",").forEach(p => window.open("/uploads/" + p, "_blank"));
};

window.delKalemRow = async (kind, kid) => {
  if (!confirm("Bu kalem silinsin mi? Stok/sarf etkisi geri alınır.")) return;
  try {
    const r = await api(`/api/${kind}/kalem/${kid}`, { method: "DELETE" });
    toast(r.beyanname_silindi || r.fatura_silindi ? "Kalem ve boş kalan kayıt silindi" : "Kalem silindi");
    kind === "ithalat" ? loadIthalatList() : loadIhracatList();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};

window.editKalem = (kind, kid) => {
  const r = (window._kalemRows?.[kind] || []).find(x => x.kalem_id === kid);
  if (!r) return;
  const isIth = kind === "ithalat";
  const katalogSel = isIth
    ? `<select id="em_katalog">${META.hammaddeler.map(h =>
        `<option value="${h.id}" ${h.ad === r.hammadde_ad ? "selected" : ""}>${esc(h.ad)}</option>`).join("")}</select>`
    : `<select id="em_katalog">${META.mamuller.map(m =>
        `<option value="${m.id}" ${m.satir_kodu === r.diib_kodu ? "selected" : ""}>${m.satir_kodu.split(".").pop()} — ${esc(m.ad)}</option>`).join("")}</select>`;

  openModal(`
    <h3>Kalem Düzenle — ${esc(isIth ? (r.beyanname_no || "") : (r.fatura_no || ""))}</h3>
    <div class="grid2">
      <div class="field"><label>${isIth ? "Açıklama / Ürün" : "Ürün Adı"}</label>
        <input id="em_urun" value="${esc(isIth ? r.aciklama : r.urun_adi)}"></div>
      <div class="field"><label>${isIth ? "Hammadde" : "DİİB Satır Kodu (Mamul)"}</label>${katalogSel}</div>
      <div class="field"><label>Miktar (kg)</label><input id="em_kg" type="number" step="any" value="${r.miktar_kg}"></div>
      <div class="field"><label>Birim Fiyat</label><input id="em_bf" type="number" step="any" value="${r.birim_fiyat}"></div>
      <div class="field"><label>Tutar</label><input id="em_tutar" type="number" step="any" value="${r.tutar}"></div>
      <div class="field"><label>Tarih</label><input id="em_tarih" type="date" value="${r.tarih}"></div>
      <div class="field"><label>${isIth ? "Beyanname No" : "Fatura No"}</label>
        <input id="em_no" value="${esc(isIth ? r.beyanname_no : r.fatura_no)}"></div>
      <div class="field"><label>Firma</label><input id="em_firma" value="${esc(r.firma)}"></div>
    </div>
    <p class="muted">Not: Tarih, ${isIth ? "beyanname" : "fatura"} no ve firma alanları aynı belgeye bağlı tüm kalemleri günceller.</p>
    <div class="modal-btns">
      <button class="ghost slim" onclick="closeModal()">Vazgeç</button>
      <button class="primary slim" onclick="saveKalem('${kind}', ${kid})">Kaydet</button>
    </div>`);
};

window.saveKalem = async (kind, kid) => {
  const isIth = kind === "ithalat";
  const body = {
    miktar_kg: +$("#em_kg").value || 0,
    birim_fiyat: +$("#em_bf").value || 0,
    tutar: +$("#em_tutar").value || 0,
    tarih: $("#em_tarih").value,
  };
  if (isIth) {
    body.aciklama = $("#em_urun").value;
    body.hammadde_id = +$("#em_katalog").value;
    body.beyanname_no = $("#em_no").value;
    body.satici = $("#em_firma").value;
  } else {
    body.urun_adi = $("#em_urun").value;
    body.mamul_id = +$("#em_katalog").value;
    body.fatura_no = $("#em_no").value;
    body.musteri = $("#em_firma").value;
  }
  try {
    await jpost(`/api/${kind}/kalem/${kid}`, body, "PUT");
    closeModal();
    toast("✅ Kalem güncellendi — stok/sarf yeniden hesaplandı");
    isIth ? loadIthalatList() : loadIhracatList();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};

window.delIthalat = async id => {
  if (!confirm("Bu ithalat kaydı silinsin mi? Stok geri alınır.")) return;
  await api("/api/ithalat/" + id, { method: "DELETE" });
  toast("Silindi"); loadIthalatList();
};
window.delIhracat = async id => {
  if (!confirm("Bu ihracat kaydı silinsin mi? Sarf geri alınır.")) return;
  await api("/api/ihracat/" + id, { method: "DELETE" });
  toast("Silindi"); loadIhracatList();
};

/* ================================================================ TANIMLAR */
function renderTanimlar() {
  const recByMamul = {};
  META.receteler.forEach(r => (recByMamul[r.satir_kodu] ??= []).push(r));

  const mamulHtml = META.mamuller.map(m => {
    const recs = recByMamul[m.satir_kodu] || [];
    return `<details class="rec">
      <summary><span>${m.satir_kodu.split(".").pop()} — ${esc(m.ad)}</span><small>${fmt(m.taahhut_kg)} kg taahhüt</small></summary>
      <div class="body">
        <p class="muted">1 kg ürün için sarf katsayıları:</p>
        <table>${recs.map(r => `<tr><td>${esc(r.hammadde_ad)}</td>
          <td style="width:90px"><input class="mini" type="number" step="any" value="${r.katsayi}"
              onchange="updRecete(${r.id}, this.value)"></td></tr>`).join("")}</table>
      </div>
    </details>`;
  }).join("");

  const hamHtml = META.hammaddeler.map(h => `
    <details class="rec">
      <summary><span>${esc(h.ad)}${h.yerli ? " <small>(yerli)</small>" : ""}</span><small>izin: ${fmt(h.izin_miktari_kg)} kg</small></summary>
      <div class="body">
        <div class="grid2">
          <div class="field"><label>DİİB Satır Kodu</label><input value="${esc(h.satir_kodu)}" onchange="updHam(${h.id},'satir_kodu',this.value)"></div>
          <div class="field"><label>GTİP</label><input value="${esc(h.gtip)}" onchange="updHam(${h.id},'gtip',this.value)"></div>
        </div>
        <div class="field"><label>İthal İzin Miktarı (kg)</label>
          <input type="number" step="any" value="${h.izin_miktari_kg || 0}" onchange="updHam(${h.id},'izin_miktari_kg',+this.value)"></div>
      </div>
    </details>`).join("");

  view.innerHTML = `
    <div class="page-head"><h2>Tanımlar</h2><p>Belge, reçeteler ve hammadde kartları</p></div>
    <div class="two-col">
      <div>
        <div class="card"><h3>Belge</h3>
          <div class="row"><div class="name"><b>${META.belge.belge_no}</b><small>${esc(ME.firma)}</small></div>
          <div class="num">${META.belge.belge_tarihi}<small>${META.belge.sure_sonu} bitiş</small></div></div>
          <div class="row"><div class="name"><b>Öngörülen ihracat</b></div><div class="num">$${fmt(META.belge.ongorulen_ihracat_usd)}</div></div>
          <div class="row"><div class="name"><b>Öngörülen ithalat</b></div><div class="num">$${fmt(META.belge.ongorulen_ithalat_usd)}</div></div>
        </div>
        <div class="card"><h3>Hammaddeler</h3>${hamHtml}</div>
      </div>
      <div class="card"><h3>Reçeteler (Sarf Katsayıları)</h3>${mamulHtml}</div>
    </div>`;
}

window.updRecete = async (id, v) => {
  try { await jpost("/api/recete/" + id, { katsayi: +v }, "PUT"); await loadMeta(); toast("Katsayı güncellendi"); }
  catch (e) { toast("Hata: " + e.message); }
};
window.updHam = async (id, field, v) => {
  try { await jpost("/api/hammadde/" + id, { [field]: v }, "PUT"); await loadMeta(); toast("Güncellendi"); }
  catch (e) { toast("Hata: " + e.message); }
};

/* ================================================================ YÖNETİM */
async function renderYonetim() {
  if (ME.rol !== "admin") { view.innerHTML = "<div class='card'><p>Bu sayfa için yönetici yetkisi gerekli.</p></div>"; return; }
  view.innerHTML = spinner();
  const [users, birimler] = await Promise.all([api("/api/kullanici"), api("/api/birim")]);
  BIRIMLER = birimler;
  const bopts = `<option value="">— Birim yok —</option>` + birimler.map(b => `<option value="${b.id}">${esc(b.ad)}</option>`).join("");
  const rolAd = { admin: "Yönetici", operator: "Operatör", viewer: "İzleyici" };

  view.innerHTML = `
    <div class="page-head"><h2>Yönetim</h2><p>${esc(ME.firma)} — çalışanlar ve birimler</p></div>
    <div class="two-col">
      <div class="card">
        <h3>Çalışanlar (${users.length})</h3>
        <div class="scrollx"><table class="tbl">
          <thead><tr><th>Ad</th><th>E-posta</th><th>Birim</th><th>Rol</th><th>Durum</th><th></th></tr></thead>
          <tbody>${users.map(u => `
            <tr class="${u.aktif ? "" : "pasif"}">
              <td><b>${esc(u.ad)}</b>${u.unvan ? `<br><small class="muted">${esc(u.unvan)}</small>` : ""}</td>
              <td>${esc(u.eposta)}</td>
              <td><select class="mini-sel" onchange="updUser(${u.id},'birim_id',this.value?+this.value:null)">
                ${`<option value="">—</option>` + birimler.map(b => `<option value="${b.id}" ${u.birim_id === b.id ? "selected" : ""}>${esc(b.ad)}</option>`).join("")}
              </select></td>
              <td><select class="mini-sel" onchange="updUser(${u.id},'rol',this.value)" ${u.id === ME_id() ? "disabled" : ""}>
                ${Object.entries(rolAd).map(([k, v]) => `<option value="${k}" ${u.rol === k ? "selected" : ""}>${v}</option>`).join("")}
              </select></td>
              <td>${u.aktif ? "<span class='badge b-ok'>aktif</span>" : "<span class='badge'>pasif</span>"}</td>
              <td>
                ${u.id !== ME_id() ? `<button class="danger-link" onclick="updUser(${u.id},'aktif',${u.aktif ? 0 : 1})">${u.aktif ? "Pasifleştir" : "Aktifleştir"}</button>` : "<small class='muted'>siz</small>"}
                <button class="linkbtn2" onclick="resetParola(${u.id},'${esc(u.ad)}')">Parola</button>
              </td>
            </tr>`).join("")}</tbody>
        </table></div>
        <details class="rec mt8"><summary><span>＋ Çalışan Ekle</span></summary>
          <div class="body">
            <div class="grid2">
              <div class="field"><label>Ad Soyad *</label><input id="nu_ad"></div>
              <div class="field"><label>E-posta *</label><input id="nu_eposta" type="email"></div>
              <div class="field"><label>Parola * (en az 6)</label><input id="nu_parola" type="text"></div>
              <div class="field"><label>Ünvan</label><input id="nu_unvan" placeholder="örn. Dış Ticaret Uzmanı"></div>
              <div class="field"><label>Telefon</label><input id="nu_tel"></div>
              <div class="field"><label>Birim</label><select id="nu_birim">${bopts}</select></div>
              <div class="field"><label>Rol</label><select id="nu_rol">
                <option value="operator">Operatör (kayıt girer)</option>
                <option value="viewer">İzleyici (sadece görür)</option>
                <option value="admin">Yönetici (tam yetki)</option>
              </select></div>
            </div>
            <button class="primary" onclick="createUser()">Çalışanı Ekle</button>
          </div>
        </details>
      </div>
      <div class="card">
        <h3>Birimler (${birimler.length})</h3>
        ${birimler.map(b => `
          <div class="row">
            <div class="name"><b>${esc(b.ad)}</b><small>${b.kullanici_sayisi} çalışan${b.aciklama ? " · " + esc(b.aciklama) : ""}</small></div>
            <button class="danger-link" onclick="delBirim(${b.id})">Sil</button>
          </div>`).join("") || "<p class='muted'>Birim yok</p>"}
        <div class="addline">
          <input id="nb_ad" placeholder="Yeni birim adı (örn. Kalite)">
          <button class="primary slim" onclick="createBirim()">Ekle</button>
        </div>
      </div>
    </div>`;
}

function ME_id() { return ME._id || 0; }

window.updUser = async (id, field, v) => {
  try { await jpost("/api/kullanici/" + id, { [field]: v }, "PUT"); toast("Güncellendi"); renderYonetim(); }
  catch (e) { toast("Hata: " + e.message, 4000); }
};
window.resetParola = async (id, ad) => {
  const p = prompt(`${ad} için yeni parola (en az 6 karakter):`);
  if (!p) return;
  try { await jpost("/api/kullanici/" + id, { parola: p }, "PUT"); toast("Parola güncellendi"); }
  catch (e) { toast("Hata: " + e.message, 4000); }
};
window.createUser = async () => {
  try {
    await jpost("/api/kullanici", {
      ad: $("#nu_ad").value, eposta: $("#nu_eposta").value, parola: $("#nu_parola").value,
      unvan: $("#nu_unvan").value, telefon: $("#nu_tel").value,
      birim_id: $("#nu_birim").value ? +$("#nu_birim").value : null, rol: $("#nu_rol").value,
    });
    toast("✅ Çalışan eklendi"); renderYonetim();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.createBirim = async () => {
  const ad = $("#nb_ad").value.trim();
  if (!ad) return toast("Birim adı girin");
  try { await jpost("/api/birim", { ad }); toast("✅ Birim eklendi"); renderYonetim(); }
  catch (e) { toast("Hata: " + e.message, 4000); }
};
window.delBirim = async id => {
  if (!confirm("Birim silinsin mi? Çalışanların birim ataması kaldırılır.")) return;
  await api("/api/birim/" + id, { method: "DELETE" });
  toast("Silindi"); renderYonetim();
};

/* ================================================================ PROFİL */
async function renderProfil() {
  view.innerHTML = spinner();
  const [p, birimler] = await Promise.all([api("/api/profil"), api("/api/birim")]);
  ME._id = p.id;
  const rolAd = { admin: "Yönetici", operator: "Operatör", viewer: "İzleyici" };
  view.innerHTML = `
    <div class="page-head"><h2>Profil</h2><p>${esc(p.eposta)} · ${rolAd[p.rol] || p.rol}</p></div>
    <div class="two-col">
      <div class="card">
        <h3>Kişisel Bilgiler</h3>
        <div class="field"><label>Ad Soyad</label><input id="pf_ad" value="${esc(p.ad)}"></div>
        <div class="grid2">
          <div class="field"><label>Ünvan</label><input id="pf_unvan" value="${esc(p.unvan)}"></div>
          <div class="field"><label>Telefon</label><input id="pf_tel" value="${esc(p.telefon)}"></div>
        </div>
        <div class="field"><label>Birim</label>
          <select id="pf_birim">
            <option value="">— Birim yok —</option>
            ${birimler.map(b => `<option value="${b.id}" ${p.birim_id === b.id ? "selected" : ""}>${esc(b.ad)}</option>`).join("")}
          </select></div>
        <button class="primary" id="pf_kaydet">Bilgileri Kaydet</button>
      </div>
      <div class="card">
        <h3>Parola Değiştir</h3>
        <div class="field"><label>Mevcut Parola</label><input id="pf_eski" type="password" autocomplete="current-password"></div>
        <div class="field"><label>Yeni Parola (en az 6)</label><input id="pf_yeni" type="password" autocomplete="new-password"></div>
        <div class="field"><label>Yeni Parola (tekrar)</label><input id="pf_yeni2" type="password" autocomplete="new-password"></div>
        <button class="primary" id="pf_parola">Parolayı Değiştir</button>
        <div class="card sub-info mt8">
          <h3>Hesap</h3>
          <p class="muted">Firma: ${esc(ME.firma)}<br>Kayıt: ${p.created_at || "-"}</p>
        </div>
      </div>
    </div>`;

  $("#pf_kaydet").onclick = async () => {
    try {
      await jpost("/api/profil", {
        ad: $("#pf_ad").value, unvan: $("#pf_unvan").value, telefon: $("#pf_tel").value,
        birim_id: $("#pf_birim").value ? +$("#pf_birim").value : null,
      }, "PUT");
      await loadMeta(); toast("✅ Profil güncellendi");
    } catch (e) { toast("Hata: " + e.message, 4000); }
  };
  $("#pf_parola").onclick = async () => {
    if ($("#pf_yeni").value !== $("#pf_yeni2").value) return toast("Yeni parolalar eşleşmiyor");
    try {
      await jpost("/api/profil", { mevcut_parola: $("#pf_eski").value, yeni_parola: $("#pf_yeni").value }, "PUT");
      toast("✅ Parola değiştirildi");
      $("#pf_eski").value = $("#pf_yeni").value = $("#pf_yeni2").value = "";
    } catch (e) { toast("Hata: " + e.message, 4000); }
  };
}

/* ================================================================ DEPO */
async function renderDepo() {
  view.innerHTML = spinner();
  const d = await api("/api/depo");
  const hamOpts = d.hammaddeler.map(h => `<option value="hammadde:${h.id}">${esc(h.ad)} (hammadde)</option>`).join("");
  const mamOpts = d.mamuller.map(m => `<option value="mamul:${m.id}">${esc(m.ad)} (mamul)</option>`).join("");

  const hamTbl = d.hammaddeler.map(h => `
    <tr><td><b>${esc(h.ad)}</b>${h.yerli ? " <small class='muted'>(yerli)</small>" : ""}</td>
    <td class="r">${fmt(h.diib_ithal)}</td><td class="r">${fmt(h.diib_sarf)}</td>
    <td class="r">${fmt(h.manuel_net)}</td>
    <td class="r ${h.stok < 0 ? "neg" : "pos"}"><b>${fmt(h.stok)}</b></td></tr>`).join("");

  const mamTbl = d.mamuller.filter(m => m.uretim_net || m.sevk).map(m => `
    <tr><td><b>${esc(m.ad)}</b><br><small class="muted">${m.satir_kodu}</small></td>
    <td class="r">${fmt(m.uretim_net)}</td><td class="r">${fmt(m.sevk)}</td>
    <td class="r ${m.stok < 0 ? "neg" : "pos"}"><b>${fmt(m.stok)}</b></td></tr>`).join("");

  const hrkTbl = d.hareketler.map(h => `
    <tr><td>${h.tarih}</td><td>${esc(h.kalem_ad)}</td>
    <td><span class="badge ${h.tip.includes("giris") ? "b-ok" : h.tip.includes("cikis") ? "b-ai" : ""}">${h.tip}</span></td>
    <td class="r">${fmt(h.miktar_kg, 1)} kg</td><td>${esc(h.aciklama)}</td>
    <td>${h.is_emri_id ? "" : `<button class="danger-link" onclick="delHareket(${h.id})">Sil</button>`}</td></tr>`).join("");

  view.innerHTML = `
    <div class="page-head"><h2>Depo</h2><p>Hammadde ve mamul stokları · hareket kayıtları</p></div>
    <div class="two-col">
      <div>
        <div class="card"><h3>Hammadde Stok</h3>
          <div class="scrollx"><table class="tbl">
            <thead><tr><th>Hammadde</th><th class="r">DİİB İthal</th><th class="r">DİİB Sarf</th><th class="r">Depo Hrk.</th><th class="r">Stok kg</th></tr></thead>
            <tbody>${hamTbl}</tbody></table></div>
          <p class="muted mt8">Stok = DİİB ithalatı − reçete sarfı + manuel depo hareketleri (yerli alım girişleri dahil).</p>
        </div>
        <div class="card"><h3>Mamul Stok</h3>
          <div class="scrollx"><table class="tbl">
            <thead><tr><th>Mamul</th><th class="r">Üretim (net)</th><th class="r">Sevk (ihracat)</th><th class="r">Depo kg</th></tr></thead>
            <tbody>${mamTbl || "<tr><td colspan='4' class='muted'>Henüz üretim girişi yok — iş emri tamamlandığında burada görünür</td></tr>"}</tbody></table></div>
        </div>
      </div>
      <div>
        <div class="card"><h3>Yeni Hareket</h3>
          <div class="field"><label>Kalem</label><select id="dh_kalem">${hamOpts}${mamOpts}</select></div>
          <div class="grid3">
            <div class="field"><label>Tür</label><select id="dh_tip">
              <option value="giris">Giriş (alım)</option>
              <option value="cikis">Çıkış</option>
              <option value="sayim-duzeltme">Sayım düzeltme (+/−)</option>
            </select></div>
            <div class="field"><label>Miktar (kg)</label><input id="dh_kg" type="number" step="any"></div>
            <div class="field"><label>Tarih</label><input id="dh_tarih" type="date"></div>
          </div>
          <div class="field"><label>Açıklama</label><input id="dh_acik" placeholder="örn. yerli etil alkol alımı — İRM Kimya"></div>
          <button class="primary" onclick="addHareket()">Hareketi Kaydet</button>
        </div>
        <div class="card"><h3>Son Hareketler</h3>
          <div class="scrollx"><table class="tbl">
            <thead><tr><th>Tarih</th><th>Kalem</th><th>Tür</th><th class="r">Miktar</th><th>Açıklama</th><th></th></tr></thead>
            <tbody>${hrkTbl || "<tr><td colspan='6' class='muted'>Hareket yok</td></tr>"}</tbody></table></div>
        </div>
      </div>
    </div>`;
}

window.addHareket = async () => {
  const [kalem_tipi, kalem_id] = $("#dh_kalem").value.split(":");
  try {
    await jpost("/api/depo/hareket", {
      kalem_tipi, kalem_id: +kalem_id, tip: $("#dh_tip").value,
      miktar_kg: +$("#dh_kg").value || 0, tarih: $("#dh_tarih").value, aciklama: $("#dh_acik").value,
    });
    toast("✅ Hareket kaydedildi"); renderDepo();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.delHareket = async id => {
  if (!confirm("Hareket silinsin mi?")) return;
  try { await api("/api/depo/hareket/" + id, { method: "DELETE" }); toast("Silindi"); renderDepo(); }
  catch (e) { toast("Hata: " + e.message, 4000); }
};

/* ================================================================ ÜRETİM */
async function renderUretim() {
  view.innerHTML = spinner();
  const items = await api("/api/isemri");
  const durumBadge = d => ({ planlandi: "<span class='badge'>planlandı</span>",
    uretimde: "<span class='badge b-ai'>üretimde</span>",
    tamamlandi: "<span class='badge b-ok'>tamamlandı</span>",
    iptal: "<span class='badge' style='background:#fdecea;color:var(--err)'>iptal</span>" }[d] || d);
  const mamOpts = META.mamuller.map(m => `<option value="${m.id}">${m.satir_kodu.split(".").pop()} — ${esc(m.ad)}</option>`).join("");

  const tbl = items.map(e => `
    <tr class="mrow" data-id="${e.id}">
      <td><b>${e.no}</b></td><td>${esc(e.mamul_ad)}<br><small class="muted">${e.satir_kodu}</small></td>
      <td class="r">${fmt(e.miktar_kg)} kg</td><td>${e.baslangic}</td><td>${durumBadge(e.durum)}</td>
      <td>
        ${e.durum === "planlandi" ? `<button class="linkbtn2" onclick="event.stopPropagation();setEmir(${e.id},'uretimde')">Başlat</button>` : ""}
        ${e.durum === "uretimde" ? `<button class="linkbtn2" onclick="event.stopPropagation();setEmir(${e.id},'tamamlandi')">Tamamla</button>` : ""}
        ${e.durum !== "iptal" && e.durum !== "tamamlandi" ? `<button class="danger-link" onclick="event.stopPropagation();setEmir(${e.id},'iptal')">İptal</button>` : ""}
        ${e.durum === "tamamlandi" ? `<button class="danger-link" onclick="event.stopPropagation();setEmir(${e.id},'uretimde')">Geri Al</button>` : ""}
      </td>
    </tr>
    <tr class="detail" id="det-u-${e.id}"><td colspan="6">
      <b class="muted">Reçete ihtiyacı (${fmt(e.miktar_kg)} kg için):</b>
      <table class="tbl sub">${e.ihtiyac.map(i => `<tr><td>${esc(i.ad)}</td><td class="r">${fmt(i.kg, 1)} kg</td></tr>`).join("")}</table>
      ${e.notlar ? `<p class="muted">${esc(e.notlar)}</p>` : ""}
    </td></tr>`).join("");

  view.innerHTML = `
    <div class="page-head"><h2>Üretim — İş Emirleri</h2><p>Tamamlanan emir depoya işlenir: mamul girişi + reçete sarfı çıkışı</p></div>
    <div class="two-col">
      <div class="card">
        <h3>İş Emirleri (${items.length})</h3>
        <div class="scrollx"><table class="tbl hover">
          <thead><tr><th>No</th><th>Mamul</th><th class="r">Miktar</th><th>Başlangıç</th><th>Durum</th><th>İşlem</th></tr></thead>
          <tbody>${tbl || "<tr><td colspan='6' class='muted'>İş emri yok</td></tr>"}</tbody></table></div>
      </div>
      <div class="card">
        <h3>Yeni İş Emri</h3>
        <div class="field"><label>Mamul</label><select id="ie_mamul">${mamOpts}</select></div>
        <div class="grid2">
          <div class="field"><label>Miktar (kg)</label><input id="ie_kg" type="number" step="any"></div>
          <div class="field"><label>Başlangıç</label><input id="ie_bas" type="date"></div>
        </div>
        <div class="field"><label>Not</label><input id="ie_not" placeholder="örn. STARKİM siparişi"></div>
        <button class="primary" onclick="createEmir()">İş Emri Oluştur</button>
        <p class="muted mt8">Reçete ihtiyacı otomatik hesaplanır; satıra tıklayınca görünür.</p>
      </div>
    </div>`;
  $$(".mrow", view).forEach(tr => tr.onclick = () => $("#det-u-" + tr.dataset.id).classList.toggle("open"));
}

window.createEmir = async () => {
  try {
    const r = await jpost("/api/isemri", {
      mamul_id: +$("#ie_mamul").value, miktar_kg: +$("#ie_kg").value || 0,
      baslangic: $("#ie_bas").value, notlar: $("#ie_not").value,
    });
    toast(`✅ ${r.no} oluşturuldu`); renderUretim();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.setEmir = async (id, durum) => {
  if (durum === "iptal" && !confirm("İş emri iptal edilsin mi?")) return;
  try { await jpost("/api/isemri/" + id, { durum }, "PUT"); toast("Güncellendi"); renderUretim(); }
  catch (e) { toast("Hata: " + e.message, 4000); }
};

/* ================================================================ KALİTE */
async function renderKalite() {
  view.innerHTML = spinner();
  const items = await api("/api/kalite");
  const sonucBadge = s => ({ uygun: "<span class='badge b-ok'>uygun</span>",
    sartli: "<span class='badge b-ai'>şartlı</span>",
    red: "<span class='badge' style='background:#fdecea;color:var(--err)'>red</span>" }[s] || s);

  const tbl = items.map(t => `
    <tr><td>${t.tarih}</td><td><b>${esc(t.urun)}</b></td><td>${esc(t.parti_no)}</td>
    <td>${esc(t.test_turu)}</td><td>${esc(t.deger)}</td><td>${sonucBadge(t.sonuc)}</td>
    <td><small class="muted">${esc(t.kullanici_ad || "")}</small></td>
    <td><button class="danger-link" onclick="delKalite(${t.id})">Sil</button></td></tr>`).join("");

  view.innerHTML = `
    <div class="page-head"><h2>Kalite Kontrol</h2><p>Parti / numune test kayıtları</p></div>
    <div class="two-col">
      <div class="card">
        <h3>Test Kayıtları (${items.length})</h3>
        <div class="scrollx"><table class="tbl">
          <thead><tr><th>Tarih</th><th>Ürün</th><th>Parti</th><th>Test</th><th>Değer</th><th>Sonuç</th><th>Kontrol</th><th></th></tr></thead>
          <tbody>${tbl || "<tr><td colspan='8' class='muted'>Test kaydı yok</td></tr>"}</tbody></table></div>
      </div>
      <div class="card">
        <h3>Yeni Test Kaydı</h3>
        <div class="grid2">
          <div class="field"><label>Ürün *</label><input id="kt_urun" placeholder="örn. SÜPERLAM BEYAZ"></div>
          <div class="field"><label>Parti No</label><input id="kt_parti" placeholder="örn. P-2025-014"></div>
          <div class="field"><label>Tarih</label><input id="kt_tarih" type="date"></div>
          <div class="field"><label>Test Türü</label><select id="kt_tur">
            <option>viskozite</option><option>renk</option><option>yoğunluk</option>
            <option>kuruma süresi</option><option>yapışma</option><option>pH</option><option>diğer</option>
          </select></div>
          <div class="field"><label>Ölçüm Değeri</label><input id="kt_deger" placeholder="örn. 22 sn (DIN4)"></div>
          <div class="field"><label>Sonuç</label><select id="kt_sonuc">
            <option value="uygun">Uygun</option><option value="sartli">Şartlı kabul</option><option value="red">Red</option>
          </select></div>
        </div>
        <div class="field"><label>Not</label><input id="kt_not"></div>
        <button class="primary" onclick="createKalite()">Testi Kaydet</button>
      </div>
    </div>`;
}

window.createKalite = async () => {
  try {
    await jpost("/api/kalite", {
      urun: $("#kt_urun").value, parti_no: $("#kt_parti").value, tarih: $("#kt_tarih").value,
      test_turu: $("#kt_tur").value, deger: $("#kt_deger").value, sonuc: $("#kt_sonuc").value,
      notlar: $("#kt_not").value,
    });
    toast("✅ Test kaydedildi"); renderKalite();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.delKalite = async id => {
  if (!confirm("Test kaydı silinsin mi?")) return;
  await api("/api/kalite/" + id, { method: "DELETE" });
  toast("Silindi"); renderKalite();
};

/* ================================================================ MUHASEBE */
async function renderMuhasebe() {
  view.innerHTML = spinner();
  const [cariler, faturalar, odemeler, ozet] = await Promise.all([
    api("/api/cari"), api("/api/fatura"), api("/api/odeme"), api("/api/erp/ozet")]);

  const durumBadge = d => ({ acik: "<span class='badge b-ai'>açık</span>",
    kismi: "<span class='badge'>kısmi</span>",
    odendi: "<span class='badge b-ok'>ödendi</span>" }[d] || d);

  const fatTbl = faturalar.map(f => `
    <tr>
      <td>${f.tip === "satis" ? "📤" : "📥"} <b>${esc(f.fatura_no || "—")}</b>
        ${f.kaynak !== "manuel" ? "<span class='badge b-arsiv'>oto</span>" : ""}</td>
      <td>${esc(f.cari_unvan || "—")}</td><td>${f.tarih}</td>
      <td class="r">${fmt(f.tutar, 2)} ${f.doviz}</td>
      <td class="r">${fmt(f.kalan, 2)}</td>
      <td>${durumBadge(f.durum)}</td>
      <td>${f.kalan > 0 ? `<button class="linkbtn2" onclick="odemeAl(${f.id}, ${f.kalan}, '${f.tip}')">${f.tip === "satis" ? "Tahsil Et" : "Öde"}</button>` : ""}
          ${f.kaynak === "manuel" ? `<button class="danger-link" onclick="delFatura(${f.id})">Sil</button>` : ""}</td>
    </tr>`).join("");

  const cariTbl = cariler.map(c => `
    <tr><td><b>${esc(c.unvan)}</b><br><small class="muted">${esc(c.ulke)}</small></td>
    <td><span class="badge">${c.tip === "musteri" ? "müşteri" : "tedarikçi"}</span></td>
    <td class="r ${c.alacak_bakiye > 0 ? "pos" : ""}">${fmt(c.alacak_bakiye, 2)}</td>
    <td class="r ${c.borc_bakiye > 0 ? "neg" : ""}">${fmt(c.borc_bakiye, 2)}</td></tr>`).join("");

  const odmTbl = odemeler.slice(0, 30).map(o => `
    <tr><td>${o.tarih}</td><td>${o.yon === "tahsilat" ? "⬇️ Tahsilat" : "⬆️ Ödeme"}</td>
    <td>${esc(o.cari_unvan || "")}</td><td class="r">${fmt(o.tutar, 2)} ${o.doviz}</td>
    <td>${esc(o.fatura_no || "")}</td></tr>`).join("");

  const cariOpts = cariler.map(c => `<option value="${c.id}">${esc(c.unvan)}</option>`).join("");

  view.innerHTML = `
    <div class="page-head"><h2>Muhasebe</h2><p>Cari hesaplar · faturalar · tahsilat/ödeme</p></div>
    <div class="kpis">
      <div class="kpi ok"><div class="v">$${fmt(ozet.acik_alacak)}</div><div class="l">Açık alacak (tahsil edilecek)</div></div>
      <div class="kpi warn"><div class="v">$${fmt(ozet.acik_borc)}</div><div class="l">Açık borç (ödenecek)</div></div>
      <div class="kpi"><div class="v">${ozet.cari_sayisi}</div><div class="l">Cari hesap</div></div>
      <div class="kpi brand"><div class="v">${faturalar.length}</div><div class="l">Fatura kaydı</div></div>
    </div>
    <div class="two-col">
      <div class="card">
        <h3>Faturalar</h3>
        <div class="scrollx"><table class="tbl">
          <thead><tr><th>Fatura</th><th>Cari</th><th>Tarih</th><th class="r">Tutar</th><th class="r">Kalan</th><th>Durum</th><th></th></tr></thead>
          <tbody>${fatTbl || "<tr><td colspan='7' class='muted'>Fatura yok</td></tr>"}</tbody></table></div>
        <details class="rec mt8"><summary><span>＋ Manuel Fatura Ekle</span></summary>
          <div class="body"><div class="grid2">
            <div class="field"><label>Tür</label><select id="nf_tip"><option value="satis">Satış</option><option value="alis">Alış</option></select></div>
            <div class="field"><label>Cari</label><select id="nf_cari">${cariOpts}</select></div>
            <div class="field"><label>Fatura No</label><input id="nf_no"></div>
            <div class="field"><label>Tarih</label><input id="nf_tarih" type="date"></div>
            <div class="field"><label>Vade</label><input id="nf_vade" type="date"></div>
            <div class="field"><label>Tutar</label><input id="nf_tutar" type="number" step="any"></div>
            <div class="field"><label>Döviz</label><select id="nf_doviz"><option>USD</option><option>EUR</option><option>TL</option></select></div>
          </div>
          <button class="primary" onclick="createFatura()">Faturayı Kaydet</button></div>
        </details>
      </div>
      <div>
        <div class="card"><h3>Cari Hesaplar</h3>
          <div class="scrollx"><table class="tbl">
            <thead><tr><th>Ünvan</th><th>Tip</th><th class="r">Alacak $</th><th class="r">Borç $</th></tr></thead>
            <tbody>${cariTbl}</tbody></table></div>
          <details class="rec mt8"><summary><span>＋ Cari Ekle</span></summary>
            <div class="body"><div class="grid2">
              <div class="field"><label>Ünvan *</label><input id="nc_unvan"></div>
              <div class="field"><label>Tip</label><select id="nc_tip"><option value="musteri">Müşteri</option><option value="tedarikci">Tedarikçi</option></select></div>
              <div class="field"><label>Ülke</label><input id="nc_ulke"></div>
              <div class="field"><label>E-posta</label><input id="nc_eposta"></div>
            </div>
            <button class="primary" onclick="createCari()">Cariyi Kaydet</button></div>
          </details>
        </div>
        <div class="card"><h3>Son Tahsilat / Ödemeler</h3>
          <div class="scrollx"><table class="tbl">
            <thead><tr><th>Tarih</th><th>Yön</th><th>Cari</th><th class="r">Tutar</th><th>Fatura</th></tr></thead>
            <tbody>${odmTbl || "<tr><td colspan='5' class='muted'>Kayıt yok</td></tr>"}</tbody></table></div>
        </div>
      </div>
    </div>`;
}

window.odemeAl = async (faturaId, kalan, tip) => {
  const t = prompt(`${tip === "satis" ? "Tahsilat" : "Ödeme"} tutarı (kalan: ${kalan}):`, kalan);
  if (!t) return;
  try {
    await jpost("/api/odeme", { yon: tip === "satis" ? "tahsilat" : "odeme", fatura_id: faturaId, tutar: +t });
    toast("✅ Kaydedildi"); renderMuhasebe();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.createFatura = async () => {
  try {
    await jpost("/api/fatura", {
      tip: $("#nf_tip").value, cari_id: +$("#nf_cari").value || null, fatura_no: $("#nf_no").value,
      tarih: $("#nf_tarih").value, vade_tarihi: $("#nf_vade").value,
      tutar: +$("#nf_tutar").value || 0, doviz: $("#nf_doviz").value,
    });
    toast("✅ Fatura eklendi"); renderMuhasebe();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.createCari = async () => {
  try {
    await jpost("/api/cari", { unvan: $("#nc_unvan").value, tip: $("#nc_tip").value,
      ulke: $("#nc_ulke").value, eposta: $("#nc_eposta").value });
    toast("✅ Cari eklendi"); renderMuhasebe();
  } catch (e) { toast("Hata: " + e.message, 4000); }
};
window.delFatura = async id => {
  if (!confirm("Fatura silinsin mi?")) return;
  try { await api("/api/fatura/" + id, { method: "DELETE" }); toast("Silindi"); renderMuhasebe(); }
  catch (e) { toast("Hata: " + e.message, 4000); }
};

/* ================================================================ NAV */
const tabs = { panel: renderPanel, yeni: renderYeni, ithalat: renderIthalat, ihracat: renderIhracat,
               tanimlar: renderTanimlar, yonetim: renderYonetim, profil: renderProfil,
               depo: renderDepo, uretim: renderUretim, kalite: renderKalite, muhasebe: renderMuhasebe };

function switchTab(name) {
  $$("[data-tab]").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  closeSheet();
  tabs[name]();
  window.scrollTo({ top: 0 });
}
window.switchTab = switchTab;
$$("[data-tab]").forEach(b => b.onclick = () => switchTab(b.dataset.tab));

function closeSheet() { $("#sheetBack").classList.remove("open"); }
$("#btnMore").onclick = () => $("#sheetBack").classList.add("open");
$("#sheetBack").onclick = e => { if (e.target.id === "sheetBack") closeSheet(); };

const doLogout = async () => { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; };
const lo = $("#btnLogout"); if (lo) lo.onclick = doLogout;
const lom = $("#btnLogoutM"); if (lom) lom.onclick = doLogout;

let lastDesktop = isDesktop();
window.addEventListener("resize", () => {
  if (isDesktop() !== lastDesktop) {
    lastDesktop = isDesktop();
    const active = $("[data-tab].active");
    if (active) tabs[active.dataset.tab]();
  }
});

(async () => {
  try {
    await loadMeta();
    const p = await api("/api/profil");
    ME._id = p.id;
    renderPanel();
  } catch (e) {
    view.innerHTML = `<div class="card"><h3>Bağlantı hatası</h3><p style="font-size:13px">${esc(e.message)}</p></div>`;
  }
})();
