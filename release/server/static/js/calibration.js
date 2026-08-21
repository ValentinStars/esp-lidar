// клиентский javascript для интерфейса калибровки зон лидара

const canvas = document.getElementById('lidarCanvas');
const ctx = canvas.getContext('2d');
const width = canvas.width;
const height = canvas.height;
const centerX = width / 2;
const centerY = height / 2;

// максимальная дистанция для отрисовки (мм)
const maxDistance = 6000;
// коэффициент масштабирования: пикселей на миллиметр
const scale = (width / 2 - 20) / maxDistance;

// данные последнего скана: массив 360 значений
let currentScan = new Array(360).fill(0);

// список заданных стекол (panes) и зон
let panes = [];
let nextPaneId = 1;
let nextZoneId = 1;

// флаги рисования мышью
let isDrawing = false;
let startDrawAngle = 0;
let currentDrawAngle = 0;

// угол наведения для диагностики
let hoverAngle = -1;

document.addEventListener('DOMContentLoaded', () => {
    // кнопка переключения в режим калибровки
    document.getElementById('btnStartCalibMode').addEventListener('click', async () => {
        try {
            await fetch(`/api/devices/${DEVICE_SN}/cmd`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cmd: 'start_calib' })
            });
            document.getElementById('scanStatusBadge').textContent = 'Стриминг скана...';
            document.getElementById('scanStatusBadge').className = 'badge badge-online';
        } catch (e) {
            console.error(e);
        }
    });

    // кнопка переключения в боевой режим
    document.getElementById('btnMonitoringMode').addEventListener('click', async () => {
        try {
            await fetch(`/api/devices/${DEVICE_SN}/cmd`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cmd: 'start_monitoring' })
            });
            document.getElementById('scanStatusBadge').textContent = 'Боевой режим';
            document.getElementById('scanStatusBadge').className = 'badge badge-monitoring';
        } catch (e) {
            console.error(e);
        }
    });

    // добавление нового стекла
    document.getElementById('btnAddPane').addEventListener('click', () => {
        panes.push({ id: nextPaneId++, zones: [] });
        renderPanes();
    });

    // сохранение и отправка зон
    document.getElementById('btnSaveZones').addEventListener('click', saveZones);

    // инициализация мыши на canvas
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseUp);

    // запуск периодического опроса сырого скана
    setInterval(pollRawScan, 2000);
    
    // первичная отрисовка
    drawRadar();
});

// получение угла мыши относительно центра (в градусах от 0 до 360, 0 = верх)
function getMouseAngle(e) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - centerX;
    const y = e.clientY - rect.top - centerY;
    // atan2 от x, -y для того чтобы 0 градусов был на севере, по часовой стрелке
    let angle = Math.atan2(x, -y) * 180 / Math.PI;
    if (angle < 0) angle += 360;
    return angle;
}

function handleMouseDown(e) {
    isDrawing = true;
    startDrawAngle = getMouseAngle(e);
    currentDrawAngle = startDrawAngle;
}

function handleMouseMove(e) {
    let rawAngle = getMouseAngle(e);
    
    // обновление панели диагностики (курсор)
    hoverAngle = Math.round(rawAngle);
    const hAngleEl = document.getElementById('diagHoverAngle');
    const hDistEl = document.getElementById('diagHoverDist');
    
    if (hAngleEl && hDistEl) {
        hAngleEl.textContent = `${hoverAngle}°`;
        const dist = currentScan[hoverAngle] || 0;
        if (dist > 0) {
            hDistEl.textContent = `${dist} мм (${(dist/10).toFixed(1)} см)`;
            hDistEl.style.color = "var(--accent-green)";
        } else {
            hDistEl.textContent = `-- мм (-- см)`;
            hDistEl.style.color = "var(--text-muted)";
        }
    }

    if (!isDrawing) {
        drawRadar();
        return;
    }
    currentDrawAngle = rawAngle;
    drawRadar();
}

function handleMouseUp(e) {
    if (!isDrawing) return;
    isDrawing = false;
    
    // добавление зоны при отпускании мыши
    let start = Math.round(startDrawAngle);
    let end = Math.round(currentDrawAngle);
    if (start > end && (start - end) > 180) {
        let temp = start; start = end; end = temp;
    }
    
    if (Math.abs(start - end) > 2) {
        if (panes.length === 0) panes.push({ id: nextPaneId++, zones: [] });
        let targetPane = panes[panes.length - 1];
        addZone(targetPane.id, start, end, 2500, 150);
    }
    drawRadar();
}

