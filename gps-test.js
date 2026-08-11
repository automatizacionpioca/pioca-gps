console.log("piOca GPS externo cargado");

window.addEventListener("load", function () {
  var estado = document.getElementById("gpsEstado");

  if (estado) {
    estado.innerHTML = "✅ JS EXTERNO FUNCIONA";
    estado.style.background = "#dff5e1";
  }
});
