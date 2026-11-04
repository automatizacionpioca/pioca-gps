#!/usr/bin/env python3
"""Genera archivos completos B16 Fluidez partiendo SOLO de blobs GitHub verificados.

Este generador no modifica ni publica la rama main.
Uso: python pioca_seguimiento_B16_fluidez_builder.py /ruta/pioca-gps
"""
from __future__ import annotations
import pathlib, re, sys, hashlib, subprocess, json, difflib
import pioca_b16_base as base

EXPECTED = base.EXPECTED


def once(s: str, old: str, new: str, name: str) -> str:
    return base.once(s,old,new,name)


def admin(s: str) -> str:
    # Sólo una consulta al estado activo puede ejecutarse concurrentemente.
    s=base.patch_admin(s)
    s=once(s,
'''  async function recuperarEstadoAlVolver(){

    if(
      recuperacionEnCurso ||''',
'''  async function recuperarEstadoAlVolver(){
    // B16: una recuperación de foco no compite con la comprobación inicial.
    if(!document.body.classList.contains('piocaListo')) return;

    if(
      recuperacionEnCurso ||''','admin evitar doble navegacion')
    s=once(s, '  <style>', '''  <!-- B16: adelantar DNS/TLS para dependencias sin modificar la autenticación. -->
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="preconnect" href="https://apxrmkdegjnblkbyjsbp.supabase.co" crossorigin>
  <style>''', 'admin preconnect')
    # Instrumentación sólo de duraciones; no se registran códigos ni datos personales.
    s=once(s,
'''  async function comprobarSesion(){
    const {data} =
      await supabaseClient.auth.getSession();''',
'''  async function comprobarSesion(){
    const b16InicioSesion = performance.now();
    let data;
    let b16TimerSesion = null;
    try{
      const respuesta = await Promise.race([
        supabaseClient.auth.getSession(),
        new Promise(function(_resolve, reject){
          b16TimerSesion=setTimeout(function(){reject(new Error('TIMEOUT_SESION'));},12000);
        })
      ]);
      if(respuesta.error) throw respuesta.error;
      data = respuesta.data;
      console.info('[piOcaPERF] sesion '+Math.round(performance.now()-b16InicioSesion)+'ms');
    }catch(error){
      var splashError=document.getElementById('splashTexto');
      if(splashError) splashError.textContent='No se pudo verificar la sesión. Reintentá sin borrar datos.';
      console.warn('[piOcaPERF] sesion error '+Math.round(performance.now()-b16InicioSesion)+'ms');
      return;
    }finally{
      if(b16TimerSesion !== null) clearTimeout(b16TimerSesion);
    }''','admin sesion tiempo')
    s=once(s,
'''  async function verificarSeguimientoActivo(){
    formNuevo.style.display''',
'''  async function verificarSeguimientoActivo(){
    const b16InicioConsulta = performance.now();
    formNuevo.style.display''', 'admin consulta tiempo inicio')
    s=once(s,
'''      const {data,error} =
        await consultarSeguimientoActivoConRecuperacion();

      if(error){
        throw error;
      }

      if(Array.isArray(data) && data.length > 0){''',
'''      const {data,error} =
        await consultarSeguimientoActivoConRecuperacion();
      console.info('[piOcaPERF] verificar_activo '+Math.round(performance.now()-b16InicioConsulta)+'ms');

      if(error){
        throw error;
      }

      if(Array.isArray(data) && data.length > 0){''','admin consulta tiempo fin')
    return s


def index(s: str) -> str:
    s=base.patch_index(s)
    # Dejar el aviso de carga en el botón desde el mismo toque, sin redirecciones extra.
    s=once(s,
'''    window.location.href =
      urlPreview;''',
'''    // B16: feedback visual inmediato. No consulta ni reinicia el GPS.
    if(btnVerSeguimiento){
      btnVerSeguimiento.disabled = true;
      btnVerSeguimiento.textContent = 'ABRIENDO SEGUIMIENTO...';
    }
    window.location.href =
      urlPreview;''','index aviso preview')
    # Al restaurar la pantalla (navegación atrás o bfcache), habilitar el botón.
    s=once(s,
'''  window.addEventListener(
    "pageshow",
    function(){
      let retornoPreview = null;''',
'''  window.addEventListener(
    "pageshow",
    function(){
      if(btnVerSeguimiento){
        btnVerSeguimiento.disabled = false;
        btnVerSeguimiento.textContent = '👁 VER SEGUIMIENTO';
      }
      let retornoPreview = null;''','index restaurar boton')
    s=once(s,'  <style>', '''  <link rel="preconnect" href="https://apxrmkdegjnblkbyjsbp.supabase.co" crossorigin>
  <link rel="preconnect" href="https://maps.googleapis.com">
  <style>''','index preconnect')
    return s


