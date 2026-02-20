// Reset all brew form fields to blank
function resetBrewForm() {
    const allFields = [
        'roaster', 'bean_name', 'bean_origin', 'bean_process', 'roast_date',
        'roast_level', 'bean_amount_grams', 'grind_setting', 'grinder',
        'bloom_time_seconds', 'bloom_water_ml', 'water_amount_ml',
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
    const bloomEl = document.getElementById('bloom-toggle');
    if (bloomEl) {
        bloomEl.checked = false;
        document.getElementById('bloom-fields').style.display = 'none';
    }
    const tplIdEl = document.querySelector('[name="template_id"]');
    if (tplIdEl) tplIdEl.value = '';
}

// Template loading
async function loadTemplate(selectEl) {
    const id = selectEl.value;
    // Always reset the form first
    resetBrewForm();
    if (!id) return;
    try {
        const resp = await fetch(`/api/v1/templates/${id}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const fieldMap = {
            roaster: 'roaster', bean_name: 'bean_name', bean_origin: 'bean_origin',
            bean_process: 'bean_process', roast_date: 'roast_date', roast_level: 'roast_level',
            bean_amount_grams: 'bean_amount_grams', grind_setting: 'grind_setting',
            grinder: 'grinder', bloom_time_seconds: 'bloom_time_seconds',
            bloom_water_ml: 'bloom_water_ml', water_amount_ml: 'water_amount_ml',
            brew_method: 'brew_method', brew_device: 'brew_device',
            water_filter_type: 'water_filter_type',
            altitude_ft: 'altitude_ft', notes: 'notes',
        };
        for (const [key, formName] of Object.entries(fieldMap)) {
            const el = document.querySelector(`[name="${formName}"]`);
            if (el && data[key] != null) el.value = data[key];
        }
        // Handle brew_time_seconds as m:ss
        if (data.brew_time_seconds != null) {
            const btEl = document.querySelector('[name="brew_time_seconds"]');
            if (btEl) {
                const m = Math.floor(data.brew_time_seconds / 60);
                const s = data.brew_time_seconds % 60;
                btEl.value = `${m}:${String(s).padStart(2, '0')}`;
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
        // Handle bloom checkbox and fields visibility
        if (data.bloom) {
            const bloomEl = document.getElementById('bloom-toggle');
            if (bloomEl) {
                bloomEl.checked = true;
                document.getElementById('bloom-fields').style.display = '';
            }
        }
        // Set template_id hidden field
        const tplIdEl = document.querySelector('[name="template_id"]');
        if (tplIdEl) tplIdEl.value = id;
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
        // Add new checkbox pill to the container
        const container = document.getElementById('flavor-checkboxes');
        const label = document.createElement('label');
        label.className = 'checkbox-pill';
        label.innerHTML = `<input type="checkbox" name="flavor_notes_expected" value="${note.name}" onchange="limitCheckboxes(this, 4)"><span>${note.name}</span>`;
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
