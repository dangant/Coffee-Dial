// Reset all brew form fields to blank
function resetBrewForm() {
    const allFields = [
        'roaster', 'bean_name', 'bean_origin', 'bean_process', 'roast_date',
        'roast_level', 'bean_amount_grams', 'grind_setting', 'grind_suggestion_um', 'grinder',
        'bloom_time_seconds', 'bloom_water_ml', 'bloom_pour_time_seconds',
        'first_pour_grams', 'first_pour_time_seconds',
        'second_pour_grams', 'second_pour_time_seconds',
        'final_pour_grams', 'final_pour_time_seconds', 'pour_method',
        'water_amount_ml',
        'brew_method', 'brew_device', 'water_filter_type', 'altitude_ft',
    ];
    allFields.forEach(name => {
        const el = document.querySelector(`[name="${name}"]`);
        if (el) el.value = '';
    });
    const btEl = document.querySelector('[name="brew_time_seconds"]');
    if (btEl) btEl.value = '';
    const notesEl = document.querySelector('[name="notes"]');
    if (notesEl) notesEl.value = '';
    const tempInput = document.getElementById('water-temp-input');
    if (tempInput) tempInput.value = '';
    toggleTemp('F');
    document.querySelectorAll('[name="flavor_notes_expected"]').forEach(cb => cb.checked = false);
    enforceCheckboxLimit(4);
    const tplIdEl = document.querySelector('[name="template_id"]');
    if (tplIdEl) tplIdEl.value = '';
    showTemplateProductLink(null);
    captureDoseBaseline();
}

// Pre-tick "first brew" for a template nothing has been brewed from yet.
// A manual click marks the box as touched and we stop guessing for the rest
// of the form session.
function applyFirstBrewHint(selectEl) {
    const cb = document.getElementById('first-brew-checkbox');
    if (!cb || cb.dataset.touched) return;
    const opt = selectEl && selectEl.selectedOptions[0];
    cb.checked = !!(selectEl && selectEl.value && opt && opt.dataset.firstBrew === '1');
}

