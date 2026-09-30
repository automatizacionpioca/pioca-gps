from pathlib import Path
import re

gradle = Path("android-pioca/app/build.gradle")
service = Path(
    "android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java"
)


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR V11 ETA: " + label)
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
        raise SystemExit("ERROR V11 ETA: " + label)

    return out


# ==========================================================
# VERSION
# Parte de V10 Maps Share YA aplicada.
# ==========================================================

t = gradle.read_text(encoding="utf-8")

t = replace_once(
    t,
    "versionCode 10",
    "versionCode 11",
    "versionCode",
)

t = replace_once(
    t,
    'versionName "0.10-maps-share"',
    'versionName "0.11-eta-dinamica"',
    "versionName",
)

gradle.write_text(
    t,
    encoding="utf-8",
)


# ==========================================================
# TRACKING SERVICE
#
# V11 ETA DINÁMICA:
# - conserva GPS V9 a 2 s;
# - conserva No molestar V8 a 3 min;
# - usa tracking-router solamente para ETA/ruta;
# - 60 s durante el viaje;
# - 15 s dentro de los últimos 3 min;
# - actualiza client_arrival + expires_at en Supabase;
# - Google Maps puede estar cerrado.
# ==========================================================

t = service.read_text(
    encoding="utf-8"
)


# ----------------------------------------------------------
# 1) Estado y temporizadores ETA.
# ----------------------------------------------------------

t = re_once(
    t,
    r'(private volatile boolean dndHandled\s*=\s*false;)',
    r'''\1

private static final long ETA_REFRESH_NORMAL_MS =
        60L * 1000L;

private static final long ETA_REFRESH_FINAL_MS =
        15L * 1000L;

private static final long ETA_FINAL_WINDOW_MS =
        3L * 60L * 1000L;

private static final long ETA_RETRY_MS =
        15L * 1000L;

private static final long ETA_LOCATION_MAX_AGE_MS =
        30L * 1000L;

private volatile double destinationLat =
        Double.NaN;

private volatile double destinationLon =
        Double.NaN;

private volatile long lastEtaSuccessAt =
        0L;

private volatile long lastEtaAttemptAt =
        0L;

private final AtomicBoolean etaRefreshing =
        new AtomicBoolean(false);''',
    "campos ETA dinámica",
)


# ----------------------------------------------------------
# 2) Evaluar ETA desde el heartbeat ya existente.
#    No modifica el intervalo de GPS.
# ----------------------------------------------------------

t = re_once(
    t,
    r'(maybeEnableDnd\(now\);)',
    r'''\1

      maybeRefreshRouteEta(now);''',
    "heartbeat ETA dinámica",
)


# ----------------------------------------------------------
# 3) El estado remoto Android pasa a la variante ETA.
#    Mantiene la misma semántica de active/finished, pero además
#    devuelve client_arrival y destino.
# ----------------------------------------------------------

t = replace_once(
    t,
    'BASE\n\n                            + "/rest/v1/rpc/get_tracking_runtime_state"',
    'BASE\n\n                            + "/rest/v1/rpc/get_tracking_runtime_eta_state"',
    "RPC runtime ETA",
)


# ----------------------------------------------------------
# 4) Leer client_arrival real, destino y fecha de última ETA.
#    Esto ocurre dentro de loadRemoteState(), antes de devolver ACTIVE.
# ----------------------------------------------------------

anchor = r'''            String name =

                    row.optString(

                            "client_name",

                            ""
                    );
'''

addition = r'''            String name =

                    row.optString(

                            "client_name",

                            ""
                    );


            long serverArrival =

                    parseTime(

                            row.optString(

                                    "client_arrival",

                                    ""
                            )
                    );


            if (serverArrival > 0) {

                clientArrivalMillis =
                        serverArrival;
            }


            double serverDestinationLat =

                    row.optDouble(

                            "destination_latitude",

                            Double.NaN
                    );


            double serverDestinationLon =

                    row.optDouble(

                            "destination_longitude",

                            Double.NaN
                    );


            if (
                    Double.isFinite(serverDestinationLat)
                    && Double.isFinite(serverDestinationLon)
                    && serverDestinationLat >= -90.0
                    && serverDestinationLat <= 90.0
                    && serverDestinationLon >= -180.0
                    && serverDestinationLon <= 180.0
            ) {

                destinationLat =
                        serverDestinationLat;

                destinationLon =
                        serverDestinationLon;
            }


            long serverEtaUpdatedAt =

                    parseTime(

                            row.optString(

                                    "eta_updated_at",

                                    ""
                            )
                    );


            if (
                    serverEtaUpdatedAt > 0
                    && serverEtaUpdatedAt > lastEtaSuccessAt
            ) {

                lastEtaSuccessAt =
                        serverEtaUpdatedAt;
            }
'''

