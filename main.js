window.onload = function () {
    const apiUrl = "https://api.thingspeak.com/channels/2770121/feeds.json";

    // Inicializa pestañas
    openTab('actual');

    // Crea gráficos
    const charts = createZoomableCharts();

    // Cargar datos iniciales
    fetchLatestData(apiUrl);

    // Configura eventos
    document.querySelector('button[onclick="openTab(\'grafico\')"]').addEventListener('click', () => {
        fetchDataAndPlotAll(apiUrl, charts);
    });
    document.getElementById('fetchForecastBtn').addEventListener('click', async () => {
        const loading = document.getElementById("loading");
        try {
            loading.style.display = "block";
            await cargarPrevision();
        } catch (error) {
            console.error('Error al cargar la previsión:', error);
            alert('No se pudieron cargar los datos de previsión.');
        } finally {
            loading.style.display = "none";
        }
    });

};







// URL de la API
const url = 'https://www.meteosource.com/api/v1/free/point?lat=41.0620N&lon=6.2853W&sections=all&timezone=auto&language=en&units=metric&key=3anr1qzk4s6wgfv0u6k8gsjawl8ilqhyzeya64fx'; // Sustituye con tu URL real

// Función para hacer el fetch y obtener los datos
async function obtenerDatosPrevision() {
    try {
        const response = await fetch(url);
        const datos = await response.json();
        return datos;
    } catch (error) {
        console.error('Error al obtener los datos de la API:', error);
        return null;
    }
}

const weatherPhraseTranslations = {
    "Fog": "Niebla",
    "Cloudy": "Nublado",
    "Partly": "Parcialmente",
    "Overcast": "Mayormente nublado",
    "Mostly": "Mayormente",
    "Sunny": "Soleado",
    "Fewer clouds": "Menos nubes",
    "More clouds": "Más nubes",
    "cloud": "nube",
    "clear": "despejado",
    "Temperature falling to": "La temperatura bajará a",
    "Temperature rising to": "La temperatura subirá a",
    "Temperature": "Temperatura",
    "°C": "°C",
    "Wind from": "Viento del",
    "km/h": "km/h",
    "Rain": "Lluvia",
    "Snow": "Nieve",
    "None": "Ninguna",
    "Precipitation": "Precipitación",
    "Cloud cover": "Cobertura de nubes"
};

function translateSummary(summary) {
    let translated = summary;
    for (const [englishPhrase, spanishPhrase] of Object.entries(weatherPhraseTranslations)) {
        const regex = new RegExp(englishPhrase, "gi");
        translated = translated.replace(regex, spanishPhrase);
    }
    return translated;
}

function extraerDatosPrevision(datos) {
    const datosTemperatura = [];
    const datosViento = [];
    const datosLluvia = [];

    datos.hourly.data.forEach(hour => {
        datosTemperatura.push({
            x: new Date(hour.date * 1000),
            y: hour.temperature
        });

        datosViento.push({
            x: new Date(hour.date * 1000),
            y: hour.wind.speed
        });

        datosLluvia.push({
            x: new Date(hour.date * 1000),
            y: hour.precipitation.total || 0
        });
    });

    return {
        temperatura: datosTemperatura,
        viento: datosViento,
        lluvia: datosLluvia
    };
}

async function cargarPrevision() {
    const datos = await obtenerDatosPrevision();
    if (datos) {
        mostrarActual(datos.current);
        mostrarHoraria(datos.hourly.data);
        mostrarDiaria(datos.daily.data);
    } else {
        console.error('No se pudieron cargar los datos de previsión.');
    }
}

function mostrarActual(datos) {
    const tbody = document.getElementById('tablaActual').querySelector('tbody');
    tbody.innerHTML = '';
    const fila = document.createElement('tr');
    fila.innerHTML = `
        <td>${translateSummary(datos.summary)}</td>
        <td>${datos.temperature} °C</td>
        <td>${datos.wind.speed} km/h, ${datos.wind.dir}</td>
        <td>${datos.precipitation.total} mm</td>
        <td>${datos.cloud_cover}%</td>
    `;
    tbody.appendChild(fila);
}

function mostrarHoraria(datos) {
    const tbody = document.getElementById('tablaHoraria').querySelector('tbody');
    tbody.innerHTML = '';
    datos.forEach(hour => {
        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td>${new Date(hour.date).toLocaleString()}</td>
            <td>${translateSummary(hour.summary)}</td>
            <td>${hour.temperature} °C</td>
            <td>${hour.wind.speed} km/h, ${hour.wind.dir}</td>
            <td>${hour.precipitation.total || 0} mm</td>
            <td>${hour.cloud_cover}%</td>
        `;
        tbody.appendChild(fila);
    });
}

function mostrarDiaria(datos) {
    const tbody = document.getElementById('tablaDiaria').querySelector('tbody');
    tbody.innerHTML = '';
    datos.forEach(day => {
        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td>${day.day}</td>
            <td>${translateSummary(day.summary)}</td>
            <td>${day.all_day.temperature_min} °C</td>
            <td>${day.all_day.temperature_max} °C</td>
            <td>${day.all_day.wind.speed} km/h, ${day.all_day.wind.dir}</td>
            <td>${day.all_day.precipitation.total || 0} mm</td>
            <td>${day.all_day.cloud_cover}%</td>
        `;
        tbody.appendChild(fila);
    });
}

