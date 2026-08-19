from pathlib import Path
import re

gradle = Path('android-pioca/app/build.gradle')
manifest = Path('android-pioca/app/src/main/AndroidManifest.xml')
main = Path('android-pioca/app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java')
service = Path('android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java')


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit('ERROR PATCH ' + label)
    return text.replace(old, new, 1)


def re_once(text, pattern, repl, label, flags=0):
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit('ERROR PATCH ' + label)
    return out


def re_once_literal(text, pattern, repl, label, flags=0):
    rx = re.compile(pattern, flags)
    match = rx.search(text)
    if not match:
        raise SystemExit('ERROR PATCH ' + label)

    return (
        text[:match.start()]
        + repl
        + text[match.end():]
    )

# ----------------------------------------------------------
# VERSION
# ----------------------------------------------------------
t = gradle.read_text(encoding='utf-8')
t = replace_once(t, 'versionCode 7', 'versionCode 8', 'versionCode')
t = replace_once(t, 'versionName "0.7"', 'versionName "0.8-silencio"', 'versionName')
gradle.write_text(t, encoding='utf-8')

# ----------------------------------------------------------
# MANIFEST - acceso especial a No molestar
# ----------------------------------------------------------
t = manifest.read_text(encoding='utf-8')
if 'android.permission.ACCESS_NOTIFICATION_POLICY' not in t:
    t = re_once(
        t,
        r'(<uses-permission\s*\n\s*android:name="android\.permission\.POST_NOTIFICATIONS"\s*/>)',
        r'\1\n\n  <uses-permission\n    android:name="android.permission.ACCESS_NOTIFICATION_POLICY"/>',
        'ACCESS_NOTIFICATION_POLICY'
    )
manifest.write_text(t, encoding='utf-8')

# ----------------------------------------------------------
# MAIN ACTIVITY
# ----------------------------------------------------------
t = main.read_text(encoding='utf-8')

if 'import android.app.NotificationManager;' not in t:
    t = replace_once(
        t,
        'import android.app.AlertDialog;\n',
        'import android.app.AlertDialog;\n\nimport android.app.NotificationManager;\n',
        'import NotificationManager MainActivity'
    )

# Campo para evitar múltiples diálogos de permiso.
t = re_once(
    t,
    r'(private long lastBatteryPromptAt\s*=\s*0L;)',
    r'\1\n\nprivate boolean dndDialogVisible = false;\n\nprivate boolean dndRestoreDialogVisible = false;',
    'campo dndDialogVisible'
)

