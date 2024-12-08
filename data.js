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
 * Calcula la sensación térmica simplificada (índice de calor y Wind Chill)
 * Temperatura en °C, Humedad en % y Viento en km/h
*/
function calculateImprovedHeatIndex(temperature, humidity, windSpeed) {
    if (isNaN(temperature) || isNaN(humidity) || isNaN(windSpeed)) return null;

    // Calcula el Heat Index (sensación térmica por calor) utilizando la fórmula estándar
    const heatIndex = -8.78469475556 + 1.61139411 * temperature + 2.33854883889 * humidity
        - 0.14611605 * temperature * humidity - 0.012308094 * Math.pow(temperature, 2)
        - 0.016424827777 * Math.pow(humidity, 2) + 0.002211732 * Math.pow(temperature, 2) * humidity
        + 0.00072546 * temperature * Math.pow(humidity, 2) - 0.000003582 * Math.pow(temperature, 2) * Math.pow(humidity, 2);

    // Si la temperatura es mayor a 27.8°C, la humedad afecta significativamente la sensación térmica
    if (temperature > 27.8) {
        return heatIndex;  // Cuando la temperatura es suficientemente alta, se usa el Heat Index
    }

    // Calcula el Wind Chill (sensación térmica por frío debido al viento)
    const windChill = 13.12 + 0.6215 * temperature - 11.37 * Math.pow(windSpeed, 0.16) + 0.3965 * temperature * Math.pow(windSpeed, 0.16);

    // Si hace frío y el viento es fuerte, usamos el Wind Chill
    if (temperature < 10) {
        return windChill;
    }

    // Si la temperatura no es ni muy caliente ni muy fría, usamos un promedio de ambos índices
    return (heatIndex + windChill) / 2;
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
            const humidity = parseFloat(latest.field6);
            const windSpeed = parseFloat(latest.field4);
            const improvedHeatIndex = calculateImprovedHeatIndex(temperature, humidity, windSpeed);
            if (improvedHeatIndex !== null) {
                document.getElementById("heatIndexData").textContent = `${improvedHeatIndex.toFixed(2)} °C`;
            } else {
                document.getElementById("heatIndexData").textContent = "No disponible";
            }
        })
        .catch(console.error);
}


/**
 * Realiza una solicitud para obtener datos históricos y graficarlos.
 */
function fetchDataAndPlotAll(apiUrl, charts) {
    // Agrega el evento al formulario
    document.getElementById('dateRangeForm').addEventListener('submit', function (e) {
        e.preventDefault();

        const startDateInput = document.getElementById('startDate').value;
        const endDateInput = document.getElementById('endDate').value;

        if (!validateDates(startDateInput, endDateInput)) return;

        const loading = document.getElementById("loading");
        loading.style.display = "block";

        const startDate = new Date(startDateInput).toISOString().slice(0, 19);
        const endDate = new Date(endDateInput).toISOString().slice(0, 19);

        const apiUrlWithParams = `${apiUrl}?start=${startDate}&end=${endDate}`;

        fetch(apiUrlWithParams)
            .then(response => {
                if (!response.ok) throw new Error(`Error ${response.status}: ${response.statusText}`);
                return response.json();
            })
            .then(data => {
                processAndPlotData(data, charts, startDateInput, endDateInput);
                loading.style.display = "none";
            })
            .catch(error => {
                console.error('Error:', error);
                loading.style.display = "none";
            });


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
    const fields = ["lluvia", "temperatura", "vientoMedio", "rafaga", "humedad"];
    fields.forEach(field => {
        const fieldData = parseFieldData(data.feeds, field);
        plotData(charts[field], fieldData);
    });
    const totalRain = calculateTotalRain(data.feeds, startDateInput, endDateInput);
    document.getElementById("totalRainData").textContent = `${totalRain.toFixed(2)} mm`;
}

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
