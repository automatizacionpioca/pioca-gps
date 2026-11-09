#!/usr/bin/env python3
"""Generador B20 aislado: ejecutar después de generar fuentes B19 desde el workflow existente."""
from pathlib import Path
import shutil
import re
import subprocess
import tempfile

ROOT = Path.cwd()


def one(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'B20: ancla {label}: {count} coincidencias, esperaba una')
    return text.replace(old, new, 1)


def new_html(name):
    src = ROOT / f'{name}-b19-diag.html'
    if not src.is_file():
        raise RuntimeError(f'Falta fuente B19 generada: {src}')
    return src.read_text(encoding='utf-8').replace('-b19-diag.html', '-b20-diag.html')


# ========================== ADMIN ==========================
admin = new_html('admin')
admin = one(admin,
    r'''      const confirmar =
        window.confirm(
          "¿Usar esta dirección para crear un seguimiento?\n\n" +
          direccion
        );

      if(!confirmar){
        ocultarEstado(adminEstado);
        return;
      }
''',
    '''      // B20: compartir una ubicación desde Google Maps ya expresa la
      // decisión de iniciar el seguimiento. Sin confirmación bloqueante.
      // Las validaciones del destino, ruta y servidor se mantienen intactas.
      b20Medir('b20.share_auto_confirm',1,false);
''',
    'autocreación al compartir desde Google Maps sin cuadro confirm')
admin = one(admin,
    '    verificandoBox.textContent =\n      "Verificando si existe un seguimiento activo...";',
    '''    verificandoBox.textContent =
      "Verificando si existe un seguimiento activo...";

    // B20: no bloquear el acceso visual a la verificación mientras responde Supabase.
    ocultarSplash();
    try{if(window.__piocaDiagMetric)window.__piocaDiagMetric('b20.admin_early_display',1,0)}catch(_){}''',
    'panel visible durante comprobación')
admin = one(admin,
    '  async function procesarCompartidoPendiente(){',
    '''  function b20Medir(nombre,valor,fallo){
    try{if(window.__piocaDiagMetric)window.__piocaDiagMetric(nombre,valor,fallo?1:0)}catch(_){}
  }

  async function procesarCompartidoPendiente(){''',
    'instrumentación de compartir')
admin = one(admin,
    '    compartidoEnProceso = true;\n',
    '''    compartidoEnProceso = true;
    const b20InicioCompartido=performance.now();
    b20Medir('b20.share_begin',1,false);
''',
    'medir comienzo')
admin = one(admin,
    '''      const resuelto =
        await invocarTrackingRouter({
          action:"resolve_shared_destination",
          shared_text:textoCompartido
        });''',
    '''      // B20: posición GPS y resolución del destino en paralelo.
      // Se conservan las mismas verificaciones y llamadas de ruta.
      const b20InicioResolve=performance.now();
      const b20OrigenPendiente=obtenerPosicionActual().then(
        value=>({value:value,error:null}),
        error=>({value:null,error:error})
      );
      const resuelto =
        await invocarTrackingRouter({
          action:"resolve_shared_destination",
          shared_text:textoCompartido
        });
      b20Medir('b20.share_resolve_ms',performance.now()-b20InicioResolve,false);''',
    'paralelizar GPS con resolución')
admin = one(admin,
    '''      const origen =
        await obtenerPosicionActual();

      const ruta =
        await invocarTrackingRouter({''',
    '''      const b20EsperaGps=performance.now();
      const b20Origen=await b20OrigenPendiente;
      if(b20Origen.error || !b20Origen.value){
        throw b20Origen.error || new Error('GPS_NO_DISPONIBLE');
      }
      const origen=b20Origen.value;
      b20Medir('b20.share_gps_wait_ms',performance.now()-b20EsperaGps,false);

      const b20InicioRuta=performance.now();
      const ruta =
        await invocarTrackingRouter({''',
    'esperar GPS sin repetir obtención')
admin = one(admin,
    '''      if(
        !ruta.route ||
        !ruta.route.arrival_at
      ){''',
    '''      b20Medir('b20.share_route_ms',performance.now()-b20InicioRuta,false);
      if(
        !ruta.route ||
        !ruta.route.arrival_at
      ){''',
    'medir resolución de ruta')
admin = one(admin,
    '''      const {data,error} =
        await supabaseClient.rpc(
          "create_tracking_service_eta",''',
    '''      const b20InicioCrear=performance.now();
      const {data,error} =
        await supabaseClient.rpc(
          "create_tracking_service_eta",''',
    'medir creación')
admin = one(admin,
    '''      const s = data[0];

      if(
        s.success === false &&
        s.message === "ACTIVE_EXISTS"
      ){''',
    '''      const s = data[0];
      b20Medir('b20.share_create_ms',performance.now()-b20InicioCrear,false);
      b20Medir('b20.share_total_ms',performance.now()-b20InicioCompartido,false);

      if(
        s.success === false &&
        s.message === "ACTIVE_EXISTS"
      ){''',
    'medir creación y total')
admin = one(admin,
    '  async function seleccionarContacto(){',
    '''  // Cuando Android entrega otro ACTION_SEND y este panel está abierto,
  // procesamos el destino recibido sin descargar nuevamente el documento.
  window.piocaB20ProcesarCompartidoNuevo=function(){
    b20Medir('b20.share_reuse_admin',1,false);
    void procesarCompartidoPendiente();
  };

  async function seleccionarContacto(){''',
    'evitar recarga al volver a compartir')
admin = one(admin,"'build.b18_diag'","'build.b20_diag'",'etiqueta admin B20')
admin += '\n'
(ROOT/'admin-b20-diag.html').write_text(admin,encoding='utf-8')

# ========================== PANEL ==========================
index = new_html('index').replace('piocaB19','piocaB20')
index = one(index,
    '''  window.addEventListener('popstate',function(){
    if(piocaB20PreviewActivo)piocaB20CerrarPreview();
  });''',
    '''  window.addEventListener('popstate',function(){
    if(piocaB20PreviewActivo){
      piocaB20Metrica('b20.preview_exit_history',1,false);
      piocaB20CerrarPreview();
    }
  });
  window.addEventListener('pagehide',function(){
    if(piocaB20PreviewActivo){
      piocaB20Metrica('b20.preview_parent_pagehide',1,false);
    }
  });''',
    'causa de salida de Preview')
index = one(index,"'build.b19_diag'","'build.b20_diag'",'etiqueta de diagnóstico B20')
(ROOT/'index-b20-diag.html').write_text(index,encoding='utf-8')

# ========================== CLIENTE R67 / VÉRTICES ==========================
cliente = new_html('cliente')

# B20 busca solo una intersección vial con nodeId COMPARTIDO entre dos ways.
# Nunca acepta únicamente un cruce geométrico de segmentos desconectados.
vertex_code = r'''  /* ==========================================================
     B20 DIAG: INTERSECCIÓN CARTOGRÁFICA COMO PRIMERA OPCIÓN
     R67 proporciona topología OSM; R63/R64 conserva fallback completo.
     Solo modifica la esquina VISUAL (nunca GPS físico ni ETA).
     ========================================================== */
  function b20MetricaVertice(nombre,valor,fallo){
    try{if(window.__piocaDiagMetric)window.__piocaDiagMetric(nombre,valor,fallo?1:0)}catch(_){}
  }

  function b20InterseccionVial(latEntrada,lonEntrada,latSalida,lonSalida,
                             latVertice,lonVertice,velocidadKmh){
    const t0=performance.now();
    try{
      if(!R67_MAP_MATCH.ACTIVO ||
         !Number.isFinite(velocidadKmh) ||
         velocidadKmh>=R67_MAP_MATCH.VELOCIDAD_MAX_KMH ||
         r67SegmentosViales.length===0 ||
         ![latEntrada,lonEntrada,latSalida,lonSalida,latVertice,lonVertice].every(Number.isFinite)){
        return null;
      }

      const candidatos=r67CandidatosIndice(latVertice,lonVertice);
      const nodos=new Map();
      for(const seg of candidatos){
        for(const extremo of [
          {id:seg.nodeA,lat:seg.lat1,lon:seg.lon1},
          {id:seg.nodeB,lat:seg.lat2,lon:seg.lon2}
        ]){
          if(extremo.id===null || extremo.id===undefined)continue;
          if(distanciaMetros(extremo.lat,extremo.lon,latVertice,lonVertice)>20)continue;
          const id=String(extremo.id);
          let grupo=nodos.get(id);
          if(!grupo){grupo={lat:extremo.lat,lon:extremo.lon,vias:new Map()};nodos.set(id,grupo);}
          const wayId=String(seg.wayId);
          let via=grupo.vias.get(wayId);
          if(!via){via=[];grupo.vias.set(wayId,via);}
          via.push(seg);
        }
      }

      let mejor=null;
      for(const nodo of nodos.values()){
        if(nodo.vias.size<2)continue;
        const distanciaVertice=distanciaMetros(latVertice,lonVertice,nodo.lat,nodo.lon);
        const distanciaEntradaNodo=distanciaMetros(latEntrada,lonEntrada,nodo.lat,nodo.lon);
        const distanciaSalidaNodo=distanciaMetros(latSalida,lonSalida,nodo.lat,nodo.lon);
        if(distanciaEntradaNodo>45 || distanciaSalidaNodo>45)continue;

        let mejorEntrada=null,mejorSalida=null;
        for(const [wayId,segmentos] of nodo.vias.entries()){
          let de=Infinity,ds=Infinity;
          for(const seg of segmentos){
            const pe=r67ProyectarSobreSegmento(latEntrada,lonEntrada,seg);
            const ps=r67ProyectarSobreSegmento(latSalida,lonSalida,seg);
            if(pe)de=Math.min(de,pe.distancia);
            if(ps)ds=Math.min(ds,ps.distancia);
          }
          if(!mejorEntrada || de<mejorEntrada.distancia){mejorEntrada={wayId:wayId,distancia:de};}
          if(!mejorSalida || ds<mejorSalida.distancia){mejorSalida={wayId:wayId,distancia:ds};}
        }
        // Encontrar dos vías diferentes: calle de entrada y calle de salida.
        let puntaje=Infinity;
        for(const [wayEntrada,ssEntrada] of nodo.vias.entries()){
          const de=Math.min(...ssEntrada.map(seg=>r67ProyectarSobreSegmento(latEntrada,lonEntrada,seg).distancia));
          if(de>15)continue;
          for(const [waySalida,ssSalida] of nodo.vias.entries()){
            if(wayEntrada===waySalida)continue;
            const ds=Math.min(...ssSalida.map(seg=>r67ProyectarSobreSegmento(latSalida,lonSalida,seg).distancia));
            if(ds>15)continue;
            puntaje=Math.min(puntaje, distanciaVertice*0.6+de+ds);
          }
        }
        if(Number.isFinite(puntaje)&&(!mejor||puntaje<mejor.puntaje)){
          mejor={lat:nodo.lat,lon:nodo.lon,puntaje:puntaje};
        }
      }
      return mejor;
    }finally{
      b20MetricaVertice('b20.vertex_r67_eval_ms',performance.now()-t0,false);
    }
  }

'''
cliente = one(cliente,
    '  function abrirVerticeGeometricoR63(\n',
    vertex_code + '  function abrirVerticeGeometricoR63(\n',
    'introducir topología R67 antes del estimador R63')
# B20: ambos caminos de giro tardío R65 (normal y reenganche) reciben
# una intersección OSM cuando existe; sin cartografía, R65/R63 quedan intactos.
# Un giro tardío JAMÁS introduce el nodo detrás del pin ni retrocede.
cliente = one(cliente,
    "  function construirCurvaTangencialR65(\n    inicio,\n    destino\n  ){",
    "  function construirCurvaTangencialR65(\n    inicio,\n    destino,\n    esquinaR67\n  ){",
    'habilitar referencia R67 en constructor de curva tardía')
cliente = one(cliente,
    """    const controlMetros =
      Math.max(
        1.4,""",
    """    /* B20: la esquina cartográfica refina la tangente de salida.
       No hay recorrido de regreso hacia una esquina ya sobrepasada. */
    if(esquinaR67 && Number.isFinite(esquinaR67.lat) &&
       Number.isFinite(esquinaR67.lon)){
      const dSalidaR67=distanciaMetros(esquinaR67.lat,esquinaR67.lon,
                                     destino.lat,destino.lon);
      if(Number.isFinite(dSalidaR67) && dSalidaR67>=2 && dSalidaR67<=45){
        const rumboCartografia=rumboGrados(esquinaR67.lat,esquinaR67.lon,
                                          destino.lat,destino.lon);
        if(Number.isFinite(rumboCartografia)){
          rumboSalida=rumboCartografia;
          b20MetricaVertice('b20.vertex_r67_late_tangent',1,false);
        }
      }
    }

    const controlMetros =
      Math.max(
        1.4,""",
    'tangente de salida guiada por el nodo R67 sin retroceso')
cliente = one(cliente,
    """  function animarGiroTardioR65(
    latDestino,
    lonDestino,
    duracionMs,
    velocidadKmh
  ){""",
    """  function animarGiroTardioR65(
    latDestino,
    lonDestino,
    duracionMs,
    velocidadKmh,
    esquinaR67
  ){""",
    'aceptar esquina opcional en giro tardío R65')
cliente = one(cliente,
    """    const puntos =
      construirCurvaTangencialR65(
        inicio,
        destino
      );""",
    """    const puntos =
      construirCurvaTangencialR65(
        inicio,
        destino,
        esquinaR67 || null
      );""",
    'pasar esquina cartográfica a generador de curva')

# Giro tardío regular: consultar la intersección antes de decidir el tipo.
cliente = one(cliente,
    """      let giroTardioR65 =
        false;

      if(
        giroProtegido &&""",
    """      let giroTardioR65 =
        false;
      let esquinaR67TardiaB20=null;

      if(
        giroProtegido &&""",
    'guardar candidata R67 para giro normal/tardío')
cliente = one(cliente,
    """        const longitudColaAntesR63 =
          verticesVisualesPendientes.length;

        giroTardioR65 =
          verticeDebeResolverseTardioR65(
            verticeVisual.lat,
            verticeVisual.lon,
            latVisual,
            lonVisual
          );""",
    """        const longitudColaAntesR63 =
          verticesVisualesPendientes.length;

        esquinaR67TardiaB20=b20InterseccionVial(
          ultimoPuntoServidor.lat,ultimoPuntoServidor.lon,
          lat,lon,verticeVisual.lat,verticeVisual.lon,velocidadInterna
        );
        const verticePrioritarioB20=esquinaR67TardiaB20 || verticeVisual;
        giroTardioR65 =
          verticeDebeResolverseTardioR65(
            verticePrioritarioB20.lat,
            verticePrioritarioB20.lon,
            latVisual,
            lonVisual
          );""",
    'priorizar intersección R67 al clasificar giro tardío')
