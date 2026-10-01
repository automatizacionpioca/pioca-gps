from pathlib import Path
import re

gradle = Path("android-pioca/app/build.gradle")
service = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java"
)


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR V12 ETA FREEZE: " + label)
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
        raise SystemExit("ERROR V12 ETA FREEZE: " + label)

    return out


# ==========================================================
# VERSION
# Parte de V11 ETA dinámica YA aplicada.
# ==========================================================

t = gradle.read_text(encoding="utf-8")

t = replace_once(
    t,
    "versionCode 11",
    "versionCode 12",
    "versionCode",
)

t = replace_once(
    t,
    'versionName "0.11-eta-dinamica"',
    'versionName "0.12-eta-freeze"',
    "versionName",
)

gradle.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# TRACKING SERVICE
#
# V12 ETA FREEZE:
# - conserva ETA dinámica V11 mientras todavía no llegó T0;
# - al alcanzar clientArrivalMillis, deja de pedir nuevos ETA;
# - evita que una respuesta de Google iniciada antes de T0 pueda
#   empujar client_arrival/expires_at después de la llegada;
# - el vencimiento real queda fijo y finishExpired() puede cortar
#   exactamente en client_arrival + 5 minutos;
# - conserva GPS 2 s, DND 3 min y toda la lógica previa.
# ==========================================================

t = service.read_text(encoding="utf-8")


# ----------------------------------------------------------
# 1) Corte duro ANTES de iniciar cualquier refresco ETA.
#    Si T0 ya llegó, la ETA automática queda congelada.
# ----------------------------------------------------------

pattern_pre_request = r'''(private void maybeRefreshRouteEta\(\s*long now\s*\) \{.*?\n\s*if \(\s*ending.*?\n\s*\}\n)(\s*long locationTime =)'''

replacement_pre_request = r'''\1

    /*
     * V12: T0 alcanzado = ETA automática congelada.
     * Desde este instante client_arrival y expires_at ya no deben
     * moverse por Google Routes. El cierre real queda a T0 + 5 min.
     */
    if (
            clientArrivalMillis > 0
            && now >= clientArrivalMillis
    ) {

        return;
    }


\2'''

t = re_once(
    t,
    pattern_pre_request,
    replacement_pre_request,
    "freeze antes de refrescar ETA",
    flags=re.S,
)


# ----------------------------------------------------------
# 2) Protección contra carrera de red.
#    La consulta a Google pudo comenzar antes de T0 y terminar después.
#    Antes de enviar el nuevo ETA a Supabase, comprobamos T0 otra vez.
# ----------------------------------------------------------

pattern_before_update = r'''(if \(\s*!route\.ok\s*\|\|\s*route\.arrivalMillis <= 0\s*\) \{\s*return;\s*\}\s*)(UpdateEtaResult update =)'''

replacement_before_update = r'''\1

            /*
             * V12: segunda barrera anti-carrera.
             * Si T0 ocurrió mientras esperábamos la respuesta de Google,
             * descartamos esa respuesta y no movemos el vencimiento.
             */
            long etaApplyNow =
                    System.currentTimeMillis();


            if (
                    clientArrivalMillis > 0
                    && etaApplyNow >= clientArrivalMillis
            ) {

                return;
            }


            \2'''

t = re_once(
    t,
    pattern_before_update,
    replacement_before_update,
    "freeze antes de updateRouteEta",
    flags=re.S,
)


# ==========================================================
# VALIDACIONES
# ==========================================================

checks = [
    (
        'versionName "0.12-eta-freeze"',
        gradle.read_text(encoding="utf-8"),
        "versionName V12",
    ),
    (
        'now >= clientArrivalMillis',
        t,
        "barrera T0 previa",
    ),
    (
        'etaApplyNow >= clientArrivalMillis',
        t,
        "barrera T0 anti-carrera",
    ),
    (
        'maybeRefreshRouteEta(now)',
        t,
        "motor ETA V11 preservado",
    ),
    (
        'update_tracking_route_eta',
        t,
        "RPC ETA preservada",
    ),
    (
        'get_tracking_runtime_eta_state',
        t,
        "runtime ETA preservado",
    ),
]

for needle, haystack, label in checks:
    if needle not in haystack:
        raise SystemExit(
            "ERROR V12 ETA FREEZE: falta " + label
        )


# Deben existir exactamente dos barreras nuevas sobre clientArrivalMillis:
# una antes de pedir ETA y otra antes de enviarla a Supabase.
if t.count("now >= clientArrivalMillis") < 1:
    raise SystemExit(
        "ERROR V12 ETA FREEZE: falta barrera previa T0"
    )

if t.count("etaApplyNow >= clientArrivalMillis") != 1:
    raise SystemExit(
        "ERROR V12 ETA FREEZE: barrera anti-carrera inválida"
    )


# Protecciones históricas que no deben tocarse.
if not re.search(
    r'LocationManager\.GPS_PROVIDER,\s*2000L',
    t,
    re.S,
):
    raise SystemExit(
        "ERROR V12 ETA FREEZE: GPS_PROVIDER dejó de estar en 2 s"
    )

if not re.search(
    r'DND_BEFORE_ARRIVAL_MS\s*=\s*3L\s*\*\s*60L\s*\*\s*1000L',
    t,
    re.S,
):
    raise SystemExit(
        "ERROR V12 ETA FREEZE: No Molestar dejó de estar en 3 min"
    )

service.write_text(
    t,
    encoding="utf-8",
)

print(
    "V12 ETA FREEZE aplicada: "
    "ETA dinámica hasta T0, congelada desde T0, "
    "expires_at estable a T0 + 5 min, GPS 2 s y DND preservados."
)