t = replace_once(
    t,
    anchor,
    addition,
    "parseo runtime ETA/destino",
)


# ----------------------------------------------------------
# 5) Motor ETA independiente.
# ----------------------------------------------------------

eta_engine = r'''

private void maybeRefreshRouteEta(
        long now
) {

    if (
            ending
            || code.isEmpty()
            || accessToken.isEmpty()
            || last == null
            || !Double.isFinite(destinationLat)
            || !Double.isFinite(destinationLon)
    ) {

        return;
    }


    long locationTime =
            last.getTime();


    if (
            locationTime > 0
            && now - locationTime > ETA_LOCATION_MAX_AGE_MS
    ) {

        return;
    }


    long remaining =
            clientArrivalMillis > 0
                    ? clientArrivalMillis - now
                    : Long.MAX_VALUE;


    long interval =
            remaining <= ETA_FINAL_WINDOW_MS
                    ? ETA_REFRESH_FINAL_MS
                    : ETA_REFRESH_NORMAL_MS;


    if (
            lastEtaSuccessAt > 0
            && now - lastEtaSuccessAt < interval
    ) {

        return;
    }


    if (
            lastEtaAttemptAt > 0
            && now - lastEtaAttemptAt < ETA_RETRY_MS
    ) {

        return;
    }


    if (
            !etaRefreshing.compareAndSet(
                    false,
                    true
            )
    ) {

        return;
    }


    lastEtaAttemptAt =
            now;


    final Location current =
            new Location(last);


    final double destLat =
            destinationLat;


    final double destLon =
            destinationLon;


    new Thread(() -> {

        try {

            RouteEtaResult route =
                    loadRouteEta(
                            current,
                            destLat,
                            destLon,
                            accessToken
                    );


            if (
                    !route.ok
                    || route.arrivalMillis <= 0
            ) {

                return;
            }


            UpdateEtaResult update =
                    updateRouteEta(
                            route,
                            accessToken
                    );


            if (update.finished) {

                finishExpired();
                return;
            }


            if (!update.ok) {

                return;
            }


            if (update.arrivalMillis > 0) {

                clientArrivalMillis =
                        update.arrivalMillis;
            }


            if (update.expiresAtMillis > 0) {

                expiresAtMillis =
                        update.expiresAtMillis;
            }


            lastEtaSuccessAt =
                    System.currentTimeMillis();


            saveActiveConfig();


            /*
             * Si Google atrasó la llegada y salimos de la ventana
             * de 3 minutos, maybeEnableDnd() deshará únicamente el
             * No molestar que hubiera activado piOca.
             *
             * Si Google acercó la llegada, el próximo heartbeat
             * activará No molestar al entrar en <= 3 minutos.
             */

        } finally {

            etaRefreshing.set(
                    false
            );
        }

    }).start();
}


private RouteEtaResult loadRouteEta(
        Location current,
        double destLat,
        double destLon,
        String token
) {

    HttpURLConnection c =
            null;


    try {

        URL url =
                new URL(
                        BASE
                        + "/functions/v1/tracking-router"
                );


        c =
                (HttpURLConnection)
                        url.openConnection();


        c.setRequestMethod(
                "POST"
        );


        c.setDoOutput(
                true
        );


        c.setConnectTimeout(
                12000
        );


        c.setReadTimeout(
                15000
        );


        c.setRequestProperty(
                "apikey",
                KEY
        );


        c.setRequestProperty(
                "Authorization",
                "Bearer " + token
        );


        c.setRequestProperty(
                "Content-Type",
                "application/json"
        );


        JSONObject body =
                new JSONObject();


        body.put(
                "action",
                "route"
        );


        JSONObject origin =
                new JSONObject();


        origin.put(
                "lat",
                current.getLatitude()
        );


        origin.put(
                "lng",
                current.getLongitude()
        );


        JSONObject destination =
                new JSONObject();


        destination.put(
                "lat",
                destLat
        );


        destination.put(
                "lng",
                destLon
        );


        body.put(
                "origin",
                origin
        );


        body.put(
                "destination",
                destination
        );


        try (
                OutputStream os =
                        c.getOutputStream()
        ) {

            os.write(
                    body.toString()
                            .getBytes(
                                    StandardCharsets.UTF_8
                            )
            );
        }


        int status =
                c.getResponseCode();


        if (
                status < 200
                || status >= 300
        ) {

            return new RouteEtaResult(
                    false,
                    status,
                    0L,
                    "",
                    0,
                    0
            );
        }


        JSONObject root =
                new JSONObject(
                        readBody(
                                c.getInputStream()
                        )
                );


        if (!root.optBoolean("ok", false)) {

            return new RouteEtaResult(
                    false,
                    status,
                    0L,
                    "",
                    0,
                    0
            );
        }


        JSONObject route =
                root.optJSONObject(
                        "route"
                );


        if (route == null) {

            return new RouteEtaResult(
                    false,
                    status,
                    0L,
                    "",
                    0,
                    0
            );
        }


        long arrival =
                parseTime(
                        route.optString(
                                "arrival_at",
                                ""
                        )
                );


        int distance =
                Math.max(
                        0,
                        route.optInt(
                                "distance_meters",
                                0
                        )
                );


        int duration =
                Math.max(
                        0,
                        route.optInt(
                                "duration_seconds",
                                0
                        )
                );


        String polyline =
                route.optString(
                        "encoded_polyline",
                        ""
                );


        return new RouteEtaResult(
                arrival > 0,
                status,
                arrival,
                polyline,
                distance,
                duration
        );


    } catch (Exception e) {

        return new RouteEtaResult(
                false,
                0,
                0L,
                "",
                0,
                0
        );


    } finally {

        if (c != null) {

            c.disconnect();
        }
    }
}


private UpdateEtaResult updateRouteEta(
        RouteEtaResult route,
        String token
) {

    HttpURLConnection c =
            null;


    try {

        URL url =
                new URL(
                        BASE
                        + "/rest/v1/rpc/update_tracking_route_eta"
                );


        c =
                (HttpURLConnection)
                        url.openConnection();


        c.setRequestMethod(
                "POST"
        );


        c.setDoOutput(
                true
        );


        c.setConnectTimeout(
                10000
        );


        c.setReadTimeout(
                10000
        );


        c.setRequestProperty(
                "apikey",
                KEY
        );


        c.setRequestProperty(
                "Authorization",
                "Bearer " + token
        );


        c.setRequestProperty(
                "Content-Type",
                "application/json"
        );


        JSONObject body =
                new JSONObject();


        body.put(
                "p_code",
                code
        );


        body.put(
                "p_client_arrival",
                Instant.ofEpochMilli(
                        route.arrivalMillis
                ).toString()
        );


        if (
                route.polyline != null
                && !route.polyline.trim().isEmpty()
        ) {

            body.put(
                    "p_route_polyline",
                    route.polyline
            );

        } else {

            body.put(
                    "p_route_polyline",
                    JSONObject.NULL
            );
        }


        body.put(
                "p_route_distance_meters",
                route.distanceMeters
        );


        body.put(
                "p_route_duration_seconds",
                route.durationSeconds
        );


        try (
                OutputStream os =
                        c.getOutputStream()
        ) {

            os.write(
                    body.toString()
                            .getBytes(
                                    StandardCharsets.UTF_8
                            )
            );
        }


        int status =
                c.getResponseCode();


        if (
                status < 200
                || status >= 300
        ) {

            return new UpdateEtaResult(
                    false,
                    false,
                    status,
                    0L,
                    0L
            );
        }


        JSONArray arr =
                new JSONArray(
                        readBody(
                                c.getInputStream()
                        )
                );


        if (arr.length() == 0) {

            return new UpdateEtaResult(
                    false,
                    false,
                    status,
                    0L,
                    0L
            );
        }


        JSONObject row =
                arr.getJSONObject(
                        0
                );


        String state =
                row.optString(
                        "state",
                        ""
                );


        boolean finished =
                "finished".equalsIgnoreCase(
                        state
                );


        boolean ok =
                row.optBoolean(
                        "success",
                        false
                );


        long arrival =
                parseTime(
                        row.optString(
                                "client_arrival",
                                ""
                        )
                );


        long expires =
                parseTime(
                        row.optString(
                                "expires_at",
                                ""
                        )
                );


        return new UpdateEtaResult(
                ok,
                finished,
                status,
                arrival,
                expires
        );


    } catch (Exception e) {

        return new UpdateEtaResult(
                false,
                false,
                0,
                0L,
                0L
        );


    } finally {

        if (c != null) {

            c.disconnect();
        }
    }
}


'''

