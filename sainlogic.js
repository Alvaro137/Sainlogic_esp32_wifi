window.onload = function () {
    openTab('actual');

    // Crear gráficos
    const charts = createZoomableCharts();

    // Cargar datos al seleccionar la pestaña de gráficos
    document.querySelector('button[onclick="openTab(\'grafico\')"]').addEventListener('click', () => {
        fetchDataAndPlotAll(charts);
    });

    // Mostrar datos actuales
    fetchLatestData();
}

/**
 * Cambia entre las pestañas
 * @param {string} tabName - El nombre de la pestaña a mostrar
 */
function openTab(tabName) {
    const tabContents = document.querySelectorAll(".tabcontent");
    tabContents.forEach(content => content.style.display = "none");

    const tabLinks = document.querySelectorAll(".tablink");
    tabLinks.forEach(link => link.classList.remove("active"));

    const activeTab = document.getElementById(tabName);
    if (activeTab) activeTab.style.display = "block";

    const button = document.querySelector(`button[onclick="openTab('${tabName}')"]`);
    if (button) button.classList.add("active");
}

/**
 * Crea gráficos zoomeables para todos los campos.
 * @returns {Object} Un objeto con gráficos por campo.
 */
function createZoomableCharts() {
    return {
        temperatura: new CanvasJS.Chart("chartContainerTemperatura", {
            theme: "dark1",
            animationEnabled: true,
            zoomEnabled: true,
            title: { text: "Temperatura" },
            axisX: { title: "Fecha y Hora", valueFormatString: "DD-MM HH:mm" },
            axisY: { title: "°C" },
            data: [{ type: "line", color: "#ff2121", lineThickness: 3, markerSize: 5, dataPoints: [] }]
        }),
        lluvia: new CanvasJS.Chart("chartContainerLluvia", {
            theme: "dark1",
            animationEnabled: true,
            zoomEnabled: true,
            title: { text: "Lluvia" },
            axisX: { title: "Fecha y Hora", valueFormatString: "DD-MM HH:mm" },
            axisY: { title: "mm" },
            data: [{ type: "area", color: "#2196f3", fillOpacity: 0.8, lineThickness: 3, markerSize: 5, dataPoints: [] }]
        }),
        vientoMedio: new CanvasJS.Chart("chartContainerVientoMedio", {
            theme: "dark1",
            animationEnabled: true,
            zoomEnabled: true,
            title: { text: "Viento Medio" },
            axisX: { title: "Fecha y Hora", valueFormatString: "DD-MM HH:mm" },
            axisY: { title: "m/s" },
            data: [{ type: "line", color: "#fcbb08", lineThickness: 3, markerSize: 5, dataPoints: [] }]
        }),
        rafaga: new CanvasJS.Chart("chartContainerRafaga", {
            theme: "dark1",
            animationEnabled: true,
            zoomEnabled: true,
            title: { text: "Ráfaga" },
            axisX: { title: "Fecha y Hora", valueFormatString: "DD-MM HH:mm" },
            axisY: { title: "m/s" },
            data: [{ type: "line", color: "#fcbb08", lineThickness: 3, markerSize: 5, dataPoints: [] }]
        }),
        humedad: new CanvasJS.Chart("chartContainerHumedad", {
            theme: "dark1",
            animationEnabled: true,
            zoomEnabled: true,
            title: { text: "Humedad" },
            axisX: { title: "Fecha y Hora", valueFormatString: "DD-MM HH:mm" },
            axisY: { title: "%" },
            data: [{ type: "line", color: "#2196f3", lineThickness: 3, markerSize: 5, dataPoints: [] }]
        })
    };
}

/**
 * Realiza una solicitud para obtener datos históricos y graficarlos.
 * @param {Object} charts - Los gráficos por campo.
 */
function fetchDataAndPlotAll(charts) {
    const apiUrl = "https://api.thingspeak.com/channels/2770121/feeds.json";
    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            const fields = ["lluvia", "temperatura", "vientoMedio", "rafaga", "humedad"];
            fields.forEach(field => {
                const fieldData = parseFieldData(data.feeds, field);
                plotData(charts[field], fieldData);
            });
        })
        .catch(console.error);
}

