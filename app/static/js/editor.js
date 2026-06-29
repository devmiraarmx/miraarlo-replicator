// Initialize Lucide icons
lucide.createIcons();

// ── CSRF-aware fetch helper ─────────────────────────────────
function apiFetch(url, options = {}) {
  const headers = { 'X-CSRFToken': window.CSRF_TOKEN, ...(options.headers || {}) };
  return fetch(url, { ...options, headers });
}

let currentItem = null;
let selectedPhotos = [];
let categoryAttributes = [];
let prefilledAttributes = {};
let blankPhotos = []; // For blank mode uploaded photos
let blankCategoryId = '';

// ── SETTINGS MENU ──────────────────────────────────────────
function toggleSettings(e) {
  e.stopPropagation();
  document.getElementById('settingsMenu').classList.toggle('open');
}
function closeSettings() {
  document.getElementById('settingsMenu').classList.remove('open');
}
document.addEventListener('click', closeSettings);

async function checkStatus() {
  try {
    const res = await apiFetch('/me');
    const data = await res.json();
    if (data.success) {
      toast(`Conectado como: ${data.nickname} (${data.id})`, 'success');
    } else { toast('No hay cuenta conectada', 'error'); }
  } catch(e) { toast('Error de conexión', 'error'); }
}

function doOAuth() {
  window.location.href = window.ML_CONNECT_URL;
}

async function loadCredits() {
  try {
    const r = await apiFetch('/billing/balance');
    if (r.ok) {
      const d = await r.json();
      const el = document.getElementById('creditsCount');
      if (el) el.textContent = d.available ?? '?';
      // Deshabilitar publicar si no hay créditos
      const publishBtn = document.getElementById('publishBtn');
      if (publishBtn && d.available === 0) {
        publishBtn.disabled = true;
        publishBtn.title = 'Sin créditos — compra un paquete';
      }
    }
  } catch (_) {}
}
loadCredits();

// ── CARD TOGGLE ──────────────────────────────────────────
function toggleCard(header) {
  header.closest('.card').classList.toggle('collapsed');
  lucide.createIcons();
}

// ── EXTRACTION ──────────────────────────────────────────────
async function extractItem() {
  const input = document.getElementById('mlInput').value.trim();
  if (!input) { toast('Ingresa una URL o ID de ML', 'error'); return; }
  const btn = document.getElementById('extractBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Extrayendo…';

  renderDynAttrsLoading();

  try {
    const res = await apiFetch('/extract', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input })
    });
    const data = await res.json();
    if (!data.success) { toast(data.error, 'error'); renderDynAttrsEmpty(); return; }

    currentItem = data;
    selectedPhotos = [...(data.photos || [])];
    categoryAttributes = data.category_attributes || [];
    prefilledAttributes = data.prefilled_attributes || {};

    render(data);

    const catSource = data.category_source;
    if (catSource === 'predicted') {
      toast(`Categoría auto-detectada: ${data.category_id}`, 'success');
    } else if (data.category_id) {
      toast('Producto extraído', 'success');
    } else {
      toast('Extraído (sin categoría)', 'info');
    }
  } catch(e) { toast('Error de conexión', 'error'); renderDynAttrsEmpty(); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="zap"></i> Extraer';
    lucide.createIcons();
  }
}