t = re_once(
    t,
    r'(private long loadClientArrival\(\) \{)',
    eta_engine + r'\1',
    "motor ETA antes de loadClientArrival",
)


# ----------------------------------------------------------
# 6) Clases de resultado aisladas.
# ----------------------------------------------------------

result_classes = r'''

    private static class RouteEtaResult {

        final boolean ok;
        final int status;
        final long arrivalMillis;
        final String polyline;
        final int distanceMeters;
        final int durationSeconds;


        RouteEtaResult(
                boolean ok,
                int status,
                long arrivalMillis,
                String polyline,
                int distanceMeters,
                int durationSeconds
        ) {

            this.ok =
                    ok;

            this.status =
                    status;

            this.arrivalMillis =
                    arrivalMillis;

            this.polyline =
                    polyline == null
                            ? ""
                            : polyline;

            this.distanceMeters =
                    distanceMeters;

            this.durationSeconds =
                    durationSeconds;
        }
    }


    private static class UpdateEtaResult {

        final boolean ok;
        final boolean finished;
        final int status;
        final long arrivalMillis;
        final long expiresAtMillis;


        UpdateEtaResult(
                boolean ok,
                boolean finished,
                int status,
                long arrivalMillis,
                long expiresAtMillis
        ) {

            this.ok =
                    ok;

            this.finished =
                    finished;

            this.status =
                    status;

            this.arrivalMillis =
                    arrivalMillis;

            this.expiresAtMillis =
                    expiresAtMillis;
        }
    }


'''

