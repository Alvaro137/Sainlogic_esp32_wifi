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

};