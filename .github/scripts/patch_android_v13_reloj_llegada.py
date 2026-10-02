from pathlib import Path
import re

gradle = Path("android-pioca/app/build.gradle")
main = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java"
)
service = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java"
)


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR V13 RELOJ LLEGADA: " + label)
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
        raise SystemExit("ERROR V13 RELOJ LLEGADA: " + label)

    return out


# ==========================================================
# VERSION
# Parte de V12 ETA Freeze YA aplicada.
# ==========================================================

t = gradle.read_text(encoding="utf-8")

t = replace_once(
    t,
    "versionCode 12",
    "versionCode 13",
    "versionCode",
)

t = replace_once(
    t,
    'versionName "0.12-eta-freeze"',
    'versionName "0.13-reloj-llegada"',
    "versionName",
)

gradle.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# MAIN ACTIVITY
#
# El permiso de No Molestar se explica con el nuevo umbral:
# entra al llegar a <= 2 minutos.
# ==========================================================

t = main.read_text(encoding="utf-8")

t = replace_once(
    t,
    "piOca puede activar No molestar cuando falten 3 minutos para llegar.",
    "piOca puede activar No molestar cuando falten 2 minutos para llegar.",
    "texto permiso DND 2 min",
)

main.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# TRACKING SERVICE
#
# V13:
# - ETA dinámica mientras no llegó T0;
# - No Molestar entra en <= 2 min;
# - No Molestar sale recién en >= 4 min si piOca lo activó;
# - entre 2 y 4 min conserva el estado (histéresis);
# - al alcanzar T0 se enclava la llegada;
# - desde T0 nace un reloj NATIVO fijo de 5 min;
# - antes de T0 expiresAtMillis NO puede cerrar el servicio;
# - T0 + 5 corta GPS/servicio;
# - V12 sigue congelando ETA desde T0;
# - Supabase conserva expires_at como respaldo de T0 + 5.
# ==========================================================

t = service.read_text(encoding="utf-8")


# ----------------------------------------------------------
# 1) Histéresis No Molestar: entra 2 min / sale 4 min.
# ----------------------------------------------------------

t = re_once(
    t,
    r'''private static final long DND_BEFORE_ARRIVAL_MS\s*=\s*3L\s*\*\s*60L\s*\*\s*1000L;''',
    '''private static final long DND_ENTER_BEFORE_ARRIVAL_MS =
        2L * 60L * 1000L;

private static final long DND_EXIT_BEFORE_ARRIVAL_MS =
        4L * 60L * 1000L;''',
    "constantes DND 2/4",
    flags=re.S,
)


# ----------------------------------------------------------
# 2) Latch nativo de T0.
#
# No hace falta persistir otra hora:
# clientArrivalMillis ya se guarda en SharedPreferences.
# V12 la congela al llegar a T0. Si Android reinicia el servicio,
# el latch se reconstruye usando exactamente ese mismo T0.
# ----------------------------------------------------------

t = re_once(
    t,
    r'''(private volatile boolean dndHandled\s*=\s*false;)''',
    r'''\1

private volatile long arrivalReachedAtMillis =
        0L;''',
    "campo arrivalReachedAtMillis",
)


# Si MainActivity vuelve a iniciar el servicio, el latch se
# reconstruirá en el próximo heartbeat desde clientArrivalMillis.
t = re_once(
    t,
    r'''(clientArrivalMillis\s*=\s*expiresAtMillis\s*>\s*TRACKING_AFTER_ARRIVAL_MS\s*\?\s*expiresAtMillis\s*-\s*TRACKING_AFTER_ARRIVAL_MS\s*:\s*0L;)''',
    r'''\1

arrivalReachedAtMillis =
        0L;''',
    "reset latch al iniciar servicio",
    flags=re.S,
)


# ----------------------------------------------------------
# 3) Motor de llegada.
#
# Antes de T0 NO existe reloj de cierre.
# Al alcanzar T0 se fija arrivalReachedAtMillis = clientArrivalMillis.
# El deadline local queda T0 + 5 minutos y ya no se mueve.
# ----------------------------------------------------------

