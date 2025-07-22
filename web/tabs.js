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