cliente = one(cliente,
    """          verticeAgregadoR65 =
            agregarVerticeVisualPendiente(
              verticeVisual.lat,
              verticeVisual.lon
            ) === true;""",
    """          verticeAgregadoR65 =
            agregarVerticeVisualPendiente(
              verticePrioritarioB20.lat,
              verticePrioritarioB20.lon
            ) === true;""",
    'encolar esquina cartográfica si no fue consumida')
cliente = one(cliente,
    """        if(
          verticeAgregadoR65
        ){
          abrirVerticeGeometricoR63(
            verticeVisual,
            lat,
            lon,
            createdAt,
            longitudColaAntesR63
          );
        }""",
    """        if(verticeAgregadoR65){
          if(esquinaR67TardiaB20){
            // R67 tiene prioridad: no sustituir el nodo por TLS de R63.
            verticeGeometricoPendienteR63=null;
            b20MetricaVertice('b20.vertex_r67_used',1,false);
          }else{
            b20MetricaVertice('b20.vertex_r63_fallback',1,false);
            abrirVerticeGeometricoR63(
              verticeVisual,lat,lon,createdAt,longitudColaAntesR63
            );
          }
        }else if(giroTardioR65 && esquinaR67TardiaB20){
          // Nodo tomado como rumbo de salida, sin buscarlo hacia atrás.
          b20MetricaVertice('b20.vertex_r67_late_candidate',1,false);
        }else if(giroTardioR65){
          b20MetricaVertice('b20.vertex_r65_late_fallback',1,false);
        }""",
    'usar R67 tanto en vértices pendientes como tardíos')
cliente = one(cliente,
    """        animarGiroTardioR65(
          latVisual,
          lonVisual,
          duracion,
          velocidadInterna
        );""",
    """        animarGiroTardioR65(
          latVisual,
          lonVisual,
          duracion,
          velocidadInterna,
          esquinaR67TardiaB20
        );""",
    'dibujar giro tardío con referencia cartográfica')

# El reenganche urbano tiene un segundo camino de giro tardío R65.
cliente = one(cliente,
    """      let verticeConfirmadoAgregadoR65 =
        false;

      if(""",
    """      let verticeConfirmadoAgregadoR65 =
        false;
      let esquinaR67ReengancheB20=null;

      if(""",
    'guardar esquina cartográfica en reenganche')
cliente = one(cliente,
    """        verticeConfirmadoTardioR65 =
          verticeDebeResolverseTardioR65(
            v.lat,
            v.lon,
            latVisual,
            lonVisual
          );""",
    """        esquinaR67ReengancheB20=b20InterseccionVial(
          ultimoPuntoServidor ? ultimoPuntoServidor.lat : v.lat,
          ultimoPuntoServidor ? ultimoPuntoServidor.lon : v.lon,
          lat,lon,v.lat,v.lon,velocidadInterna
        );
        const verticePrioritarioB20=esquinaR67ReengancheB20 || v;
        verticeConfirmadoTardioR65 =
          verticeDebeResolverseTardioR65(
            verticePrioritarioB20.lat,
            verticePrioritarioB20.lon,
            latVisual,
            lonVisual
          );""",
    'reenganche R65 consulta intersección R67')
cliente = one(cliente,
    """          verticeConfirmadoAgregadoR65 =
            agregarVerticeVisualPendiente(
              v.lat,
              v.lon
            ) === true;""",
    """          verticeConfirmadoAgregadoR65 =
            agregarVerticeVisualPendiente(
              verticePrioritarioB20.lat,
              verticePrioritarioB20.lon
            ) === true;
          if(verticeConfirmadoAgregadoR65){
            b20MetricaVertice(esquinaR67ReengancheB20
              ? 'b20.vertex_r67_used' : 'b20.vertex_r63_fallback',1,false);
          }""",
    'esquina R67 en reenganche no tardío')
cliente = one(cliente,
    """          animarGiroTardioR65(
            latVisual,
            lonVisual,
            duracionReenganche,
            velocidadInterna
          );""",
    """          if(esquinaR67ReengancheB20){
            b20MetricaVertice('b20.vertex_r67_late_candidate',1,false);
          }else{
            b20MetricaVertice('b20.vertex_r65_late_fallback',1,false);
          }
          animarGiroTardioR65(
            latVisual,
            lonVisual,
            duracionReenganche,
            velocidadInterna,
            esquinaR67ReengancheB20
          );""",
    'giro tardío R65 en reenganche también usa R67')

cliente = one(cliente,
    '  function mostrarFinalizado(finalDefinitivoServidor){\n\n    terminado =',
    '''  function mostrarFinalizado(finalDefinitivoServidor){
    if(esPreviewTecnico){
      b20MetricaVertice(finalDefinitivoServidor
        ? 'b20.preview_client_finalized_server'
        : 'b20.preview_client_finalized_local',1,false);
    }

    terminado =''',
    'medir causa de pantalla final')
cliente = one(cliente,
    "'build.b18_diag'","'build.b20_diag'",'etiqueta cliente B20')
(ROOT/'cliente-b20-diag.html').write_text(cliente,encoding='utf-8')

# ========================== APK NATIVA ==========================
original = ROOT/'android-b19-diag'
if not original.is_dir():
    raise RuntimeError('Falta Android B19 generado')
native = ROOT/'android-b20-diag'
if native.exists():
    shutil.rmtree(native)
shutil.copytree(original,native)

build_gradle=native/'app/build.gradle'
gradle=build_gradle.read_text('utf-8')
gradle=one(gradle,
    'applicationId "ar.com.pioca.seguimiento.b19diag"',
    'applicationId "ar.com.pioca.seguimiento.b20diag"',
    'ID de instalación separada')
gradle,n=re.subn(r'\bversionCode\s+19\b','versionCode 20',gradle,count=1)
if n!=1:raise RuntimeError('versionCode B19 no encontrado')
gradle=one(gradle,
    'versionName "0.19-DIAG-WEBVIEW-R67"',
    'versionName "0.20-DIAG-MAPS-VERTICES"',
    'nombre B20')
build_gradle.write_text(gradle,encoding='utf-8')

manifest=native/'app/src/main/AndroidManifest.xml'
x=manifest.read_text('utf-8')
x=one(x,'android:label="piOca Seguimiento B19 DIAG"',
    'android:label="piOca Seguimiento B20 DIAG"',
    'nombre visible B20')
x=one(x,'android:launchMode="singleTop"',
    'android:launchMode="singleTask"',
    'reusar MainActivity al compartir desde Google Maps')
manifest.write_text(x,encoding='utf-8')

java=native/'app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java'
m=java.read_text('utf-8')
for page in ('admin','index','cliente'):
    m=m.replace(page+'-b19-diag.html',page+'-b20-diag.html')
# Solo optimizamos el caso ya alojado en admin. Desde otra vista, carga admin normalmente.
m=one(m,
    '''        if (
                captured
                && web != null
        ) {

            web.post(() ->
                    web.loadUrl(
                            ADMIN
                    )
            );
        }''',
    '''        if (
                captured
                && web != null
        ) {
            web.post(() -> {
                String urlActual=web.getUrl();
                if(urlActual!=null && urlActual.contains("/admin-b20-diag.html")) {
                    DiagnosticTelemetry.record("b20.share_native_reuse_admin",1,false);
                    web.evaluateJavascript(
                        "(function(){if(window.piocaB20ProcesarCompartidoNuevo){"+
                        "window.piocaB20ProcesarCompartidoNuevo();"+
                        "}else{location.reload();}})()",null);
                } else {
                    DiagnosticTelemetry.record("b20.share_native_navigation",1,false);
                    web.loadUrl(ADMIN);
                }
            });
        }''',
    'nueva recepción de Google Maps sin reconstruir panel abierto')
java.write_text(m,encoding='utf-8')

# ==================== B20 PREMIUM: ADMIN + PANEL ====================
# Interfaz y observabilidad únicamente; NO se altera GPS/ETA/R65/R67.
admin_path = ROOT/'admin-b20-diag.html'
admin = admin_path.read_text('utf-8')

admin_overlay = r'''
<div id="b20CrearOverlay" class="b20CrearOverlay" role="status" aria-live="polite" aria-label="Creando seguimiento" style="display:none">
  <div class="b20CrearTarjeta">
    <img src="icono-pioca.png" alt="Camioneta piOca" class="b20CrearCamioneta">
    <div class="b20CrearEyebrow">piOca® · GEOSEGUIMIENTO</div>
    <div class="b20CrearTitulo">CREANDO SEGUIMIENTO</div>
    <div id="b20CrearFase" class="b20CrearFase">Preparando destino...</div>
    <div class="b20CrearMeta"><span>Progreso de preparación</span><strong id="b20CrearPorcentaje">4%</strong></div>
    <div id="b20CrearPista" class="b20CrearPista" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="4" aria-label="Progreso de creación">
      <div id="b20CrearRelleno" class="b20CrearRelleno" style="width:4%"></div>
    </div>
    <div class="b20CrearNota">Preparando ID, ETA y acceso para compartir por WhatsApp</div>
  </div>
</div>
'''
admin = one(admin, '<body class="modoLogin">', '<body class="modoLogin">\n'+admin_overlay,
            'crear overlay B20 en admin')

admin_css = r'''
<style id="b20-premium-crear">
.b20CrearOverlay{position:fixed;z-index:2147483000;inset:0;background:rgba(12,32,60,.54);backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);align-items:center;justify-content:center;padding:16px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.b20CrearTarjeta{width:min(100%,420px);border:1px solid rgba(221,234,247,.92);border-radius:25px;background:linear-gradient(165deg,#fff 40%,#eff6fd);padding:27px 23px 24px;box-shadow:0 22px 65px rgba(4,25,59,.28);text-align:center}
.b20CrearCamioneta{display:block;width:96px;height:88px;object-fit:contain;margin:0 auto 5px}
.b20CrearEyebrow{color:#6c8197;font-size:10px;font-weight:800;letter-spacing:1.55px;margin-bottom:6px}
.b20CrearTitulo{color:#103865;font-size:19px;letter-spacing:.35px;font-weight:850}
.b20CrearFase{margin-top:10px;min-height:20px;color:#506984;font-size:13px;font-weight:650}
.b20CrearMeta{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:24px;color:#60758d;font-size:11px;font-weight:650}
.b20CrearMeta strong{color:#1764b0;font-size:19px;font-variant-numeric:tabular-nums}
.b20CrearPista{height:11px;border-radius:999px;background:#dce8f4;overflow:hidden;margin-top:8px;box-shadow:inset 0 1px 3px rgba(6,42,82,.1)}
.b20CrearRelleno{height:100%;border-radius:999px;background:linear-gradient(90deg,#17449e,#258ddd 80%,#55c1eb);box-shadow:0 2px 9px rgba(34,122,211,.28);transition:width .11s linear}
.b20CrearNota{margin-top:16px;font-size:11px;line-height:1.45;color:#7b8ea0}
@media(max-width:420px){.b20CrearTarjeta{padding:25px 19px}.b20CrearTitulo{font-size:17px}}
</style>
'''
admin = one(admin,'</head>',admin_css+'\n</head>','CSS overlay B20')

admin_progress_js = r'''
  /* B20 PREMIUM - avance por HITOS reales de la operación, interpolado.
     Los porcentajes intermedios son estimados (el servidor no informa %).
     El 100% sólo se registra en el panel con ID, ETA y WhatsApp listos. */
  let b20BarraActiva=false;
  let b20BarraNavegando=false;
  let b20BarraValor=0;
  let b20BarraMeta=0;
  let b20BarraTecho=0;
  let b20BarraTimer=null;
  let b20BarraUltimoT=0;
  function b20BarraPintar(){
    const valor=Math.max(0,Math.min(99,Math.floor(b20BarraValor)));
    const txt=document.getElementById('b20CrearPorcentaje');
    const fill=document.getElementById('b20CrearRelleno');
    const barra=document.getElementById('b20CrearPista');
    if(txt)txt.textContent=valor+'%';
    if(fill)fill.style.width=valor+'%';
    if(barra)barra.setAttribute('aria-valuenow',String(valor));
  }
  function b20BarraFase(texto,meta,techo){
    if(!b20BarraActiva)return;
    const fase=document.getElementById('b20CrearFase');
    if(fase)fase.textContent=texto;
    b20BarraMeta=Math.max(b20BarraMeta,Math.min(98,meta));
    b20BarraTecho=Math.max(b20BarraTecho,Math.min(98,techo));
    b20BarraPintar();
  }
  function b20BarraIniciar(){
    b20BarraCerrar();
    b20BarraActiva=true;
    b20BarraNavegando=false;
    b20BarraValor=4;
    b20BarraMeta=17;
    b20BarraTecho=31;
    b20BarraUltimoT=performance.now();
    const overlay=document.getElementById('b20CrearOverlay');
    if(overlay)overlay.style.display='flex';
    const fase=document.getElementById('b20CrearFase');
    if(fase)fase.textContent='Resolviendo ubicación de Google Maps...';
    b20BarraPintar();
    b20BarraTimer=setInterval(function(){
      if(!b20BarraActiva)return;
      const ahora=performance.now();
      const delta=Math.max(0,Math.min(1000,ahora-b20BarraUltimoT));
      b20BarraUltimoT=ahora;
      // Acelera ante la llegada de cada fase; en demoras avanza suavemente.
      if(b20BarraMeta<b20BarraTecho){
        b20BarraMeta=Math.min(b20BarraTecho,b20BarraMeta+delta*.0028);
      }
      const faltante=b20BarraMeta-b20BarraValor;
      if(faltante>.05){
        b20BarraValor=Math.min(b20BarraMeta,b20BarraValor+Math.max(.7,faltante*.28));
      }
      b20BarraPintar();
    },100);
  }
  function b20BarraCerrar(){
    b20BarraActiva=false;
    b20BarraNavegando=false;
    if(b20BarraTimer!==null){clearInterval(b20BarraTimer);b20BarraTimer=null;}
    const overlay=document.getElementById('b20CrearOverlay');
    if(overlay)overlay.style.display='none';
  }
'''
admin = one(admin,'  function b20Medir(nombre,valor,fallo){',
            admin_progress_js+'\n  function b20Medir(nombre,valor,fallo){',
            'lógica barra de creación B20')