// Template loading
async function loadTemplate(selectEl) {
    const id = selectEl.value;
    // Always reset the form first
    resetBrewForm();
    applyFirstBrewHint(selectEl);
    if (!id) return;
    try {
        const resp = await fetch(`/api/v1/templates/${id}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const fieldMap = {
            roaster: 'roaster', bean_name: 'bean_name', bean_origin: 'bean_origin',
            bean_process: 'bean_process', roast_date: 'roast_date', roast_level: 'roast_level',
            bean_amount_grams: 'bean_amount_grams', grind_setting: 'grind_setting',
            grind_suggestion_um: 'grind_suggestion_um',
            grinder: 'grinder', bloom_time_seconds: 'bloom_time_seconds',
            bloom_water_ml: 'bloom_water_ml', water_amount_ml: 'water_amount_ml',
            brew_method: 'brew_method', brew_device: 'brew_device',
            first_pour_grams: 'first_pour_grams', second_pour_grams: 'second_pour_grams',
            final_pour_grams: 'final_pour_grams', pour_method: 'pour_method',
            water_filter_type: 'water_filter_type',
            altitude_ft: 'altitude_ft', notes: 'notes',
        };
        for (const [key, formName] of Object.entries(fieldMap)) {
            const el = document.querySelector(`[name="${formName}"]`);
            if (el && data[key] != null) el.value = data[key];
        }
        // Time fields render as m:ss
        for (const field of ['brew_time_seconds', 'bloom_pour_time_seconds',
                             'first_pour_time_seconds', 'second_pour_time_seconds',
                             'final_pour_time_seconds']) {
            if (data[field] != null) {
                const el = document.querySelector(`[name="${field}"]`);
                if (el) {
                    const m = Math.floor(data[field] / 60);
                    const s = data[field] % 60;
                    el.value = `${m}:${String(s).padStart(2, '0')}`;
                }
            }
        }
        // Handle water temp
        if (data.water_temp_f != null) {
            const tempInput = document.getElementById('water-temp-input');
            if (tempInput) tempInput.value = data.water_temp_f;
            toggleTemp('F');
        } else if (data.water_temp_c != null) {
            const tempInput = document.getElementById('water-temp-input');
            if (tempInput) tempInput.value = data.water_temp_c;
            toggleTemp('C');
        }
        // Handle flavor notes checkboxes
        if (data.flavor_notes_expected) {
            const notes = data.flavor_notes_expected.split(', ');
            document.querySelectorAll('[name="flavor_notes_expected"]').forEach(cb => {
                cb.checked = notes.includes(cb.value);
            });
            enforceCheckboxLimit(4);
        }
        // Set template_id hidden field
        const tplIdEl = document.querySelector('[name="template_id"]');
        if (tplIdEl) tplIdEl.value = id;
        showTemplateProductLink(data.product_url);
        // The loaded recipe is what a dose change scales from
        captureDoseBaseline();
    } catch (e) {
        console.error('Failed to load template:', e);
    }
}

// Slider value display
function updateSliderValue(slider) {
    const display = slider.parentElement.querySelector('.slider-value');
    if (display) display.textContent = slider.value;
}

// Init sliders on page load
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[type="range"]').forEach(slider => {
        updateSliderValue(slider);
        slider.addEventListener('input', () => updateSliderValue(slider));
    });
    // Init checkbox limit on load
    enforceCheckboxLimit(4);
});

// Temperature toggle — single input field, switch between F and C
let currentTempUnit = 'F';
function toggleTemp(unit) {
    const input = document.getElementById('water-temp-input');
    const unitInput = document.getElementById('water-temp-unit');
    const btns = document.querySelectorAll('.temp-toggle button');

    btns.forEach(b => b.classList.remove('active'));
    document.querySelector(`.temp-toggle button[data-unit="${unit}"]`).classList.add('active');

    // Convert existing value
    if (input && input.value && unit !== currentTempUnit) {
        const val = parseFloat(input.value);
        if (unit === 'C') {
            input.value = Math.round((val - 32) * 5 / 9 * 10) / 10;
            input.placeholder = 'e.g., 96';
        } else {
            input.value = Math.round(val * 9 / 5 + 32);
            input.placeholder = 'e.g., 205';
        }
    } else if (input && !input.value) {
        input.placeholder = unit === 'C' ? 'e.g., 96' : 'e.g., 205';
    }

    if (unitInput) unitInput.value = unit;
    currentTempUnit = unit;
}

// Limit flavor note checkboxes to max selections
function limitCheckboxes(checkbox, max) {
    const checked = document.querySelectorAll('[name="flavor_notes_expected"]:checked');
    if (checked.length > max) {
        checkbox.checked = false;
    }
    enforceCheckboxLimit(max);
}

function enforceCheckboxLimit(max) {
    const checked = document.querySelectorAll('[name="flavor_notes_expected"]:checked');
    const all = document.querySelectorAll('[name="flavor_notes_expected"]');
    // Always enable all checkboxes — the limitCheckboxes handler prevents exceeding max
    all.forEach(cb => cb.disabled = false);
}

// Inline add flavor note via API (no form submission)
async function addFlavorNote() {
    const input = document.getElementById('new-flavor-input');
    const name = input.value.trim();
    if (!name) return;
    try {
        const resp = await fetch('/api/v1/lookups/flavor-notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (!resp.ok) {
            if (resp.status === 422) {
                alert('Invalid flavor note name.');
            }
            return;
        }
        const note = await resp.json();
        // Add new checkbox pill to the container, pre-selected (adding it means you want it)
        // unless the 4-note limit is already hit
        const checkedCount = document.querySelectorAll('[name="flavor_notes_expected"]:checked').length;
        const checked = checkedCount < 4 ? ' checked' : '';
        const container = document.getElementById('flavor-checkboxes');
        const label = document.createElement('label');
        label.className = 'checkbox-pill';
        label.innerHTML = `<input type="checkbox" name="flavor_notes_expected" value="${note.name}"${checked} onchange="limitCheckboxes(this, 4)"><span>${note.name}</span>`;
        container.appendChild(label);
        input.value = '';
        enforceCheckboxLimit(4);
        // Re-apply search filter if active
        const search = document.getElementById('flavor-search');
        if (search && search.value) filterFlavorNotes(search.value);
    } catch (e) {
        console.error('Failed to add flavor note:', e);
    }
}

// Filter flavor note pills by search text
function filterFlavorNotes(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('#flavor-checkboxes .checkbox-pill').forEach(pill => {
        const text = pill.querySelector('span').textContent.toLowerCase();
        pill.style.display = text.includes(q) || pill.querySelector('input').checked ? '' : 'none';
    });
}

// Inline add brew device via API
async function addBrewDevice() {
    const input = document.getElementById('new-device-input');
    const name = input.value.trim();
    if (!name) return;
    try {
        const resp = await fetch('/api/v1/lookups/brew-devices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (!resp.ok) return;
        const device = await resp.json();
        // Add to select dropdown
        const select = document.querySelector('select[name="brew_device"]');
        if (select) {
            const opt = document.createElement('option');
            opt.value = device.name;
            opt.textContent = device.name;
            opt.selected = true;
            select.appendChild(opt);
        }
        input.value = '';
    } catch (e) {
        console.error('Failed to add brew device:', e);
    }
}

// Inline add brew method via API
async function addBrewMethod() {
    const input = document.getElementById('new-method-input');
    const name = input.value.trim();
    if (!name) return;
    try {
        const resp = await fetch('/api/v1/lookups/brew-methods', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (!resp.ok) return;
        const method = await resp.json();
        const select = document.querySelector('select[name="brew_method"]');
        if (select) {
            const opt = document.createElement('option');
            opt.value = method.name;
            opt.textContent = method.name;
            opt.selected = true;
            select.appendChild(opt);
        }
        input.value = '';
    } catch (e) {
        console.error('Failed to add brew method:', e);
    }
}

// Inline add grinder via API
async function addGrinder() {
    const input = document.getElementById('new-grinder-input');
    const name = input.value.trim();
    if (!name) return;
    try {
        const resp = await fetch('/api/v1/lookups/grinders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (!resp.ok) return;
        const grinder = await resp.json();
        const select = document.querySelector('select[name="grinder"]');
        if (select) {
            const opt = document.createElement('option');
            opt.value = grinder.name;
            opt.textContent = grinder.name;
            opt.selected = true;
            select.appendChild(opt);
        }
        input.value = '';
    } catch (e) {
        console.error('Failed to add grinder:', e);
    }
}

// CSV export
async function exportCSV() {
    try {
        const resp = await fetch('/api/v1/brews/?limit=10000');
        if (!resp.ok) return;
        const brews = await resp.json();
        if (brews.length === 0) { alert('No brews to export'); return; }
        const headers = Object.keys(brews[0]);
        const csv = [headers.join(',')];
        for (const brew of brews) {
            csv.push(headers.map(h => {
                const v = brew[h];
                if (v == null) return '';
                const s = String(v);
                return s.includes(',') ? `"${s}"` : s;
            }).join(','));
        }
        const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'brews.csv';
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('Export failed:', e);
    }
}

// --- Dose scaling -----------------------------------------------------------
// Changing the coffee dose rescales every water number by the same multiplier,
// so the brew ratio (and the shape of the pour schedule) is preserved.
// Pour times are left alone.
const DOSE_WATER_FIELDS = [
    'water_amount_ml', 'bloom_water_ml',
    'first_pour_grams', 'second_pour_grams', 'final_pour_grams',
];
let doseBaseline = null;  // { dose: number, water: { fieldName: number } }

function doseField() {
    return document.querySelector('[name="bean_amount_grams"]');
}

// Snapshot the current dose + water values as the recipe we scale from.
function captureDoseBaseline() {
    const input = doseField();
    if (!input) return;
    const dose = parseFloat(input.value);
    const water = {};
    DOSE_WATER_FIELDS.forEach(name => {
        const el = document.querySelector(`[name="${name}"]`);
        if (el && el.value !== '') water[name] = parseFloat(el.value);
    });
    doseBaseline = dose > 0 ? { dose, water } : null;
    hideDoseNotice();
}

function scaleWaterToDose() {
    const input = doseField();
    if (!input || !doseBaseline) return;
    const dose = parseFloat(input.value);
    if (!(dose > 0)) return;
    if (Math.abs(dose - doseBaseline.dose) < 1e-9) {
        hideDoseNotice();
        return;
    }
    // Always scale from the baseline, never from already-scaled values, so
    // rounding never compounds as you nudge the dose around.
    const mult = dose / doseBaseline.dose;
    Object.entries(doseBaseline.water).forEach(([name, base]) => {
        const el = document.querySelector(`[name="${name}"]`);
        if (el) el.value = Math.round(base * mult);
    });
    showDoseNotice(dose, mult);
}

function undoDoseScaling() {
    const input = doseField();
    if (!input || !doseBaseline) return;
    input.value = doseBaseline.dose;
    Object.entries(doseBaseline.water).forEach(([name, base]) => {
        const el = document.querySelector(`[name="${name}"]`);
        if (el) el.value = base;
    });
    hideDoseNotice();
}

function showDoseNotice(dose, mult) {
    const notice = document.getElementById('dose-scale-notice');
    if (!notice) return;
    const text = notice.querySelector('.dose-scale-text');
    const water = doseBaseline.water.water_amount_ml;
    const ratio = water ? ` — ratio 1:${(water / doseBaseline.dose).toFixed(1)} kept` : '';
    text.textContent = `Water scaled ×${mult.toFixed(3)} for ${dose} g coffee${ratio}.`;
    notice.style.display = 'flex';
}

function hideDoseNotice() {
    const notice = document.getElementById('dose-scale-notice');
    if (notice) notice.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', () => {
    const input = doseField();
    if (!input) return;
    captureDoseBaseline();
    input.addEventListener('change', scaleWaterToDose);
    // A hand-edited water value becomes the new recipe to scale from.
    DOSE_WATER_FIELDS.forEach(name => {
        const el = document.querySelector(`[name="${name}"]`);
        if (el) el.addEventListener('change', captureDoseBaseline);
    });
});

// --- Roaster product link ---------------------------------------------------
// Templates can carry the roaster's product page (auto-filled by the Onyx
// importer, or typed on the template form) so the source recipe is one click away.
function productLinkLabel(url) {
    return url.includes('onyxcoffeelab.com') ? '☕ View on Onyx ↗' : '🔗 View product page ↗';
}

// Brew form: surface the selected template's product page under the picker.
function showTemplateProductLink(url) {
    const link = document.getElementById('template-product-link');
    if (!link) return;
    if (!url) {
        link.style.display = 'none';
        link.removeAttribute('href');
        return;
    }
    link.href = url;
    link.textContent = productLinkLabel(url);
    link.style.display = 'inline-block';
}

// Template form: keep the "Open page" link in step with what is typed.
function updateProductLinkPreview() {
    const input = document.getElementById('product-url-input');
    const link = document.getElementById('product-url-open');
    if (!input || !link) return;
    const url = input.value.trim();
    const ok = /^https?:\/\//i.test(url);
    link.href = ok ? url : '#';
    link.textContent = ok ? productLinkLabel(url) : '';
    link.style.display = ok ? 'inline-block' : 'none';
}

document.addEventListener('DOMContentLoaded', updateProductLinkPreview);
