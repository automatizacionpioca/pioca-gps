
package ar.com.pioca.seguimiento;


import android.Manifest;

import android.app.Activity;

import android.app.AlertDialog;

import android.app.NotificationManager;

import android.content.Intent;

import android.content.SharedPreferences;

import android.content.pm.PackageManager;

import android.database.Cursor;

import android.net.Uri;

import android.os.Build;

import android.os.Bundle;

import android.os.PowerManager;

import android.provider.ContactsContract;

import android.provider.Settings;

import android.webkit.GeolocationPermissions;

import android.webkit.JavascriptInterface;

import android.webkit.WebChromeClient;

import android.webkit.WebResourceRequest;

import android.webkit.WebSettings;

import android.webkit.WebView;

import android.webkit.WebViewClient;

import org.json.JSONObject;


public class MainActivity extends Activity {


    private static final String ADMIN =

            "https://automatizacionpioca.github.io/pioca-gps/admin.html";


    private static final String AUTH_KEY =

            "sb-apxrmkdegjnblkbyjsbp-auth-token";


    private static final int REQ_PERMISSIONS = 100;

    private static final int REQ_CONTACT = 200;


    private WebView web;
              // URL del panel/preview para que un reinicio de Activity no vuelva a cero.
              private String ultimaPaginaPioca=ADMIN;
              private boolean paginaPioca(String url){
                  if(url==null)return false;
                  return url.startsWith("https://automatizacionpioca.github.io/pioca-gps/admin.html")
                      || url.startsWith("https://automatizacionpioca.github.io/pioca-gps/index.html")
                      || url.startsWith("https://automatizacionpioca.github.io/pioca-gps/cliente.html")
                      || url.startsWith("https://trackingpioca.com/");
              }
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
                  view.postVisualStateCallback(seq,
                          new android.webkit.WebView.VisualStateCallback() {
                              @Override
                              public void onComplete(long requestId) {
                                  if (seq != loadSequence || isFinishing()) return;
                                  loadPainted = true;
                                  android.util.Log.i("piOcaWebView", "Pantalla lista "+safePage(view.getUrl())
                                          +" en "+(android.os.SystemClock.elapsedRealtime()-loadStartedAt)+"ms");
                                  if (nativeLoading != null) nativeLoading.setVisibility(android.view.View.GONE);
                              }
                          });
              }

              private void showWebRecovery(String reason) {
                  if (isFinishing() || loadDialogVisible) return;
                  loadDialogVisible = true;
         if (web == null) {
             new AlertDialog.Builder(this)
                 .setTitle("piOca Seguimiento")
                 .setMessage("Android cerró la pantalla del seguimiento. El GPS nativo continúa funcionando. Reabrí el panel.")
                 .setCancelable(false)
                 .setPositiveButton("RECUPERAR", (d,which) -> {
                     loadDialogVisible=false;
                     recreate();
                 }).show();
             return;
         }
         new AlertDialog.Builder(this)
                          .setTitle("piOca Seguimiento")
                          .setMessage(reason + "\nEl GPS nativo y los datos existentes no se borran.")
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


    private boolean batteryDialogVisible = false;

    private long lastBatteryPromptAt = 0L;

private boolean dndDialogVisible = false;

private boolean dndRestoreDialogVisible = false;


    @Override
    public void onCreate(Bundle state) {


        super.onCreate(state);


        captureSharedDestination(
                getIntent()
        );


        web = new WebView(this);
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
                  title.setText("piOca® Seguimiento\nCargando panel...");
                  title.setTextColor(android.graphics.Color.rgb(23,49,75));
                  title.setTextSize(17f);
                  title.setGravity(android.view.Gravity.CENTER);
                  nativeLoading.addView(title);
                  nativeRoot.addView(nativeLoading, new android.widget.FrameLayout.LayoutParams(-1,-1));
                  setContentView(nativeRoot);


        WebSettings settings =
                web.getSettings();


        settings.setJavaScriptEnabled(true);

        settings.setDomStorageEnabled(true);

        settings.setDatabaseEnabled(true);

        settings.setGeolocationEnabled(true);


        web.addJavascriptInterface(

                new NativeBridge(),

                "PiocaNative"

        );


        web.setWebChromeClient(

                new WebChromeClient() {
                      @Override
                      public boolean onConsoleMessage(android.webkit.ConsoleMessage m){
                          if(m != null && m.message() != null && m.message().startsWith("[piOcaPERF]")){
                              android.util.Log.i("piOcaWebView",m.message());
                          }
                          return super.onConsoleMessage(m);
                      }
                      


                    @Override
                    public void onGeolocationPermissionsShowPrompt(

                            String origin,

                            GeolocationPermissions.Callback callback) {


                        boolean ok =

                                checkSelfPermission(

                                        Manifest.permission.ACCESS_FINE_LOCATION)

                                == PackageManager.PERMISSION_GRANTED;


                        callback.invoke(

                                origin,

                                ok,

                                false
                        );
                    }
                }
        );


        web.setWebViewClient(

                new WebViewClient() {
                      // B16: agregar diagnóstico sin borrar comportamiento original B15.
                      @Override
                      public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                          super.onPageStarted(view, url, favicon);
                          if(view == web){
                              if(paginaPioca(url))ultimaPaginaPioca=url;
                              beginWebNavigation(url);
                          }
                      }

                      @Override
                      public void onReceivedError(WebView view, WebResourceRequest req,
                                                  android.webkit.WebResourceError error) {
                          super.onReceivedError(view, req, error);
                          if (req != null && req.isForMainFrame()) {
                              android.util.Log.e("piOcaWebView", "Carga principal falló: "
                                      + safePage(req.getUrl().toString()) + " " + error.getErrorCode());
                              showWebRecovery("La carga de la página falló.");
                          }
                      }

                      @Override
                      public void onReceivedHttpError(WebView view, WebResourceRequest req,
                                                      android.webkit.WebResourceResponse response) {
                          super.onReceivedHttpError(view, req, response);
                          if (req != null && req.isForMainFrame() && response != null
                                  && response.getStatusCode() >= 400) {
                              showWebRecovery("Error HTTP " + response.getStatusCode() + ".");
                          }
                      }

                      @Override
                      public boolean onRenderProcessGone(WebView view,
                                                         android.webkit.RenderProcessGoneDetail detail) {
                          android.util.Log.e("piOcaWebView", "Renderizador terminado. Crash=" + detail.didCrash());
                          if (view == web) {
                              loadSequence++;
                              loadPainted = false;
                              if (nativeLoading != null) nativeLoading.setVisibility(android.view.View.VISIBLE);
                              if (view.getParent() instanceof android.view.ViewGroup)
                                  ((android.view.ViewGroup)view.getParent()).removeView(view);
                              view.destroy();
                              web = null;
                          }
                          showWebRecovery("Android detuvo el motor que muestra la pantalla.");
                          return true;
                      }



                    @Override
                    public boolean shouldOverrideUrlLoading(

                            WebView view,

                            WebResourceRequest request) {


                        Uri uri =
                                request.getUrl();


                        String scheme =

                                uri.getScheme() == null

                                        ? ""

                                        : uri.getScheme();


                        if ("intent".equalsIgnoreCase(scheme)) {


                            try {

                                startActivity(

                                        Intent.parseUri(

                                                uri.toString(),

                                                Intent.URI_INTENT_SCHEME

                                        )
                                );

                            } catch (Exception ignored) {
                            }


                            return true;
                        }


                        return false;
                    }


                    @Override
                    public void onPageFinished(

                            WebView view,

                            String url) {


                        super.onPageFinished(

                                view,

                                url
                        );
                          if(view == web) webPainted(view);


                        Uri uri =
                                Uri.parse(url);


                        if (url.contains(

                                "/pioca-gps/index.html")) {


                            clearPendingSharedDestination();


                            String code =

                                    uri.getQueryParameter(

                                            "tracking"
                                    );


                            if (

                                    code != null

                                    && !code.trim().isEmpty()

                            ) {


                                String safeCode =

                                        JSONObject.quote(

                                                code.trim()

                                                        .toUpperCase()
                                        );


                                String js =

                                        "(function(){try{"

                                        + "var raw=localStorage.getItem("

                                        + JSONObject.quote(AUTH_KEY)

                                        + ");"

                                        + "if(!raw)return;"

                                        + "var s=JSON.parse(raw);"

                                        + "if(s&&s.access_token){"

                                        + "PiocaNative.startTracking("

                                        + safeCode

                                        + ",String(s.access_token||''),"

                                        + "String(s.refresh_token||''),"

                                        + "String(localStorage.getItem('pioca_client_name')||''),"

                                        + "String(localStorage.getItem('pioca_tracking_expires_at')||''));"

                                        + "}"

                                        + "}catch(e){}})();";


                                view.evaluateJavascript(

                                        js,

                                        null
                                );
                            }
                        }


                        /*
                         * V5
                         *
                         * Ya NO detenemos el servicio GPS simplemente
                         * porque falte localStorage al entrar a admin.html.
                         *
                         * El admin consulta primero al servidor.
                         *
                         * Solamente si Supabase confirma que NO existe
                         * seguimiento activo se llama stopTracking().
                         */
                    }
                }
        );


        requestRuntimePermissions();


        String paginaGuardada=state==null ? null : state.getString("pioca_url_actual");
                  if(paginaPioca(paginaGuardada)) ultimaPaginaPioca=paginaGuardada;
                  web.loadUrl(ultimaPaginaPioca);
    }


    @Override
    protected void onSaveInstanceState(Bundle state){
                  state.putString("pioca_url_actual", ultimaPaginaPioca);
                  super.onSaveInstanceState(state);
              }

              @Override
              protected void onResume() {


        super.onResume();


        if (web != null) {


            web.postDelayed(

                    this::showPendingEndDialog,

                    350
            );


            web.postDelayed(

                    this::checkBatteryOptimization,

                    1000
            );
        }
    }


    private void checkBatteryOptimization() {


        if (

                Build.VERSION.SDK_INT < 23

                || isFinishing()

        ) {


            return;
        }


        PowerManager pm =

                (PowerManager)

                        getSystemService(

                                POWER_SERVICE
                        );


        if (pm == null) {


            return;
        }


        if (

                pm.isIgnoringBatteryOptimizations(

                        getPackageName()
                )

        ) {


            return;
        }


        long now =

                System.currentTimeMillis();


        if (

                batteryDialogVisible

                || now - lastBatteryPromptAt < 30000L

        ) {


            return;
        }


        batteryDialogVisible = true;

        lastBatteryPromptAt = now;


        AlertDialog dialog =

                new AlertDialog.Builder(this)

                        .setTitle(

                                "Protección del seguimiento GPS"
                        )

                        .setMessage(

                                "La optimización de batería está activa para piOca.\n\n"

                                + "Android puede detener el envío de ubicación cuando se bloquea la pantalla.\n\n"

                                + "Para un seguimiento estable, configurá piOca sin optimización de batería."
                        )

                        .setPositiveButton(

                                "CONFIGURAR",

                                (d, which) -> {


                                    batteryDialogVisible = false;


                                    try {


                                        Intent batteryIntent =

                                                new Intent(

                                                        Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
                                                );


                                        batteryIntent.setData(

                                                Uri.parse(

                                                        "package:" + getPackageName()
                                                )
                                        );


                                        startActivity(

                                                batteryIntent
                                        );


                                    } catch (Exception e) {


                                        try {


                                            Intent fallback =

                                                    new Intent(

                                                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS
                                                    );


                                            fallback.setData(

                                                    Uri.parse(

                                                            "package:" + getPackageName()
                                                    )
                                            );


                                            startActivity(

                                                    fallback
                                            );


                                        } catch (Exception ignored) {
                                        }
                                    }
                                }
                        )

                        .setNegativeButton(

                                "AHORA NO",

                                (d, which) -> batteryDialogVisible = false
                        )

                        .create();


        dialog.setOnCancelListener(

                d -> batteryDialogVisible = false
        );


        dialog.show();
    }

    private boolean captureSharedDestination(
            Intent intent
    ) {

        if (intent == null) {
            return false;
        }

        String action =
                intent.getAction();

        if (!Intent.ACTION_SEND.equals(action)) {
            return false;
        }

        String type =
                intent.getType();

        if (
                type != null
                && !"text/plain".equalsIgnoreCase(type)
        ) {
            return false;
        }

        CharSequence extra =
                intent.getCharSequenceExtra(
                        Intent.EXTRA_TEXT
                );

        String shared =
                extra == null
                        ? ""
                        : extra.toString().trim();

        if (shared.isEmpty()) {
            return false;
        }

        getSharedPreferences(
                "pioca_tracking",
                MODE_PRIVATE
        )
        .edit()
        .putString(
                "pending_shared_destination",
                shared
        )
        .apply();

        return true;
    }


    private String consumePendingSharedDestination() {

        SharedPreferences prefs =
                getSharedPreferences(
                        "pioca_tracking",
                        MODE_PRIVATE
                );

        String shared =
                prefs.getString(
                        "pending_shared_destination",
                        ""
                );

        prefs.edit()
                .remove(
                        "pending_shared_destination"
                )
                .apply();

        return shared == null
                ? ""
                : shared.trim();
    }


    private void clearPendingSharedDestination() {

        getSharedPreferences(
                "pioca_tracking",
                MODE_PRIVATE
        )
        .edit()
        .remove(
                "pending_shared_destination"
        )
        .apply();
    }


    private void shareWhatsAppNative(
            String message
    ) {

        final String text =
                message == null
                        ? ""
                        : message.trim();

        if (text.isEmpty()) {
            return;
        }

        Intent base =
                new Intent(
                        Intent.ACTION_SEND
                );

        base.setType(
                "text/plain"
        );

        base.putExtra(
                Intent.EXTRA_TEXT,
                text
        );

        /*
         * Primero WhatsApp Business porque es el destino histórico
         * usado por piOca. Si no está instalado, se intenta WhatsApp
         * normal. En ambos casos NO se preselecciona contacto:
         * WhatsApp abre su selector de destinatario.
         */
        try {

            Intent business =
                    new Intent(base);

            business.setPackage(
                    "com.whatsapp.w4b"
            );

            startActivity(
                    business
            );

            return;

        } catch (Exception ignored) {
        }

        try {

            Intent normal =
                    new Intent(base);

            normal.setPackage(
                    "com.whatsapp"
            );

            startActivity(
                    normal
            );

            return;

        } catch (Exception ignored) {
        }

        try {

            startActivity(
                    Intent.createChooser(
                            base,
                            "Compartir seguimiento"
                    )
            );

        } catch (Exception ignored) {
        }
    }


    @Override
    protected void onNewIntent(
            Intent intent
    ) {

        super.onNewIntent(
                intent
        );

        setIntent(
                intent
        );

        boolean captured =
                captureSharedDestination(
                        intent
                );

        if (
                captured
                && web != null
        ) {

            web.post(() ->
                    web.loadUrl(
                            ADMIN
                    )
            );
        }
    }





    private void requestRuntimePermissions() {


        if (Build.VERSION.SDK_INT >= 33) {


            requestPermissions(

                    new String[]{

                            Manifest.permission.ACCESS_FINE_LOCATION,

                            Manifest.permission.READ_CONTACTS,

                            Manifest.permission.POST_NOTIFICATIONS

                    },

                    REQ_PERMISSIONS
            );


        } else {


            requestPermissions(

                    new String[]{

                            Manifest.permission.ACCESS_FINE_LOCATION,

                            Manifest.permission.READ_CONTACTS

                    },

                    REQ_PERMISSIONS
            );
        }
    }


    private void launchContactPicker() {


        try {


            Intent i =

                    new Intent(

                            Intent.ACTION_PICK,

                            ContactsContract.CommonDataKinds.Phone.CONTENT_URI
                    );


            startActivityForResult(

                    i,

                    REQ_CONTACT
            );


        } catch (Exception e) {


            if (web != null) {


                web.evaluateJavascript(

                        "(function(){"

                        + "var e=document.getElementById('contactoEstado');"

                        + "if(e){"

                        + "e.textContent='No se pudo abrir la agenda.';"

                        + "e.className='estado error';"

                        + "e.style.display='block';"

                        + "}"

                        + "})();",

                        null
                );
            }
        }
    }


    @Override
    protected void onActivityResult(

            int requestCode,

            int resultCode,

            Intent data) {


        super.onActivityResult(

                requestCode,

                resultCode,

                data
        );


        if (

                requestCode != REQ_CONTACT

                || resultCode != RESULT_OK

                || data == null

                || data.getData() == null

        ) {

            return;
        }


        Uri uri =
                data.getData();


        String name = "";

        String phone = "";


        Cursor cursor = null;


        try {


            cursor =

                    getContentResolver().query(

                            uri,

                            new String[]{

                                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,

                                    ContactsContract.CommonDataKinds.Phone.NUMBER

                            },

                            null,

                            null,

                            null
                    );


            if (

                    cursor != null

                    && cursor.moveToFirst()

            ) {


                int nameIndex =

                        cursor.getColumnIndex(

                                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME
                        );


                int phoneIndex =

                        cursor.getColumnIndex(

                                ContactsContract.CommonDataKinds.Phone.NUMBER
                        );


                if (nameIndex >= 0) {


                    name =
                            cursor.getString(
                                    nameIndex
                            );
                }


                if (phoneIndex >= 0) {


                    phone =
                            cursor.getString(
                                    phoneIndex
                            );
                }
            }


        } catch (Exception ignored) {


        } finally {


            if (cursor != null) {


                cursor.close();
            }
        }


        final String safeName =

                JSONObject.quote(

                        name == null

                                ? ""

                                : name
                );


        final String safePhone =

                JSONObject.quote(

                        phone == null

                                ? ""

                                : phone
                );


        web.evaluateJavascript(

                "(function(){"

                + "var n=document.getElementById('clientName');"

                + "var p=document.getElementById('clientPhone');"

                + "if(n)n.value="

                + safeName

                + ";"

                + "if(p)p.value="

                + safePhone

                + ";"

                + "var e=document.getElementById('contactoEstado');"

                + "if(e){"

                + "e.textContent='Contacto cargado.';"

                + "e.className='estado ok';"

                + "e.style.display='block';"

                + "}"

                + "})();",

                null
        );
    }


    private void showPendingEndDialog() {


        SharedPreferences prefs =

                getSharedPreferences(

                        "pioca_tracking",

                        MODE_PRIVATE
                );


        boolean pending =

                prefs.getBoolean(

                        "pending_finished_dialog",

                        false
                );


        if (!pending) {



      boolean dndAfterRealExpiry =
              prefs.getBoolean(
                      "dnd_restore_after_real_expiry",
                      false
              );

      if (dndAfterRealExpiry) {

          prefs.edit()
                  .putBoolean(
                          "dnd_restore_after_real_expiry",
                          false
                  )
                  .apply();

          showPendingDndRestoreDialog();
      }

            return;
        }


        String name =

                prefs.getString(

                        "finished_client_name",

                        ""
                );


        String who =

                name == null

                || name.trim().isEmpty()

                        ? "Este cliente"

                        : name.trim();


        prefs.edit()

                .putBoolean(

                        "pending_finished_dialog",

                        false
                )
                          .putBoolean(
                                  "dnd_restore_after_real_expiry",
                                  false
                          )

                .apply();


        new AlertDialog.Builder(this)

                .setTitle(

                        "Seguimiento finalizado"
                )

                .setMessage(

                        "El seguimiento de "

                        + who

                        + " ya no está activo.\n\n"

                        + "El cliente ya no puede ver la ubicación de la camioneta."
                )

                .setPositiveButton(

        "ACEPTAR",

        (d, which) -> showPendingDndRestoreDialog()
    )

    .show();
}


