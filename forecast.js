// forecast.js

// URL de la API
export const url = 'https://www.meteosource.com/api/v1/free/point?lat=41.0620N&lon=6.2853W&sections=all&timezone=auto&language=en&units=metric&key=3anr1qzk4s6wgfv0u6k8gsjawl8ilqhyzeya64fx';

// Traducciones de frases meteorológicas
export const weatherPhraseTranslations = {
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
    "changing to": "cambiando a",
    "by evening": "hacia la tarde",
    "Temperature falling to": "La temperatura bajará a",
    "Rain": "Lluvia",
    "Snow": "Nieve",
    "Wind from": "Viento del",
    "km/h": "km/h",
    "°C": "°C"
};

// Función para traducir el resumen
export function translateSummary(summary) {
    let translated = summary;

    for (const [englishPhrase, spanishPhrase] of Object.entries(weatherPhraseTranslations)) {
        const regex = new RegExp(englishPhrase, "gi");
        translated = translated.replace(regex, spanishPhrase);
    }

    translated = translated.replace(/(\d+)\s*\/\s*(\d+)\s*°C/gi, "$1 °C / $2 °C");
    return translated;
}

// Función para obtener datos de la API
export async function obtenerDatosPrevision() {
    try {
        const response = await fetch(url);
        const datos = await response.json();
        return datos;
    } catch (error) {
        console.error('Error al obtener los datos de la API:', error);
        throw error;
    }
}

// Función para mostrar datos actuales
export function mostrarActual(datos) {
    const tbody = document.getElementById('tablaActual').querySelector('tbody');
    tbody.innerHTML = '';
    const fila = document.createElement('tr');
    fila.innerHTML = `
        <td>${translateSummary(datos.summary)}</td>
        <td>${datos.temperature}</td>
        <td>${datos.wind.speed} km/h, ${datos.wind.dir}</td>
        <td>${datos.precipitation.total}</td>
        <td>${datos.cloud_cover}</td>
    `;
    tbody.appendChild(fila);
}

// Funciones similares para mostrarHoraria y mostrarDiaria
export function mostrarHoraria(datos) {
    const tbody = document.getElementById('tablaHoraria').querySelector('tbody');
    tbody.innerHTML = '';
    datos.forEach(hour => {
        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td>${new Date(hour.date).toLocaleString()}</td>
            <td>${translateSummary(hour.summary)}</td>
            <td>${hour.temperature}</td>
            <td>${hour.wind.speed} km/h, ${hour.wind.dir}</td>
            <td>${hour.precipitation.total}</td>
            <td>${hour.cloud_cover.total}</td>
        `;
        tbody.appendChild(fila);
    });
}

export function mostrarDiaria(datos) {
    const tbody = document.getElementById('tablaDiaria').querySelector('tbody');
    tbody.innerHTML = '';
    datos.forEach(day => {
        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td>${day.day}</td>
            <td>${translateSummary(day.summary)}</td>
            <td>${day.all_day.temperature_min}</td>
            <td>${day.all_day.temperature_max}</td>
            <td>${day.all_day.wind.speed} km/h, ${day.all_day.wind.dir}</td>
            <td>${day.all_day.precipitation.total}</td>
            <td>${day.all_day.cloud_cover.total}</td>
        `;
        tbody.appendChild(fila);
    });
}
