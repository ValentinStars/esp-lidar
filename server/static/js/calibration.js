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

// список заданных зон
let zones = [];
let nextZoneId = 1;

// флаги рисования мышью
let isDrawing = false;
let startDrawAngle = 0;
let currentDrawAngle = 0;

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

    // добавление пустой зоны
    document.getElementById('btnAddZone').addEventListener('click', () => {
        addZone(Math.floor(zones.length / 4) + 1, nextZoneId, 0, 90, 2000, 150);
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
    if (!isDrawing) return;
    currentDrawAngle = getMouseAngle(e);
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
        addZone(Math.floor(zones.length / 4) + 1, nextZoneId, start, end, 2500, 150);
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
function addZone(paneId, zId, startA, endA, baseline, tol) {
    const zone = {
        internalId: zId,
        paneId: paneId,
        zoneId: zId,
        start_a: startA,
        end_a: endA,
        baseline: baseline,
        tolerance: tol
    };
    zones.push(zone);
    nextZoneId++;
    renderZoneCards();
}

function deleteZone(id) {
    zones = zones.filter(z => z.internalId !== id);
    renderZoneCards();
    drawRadar();
}

function updateZoneData(id, field, value) {
    const z = zones.find(z => z.internalId === id);
    if (z) {
        z[field] = parseInt(value) || 0;
        drawRadar();
    }
}

function renderZoneCards() {
    const container = document.getElementById('zonesContainer');
    container.innerHTML = zones.map(z => `
        <div class="zone-card">
            <div style="display: flex; justify-content: space-between;">
                <strong>Стекло ${z.paneId} - Зона ${z.zoneId}</strong>
                <button class="btn btn-secondary btn-sm" onclick="deleteZone(${z.internalId})" style="color: #f85149; padding: 2px 6px;">×</button>
            </div>
            <div class="zone-inputs">
                <div>
                    <label style="font-size: 0.7rem; color: #8b949e;">Начало (°)</label>
                    <input type="number" value="${z.start_a}" onchange="updateZoneData(${z.internalId}, 'start_a', this.value)">
                </div>
                <div>
                    <label style="font-size: 0.7rem; color: #8b949e;">Конец (°)</label>
                    <input type="number" value="${z.end_a}" onchange="updateZoneData(${z.internalId}, 'end_a', this.value)">
                </div>
                <div>
                    <label style="font-size: 0.7rem; color: #8b949e;">Дистанция (мм)</label>
                    <input type="number" value="${z.baseline}" onchange="updateZoneData(${z.internalId}, 'baseline', this.value)">
                </div>
                <div>
                    <label style="font-size: 0.7rem; color: #8b949e;">Погрешность (мм)</label>
                    <input type="number" value="${z.tolerance}" onchange="updateZoneData(${z.internalId}, 'tolerance', this.value)">
                </div>
            </div>
        </div>
    `).join('');
}

// отправка сформированного массива зон на сервер
async function saveZones() {
    // группировка по стеклам
    const panesMap = {};
    zones.forEach(z => {
        if (!panesMap[z.paneId]) {
            panesMap[z.paneId] = [];
        }
        panesMap[z.paneId].push({
            id: z.zoneId,
            start_a: z.start_a,
            end_a: z.end_a,
            baseline: z.baseline,
            tolerance: z.tolerance
        });
    });

    const payload = { panes: [] };
    for (const [pId, zArr] of Object.entries(panesMap)) {
        payload.panes.push({
            id: parseInt(pId),
            zones: zArr
        });
    }

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
    zones.forEach(z => {
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

    // отрисовка сырого скана 360 точек
    ctx.fillStyle = '#58a6ff';
    for (let i = 0; i < 360; i++) {
        const dist = currentScan[i];
        if (dist > 0 && dist <= maxDistance) {
            const rad = (i - 90) * Math.PI / 180;
            const px = centerX + Math.cos(rad) * (dist * scale);
            const py = centerY + Math.sin(rad) * (dist * scale);
            
            ctx.beginPath();
            ctx.arc(px, py, 2, 0, 2 * Math.PI);
            ctx.fill();
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