// ── RENDER ──────────────────────────────────────────────────
function render(d) {
  // Hide hero, show workspace
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('workspace').classList.add('visible');
  document.getElementById('actionBar').classList.add('visible');
  document.getElementById('publishPreview').classList.remove('visible');

  document.getElementById('mlmChip').textContent = d.mlm_id || 'Nuevo';
  document.getElementById('photoCount').textContent = (d.photos||[]).length + ' fotos';

  const main = document.getElementById('mainPhoto');
  if (d.photos && d.photos.length) {
    main.src = d.photos[0];
    main.style.display = 'block';
  } else {
    main.style.display = 'none';
  }

  const strip = document.getElementById('thumbsContainer');
  strip.innerHTML = '';
  (d.photos||[]).forEach((url, i) => {
    const img = document.createElement('img');
    img.src = url; img.className = 'thumb' + (i===0?' active':'');
    img.onclick = () => {
      main.src = url;
      strip.querySelectorAll('.thumb').forEach(t => t.classList.remove('active'));
      img.classList.add('active');
    };
    strip.appendChild(img);
  });

  const srcLink = document.getElementById('sourceLink');
  if (d.permalink) {
    srcLink.href = d.permalink;
    srcLink.style.display = 'flex';
  } else {
    srcLink.style.display = 'none';
  }

  const ac = document.getElementById('attrsContainer');
  const attrs = d.attributes || {};
  const keys = Object.keys(attrs);
  ac.innerHTML = keys.length
    ? keys.map(k => {
        const v = attrs[k];
        const display = (typeof v === 'object' && v !== null) ? (v.value_name || v.value_id || JSON.stringify(v)) : v;
        const label = (typeof v === 'object' && v !== null && v.name) ? v.name : k;
        return `<div class="attr-row"><span class="attr-key">${label}</span><span class="attr-val">${display}</span></div>`;
      }).join('')
    : '<div class="attr-row"><span class="attr-key" style="color:var(--text-3)">Sin atributos disponibles</span></div>';

  document.getElementById('fTitle').value = d.title || '';
  document.getElementById('fPrice').value = d.price || '';
  document.getElementById('fStock').value = d.available_quantity || 1;
  document.getElementById('fCategory').value = d.category_id || '';
  document.getElementById('fDescription').value = d.description || '';
  document.getElementById('fCondition').value = d.condition || 'new';

  updateChars();
  renderDynAttrs();

  // Load category breadcrumb
  if (d.category_id) loadCategoryBreadcrumb();

  document.getElementById('resultLink').classList.remove('visible');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── DYNAMIC ATTRS ──────────────────────────────────────────
function renderDynAttrs() {
  const body = document.getElementById('dynAttrsBody');
  const countEl = document.getElementById('dynAttrsCount');

  if (!categoryAttributes || categoryAttributes.length === 0) {
    countEl.textContent = '0';
    body.innerHTML = '<div class="dyn-empty">No se encontraron atributos obligatorios para esta categoría</div>';
    return;
  }

  countEl.textContent = categoryAttributes.length;

  let html = '<div class="dyn-grid">';
  for (const attr of categoryAttributes) {
    const prefilled = prefilledAttributes[attr.id] || '';
    const hasValue = prefilled.length > 0;
    const inputId = `dyn_${attr.id}`;

    html += `<div class="dyn-field">`;
    html += `<div class="dyn-label">`;
    html += `<span class="req">*</span> ${attr.name}`;
    if (hasValue) html += ` <span class="auto-tag">auto</span>`;
    html += `</div>`;

    if (attr.allowed_values && attr.allowed_values.length > 0) {
      html += `<select class="dyn-input${hasValue ? ' has-value' : ''}" id="${inputId}" data-attr-id="${attr.id}"
                onchange="this.classList.toggle('has-value', this.value !== '')">`;
      html += `<option value="">— Seleccionar —</option>`;
      for (const v of attr.allowed_values) {
        const sel = (v.name === prefilled || v.id === prefilled) ? ' selected' : '';
        html += `<option value="${v.name}"${sel}>${v.name}</option>`;
      }
      html += `</select>`;
    } else {
      const unit = attr.unit ? ` (${attr.unit})` : '';
      const placeholder = attr.hint || `Ingresa ${attr.name.toLowerCase()}${unit}`;
      html += `<input type="${attr.type === 'number' ? 'number' : 'text'}"
                class="dyn-input${hasValue ? ' has-value' : ''}" id="${inputId}"
                data-attr-id="${attr.id}" placeholder="${placeholder}"
                value="${prefilled}"
                oninput="this.classList.toggle('has-value', this.value !== '')">`;
    }

    html += `</div>`;
  }
  html += '</div>';
  body.innerHTML = html;
}

function renderDynAttrsLoading() {
  document.getElementById('dynAttrsBody').innerHTML = '<div class="dyn-loading"><span class="spin" style="border-color: rgba(139,92,246,.2); border-top-color: var(--purple);"></span>Cargando atributos…</div>';
}

function renderDynAttrsEmpty() {
  document.getElementById('dynAttrsBody').innerHTML = '<div class="dyn-empty">Extrae un producto para ver los atributos requeridos</div>';
  document.getElementById('dynAttrsCount').textContent = '0';
}

async function reloadCategoryAttrs() {
  const catId = document.getElementById('fCategory').value.trim();
  if (!catId) { toast('Ingresa un ID de categoría primero', 'error'); return; }

  const btn = document.getElementById('detectBtn');
  btn.innerHTML = '<span class="spin" style="width:10px;height:10px;border-width:1.5px;border-color:rgba(139,92,246,.2);border-top-color:var(--purple);"></span>';
  btn.disabled = true;
  renderDynAttrsLoading();

  try {
    const res = await apiFetch('/category-attributes', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category_id: catId,
        attributes: currentItem ? currentItem.attributes : {}
      })
    });
    const data = await res.json();
    if (data.success) {
      categoryAttributes = data.attributes || [];
      prefilledAttributes = data.prefilled || {};
      renderDynAttrs();
      toast(`${categoryAttributes.length} atributos cargados`, 'success');
    } else {
      toast(data.error || 'Error al cargar atributos', 'error');
    }
  } catch(e) { toast('Error de conexión', 'error'); }
  finally {
    btn.innerHTML = '<i data-lucide="refresh-cw"></i> Recargar';
    btn.disabled = false;
    lucide.createIcons();
  }
}

