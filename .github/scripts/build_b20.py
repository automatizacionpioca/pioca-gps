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
