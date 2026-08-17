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
    "private void startLocations() {"
]:
    if token not in t:
        raise SystemExit("ERROR PATCH V9: falta token esperado " + token)

service.write_text(t, encoding="utf-8")
print("V9 aplicada correctamente: GPS 2 s + envio 2 s + respaldo 5 s, manteniendo V8 No molestar.")
