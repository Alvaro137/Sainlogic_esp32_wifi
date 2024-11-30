const apiURL = "https://api.thingspeak.com/channels/2770121/feeds.json";

// Función para obtener datos de la API
async function obtenerDatos() {
    try {
        const response = await fetch(apiURL);
        const data = await response.json();

        // Mostrar datos actuales
        mostrarDatosActuales(data.feeds);

        // Graficar datos históricos
        graficarHistorico(data.feeds);
    } catch (error) {
        console.error("Error al obtener los datos:", error);
    }
}

// Función para filtrar los datos según el intervalo
function filtrarDatosPorIntervalo(feeds, intervalo) {
    const ahora = new Date();
    let fechaLimite;

    switch (intervalo) {
        case '1d': // Último día
            fechaLimite = new Date(ahora.setDate(ahora.getDate() - 1));
            break;
        case '1w': // Última semana
            fechaLimite = new Date(ahora.setDate(ahora.getDate() - 7));
            break;
        case '1m': // Último mes
            fechaLimite = new Date(ahora.setMonth(ahora.getMonth() - 1));
            break;
        default: // Todos los datos
            return feeds;
    }

    return feeds.filter(feed => new Date(feed.created_at) >= fechaLimite);
}

// Función para mostrar datos actuales
function mostrarDatosActuales(feeds) {
    const ultimoDato = feeds[feeds.length - 1];
    const datosActuales = document.getElementById("datosActuales");

    datosActuales.innerHTML = `
    <li><strong>Lluvia:</strong> ${ultimoDato.field1 || "N/A"} mm</li>
    <li><strong>Temperatura:</strong> ${ultimoDato.field2 || "N/A"} °C</li>
    <li><strong>Dirección del viento:</strong> ${ultimoDato.field3 || "N/A"}</li>
    <li><strong>Viento medio:</strong> ${ultimoDato.field4 || "N/A"} km/h</li>
    <li><strong>Ráfaga:</strong> ${ultimoDato.field5 || "N/A"} km/h</li>
    <li><strong>Humedad:</strong> ${ultimoDato.field6 || "N/A"} %</li>
  `;
}

// Función para graficar datos históricos
function graficarHistorico(feeds) {
    const ctxLluvia = document.getElementById("graficoLluvia").getContext("2d");
    const ctxTemperatura = document.getElementById("graficoTemperatura").getContext("2d");
    const ctxViento = document.getElementById("graficoViento").getContext("2d");
    const ctxRafaga = document.getElementById("graficoRafaga").getContext("2d");
    const ctxHumedad = document.getElementById("graficoHumedad").getContext("2d");

    const intervalo = document.getElementById("intervaloTiempo").value;
    const datosFiltrados = filtrarDatosPorIntervalo(feeds, intervalo);

    const etiquetas = datosFiltrados.map(feed => feed.created_at);
    const lluviaData = datosFiltrados.map(feed => feed.field1 || 0);
    const temperaturaData = datosFiltrados.map(feed => feed.field2 || 0);
    const vientoData = datosFiltrados.map(feed => feed.field3 || 0);
    const rafagaData = datosFiltrados.map(feed => feed.field4 || 0);
    const humedadData = datosFiltrados.map(feed => feed.field5 || 0);

    // Configuración de los gráficos
    const opciones = {
        responsive: true,
        plugins: {
            tooltip: {
                callbacks: {
                    label: function (tooltipItem) {
                        return tooltipItem.raw + " unidades";
                    }
                }
            }
        }
    };

    // Crear los gráficos
    new Chart(ctxLluvia, {
        type: 'line',
        data: {
            labels: etiquetas,
            datasets: [{
                label: 'Lluvia (mm)',
                data: lluviaData,
                borderColor: '#007bff',
                fill: false,
            }]
        },
        options: opciones
    });

    new Chart(ctxTemperatura, {
        type: 'line',
        data: {
            labels: etiquetas,
            datasets: [{
                label: 'Temperatura (°C)',
                data: temperaturaData,
                borderColor: '#ff4500',
                fill: false,
            }]
        },
        options: opciones
    });

    new Chart(ctxViento, {
        type: 'line',
        data: {
            labels: etiquetas,
            datasets: [{
                label: 'Viento (km/h)',
                data: vientoData,
                borderColor: '#00ff7f',
                fill: false,
            }]
        },
        options: opciones
    });

    new Chart(ctxRafaga, {
        type: 'line',
        data: {
            labels: etiquetas,
            datasets: [{
                label: 'Ráfaga (km/h)',
                data: rafagaData,
                borderColor: '#ff6347',
                fill: false,
            }]
        },
        options: opciones
    });

    new Chart(ctxHumedad, {
        type: 'line',
        data: {
            labels: etiquetas,
            datasets: [{
                label: 'Humedad (%)',
                data: humedadData,
                borderColor: '#008080',
                fill: false,
            }]
        },
        options: opciones
    });
}

// Recargar los datos
document.getElementById("reloadButton").addEventListener("click", obtenerDatos);

// Inicializar la aplicación
obtenerDatos();
