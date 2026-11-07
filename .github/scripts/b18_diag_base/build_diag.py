#!/usr/bin/env python3
"""piOca B17-DIAG: toma fuentes B17 consolidadas y produce APK diagnóstica.
NO modifica B17 ni archivos de producción. Crea android-b17-diag y *-diag.html.
"""
from pathlib import Path
import re, hashlib, sys
root=Path.cwd()
base=root/'android-b17'
out=root/'android-b17-diag'
assert (base/'app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java').is_file(), 'Falta fuente B17 nativa consolidada'
assert not out.exists(), 'No sobrescribir android-b17-diag existente'
from shutil import copytree
copytree(base,out,ignore=lambda d,n: [x for x in n if x in ('build','.gradle','tmp')])

here=Path(__file__).resolve().parent
native=out/'app/src/main/java/ar/com/pioca/seguimiento'
main=native/'MainActivity.java'
service=native/'TrackingService.java'
manifest=out/'app/src/main/AndroidManifest.xml'
gradle=out/'app/build.gradle'

orig_service=service.read_text('utf-8')
orig_main=main.read_text('utf-8')
orig_service_hash=hashlib.sha256(orig_service.encode('utf-8')).hexdigest()
s=orig_service
m=orig_main

def exact(body,old,new,label):
    count=body.count(old)
    if count!=1: raise ValueError(f'B17-DIAG {label}: ancla encontrada {count} veces, se requiere 1')
    return body.replace(old,new,1)

def regex_once(body,rx,replacement,label):
    new,n=re.subn(rx,replacement,body,count=1,flags=re.M)
    if n!=1:raise ValueError(f'B17-DIAG {label}: ancla no hallada')
    return new

key=re.search(r'private\s+static\s+final\s+String\s+KEY\s*=\s*"([a-zA-Z0-9_]+)"\s*;',s)
assert key, 'No se encontró publishable key en TrackingService'
api_key=key.group(1)
assert api_key.startswith('sb_publishable_'), 'La clave no es publicable. Revisión necesaria'
java=(here/'DiagnosticTelemetry.java').read_text('utf-8').replace('__API_KEY_FROM_B17_SOURCE__',api_key)
(native/'DiagnosticTelemetry.java').write_text(java,'utf-8')

# Edición que NO toca los algoritmos, sólo lectura de métricas y envío aislado.
s=exact(s,'        startLocations();',
'''        DiagnosticTelemetry.init(this);
        DiagnosticTelemetry.setAuth(this,accessToken);
        startLocations();''','inicio de telemetría')
s=exact(s,'        last =\n                l;',
'''        last =
                l;
        DiagnosticTelemetry.gps(l);''','muestras GPS')
s=exact(s,'      maybeEnableDnd(now);',
'''      DiagnosticTelemetry.heartbeat();
      maybeEnableDnd(now);''','jitter heartbeat')
# Instrumentación de RPC: mide tiempo de pared de cada solicitud, sin interceptarla.
measurements=[
    ('RemoteResult r', 'loadRemoteState', 'accessToken', 'net.state_rtt_ms','r.state == RemoteState.UNAUTHORIZED'),
    ('SendResult r', 'send', r'l,\n\s*accessToken', 'net.position_rtt_ms','!r.ok'),
    ('RouteEtaResult route', 'loadRouteEta', r'current,\n\s*destLat,\n\s*destLon,\n\s*accessToken','net.route_rtt_ms','!route.ok'),
    ('UpdateEtaResult update','updateRouteEta',r'route,\n\s*accessToken','net.update_eta_rtt_ms','!update.ok')
]
for typ,call,args,metric,err in measurements:
    pattern=r'('+re.escape(typ)+r'\s*=\s*'+call+r'\(\s*'+args+r'\s*\);)'
    if not re.search(pattern,s):raise ValueError('B17-DIAG solicitud no hallada '+metric)
    s=re.sub(pattern,lambda x:
        'long diagStart'+metric.replace('.','_')+'=android.os.SystemClock.elapsedRealtime();\n'
        +x.group(1)+'\n'
        +'DiagnosticTelemetry.record("'+metric+'",android.os.SystemClock.elapsedRealtime()-diagStart'+metric.replace('.','_')+','+err+');',s,count=1)