def cliente(s: str) -> str:
    s=base.patch_cliente(s)
    # Google recomienda callback de carga async. Evita bloquear el parsing del HTML de 429 KB.
    # Toda ejecución de crearMapa() queda diferida a la resolución de este Promise.
    google_old='''<script
  src="https://maps.googleapis.com/maps/api/js?key=AIzaSyDE0iExc9s5QeZBPIN6BNYCucNFDrjmyKM&v=weekly">
</script>'''
    google_new='''<!-- B16 FLUIDEZ: Google Maps se carga en paralelo con el panel visual. -->
<script>
(function(){
  window.piocaGoogleMapsCargado=false;
  window.piocaGoogleMapsListo=new Promise(function(resolve,reject){
    window.piocaGoogleMapsOk=function(){
      window.piocaGoogleMapsCargado=true;
      console.info('[piOcaPERF] mapa API '+Math.round(performance.now())+'ms');
      resolve(true);
    };
    window.piocaGoogleMapsError=function(){
      reject(new Error('MAPS_NO_DISPONIBLE'));
    };
  });
})();
</script>
<script async
  src="https://maps.googleapis.com/maps/api/js?key=AIzaSyDE0iExc9s5QeZBPIN6BNYCucNFDrjmyKM&v=weekly&loading=async&callback=piocaGoogleMapsOk"
  onerror="piocaGoogleMapsError()">
</script>'''
    s=once(s,google_old,google_new,'cliente async maps')
    # Un visitante en preview vuelve al controlador en una sola navegación,
    # evitando history.back() + pageshow + una segunda location.replace().
    s=once(s,
'''    try{
      if(
        window.history.length > 1
      ){
        window.history.back();
        return;
      }
    }catch(e){}

    window.location.href =
      "index.html?tracking=" +''',
'''    // B16: una sola navegación. No reactivar timers antiguos por BFCache.
    try{ sessionStorage.removeItem('pioca_preview_retorno_panel'); }catch(e){}
    window.location.replace(
      "index.html?tracking=" +''', 'cliente vuelta preview inicio')
    # Cerrar paréntesis cambiado por reemplazo anterior.
    s=once(s,
'''      encodeURIComponent(
        String(codigo || "").trim().toUpperCase()
      );
  }

  if(
    btnVolverPanelPreview''',
'''      encodeURIComponent(
        String(codigo || "").trim().toUpperCase()
      )
    );
  }

  if(
    btnVolverPanelPreview''','cliente vuelta preview cierre')
    # Evitar consultar y crear mapa si el recurso externo aún no terminó.
    s=once(s,
'''  async function consultar(
    forzar
  ){

    forzar =''',
'''  async function consultar(
    forzar
  ){
    // B16: si Google Maps sigue cargando, conservar la interfaz y esperar
    // sin tocar estados físicos ni iniciar un renderer inexistente.
    if(!window.piocaGoogleMapsCargado) return;

    forzar =''','cliente consulta guard')
    s=once(s,
'''  }else{

    consultar(true);

    iniciarCicloConsultas();

    iniciarHeartbeatCliente();
  }

})();''',
'''  }else{
    // B16: mostrar un estado de carga inmediato antes de tener cartografía.
    var piocaMapaAviso=document.getElementById('estado');
    if(piocaMapaAviso){
      piocaMapaAviso.textContent='Cargando mapa de seguimiento...';
      piocaMapaAviso.classList.remove('estadoOculto');
      piocaMapaAviso.style.display='block';
    }
    window.piocaGoogleMapsListo.then(function(){
      if(terminado) return;
      if(piocaMapaAviso && piocaMapaAviso.textContent==='Cargando mapa de seguimiento...'){
        piocaMapaAviso.textContent='';
        piocaMapaAviso.classList.add('estadoOculto');
        piocaMapaAviso.style.display='';
      }
      consultar(true);
      iniciarCicloConsultas();
      iniciarHeartbeatCliente();
    }).catch(function(){
      var estadoInicio=document.getElementById('estado');
      if(estadoInicio){
        estadoInicio.textContent='No se pudo cargar el mapa. Revisá la conexión y volvé a entrar.';
        estadoInicio.classList.remove('estadoOculto');
        estadoInicio.style.display='block';
      }
    });
  }

})();''','cliente startup async')
    return s


def native_builder() -> str:
    # El patch nativo verificado conserva los GPS y reemplaza sólo WebViewClient.
    base.NATIVE_WEBVIEW_CLIENT = once(
      base.NATIVE_WEBVIEW_CLIENT,
      '                          if (view == web) {\n                              if (view.getParent()',
      '                          if (view == web) {\n                              loadSequence++;\n                              loadPainted = false;\n                              if(nativeLoading != null) nativeLoading.setVisibility(android.view.View.VISIBLE);\n                              if (view.getParent()',
      'native proteger splash al caer renderer'
    ) if 'loadSequence++;\n                              loadPainted' not in base.NATIVE_WEBVIEW_CLIENT else base.NATIVE_WEBVIEW_CLIENT
    t=base.native_builder()
    # Agrega logs de los hitos web sin almacenar ID ni tokens.
    anchor='''p.write_text(s,encoding="utf-8")
gradle=g.read_text(encoding="utf-8")'''
    addition='''# Instrumentación segura del renderizador: sólo etiquetas piOcaPERF.
s, count_console = re.subn(
    r'(new WebChromeClient\\(\\)\\s*\\{)',
    lambda m: m.group(1) + r"""
                      @Override
                      public boolean onConsoleMessage(android.webkit.ConsoleMessage m){
                          if(m != null && m.message() != null && m.message().startsWith("[piOcaPERF]")){
                              android.util.Log.i("piOcaWebView",m.message());
                          }
                          return super.onConsoleMessage(m);
                      }
                      """,
    s,
    count=1
)
if count_console != 1: raise SystemExit('B16 consola WebView no encontrada')
p.write_text(s,encoding="utf-8")
gradle=g.read_text(encoding="utf-8")'''
    t=once(t,anchor,addition,'native instrumentacion')
    return t