admin = one(admin,
    "    b20Medir('b20.share_begin',1,false);",
    "    b20Medir('b20.share_begin',1,false);\n    b20BarraIniciar();",
    'inicio de la barra')
admin = one(admin,
    "      b20Medir('b20.share_resolve_ms',performance.now()-b20InicioResolve,false);",
    "      b20Medir('b20.share_resolve_ms',performance.now()-b20InicioResolve,false);\n      b20BarraFase('Destino identificado · calculando ETA...',53,67);",
    'hito destino resuelto')
admin = one(admin,
    "      b20Medir('b20.share_route_ms',performance.now()-b20InicioRuta,false);",
    "      b20Medir('b20.share_route_ms',performance.now()-b20InicioRuta,false);\n      b20BarraFase('Ruta lista · activando geoseguimiento...',78,88);",
    'hito ruta resuelta')
admin = one(admin,
    "      const b20InicioCrear=performance.now();",
    "      b20BarraFase('Generando ID y enlace de seguimiento...',87,94);\n      const b20InicioCrear=performance.now();",
    'hito de creación en servidor')
admin = one(admin,
    "      b20Medir('b20.share_total_ms',performance.now()-b20InicioCompartido,false);",
    "      b20Medir('b20.share_total_ms',performance.now()-b20InicioCompartido,false);\n      b20BarraFase('Abriendo panel, ETA y WhatsApp...',94,97);",
    'preparando panel')
admin = one(admin,
    '  function abrirPanelActivo(s){\n    guardarSeguimientoLocal(s);',
    '''  function abrirPanelActivo(s){
    guardarSeguimientoLocal(s);
    if(b20BarraActiva){
      b20BarraNavegando=true;
      try{
        sessionStorage.setItem('pioca_b20_creacion_handoff',JSON.stringify({
          codigo:String(s.tracking_code||'').trim().toUpperCase(),
          t0:Date.now()-Math.max(0,Math.floor(performance.now()-b20InicioCompartidoGlobal)),
          creado:Date.now()
        }));
      }catch(_){}
    }''',
    'pasaje de progreso entre admin y panel')
# Inicio global se toma justo cuando comienza Google Maps, antes de cualquier RPC.
admin = one(admin,
    "    const b20InicioCompartido=performance.now();",
    "    const b20InicioCompartido=performance.now();\n    b20InicioCompartidoGlobal=b20InicioCompartido;",
    'tiempo origen para handoff')
admin = one(admin,
    '  let b20BarraActiva=false;',
    '  let b20InicioCompartidoGlobal=0;\n  let b20BarraActiva=false;',
    'reloj de medición de comienzo')
# Persistimos domicilio asociado al código, nunca sólo una dirección suelta.
admin = one(admin,
    '''    localStorage.setItem(
      "pioca_tracking_code",
      codigo
    );''',
    '''    localStorage.setItem(
      "pioca_tracking_code",
      codigo
    );
    try{
      const domicilio=String(s.destination_address||'').trim();
      localStorage.setItem('pioca_b20_destino',JSON.stringify({codigo:codigo,direccion:domicilio}));
    }catch(_){}''',
    'guardar domicilio y código pareados')
# Sólo cerrar overlay tras error. En éxito la página cambiará y lo completará index.
admin = one(admin,
    '''    }catch(error){

      mostrarEstado(
        adminEstado,
        "No se pudo crear el seguimiento desde Google Maps.''',
    '''    }catch(error){
      b20BarraCerrar();

      mostrarEstado(
        adminEstado,
        "No se pudo crear el seguimiento desde Google Maps.''',
    'ocultar progreso si falla la creación')
admin = one(admin,
    '''    }finally{

      btnCrear.disabled = false;''',
    '''    }finally{
      if(!b20BarraNavegando)b20BarraCerrar();

      btnCrear.disabled = false;''',
    'limpiar barra al cancelar')
admin_path.write_text(admin,encoding='utf-8')

# Panel activo B20: reordenamos la presentación sin eliminar IDs ni listeners.
index_path=ROOT/'index-b20-diag.html'
index=index_path.read_text('utf-8')

destino_html=r'''
    <section id="piocaDestinoCard" aria-label="Destino del geoseguimiento">
      <div class="piocaDestinoTop"><span class="piocaDestinoIcon" aria-hidden="true">⌖</span><span>DOMICILIO DEL SEGUIMIENTO</span></div>
      <div id="piocaDestinoDireccion">Consultando domicilio...</div>
      <div class="piocaDestinoHint">Destino confirmado al iniciar el seguimiento</div>
    </section>
'''
index=one(index,'    <div id="trackingBox">',destino_html+'\n    <div id="trackingBox">',
          'domicilio destacado en panel activo')
index=one(index,
    '      "Seguimiento: " +',
    '      "ID de seguimiento: " +',
    'identificador explícito sin alterar código')
index=one(index,'      ⛔ FINALIZAR SEGUIMIENTO','      ■ FINALIZAR GEOSEGUIMIENTO',
          'texto de botón finalizar')
index=index.replace('"⛔ FINALIZAR SEGUIMIENTO"','"■ FINALIZAR GEOSEGUIMIENTO"')

panel_css = r'''
<style id="b20-premium-panel">
:root{--p20-azul:#153f88;--p20-acento:#2273c0;--p20-tinta:#172f4b;--p20-muted:#697c91;--p20-borde:#dfe8f1}
body{background:#edf2f8;font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;padding:12px 9px 24px}
.panel{position:relative;max-width:620px;padding:0 18px 22px;border:1px solid #dce5ef;border-radius:23px;box-shadow:0 13px 35px rgba(20,49,84,.09);overflow:hidden;background:#fff}
.panel::before{height:5px;margin:0 -18px 15px;background:linear-gradient(90deg,#123988,#1d79b8,#2da4d1)}
.logoSeguimiento{min-height:98px;margin:0 0 6px;align-items:flex-start;padding-top:7px}
.logoSeguimiento img{width:98px;max-width:29vw;height:auto}
.subtitulo{position:absolute;top:24px;right:17px;min-width:0;max-width:55%;margin:0;padding:10px 13px;border-radius:999px;border:1px solid #c4e4d4;background:#eef9f1;color:#18653c;font-size:12px;font-weight:800;box-shadow:none;line-height:1.2}
.subtitulo::before{content:"";width:9px;height:9px;margin:0 8px 1px 0;background:#21b96b;border:2px solid #fff;box-shadow:0 0 0 2px #bee9d0;vertical-align:middle}
#bloqueGPS{padding-top:0}
#piocaDestinoCard{margin:0 0 12px;padding:17px 17px 16px;background:linear-gradient(145deg,#f5f9ff,#ecf4fc);border:1px solid #cbdceb;border-radius:17px;box-shadow:0 4px 13px rgba(18,65,105,.04)}
.piocaDestinoTop{display:flex;align-items:center;gap:9px;color:#50739b;font-size:10px;font-weight:850;letter-spacing:1.15px}
.piocaDestinoIcon{display:inline-flex;align-items:center;justify-content:center;background:#e0ecfc;color:#135fae;border-radius:50%;width:26px;height:26px;font-size:19px;line-height:1}
#piocaDestinoDireccion{margin:9px 0 6px;font-size:19px;line-height:1.32;font-weight:850;color:#183859;overflow-wrap:anywhere;white-space:normal}
.piocaDestinoHint{font-size:11px;color:#6b839a}
#trackingBox{margin:0 0 12px;padding:11px 14px;background:#f7f9fc;border:1px solid #e0e8f1;border-radius:13px;text-align:left;color:#526982;font-size:11.5px;letter-spacing:.15px;font-weight:750;overflow-wrap:anywhere}
#gpsEstado{position:relative;min-height:63px;padding:18px 91px 18px 37px;margin-bottom:12px;border:1px solid #d8e4ef;border-radius:16px;background:#f2f6fc;color:#435973;text-align:left;font-size:12.5px;font-weight:850;letter-spacing:.05px}
#gpsEstado::before{content:"";left:15px;top:50%;width:10px;height:10px;border-radius:50%;transform:translateY(-50%);background:#a1afbe;box-shadow:0 0 0 4px rgba(141,161,180,.13)}
#gpsEstado::after{content:"";position:absolute;display:block;right:13px;top:7px;width:67px;height:47px;background:url("icono-pioca.png") no-repeat center / contain;filter:drop-shadow(0 2px 3px rgba(25,52,73,.1));pointer-events:none}
#gpsEstado.b20GpsOn{background:linear-gradient(100deg,#edf9f1,#e2f6e9);border-color:#b9dfca;color:#155a35}
#gpsEstado.b20GpsOn::before{background:#1fb968;box-shadow:0 0 0 4px rgba(28,171,99,.15),0 0 8px rgba(28,171,99,.3)}
.datos{background:#f8fafc;border:1px solid #e4ebf1;border-radius:15px;padding:3px 13px;margin-bottom:15px}
.datos > div{grid-template-columns:1fr auto;gap:14px;padding:11px 2px;font-size:12.5px;min-height:42px;border-bottom:1px solid #e4eaf1}
.datos > div:nth-child(-n+3){display:none}
.datos strong{font-weight:680;color:#61758a}
.datos span{color:#193c5c;font-weight:800;font-variant-numeric:tabular-nums;max-width:65%;overflow-wrap:anywhere;text-align:right}
#horaClienteBox{margin:0 0 13px;padding:20px 17px 18px;border:1px solid #cbdced;border-radius:19px;background:linear-gradient(160deg,#f8fbff,#ecf5ff);box-shadow:0 7px 22px rgba(31,81,130,.055)}
.horaClienteTitulo{font-size:11px;letter-spacing:1.15px;color:#5b7da1}
#horaCliente{font-size:46px;line-height:1.1;margin:9px 0 8px;letter-spacing:-1px;color:#155ba4;font-weight:850;font-variant-numeric:tabular-nums}
.horaClienteTexto{color:#58728a;font-size:12px;font-weight:650}
#btnVerSeguimiento{padding:10px 15px;margin-top:15px;min-height:39px;background:#fff;border:1px solid #bdd2e5;color:#154f8c;box-shadow:0 3px 9px rgba(33,77,120,.045);font-size:11px}
#clienteVistaBox{margin-top:0;margin-bottom:12px;padding:12px;border-radius:13px;font-size:11px;letter-spacing:.2px}
#clienteVistaBox.never{border-color:#eee0b7;background:#fffbec;color:#907223}
#btnAbrirMensajes{margin-top:0;min-height:51px;border-radius:14px;border-color:#d6e2ef;background:#f6f9fd;color:#20558e;font-size:12px}
#btnWhatsapp{margin-top:14px;min-height:59px;border-radius:14px;background:linear-gradient(125deg,#137b42,#20a85d);box-shadow:0 7px 20px rgba(27,139,79,.16);font-size:13px;letter-spacing:.1px}
#btnFinalizar{margin-top:13px;min-height:55px;border-radius:14px;background:linear-gradient(120deg,#c92c34,#e33d45);box-shadow:0 6px 16px rgba(200,45,54,.11);font-size:12px;letter-spacing:.15px}
#mensajeClienteBox{border-radius:15px}
@media(max-width:460px){body{padding:8px 8px 22px}.panel{padding:0 13px 19px;border-radius:19px}.panel::before{margin:0 -13px 12px}.logoSeguimiento{min-height:91px}.logoSeguimiento img{width:84px}.subtitulo{top:24px;right:11px;max-width:57%;padding:9px 11px;font-size:11px}#piocaDestinoCard{padding:15px 14px}#piocaDestinoDireccion{font-size:17px}#gpsEstado{padding-right:75px;font-size:12px}#gpsEstado::after{right:10px;width:61px}#horaCliente{font-size:40px}.datos > div{font-size:12px}}
/* Continuidad visual de la barra durante la navegación hacia index. */
#b20PanelCreacion{position:fixed;inset:0;z-index:2147483000;background:rgba(12,32,60,.58);backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);display:none;align-items:center;justify-content:center;padding:16px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
#b20PanelCreacion .b20PCaja{background:linear-gradient(150deg,#fff,#eff6ff);border:1px solid #d8e5f3;border-radius:24px;padding:27px 23px 23px;width:min(100%,420px);text-align:center;box-shadow:0 25px 60px rgba(3,23,55,.3)}
#b20PanelCreacion img{width:93px;height:88px;object-fit:contain;display:block;margin:0 auto 9px}
#b20PanelCreacion .b20PEtiqueta{color:#6483a1;font-size:10px;font-weight:850;letter-spacing:1.3px}
#b20PanelCreacion .b20PTitulo{color:#153d83;font-size:18px;font-weight:850;margin:6px 0 12px}
#b20PanelCreacion .b20PSubtitulo{color:#576e86;font-size:12px;margin-bottom:22px}
#b20PanelCreacion .b20PFila{display:flex;justify-content:space-between;font-size:11px;color:#6d8298;align-items:center;margin-bottom:7px}
#b20PanelCreacion .b20PFila strong{color:#1567b4;font-size:20px;font-variant-numeric:tabular-nums}
#b20PanelCreacion .b20PPista{width:100%;height:11px;border-radius:99px;background:#dfebf6;overflow:hidden}
#b20PanelCreacion .b20PRelleno{background:linear-gradient(90deg,#15459b,#1980d2,#52b6e4);height:100%;width:94%;border-radius:99px;transition:width .16s}
</style>
'''
index=one(index,'</head>',panel_css+'\n</head>','estética premium B20')