# Actualiza JWT diagnóstico cuando B17 refresca su sesión.
s=exact(s,'            return !accessToken.isEmpty();',
'''            DiagnosticTelemetry.setAuth(this,accessToken);
            return !accessToken.isEmpty();''','JWT actualizado')
service.write_text(s,'utf-8')

# Navegación de DIAG a páginas DIAG; rutas de compartición a clientes quedan originales.
for a,b in [('admin.html','admin-diag.html'),('index.html','index-diag.html'),('cliente.html','cliente-diag.html')]:
    m=m.replace('https://automatizacionpioca.github.io/pioca-gps/'+a,
                'https://automatizacionpioca.github.io/pioca-gps/'+b)
# La verificación en onPageFinished debe reconocer index-diag.
m=m.replace('"/pioca-gps/index.html"','"/pioca-gps/index-diag.html"')
m=exact(m,'        super.onCreate(state);\n\n\n        captureSharedDestination(\n',
'''        super.onCreate(state);

        DiagnosticTelemetry.init(this);

        captureSharedDestination(
''','inicialización Activity')
m=exact(m,'        web.addJavascriptInterface(\n',
'''        web.addJavascriptInterface(new DiagnosticTelemetry.Bridge(),"PiocaDiag");
        web.addJavascriptInterface(
''','puente JavaScript')
m=exact(m,'                                  loadPainted = true;',
'''                                  DiagnosticTelemetry.record("android.web_visual_ready_ms",
                                          android.os.SystemClock.elapsedRealtime()-loadStartedAt,false);
                                  loadPainted = true;''','pintado real')
m=exact(m,'                          if(view == web) webPainted(view);',
'''                          if(view == web) {
                              DiagnosticTelemetry.record("android.web_page_finished_ms",
                                      android.os.SystemClock.elapsedRealtime()-loadStartedAt,false);
                              webPainted(view);
                          }''','page finish')
m=exact(m,'                          showWebRecovery("Android detuvo el motor que muestra la pantalla.");',
'''                          DiagnosticTelemetry.record("android.renderer_gone",0,true);
                          showWebRecovery("Android detuvo el motor que muestra la pantalla.");''','crash renderer')
main.write_text(m,'utf-8')

x=manifest.read_text('utf-8')
x=exact(x,'  <uses-permission\n    android:name="android.permission.INTERNET"/>',
'''  <uses-permission
    android:name="android.permission.INTERNET"/>
  <uses-permission
    android:name="android.permission.ACCESS_NETWORK_STATE"/>''','red capacidades')
x=exact(x,'android:label="piOca Seguimiento"','android:label="piOca Seguimiento DIAG"','etiqueta Android')
manifest.write_text(x,'utf-8')
g=gradle.read_text('utf-8')
g=exact(g,'applicationId "ar.com.pioca.seguimiento"','applicationId "ar.com.pioca.seguimiento.diag"','paquete paralelo')
g=exact(g,'versionCode 17','versionCode 171','versión')
g=exact(g,'versionName "0.17-integral"','versionName "0.17-DIAG"','nombre')
gradle.write_text(g,'utf-8')