/**
 * Obtiene y muestra los últimos datos de todos los campos.
 */
function fetchLatestData() {
    const apiUrl = "https://api.thingspeak.com/channels/2770121/feeds.json";
    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            const latest = data.feeds[data.feeds.length - 1];
            document.getElementById("rainData").textContent = `${latest.field1 || 0} mm`;
            document.getElementById("tempData").textContent = `${latest.field2 || 0} °C`;
            document.getElementById("windData").textContent = `${latest.field4 || 0} m/s`;
            document.getElementById("gustData").textContent = `${latest.field5 || 0} m/s`;
            document.getElementById("humidityData").textContent = `${latest.field6 || 0}%`;
        })
        .catch(console.error);
}


/**
 * Extrae datos de un campo específico de la respuesta de la API.
 */
function parseFieldData(feeds, fieldName) {
    const fieldMap = {
        lluvia: "field1",
        temperatura: "field2",
        vientoMedio: "field4",
        rafaga: "field5",
        humedad: "field6"
    };
    const field = fieldMap[fieldName];
    return feeds.map(feed => ({
        x: new Date(feed.created_at),
        y: parseFloat(feed[field])
    }));
}

/**
 * Plotea los datos en un gráfico.
 */
function plotData(chart, data) {
    chart.options.data[0].dataPoints = data;
    chart.render();
}


document.getElementById("darkModeToggle").addEventListener("click", () => {
    document.body.classList.toggle("dark-mode");
    const isDarkMode = document.body.classList.contains("dark-mode");
    document.getElementById("darkModeToggle").textContent = isDarkMode ? "Oscuro" : "Claro";
});


// URL de la API
const url = 'https://www.meteosource.com/api/v1/free/point?lat=41.0620N&lon=6.2853W&sections=all&timezone=auto&language=en&units=metric&key=3anr1qzk4s6wgfv0u6k8gsjawl8ilqhyzeya64fx';  // Sustituye con tu URL real

// Función para hacer el fetch y obtener los datos
async function obtenerDatosPrevision() {
    try {
        const response = await fetch(url);
        const datos = await response.json();
        return datos;
    } catch (error) {
        console.error('Error al obtener los datos de la API:', error);
    }
}
// Diccionario para traducir el resumen
const weatherPhraseTranslations = {
    // Condiciones meteorológicas básicas
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

    // Cambios meteorológicos
    "changing to": "cambiando a",
    "by evening": "hacia la tarde",
    "by afternoon and evening": "por la tarde y la noche",
    "in the evening": "en la noche",
    "in the afternoon": "en la tarde",
    "in the morning": "por la mañana",
    "later": "más tarde",

    // Temperaturas
    "Temperature falling to": "La temperatura bajará a",
    "Temperature rising to": "La temperatura subirá a",
    "Temperature": "Temperatura",
    "°C": "°C",

    // Dirección y velocidad del viento
    "Wind from": "Viento del",
    "m/s": "m/s",

    // Precipitación
    "Rain": "Lluvia",
    "Snow": "Nieve",
    "None": "Ninguna",
    "Precipitation": "Precipitación",

    // Nubes
    "Cloud cover": "Cobertura de nubes",

    // General
    "Falling to": "Bajando a",
    "Rising to": "Subiendo a",
    "°C": "°C"
};


// Función para traducir el resumen
function translateSummary(summary) {
    let translated = summary;

    // Reemplaza frases comunes según el diccionario
    for (const [englishPhrase, spanishPhrase] of Object.entries(weatherPhraseTranslations)) {
        const regex = new RegExp(englishPhrase, "gi"); // Busca la frase ignorando mayúsculas
        translated = translated.replace(regex, spanishPhrase);
    }

    // Ajustes adicionales: manejo de rangos de temperatura
    translated = translated.replace(/(\d+)\s*\/\s*(\d+)\s*°C/gi, "$1 °C / $2 °C");
    return translated;
}