handoff_html=r'''
<div id="b20PanelCreacion" role="status" aria-live="polite" aria-label="Preparando seguimiento">
  <div class="b20PCaja">
    <img src="icono-pioca.png" alt="Camioneta piOca">
    <div class="b20PEtiqueta">piOca® · GEOSEGUIMIENTO</div>
    <div class="b20PTitulo">CREANDO SEGUIMIENTO</div>
    <div class="b20PSubtitulo">Preparando ID, ETA y WhatsApp...</div>
    <div class="b20PFila"><span>Activando panel operativo</span><strong id="b20PanelPct">94%</strong></div>
    <div id="b20PanelPista" class="b20PPista" role="progressbar" aria-valuenow="94" aria-valuemin="0" aria-valuemax="100" aria-label="Progreso de creación">
      <div id="b20PanelRelleno" class="b20PRelleno"></div>
    </div>
  </div>
</div>
<script>
/* Traspaso visual: no declarar el 100% hasta que el panel sea operativo. */
(function(){
  let d=null;
  let timer=null;
  let pct=94;
  const box=document.getElementById('b20PanelCreacion');
  try{
    const raw=sessionStorage.getItem('pioca_b20_creacion_handoff');
    if(raw)d=JSON.parse(raw);
    const codigo=new URLSearchParams(location.search).get('tracking')||localStorage.getItem('pioca_tracking_code');
    if(d && String(d.codigo||'').toUpperCase()===String(codigo||'').toUpperCase() &&
      Date.now()-Number(d.creado||0)<120000){
      box.style.display='flex';
      const txt=document.getElementById('b20PanelPct');
      const fill=document.getElementById('b20PanelRelleno');
      const progress=document.getElementById('b20PanelPista');
      timer=setInterval(function(){
        pct=Math.min(98,pct+.5);
        const n=Math.floor(pct);
        txt.textContent=n+'%';fill.style.width=n+'%';
        progress.setAttribute('aria-valuenow',String(n));
      },300);
    }else{d=null;sessionStorage.removeItem('pioca_b20_creacion_handoff');}
  }catch(_){d=null;}
  window.piocaB20PanelListo=function(operativo){
    if(!d)return;
    if(timer!==null){clearInterval(timer);timer=null;}
    if(operativo){
      const n=Date.now()-Number(d.t0||Date.now());
      try{if(window.__piocaDiagMetric)window.__piocaDiagMetric('b20.panel_full_ready_ms',Math.max(0,n),false)}catch(_){}
      document.getElementById('b20PanelPct').textContent='100%';
      document.getElementById('b20PanelRelleno').style.width='100%';
      document.getElementById('b20PanelPista').setAttribute('aria-valuenow','100');
    }else{
      try{if(window.__piocaDiagMetric)window.__piocaDiagMetric('b20.panel_full_ready_failed',1,true)}catch(_){}
    }
    try{sessionStorage.removeItem('pioca_b20_creacion_handoff')}catch(_){}
    d=null;
    setTimeout(function(){box.style.display='none';},operativo?220:0);
  };
})();
</script>
'''
index=one(index,'<body>','<body>\n'+handoff_html,'barra persistente en index')

# Lógica de destino. Consulta directa sólo si falta el valor local; el RLS
# existente de services limita SELECT a la cuenta propietaria.
index_destino_js=r'''
  const b20DestinoTexto=document.getElementById('piocaDestinoDireccion');
  let b20DestinoEnConsulta=false;
  let b20DestinoConsultadoCodigo='';
  function b20AsignarDomicilio(codigo,direccion){
    if(!b20DestinoTexto || !codigo)return;
    const valido=String(direccion||'').trim();
    if(!valido)return;
    b20DestinoTexto.textContent=valido;
    try{localStorage.setItem('pioca_b20_destino',JSON.stringify({codigo:codigo,direccion:valido}))}catch(_){}
  }
  function b20ActualizarDomicilio(s){
    if(!trackingCode || !b20DestinoTexto)return;
    const codigo=String(trackingCode).toUpperCase();
    if(s && typeof s.destination_address==='string' && s.destination_address.trim()){
      b20AsignarDomicilio(codigo,s.destination_address);return;
    }
    try{
      const raw=JSON.parse(localStorage.getItem('pioca_b20_destino')||'null');
      if(raw && raw.codigo===codigo && raw.direccion){
        b20DestinoTexto.textContent=String(raw.direccion);return;
      }
    }catch(_){}
    if(b20DestinoEnConsulta || b20DestinoConsultadoCodigo===codigo)return;
    b20DestinoEnConsulta=true;
    b20DestinoConsultadoCodigo=codigo;
    b20DestinoTexto.textContent='Consultando domicilio...';
    void (async function(){
      try{
        const {data,error}=await supabaseClient.from('services')
          .select('destination_address').eq('tracking_code',codigo).limit(1).maybeSingle();
        if(codigo!==String(trackingCode||'').toUpperCase())return;
        if(!error && data && data.destination_address){
          b20AsignarDomicilio(codigo,data.destination_address);
        }else if(!error){
          b20DestinoTexto.textContent='Sin domicilio asociado a este seguimiento';
        }else{
          b20DestinoTexto.textContent='No se pudo consultar el domicilio';
          b20DestinoConsultadoCodigo='';
        }
      }catch(_){
        b20DestinoTexto.textContent='No se pudo consultar el domicilio';
        b20DestinoConsultadoCodigo='';
      }finally{b20DestinoEnConsulta=false;}
    })();
  }
'''
index=one(index,
    '  function guardarServidorEnLocal(\n    s\n  ){',
    index_destino_js+'\n  function guardarServidorEnLocal(\n    s\n  ){',
    'lógica domicilio robusta en panel')
index=one(index,
    '''    serviceId =
      s.id ||
      serviceId;''',
    '''    serviceId =
      s.id ||
      serviceId;
    b20ActualizarDomicilio(s);''',
    'direccion en cada recuperación activa')
# Limpieza de domicilio al finalizar (evita mostrar otro destino en sucesivos servicios).
index=one(index,
    '''    localStorage.removeItem(
      "pioca_tracking_code"
    );''',
    '''    localStorage.removeItem(
      "pioca_tracking_code"
    );
    localStorage.removeItem('pioca_b20_destino');''',
    'eliminar destino al finalizar')
# Pintado de semáforo coherente con el estado real del GPS.
semaforo_js=r'''
<script id="b20PremiumGpsSemaforo">
(function(){
  function iniciar(){
    const gps=document.getElementById('gpsEstado');
    if(!gps)return;
    function aplicar(){
      const ok=/\bGPS\s+(?:NATIVO\s+)?ACTIVO\b/i.test(gps.textContent||'');
      gps.classList.toggle('b20GpsOn',ok);
    }
    new MutationObserver(aplicar).observe(gps,{subtree:true,childList:true,characterData:true});
    aplicar();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',iniciar,{once:true});
  else iniciar();
})();
</script>
'''
index=one(index,'</body>',semaforo_js+'\n</body>','semaforo GPS sincronizado')
# Cronómetro del proceso completo: sólo al estar ID + ETA + WhatsApp disponibles.
index=one(index,
    '    panelInicializado = true;\n    actualizarBotonesHora();',
    '''    panelInicializado = true;
    actualizarBotonesHora();
    if(window.piocaB20PanelListo){
      const operativo=!!(trackingCode && Number.isFinite(llegadaClienteMs) &&
        btnWhatsapp.style.display==='block' &&
        bloqueGPS.style.display==='block' &&
        usaGpsNativo);
      window.piocaB20PanelListo(operativo);
    }''',
    'medir primer panel con ETA WhatsApp GPS')
index=one(index,
    '''  const acceso =
    await validarAcceso();

  if(''',
    '''  const acceso =
    await validarAcceso();
  if(!acceso && window.piocaB20PanelListo)window.piocaB20PanelListo(false);

  if(''',
    'cerrar progreso si falla panel')
index_path.write_text(index,encoding='utf-8')

assert 'piocaDestinoDireccion' in index
assert 'b20.panel_full_ready_ms' in index
assert 'b20.share_auto_confirm' in admin
assert 'b20CrearOverlay' in admin
assert 'b20BarraIniciar' in admin
assert 'b20.vertex_r67_late_tangent' in (ROOT/'cliente-b20-diag.html').read_text('utf-8')