def workflow(s: str) -> str:
    s=base.patch_b15(s)
    s=once(s,'piOca-Seguimiento-APK-B16-ESTABILIDAD','piOca-Seguimiento-APK-B16-FLUIDEZ','artifact nombre fluidez')
    s=once(s,'name: Compilar piOca Android APK B15 ETA PREAPROXIMACION AUTOCONTENIDO','name: Compilar piOca Android APK B16 FLUIDEZ','workflow nombre')
    if s.count('piOca-Seguimiento-B16-ESTABILIDAD.apk')!=2:
        raise RuntimeError('nombre B16 apk no coincide')
    return s.replace('piOca-Seguimiento-B16-ESTABILIDAD.apk','piOca-Seguimiento-B16-FLUIDEZ.apk')


def verify_unchanged_regions(before: str, after: str, filename: str) -> None:
    # Aserciones mínimas específicas, no sustituyen tests Android en equipo real.
    keep = {
       'cliente.html': ['ALGORITMO_SEGUIMIENTO = Object.freeze(', 'DISTANCIA_CERCA_M:300', 'liberarEncuadreInicialYSeguirPin', 'procesarPosicionProximidad('],
       'index.html': ['finish_tracking', 'iniciarNativoConServidor(', 'detenerNativo(', 'setInterval('],
       'admin.html': ['get_my_active_tracking', 'crearTracking', 'verificarSeguimientoActivo('],
    }
    for needle in keep.get(filename,[]):
        if needle in before and needle not in after:
            raise RuntimeError(f'Protección funcional: desapareció {needle} en {filename}')


def main(repo: pathlib.Path) -> None:
    repo=repo.resolve()
    for path,sha in EXPECTED.items():
        file=repo/path
        if not file.is_file(): raise SystemExit('No encuentro archivo actual de GitHub: '+str(file))
        digest=base.blob_sha(file.read_bytes())
        if digest != sha:
            raise SystemExit('PROTECCIÓN: '+path+' fue modificado respecto del original verificado. SHA='+digest+'; no aplicar sin nueva auditoría.')
    output=repo/'pioca_B16_FLUIDEZ_ENTREGA'
    if output.exists(): raise SystemExit('Ya existe carpeta de entrega: '+str(output))
    transforms={
        'admin.html':admin,
        'index.html':index,
        'cliente.html':cliente,
        '.github/workflows/build-android-apk-B15-ETA-PREAPROXIMACION-AUTOCONTENIDO.yml':workflow,
    }
    data={}
    for filename, fn in transforms.items():
        before=(repo/filename).read_text(encoding='utf-8')
        after=fn(before)
        verify_unchanged_regions(before,after,filename)
        data[filename]=after
    # Publicar B16 como NUEVO workflow; mantener B15 en GitHub para rollback.
    workflow_anterior='.github/workflows/build-android-apk-B15-ETA-PREAPROXIMACION-AUTOCONTENIDO.yml'
    workflow_nuevo='.github/workflows/build-android-apk-B16-FLUIDEZ.yml'
    data[workflow_nuevo]=data.pop(workflow_anterior)
    data['.github/scripts/patch_android_b16_webview.py']=native_builder()
    for path,contents in data.items():
        p=output/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(contents,encoding='utf-8')
    # Diff legible de cada archivo: permite auditar antes de subir nada.
    diffs=[]
    for path in transforms:
        a=(repo/path).read_text(encoding='utf-8').splitlines(keepends=True)
        target=workflow_nuevo if path==workflow_anterior else path
        b=data[target].splitlines(keepends=True)
        diffs.extend(difflib.unified_diff(a,b,fromfile='main/'+path,tofile='B16/'+target,n=4))
    (output/'CAMBIOS_B16.diff').write_text(''.join(diffs),encoding='utf-8')
    (output/'VERIFICACION_SHA_BASE.json').write_text(json.dumps(EXPECTED,indent=2),encoding='utf-8')
    # No sobreescribir ni desplegar el repositorio original.
    print('ENTREGA DE ARCHIVOS COMPLETOS:',output)
    for f in data: print(' -',f, '(',len(data[f]),'caracteres )')
    print('No se modificó GitHub ni se compiló la APK: instalar sólo luego de pruebas.')

if __name__=='__main__':
    if len(sys.argv)!=2: sys.exit('Uso: python pioca_seguimiento_B16_fluidez_builder.py /ruta/pioca-gps')
    main(pathlib.Path(sys.argv[1]))
