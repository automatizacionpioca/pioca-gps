from pathlib import Path
import re

gradle = Path("android-pioca/app/build.gradle")
manifest = Path("android-pioca/app/src/main/AndroidManifest.xml")
main = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java"
)


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR V10 MAPS SHARE: " + label)
    return text.replace(old, new, 1)


def re_once(text, pattern, repl, label, flags=0):
    out, n = re.subn(
        pattern,
        repl,
        text,
        count=1,
        flags=flags,
    )

    if n != 1:
        raise SystemExit("ERROR V10 MAPS SHARE: " + label)

    return out


# ==========================================================
# VERSION
# Parte de V9 estable YA aplicada.
# ==========================================================

t = gradle.read_text(encoding="utf-8")

t = replace_once(
    t,
    "versionCode 9",
    "versionCode 10",
    "versionCode",
)

t = replace_once(
    t,
    'versionName "0.9-estable-2s"',
    'versionName "0.10-maps-share"',
    "versionName",
)

gradle.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# MANIFEST
#
# Se conserva MAIN/LAUNCHER y se AGREGA ACTION_SEND text/plain
# para que piOca aparezca en "Compartir" de Google Maps.
# ==========================================================

t = manifest.read_text(encoding="utf-8")

t = re_once(
    t,
    r'(<activity\s*\n\s*android:name="\.MainActivity"\s*\n\s*android:exported="true")(\s*>)',
    r'''\1
      android:launchMode="singleTop"\2''',
    "launchMode singleTop",
    re.S,
)

launcher_block = r'''
      <intent-filter>

        <action
          android:name="android.intent.action.MAIN"/>

        <category
          android:name="android.intent.category.LAUNCHER"/>

      </intent-filter>
'''

share_block = r'''
      <intent-filter>

        <action
          android:name="android.intent.action.SEND"/>

        <category
          android:name="android.intent.category.DEFAULT"/>

        <data
          android:mimeType="text/plain"/>

      </intent-filter>
'''

if share_block.strip() in t:
    raise SystemExit(
        "ERROR V10 MAPS SHARE: ACTION_SEND ya estaba presente"
    )

t = replace_once(
    t,
    launcher_block,
    launcher_block + "\n" + share_block,
    "intent-filter ACTION_SEND",
)

manifest.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# MAIN ACTIVITY
# ==========================================================

t = main.read_text(encoding="utf-8")

# ----------------------------------------------------------
# 1) Capturar el contenido compartido también en arranque frío.
# ----------------------------------------------------------

t = re_once(
    t,
    r'(super\.onCreate\(state\);)',
    r'''\1


        captureSharedDestination(
                getIntent()
        );''',
    "captura share en onCreate",
)

# ----------------------------------------------------------
# 2) Cuando el WebView entra al panel activo, cualquier share
#    que no pudo usarse por existir un seguimiento previo se
#    descarta. Evita que quede pendiente para otro servicio.
# ----------------------------------------------------------

t = re_once(
    t,
    r'(if \(url\.contains\(\s*"/pioca-gps/index\.html"\s*\)\) \{)',
    r'''\1


                            clearPendingSharedDestination();''',
    "limpieza de share pendiente al entrar a index",
    re.S,
)

# ----------------------------------------------------------
# 3) Métodos nativos para:
#    - extraer ACTION_SEND;
#    - persistirlo hasta que admin.html lo consuma;
#    - recibir un share cuando la app ya está abierta;
#    - compartir WhatsApp sin destinatario preseleccionado.
# ----------------------------------------------------------

native_helpers = r'''

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


'''

t = re_once(
    t,
    r'(\n\s*private void requestRuntimePermissions\(\) \{)',
    native_helpers + r'\1',
    "helpers share antes de permisos",
)

# ----------------------------------------------------------
# 4) Puente JavaScript esperado por admin.html e index.html.
# ----------------------------------------------------------

bridge_methods = r'''

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


'''

t = re_once(
    t,
    r'(public class NativeBridge \{\s*)',
    r'\1' + bridge_methods,
    "métodos NativeBridge share",
    re.S,
)

main.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# VALIDACIONES
# ==========================================================

gradle_text = gradle.read_text(encoding="utf-8")
manifest_text = manifest.read_text(encoding="utf-8")
main_text = main.read_text(encoding="utf-8")

checks = [
    (
        'versionCode 10',
        gradle_text,
        "versionCode 10",
    ),
    (
        'versionName "0.10-maps-share"',
        gradle_text,
        "versionName V10",
    ),
    (
        'android.intent.action.SEND',
        manifest_text,
        "ACTION_SEND",
    ),
    (
        'android:mimeType="text/plain"',
        manifest_text,
        "MIME text/plain",
    ),
    (
        'android:launchMode="singleTop"',
        manifest_text,
        "singleTop",
    ),
    (
        'consumeSharedDestination',
        main_text,
        "bridge consumeSharedDestination",
    ),
    (
        'shareWhatsApp',
        main_text,
        "bridge shareWhatsApp",
    ),
    (
        'pending_shared_destination',
        main_text,
        "persistencia share pendiente",
    ),
    (
        'com.whatsapp.w4b',
        main_text,
        "WhatsApp Business",
    ),
    (
        'com.whatsapp',
        main_text,
        "WhatsApp normal",
    ),
]

for needle, haystack, label in checks:
    if needle not in haystack:
        raise SystemExit(
            "ERROR V10 MAPS SHARE: falta " + label
        )

# Protección V9: no se toca TrackingService en este parche.
service = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java"
)

service_text = service.read_text(
    encoding="utf-8"
)

if not re.search(
    r'LocationManager\.GPS_PROVIDER,\s*2000L',
    service_text,
    re.S,
):
    raise SystemExit(
        "ERROR V10 MAPS SHARE: se perdió GPS V9 a 2 segundos"
    )

if "maybeEnableDnd" not in service_text:
    raise SystemExit(
        "ERROR V10 MAPS SHARE: se perdió No molestar V8/V9"
    )

print(
    "V10 MAPS SHARE aplicada: "
    "ACTION_SEND Google Maps + destino pendiente + "
    "WhatsApp nativo sin destinatario. "
    "TrackingService V9 quedó intacto."
)
