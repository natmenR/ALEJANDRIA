// ============================================================================
// REPORTE.JS - VERSIÓN FINAL SIMPLIFICADA
// ============================================================================

const meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const diasSem = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab'];
let rules = [];

// DEPENDENCIAS (simplificado: solo DEPENDE_DE)
let dependencias = [];

function init() {
    const wg = document.getElementById('week-grid');
    if (wg) diasSem.forEach((d, i) => wg.innerHTML += `<div class="select-btn" data-type="week" data-val="${i}">${d}</div>`);
    
    const dg = document.getElementById('day-grid');
    if (dg) for(let i=1; i<=31; i++) dg.innerHTML += `<div class="select-btn" data-type="day" data-val="${i}">${i}</div>`;

    document.querySelectorAll('.select-btn').forEach(btn => {
        btn.onclick = () => btn.classList.toggle('active');
    });

    handleFrecuenciaChange();
    
    const form = document.querySelector('form');
    if (form) form.addEventListener('submit', handleSubmit);
}

function handleFrecuenciaChange() {
    const freq = document.getElementById('frecuencia').value;
    const isCycle = ['anual', 'semestral', 'cuatrimestral', 'trimestral'].includes(freq);
    
    document.getElementById('dyn-area').classList.toggle('hidden', isCycle);
    document.getElementById('rules-list').classList.toggle('hidden', isCycle);
    document.getElementById('hitos-grid').classList.toggle('hidden', !isCycle);
    document.getElementById('empty-state').classList.add('hidden');

    if(isCycle) {
        buildCycleHitos(freq);
    } else {
        renderRules();
        document.getElementById('week-box').classList.toggle('hidden', freq === 'diaria');
        document.getElementById('day-box').classList.toggle('hidden', freq !== 'mensual');
    }
}

function addRule() {
    const freq = document.getElementById('frecuencia').value;
    const time = document.getElementById('rule-time').value;
    const weeks = Array.from(document.querySelectorAll('.select-btn[data-type="week"].active')).map(b => parseInt(b.dataset.val));
    const days = Array.from(document.querySelectorAll('.select-btn[data-type="day"].active')).map(b => parseInt(b.dataset.val));

    if(freq === 'semanal' && weeks.length === 0) return alert("Selecciona días de la semana.");
    if(freq === 'mensual' && days.length === 0) return alert("Selecciona días del mes.");

    rules.push({ id: Date.now(), freq, time, weeks, days });
    renderRules();
    
    document.querySelectorAll('.select-btn').forEach(b => b.classList.remove('active'));
}

function renderRules() {
    const list = document.getElementById('rules-list');
    if(rules.length === 0) {
        list.innerHTML = '';
        document.getElementById('empty-state').classList.remove('hidden');
        return;
    }
    document.getElementById('empty-state').classList.add('hidden');
    list.innerHTML = rules.map(r => `
        <div class="rule-badge">
            <div class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-[10px]">${r.time}</div>
            <div class="flex-1 text-gray-600 truncate">
                ${r.freq === 'diaria' ? 'Todos los días' : ''}
                ${r.weeks.length ? 'Sem: ' + r.weeks.map(w => diasSem[w]).join(',') : ''}
                ${r.days.length ? 'Días: ' + r.days.join(',') : ''}
            </div>
            <button type="button" onclick="removeRule(${r.id})" class="text-red-300 hover:text-red-500"><i class="fas fa-times"></i></button>
        </div>
    `).join('');
}

function removeRule(id) {
    rules = rules.filter(r => r.id !== id);
    renderRules();
}

