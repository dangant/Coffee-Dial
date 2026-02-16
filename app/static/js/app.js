// Template loading
async function loadTemplate(selectEl) {
    const id = selectEl.value;
    if (!id) return;
    try {
        const resp = await fetch(`/api/v1/templates/${id}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const fieldMap = {
            roaster: 'roaster', bean_name: 'bean_name', bean_origin: 'bean_origin',
            bean_process: 'bean_process', roast_level: 'roast_level',
            flavor_notes_expected: 'flavor_notes_expected',
            bean_amount_grams: 'bean_amount_grams', grind_setting: 'grind_setting',
            grinder: 'grinder', bloom_time_seconds: 'bloom_time_seconds',
            bloom_water_ml: 'bloom_water_ml', water_amount_ml: 'water_amount_ml',
            water_temp_f: 'water_temp_f', water_temp_c: 'water_temp_c',
            brew_method: 'brew_method', brew_device: 'brew_device',
            brew_time_seconds: 'brew_time_seconds', water_filter_type: 'water_filter_type',
            paper_filter_type: 'paper_filter_type', altitude_ft: 'altitude_ft',
            notes: 'notes',
        };
        for (const [key, formName] of Object.entries(fieldMap)) {
            if (data[key] != null) {
                const el = document.querySelector(`[name="${formName}"]`);
                if (el) el.value = data[key];
            }
        }
        // Handle bloom checkbox
        if (data.bloom != null) {
            const bloomEl = document.querySelector('[name="bloom"]');
            if (bloomEl) bloomEl.checked = data.bloom;
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
});

// Temperature conversion
function toggleTemp(unit) {
    const fInput = document.querySelector('[name="water_temp_f"]');
    const cInput = document.querySelector('[name="water_temp_c"]');
    const fGroup = document.getElementById('temp-f-group');
    const cGroup = document.getElementById('temp-c-group');
    const btns = document.querySelectorAll('.temp-toggle button');

    btns.forEach(b => b.classList.remove('active'));
    document.querySelector(`.temp-toggle button[data-unit="${unit}"]`).classList.add('active');

    if (unit === 'F') {
        fGroup.style.display = '';
        cGroup.style.display = 'none';
        if (cInput.value && !fInput.value) {
            fInput.value = Math.round(parseFloat(cInput.value) * 9 / 5 + 32);
        }
    } else {
        fGroup.style.display = 'none';
        cGroup.style.display = '';
        if (fInput.value && !cInput.value) {
            cInput.value = Math.round((parseFloat(fInput.value) - 32) * 5 / 9);
        }
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