// периодический запрос 360 точек
async function pollRawScan() {
    try {
        const res = await fetch(`/api/devices/${DEVICE_SN}/scan`);
        if (res.ok) {
            const data = await res.json();
            if (data.scan && data.scan.length === 360) {
                currentScan = data.scan;
                drawRadar();
            }
        }
    } catch (e) {
        // игнорирование ошибок при отсутствии сети
    }
}

// добавление ui карточки зоны
function addZone(paneId, startA, endA, baseline, tol) {
    const pane = panes.find(p => p.id === paneId);
    if (!pane) return;
    pane.zones.push({
        internalId: nextZoneId++,
        zoneId: pane.zones.length + 1,
        start_a: startA,
        end_a: endA,
        baseline: baseline,
        tolerance: tol
    });
    renderPanes();
}

function deleteZone(paneId, internalId) {
    const pane = panes.find(p => p.id === paneId);
    if (pane) {
        pane.zones = pane.zones.filter(z => z.internalId !== internalId);
        // переиндексация
        pane.zones.forEach((z, i) => z.zoneId = i + 1);
        renderPanes();
        drawRadar();
    }
}

function deletePane(paneId) {
    panes = panes.filter(p => p.id !== paneId);
    renderPanes();
    drawRadar();
}

function updateZoneData(paneId, internalId, field, value) {
    const pane = panes.find(p => p.id === paneId);
    if (pane) {
        const z = pane.zones.find(z => z.internalId === internalId);
        if (z) {
            z[field] = parseInt(value) || 0;
            drawRadar();
        }
    }
}

// создание глобальных обработчиков для onclick в html
window.addZoneToPane = (paneId) => {
    addZone(paneId, 0, 90, 2000, 150);
};
window.deleteZone = deleteZone;
window.deletePane = deletePane;
window.updateZoneData = updateZoneData;

function renderPanes() {
    const container = document.getElementById('panesContainer');
    container.innerHTML = panes.map(p => `
        <div class="pane-card" style="background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong style="color: var(--text-main);">Стекло ${p.id}</strong>
                <div>
                    <button class="btn btn-secondary btn-sm" onclick="addZoneToPane(${p.id})">+ Зона</button>
                    <button class="btn btn-secondary btn-sm" onclick="deletePane(${p.id})" style="color: #f85149; margin-left: 8px;">Удалить</button>
                </div>
            </div>
            ${p.zones.map(z => `
                <div class="zone-card" style="background: rgba(0,0,0,0.2); border: 1px dashed var(--border-color); padding: 8px; border-radius: 6px; margin-top: 8px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 0.8rem; color: #8b949e;">Зона ${z.zoneId}</span>
                        <button class="btn btn-secondary btn-sm" onclick="deleteZone(${p.id}, ${z.internalId})" style="color: #f85149; padding: 2px 6px;">×</button>
                    </div>
                    <div class="zone-inputs">
                        <div>
                            <label style="font-size: 0.7rem; color: #8b949e;">Начало (°)</label>
                            <input type="number" value="${z.start_a}" onchange="updateZoneData(${p.id}, ${z.internalId}, 'start_a', this.value)">
                        </div>
                        <div>
                            <label style="font-size: 0.7rem; color: #8b949e;">Конец (°)</label>
                            <input type="number" value="${z.end_a}" onchange="updateZoneData(${p.id}, ${z.internalId}, 'end_a', this.value)">
                        </div>
                        <div>
                            <label style="font-size: 0.7rem; color: #8b949e;">Дистанция</label>
                            <input type="number" value="${z.baseline}" onchange="updateZoneData(${p.id}, ${z.internalId}, 'baseline', this.value)">
                        </div>
                        <div>
                            <label style="font-size: 0.7rem; color: #8b949e;">Погрешность</label>
                            <input type="number" value="${z.tolerance}" onchange="updateZoneData(${p.id}, ${z.internalId}, 'tolerance', this.value)">
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `).join('');
}

// отправка сформированного массива зон на сервер
async function saveZones() {
    const payload = { panes: [] };
    panes.forEach(p => {
        if (p.zones.length > 0) {
            payload.panes.push({
                id: p.id,
                zones: p.zones.map(z => ({
                    id: z.zoneId,
                    start_a: z.start_a,
                    end_a: z.end_a,
                    baseline: z.baseline,
                    tolerance: z.tolerance
                }))
            });
        }
    });

    try {
        const res = await fetch(`/api/devices/${DEVICE_SN}/calibrate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
            alert('Зоны успешно сохранены и отправлены на устройство!');
        } else {
            alert('Ошибка: ' + result.error);
        }
    } catch (e) {
        alert('Ошибка сети: ' + e.message);
    }
}

