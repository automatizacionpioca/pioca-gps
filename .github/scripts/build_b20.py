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