# Las tres páginas son COPIAS nuevas. Los originales jamás se editan.
js=(here/'diag_web.js').read_text('utf-8')
for page in ('admin','index','cliente'):
    src=(root/(page+'.html')).read_text('utf-8')
    assert src.count('</head>')==1,page+' /head'
    src=src.replace('</head>','<script>\n'+js+'\n</script>\n</head>',1)
    if page=='admin':
        # Sólo el panel interno; el vínculo que recibe el cliente queda original.
        src=src.replace('"index.html?tracking="','"index-diag.html?tracking="')
    if page=='index':
        # Al volver al panel, permanecer en DIAG; el WhatsApp del cliente es normal.
        src=src.replace('"admin.html"','"admin-diag.html"')
        # Preview se redirige a una COPIA instrumentada, conservando el parámetro.
        pattern=r'const urlPreview\s*=\s*linkCliente\s*\+\s*separador\s*\+\s*"preview=([a-zA-Z0-9_-]+)";'
        mo=re.search(pattern,src)
        if not mo: raise ValueError('B17-DIAG preview: no se encontro formato esperado')
        mode=mo.group(1)
        replacement=(
          'const urlPreview =\n'
          '      "https://automatizacionpioca.github.io/pioca-gps/cliente-diag.html?id=" +\n'
          '      encodeURIComponent(trackingCode) +\n'
          '      "&preview='+mode+'";'
        )
        src=src[:mo.start()]+replacement+src[mo.end():]
    if page=='cliente':
        # Retorno del Preview al panel diagnóstico, sin tocar datos del cliente.
        src=src.replace('index.html?tracking=', 'index-diag.html?tracking=')
        # Instrumentación al nivel de las funciones de cierre léxico de R67/R64/R65.
        wrappers=[
          ('r67BuscarCandidato','cart.r67_candidate_ms',False),
          ('r67CargarSector','cart.r67_sector_ms',True),
          ('r67ReconstruirSegmentosActivos','cart.r67_index_ms',False),
          ('r67CandidatosIndice','cart.r67_local_index_ms',False),
          ('r67ProyectarSobreSegmento','cart.r67_projection_ms',False),
          ('ajustarPuntoVisualR67','cart.r67_visual_match_ms',False),
          ('evaluarProteccionGeometrica','filter.geometry_ms',False),
          ('calcularConfianzaGpsVisual','filter.confidence_ms',False),
          ('calcularDuracionAnimacion','anim.duration_calc_ms',False),
          ('animarMarcadorConColaVertices','anim.queue_vertices_ms',False),
          ('construirCurvaTangencialR65','anim.bezier_ms',False),
          ('pasoR65','anim.frame_r65_ms',False),
          ('pasoRuta','anim.frame_route_ms',False),
          ('actualizarZoomSegunEta','view.zoom_eta_ms',False),
          ('actualizarEstadoLlegada','view.arrival_state_ms',False),
          ('consultar','net.client_poll_ms',True),
          ('crearMapa','view.create_map_ms',False),
          ('actualizarPanelTrayecto','view.progress_ms',False),
        ]
        funcs=[]
        for name,metric,is_async in wrappers:
            if len(re.findall(r'\b(?:async\s+)?function\s+'+name+r'\s*\(',src))!=1:
                raise ValueError('B17-DIAG función del mapa no hallada: '+name)
            if not is_async:
                funcs.append('''  {const original=%(fn)s;
    %(fn)s=function(){const t=performance.now();let err=0;
      try{return original.apply(this,arguments)}catch(e){err=1;throw e}
      finally{window.__piocaDiagMetric('%(metric)s',performance.now()-t,err);}
    };}'''%{'fn':name,'metric':metric})
            else:
                funcs.append('''  {const original=%(fn)s;
    %(fn)s=function(){const t=performance.now();let p;
      try{p=original.apply(this,arguments)}catch(e){window.__piocaDiagMetric('%(metric)s',performance.now()-t,1);throw e;}
      if(p&&typeof p.then==='function')p.then(
        ()=>window.__piocaDiagMetric('%(metric)s',performance.now()-t,0),
        ()=>window.__piocaDiagMetric('%(metric)s',performance.now()-t,1));
      else window.__piocaDiagMetric('%(metric)s',performance.now()-t,0);
      return p;
    };}'''%{'fn':name,'metric':metric})
        plugin='''  // B17-DIAG: sólo se envuelven las funciones si el visor es la APK DIAG.
  if(window.PiocaDiag && window.__piocaDiagMetric){
'''+ '\n'.join(funcs)+ '\n  }\n\n'
        src=exact(src,'  ocultarEstadoSuperior();',plugin+'  ocultarEstadoSuperior();','funciones del cliente')
    (root/(page+'-diag.html')).write_text(src,'utf-8')

# Asegura que la compilación no haya cambiado TrackingService principal.
assert hashlib.sha256(service.read_bytes()).hexdigest()!=orig_service_hash
assert hashlib.sha256((base/'app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java').read_bytes()).hexdigest()==orig_service_hash
assert 'startForeground(' in s and 'maybeLatchArrivalAndFinish(' in s
print('B17-DIAG preparado: fuente Android separada y tres páginas independientes. B17 intacta.')
