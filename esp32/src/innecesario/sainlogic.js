function fetchData() {
    fetch("/data")
        .then(response => response.json())
        .then(data => {
            document.getElementById("temperature").innerText = "Temperatura: " + data.temp_f + " °C";
            document.getElementById("humidity").innerText = "Humedad: " + data.humidity_ + " %";
            document.getElementById("wind_dir").innerText = "Dirección del Viento: " + data.wind_dir_deg + " °";
            document.getElementById("avr_wind_speed").innerText = "Velocidad Promedio del Viento: " + data.avr_wind_m_s + " m/s";
            document.getElementById("gust_wind_speed").innerText = "Ráfaga de Viento: " + data.gust_wind_m_s + " m/s";
            document.getElementById("rain").innerText = "Lluvia: " + data.rain_mm + " mm";
        })
        .catch(error => console.error("Error fetching data:", error));
}

// Actualizar los datos cada 2 segundos
setInterval(fetchData, 2000);
