/**
 * Crea gráficos zoomeables para todos los campos.
 * @returns {Object} Un objeto con gráficos por campo.
 */
function createZoomableCharts() {
    return {
        temperatura: createChart("chartContainerTemperatura", "Temperatura", "°C", "#ff2121"),
        lluvia: createChart("chartContainerLluvia", "Lluvia", "mm", "#2196f3"),
        vientoMedio: createChart("chartContainerVientoMedio", "Viento Medio", "km/h", "#fcbb08"),
        rafaga: createChart("chartContainerRafaga", "Ráfaga", "km/h", "#fcbb08"),
        humedad: createChart("chartContainerHumedad", "Humedad", "%", "#2196f3")
    };
}

/**
 * Crea un gráfico genérico con las opciones proporcionadas.
 */
function createChart(containerId, title, yTitle, color) {
    return new CanvasJS.Chart(containerId, {
        theme: "dark1",
        animationEnabled: true,
        zoomEnabled: true,
        title: { text: title },
        axisX: { title: "Fecha y Hora", valueFormatString: "DD-MM HH:mm" },
        axisY: { title: yTitle },
        data: [{ type: "line", color, lineThickness: 3, markerSize: 5, dataPoints: [] }]
    });
}

/**
 * Plotea los datos en un gráfico.
 */
function plotData(chart, data) {
    chart.options.data[0].dataPoints = data;
    chart.render();
}
