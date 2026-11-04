#!/usr/bin/env python3
"""piOca® Seguimiento: generar propuesta B16 de estabilidad sin modificar producción.

Uso: python3 pioca_seguimiento_hotfix_builder.py /ruta/al/clone/pioca-gps
Genera una carpeta pioca_b16_revision con archivos propuestos; NO sobreescribe el repo.
Exige los SHA Git reales de los archivos auditados el 2026-11-03.
"""
from __future__ import annotations
import hashlib, pathlib, re, shutil, sys

EXPECTED = {
    'admin.html': '2aac823905540cfae0f3c25b3dbbfa0f80cd5602',
    'index.html': '0942feeb82e281149fe617a4bd99a2261e471830',
    'cliente.html': '48dc8448b36c877c9227cd2a572b2a43e49fad1e',
    '.github/workflows/build-android-apk-B15-ETA-PREAPROXIMACION-AUTOCONTENIDO.yml': '9fa284fe191c13d9b1477ec9d9773a83c627a267',
}


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def once(text: str, before: str, after: str, label: str) -> str:
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f'{label}: se esperaban 1 coincidencia, hay {n}')
    return text.replace(before, after, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    result, n = re.subn(pattern, lambda m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f'{label}: no se encontro patrón único')
    return result


ADMIN_WATCHDOG = '''<script>
/* B16: el inicio no puede dejar la pantalla silenciosamente bloqueada. */
(function(){
  setTimeout(function(){
    if(document.body.classList.contains('piocaListo')) return;
    var t=document.getElementById('splashTexto');
    if(t) t.textContent='La aplicación está tardando en iniciar. Podés reintentar sin borrar datos.';
    var panel=document.querySelector('#splashPioca .splashContenido');
    if(panel && !document.getElementById('piocaReintentarInicio')){
      var btn=document.createElement('button');
      btn.type='button';
      btn.id='piocaReintentarInicio';
      btn.textContent='REINTENTAR CARGA';
      btn.style.cssText='display:block;margin:20px auto;padding:13px 18px;border:0;border-radius:12px;background:#1769aa;color:#fff;font-weight:700;';
      btn.onclick=function(){window.location.reload();};
      panel.appendChild(btn);
    }
  },12000);
})();
</script>
'''


def patch_admin(s: str) -> str:
    s = once(s,
      '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>',
      ADMIN_WATCHDOG + '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>',
      'admin watchdog')
    s = once(s,
      '  async function consultarSeguimientoActivoConRecuperacion(){\n',
      '  let consultaActivaCompartida = null;\n\n  async function consultarSeguimientoActivoConRecuperacion(){\n'
      '    if(consultaActivaCompartida) return consultaActivaCompartida;\n'
      '    consultaActivaCompartida = (async function(){\n',
      'admin singleflight inicio')
    s = once(s,
      '  }\n\n\n  function detenerGpsNativoResidual(){',
      '    })();\n'
      '    try { return await consultaActivaCompartida; }\n'
      '    finally { consultaActivaCompartida = null; }\n'
      '  }\n\n\n  function detenerGpsNativoResidual(){',
      'admin singleflight cierre')
    return s


def patch_index(s: str) -> str:
    pattern = r'''      const \{\s*data,\s*error\s*\}\s*=\s*await supabaseClient\.rpc\(\s*"finish_tracking",\s*\{\s*p_code:\s*trackingCode\s*\}\s*\);'''
    replace = '''      // B16: la confirmación debe tener un tiempo máximo de espera.
      // Nunca cerramos localmente si Supabase no confirmó el cierre.
      const controladorCierre = new AbortController();
      const plazoCierre = setTimeout(function(){controladorCierre.abort();},12000);
      let respuestaCierre;
      try{
        respuestaCierre = await supabaseClient.rpc(
          "finish_tracking", {p_code:trackingCode}
        ).abortSignal(controladorCierre.signal);
      }finally{
        clearTimeout(plazoCierre);
      }
      const {data,error} = respuestaCierre;'''
    s = regex_once(s,pattern,replace,'index timeout cierre')
    needle = '''    }catch(error){

      btnFinalizar.disabled =
        false;'''
    replacement = '''    }catch(error){

      // Si el pedido se cortó luego de llegar al servidor, confirmamos
      // su estado antes de permitir cualquier nuevo intento.
      try{
        const estadoCierre = await obtenerEstadoServidor();
        if(servidorConfirmaFinalizado(estadoCierre)){
          mostrarFinalizado((estadoCierre && estadoCierre.client_name) || nombreCliente);
          return;
        }
      }catch(e){}

      btnFinalizar.disabled =
        false;'''
    s = once(s,needle,replacement,'index verificar cierre después del timeout')
    return s


def patch_cliente(s: str) -> str:
    # Se conecta antes a proveedores conocidos. No modifica el mapa ni su lógica.
    s = once(s,
       '  <style>',
       '''  <!-- B16: calentamiento de conexiones para el mapa/recursos visuales. -->
  <link rel="preconnect" href="https://maps.googleapis.com">
  <link rel="preconnect" href="https://maps.gstatic.com" crossorigin>
  <link rel="preconnect" href="https://raw.githubusercontent.com" crossorigin>
  <style>''',
       'cliente preconnect')
    return s


NATIVE_HELPERS = '''
              // B16: monitor nativo. No altera el estado del tracking ni los GPS.
              private android.widget.LinearLayout nativeLoading;
              private final android.os.Handler loadHandler =
                      new android.os.Handler(android.os.Looper.getMainLooper());
              private int loadSequence = 0;
              private boolean loadPainted = false;
              private boolean loadDialogVisible = false;
              private long loadStartedAt = 0L;

              private void beginWebNavigation(String url) {
                  loadSequence++;
                  loadPainted = false;
                  loadStartedAt = android.os.SystemClock.elapsedRealtime();
                  if (nativeLoading != null) nativeLoading.setVisibility(android.view.View.VISIBLE);
                  final int seq = loadSequence;
                  loadHandler.postDelayed(() -> {
                      if (seq == loadSequence && !loadPainted && !isFinishing()) {
                          android.util.Log.w("piOcaWebView", "Carga lenta: " + safePage(url)
                                  + ", t=" + (android.os.SystemClock.elapsedRealtime()-loadStartedAt));
                          showWebRecovery("La página está tardando en cargar.");
                      }
                  }, 12000L);
              }

              private String safePage(String url) {
                  // Nunca registrar ID de seguimiento, tokens ni parámetros URL.
                  try { return android.net.Uri.parse(url).getPath(); }
                  catch (Exception ex) { return "pagina"; }
              }

              private void webPainted(android.webkit.WebView view) {
                  if (view != web || isFinishing()) return;
                  final int seq = loadSequence;
                  view.postVisualStateCallback(seq, requestId -> {
                      if (seq != loadSequence || isFinishing()) return;
                      loadPainted = true;
                      android.util.Log.i("piOcaWebView", "Pantalla lista "+safePage(view.getUrl())
                              +" en "+(android.os.SystemClock.elapsedRealtime()-loadStartedAt)+"ms");
                      if (nativeLoading != null) nativeLoading.setVisibility(android.view.View.GONE);
                  });
              }

              private void showWebRecovery(String reason) {
                  if (isFinishing() || loadDialogVisible) return;
                  loadDialogVisible = true;
                  new AlertDialog.Builder(this)
                          .setTitle("piOca Seguimiento")
                          .setMessage(reason + "\\nEl GPS nativo y los datos existentes no se borran.")
                          .setPositiveButton("REINTENTAR", (d, which) -> {
                              loadDialogVisible = false;
                              if (web != null) web.reload();
                              else recreate();
                          })
                          .setNegativeButton("SEGUIR ESPERANDO", (d, which) -> {
                              loadDialogVisible = false;
                          })
                          .setOnCancelListener(d -> loadDialogVisible = false)
                          .show();
              }
'''


NATIVE_WEBVIEW_CLIENT = '''                  web.setWebViewClient(new WebViewClient() {
                      @Override
                      public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                          Uri uri = request.getUrl();
                          String scheme = uri.getScheme() == null ? "" : uri.getScheme();
                          if ("intent".equalsIgnoreCase(scheme)) {
                              try {
                                  startActivity(Intent.parseUri(uri.toString(), Intent.URI_INTENT_SCHEME));
                              } catch (Exception ignored) {}
                              return true;
                          }
                          return false;
                      }

                      @Override
                      public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                          super.onPageStarted(view,url,favicon);
                          if (view == web) beginWebNavigation(url);
                      }

                      @Override
                      public void onPageFinished(WebView view, String url) {
                          super.onPageFinished(view,url);
                          if (view == web) webPainted(view);
                          // B16: NO reiniciar aquí el servicio GPS desde localStorage.
                          // index.html valida sesión y seguimiento en Supabase antes de
                          // llamar una sola vez a PiocaNative.startTracking().
                      }

                      @Override
                      public void onReceivedError(WebView view, WebResourceRequest req,
                                                  android.webkit.WebResourceError error) {
                          super.onReceivedError(view,req,error);
                          if (req != null && req.isForMainFrame()) {
                              android.util.Log.e("piOcaWebView", "Carga principal falló: "
                                      + safePage(req.getUrl().toString())+" "+error.getErrorCode());
                              showWebRecovery("La carga de la página falló.");
                          }
                      }

                      @Override
                      public void onReceivedHttpError(WebView view, WebResourceRequest req,
                                                      android.webkit.WebResourceResponse response) {
                          super.onReceivedHttpError(view,req,response);
                          if (req != null && req.isForMainFrame() && response != null
                                  && response.getStatusCode() >= 400) {
                              showWebRecovery("Error HTTP " + response.getStatusCode() + ".");
                          }
                      }

                      @Override
                      public boolean onRenderProcessGone(WebView view,
                                                         android.webkit.RenderProcessGoneDetail detail) {
                          android.util.Log.e("piOcaWebView", "Renderizador terminado. Crash="+detail.didCrash());
                          if (view == web) {
                              if (view.getParent() instanceof android.view.ViewGroup)
                                  ((android.view.ViewGroup)view.getParent()).removeView(view);
                              view.destroy();
                              web = null;
                          }
                          showWebRecovery("Android detuvo el motor que muestra la pantalla.");
                          return true;
                      }
                  });

                  requestRuntimePermissions();'''


def native_builder() -> str:
    return '''#!/usr/bin/env python3
# B16: se aplica únicamente al Android generado por el flujo B15.
from pathlib import Path
import re
p=Path("android-pioca/app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java")
g=Path("android-pioca/app/build.gradle")
s=p.read_text(encoding="utf-8")

def one(before,after,name):
    global s
    if s.count(before)!=1: raise SystemExit("B16 falta ancla única: "+name)
    s=s.replace(before,after,1)

one("              private WebView web;", "              private WebView web;"+''' + repr(NATIVE_HELPERS) + ''',"helper nativo")
s,n=re.subn(r'web = new WebView\\(this\\);\\s*setContentView\\(web\\);',
''' + repr('''web = new WebView(this);
                  android.widget.FrameLayout nativeRoot = new android.widget.FrameLayout(this);
                  nativeRoot.addView(web, new android.widget.FrameLayout.LayoutParams(-1,-1));
                  nativeLoading = new android.widget.LinearLayout(this);
                  nativeLoading.setOrientation(android.widget.LinearLayout.VERTICAL);
                  nativeLoading.setGravity(android.view.Gravity.CENTER);
                  nativeLoading.setBackgroundColor(android.graphics.Color.rgb(243,246,249));
                  android.widget.ImageView image = new android.widget.ImageView(this);
                  image.setImageResource(R.mipmap.ic_launcher);
                  nativeLoading.addView(image, new android.widget.LinearLayout.LayoutParams(140,140));
                  android.widget.TextView title = new android.widget.TextView(this);
                  title.setText("piOca® Seguimiento\\nCargando panel...");
                  title.setTextColor(android.graphics.Color.rgb(23,49,75));
                  title.setTextSize(17f);
                  title.setGravity(android.view.Gravity.CENTER);
                  nativeLoading.addView(title);
                  nativeRoot.addView(nativeLoading, new android.widget.FrameLayout.LayoutParams(-1,-1));
                  setContentView(nativeRoot);''') + ''',s,count=1)
if n!=1: raise SystemExit("B16 no encontró la inicialización WebView")
pattern=r'web\\.setWebViewClient\\(\\s*new WebViewClient\\(\\) \\{[\\s\\S]*?\\}\\s*\\);\\s*requestRuntimePermissions\\(\\);'
s,n=re.subn(pattern,lambda m: ''' + repr(NATIVE_WEBVIEW_CLIENT) + ''',s,count=1)
if n!=1: raise SystemExit("B16 WebViewClient no único")
p.write_text(s,encoding="utf-8")
gradle=g.read_text(encoding="utf-8")
if gradle.count("versionCode 15")!=1 or gradle.count('versionName "0.15-eta-preaproximacion"')!=1:
    raise SystemExit("B16 requiere proyecto B15 confirmado")
gradle=gradle.replace("versionCode 15","versionCode 16",1).replace(
    'versionName "0.15-eta-preaproximacion"',
    'versionName "0.16-estabilidad-webview"',1)
g.write_text(gradle,encoding="utf-8")
print("B16: WebView nativo protegido, timeout 12 s, logs y sin doble inicio nativo")
'''


def patch_b15(s: str) -> str:
    s=once(s,'      - name: Compilar APK debug',
'''      - name: Aplicar B16 estabilidad WebView
        shell: bash
        run: |
          python3 .github/scripts/patch_android_b16_webview.py
          grep -q 'versionCode 16' android-pioca/app/build.gradle
          grep -q 'onRenderProcessGone' android-pioca/app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java

      - name: Compilar APK debug''', 'b15 nuevo paso')
    s=once(s,'piOca-Seguimiento-APK-B15-ETA-PREAPROXIMACION',
        'piOca-Seguimiento-APK-B16-ESTABILIDAD','b15 nombre artifact')
    # La ocurrencia del APK en cp y en path debe cambiar en los dos lugares.
    if s.count('piOca-Seguimiento-B15-ETA-PREAPROXIMACION.apk')!=2:
        raise RuntimeError('B15 artefactos APK distintos a versión auditada')
    s=s.replace('piOca-Seguimiento-B15-ETA-PREAPROXIMACION.apk',
                'piOca-Seguimiento-B16-ESTABILIDAD.apk')
    return s


def main(repo: pathlib.Path) -> None:
    root=repo.resolve()
    for path,sha in EXPECTED.items():
        f=root/path
        if not f.exists(): raise SystemExit(f'Falta archivo: {f}')
        actual=blob_sha(f.read_bytes())
        if actual!=sha:
            raise SystemExit(f'PROTECCIÓN: {path} cambió (SHA {actual}). Requiere nueva auditoría.')
    destination=root/'pioca_b16_revision'
    if destination.exists(): raise SystemExit('Carpeta de revisión ya existe; no se sobrescribe.')
    transformations={
        'admin.html':patch_admin,
        'index.html':patch_index,
        'cliente.html':patch_cliente,
        '.github/workflows/build-android-apk-B15-ETA-PREAPROXIMACION-AUTOCONTENIDO.yml':patch_b15,
    }
    contents={p:fn((root/p).read_text(encoding='utf-8')) for p,fn in transformations.items()}
    dest_helper='.github/scripts/patch_android_b16_webview.py'
    contents[dest_helper]=native_builder()
    for path,content in contents.items():
        target=destination/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content,encoding='utf-8')
    print('PROPUESTA GENERADA EN:',destination)
    print('NO se editó producción, ni se publicaron cambios, ni se compiló la APK.')
    print('ANTES de distribuir: ejecutar compilación B16, pruebas Android y regreso tras finalizar servicio.')


if __name__=='__main__':
    if len(sys.argv)!=2:
        sys.exit('Uso: python3 pioca_seguimiento_hotfix_builder.py /ruta/al/repositorio/pioca-gps')
    main(pathlib.Path(sys.argv[1]))