# B20: misma barra web y sesión coordinada entre GPS nativo y WebView.
p=ROOT/'admin-b20-diag.html'
s=p.read_text('utf-8')
s=one(s,'\n  cargarUltimoTest();\n\n  comprobarSesion();\n\n})();\n</script>\n',"\n  cargarUltimoTest();\n\n  comprobarSesion().catch(function(){\n    document.body.classList.add('modoLogin');\n    loginBox.style.display='block';\n    panelAdmin.style.display='none';\n    ocultarSplash('No se pudo recuperar la sesión · revisá la conexión');\n  });\n\n})();\n</script>\n",'barra 2894')
s=one(s,'      "modoLogin"\n    );\n\n    ocultarSplash();\n  }\n\n  btnContacto.addEventListener(\n','      "modoLogin"\n    );\n\n    ocultarSplash(\'Acceso preparado · ingresá para continuar\');\n  }\n\n  btnContacto.addEventListener(\n','barra 2547')
s=one(s,'  }\n\n  async function comprobarSesion(){\n    const {data} =\n      await supabaseClient.auth.getSession();\n\n',"  }\n\n  async function comprobarSesion(){\n    splashFaseCargaB20('Recuperando sesión segura...',45);\n    const {data} =\n      await supabaseClient.auth.getSession();\n\n",'barra 2530')
s=one(s,'        "error"\n      );\n\n      ocultarSplash();\n    }\n  }\n\n','        "error"\n      );\n\n      ocultarSplash(\'Verificación incompleta · revisá la conexión\');\n    }\n  }\n\n','barra 2515')
s=one(s,'      }\n\n      if(Array.isArray(data) && data.length > 0){\n        abrirPanelActivo(data[0]);\n        return;\n      }\n\n      mostrarFormularioSinSeguimiento();\n\n      ocultarSplash();\n\n    }catch(error){\n\n',"      }\n\n      if(Array.isArray(data) && data.length > 0){\n        // 100% visible antes del cambio a controlador, sin mostrar formulario intermedio.\n        await completarSplashB20('Seguimiento activo · abriendo panel...',false);\n        abrirPanelActivo(data[0]);\n        return;\n      }\n\n      mostrarFormularioSinSeguimiento();\n      ocultarSplash('Panel listo · sin seguimiento activo');\n\n    }catch(error){\n\n",'barra 2469')
s=one(s,'    verificandoBox.textContent =\n      "Verificando si existe un seguimiento activo...";\n\n    // B20: no bloquear el acceso visual a la verificación mientras responde Supabase.\n    ocultarSplash();\n    try{if(window.__piocaDiagMetric)window.__piocaDiagMetric(\'b20.admin_early_display\',1,0)}catch(_){}\n\n    try{\n      const {data,error} =\n        await consultarSeguimientoActivoConRecuperacion();\n','    verificandoBox.textContent =\n      "Verificando si existe un seguimiento activo...";\n\n    // Mantener la ÚNICA barra a la vista hasta conocer el resultado del servidor.\n    splashFaseCargaB20(\'Verificando seguimiento activo...\',82);\n    try{\n      const {data,error} =\n        await consultarSeguimientoActivoConRecuperacion();\n','barra 2456')
s=one(s,'<script>\n(function(){\n\n  const splashPioca =\n    document.getElementById(\n      "splashPioca"\n    );\n\n  const splashInicio =\n    Date.now();\n\n  const SPLASH_MINIMO_MS =\n    1000;\n\n  let splashCerrando =\n    false;\n\n  function ocultarSplash(){\n\n    if(\n      splashCerrando ||\n      !splashPioca\n    ){\n      return;\n    }\n\n    splashCerrando =\n      true;\n\n    const transcurrido =\n      Date.now() -\n      splashInicio;\n\n    const espera =\n      Math.max(\n        0,\n        SPLASH_MINIMO_MS -\n        transcurrido\n      );\n\n    setTimeout(\n      function(){\n\n        /*\n          Primero habilitamos el panel ya resuelto y\n          recién después retiramos el splash.\n          Así nunca queda visible un estado intermedio.\n        */\n        document.body.classList.add(\n          "piocaListo"\n        );\n\n        requestAnimationFrame(\n          function(){\n\n            splashPioca.classList.add(\n              "splashOculto"\n            );\n\n          }\n        );\n\n      },\n      espera\n    );\n  }\n\n  const SUPABASE_URL =\n','<script>\n(function(){\n\n  /*\n    B20 · CARGA WEB UNIFICADA\n    Una sola barra del 0 al 100. El panel no aparece hasta estar resuelto.\n    La pantalla de carga Android nativa sigue siendo independiente (requiere APK).\n  */\n  const splashPioca = document.getElementById("splashPioca");\n  const splashFaseB20 = document.getElementById("b20PanelCargaFase");\n  const splashNumeroB20 = document.getElementById("b20PanelCargaPorcentaje");\n  const splashPistaB20 = document.getElementById("b20PanelCargaPista");\n  const splashRellenoB20 = document.getElementById("b20PanelCargaRelleno");\n  let splashValorB20 = 0;\n  let splashMetaB20 = 18;\n  let splashUltimoMsB20 = performance.now();\n  let splashCerrando = false;\n  let splashCerradoB20 = false;\n  let splashCompletarPromesaB20 = null;\n  let splashResolverB20 = null;\n  let splashMostrarPanelB20 = true;\n  let splashFinEnMsB20 = 0;\n\n  function splashPintarB20(){\n    const valor = Math.max(0,Math.min(100,Math.floor(splashValorB20)));\n    if(splashNumeroB20) splashNumeroB20.textContent = String(valor)+\'%\';\n    if(splashPistaB20) splashPistaB20.setAttribute(\'aria-valuenow\',String(valor));\n    if(splashRellenoB20) splashRellenoB20.style.width = String(valor)+\'%\';\n  }\n  function splashFaseCargaB20(texto, meta){\n    if(splashCerrando || splashCerradoB20)return;\n    if(splashFaseB20)splashFaseB20.textContent=texto;\n    if(Number.isFinite(meta))splashMetaB20=Math.max(splashMetaB20,Math.min(93,meta));\n  }\n  // Un solo contador y una sola barra; sin reset de porcentaje ni splash extra.\n  const splashIntervaloB20 = setInterval(function(){\n    if(splashCerradoB20){clearInterval(splashIntervaloB20);return;}\n    const ahora=performance.now();\n    const delta=Math.min(250,Math.max(0,ahora-splashUltimoMsB20));\n    splashUltimoMsB20=ahora;\n    const restante=Math.max(0,splashMetaB20-splashValorB20);\n    const paso=splashCerrando\n      ? Math.min(restante,Math.max(1.7,restante*0.23)*(delta/65))\n      : Math.min(restante,Math.max(0.14,restante*0.085)*(delta/65));\n    splashValorB20=Math.min(splashMetaB20,splashValorB20+paso);\n    if(splashCerrando && splashMetaB20===100 && splashValorB20>=99.4){\n      splashValorB20=100;\n    }\n    splashPintarB20();\n    if(splashCerrando && splashValorB20===100 && !splashFinEnMsB20){\n      splashFinEnMsB20=ahora;\n    }\n    if(splashFinEnMsB20 && ahora-splashFinEnMsB20>=180){\n      splashCerradoB20=true;\n      clearInterval(splashIntervaloB20);\n      if(splashMostrarPanelB20){\n        // Sólo mostramos el formulario o el login ya listos, nunca un logo aislado.\n        document.body.classList.add(\'piocaListo\');\n        requestAnimationFrame(function(){\n          if(splashPioca)splashPioca.classList.add(\'splashOculto\');\n        });\n      }\n      if(splashResolverB20)splashResolverB20();\n    }\n  },65);\n  splashPintarB20();\n\n  function completarSplashB20(texto,mostrarPanel){\n    if(splashCompletarPromesaB20)return splashCompletarPromesaB20;\n    splashMostrarPanelB20=(mostrarPanel!==false);\n    splashCerrando=true;\n    splashMetaB20=100;\n    if(splashFaseB20)splashFaseB20.textContent=texto||\'Panel preparado\';\n    splashCompletarPromesaB20=new Promise(function(resolve){\n      splashResolverB20=resolve;\n    });\n    return splashCompletarPromesaB20;\n  }\n  function ocultarSplash(texto){\n    return completarSplashB20(texto||\'Panel listo\',true);\n  }\n\n  const SUPABASE_URL =\n','barra 1165')
s=one(s,'\n\n\n<div id="splashPioca">\n\n  <div class="splashContenido">\n\n    <img\n      id="splashLogo"\n      src="logo-pioca.png"\n      alt="piOca"\n    >\n\n    <div id="splashTexto">\n      Cargando…\n    </div>\n\n  </div>\n\n</div>\n\n\n','\n\n\n<div id="splashPioca" role="status" aria-live="polite" aria-label="Cargando panel">\n  <div class="b20CrearTarjeta">\n    <div class="b20CrearEyebrow">piOca® · GEOSEGUIMIENTO</div>\n    <div class="b20CrearTitulo">CARGANDO PANEL</div>\n    <div id="b20PanelCargaFase" class="b20CrearFase">Iniciando aplicación...</div>\n    <div class="b20CrearMeta">\n      <span>Progreso de carga</span>\n      <strong id="b20PanelCargaPorcentaje">0%</strong>\n    </div>\n    <div id="b20PanelCargaPista" class="b20CrearPista" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-label="Progreso de carga del panel">\n      <div id="b20PanelCargaRelleno" class="b20CrearRelleno" style="width:0%"></div>\n    </div>\n    <div class="b20CrearNota">Recuperando sesión y verificando seguimientos</div>\n  </div>\n</div>\n\n\n','barra 943')
s=one(s,'      pointer-events:none;\n    }\n\n    .splashContenido{\n      width:100%;\n      padding:24px;\n      text-align:center;\n    }\n\n    #splashLogo{\n      width:78vw;\n      max-width:390px;\n      height:auto;\n      display:block;\n      margin:0 auto 18px;\n    }\n\n    #splashTexto{\n      font-size:15px;\n      font-weight:800;\n      color:#596673;\n    }\n\n    @media(max-width:460px){\n','      pointer-events:none;\n    }\n\n    /* B20: única carga WEB 0-100%, mismo diseño del creador, sin logo gráfico. */\n    #splashPioca{\n      z-index:2147483001;\n      padding:16px;\n      font-family:system-ui,-apple-system,"Segoe UI",sans-serif;\n    }\n    #splashPioca .b20CrearTarjeta{width:min(100%,420px)}\n    #b20PanelCargaPorcentaje{font-variant-numeric:tabular-nums}\n    @media(prefers-reduced-motion:reduce){\n      #splashPioca{transition:none}\n      #splashPioca .b20CrearRelleno{transition:none}\n    }\n\n    @media(max-width:460px){\n','barra 693')
p.write_text(s,encoding='utf-8')
p=ROOT/'admin-b20-diag.html'
s=p.read_text('utf-8')
s=one(s,"  cargarUltimoTest();\n\n  comprobarSesion().catch(function(){\n    document.body.classList.add('modoLogin');\n    loginBox.style.display='block';\n    panelAdmin.style.display='none';\n    ocultarSplash('No se pudo recuperar la sesión · revisá la conexión');\n  });\n\n})();\n","  cargarUltimoTest();\n\n  comprobarSesion().catch(function(){\n    // La carga puede fallar DESPUÉS de recuperar la sesión, al consultar\n    // el seguimiento o abrir el panel. Ese error no significa logout.\n    // Se conserva getSession y el acceso anterior, sin tocar credenciales.\n    const aviso=document.createElement('div');\n    aviso.id='b20ErrorCargaPanel';\n    aviso.style.cssText='padding:24px 8px;text-align:center;line-height:1.5';\n    const texto=document.createElement('p');\n    texto.textContent='No se pudo completar la carga del panel. Revisá la conexión y reintentá.';\n    const reintentar=document.createElement('button');\n    reintentar.type='button';\n    reintentar.className='btnAzul';\n    reintentar.textContent='REINTENTAR CARGA';\n    reintentar.addEventListener('click',function(){window.location.reload();});\n    aviso.append(texto,reintentar);\n    document.querySelector('.panel').appendChild(aviso);\n    // Un cierre iniciado para navegar puede haber ocultado el contenido.\n    // Retirar sólo el splash, sin cambiar la vista de autenticación.\n    ocultarSplash('Carga pendiente · reintentá con conexión');\n    document.body.classList.add('piocaListo');\n    if(splashPioca)splashPioca.classList.add('splashOculto');\n    try{if(window.__piocaDiagMetric)window.__piocaDiagMetric('b20.panel_load_error',1,1)}catch(_){}\n  });\n\n})();\n",'auth admin 2901')
s=one(s,'        if(cierre.error){\n\n          try{\n            await supabaseClient.auth.refreshSession();\n          }catch(e){}\n\n          await esperar(450);\n',"        if(cierre.error){\n\n          try{\n            if(Number(cierre.error.status)===401 || ['PGRST301','PGRST303'].includes(cierre.error.code))await supabaseClient.auth.refreshSession();\n          }catch(e){}\n\n          await esperar(450);\n",'auth admin 2774')
s=one(s,'      if(intento === 0){\n\n        try{\n          await supabaseClient.auth.refreshSession();\n        }catch(e){}\n\n        await esperar(\n',"      if(intento === 0){\n\n        try{\n          if(Number(error.status)===401 || ['PGRST301','PGRST303'].includes(error.code))await supabaseClient.auth.refreshSession();\n        }catch(e){}\n\n        await esperar(\n",'auth admin 2294')
s=one(s,'  const SUPABASE_KEY =\n    "sb_publishable_htgEX8HiRGAjpCVhPw1gfg_tOPxkJoI";\n\n  const supabaseClient =\n    supabase.createClient(\n      SUPABASE_URL,\n      SUPABASE_KEY\n    );\n\n  const loginBox =\n    document.getElementById("loginBox");\n','  const SUPABASE_KEY =\n    "sb_publishable_htgEX8HiRGAjpCVhPw1gfg_tOPxkJoI";\n\n  // B20: keep the existing SDK session API; coordinate rotation in Android.\n  const b20AuthBridge=window.PiocaNative;\n  const b20CoordinatedAuth=!!(b20AuthBridge &&\n    typeof b20AuthBridge.b20SeedAuthSession===\'function\' &&\n    typeof b20AuthBridge.b20RefreshAuthSession===\'function\');\n  const b20AuthPending=new Map();\n  let b20AuthRequest=0;\n  if(b20CoordinatedAuth){\n    try{\n      const raw=localStorage.getItem(\'sb-apxrmkdegjnblkbyjsbp-auth-token\');\n      if(raw){\n        const latest=b20AuthBridge.b20SeedAuthSession(raw);\n        if(latest)localStorage.setItem(\'sb-apxrmkdegjnblkbyjsbp-auth-token\',latest);\n      }\n    }catch(_){}\n    window.__piocaB20AuthResult=function(id,status,body){\n      const pending=b20AuthPending.get(String(id));\n      if(!pending)return;\n      b20AuthPending.delete(String(id));clearTimeout(pending.timer);\n      pending.resolve(new Response(String(body),{status:Number(status),headers:{\'Content-Type\':\'application/json\'}}));\n    };\n  }\n  async function b20AuthFetch(input,init){\n    let url;\n    try{url=new URL(typeof input===\'string\'?input:input.url,window.location.href);}catch(_){}\n    if(b20CoordinatedAuth && url && url.origin===SUPABASE_URL &&\n      url.pathname===\'/auth/v1/token\' && url.searchParams.get(\'grant_type\')===\'refresh_token\'){\n      const raw=init&&init.body!==undefined?init.body:await input.clone().text();\n      const data=JSON.parse(raw);\n      return new Promise(function(resolve){\n        const id=Date.now().toString(36)+\'-\'+Math.random().toString(36).slice(2)+\'-\'+String(++b20AuthRequest);\n        const timer=setTimeout(function(){\n          b20AuthPending.delete(id);\n          resolve(new Response(\'{"msg":"Session renewal temporarily unavailable"}\',{status:503,headers:{\'Content-Type\':\'application/json\'}}));\n        },25000);\n        b20AuthPending.set(id,{resolve:resolve,timer:timer});\n        try{b20AuthBridge.b20RefreshAuthSession(id,String(data.refresh_token||\'\'));}\n        catch(_){window.__piocaB20AuthResult(id,503,\'{"msg":"Session renewal temporarily unavailable"}\');}\n      });\n    }\n    const response=await window.fetch(input,init);\n    // Only a successful password exchange may replace an equal-age session.\n    if(b20CoordinatedAuth && response.ok && url && url.origin===SUPABASE_URL &&\n      url.pathname===\'/auth/v1/token\' && url.searchParams.get(\'grant_type\')===\'password\' &&\n      typeof b20AuthBridge.b20AcceptAuthSession===\'function\'){\n      try{b20AuthBridge.b20AcceptAuthSession(await response.clone().text());}catch(_){}\n    }\n    return response;\n  }\n\n  const supabaseClient =\n    supabase.createClient(\n      SUPABASE_URL,\n      SUPABASE_KEY,\n      {global:{fetch:b20AuthFetch}}\n    );\n\n  supabaseClient.auth.onAuthStateChange(function(event,session){\n    if(!b20CoordinatedAuth)return;\n    try{\n      if(event===\'SIGNED_OUT\' && typeof b20AuthBridge.b20ClearAuthSession===\'function\')b20AuthBridge.b20ClearAuthSession();\n      else if(session)b20AuthBridge.b20SeedAuthSession(JSON.stringify(session));\n    }catch(_){}\n  });\n\n\n  const loginBox =\n    document.getElementById("loginBox");\n','auth admin 1241')
p.write_text(s,encoding='utf-8')
p=ROOT/'index-b20-diag.html'
s=p.read_text('utf-8')
s=one(s,'  const SUPABASE_KEY =\n    "sb_publishable_htgEX8HiRGAjpCVhPw1gfg_tOPxkJoI";\n\n  const supabaseClient =\n    supabase.createClient(\n      SUPABASE_URL,\n      SUPABASE_KEY\n    );\n\n  /*\n    V9 - ARQUITECTURA DE EMISOR ÚNICO\n','  const SUPABASE_KEY =\n    "sb_publishable_htgEX8HiRGAjpCVhPw1gfg_tOPxkJoI";\n\n  // B20: keep the existing SDK session API; coordinate rotation in Android.\n  const b20AuthBridge=window.PiocaNative;\n  const b20CoordinatedAuth=!!(b20AuthBridge &&\n    typeof b20AuthBridge.b20SeedAuthSession===\'function\' &&\n    typeof b20AuthBridge.b20RefreshAuthSession===\'function\');\n  const b20AuthPending=new Map();\n  let b20AuthRequest=0;\n  if(b20CoordinatedAuth){\n    try{\n      const raw=localStorage.getItem(\'sb-apxrmkdegjnblkbyjsbp-auth-token\');\n      if(raw){\n        const latest=b20AuthBridge.b20SeedAuthSession(raw);\n        if(latest)localStorage.setItem(\'sb-apxrmkdegjnblkbyjsbp-auth-token\',latest);\n      }\n    }catch(_){}\n    window.__piocaB20AuthResult=function(id,status,body){\n      const pending=b20AuthPending.get(String(id));\n      if(!pending)return;\n      b20AuthPending.delete(String(id));clearTimeout(pending.timer);\n      pending.resolve(new Response(String(body),{status:Number(status),headers:{\'Content-Type\':\'application/json\'}}));\n    };\n  }\n  async function b20AuthFetch(input,init){\n    let url;\n    try{url=new URL(typeof input===\'string\'?input:input.url,window.location.href);}catch(_){}\n    if(b20CoordinatedAuth && url && url.origin===SUPABASE_URL &&\n      url.pathname===\'/auth/v1/token\' && url.searchParams.get(\'grant_type\')===\'refresh_token\'){\n      const raw=init&&init.body!==undefined?init.body:await input.clone().text();\n      const data=JSON.parse(raw);\n      return new Promise(function(resolve){\n        const id=Date.now().toString(36)+\'-\'+Math.random().toString(36).slice(2)+\'-\'+String(++b20AuthRequest);\n        const timer=setTimeout(function(){\n          b20AuthPending.delete(id);\n          resolve(new Response(\'{"msg":"Session renewal temporarily unavailable"}\',{status:503,headers:{\'Content-Type\':\'application/json\'}}));\n        },25000);\n        b20AuthPending.set(id,{resolve:resolve,timer:timer});\n        try{b20AuthBridge.b20RefreshAuthSession(id,String(data.refresh_token||\'\'));}\n        catch(_){window.__piocaB20AuthResult(id,503,\'{"msg":"Session renewal temporarily unavailable"}\');}\n      });\n    }\n    const response=await window.fetch(input,init);\n    // Only a successful password exchange may replace an equal-age session.\n    if(b20CoordinatedAuth && response.ok && url && url.origin===SUPABASE_URL &&\n      url.pathname===\'/auth/v1/token\' && url.searchParams.get(\'grant_type\')===\'password\' &&\n      typeof b20AuthBridge.b20AcceptAuthSession===\'function\'){\n      try{b20AuthBridge.b20AcceptAuthSession(await response.clone().text());}catch(_){}\n    }\n    return response;\n  }\n\n  const supabaseClient =\n    supabase.createClient(\n      SUPABASE_URL,\n      SUPABASE_KEY,\n      {global:{fetch:b20AuthFetch}}\n    );\n\n  supabaseClient.auth.onAuthStateChange(function(event,session){\n    if(!b20CoordinatedAuth)return;\n    try{\n      if(event===\'SIGNED_OUT\' && typeof b20AuthBridge.b20ClearAuthSession===\'function\')b20AuthBridge.b20ClearAuthSession();\n      else if(session)b20AuthBridge.b20SeedAuthSession(JSON.stringify(session));\n    }catch(_){}\n  });\n\n\n  /*\n    V9 - ARQUITECTURA DE EMISOR ÚNICO\n','auth index 959')
p.write_text(s,encoding='utf-8')
native_java=native/'app/src/main/java/ar/com/pioca/seguimiento'
(native_java/'B20AuthCoordinator.java').write_text('package ar.com.pioca.seguimiento;\n\nimport android.content.Context;\nimport android.content.SharedPreferences;\nimport android.util.Base64;\nimport org.json.JSONObject;\nimport java.net.HttpURLConnection;\nimport java.net.URL;\nimport java.io.InputStream;\nimport java.nio.charset.StandardCharsets;\n\n/** One renewal owner for WebView and TrackingService. Never logs credentials. */\npublic final class B20AuthCoordinator {\n    private static final String STORE="pioca_b20_auth";\n    private static final String BASE="https://apxrmkdegjnblkbyjsbp.supabase.co";\n    private static final String KEY="sb_publishable_htgEX8HiRGAjpCVhPw1gfg_tOPxkJoI";\n    private B20AuthCoordinator() {}\n    public static final class Result {\n        public final int status;\n        public final JSONObject body;\n        Result(int status, JSONObject body){this.status=status;this.body=body;}\n    }\n    private static SharedPreferences prefs(Context ctx){return ctx.getSharedPreferences(STORE,Context.MODE_PRIVATE);}\n    private static JSONObject read(Context ctx){\n        try{return new JSONObject(prefs(ctx).getString("session","{}"));}\n        catch(Exception ex){return new JSONObject();}\n    }\n    private static JSONObject claims(JSONObject session){\n        try{\n            String[] parts=session.optString("access_token","").split("\\\\.");\n            return new JSONObject(new String(Base64.decode(parts[1],Base64.URL_SAFE|Base64.NO_WRAP|Base64.NO_PADDING),StandardCharsets.UTF_8));\n        }catch(Exception ex){return new JSONObject();}\n    }\n    private static long expiry(JSONObject session){return claims(session).optLong("exp",0);}\n    private static boolean valid(JSONObject session){return !session.optString("access_token","").isEmpty()&&!session.optString("refresh_token","").isEmpty();}\n    private static void save(Context ctx,JSONObject session) throws Exception {\n        // commit is intentional: a process killed after rotation must retain the new pair.\n        if(!prefs(ctx).edit().putString("session",session.toString()).commit())throw new java.io.IOException("AUTH_STORAGE");\n    }\n    public static synchronized String seed(Context ctx,String raw){\n        try{\n            JSONObject incoming=new JSONObject(raw), current=read(ctx);\n            if(!valid(incoming))return "";\n            String newUser=claims(incoming).optString("sub","");\n            String oldUser=claims(current).optString("sub","");\n            if(!valid(current)||!newUser.equals(oldUser)||expiry(incoming)>expiry(current)){\n                save(ctx,incoming);current=incoming;\n            }\n            // Never restore a partial session into supabase-js.\n            return current.optJSONObject("user")!=null?current.toString():"";\n        }catch(Exception ex){return "";}\n    }\n    public static synchronized void acceptLogin(Context ctx,String raw){\n        try{JSONObject session=new JSONObject(raw);if(valid(session)&&session.optJSONObject("user")!=null)save(ctx,session);}catch(Exception ignored){}\n    }\n    public static synchronized void clear(Context ctx){prefs(ctx).edit().remove("session").commit();}\n    public static synchronized Result refresh(Context ctx,String requestedRefresh,String fallbackAccess){\n        HttpURLConnection conn=null;\n        try{\n            JSONObject current=read(ctx);\n            String refresh=current.optString("refresh_token",requestedRefresh);\n            if(refresh.isEmpty())return new Result(400,new JSONObject().put("error_code","refresh_token_not_found").put("msg","Session unavailable"));\n            // A different caller already rotated this pair. Reuse that response.\n            if(!refresh.equals(requestedRefresh)&&expiry(current)>System.currentTimeMillis()/1000+30&&current.optJSONObject("user")!=null){\n                return new Result(200,current);\n            }\n            conn=(HttpURLConnection)new URL(BASE+"/auth/v1/token?grant_type=refresh_token").openConnection();\n            conn.setRequestMethod("POST");conn.setDoOutput(true);\n            conn.setConnectTimeout(10000);conn.setReadTimeout(10000);\n            conn.setRequestProperty("apikey",KEY);conn.setRequestProperty("Content-Type","application/json");\n            byte[] body=new JSONObject().put("refresh_token",refresh).toString().getBytes(StandardCharsets.UTF_8);\n            try(java.io.OutputStream out=conn.getOutputStream()){out.write(body);}\n            int status=conn.getResponseCode();\n            InputStream stream=status>=200&&status<300?conn.getInputStream():conn.getErrorStream();\n            if(stream==null)throw new java.io.IOException("AUTH_RESPONSE");\n            java.io.ByteArrayOutputStream bytes=new java.io.ByteArrayOutputStream();\n            try(InputStream in=stream){byte[] buffer=new byte[4096];int n;while((n=in.read(buffer))!=-1){bytes.write(buffer,0,n);if(bytes.size()>1048576)throw new java.io.IOException("AUTH_SIZE");}}\n            JSONObject result=new JSONObject(new String(bytes.toByteArray(),StandardCharsets.UTF_8));\n            if(status>=200&&status<300){\n                if(!valid(result)||result.optJSONObject("user")==null)throw new java.io.IOException("AUTH_FORMAT");\n                result.put("expires_at",expiry(result));\n                save(ctx,result);\n            }\n            return new Result(status,result);\n        }catch(Exception ex){\n            // A transport/storage failure must remain retryable, never an invalid grant.\n            try{return new Result(503,new JSONObject().put("msg","Session renewal temporarily unavailable"));}\n            catch(Exception ignored){return new Result(503,new JSONObject());}\n        }finally{if(conn!=null)conn.disconnect();}\n    }\n}\n',encoding='utf-8')
p=native_java/'MainActivity.java'
s=p.read_text('utf-8')
s=one(s,'    public class NativeBridge {','    public class NativeBridge {\n'+'        @JavascriptInterface\n        public void b20AcceptAuthSession(String raw) {\n            B20AuthCoordinator.acceptLogin(MainActivity.this,raw);\n        }\n        @JavascriptInterface\n        public String b20SeedAuthSession(String raw) {\n            return B20AuthCoordinator.seed(MainActivity.this,raw);\n        }\n        @JavascriptInterface\n        public void b20ClearAuthSession() {\n            B20AuthCoordinator.clear(MainActivity.this);\n        }\n        @JavascriptInterface\n        public void b20RefreshAuthSession(String requestId,String refreshToken) {\n            // Network work stays off the UI thread and off the WebView JS thread.\n            new Thread(() -> {\n                B20AuthCoordinator.Result result=B20AuthCoordinator.refresh(MainActivity.this,refreshToken,"");\n                final String script="window.__piocaB20AuthResult&&window.__piocaB20AuthResult("\n                    +JSONObject.quote(requestId)+","+result.status+","+JSONObject.quote(result.body.toString())+");";\n                runOnUiThread(() -> {if(web!=null)web.evaluateJavascript(script,null);});\n            },"pioca-b20-auth").start();\n        }\n','puente auth B20')
p.write_text(s,encoding='utf-8')
p=native_java/'TrackingService.java'
s=p.read_text('utf-8')
start=s.index('    private boolean refresh() {')
brace=s.index('{',start)
depth=1
end=brace+1
while depth:
    if s[end]=='{':depth+=1
    elif s[end]=='}':depth-=1
    end+=1
