// клиентский javascript для динамического обновления данных в реальном времени

let selectedDeviceSn = null;

// запуск периодического обновления при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    fetchStats();
    fetchDevicesData();
    fetchAlertsData();

    // периодический опрос сервера каждые 2 секунды
    setInterval(() => {
        fetchStats();
        fetchDevicesData();
        fetchAlertsData();
    }, 2000);

    // обновление часов в шапке
    setInterval(updateClock, 1000);
    updateClock();
});

// обновление текущего времени
function updateClock() {
    const now = new Date();
    const clockEl = document.getElementById('liveClock');
    if (clockEl) {
        clockEl.textContent = now.toLocaleTimeString('ru-RU');
    }
}

// получение общей статистики
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        document.getElementById('metricTotalDevices').textContent = data.total_devices || 0;
        document.getElementById('metricOnlineDevices').textContent = data.online_devices || 0;
        document.getElementById('metricOfflineDevices').textContent = data.offline_devices || 0;
        document.getElementById('metricTotalAlerts').textContent = data.total_alerts || 0;

        // статус mqtt брокера
        const mqttBadge = document.getElementById('mqttStatusBadge');
        if (mqttBadge) {
            if (data.mqtt_connected) {
                mqttBadge.className = 'status-pill online';
                mqttBadge.querySelector('.text').textContent = 'MQTT: Connected';
            } else {
                mqttBadge.className = 'status-pill';
                mqttBadge.querySelector('.text').textContent = 'MQTT: Standby';
            }
        }
    } catch (e) {
        console.error('Ошибка получения статистики:', e);
    }
}

// получение и отрисовка списка устройств
async function fetchDevicesData() {
    try {
        const res = await fetch('/api/devices');
        const devices = await res.json();

        const tableBody = document.getElementById('devicesTableBody');
        const countBadge = document.getElementById('devicesCountBadge');

        countBadge.textContent = devices.length;

        if (devices.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="12" class="text-center py-4 text-muted">Ожидание первого Auto-Discovery сигнала от узлов ESP32...</td></tr>';
            return;
        }

        tableBody.innerHTML = devices.map(d => {
            const isOnline = d.is_online;
            const statusBadge = isOnline 
                ? `<span class="badge badge-online">ONLINE</span>` 
                : `<span class="badge badge-offline">OFFLINE</span>`;

            let modeBadge = `<span class="badge badge-unconfigured">${d.status}</span>`;
            if (d.status === 'monitoring') {
                modeBadge = `<span class="badge badge-monitoring">МОНИТОРИНГ</span>`;
            }

            return `
                <tr>
                    <td>${statusBadge}</td>
                    <td class="mono font-bold">${d.sn}</td>
                    <td class="mono text-blue">${d.ip}</td>
                    <td class="mono text-muted">${d.mac}</td>
                    <td>${modeBadge}</td>
                    <td class="mono">${d.uptime || 0} с</td>
                    <td class="mono">${Math.round((d.free_heap || 0) / 1024)} КБ</td>
                    <td class="mono">${d.valid_packets || 0}</td>
                    <td class="mono ${d.crc_errors > 0 ? 'text-yellow' : ''}">${d.crc_errors || 0}</td>
                    <td class="mono ${d.alerts_count > 0 ? 'text-red font-bold' : ''}">${d.alerts_count || 0}</td>
                    <td class="text-muted">${d.last_seen_sec_ago} с назад</td>
                    <td>
                        <a href="/device/${d.sn}" class="btn btn-primary btn-sm" style="text-decoration: none; padding: 4px 8px; font-size: 0.8rem; margin-right: 4px;">Диагностика</a>
                        <button class="btn btn-secondary btn-sm" onclick="openCmdModal('${d.sn}')">Управление ⚙️</button>
                    </td>
                </tr>
            `;
        }).join('');

    } catch (e) {
        console.error('Ошибка получения списка устройств:', e);
    }
}

// получение и отрисовка ленты алертов
async function fetchAlertsData() {
    try {
        const res = await fetch('/api/alerts?limit=20');
        const alerts = await res.json();

        const tableBody = document.getElementById('alertsTableBody');
        const countBadge = document.getElementById('alertsCountBadge');

        countBadge.textContent = alerts.length;

        if (alerts.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-muted">Алертов не зафиксировано. Все стекла в норме.</td></tr>';
            return;
        }

        tableBody.innerHTML = alerts.map(a => {
            const timeStr = new Date(a.timestamp * 1000).toLocaleTimeString('ru-RU');
            const deltaSign = a.delta_mm > 0 ? `+${a.delta_mm}` : `${a.delta_mm}`;
            let typeBadge = '';
            if (a.alert_type === 'destruction') {
                typeBadge = `<span class="badge badge-offline text-red">РАЗРУШЕНИЕ (+Δ)</span>`;
            } else if (a.alert_type === 'proximity') {
                typeBadge = `<span class="badge badge-unconfigured">ПРИБЛИЖЕНИЕ (-Δ)</span>`;
            } else if (a.alert_type === 'restored') {
                typeBadge = `<span class="badge badge-monitoring" style="color: #3fb950; border-color: #3fb950;">ВОССТАНОВЛЕНО</span>`;
            } else {
                typeBadge = `<span class="badge badge-unconfigured">${a.alert_type}</span>`;
            }

            return `
                <tr>
                    <td class="mono">#${a.id}</td>
                    <td class="mono font-bold">${a.sn}</td>
                    <td class="mono">${timeStr}</td>
                    <td class="mono">Стекло ${a.pane_id}</td>
                    <td class="mono">Зона ${a.zone_id}</td>
                    <td>${typeBadge}</td>
                    <td class="mono">${a.distance_mm} мм</td>
                    <td class="mono">${a.calib_dist_mm} мм</td>
                    <td class="mono font-bold ${a.delta_mm > 0 ? 'text-red' : 'text-yellow'}">${deltaSign} мм</td>
                </tr>
            `;
        }).join('');

    } catch (e) {
        console.error('Ошибка получения алертов:', e);
    }
}

// открытие модального окна управления
function openCmdModal(sn) {
    selectedDeviceSn = sn;
    document.getElementById('modalDeviceSn').textContent = `Команда для ${sn}`;
    document.getElementById('cmdModal').style.display = 'flex';
}

// закрытие модального окна
function closeCmdModal() {
    document.getElementById('cmdModal').style.display = 'none';
    selectedDeviceSn = null;
}

// отправка выбранной команды
async function sendSelectedCommand() {
    if (!selectedDeviceSn) return;
    const cmd = document.getElementById('cmdSelect').value;

    try {
        const res = await fetch(`/api/devices/${selectedDeviceSn}/cmd`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cmd: cmd })
        });
        const result = await res.json();
        alert(`Команда "${cmd}" успешно отправлена на узел ${selectedDeviceSn}`);
        closeCmdModal();
    } catch (e) {
        alert(`Ошибка отправки команды: ${e}`);
    }
}