// главная функция отрисовки радара
function drawRadar() {
    ctx.clearRect(0, 0, width, height);

    // сетка кругов
    ctx.strokeStyle = 'rgba(240, 246, 252, 0.1)';
    ctx.lineWidth = 1;
    for (let r = 1000; r <= maxDistance; r += 1000) {
        ctx.beginPath();
        ctx.arc(centerX, centerY, r * scale, 0, 2 * Math.PI);
        ctx.stroke();
    }

    // оси
    ctx.beginPath();
    ctx.moveTo(centerX, 0); ctx.lineTo(centerX, height);
    ctx.moveTo(0, centerY); ctx.lineTo(width, centerY);
    ctx.stroke();

    // отрисовка сконфигурированных зон
    panes.forEach(p => {
        p.zones.forEach(z => {
            const startRad = (z.start_a - 90) * Math.PI / 180;
            const endRad = (z.end_a - 90) * Math.PI / 180;
            
            ctx.beginPath();
            ctx.arc(centerX, centerY, z.baseline * scale, startRad, endRad);
            ctx.strokeStyle = '#3fb950';
            ctx.lineWidth = 3;
            ctx.stroke();

            // погрешность (полупрозрачная заливка)
            ctx.beginPath();
            ctx.arc(centerX, centerY, (z.baseline + z.tolerance) * scale, startRad, endRad);
            ctx.arc(centerX, centerY, (z.baseline - z.tolerance) * scale, endRad, startRad, true);
            ctx.fillStyle = 'rgba(63, 185, 80, 0.15)';
            ctx.fill();
        });
    });

    // отрисовка сырого скана 360 точек
    ctx.fillStyle = '#58a6ff';
    for (let i = 0; i < 360; i++) {
        const dist = currentScan[i];
        if (dist > 0 && dist <= maxDistance) {
            const rad = (i - 90) * Math.PI / 180;
            const px = centerX + Math.cos(rad) * (dist * scale);
            const py = centerY + Math.sin(rad) * (dist * scale);
            
            // выделение точки под курсором красным цветом и размером побольше
            if (i === hoverAngle) {
                ctx.fillStyle = '#ff7b72';
                ctx.beginPath();
                ctx.arc(px, py, 4, 0, 2 * Math.PI);
                ctx.fill();
                
                // линия-лазер от центра
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(px, py);
                ctx.strokeStyle = 'rgba(255, 123, 114, 0.5)';
                ctx.lineWidth = 1;
                ctx.stroke();
                
                ctx.fillStyle = '#58a6ff'; // возврат цвета
            } else {
                ctx.beginPath();
                ctx.arc(px, py, 2, 0, 2 * Math.PI);
                ctx.fill();
            }
        }
    }

    // отрисовка текущего выделения
    if (isDrawing) {
        const sRad = (startDrawAngle - 90) * Math.PI / 180;
        const cRad = (currentDrawAngle - 90) * Math.PI / 180;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, 300, sRad, cRad, false);
        ctx.lineTo(centerX, centerY);
        ctx.fillStyle = 'rgba(88, 166, 255, 0.3)';
        ctx.fill();
    }
}

// ручной запрос угла из панели диагностики
window.queryManualAngle = () => {
    const input = document.getElementById('diagManualAngle');
    const result = document.getElementById('diagManualResult');
    if (!input || !result) return;
    
    let angle = parseInt(input.value);
    if (isNaN(angle) || angle < 0 || angle > 359) {
        result.textContent = "Некорректный угол!";
        result.style.color = "var(--text-red)";
        return;
    }
    
    const dist = currentScan[angle] || 0;
    if (dist > 0) {
        result.textContent = `${dist} мм (${(dist/10).toFixed(1)} см)`;
        result.style.color = "var(--accent-green)";
    } else {
        result.textContent = "Нет эха (0 мм)";
        result.style.color = "var(--text-yellow)";
    }
    
    // форсируем подсветку этого луча на канвасе
    hoverAngle = angle;
    drawRadar();
};