s=s[:start]+'    private boolean refresh() {\n        B20AuthCoordinator.Result result=B20AuthCoordinator.refresh(this,refreshToken,accessToken);\n        if(result.status<200 || result.status>=300)return false;\n        accessToken=result.body.optString("access_token",accessToken);\n        refreshToken=result.body.optString("refresh_token",refreshToken);\n        saveActiveConfig();\n        return !accessToken.isEmpty();\n    }\n'+s[end:]
p.write_text(s,encoding='utf-8')
p=native/'app/build.gradle'
s=p.read_text('utf-8')
s=re.sub(r'\bversionCode\s+20\b','versionCode 21',s,count=1)
s=s.replace('0.20-DIAG-MAPS-VERTICES','0.20.1-DIAG-SESION-COORDINADA')
p.write_text(s,encoding='utf-8')


# Preservar la mejora web aprobada: cartografía a toda velocidad y cámara de salida.
p=ROOT/'cliente-b20-diag.html'
s=p.read_text('utf-8')
s=one(s,'    DISTANCIA_REARME_MARGEN_M:500\n  });\n\n  /*\n    R44/R68 - ENCUADRE INICIAL CAMIONETA + DESTINO\n    Se ejecuta una sola vez cuando ambos pines ya existen.\n',"    DISTANCIA_REARME_MARGEN_M:500\n  });\n\n  /* ==========================================================\n     B20 CARTOGRAFIA TOTAL + CAMARA SALIDA / 2026-11-09\n     La salida visual es INDEPENDIENTE de T0, 50/300 m, expiración y ETA.\n     Sólo nuevas posiciones GPS físicas confirmadas votan una salida.\n     ========================================================== */\n  const CAMARA_SALIDA_B20 = Object.freeze({\n    DISTANCIA_ACTIVACION_M:65,\n    AVANCE_MINIMO_LECTURA_M:4,\n    LECTURAS_ACTIVACION:2,\n    DISTANCIA_REGRESO_M:50,\n    LECTURAS_REGRESO:2,\n    ZOOM_MAXIMO_SALIDA:17,\n    TRANSICION_MS:1350\n  });\n  let modoCamaraSalidaB20=false;\n  let votosSalidaCamaraB20=0;\n  let votosRegresoCamaraB20=0;\n  let distanciaAnteriorCamaraB20=null;\n  let camaraSalidaRafB20=null;\n\n  function cancelarTransicionCamaraSalidaB20(){\n    if(camaraSalidaRafB20!==null){\n      cancelAnimationFrame(camaraSalidaRafB20);\n      camaraSalidaRafB20=null;\n    }\n    try{\n      if(mapa && mapa._map){\n        mapa._map.setOptions({isFractionalZoomEnabled:false});\n      }\n    }catch(_){}\n  }\n\n  /* Una sola animación de cámara, recalculada alrededor del pin REAL visible.\n     El nivel de zoom no interviene en el map matching R67: sólo escala el mapa. */\n  function iniciarTransicionCamaraSalidaB20(){\n    cancelarTransicionCamaraSalidaB20();\n    if(!mapa || !marcador || !mapa._map){return;}\n    const gm=mapa._map;\n    const inicioZoom=Number(gm.getZoom());\n    if(!Number.isFinite(inicioZoom)){return;}\n    const finalZoom=Math.min(inicioZoom,CAMARA_SALIDA_B20.ZOOM_MAXIMO_SALIDA);\n    const inicioMs=performance.now();\n    let ultimoZoomOrdenado=inicioZoom;\n    let ultimoPintadoMs=0;\n    try{gm.setOptions({isFractionalZoomEnabled:true});}catch(_){}\n    function fotograma(t){\n      if(!modoCamaraSalidaB20 || !mapa || !marcador){\n        cancelarTransicionCamaraSalidaB20();\n        return;\n      }\n      if(t-ultimoPintadoMs<28){\n        camaraSalidaRafB20=requestAnimationFrame(fotograma);\n        return;\n      }\n      ultimoPintadoMs=t;\n      try{\n        const zoomLeido=Number(gm.getZoom());\n        /* Si el cliente modificó el zoom, su gesto tiene prioridad. */\n        if(Number.isFinite(zoomLeido) &&\n           Math.abs(zoomLeido-ultimoZoomOrdenado)>0.65){\n          cancelarTransicionCamaraSalidaB20();\n          return;\n        }\n        const tNormal=Math.max(0,Math.min(1,(t-inicioMs)/CAMARA_SALIDA_B20.TRANSICION_MS));\n        const ease=tNormal*tNormal*(3-2*tNormal);\n        const z=inicioZoom+(finalZoom-inicioZoom)*ease;\n        const pin=marcador.getLatLng();\n        const altoMapa=Number(mapa.getSize().y)||0;\n        const anchoMapa=Number(mapa.getSize().x)||0;\n        const altoPanel=piocaTrayectoPanel\n          ? piocaTrayectoPanel.getBoundingClientRect().height : 0;\n        const offsetY=Math.max(0,Math.min(altoPanel*0.50,altoMapa*0.32));\n        const rumbo=Number(typeof gm.getHeading==='function'?gm.getHeading():0)||0;\n        const centro=calcularCentroPuntoEnPantallaConRumbo(\n          Number(pin.lat),Number(pin.lng),z,anchoMapa*0.5,\n          altoMapa*0.5-offsetY,rumbo\n        );\n        if(centro){\n          if(typeof gm.moveCamera==='function'){\n            gm.moveCamera({center:{lat:Number(centro.lat),lng:Number(centro.lng)},zoom:z});\n          }else{\n            mapa.setView([Number(centro.lat),Number(centro.lng)],z);\n          }\n        }\n        ultimoZoomOrdenado=z;\n        if(tNormal<1){\n          camaraSalidaRafB20=requestAnimationFrame(fotograma);\n        }else{\n          camaraSalidaRafB20=null;\n          try{gm.setOptions({isFractionalZoomEnabled:false});}catch(_){}\n        }\n      }catch(_){cancelarTransicionCamaraSalidaB20();}\n    }\n    camaraSalidaRafB20=requestAnimationFrame(fotograma);\n  }\n\n  function actualizarModoCamaraSalidaB20(distancia, llegoAntes, llegoAhora){\n    if(!Number.isFinite(distancia)){return;}\n    if(modoCamaraSalidaB20){\n      if(distancia<=CAMARA_SALIDA_B20.DISTANCIA_REGRESO_M){\n        votosRegresoCamaraB20++;\n        if(votosRegresoCamaraB20>=CAMARA_SALIDA_B20.LECTURAS_REGRESO){\n          modoCamaraSalidaB20=false;\n          votosRegresoCamaraB20=0;\n          votosSalidaCamaraB20=0;\n          cancelarTransicionCamaraSalidaB20();\n          tramoZoomEtaActual=null;\n          encuadreProximidadEnclavado=true;\n          lecturasSalidaEncuadreProximidad=0;\n          ultimaLecturaSalidaEncuadreEvaluada=null;\n        }\n      }else{\n        votosRegresoCamaraB20=0;\n      }\n    }else if(llegoAntes || llegoAhora){\n      if(distancia>=CAMARA_SALIDA_B20.DISTANCIA_ACTIVACION_M &&\n         Number.isFinite(distanciaAnteriorCamaraB20) &&\n         distancia-distanciaAnteriorCamaraB20>=CAMARA_SALIDA_B20.AVANCE_MINIMO_LECTURA_M){\n        votosSalidaCamaraB20++;\n      }else{\n        votosSalidaCamaraB20=0;\n      }\n      if(votosSalidaCamaraB20>=CAMARA_SALIDA_B20.LECTURAS_ACTIVACION){\n        modoCamaraSalidaB20=true;\n        votosSalidaCamaraB20=0;\n        /* Desarmar inmediatamente el encuadre dual anterior. */\n        encuadreProximidadEnclavado=false;\n        lecturasSalidaEncuadreProximidad=0;\n        ultimaLecturaSalidaEncuadreEvaluada=null;\n        desactivarEncuadreProximidad();\n        tramoZoomEtaActual='salida-b20';\n        iniciarTransicionCamaraSalidaB20();\n      }\n    }\n    distanciaAnteriorCamaraB20=distancia;\n  }\n\n  function reiniciarCamaraSalidaB20(){\n    modoCamaraSalidaB20=false;\n    votosSalidaCamaraB20=0;\n    votosRegresoCamaraB20=0;\n    distanciaAnteriorCamaraB20=null;\n    cancelarTransicionCamaraSalidaB20();\n  }\n\n  /*\n    R44/R68 - ENCUADRE INICIAL CAMIONETA + DESTINO\n    Se ejecuta una sola vez cuando ambos pines ya existen.\n",'cartografia total 0')
s=one(s,'\n\n  function reiniciarEnclavamientoEncuadreProximidad(){\n    encuadreProximidadEnclavado = false;\n    lecturasSalidaEncuadreProximidad = 0;\n    ultimaLecturaSalidaEncuadreEvaluada = null;\n','\n\n  function reiniciarEnclavamientoEncuadreProximidad(){\n    reiniciarCamaraSalidaB20();\n    encuadreProximidadEnclavado = false;\n    lecturasSalidaEncuadreProximidad = 0;\n    ultimaLecturaSalidaEncuadreEvaluada = null;\n','cartografia total 1')
s=one(s,'    faltanMin\n  ){\n\n    const c =\n      ALGORITMO_ENCUADRE_PROXIMIDAD;\n\n','    faltanMin\n  ){\n\n    if(modoCamaraSalidaB20){return false;}\n\n    const c =\n      ALGORITMO_ENCUADRE_PROXIMIDAD;\n\n','cartografia total 2')
s=one(s,'    sinAnimacionReanudacion\n  ){\n\n    if(\n      encuadreInicialMapaActivo ||\n      !mapa ||\n','    sinAnimacionReanudacion\n  ){\n\n    if(modoCamaraSalidaB20){return false;}\n\n    if(\n      encuadreInicialMapaActivo ||\n      !mapa ||\n','cartografia total 3')
s=one(s,'    faltanMin\n  ){\n\n    /*\n      Mientras se muestra el encuadre inicial camioneta + destino,\n      ninguna otra cámara interviene.\n','    faltanMin\n  ){\n\n    /* La ETA vencida no recupera el zoom del domicilio durante una salida. */\n    if(modoCamaraSalidaB20){return;}\n\n    /*\n      Mientras se muestra el encuadre inicial camioneta + destino,\n      ninguna otra cámara interviene.\n','cartografia total 4')
s=one(s,'\n    ultimaDistanciaProximidad =\n      distanciaAlDomicilio;\n\n    /*\n      Para el cierre local usamos la antigüedad REAL del paquete GPS cuando\n','\n    ultimaDistanciaProximidad =\n      distanciaAlDomicilio;\n    const llegadaAntesParaCamaraB20=llegadaFisicaConfirmada;\n\n    /*\n      Para el cierre local usamos la antigüedad REAL del paquete GPS cuando\n','cartografia total 5')
s=one(s,'    zonaCercaConfirmada =\n      siguiente.zonaCerca;\n\n    /*\n      Persistimos TODA lectura física aceptada. Así una salida >300 m que\n      todavía no llegó a tres comprobaciones tampoco deja localStorage con\n','    zonaCercaConfirmada =\n      siguiente.zonaCerca;\n\n    actualizarModoCamaraSalidaB20(\n      distanciaAlDomicilio,\n      llegadaAntesParaCamaraB20,\n      llegadaFisicaConfirmada\n    );\n\n    /*\n      Persistimos TODA lectura física aceptada. Así una salida >300 m que\n      todavía no llegó a tres comprobaciones tampoco deja localStorage con\n','cartografia total 6')
s=one(s,'\n     PRINCIPIO:\n     - R65 permanece como autoridad física completa.\n     - R67 sólo corrige la POSICIÓN VISUAL del pin por debajo de 40 km/h.\n     - La geometría llega desde /__r67/sector en pequeños sectores.\n     - Cloudflare cachea cada sector; el navegador también puede reutilizarlo.\n     - Si un sector no está disponible, fallback inmediato a R65.\n','\n     PRINCIPIO:\n     - R65 permanece como autoridad física completa.\n     - R67 corrige la POSICIÓN VISUAL a CUALQUIER velocidad si hay vía confiable.\n     - La geometría llega desde /__r67/sector en pequeños sectores.\n     - Cloudflare cachea cada sector; el navegador también puede reutilizarlo.\n     - Si un sector no está disponible, fallback inmediato a R65.\n','cartografia total 7')
s=one(s,'    PASO_LAT_GRADOS:0.025,\n    PASO_LON_GRADOS:0.030,\n\n    VELOCIDAD_MAX_KMH:39.9,\n    VELOCIDAD_MIN_CAMBIO_SEGMENTO_KMH:2.5,\n    DISTANCIA_MAX_BASE_M:22,\n    DISTANCIA_MAX_CONTINUIDAD_M:30,\n','    PASO_LAT_GRADOS:0.025,\n    PASO_LON_GRADOS:0.030,\n\n    /* Sin límite por velocidad: prevalece la geometría vial confiable. */\n    VELOCIDAD_MIN_CAMBIO_SEGMENTO_KMH:2.5,\n    DISTANCIA_MAX_BASE_M:22,\n    DISTANCIA_MAX_CONTINUIDAD_M:30,\n','cartografia total 8')
s=one(s,'    const candidatosLocales = r67CandidatosIndice(lat,lon);\n\n    for(const seg of candidatosLocales){\n      if(Math.abs(lat-seg.latMid) > 0.00042){ continue; }\n      if(Math.abs(lon-seg.lonMid) > 0.00055){ continue; }\n\n      const proy = r67ProyectarSobreSegmento(lat,lon,seg);\n      if(!proy || !Number.isFinite(proy.distancia) || proy.distancia > distanciaMax){\n        continue;\n      }\n\n      let score = proy.distancia;\n\n      if(Number.isFinite(rumboMov)){\n','    const candidatosLocales = r67CandidatosIndice(lat,lon);\n\n    for(const seg of candidatosLocales){\n      /* B20 CARTOGRAFIA TOTAL: no eliminar una vía larga por su punto medio.\n         El índice espacial ya seleccionó candidatos; se verifica el tramo completo. */\n      const margenLat=0.00030, margenLon=0.00035;\n      if(lat < Math.min(seg.lat1,seg.lat2)-margenLat ||\n         lat > Math.max(seg.lat1,seg.lat2)+margenLat ||\n         lon < Math.min(seg.lon1,seg.lon2)-margenLon ||\n         lon > Math.max(seg.lon1,seg.lon2)+margenLon){ continue; }\n\n      const proy = r67ProyectarSobreSegmento(lat,lon,seg);\n      if(!proy || !Number.isFinite(proy.distancia) || proy.distancia > distanciaMax){\n        continue;\n      }\n\n      /* A velocidad alta, una calle paralela/desconectada no puede\n         desplazar el pin si contradice fuertemente el rumbo confirmado. */\n      if(Number.isFinite(rumboMov) && Number.isFinite(velocidadKmh) &&\n         velocidadKmh >= 40){\n        const difAlta=r67DiferenciaRumboEje(rumboMov,seg.rumbo);\n        const conectada=r67SegmentoActual &&\n          r67SegmentosConectados(seg,r67SegmentoActual);\n        if(difAlta > (conectada ? 72 : 48)){ continue; }\n      }\n\n      let score = proy.distancia;\n\n      if(Number.isFinite(rumboMov)){\n','cartografia total 9')
s=one(s,'      R67_MAP_MATCH.ACTIVO !== true ||\n      !Number.isFinite(latGps) ||\n      !Number.isFinite(lonGps) ||\n      !Number.isFinite(velocidadKmh) ||\n      velocidadKmh >= R67_MAP_MATCH.VELOCIDAD_MAX_KMH ||\n      r67SegmentosViales.length === 0\n    ){\n      return {\n','      R67_MAP_MATCH.ACTIVO !== true ||\n      !Number.isFinite(latGps) ||\n      !Number.isFinite(lonGps) ||\n      r67SegmentosViales.length === 0\n    ){\n      return {\n','cartografia total 10')
s=one(s,'      velocidadKmh\n    );\n\n    if(!confirmado){\n      return {\n        lat:latBase,\n        lon:lonBase,\n','      velocidadKmh\n    );\n\n    if(!confirmado ||\n       /* La cartografía tiene prioridad, pero jamás un salto lateral\n          excesivo hacia una vía paralela o una rampa errónea. */\n       (Number.isFinite(latBase) && Number.isFinite(lonBase) &&\n        distanciaMetros(latBase,lonBase,confirmado.lat,confirmado.lon) > 30)){\n      return {\n        lat:latBase,\n        lon:lonBase,\n','cartografia total 11')
s=one(s,'    return {\n      lat:confirmado.lat,\n      lon:confirmado.lon,\n      filtrado:filtradoBase === true,\n      ajustadoR67:true,\n      distanciaAjusteM:confirmado.distancia,\n      wayId:confirmado.segmento && confirmado.segmento.wayId\n','    return {\n      lat:confirmado.lat,\n      lon:confirmado.lon,\n      filtrado:false,\n      ajustadoR67:true,\n      distanciaAjusteM:confirmado.distancia,\n      wayId:confirmado.segmento && confirmado.segmento.wayId\n','cartografia total 12')
s=one(s,'    zoomDestino\n  ){\n\n    if(\n      !mapa ||\n      !marcador ||\n','    zoomDestino\n  ){\n\n    if(modoCamaraSalidaB20){cancelarTransicionCamaraSalidaB20();}\n\n    if(\n      !mapa ||\n      !marcador ||\n','cartografia total 13')
s=one(s,'      opciones ||\n      {};\n\n    /*\n      R53:\n      las animaciones actuales siguen llamando a esta misma función.\n','      opciones ||\n      {};\n\n    /* Una transición rAF gobierna sola la cámara durante el alejamiento. */\n    if(modoCamaraSalidaB20 && camaraSalidaRafB20!==null){return;}\n\n    /*\n      R53:\n      las animaciones actuales siguen llamando a esta misma función.\n','cartografia total 14')
s=one(s,'      El punto bruto sigue alimentando velocidad y memoria real.\n      Sólo el destino VISUAL puede ser estabilizado a alta velocidad.\n\n      R67 añade después un map matching VISUAL (<40 km/h) contra una\n      geometría vial independiente. La física R65 continúa usando lat/lon.\n    */\n    r67AsegurarGeometriaCerca(lat,lon);\n','      El punto bruto sigue alimentando velocidad y memoria real.\n      Sólo el destino VISUAL puede ser estabilizado a alta velocidad.\n\n      R67 añade después un map matching VISUAL a todo régimen contra una\n      geometría vial independiente. La física R65 continúa usando lat/lon.\n    */\n    r67AsegurarGeometriaCerca(lat,lon);\n','cartografia total 15')
assert 'VELOCIDAD_MAX_KMH:39.9' not in s
assert 'CAMARA_SALIDA_B20' in s
p.write_text(s,encoding='utf-8')


