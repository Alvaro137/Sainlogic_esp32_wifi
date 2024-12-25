window.onload = function () {
    const apiUrlLatest = "https://api.thingspeak.com/channels/2770121/feeds.json?days=1";
    const apiUrl = "https://api.thingspeak.com/channels/2770121/feeds.json";

    // Inicializa pestañas
    openTab('actual');

    // Cargar datos iniciales
    fetchLatestData(apiUrlLatest);
    // Crea gráficos
    const charts = createZoomableCharts();


    // Configura eventos
    document.querySelector('button[onclick="openTab(\'grafico\')"]').addEventListener('click', () => {
        fetchDataAndPlotAll(apiUrl, charts);
    });

};