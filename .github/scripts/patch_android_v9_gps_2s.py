from pathlib import Path
import re

gradle = Path("android-pioca/app/build.gradle")
service = Path("android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java")

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR PATCH V9: " + label)
    return text.replace(old, new, 1)

def re_once(text, pattern, repl, label, flags=0):
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit("ERROR PATCH V9: " + label)
    return out

t = gradle.read_text(encoding="utf-8")
t = replace_once(t, "versionCode 8", "versionCode 9", "versionCode")
t = replace_once(t, 'versionName "0.8-silencio"', 'versionName "0.9-definitiva-2s"', "versionName")
gradle.write_text(t, encoding="utf-8")

t = service.read_text(encoding="utf-8")

# ==========================================================
# V9 - PROTECCIÓN CONTRA POSICIONES GPS ATRASADAS / CACHEADAS
# ==========================================================

field_anchor = "private Location last;"

if field_anchor not in t:
    raise SystemExit(
        "ERROR PATCH V9: no encontre campo Location last"
    )

stale_fields = """private Location last;

              private volatile long lastAcceptedLocationElapsedNanos = 0L;

              private static final long MAX_LOCATION_AGE_MS =
                      6000L;
"""

t = t.replace(
    field_anchor,
    stale_fields,
    1
)

onloc_anchor = """@Override
              public void onLocationChanged(
                      Location l
              ) {
"""

if onloc_anchor not in t:
    raise SystemExit(
        "ERROR PATCH V9: no encontre onLocationChanged"
    )

onloc_filtered = """@Override
              public void onLocationChanged(
                      Location l
              ) {

                  if (l == null) {
                      return;
                  }

                  /*
                   * V9:
                   * evita puntos viejos/cacheados entregados por Android
                   * al reactivar pantalla/proveedor/proceso.
                   */
                  try {

                      long nowElapsed =
                              android.os.SystemClock.elapsedRealtimeNanos();

                      long locationElapsed =
                              l.getElapsedRealtimeNanos();

                      if (locationElapsed > 0L) {

                          long ageMs =
                                  Math.max(
                                          0L,
                                          (nowElapsed - locationElapsed)
                                          / 1000000L
                                  );

                          if (ageMs > MAX_LOCATION_AGE_MS) {
                              return;
                          }

                          if (
                                  lastAcceptedLocationElapsedNanos > 0L
                                  && locationElapsed
                                  <= lastAcceptedLocationElapsedNanos
                          ) {
                              return;
                          }

                          lastAcceptedLocationElapsedNanos =
                                  locationElapsed;
                      }

                  } catch (Exception ignored) {
                  }

"""

t = t.replace(
    onloc_anchor,
    onloc_filtered,
    1
)

t = re_once(t, r'(LocationManager\.GPS_PROVIDER,\s*)5000L', r'\g<1>2000L', "GPS_PROVIDER 2 segundos", re.S)
t = re_once(t, r'(LocationManager\.NETWORK_PROVIDER,\s*)10000L', r'\g<1>5000L', "NETWORK_PROVIDER 5 segundos", re.S)
t = re_once(t, r'(System\.currentTimeMillis\(\)\s*-\s*lastOk\s*>=\s*)5000L', r'\g<1>2000L', "envio normal cada 2 segundos", re.S)
t = re_once(t, r'(last\s*!=\s*null\s*&&\s*now\s*-\s*lastOk\s*>=\s*)10000L', r'\g<1>5000L', "heartbeat respaldo 5 segundos", re.S)

marker = (
    "\n              /*\n"
    "               * piOca V9 DEFINITIVA\n"
    "               * GPS_PROVIDER: 2 s\n"
    "               * envio normal: 2 s\n"
    "               * NETWORK_PROVIDER respaldo: 5 s\n"
    "               * heartbeat sin envio exitoso: 5 s\n"
    "               * La logica de No molestar de V8 permanece intacta.\n"
    "               */\n              "
)

method_signature = "private void startLocations() {"
pos = t.find(method_signature)
if pos == -1:
    raise SystemExit("ERROR PATCH V9: no encontre startLocations")
t = t[:pos] + marker + t[pos:]

for token in [
    "LocationManager.GPS_PROVIDER",
    "LocationManager.NETWORK_PROVIDER",
    "2000L",
    "5000L",
    "maybeEnableDnd",
    "piOca V9 DEFINITIVA",
    "private void startLocations() {",
    "lastAcceptedLocationElapsedNanos",
    "MAX_LOCATION_AGE_MS",
    "getElapsedRealtimeNanos"
]:
    if token not in t:
        raise SystemExit("ERROR PATCH V9: falta token esperado " + token)

service.write_text(t, encoding="utf-8")
print("V9 aplicada correctamente: GPS 2 s + envio 2 s + respaldo 5 s, manteniendo V8 No molestar.")