# Preservar ajustes publicados del panel posteriores a la base B20.
p=ROOT/'index-b20-diag.html'
s=p.read_text('utf-8')
s=one(s,'#btnFinalizar{margin-top:13px;min-height:55px;border-radius:14px;background:linear-gradient(120deg,#c92c34,#e33d45);box-shadow:0 6px 16px rgba(200,45,54,.11);font-size:12px;letter-spacing:.15px}\n#mensajeClienteBox{border-radius:15px}\n@media(max-width:460px){body{padding:8px 8px 22px}.panel{padding:0 13px 19px;border-radius:19px}.panel::before{margin:0 -13px 12px}.logoSeguimiento{min-height:91px}.logoSeguimiento img{width:84px}.subtitulo{top:24px;right:11px;max-width:57%;padding:9px 11px;font-size:11px}#piocaDestinoCard{padding:15px 14px}#piocaDestinoDireccion{font-size:17px}#gpsEstado{padding-right:75px;font-size:12px}#gpsEstado::after{right:10px;width:61px}#horaCliente{font-size:40px}.datos > div{font-size:12px}}\n/* Continuidad visual de la barra durante la navegación hacia index. */\n#b20PanelCreacion{position:fixed;inset:0;z-index:2147483000;background:rgba(12,32,60,.58);backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);display:none;align-items:center;justify-content:center;padding:16px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}\n#b20PanelCreacion .b20PCaja{background:linear-gradient(150deg,#fff,#eff6ff);border:1px solid #d8e5f3;border-radius:24px;padding:27px 23px 23px;width:min(100%,420px);text-align:center;box-shadow:0 25px 60px rgba(3,23,55,.3)}\n','#btnFinalizar{margin-top:13px;min-height:55px;border-radius:14px;background:linear-gradient(120deg,#c92c34,#e33d45);box-shadow:0 6px 16px rgba(200,45,54,.11);font-size:12px;letter-spacing:.15px}\n#mensajeClienteBox{border-radius:15px}\n@media(max-width:460px){body{padding:8px 8px 22px}.panel{padding:0 13px 19px;border-radius:19px}.panel::before{margin:0 -13px 12px}.logoSeguimiento{min-height:91px}.logoSeguimiento img{width:84px}.subtitulo{top:24px;right:11px;max-width:57%;padding:9px 11px;font-size:11px}#piocaDestinoCard{padding:15px 14px}#piocaDestinoDireccion{font-size:17px}#gpsEstado{padding-right:75px;font-size:12px}#gpsEstado::after{right:10px;width:61px}#horaCliente{font-size:40px}.datos > div{font-size:12px}}\n\n/* B20 DIAG · AJUSTE VISUAL GPS / DATOS (revisión sobre HTML completo) */\n#gpsEstado{\n  position:relative;\n  display:flex;\n  align-items:center;\n  min-height:65px;\n  margin-bottom:12px;\n  padding:15px 78px 15px 17px;\n  font-size:12.5px;\n  line-height:1.3;\n  white-space:nowrap;\n}\n/* Eliminar el punto izquierdo y la foto de la camioneta; semáforo a la derecha. */\n#gpsEstado::before{content:none;display:none}\n#gpsEstado::after{\n  content:"";\n  position:absolute;\n  display:block;\n  top:50%;\n  right:18px;\n  width:43px;\n  height:43px;\n  transform:translateY(-50%);\n  border:5px solid #f2f6fc;\n  border-radius:50%;\n  box-sizing:border-box;\n  background:#a3b2c1;\n  background-image:none;\n  box-shadow:0 0 0 2px rgba(80,105,133,.18);\n  filter:none;\n  pointer-events:none;\n}\n#gpsEstado.b20GpsOn::after{\n  background:#18bf5d;\n  border-color:#def9e7;\n  animation:b20GpsSemaforoPulso 1.45s ease-in-out infinite;\n}\n@keyframes b20GpsSemaforoPulso{\n  0%,100%{opacity:1;box-shadow:0 0 0 2px rgba(23,174,85,.26),0 0 0 4px rgba(20,182,91,.12)}\n  50%{opacity:.77;box-shadow:0 0 0 3px rgba(23,174,85,.22),0 0 0 13px rgba(24,190,89,.15)}\n}\n/* Datos de una sola línea: el valor puede ocupar el resto del ancho. */\n.datos{padding:3px 11px;margin-bottom:12px}\n.datos > div{\n  grid-template-columns:max-content minmax(0,1fr);\n  gap:9px;\n  padding:9px 0;\n  min-height:38px;\n}\n.datos > div:nth-child(-n+3){display:none}\n.datos strong{font-size:11.5px;white-space:nowrap;font-weight:750}\n.datos span{\n  font-size:11.5px;\n  max-width:none;\n  min-width:0;\n  white-space:nowrap;\n  overflow-wrap:normal;\n  text-align:right;\n  letter-spacing:-.12px;\n}\n@media(max-width:390px){\n  #gpsEstado{min-height:61px;padding-right:70px;font-size:11.5px}\n  #gpsEstado::after{right:14px;width:38px;height:38px}\n  .datos{padding:3px 8px}\n  .datos > div{gap:5px;padding:8px 0;min-height:36px}\n  .datos strong,.datos span{font-size:10.5px;letter-spacing:-.18px}\n}\n@media(prefers-reduced-motion:reduce){#gpsEstado.b20GpsOn::after{animation:none}}\n\n/* Continuidad visual de la barra durante la navegación hacia index. */\n#b20PanelCreacion{position:fixed;inset:0;z-index:2147483000;background:rgba(12,32,60,.58);backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);display:none;align-items:center;justify-content:center;padding:16px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}\n#b20PanelCreacion .b20PCaja{background:linear-gradient(150deg,#fff,#eff6ff);border:1px solid #d8e5f3;border-radius:24px;padding:27px 23px 23px;width:min(100%,420px);text-align:center;box-shadow:0 25px 60px rgba(3,23,55,.3)}\n','panel publicado 1-0')
s=one(s,'      segundos <= 5\n    ){\n      enviosTxt.textContent =\n        "🟢 REPORTANDO · hace " +\n        segundos +\n        " s";\n\n','      segundos <= 5\n    ){\n      enviosTxt.textContent =\n        "REPORTANDO · hace " +\n        segundos +\n        " s";\n\n','panel publicado 1-1')
s=one(s,'      segundos <= 10\n    ){\n      enviosTxt.textContent =\n        "🟡 DEMORA · hace " +\n        segundos +\n        " s";\n\n','      segundos <= 10\n    ){\n      enviosTxt.textContent =\n        "DEMORA · hace " +\n        segundos +\n        " s";\n\n','panel publicado 1-2')
s=one(s,'    }\n\n    enviosTxt.textContent =\n      "🔴 SIN REPORTE · hace " +\n      segundos +\n      " s";\n\n','    }\n\n    enviosTxt.textContent =\n      "SIN REPORTE · hace " +\n      segundos +\n      " s";\n\n','panel publicado 1-3')
s=one(s,'        null;\n\n      estado.textContent =\n        "🟢 GPS NATIVO ACTIVO";\n\n      estado.style.background =\n        "#dff5e1";\n','        null;\n\n      estado.textContent =\n        "GPS NATIVO ACTIVO";\n\n      estado.style.background =\n        "#dff5e1";\n','panel publicado 1-4')
s=one(s,'            );\n\n          estado.textContent =\n            "🟢 GPS ACTIVO";\n\n          estado.style.background =\n            "#dff5e1";\n','            );\n\n          estado.textContent =\n            "GPS ACTIVO";\n\n          estado.style.background =\n            "#dff5e1";\n','panel publicado 1-5')
s=one(s,'          }\n\n          estado.textContent =\n            "🟢 GPS NATIVO ACTIVO";\n\n          estado.style.background =\n            "#dff5e1";\n','          }\n\n          estado.textContent =\n            "GPS NATIVO ACTIVO";\n\n          estado.style.background =\n            "#dff5e1";\n','panel publicado 1-6')
s=one(s,'}\n@media(prefers-reduced-motion:reduce){#gpsEstado.b20GpsOn::after{animation:none}}\n\n/* Continuidad visual de la barra durante la navegación hacia index. */\n#b20PanelCreacion{position:fixed;inset:0;z-index:2147483000;background:rgba(12,32,60,.58);backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);display:none;align-items:center;justify-content:center;padding:16px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}\n#b20PanelCreacion .b20PCaja{background:linear-gradient(150deg,#fff,#eff6ff);border:1px solid #d8e5f3;border-radius:24px;padding:27px 23px 23px;width:min(100%,420px);text-align:center;box-shadow:0 25px 60px rgba(3,23,55,.3)}\n#b20PanelCreacion img{width:93px;height:88px;object-fit:contain;display:block;margin:0 auto 9px}\n#b20PanelCreacion .b20PEtiqueta{color:#6483a1;font-size:10px;font-weight:850;letter-spacing:1.3px}\n#b20PanelCreacion .b20PTitulo{color:#153d83;font-size:18px;font-weight:850;margin:6px 0 12px}\n#b20PanelCreacion .b20PSubtitulo{color:#576e86;font-size:12px;margin-bottom:22px}\n#b20PanelCreacion .b20PFila{display:flex;justify-content:space-between;font-size:11px;color:#6d8298;align-items:center;margin-bottom:7px}\n#b20PanelCreacion .b20PFila strong{color:#1567b4;font-size:20px;font-variant-numeric:tabular-nums}\n#b20PanelCreacion .b20PPista{width:100%;height:11px;border-radius:99px;background:#dfebf6;overflow:hidden}\n#b20PanelCreacion .b20PRelleno{background:linear-gradient(90deg,#15459b,#1980d2,#52b6e4);height:100%;width:94%;border-radius:99px;transition:width .16s}\n</style>\n\n</head>\n\n<body>\n\n<div id="b20PanelCreacion" role="status" aria-live="polite" aria-label="Preparando seguimiento">\n  <div class="b20PCaja">\n    <img src="icono-pioca.png" alt="Camioneta piOca">\n    <div class="b20PEtiqueta">piOca® · GEOSEGUIMIENTO</div>\n    <div class="b20PTitulo">CREANDO SEGUIMIENTO</div>\n    <div class="b20PSubtitulo">Preparando ID, ETA y WhatsApp...</div>\n    <div class="b20PFila"><span>Activando panel operativo</span><strong id="b20PanelPct">94%</strong></div>\n    <div id="b20PanelPista" class="b20PPista" role="progressbar" aria-valuenow="94" aria-valuemin="0" aria-valuemax="100" aria-label="Progreso de creación">\n      <div id="b20PanelRelleno" class="b20PRelleno"></div>\n    </div>\n  </div>\n</div>\n<script>\n/* Traspaso visual: no declarar el 100% hasta que el panel sea operativo. */\n(function(){\n  let d=null;\n  let timer=null;\n  let pct=94;\n  const box=document.getElementById(\'b20PanelCreacion\');\n  try{\n    const raw=sessionStorage.getItem(\'pioca_b20_creacion_handoff\');\n    if(raw)d=JSON.parse(raw);\n    const codigo=new URLSearchParams(location.search).get(\'tracking\')||localStorage.getItem(\'pioca_tracking_code\');\n    if(d && String(d.codigo||\'\').toUpperCase()===String(codigo||\'\').toUpperCase() &&\n      Date.now()-Number(d.creado||0)<120000){\n      box.style.display=\'flex\';\n      const txt=document.getElementById(\'b20PanelPct\');\n      const fill=document.getElementById(\'b20PanelRelleno\');\n      const progress=document.getElementById(\'b20PanelPista\');\n      timer=setInterval(function(){\n        pct=Math.min(98,pct+.5);\n        const n=Math.floor(pct);\n        txt.textContent=n+\'%\';fill.style.width=n+\'%\';\n        progress.setAttribute(\'aria-valuenow\',String(n));\n      },300);\n    }else{d=null;sessionStorage.removeItem(\'pioca_b20_creacion_handoff\');}\n  }catch(_){d=null;}\n  window.piocaB20PanelListo=function(operativo){\n    if(!d)return;\n    if(timer!==null){clearInterval(timer);timer=null;}\n    if(operativo){\n      const n=Date.now()-Number(d.t0||Date.now());\n      try{if(window.__piocaDiagMetric)window.__piocaDiagMetric(\'b20.panel_full_ready_ms\',Math.max(0,n),false)}catch(_){}\n      document.getElementById(\'b20PanelPct\').textContent=\'100%\';\n      document.getElementById(\'b20PanelRelleno\').style.width=\'100%\';\n      document.getElementById(\'b20PanelPista\').setAttribute(\'aria-valuenow\',\'100\');\n    }else{\n      try{if(window.__piocaDiagMetric)window.__piocaDiagMetric(\'b20.panel_full_ready_failed\',1,true)}catch(_){}\n    }\n    try{sessionStorage.removeItem(\'pioca_b20_creacion_handoff\')}catch(_){}\n    d=null;\n    setTimeout(function(){box.style.display=\'none\';},operativo?220:0);\n  };\n})();\n</script>\n\n\n<div class="panel">\n\n  <div class="logoSeguimiento">\n','}\n@media(prefers-reduced-motion:reduce){#gpsEstado.b20GpsOn::after{animation:none}}\n\n/* B20: única barra de creación en admin; sin barra duplicada en index. */\n</style>\n\n</head>\n\n<body>\n\n<script>\n/* B20: el progreso se muestra una sola vez, en admin.\n   Se conserva la caja negra de tiempo total hasta panel operativo. */\n(function(){\n  let handoff=null;\n  try{\n    const raw=sessionStorage.getItem(\'pioca_b20_creacion_handoff\');\n    if(raw)handoff=JSON.parse(raw);\n    const codigo=new URLSearchParams(location.search).get(\'tracking\')||\n      localStorage.getItem(\'pioca_tracking_code\');\n    if(!handoff ||\n      String(handoff.codigo||\'\').toUpperCase()!==String(codigo||\'\').toUpperCase() ||\n      Date.now()-Number(handoff.creado||0)>=120000){\n      handoff=null;\n      sessionStorage.removeItem(\'pioca_b20_creacion_handoff\');\n    }\n  }catch(_){\n    handoff=null;\n    try{sessionStorage.removeItem(\'pioca_b20_creacion_handoff\')}catch(__){}\n  }\n  window.piocaB20PanelListo=function(operativo){\n    if(!handoff)return;\n    try{\n      if(window.__piocaDiagMetric){\n        if(operativo){\n          const ms=Math.max(0,Date.now()-Number(handoff.t0||Date.now()));\n          window.__piocaDiagMetric(\'b20.panel_full_ready_ms\',ms,false);\n        }else{\n          window.__piocaDiagMetric(\'b20.panel_full_ready_failed\',1,true);\n        }\n      }\n    }catch(_){}\n    try{sessionStorage.removeItem(\'pioca_b20_creacion_handoff\')}catch(_){}\n    handoff=null;\n  };\n})();\n</script>\n\n<div class="panel">\n\n  <div class="logoSeguimiento">\n','panel publicado 0-0')
assert 'grid-template-columns:max-content minmax(0,1fr)' in s
assert 'id="b20PanelCreacion"' not in s
p.write_text(s,encoding='utf-8')