t = re_once(
    t,
    r'(\n\s*private static class SendResult \{)',
    result_classes + r'\1',
    "clases resultado ETA",
)


# ==========================================================
# VALIDACIONES
# ==========================================================

checks = [
    (
        'get_tracking_runtime_eta_state',
        t,
        "RPC runtime ETA",
    ),
    (
        '/functions/v1/tracking-router',
        t,
        "tracking-router",
    ),
    (
        'update_tracking_route_eta',
        t,
        "RPC actualización ETA",
    ),
    (
        'ETA_REFRESH_NORMAL_MS',
        t,
        "intervalo normal",
    ),
    (
        '60L * 1000L',
        t,
        "ETA normal 60 s",
    ),
    (
        '15L * 1000L',
        t,
        "ETA final/reintento 15 s",
    ),
    (
        'ETA_FINAL_WINDOW_MS',
        t,
        "ventana final",
    ),
    (
        'maybeRefreshRouteEta(now)',
        t,
        "heartbeat ETA",
    ),
    (
        'maybeEnableDnd(now)',
        t,
        "No molestar",
    ),
]

for needle, haystack, label in checks:
    if needle not in haystack:
        raise SystemExit(
            "ERROR V11 ETA: falta " + label
        )


# Protección explícita V9: GPS principal sigue en 2 s.
if not re.search(
    r'LocationManager\.GPS_PROVIDER,\s*2000L',
    t,
    re.S,
):
    raise SystemExit(
        "ERROR V11 ETA: GPS_PROVIDER dejó de estar en 2 s"
    )


# NETWORK de respaldo sigue en 10 s.
if not re.search(
    r'LocationManager\.NETWORK_PROVIDER,\s*10000L',
    t,
    re.S,
):
    raise SystemExit(
        "ERROR V11 ETA: NETWORK_PROVIDER dejó de estar en 10 s"
    )


# Heartbeat de respaldo GPS sigue conservando 10 s.
if not re.search(
    r'last\s*!=\s*null\s*&&\s*now\s*-\s*lastOk\s*>=\s*10000L',
    t,
    re.S,
):
    raise SystemExit(
        "ERROR V11 ETA: heartbeat GPS dejó de estar en 10 s"
    )


# No molestar sigue exactamente a 3 min.
if not re.search(
    r'DND_BEFORE_ARRIVAL_MS\s*=\s*3L\s*\*\s*60L\s*\*\s*1000L',
    t,
    re.S,
):
    raise SystemExit(
        "ERROR V11 ETA: No molestar dejó de estar en 3 min"
    )


service.write_text(
    t,
    encoding="utf-8",
)

print(
    "V11 ETA DINÁMICA aplicada: "
    "Google Routes 60 s / 15 s últimos 3 min, "
    "client_arrival dinámico, "
    "GPS 2 s y DND 3 min preservados."
)