# Cuando acepta el cartel de finalización, ofrecer quitar silencio.
t = re_once_literal(
    t,
    r'\.setPositiveButton\(\s*"ACEPTAR",\s*null\s*\)\s*\.show\(\);\s*\n\s*\}',
    '''.setPositiveButton(\n\n        "ACEPTAR",\n\n        (d, which) -> showPendingDndRestoreDialog()\n    )\n\n    .show();\n}\n\n\n/* V9: utilidad manual; no se invoca durante el seguimiento. */\nprivate void ensureDndAccess() {\n\n    NotificationManager nm =\n            (NotificationManager)\n                    getSystemService(NOTIFICATION_SERVICE);\n\n    if (nm == null\n            || nm.isNotificationPolicyAccessGranted()\n            || dndDialogVisible\n            || isFinishing()) {\n        return;\n    }\n\n    dndDialogVisible = true;\n\n    AlertDialog dialog =\n            new AlertDialog.Builder(this)\n                    .setTitle("Silencio automático al llegar")\n                    .setMessage(\n                            "piOca puede activar No molestar cuando falten 3 minutos para llegar.\\n\\n"\n                            + "Este permiso se configura una sola vez en Android.\\n\\n"\n                            + "El seguimiento GPS funciona igual aunque no lo habilites."\n                    )\n                    .setPositiveButton(\n                            "CONFIGURAR",\n                            (d, which) -> {\n                                dndDialogVisible = false;\n                                try {\n                                    startActivity(\n                                            new Intent(\n                                                    Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS\n                                            )\n                                    );\n                                } catch (Exception ignored) {\n                                }\n                            }\n                    )\n                    .setNegativeButton(\n                            "AHORA NO",\n                            (d, which) -> dndDialogVisible = false\n                    )\n                    .create();\n\n    dialog.setOnCancelListener(d -> dndDialogVisible = false);\n    dialog.show();\n}\n\n\nprivate void showPendingDndRestoreDialog() {\n\n    SharedPreferences prefs =\n            getSharedPreferences("pioca_tracking", MODE_PRIVATE);\n\n    if (!prefs.getBoolean("dnd_restore_pending", false)) {\n        return;\n    }\n\n    if (dndRestoreDialogVisible || isFinishing()) {\n        return;\n    }\n\n    NotificationManager nm =\n            (NotificationManager)\n                    getSystemService(NOTIFICATION_SERVICE);\n\n    if (nm == null || !nm.isNotificationPolicyAccessGranted()) {\n        dndRestoreDialogVisible = false;\n        return;\n    }\n\n    if (nm.getCurrentInterruptionFilter()\n            == NotificationManager.INTERRUPTION_FILTER_ALL) {\n\n        prefs.edit()\n                .putBoolean("dnd_restore_pending", false)\n                .putBoolean("dnd_activated_by_pioca", false)\n                .remove("dnd_previous_filter")\n                .apply();\n        dndRestoreDialogVisible = false;\n        return;\n    }\n\n    dndRestoreDialogVisible = true;\n\n    AlertDialog dialog =\n            new AlertDialog.Builder(this)\n            .setTitle("Seguimiento finalizado")\n            .setMessage(\n                    "No molestar sigue activo.\\n\\n"\n                    + "Confirmá cuando quieras quitar el silencio."\n            )\n            .setPositiveButton(\n                    "QUITAR SILENCIO",\n                    (d, which) -> {\n                        try {\n                            int previous = prefs.getInt(\n                                    "dnd_previous_filter",\n                                    NotificationManager.INTERRUPTION_FILTER_ALL\n                            );\n\n                            nm.setInterruptionFilter(previous);\n\n                            prefs.edit()\n                                    .putBoolean("dnd_restore_pending", false)\n                                    .putBoolean("dnd_activated_by_pioca", false)\n                                    .remove("dnd_previous_filter")\n                                    .apply();\n                        } catch (Exception ignored) {\n                        }\n\n                        dndRestoreDialogVisible = false;\n                    }\n            )\n            .create();\n\n    /* Si se cierra sin confirmar, el silencio queda activo. */\n    dialog.setOnCancelListener(\n            d -> dndRestoreDialogVisible = false\n    );\n\n    dialog.setOnDismissListener(\n            d -> dndRestoreDialogVisible = false\n    );\n\n    dialog.show();\n}\n''',
    'metodos DND MainActivity',
    re.S
)

# El permiso especial se solicita sólo si todavía no fue concedido.
# Una vez concedido, la activación a los 3 minutos es automática y sin preguntas.
t = re_once(
    t,
    r'(public void startTracking\([\s\S]*?runOnUiThread\(\(\) -> \{\s*)',
    r'\1\n      ensureDndAccess();\n',
    'ensureDndAccess startTracking'
)


# Al finalizar manualmente desde el panel, preguntar inmediatamente
# si se desea quitar el No molestar que piOca activó.
t = re_once(
    t,
    r'(public void stopTracking\(\)\s*\{[\s\S]*?stopService\(\s*new Intent\(\s*MainActivity\.this,\s*TrackingService\.class\s*\)\s*\);)',
    r'''\1


                          if (web != null) {


                              web.postDelayed(

                                      MainActivity.this::showPendingDndRestoreDialog,

                                      350
                              );
                          }''',
    'pregunta DND al finalizar manual',
    re.S
)

main.write_text(t, encoding='utf-8')