function extraerDatosPrevision(datos) {
    // Creamos tres arreglos, uno para cada gráfico
    const datosTemperatura = [];
    const datosViento = [];
    const datosLluvia = [];

    // Procesamos los datos por cada hora
    datos.hourly.data.forEach(hour => {
        datosTemperatura.push({
            x: new Date(hour.date * 1000), // Multiplicamos por 1000 para convertirlo a milisegundos
            y: hour.temperature
        });

        datosViento.push({
            x: new Date(hour.date * 1000),
            y: hour.wind.speed
        });

        datosLluvia.push({
            x: new Date(hour.date * 1000),
            y: hour.precipitation.total || 0 // Usamos 0 si no hay precipitación
        });
    });

    return {
        temperatura: datosTemperatura,
        viento: datosViento,
        lluvia: datosLluvia
    };
}

// Cargar y mostrar la previsión
async function cargarPrevision() {
    const datos = await obtenerDatosPrevision();
    const previsiones = extraerDatosPrevision(datos);
    mostrarPrevision(previsiones);
}

function mostrarActual(datos) {
    const tbody = document.getElementById('tablaActual').querySelector('tbody');
    tbody.innerHTML = ''; // Limpia el contenido anterior

    const fila = document.createElement('tr');
    fila.innerHTML = `
        <td>${translateSummary(datos.summary)}</td>
        <td>${datos.temperature}</td>
        <td>${datos.wind.speed} m/s, ${datos.wind.dir}</td>
        <td>${datos.precipitation.total}</td>
        <td>${datos.cloud_cover}</td>
    `;
    tbody.appendChild(fila);
}
function mostrarHoraria(datos) {
    const tbody = document.getElementById('tablaHoraria').querySelector('tbody');
    tbody.innerHTML = ''; // Limpia el contenido anterior

    datos.forEach(hour => {
        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td>${new Date(hour.date).toLocaleString()}</td>
            <td>${translateSummary(hour.summary)}</td>
            <td>${hour.temperature}</td>
            <td>${hour.wind.speed} m/s, ${hour.wind.dir}</td>
            <td>${hour.precipitation.total}</td>
            <td>${hour.cloud_cover.total}</td>
        `;
        tbody.appendChild(fila);
    });
}
function mostrarDiaria(datos) {
    const tbody = document.getElementById('tablaDiaria').querySelector('tbody');
    tbody.innerHTML = ''; // Limpia el contenido anterior

    datos.forEach(day => {
        const fila = document.createElement('tr');
        fila.innerHTML = `
            <td>${day.day}</td>
            <td>${translateSummary(day.summary)}</td>
            <td>${day.all_day.temperature_min}</td>
            <td>${day.all_day.temperature_max}</td>
            <td>${day.all_day.wind.speed} m/s, ${day.all_day.wind.dir}</td>
            <td>${day.all_day.precipitation.total}</td>
            <td>${day.all_day.cloud_cover.total}</td>
        `;
        tbody.appendChild(fila);
    });
}


function mostrarCondiciones(datos) {
    // Puedes acceder a los resúmenes del clima para mostrar un texto como "Nublado" o "Soleado"
    const condiciones = datos.hourly.data.map(hour => hour.summary);
    // Muestra el resumen del clima para la primera hora, por ejemplo
    document.getElementById("condicionesClima").textContent = condiciones[0];
}

// Llamamos a la función al obtener los datos
document.getElementById('fetchForecastBtn').addEventListener('click', async () => {
    const loading = document.getElementById("loading");
    try {
        loading.style.display = "block";
        const respuesta = await fetch(url); // Sustituye por la URL real
        const datos = await respuesta.json();

        mostrarActual(datos.current);
        mostrarHoraria(datos.hourly.data);
        mostrarDiaria(datos.daily.data);
    } catch (error) {
        console.error('Error al cargar la previsión:', error);
        alert('No se pudieron cargar los datos de previsión.');
    }
    loading.style.display = "none";
});