function getDynamicAttrs() {
  const result = {};
  document.querySelectorAll('[data-attr-id]').forEach(el => {
    const val = el.value.trim();
    if (val) result[el.dataset.attrId] = val;
  });
  return result;
}

// ── CHARS ───────────────────────────────────────────────────
function updateChars() {
  const n = document.getElementById('fTitle').value.length;
  const el = document.getElementById('charBadge');
  el.textContent = `${n} / 60`;
  el.className = 'char-badge' + (n>55?' over': n>45?' warn':'');
}

// ── AI ENHANCE ─────────────────────────────────────────────
async function enhance(action, btn) {
  document.querySelectorAll('.ai-pill').forEach(b => b.disabled = true);
  if (btn) btn.classList.add('active');
  try {
    const res = await apiFetch('/enhance', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        title: document.getElementById('fTitle').value,
        description: document.getElementById('fDescription').value,
        category: document.getElementById('fCategory').value,
      })
    });
    const data = await res.json();
    if (!data.success) { toast(data.error, 'error'); return data; }
    const fId = data.field === 'title' ? 'fTitle' : 'fDescription';
    const el = document.getElementById(fId);
    el.value = data.value;
    if (data.field === 'title') updateChars();
    el.classList.add('flash');
    setTimeout(() => el.classList.remove('flash'), 1600);
    return data;
  } catch(e) { toast('Error con IA', 'error'); return null; }
  finally {
    document.querySelectorAll('.ai-pill').forEach(b => b.disabled = false);
    if (btn) btn.classList.remove('active');
  }
}

async function optimizeAll(btn) {
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Optimizando…';
  try {
    // Step 1: Improve title + add keywords
    await enhance('improve_title', null);
    // Step 2: Rewrite description with SEO + keywords
    await enhance('rewrite_description', null);
    toast('Título y descripción optimizados', 'success');
  } catch(e) { toast('Error al optimizar', 'error'); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="wand-2"></i> Optimizar título, descripción y SEO';
    lucide.createIcons();
  }
}

// ── FRIENDLY ERRORS ──────────────────────────────────────────
function friendlyError(raw) {
  if (typeof raw === 'object') raw = JSON.stringify(raw);
  const str = String(raw);
  const issues = [];

  if (/without price/i.test(str)) issues.push('Falta el precio del producto');
  const minPrice = str.match(/minimum of price (\d+)/i);
  if (minPrice) issues.push(`Precio mínimo: $${minPrice[1]} MXN`);

  if (/seller_package_height|seller_package_width|seller_package_length|seller_package_weight/i.test(str)) {
    const missing = [];
    if (/seller_package_height/i.test(str)) missing.push('Alto');
    if (/seller_package_width/i.test(str))  missing.push('Ancho');
    if (/seller_package_length/i.test(str)) missing.push('Largo');
    if (/seller_package_weight/i.test(str)) missing.push('Peso');
    issues.push(`Completa medidas del paquete: ${missing.join(', ')}`);
  }

  if (/pictures\.invalid_size/i.test(str) || /tamaño mínimo.*500/i.test(str))
    issues.push('Fotos muy pequeñas (mínimo 500px)');
  if (/pictures/i.test(str) && /required/i.test(str))
    issues.push('Se necesita al menos una foto');

  const attrMatch = str.match(/attributes? \[([^\]]+)\] (?:is|are) (?:missing|required)/i);
  if (attrMatch) issues.push(`Faltan atributos: ${attrMatch[1]}`);
  if (/GTIN/i.test(str) && issues.every(i => !/GTIN/.test(i)))
    issues.push('Falta código de barras (GTIN)');

  if (/invalid.*category/i.test(str))
    issues.push('Categoría no válida');
  if (/title/i.test(str) && /length|long|short/i.test(str))
    issues.push('Revisa la longitud del título (máx. 60)');
  if (/condition/i.test(str))
    issues.push('Selecciona condición (Nuevo/Usado)');
  if (/quantity/i.test(str) && /invalid|required/i.test(str))
    issues.push('Stock inválido');
  if (/unit is not valid/i.test(str))
    issues.push('Unidades de medida inválidas');

  if (issues.length) return issues.join('\n• ');
  return str.length > 120 ? str.substring(0, 120) + '…' : str;
}