function buildCycleHitos(freq) {
    const n = { 'anual': 1, 'semestral': 2, 'cuatrimestral': 3, 'trimestral': 4 }[freq];
    const grid = document.getElementById('hitos-grid');
    grid.innerHTML = '';
    for(let i=1; i<=n; i++) {
        grid.innerHTML += `
            <div class="hito-card shadow-sm border-blue-100 bg-blue-50/30">
                <div class="text-[9px] font-black text-blue-800 uppercase mb-3 border-b border-blue-100 pb-1">Hito #${i}</div>
                <div class="grid grid-cols-1 gap-2">
                    <select class="input-field !py-1 hito-mes">
                        ${meses.map((m, idx) => `<option value="${idx}" ${getDefaultMonth(i, n) === idx ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                    <div class="flex gap-2">
                        <input type="number" value="1" min="1" max="31" class="input-field !py-1 hito-dia" placeholder="Día">
                        <input type="time" value="08:00" class="input-field !py-1 hito-hora">
                    </div>
                </div>
            </div>
        `;
    }
}

function getDefaultMonth(i, total) {
    if(total === 4) return (i-1)*3;
    if(total === 3) return (i-1)*4;
    if(total === 2) return (i-1)*6;
    return 0;
}

function handleSubmit(e) {
    const freq = document.getElementById('frecuencia').value;
    const isCycle = ['anual', 'semestral', 'cuatrimestral', 'trimestral'].includes(freq);

    let finalProgram = [];

    if (isCycle) {
        document.querySelectorAll('.hito-card').forEach(c => {
            finalProgram.push({
                type: 'fixed-cycle',
                mes: parseInt(c.querySelector('.hito-mes').value),
                dia: parseInt(c.querySelector('.hito-dia').value),
                hora: c.querySelector('.hito-hora').value
            });
        });
    } else {
        if (rules.length === 0) {
            alert("Debe agregar al menos una regla dinámica.");
            e.preventDefault();
            return;
        }

        finalProgram = rules.map(r => ({
            type: 'dynamic',
            freq: r.freq,
            time: r.time,
            weeks: r.weeks,
            days: r.days
        }));
    }

    let reglasInput = document.querySelector('input[name="reglas_json"]');
    if (!reglasInput) {
        reglasInput = document.createElement('input');
        reglasInput.type = 'hidden';
        reglasInput.name = 'reglas_json';
        e.target.appendChild(reglasInput);
    }

    reglasInput.value = JSON.stringify(finalProgram);

    // Actualizar dependencias
    document.getElementById('dependenciasHidden').value = JSON.stringify(dependencias);
}

// ============================================================================
// DEPENDENCIAS
// ============================================================================

function agregarDep() {
    const select = document.getElementById('reporteSelect');
    const idReporte = select.value;
    
    if (!idReporte) {
        alert('Selecciona un reporte');
        return;
    }
    
    const option = select.options[select.selectedIndex];
    const codigo = option.dataset.codigo;
    const nombre = option.dataset.nombre;
    const tipo = document.getElementById('tipoSelect').value;
    const criticidad = document.getElementById('criticidadSelect').value;
    const obs = document.getElementById('observacionesTextarea').value.trim();
    
    // Validar duplicado
    if (dependencias.some(d => d.id_reporte === parseInt(idReporte))) {
        alert('Esta dependencia ya fue agregada');
        return;
    }
    
    dependencias.push({
        id_reporte: parseInt(idReporte),
        codigo,
        nombre,
        tipo_dependencia: tipo,
        criticidad,
        observaciones: obs || null
    });
    
    renderDep();
    
    // Limpiar formulario
    document.getElementById('reporteSelect').value = '';
    document.getElementById('observacionesTextarea').value = '';
}

function renderDep() {
    const list = document.getElementById('depList');
    const count = document.getElementById('depCount');
    
    count.textContent = dependencias.length;
    
    if (dependencias.length === 0) {
        list.innerHTML = `
            <div class="text-center py-8 text-gray-400 italic text-sm">
                <i class="fas fa-inbox fa-2x mb-2"></i>
                <p>No hay dependencias agregadas</p>
            </div>
        `;
        return;
    }
    
    list.innerHTML = dependencias.map((d, i) => `
        <div class="dep-item">
            <div class="flex-1">
                <div class="text-xs font-bold text-blue-600">${d.codigo}</div>
                <div class="text-sm font-semibold text-gray-800 mt-1">${d.nombre}</div>
                <div class="flex gap-2 mt-2">
                    <span class="dep-badge tipo">${d.tipo_dependencia}</span>
                    <span class="dep-badge crit-${d.criticidad.toLowerCase()}">${d.criticidad}</span>
                </div>
                ${d.observaciones ? `<div class="text-xs text-gray-500 mt-2 italic"><i class="fas fa-comment-dots mr-1"></i>${d.observaciones}</div>` : ''}
            </div>
            <button type="button" onclick="removeDep(${i})" class="dep-remove">
                <i class="fas fa-trash-alt"></i>
            </button>
        </div>
    `).join('');
}

function removeDep(index) {
    if (confirm('¿Eliminar esta dependencia?')) {
        dependencias.splice(index, 1);
        renderDep();
    }
}

window.onload = init;
