const POLL_INTERVAL = 5000;

// id: ID del HTML, unit: sufijo, transform: función opcional para convertir datos
const SENSOR_CONFIG = {
    temperatura: { id: 'temperatura', unit: '°C' },
    humedad: { id: 'humedad', unit: '%' },
    viento_medio: { id: 'viento_medio', unit: ' km/h', transform: (v) => (v * 3.6).toFixed(1) },
    rafaga: { id: 'rafaga', unit: ' km/h', transform: (v) => (v * 3.6).toFixed(1) },
    rain_24h: { id: 'rain_24h', unit: ' mm' },
    rain_accumulated: { id: 'rain_accumulated', unit: ' mm' }
};

class WeatherDashboard {
    constructor() {
        this.cacheDOM();
        this.init();
    }

    cacheDOM() {
        // Elementos estructurales fijos
        this.dom = {
            lastUpdate: document.getElementById('last-update'),
            wifi: document.getElementById('wifi-signal'),
            uptime: document.getElementById('uptime'),
            windArrow: document.getElementById('wind-arrow'),
            windText: document.getElementById('direccion_text'),
            tempIcon: document.getElementById('temp-icon'),
            fields: {}
        };

        // Generación dinámica del caché basada en la config (DRY)
        // Para no hacer getElementById() para cada sensor
        for (const key in SENSOR_CONFIG) {
            const config = SENSOR_CONFIG[key];
            const el = document.getElementById(config.id);
            if (el) this.dom.fields[key] = el;
        }
    }

    init() {
        this.fetchData();
    }

    async fetchData() {
        try {
            const res = await fetch("/api/recientes?limit=1");
            if (res.ok) {
                const data = await res.json();
                const record = Array.isArray(data) ? data[0] : data;
                if (record) {
                    this.updateUI(record);
                    this.clearError();
                }
            } else {
                console.warn(`API Error: ${res.status}`);
                this.showError();
            }
        } catch (e) {
            console.error("Connection Error:", e);
            this.showError();
        } finally {
            setTimeout(() => this.fetchData(), POLL_INTERVAL);
        }
    }

    updateUI(data) {
        this.updateSensorFields(data);

        this.renderTimestamp(data.timestamp);
        this.renderSystemHealth(data);
        this.updateWindDirection(data.direccion);
        this.updateTempIcon(data.temperatura);
    }

    updateSensorFields(data) {
        for (const [key, config] of Object.entries(SENSOR_CONFIG)) {
            const element = this.dom.fields[key];
            let value = data[key];

            if (!element) continue;

            if (value === null || value === undefined) {
                element.textContent = "--" + config.unit;
                continue;
            }

            // Aplicamos transformación si existe (ej. m/s -> km/h)
            if (config.transform) {
                value = config.transform(value);
            }

            element.textContent = value + config.unit;
        }
    }

    renderTimestamp(isoDate) {
        if (!this.dom.lastUpdate) return;

        const dateStr = isoDate.endsWith('Z') ? isoDate : isoDate + 'Z';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);

        const timeText = this.getRelativeTime(diff, date, now);

        // Lógica de estado de conexión
        const isDisconnected = diff > (3600); // 1 hora
        this.dom.lastUpdate.innerHTML = timeText;
    }

    getRelativeTime(diff, date, now) {
        if (diff < 60) return "Hace unos segundos";
        if (diff < 3600) return `Hace ${Math.floor(diff / 60)} minuto${Math.floor(diff / 60) > 1 ? 's' : ''}`;

        const timeStr = date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        if (date.toDateString() === now.toDateString()) return `Hoy, ${timeStr}`;

        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) return `Ayer, ${timeStr}`;

        return date.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    renderSystemHealth(data) {
        // RSSI
        const rssi = this.dom.wifi;
        if (rssi) {
            const val = data.rssi;
            if (val && val !== 0) {
                rssi.textContent = val;
                rssi.style.color = val > -60 ? "#00d4aa" : (val > -75 ? "#ffdd00" : "#ff4444");
            } else {
                rssi.textContent = "--";
                rssi.style.color = "";
            }
        }

        // Uptime
        const up = this.dom.uptime;
        if (up && data.uptime != null) {
            const d = Math.floor(data.uptime / 86400);
            const h = Math.floor((data.uptime % 86400) / 3600);
            const m = Math.floor((data.uptime % 3600) / 60);
            // Filtrar partes vacías (ej: no mostrar "0d")
            up.textContent = [d > 0 ? `${d}d` : null, (h > 0 || d > 0) ? `${h}h` : null, `${m}m`].filter(Boolean).join(' ');
        }
    }

    updateWindDirection(deg) {
        if (deg == null) return;
        const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
        const idx = Math.round((deg % 360) / 22.5);

        if (this.dom.windText) this.dom.windText.textContent = dirs[idx % 16];
        if (this.dom.windArrow) this.dom.windArrow.style.transform = `rotate(${deg}deg)`;
    }

    updateTempIcon(t) {
        const icon = this.dom.tempIcon?.querySelector('i');
        if (!icon) return;

        icon.classList.remove('temp-hot', 'temp-mild', 'temp-cold');
        icon.classList.add(t > 25 ? 'temp-hot' : (t < 10 ? 'temp-cold' : 'temp-mild'));
    }

    showError() {
        if (this.dom.lastUpdate) {
            this.dom.lastUpdate.textContent = "Error de conexión...";
            this.dom.lastUpdate.style.color = "#ff4444";
        }
    }

    clearError() {
        if (this.dom.lastUpdate?.textContent.includes("Error")) {
            this.dom.lastUpdate.style.color = "";
        }
    }
}

document.addEventListener('DOMContentLoaded', () => new WeatherDashboard());
