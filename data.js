/**
 * Calcula la lluvia acumulada en un rango de fechas
 */
/**
 * Calcula la lluvia acumulada en un rango de fechas y solo suma lluvia mayor a 0.3 mm
 * Solo se suma si el valor actual es mayor a 0.3 mm y el valor anterior es <= 0.3 mm.
 */
function calculateTotalRain(feeds, startDate, endDate, minRain = 0.3) {
    let totalRain = 0;

    // Filtra las feeds que están dentro del rango de fechas
    const filteredFeeds = feeds.filter(feed => {
        const feedDate = new Date(feed.created_at);
        return feedDate >= new Date(startDate) && feedDate <= new Date(endDate);
    });

    // Recorre las feeds filtradas para aplicar la lógica
    for (let i = 1; i < filteredFeeds.length; i++) {
        const currentRain = parseFloat(filteredFeeds[i].field1) || 0;
        const lastRain = parseFloat(filteredFeeds[i - 1].field1) || 0;

        // Solo sumamos si el valor actual es mayor a minRain y el anterior es <= minRain
        if (currentRain > minRain && lastRain <= minRain) {
            totalRain += currentRain;
        }
    }

    return totalRain;
}




/**
 * Aplica la media móvil a un array de datos.
 * @param {Array} data - Array de datos a suavizar.
 * @param {number} period - Número de períodos para la media móvil.
 * @returns {Array} Array de datos suavizados.
 */
function movingAverage(data, numdatos) {
    const smoothedData = [];
    const periodo = data.length / numdatos
    for (let i = 0; i < data.length; i++) {
        const start = Math.max(i - periodo + 1, 0); // Asegura que no acceda a índices negativos
        const subset = data.slice(start, i + 1);
        const average = subset.reduce((sum, point) => sum + point.y, 0) / subset.length;
        smoothedData.push({ x: data[i].x, y: average });
    }
    return smoothedData;
}


// Función para verificar si el tiempo ha excedido tmax minutos
function hasTimeExceeded(lastDate, tmax) {
    const currentTime = new Date();
    const lastTime = new Date(lastDate);
    const timeDifference = (currentTime - lastTime) / 60000; // Diferencia en minutos

    const disclaimerElement = document.getElementById('disclaimer');
    if (timeDifference > tmax) {
        disclaimerElement.classList.remove('hidden');
        disclaimerElement.classList.add('show-disclaimer');
        disclaimerElement.innerHTML = `<p>No se han detectado cambios en los datos durante los últimos ${Math.floor(timeDifference)} minutos. Hay 2 posibles soluciones:</p>` +
            `<p>1) Presiona el botón "EN":</p>` +
            `<img src="EN.jpg" alt="Advertencia" />` +
            `<p>2) Conéctate al wifi ESP32_AP (contraseña: 12345678), y luego presiona configure wifi (TP_Link_AP_7C1E, contraseña: 35019503)</p>`;
    } else {
        disclaimerElement.classList.remove('show-disclaimer');
        disclaimerElement.classList.add('hidden');
    }
}
/**
 * Obtiene y muestra los últimos datos de todos los campos.
 */
function fetchLatestData(apiUrl) {
    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            const latest = data.feeds[data.feeds.length - 1];
            document.getElementById("rainData").textContent = `${parseFloat(latest.field1).toFixed(2) || 0} mm`;
            document.getElementById("tempData").textContent = `${parseFloat(latest.field2).toFixed(2) || 0} °C`;
            document.getElementById("windData").textContent = `${parseFloat(latest.field4).toFixed(2) || 0} km/h`;
            document.getElementById("gustData").textContent = `${parseFloat(latest.field5).toFixed(2) || 0} km/h`;
            document.getElementById("humidityData").textContent = `${parseFloat(latest.field6).toFixed(2) || 0}%`;

            const temperature = parseFloat(latest.field2);
            const windDirection = parseFloat(latest.field3) + 22.0;
            if (windDirection >= 360.0) {
                windDirection = windDirection - 360.0
            }
            const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
            const index = Math.floor((windDirection) / 45) % 8; // Convertir grados a un índice de los puntos cardinales
            const windDirectionText = directions[index];
            document.getElementById("directionData").textContent = `${windDirection.toFixed(2) || 0} ° (${windDirectionText})`;
            const windSpeed = parseFloat(latest.field4);
            const humidity = parseFloat(latest.field6);

            // Verificar si han pasado más de tmax minutos desde el último dato
            hasTimeExceeded(latest.created_at, 10);
        })
        .catch(console.error);
}

function updateProgressBar(percentage) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `Cargando: ${percentage.toFixed(0)}%`;
}
/**
 * Realiza una solicitud para obtener datos históricos y graficarlos.
 */