/* V9: utilidad manual; no se invoca durante el seguimiento. */
private void ensureDndAccess() {

    NotificationManager nm =
            (NotificationManager)
                    getSystemService(NOTIFICATION_SERVICE);

    if (nm == null
            || nm.isNotificationPolicyAccessGranted()
            || dndDialogVisible
            || isFinishing()) {
        return;
    }

    dndDialogVisible = true;

    AlertDialog dialog =
            new AlertDialog.Builder(this)
                    .setTitle("Silencio automático al llegar")
                    .setMessage(
                            "piOca puede activar No molestar cuando falten 2 minutos para llegar.\n\n"
                            + "Este permiso se configura una sola vez en Android.\n\n"
                            + "El seguimiento GPS funciona igual aunque no lo habilites."
                    )
                    .setPositiveButton(
                            "CONFIGURAR",
                            (d, which) -> {
                                dndDialogVisible = false;
                                try {
                                    startActivity(
                                            new Intent(
                                                    Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS
                                            )
                                    );
                                } catch (Exception ignored) {
                                }
                            }
                    )
                    .setNegativeButton(
                            "AHORA NO",
                            (d, which) -> dndDialogVisible = false
                    )
                    .create();

    dialog.setOnCancelListener(d -> dndDialogVisible = false);
    dialog.show();
}