arrival_engine = r'''

private void maybeLatchArrivalAndFinish(
        long now
) {

    if (
            arrivalReachedAtMillis <= 0
            && clientArrivalMillis > 0
            && now >= clientArrivalMillis
    ) {

        /*
         * T0 real alcanzado.
         * V12 ya impide que Google vuelva a mover clientArrivalMillis.
         * Usamos la hora exacta de T0, no la hora del heartbeat,
         * para que los cinco minutos sean precisos y reconstruibles.
         */
        arrivalReachedAtMillis =
                clientArrivalMillis;


        expiresAtMillis =
                arrivalReachedAtMillis
                + TRACKING_AFTER_ARRIVAL_MS;


        saveActiveConfig();
    }


    if (
            arrivalReachedAtMillis > 0
            && now >= (
                    arrivalReachedAtMillis
                    + TRACKING_AFTER_ARRIVAL_MS
            )
    ) {

        finishExpired();
    }
}


'''

t = re_once(
    t,
    r'''(private void maybeEnableDnd\(long now\) \{)''',
    arrival_engine + r'''\1''',
    "motor reloj llegada",
)


# ----------------------------------------------------------
# 4) Reemplazar la lógica DND vieja por histéresis 2/4.
# ----------------------------------------------------------

dnd_method = r'''private void maybeEnableDnd(long now) {

    if (clientArrivalMillis <= 0) {
        return;
    }

    NotificationManager nm =
            (NotificationManager)
                    getSystemService(NOTIFICATION_SERVICE);

    if (nm == null || !nm.isNotificationPolicyAccessGranted()) {
        return;
    }


    long remaining =
            clientArrivalMillis - now;


    boolean activatedByPioca =
            prefs.getBoolean(
                    "dnd_activated_by_pioca",
                    false
            );


    /*
     * HISTÉRESIS 2 / 4:
     *
     * - si piOca ya activó No Molestar, lo conserva mientras
     *   la ETA siga por debajo de 4 minutos;
     * - si una equivocación de camino hace subir la ETA a 4 min
     *   o más, restaura el estado anterior;
     * - entre 2 y 4 min no prende/apaga repetidamente.
     */
    if (activatedByPioca) {

        if (
                remaining >= DND_EXIT_BEFORE_ARRIVAL_MS
                && arrivalReachedAtMillis <= 0
        ) {

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

            dndHandled = false;
            return;
        }

        dndHandled = true;
        return;
    }


    /*
     * Si todavía faltan MÁS de 2 minutos, no lo activamos.
     * Entre 2 y 4 minutos, si estaba apagado, continúa apagado.
     */
    if (remaining > DND_ENTER_BEFORE_ARRIVAL_MS) {
        dndHandled = false;
        return;
    }


    int current =
            nm.getCurrentInterruptionFilter();


    /*
     * Si el teléfono ya estaba en No Molestar por decisión
     * del usuario, piOca no lo modifica ni se adjudica ese estado.
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
    r'''private void maybeEnableDnd\(long now\) \{.*?\n\}\n\n\n(?=private void sendAsync)''',
    dnd_method,
    "método DND 2/4",
    flags=re.S,
)


# ----------------------------------------------------------
# 5) Heartbeat:
#    elimina el cierre directo por expiresAtMillis.
#    El único reloj local de cierre nace en T0.
# ----------------------------------------------------------

t = re_once(
    t,
    r'''(maybeRefreshRouteEta\(now\);\s*)\n\s*if\s*\(\s*expiresAtMillis\s*>\s*0\s*&&\s*now\s*>=\s*expiresAtMillis\s*\)\s*\{\s*finishExpired\(\);\s*return;\s*\}''',
    r'''\1

      maybeLatchArrivalAndFinish(now);

      if (ending) {

          return;
      }''',
    "heartbeat reloj T0+5",
    flags=re.S,
)


# ----------------------------------------------------------
# 6) onLocationChanged:
#    tampoco puede cerrar por un expires_at móvil/pre-T0.
# ----------------------------------------------------------

t = re_once(
    t,
    r'''(last\s*=\s*l;\s*)\n\s*if\s*\(\s*expiresAtMillis\s*>\s*0\s*&&\s*System\.currentTimeMillis\(\)\s*>=\s*expiresAtMillis\s*\)\s*\{\s*finishExpired\(\);\s*return;\s*\}''',
    r'''\1

                  long arrivalNow =
                          System.currentTimeMillis();


                  maybeLatchArrivalAndFinish(
                          arrivalNow
                  );


                  if (ending) {

                      return;
                  }''',
    "location reloj T0+5",
    flags=re.S,
)


service.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# VALIDACIONES
# ==========================================================

final_service = service.read_text(encoding="utf-8")
final_main = main.read_text(encoding="utf-8")
final_gradle = gradle.read_text(encoding="utf-8")

checks = [
    (
        'versionName "0.13-reloj-llegada"',
        final_gradle,
        "versionName V13",
    ),
    (
        'DND_ENTER_BEFORE_ARRIVAL_MS',
        final_service,
        "umbral entrada DND",
    ),
    (
        'DND_EXIT_BEFORE_ARRIVAL_MS',
        final_service,
        "umbral salida DND",
    ),
    (
        'arrivalReachedAtMillis',
        final_service,
        "latch T0",
    ),
    (
        'maybeLatchArrivalAndFinish(now)',
        final_service,
        "reloj T0+5 en heartbeat",
    ),
    (
        'now >= clientArrivalMillis',
        final_service,
        "freeze V12 preservado",
    ),
    (
        'etaApplyNow >= clientArrivalMillis',
        final_service,
        "anti-carrera V12 preservada",
    ),
    (
        'maybeRefreshRouteEta(now)',
        final_service,
        "ETA dinámica preservada",
    ),
    (
        'cuando falten 2 minutos para llegar',
        final_main,
        "texto DND 2 min",
    ),
]

for needle, haystack, label in checks:
    if needle not in haystack:
        raise SystemExit(
            "ERROR V13 RELOJ LLEGADA: falta " + label
        )


if "DND_BEFORE_ARRIVAL_MS" in final_service:
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: quedó el umbral DND viejo"
    )


if not re.search(
    r'DND_ENTER_BEFORE_ARRIVAL_MS\s*=\s*2L\s*\*\s*60L\s*\*\s*1000L',
    final_service,
    re.S,
):
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: entrada DND no quedó en 2 min"
    )


if not re.search(
    r'DND_EXIT_BEFORE_ARRIVAL_MS\s*=\s*4L\s*\*\s*60L\s*\*\s*1000L',
    final_service,
    re.S,
):
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: salida DND no quedó en 4 min"
    )


if not re.search(
    r'arrivalReachedAtMillis\s*\+\s*TRACKING_AFTER_ARRIVAL_MS',
    final_service,
    re.S,
):
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: falta deadline fijo T0+5"
    )


if re.search(
    r'now\s*>=\s*expiresAtMillis',
    final_service,
    re.S,
):
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: quedó cierre heartbeat por expiresAtMillis"
    )


if re.search(
    r'System\.currentTimeMillis\(\)\s*>=\s*expiresAtMillis',
    final_service,
    re.S,
):
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: quedó cierre GPS por expiresAtMillis"
    )


if not re.search(
    r'LocationManager\.GPS_PROVIDER,\s*2000L',
    final_service,
    re.S,
):
    raise SystemExit(
        "ERROR V13 RELOJ LLEGADA: GPS dejó de estar en 2 s"
    )


print(
    "V13 aplicada: DND 2/4, ETA dinámica hasta T0, "
    "reloj nativo fijo T0+5 y cierre pre-T0 por expires_at eliminado."
)