# Rechazar una compilación que recupere por accidente los estilos del panel viejo.
import hashlib
_panel=(ROOT/'index-b20-diag.html').read_text('utf-8')
_estilos='\n'.join(re.findall(r'<style\b[^>]*>.*?</style>',_panel,re.S))
assert hashlib.sha256(_estilos.encode()).hexdigest()=='50ee9a005026726927a87c06f78598e20b3ab4284369835d68bee99a3673efc4', 'Panel B20: estilos distintos de la versión aprobada; no publicar'
assert 'id="b20PanelCreacion"' not in _panel, 'Panel B20: barra duplicada; no publicar'
assert '"🟢 GPS NATIVO ACTIVO"' not in _panel, 'Panel B20: semáforo viejo; no publicar'

# ========================== CHEQUEOS ==========================
for name in ('admin','index','cliente'):
    path=ROOT/(name+'-b20-diag.html')
    text=path.read_text('utf-8')
    for i,fragment in enumerate(re.findall(r'<script\b[^>]*>(.*?)</script\s*>',text,re.I|re.S)):
        if not fragment.strip():continue
        with tempfile.NamedTemporaryFile('w',suffix='.js',encoding='utf-8') as tmp:
            tmp.write(fragment);tmp.flush()
            subprocess.run(['node','--check',tmp.name],check=True)
    assert ('-b20-diag.html' in text),name
assert 'b20.vertex_r67_used' in cliente
assert 'b20.vertex_r63_fallback' in cliente
assert 'b20.vertex_r67_late_candidate' in cliente
assert 'b20.vertex_r67_late_tangent' in cliente
assert 'b20.vertex_r65_late_fallback' in cliente
assert 'esquinaR67TardiaB20' in cliente
assert 'b20.share_total_ms' in admin
assert 'b20.share_auto_confirm' in admin
assert '¿Usar esta dirección para crear un seguimiento?' not in admin
assert 'b20.preview_exit_history' in index
assert 'DiagnosticTelemetry.gps(' in (native/'app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java').read_text('utf-8')
assert 'applicationId "ar.com.pioca.seguimiento.b20diag"' in gradle
print('B20: 3 HTML + APK nativa independiente generadas, diagnóstico preservado, JS validado')