private void showPendingDndRestoreDialog() {

    SharedPreferences prefs =
            getSharedPreferences("pioca_tracking", MODE_PRIVATE);

    if (!prefs.getBoolean("dnd_restore_pending", false)) {
        return;
    }

    if (dndRestoreDialogVisible || isFinishing()) {
        return;
    }

    NotificationManager nm =
            (NotificationManager)
                    getSystemService(NOTIFICATION_SERVICE);

    if (nm == null || !nm.isNotificationPolicyAccessGranted()) {
        dndRestoreDialogVisible = false;
        return;
    }

    if (nm.getCurrentInterruptionFilter()
            == NotificationManager.INTERRUPTION_FILTER_ALL) {

        prefs.edit()
                .putBoolean("dnd_restore_pending", false)
                .putBoolean("dnd_activated_by_pioca", false)
                .remove("dnd_previous_filter")
                .apply();
        dndRestoreDialogVisible = false;
        return;
    }

    dndRestoreDialogVisible = true;

    AlertDialog dialog =
            new AlertDialog.Builder(this)
            .setTitle("Seguimiento finalizado")
            .setMessage(
                    "No molestar sigue activo.\n\n"
                    + "Confirmá cuando quieras quitar el silencio."
            )
            .setPositiveButton(
                    "QUITAR SILENCIO",
                    (d, which) -> {
                        try {
                            int previous = prefs.getInt(
                                    "dnd_previous_filter",
                                    NotificationManager.INTERRUPTION_FILTER_ALL
                            );

                            nm.setInterruptionFilter(previous);

                            prefs.edit()
                                    .putBoolean("dnd_restore_pending", false)
                                    .putBoolean("dnd_activated_by_pioca", false)
                                    .remove("dnd_previous_filter")
                                    .apply();
                        } catch (Exception ignored) {
                        }

                        dndRestoreDialogVisible = false;
                    }
            )
            .create();

    /* Si se cierra sin confirmar, el silencio queda activo. */
    dialog.setOnCancelListener(
            d -> dndRestoreDialogVisible = false
    );

    dialog.setOnDismissListener(
            d -> dndRestoreDialogVisible = false
    );

    dialog.show();
}



    public class NativeBridge {


        

        @JavascriptInterface
        public String consumeSharedDestination() {

            return consumePendingSharedDestination();
        }


        @JavascriptInterface
        public void shareWhatsApp(
                String message
        ) {

            runOnUiThread(() ->
                    shareWhatsAppNative(
                            message
                    )
            );
        }


@JavascriptInterface
        public void pickContact() {


            runOnUiThread(

                    MainActivity.this::launchContactPicker
            );
        }


        @JavascriptInterface
        public void startTracking(

                String code,

                String accessToken,

                String refreshToken,

                String clientName,

                String expiresAt) {


            runOnUiThread(() -> {


                
      ensureDndAccess();
checkBatteryOptimization();


                if (

                        checkSelfPermission(

                                Manifest.permission.ACCESS_FINE_LOCATION)

                        != PackageManager.PERMISSION_GRANTED

                ) {


                    requestRuntimePermissions();


                    return;
                }


                Intent service =

                        new Intent(

                                MainActivity.this,

                                TrackingService.class
                        );


                service.putExtra(

                        "tracking",

                        code
                );


                service.putExtra(

                        "access_token",

                        accessToken
                );


                service.putExtra(

                        "refresh_token",

                        refreshToken
                );


                service.putExtra(

                        "client_name",

                        clientName
                );


                service.putExtra(

                        "expires_at",

                        expiresAt
                );


                if (Build.VERSION.SDK_INT >= 26) {


                    startForegroundService(

                            service
                    );


                } else {


                    startService(

                            service
                    );
                }
            });
        }


        @JavascriptInterface
        public void stopTracking() {


            runOnUiThread(() -> {


                SharedPreferences prefs =

                        getSharedPreferences(

                                "pioca_tracking",

                                MODE_PRIVATE
                        );


                prefs.edit()

                        .putBoolean(

                                "service_active",

                                false
                        )

                        .remove(

                                "tracking_code"
                        )

                        .remove(

                                "access_token"
                        )

                        .remove(

                                "refresh_token"
                        )

                        .remove(

                                "client_name"
                        )

                        .remove(

                                "expires_at"
                        )

                        .apply();


                stopService(

                        new Intent(

                                MainActivity.this,

                                TrackingService.class
                        )
                );


                          if (web != null) {


                              web.postDelayed(

                                      MainActivity.this::showPendingDndRestoreDialog,

                                      350
                              );
                          }
            });
        }
    }


    @Override
    public void onBackPressed() {


        /*
         * REFUERZO PREVIEW TÉCNICO
         *
         * Si estamos viendo cliente.html con preview=1,
         * bloqueamos únicamente el botón/gesto ATRÁS de Android.
         *
         * Así el preview técnico no vuelve accidentalmente
         * al panel ETA por una acción de sistema.
         *
         * El botón naranja "Volver al panel" sigue funcionando
         * desde JavaScript exactamente como hasta ahora.
         */
        if (web != null) {


            String currentUrl =
                    web.getUrl();


            if (

                    currentUrl != null

                    && currentUrl.contains(
                            "/pioca-gps/cliente.html"
                    )

                    && currentUrl.contains(
                            "preview=1"
                    )

            ) {


                return;
            }


            if (web.canGoBack()) {


                web.goBack();

                return;
            }
        }


        super.onBackPressed();
    }
}