# ----------------------------------------------------------
# TRACKING SERVICE
# ----------------------------------------------------------
t = service.read_text(encoding='utf-8')

# Estado de No molestar y ETA real.
t = re_once(
    t,
    r'(private volatile boolean ending\s*=\s*false;)',
    r'''\1

private static final long DND_BEFORE_ARRIVAL_MS =
        3L * 60L * 1000L;

private static final long TRACKING_AFTER_ARRIVAL_MS =
        5L * 60L * 1000L;

private volatile long clientArrivalMillis = 0L;
private volatile boolean dndHandled = false;''',
    'campos DND TrackingService'
)

# Evaluación cada heartbeat (el servicio ya vive con pantalla bloqueada).
t = re_once(
    t,
    r'(long now\s*=\s*System\.currentTimeMillis\(\);)',
    r'''\1

      maybeEnableDnd(now);''',
    'heartbeat maybeEnableDnd'
)

# Restaurar estado si Android reinicia el servicio.
t = re_once(
    t,
    r'(if \(\s*!loaded\s*\|\|\s*code\.isEmpty\(\)\s*\) \{[\s\S]*?return START_NOT_STICKY;\s*\})',
    r'''\1


dndHandled = prefs.getBoolean(
        "dnd_activated_by_pioca",
        false
);''',
    'restore dndHandled',
    re.S
)

# Persistir ETA.
t = re_once(
    t,
    r'(\.putLong\(\s*"expires_at",\s*expiresAtMillis\s*\))',
    r'''\1

        .putLong(
                "client_arrival",
                clientArrivalMillis
        )''',
    'save clientArrival'
)

# Al recibir expires_at desde MainActivity, reconstruir ETA inmediatamente.
# Arquitectura piOca: expires_at = client_arrival + 5 minutos.
t = re_once(
    t,
    r'(expiresAtMillis\s*=\s*parseTime\(\s*i\.getStringExtra\(\s*"expires_at"\s*\)\s*\);)',
    r'''\1

clientArrivalMillis =
        expiresAtMillis > TRACKING_AFTER_ARRIVAL_MS
                ? expiresAtMillis - TRACKING_AFTER_ARRIVAL_MS
                : 0L;''',
    'derive clientArrival from incoming expires',
    re.S
)

# Restaurar ETA.
t = re_once(
    t,
    r'(expiresAtMillis\s*=\s*prefs\.getLong\(\s*"expires_at",\s*0L\s*\);)',
    r'''\1


clientArrivalMillis = prefs.getLong(
        "client_arrival",
        0L
);

if (clientArrivalMillis <= 0
        && expiresAtMillis > TRACKING_AFTER_ARRIVAL_MS) {

    clientArrivalMillis =
            expiresAtMillis -
            TRACKING_AFTER_ARRIVAL_MS;
}''',
    'restore clientArrival'
)

# Limpiar ETA cuando finaliza seguimiento, pero conservar flags DND hasta decisión del usuario.
t = re_once(
    t,
    r'(\.remove\(\s*"expires_at"\s*\))',
    r'''\1

        .remove("client_arrival")''',
    'clear clientArrival'
)

# Actualizar ETA desde el snapshot existente de Supabase.
t = re_once(
    t,
    r'(if \(\s*r\.state == RemoteState\.ACTIVE\s*\) \{)',
    r'''\1


    long arrival =
            r.expiresAt > TRACKING_AFTER_ARRIVAL_MS
                    ? r.expiresAt - TRACKING_AFTER_ARRIVAL_MS
                    : 0L;

    if (arrival > 0) {
        clientArrivalMillis = arrival;
        saveActiveConfig();
    }''',
    'refresh clientArrival'
)

