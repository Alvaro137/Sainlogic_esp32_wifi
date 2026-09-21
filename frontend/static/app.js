/**
 * Dashboard Meteorológico — El tiempo en Espadaña
 * Comunicación periódica y renderizado reactivo del sensor Sainlogic.
 */

const POLL_INTERVAL_MS = 5000;

// Configuración de sensores: mapeo de claves de API a elementos del DOM y unidades
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
        this.dom = {};
        this.cacheDOM();
        this.init();
    }

    cacheDOM() {
        this.dom = {
            lastUpdate: document.getElementById('last-update'),
            wifi: document.getElementById('wifi-signal'),
            uptime: document.getElementById('uptime'),
            windArrow: document.getElementById('wind-arrow'),
            windText: document.getElementById('direccion_text'),
            tempIcon: document.getElementById('temp-icon'),
            fields: {}
        };

        // Cache dinámico de campos
        for (const [key, config] of Object.entries(SENSOR_CONFIG)) {
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
            setTimeout(() => this.fetchData(), POLL_INTERVAL_MS);
        }
    }

    updateUI(data) {
        this.updateSensorFields(data);
        this.renderTimestamp(data.timestamp);
        this.renderSystemHealth(data);
        this.updateWindDirection(data.direccion);
        this.updateTemperatureColor(data.temperatura);
    }

    updateSensorFields(data) {
        for (const [key, config] of Object.entries(SENSOR_CONFIG)) {
            const element = this.dom.fields[key];
            if (!element) continue;

            let value = data[key];

            if (value === null || value === undefined) {
                element.textContent = `--${config.unit}`;
                continue;
            }

            if (config.transform && typeof value === 'number') {
                value = config.transform(value);
            }

            element.textContent = `${value}${config.unit}`;
        }
    }

    renderTimestamp(isoDate) {
        if (!this.dom.lastUpdate || !isoDate) return;

        let str = String(isoDate).trim();

        // Si termina en +00:00Z (formato malformado previo), arreglarlo
        if (str.includes('+00:00')) {
            str = str.replace('+00:00Z', 'Z').replace('+00:00', 'Z');
        } else if (!str.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(str)) {
            // Timestamp ingenuo UTC de la DB
            str += 'Z';
        }

        let date = new Date(str);
        if (isNaN(date.getTime())) {
            date = new Date(str.replace(' ', 'T'));
        }

        if (isNaN(date.getTime())) {
            this.dom.lastUpdate.textContent = "--";
            return;
        }

        const now = new Date();
        const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

        this.dom.lastUpdate.textContent = this.getRelativeTime(diffSeconds, date, now);
    }

    getRelativeTime(diff, date, now) {
        if (isNaN(diff) || diff < 60) return "Hace unos segundos";
        if (diff < 3600) {
            const mins = Math.floor(diff / 60);
            return `Hace ${mins} minuto${mins > 1 ? 's' : ''}`;
        }

        const timeStr = date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        if (date.toDateString() === now.toDateString()) {
            return `Hoy, ${timeStr}`;
        }

        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) {
            return `Ayer, ${timeStr}`;
        }

        return date.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    renderSystemHealth(data) {
        // RSSI WiFi
        const rssi = this.dom.wifi;
        if (rssi) {
            const val = data.rssi;
            if (val && val !== 0) {
                rssi.textContent = val;
                rssi.style.color = val > -60 ? "#16a34a" : (val > -75 ? "#d97706" : "#dc2626");
            } else {
                rssi.textContent = "--";
                rssi.style.color = "";
            }
        }

        // Tiempo de funcionamiento (Uptime)
        const up = this.dom.uptime;
        if (up && data.uptime != null) {
            const d = Math.floor(data.uptime / 86400);
            const h = Math.floor((data.uptime % 86400) / 3600);
            const m = Math.floor((data.uptime % 3600) / 60);
            const parts = [];
            if (d > 0) parts.push(`${d}d`);
            if (h > 0 || d > 0) parts.push(`${h}h`);
            parts.push(`${m}m`);
            up.textContent = parts.join(' ');
        }
    }

    updateWindDirection(deg) {
        if (deg == null) return;
        const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
        const idx = Math.round((deg % 360) / 22.5);

        if (this.dom.windText) {
            this.dom.windText.textContent = dirs[idx % 16];
        }
        if (this.dom.windArrow) {
            this.dom.windArrow.style.transform = `rotate(${deg}deg)`;
        }
    }

    updateTemperatureColor(t) {
        if (t == null) return;
        const colorClass = t > 25 ? 'temp-hot' : (t < 10 ? 'temp-cold' : 'temp-mild');

        const icon = this.dom.tempIcon?.querySelector('i');
        if (icon) {
            icon.classList.remove('temp-hot', 'temp-mild', 'temp-cold');
            icon.classList.add(colorClass);
        }

        const valEl = this.dom.fields.temperatura;
        if (valEl) {
            valEl.classList.remove('temp-hot', 'temp-mild', 'temp-cold');
            valEl.classList.add(colorClass);
        }
    }

    showError() {
        if (this.dom.lastUpdate) {
            this.dom.lastUpdate.textContent = "Error de conexión con la estación...";
            this.dom.lastUpdate.style.color = "#dc2626";
        }
    }

    clearError() {
        if (this.dom.lastUpdate?.textContent.includes("Error")) {
            this.dom.lastUpdate.style.color = "";
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new WeatherDashboard();
});