function fetchDataAndPlotAll(apiUrl, charts) {
    document.getElementById('dateRangeForm').addEventListener('submit', function (e) {
        e.preventDefault();

        const startDateInput = document.getElementById('startDate').value;
        const endDateInput = document.getElementById('endDate').value;

        if (!validateDates(startDateInput, endDateInput)) return;

        const loading = document.getElementById("loadingProgress");
        loading.style.display = "flex";

        let currentStartDate = new Date(startDateInput);
        const finalEndDate = new Date(endDateInput);
        const currentDate = new Date();
        const earliestDate = new Date("2024-11-30T11:17:40Z");
        const allData = [];
        let completedRequests = 0;

        if (currentStartDate < earliestDate) {
            currentStartDate = earliestDate;
        }

        const totalRequests = Math.ceil((finalEndDate - currentStartDate) / (2 * 24 * 60 * 60 * 1000)); // Número total de bloques

        async function fetchAllChunks() {
            try {
                while (currentStartDate <= finalEndDate && currentStartDate <= currentDate) {
                    const nextStartDate = new Date(currentStartDate);
                    nextStartDate.setDate(nextStartDate.getDate() + 2);

                    const currentEndDate = nextStartDate > finalEndDate ? finalEndDate : nextStartDate;

                    const apiUrlWithParams = `${apiUrl}?start=${currentStartDate.toISOString().slice(0, 19)}&end=${currentEndDate.toISOString().slice(0, 19)}`;
                    const response = await fetch(apiUrlWithParams);
                    if (!response.ok) {
                        throw new Error(`Error ${response.status}: ${response.statusText}`);
                    }

                    const data = await response.json();
                    if (data.feeds && data.feeds.length > 0) {
                        allData.push(...data.feeds);
                        const lastEntryDate = new Date(data.feeds[data.feeds.length - 1].created_at);
                        currentStartDate = new Date(lastEntryDate);
                        currentStartDate.setSeconds(currentStartDate.getSeconds() + 1);
                    } else {
                        currentStartDate = currentEndDate;
                    }

                    completedRequests++;
                    const progress = (completedRequests / totalRequests) * 100;
                    updateProgressBar(progress);
                }

                processAndPlotData({ feeds: allData }, charts, startDateInput, endDateInput);
                loading.style.display = "none";

            } catch (error) {
                console.error('Error:', error);
                loading.style.display = "none";
            }
        }

        fetchAllChunks();
    });
}



function validateDates(startDate, endDate) {
    if (!startDate || !endDate) {
        alert("Por favor, selecciona ambas fechas.");
        return false;
    }

    if (new Date(startDate) > new Date(endDate)) {
        alert("La fecha de inicio debe ser anterior a la fecha de fin.");
        return false;
    }
    return true;
}

function processAndPlotData(data, charts, startDateInput, endDateInput) {
    const fields = ["lluvia", "temperatura", "vientoMedio", "rafaga", "humedad", "direccionViento"];
    // Definir el número de períodos para la media móvil (en este caso 10)
    const movingAveragePeriods = {
        lluvia: 2000,
        temperatura: 3000,
        vientoMedio: 300,
        rafaga: 300,
        humedad: 500,
        direccionViento: 80
    };

    fields.forEach(field => {
        let fieldData = parseFieldData(data.feeds, field);

        // Aplicar la media móvil con el período correspondiente para cada campo
        const movingAveragePeriod = movingAveragePeriods[field];
        fieldData = movingAverage(fieldData, movingAveragePeriod);

        plotData(charts[field], fieldData);
    });

    const totalRain = calculateTotalRain(data.feeds, startDateInput, endDateInput);
    document.getElementById("totalRainData").textContent = `${totalRain.toFixed(2)} mm`;
}


function PlotTempSemanal(data) {
    const fields = ["temperatura"];
    // Definir el número de períodos para la media móvil (en este caso 10)
    const movingAveragePeriods = 1000;

    fields.forEach(field => {
        let fieldData = parseFieldData(data.feeds, field);

        // Aplicar la media móvil con el período correspondiente para cada campo
        const movingAveragePeriod = movingAveragePeriods[field];
        fieldData = movingAverage(fieldData, movingAveragePeriod);
        plotSemanal(fieldData);
    });
}

function parseFieldData(feeds, fieldName) {
    const fieldMap = {
        lluvia: "field1",
        temperatura: "field2",
        direccionViento: "field3",
        vientoMedio: "field4",
        rafaga: "field5",
        humedad: "field6",
    };
    const field = fieldMap[fieldName];
    return feeds.map(feed => ({
        x: new Date(feed.created_at),
        y: fieldName === 'direccionViento' ? (parseFloat(feed[field]) || 0) : parseFloat(feed[field])
    }));
}