# Función para leer client_arrival de get_tracking_snapshot, RPC que ya existe en V7.
insert_before_send = r'''

private long loadClientArrival() {

    HttpURLConnection c = null;

    try {
        URL url = new URL(
                BASE + "/rest/v1/rpc/get_tracking_snapshot"
        );

        c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setConnectTimeout(10000);
        c.setReadTimeout(10000);
        c.setRequestProperty("apikey", KEY);
        c.setRequestProperty("Content-Type", "application/json");

        JSONObject body = new JSONObject();
        body.put("p_code", code);

        try (OutputStream os = c.getOutputStream()) {
            os.write(
                    body.toString().getBytes(StandardCharsets.UTF_8)
            );
        }

        int status = c.getResponseCode();
        if (status < 200 || status >= 300) {
            return 0L;
        }

        JSONArray arr = new JSONArray(
                readBody(c.getInputStream())
        );

        if (arr.length() == 0) {
            return 0L;
        }

        JSONObject row = arr.getJSONObject(0);

        return parseTime(
                row.optString("client_arrival", "")
        );

    } catch (Exception e) {
        return 0L;

    } finally {
        if (c != null) {
            c.disconnect();
        }
    }
}


private void maybeEnableDnd(long now) {

    if (clientArrivalMillis <= 0) {
        return;
    }

    NotificationManager nm =
            (NotificationManager)
                    getSystemService(NOTIFICATION_SERVICE);

    if (nm == null || !nm.isNotificationPolicyAccessGranted()) {
        return;
    }

    long triggerAt =
            clientArrivalMillis - DND_BEFORE_ARRIVAL_MS;

    boolean activatedByPioca =
            prefs.getBoolean(
                    "dnd_activated_by_pioca",
                    false
            );

    /*
     * Si el técnico atrasó la ETA y volvimos a estar
     * a MÁS de 3 minutos, piOca deshace solamente
     * el No molestar que ella misma había activado.
     */
    if (now < triggerAt) {

        if (activatedByPioca) {

            int previous =
                    prefs.getInt(
                            "dnd_previous_filter",
                            NotificationManager.INTERRUPTION_FILTER_ALL
                    );

            try {
                nm.setInterruptionFilter(previous);
            } catch (Exception ignored) {
            }

            prefs.edit()
                    .putBoolean(
                            "dnd_activated_by_pioca",
                            false
                    )
                    .putBoolean(
                            "dnd_restore_pending",
                            false
                    )
                    .remove(
                            "dnd_previous_filter"
                    )
                    .apply();
        }

        dndHandled = false;
        return;
    }

    /*
     * Ya estamos dentro de los 3 minutos.
     * Si piOca ya lo activó, no hacemos nada más.
     */
    if (activatedByPioca) {
        dndHandled = true;
        return;
    }

    int current =
            nm.getCurrentInterruptionFilter();

    /*
     * Si el teléfono ya estaba en No molestar por decisión
     * del usuario, piOca no lo modifica ni se adjudica el estado.
     */
    if (current != NotificationManager.INTERRUPTION_FILTER_ALL) {
        dndHandled = false;
        return;
    }

    try {

        prefs.edit()
                .putInt(
                        "dnd_previous_filter",
                        current
                )
                .apply();

        nm.setInterruptionFilter(
                NotificationManager.INTERRUPTION_FILTER_PRIORITY
        );

        /*
         * Samsung puede tardar unos instantes en reflejar el nuevo filtro.
         * Si setInterruptionFilter() no lanzó excepción, piOca registra
         * inmediatamente que fue quien activó No molestar.
         */
        prefs.edit()
                .putBoolean(
                        "dnd_activated_by_pioca",
                        true
                )
                .putBoolean(
                        "dnd_restore_pending",
                        true
                )
                .apply();

        dndHandled = true;

    } catch (Exception ignored) {

        dndHandled = false;
    }
}


'''

t = re_once(
    t,
    r'(private void sendAsync\s*\(\s*Location l\s*\) \{)',
    insert_before_send + r'\1',
    'insert loadClientArrival and maybeEnableDnd'
)

service.write_text(t, encoding='utf-8')

print('V8 silencio aplicada correctamente: No molestar 3 min antes de la ETA.')