// ── PUBLISH ─────────────────────────────────────────────────
async function publishItem() {
  if (!currentItem) return;
  const btn = document.getElementById('publishBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Publicando…';
  try {
    const res = await apiFetch('/publish', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload())
    });
    const data = await res.json();
    if (!data.success) {
      if (data.error === 'sin_creditos') {
        toast('Sin créditos — ' + data.message, 'error');
        setTimeout(() => { window.location.href = '/billing/plans'; }, 2500);
        return;
      }
      toast(friendlyError(data.error), 'error');
      return;
    }

    // Show preview card
    const preview = document.getElementById('publishPreview');
    document.getElementById('previewImg').src = selectedPhotos[0] || '';
    document.getElementById('previewTitle').textContent = document.getElementById('fTitle').value;
    document.getElementById('previewPrice').textContent = '$' + (parseFloat(document.getElementById('fPrice').value) || 0).toLocaleString('es-MX');
    document.getElementById('previewId').textContent = data.new_id;
    document.getElementById('previewLink').href = data.url;
    preview.classList.add('visible');

    // Update step indicator
    document.getElementById('stepEdit').classList.remove('active');
    document.getElementById('stepEdit').classList.add('done');
    document.getElementById('stepEdit').querySelector('.step-num').textContent = '✓';
    document.getElementById('stepLine2').classList.add('done');
    document.getElementById('stepPublish').classList.add('active');
    document.getElementById('stepPublish').classList.add('done');
    document.getElementById('stepPublish').querySelector('.step-num').textContent = '✓';

    // Hide action bar
    document.getElementById('actionBar').classList.remove('visible');

    // Scroll to preview
    preview.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const link = document.getElementById('resultLink');
    link.href = data.url; link.classList.add('visible');
    toast('¡Publicado! ' + data.new_id, 'success');
  } catch(e) { toast('Error de conexión', 'error'); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="zap"></i> Publicar';
    lucide.createIcons();
  }
}

// ── BLANK MODE ──────────────────────────────────────────────
function toggleBlankMode() {
  const panel = document.getElementById('blankPanel');
  panel.classList.toggle('active');
  if (panel.classList.contains('active')) {
    document.getElementById('emptyState').style.display = 'none';
  } else {
    document.getElementById('emptyState').style.display = '';
  }
}

function handleBlankPhotos(input) {
  const files = Array.from(input.files);
  const preview = document.getElementById('blankPhotoPreview');
  blankPhotos = [];

  files.forEach(file => {
    const reader = new FileReader();
    reader.onload = (e) => {
      blankPhotos.push(e.target.result);
      const img = document.createElement('img');
      img.src = e.target.result;
      preview.appendChild(img);
      checkBlankReady();
    };
    reader.readAsDataURL(file);
  });
}

let predictTimer = null;
function debouncePredictCategory(title) {
  clearTimeout(predictTimer);
  if (title.length < 5) return;
  predictTimer = setTimeout(() => predictCategoryFromTitle(title), 600);
}

async function predictCategoryFromTitle(title) {
  try {
    const res = await apiFetch('/predict-category', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    const data = await res.json();
    if (data.success && data.category_id) {
      blankCategoryId = data.category_id;
      // Get breadcrumb
      const pathRes = await apiFetch('/category-path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id: data.category_id })
      });
      const pathData = await pathRes.json();
      if (pathData.success) {
        const el = document.getElementById('blankCatBreadcrumb');
        document.getElementById('blankCatPath').textContent = pathData.breadcrumb;
        el.classList.add('visible');
      }
      checkBlankReady();
    }
  } catch(e) { console.error(e); }
}

