from pathlib import Path
import re

gradle = Path("android-pioca/app/build.gradle")
service = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java"
)


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR V9 ESTABLE: " + label)
    return text.replace(old, new, 1)


def re_once(text, pattern, repl, label, flags=0):
    out, n = re.subn(
        pattern,
        repl,
        text,
        count=1,
        flags=flags
    )

    if n != 1:
        raise SystemExit("ERROR V9 ESTABLE: " + label)

    return out


# ==========================================================
# VERSION
# Parte de V8 Silencio YA aplicada.
# ==========================================================

t = gradle.read_text(encoding="utf-8")

t = replace_once(
    t,
    "versionCode 8",
    "versionCode 9",
    "versionCode"
)

t = replace_once(
    t,
    'versionName "0.8-silencio"',
    'versionName "0.9-estable-2s"',
    "versionName"
)

gradle.write_text(
    t,
    encoding="utf-8"
)


# ==========================================================
# TRACKING SERVICE
#
# V9 ESTABLE:
# - conserva EXACTAMENTE la arquitectura V8;
# - GPS_PROVIDER pasa de 5 s a 2 s;
# - envío normal pasa de 5 s a 2 s;
# - NETWORK_PROVIDER queda como en V8: 10 s;
# - heartbeat de respaldo queda como en V8: 10 s;
# - sin filtros nuevos;
# - sin cambios en index.html;
# - sin cambios en cliente.html.
# ==========================================================

t = service.read_text(
    encoding="utf-8"
)

# 1) GPS principal: 5000 ms -> 2000 ms
t = re_once(
    t,
    r'(LocationManager\.GPS_PROVIDER,\s*)5000L',
    r'\g<1>2000L',
    "GPS_PROVIDER 2 segundos",
    re.S
)

# 2) Envío normal: 5000 ms -> 2000 ms
t = re_once(
    t,
    r'(System\.currentTimeMillis\(\)\s*-\s*lastOk\s*>=\s*)5000L',
    r'\g<1>2000L',
    "envio normal cada 2 segundos",
    re.S
)

# ==========================================================
# VALIDACIONES
# ==========================================================

if "LocationManager.GPS_PROVIDER" not in t:
    raise SystemExit(
        "ERROR V9 ESTABLE: falta GPS_PROVIDER"
    )

if "2000L" not in t:
    raise SystemExit(
        "ERROR V9 ESTABLE: no quedó intervalo 2 s"
    )

if "maybeEnableDnd" not in t:
    raise SystemExit(
        "ERROR V9 ESTABLE: se perdió lógica No molestar"
    )

# Confirmamos que los respaldos V8 NO fueron alterados.
if not re.search(
    r'LocationManager\.NETWORK_PROVIDER,\s*10000L',
    t,
    re.S
):
    raise SystemExit(
        "ERROR V9 ESTABLE: NETWORK_PROVIDER dejó de estar en 10 s"
    )

if not re.search(
    r'last\s*!=\s*null\s*&&\s*now\s*-\s*lastOk\s*>=\s*10000L',
    t,
    re.S
):
    raise SystemExit(
        "ERROR V9 ESTABLE: heartbeat V8 dejó de estar en 10 s"
    )

service.write_text(
    t,
    encoding="utf-8"
)

print(
    "V9 ESTABLE aplicada: "
    "GPS 2 s + envio normal 2 s, "
    "arquitectura V8 intacta."
)