function manualCategorySearch() {
  document.getElementById('blankCatManual').style.display = 'block';
}

let catPathTimer = null;
function debounceCategoryPath(catId) {
  clearTimeout(catPathTimer);
  if (catId.length < 4) return;
  catPathTimer = setTimeout(async () => {
    blankCategoryId = catId;
    try {
      const res = await apiFetch('/category-path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id: catId })
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('blankCatPath').textContent = data.breadcrumb;
        document.getElementById('blankCatBreadcrumb').classList.add('visible');
      }
    } catch(e) {}
    checkBlankReady();
  }, 400);
}

function checkBlankReady() {
  const title = document.getElementById('blankTitle').value.trim();
  const ready = title.length >= 3 && blankCategoryId;
  document.getElementById('blankContinueBtn').disabled = !ready;
}

function startBlankProduct() {
  const title = document.getElementById('blankTitle').value.trim();
  if (!title || !blankCategoryId) return;

  // Create a minimal item object
  currentItem = {
    success: true, type: 'blank', source: 'manual',
    mlm_id: '', title, price: 0, currency: 'MXN',
    category_id: blankCategoryId, condition: 'new',
    description: '', photos: blankPhotos.length ? blankPhotos : [],
    attributes: {}, listing_type: 'gold_special',
    available_quantity: 1, permalink: ''
  };
  selectedPhotos = [...currentItem.photos];
  categoryAttributes = [];
  prefilledAttributes = {};

  render(currentItem);

  // Load category attributes for blank product
  reloadCategoryAttrs();

  toast('Producto en blanco creado', 'success');
}

// ── CATEGORY BREADCRUMB ─────────────────────────────────────
async function loadCategoryBreadcrumb() {
  const catId = document.getElementById('fCategory').value.trim();
  if (!catId) return;
  try {
    const res = await apiFetch('/category-path', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_id: catId })
    });
    const data = await res.json();
    if (data.success) {
      const el = document.getElementById('catBreadcrumbEdit');
      document.getElementById('catPathText').textContent = data.breadcrumb;
      el.classList.add('visible');
    }
  } catch(e) {}
}

// ── NAVIGATION ──────────────────────────────────────────────
function goBack() {
  document.getElementById('workspace').classList.remove('visible');
  document.getElementById('actionBar').classList.remove('visible');
  document.getElementById('heroSection').style.display = '';
  document.getElementById('emptyState').style.display = '';
  document.getElementById('blankPanel').classList.remove('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetApp() {
  currentItem = null; selectedPhotos = []; blankPhotos = [];
  categoryAttributes = []; prefilledAttributes = [];
  blankCategoryId = '';
  document.getElementById('mlInput').value = '';
  document.getElementById('blankTitle').value = '';
  document.getElementById('blankPhotoPreview').innerHTML = '';
  document.getElementById('blankCatBreadcrumb').classList.remove('visible');
  document.getElementById('publishPreview').classList.remove('visible');
  document.getElementById('catBreadcrumbEdit').classList.remove('visible');

  // Reset step indicator
  const stepEdit = document.getElementById('stepEdit');
  stepEdit.classList.add('active');
  stepEdit.classList.remove('done');
  stepEdit.querySelector('.step-num').textContent = '2';
  document.getElementById('stepLine2').classList.remove('done');
  const stepPub = document.getElementById('stepPublish');
  stepPub.classList.remove('active', 'done');
  stepPub.querySelector('.step-num').textContent = '3';

  goBack();
}

// ── FILL TEMPLATE (preserved) ───────────────────────────────
let selectedTemplateFile = null;

function openFillModal() {
  if (!currentItem) { toast('Extrae un producto primero', 'error'); return; }
  document.getElementById('fillModal').classList.add('active');
}

function closeFillModal() {
  document.getElementById('fillModal').classList.remove('active');
  selectedTemplateFile = null;
  document.getElementById('dropZone').classList.remove('has-file');
  document.getElementById('selectedFileName').style.display = 'none';
  document.getElementById('confirmFillBtn').disabled = true;
  document.getElementById('templateFileInput').value = '';
}

function handleFileSelect(input) {
  const file = input.files[0];
  if (!file) return;
  selectedTemplateFile = file;
  const nameEl = document.getElementById('selectedFileName');
  nameEl.textContent = '✓ ' + file.name;
  nameEl.style.display = 'block';
  document.getElementById('dropZone').classList.add('has-file');
  document.getElementById('confirmFillBtn').disabled = false;
}

document.addEventListener('DOMContentLoaded', () => {
  const dz = document.getElementById('dropZone');
  if (dz) {
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
    dz.addEventListener('drop', e => {
      e.preventDefault(); dz.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file && file.name.endsWith('.xlsx')) {
        selectedTemplateFile = file;
        const nameEl = document.getElementById('selectedFileName');
        nameEl.textContent = '✓ ' + file.name;
        nameEl.style.display = 'block';
        dz.classList.add('has-file');
        document.getElementById('confirmFillBtn').disabled = false;
      } else {
        toast('Solo archivos .xlsx', 'error');
      }
    });
  }
});

async function fillTemplate() {
  if (!currentItem || !selectedTemplateFile) return;
  const btn = document.getElementById('confirmFillBtn');
  btn.disabled = true;
  btn.textContent = 'Procesando…';
  try {
    const fd = new FormData();
    fd.append('template', selectedTemplateFile);
    fd.append('item_data', JSON.stringify(payload()));
    const res = await apiFetch('/fill-template', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      toast('Error: ' + (err.error || res.statusText), 'error');
      return;
    }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `ML_plantilla_${currentItem.mlm_id}_lista.xlsx`;
    a.click();
    toast('¡Plantilla lista!', 'success');
    closeFillModal();
  } catch(e) { toast('Error de conexión', 'error'); }
  finally {
    btn.disabled = false;
    btn.textContent = 'Rellenar y descargar';
  }
}

// ── EXCEL / PHOTOS (preserved but hidden) ──────────────────
async function exportExcel() {
  if (!currentItem) return;
  toast('Generando Excel…', 'info');
  const res = await apiFetch('/export-excel', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload())
  });
  if (!res.ok) { toast('Error al generar Excel', 'error'); return; }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `miraarlo_${currentItem.mlm_id}.xlsx`;
  a.click();
  toast('Excel descargado', 'success');
}

async function downloadPhotos() {
  if (!currentItem || !selectedPhotos.length) { toast('Sin fotos disponibles', 'error'); return; }
  toast('Descargando fotos…', 'info');
  const res = await apiFetch('/download-photos', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photos: selectedPhotos, mlm_id: currentItem.mlm_id })
  });
  if (!res.ok) { toast('Error al descargar fotos', 'error'); return; }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `fotos_${currentItem.mlm_id}.zip`;
  a.click();
  toast('Fotos descargadas', 'success');
}

async function refreshToken() {
  toast('Refrescando token…', 'info');
  const res = await apiFetch('/refresh-token', { method: 'POST' });
  const data = await res.json();
  if (data.success) {
    const badge = document.getElementById('statusBadge');
    badge.classList.add('ok');
    document.getElementById('statusText').textContent = 'Conectado';
    toast('Token refrescado', 'success');
  } else { toast(data.error, 'error'); }
}

// ── PAYLOAD ─────────────────────────────────────────────────
function payload() {
  return {
    ...currentItem,
    title:              document.getElementById('fTitle').value,
    price:              parseFloat(document.getElementById('fPrice').value) || 0,
    available_quantity: parseInt(document.getElementById('fStock').value) || 1,
    condition:          document.getElementById('fCondition').value,
    category_id:        document.getElementById('fCategory').value,
    description:        document.getElementById('fDescription').value,
    photos:             selectedPhotos,
    dynamic_attrs:      getDynamicAttrs(),
    pkg_height:   parseFloat(document.getElementById('fPkgHeight').value) || null,
    pkg_width:    parseFloat(document.getElementById('fPkgWidth').value)  || null,
    pkg_length:   parseFloat(document.getElementById('fPkgLength').value) || null,
    pkg_weight:   parseFloat(document.getElementById('fPkgWeight').value) || null,
  };
}

let tt;
function toast(msg, type='info') {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = `show ${type}`;
  clearTimeout(tt);
  const duration = type === 'error' ? 6000 : 3500;
  tt = setTimeout(() => el.className = '', duration);
}
