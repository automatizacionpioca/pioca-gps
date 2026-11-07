
package ar.com.pioca.seguimiento;


import android.Manifest;

import android.app.Notification;

import android.app.NotificationChannel;

import android.app.NotificationManager;

import android.app.Service;

import android.content.Intent;

import android.content.SharedPreferences;

import android.content.pm.PackageManager;

import android.location.Location;

import android.location.LocationListener;

import android.location.LocationManager;

import android.os.Handler;

import android.os.IBinder;

import android.os.Looper;

import android.os.PowerManager;

import org.json.JSONArray;

import org.json.JSONObject;

import java.io.InputStream;

import java.io.OutputStream;

import java.net.HttpURLConnection;

import java.net.URL;

import java.nio.charset.StandardCharsets;

import java.time.Instant;

import java.util.concurrent.atomic.AtomicBoolean;


public class TrackingService
        extends Service
        implements LocationListener {


    private static final String CH =
            "pioca_tracking";


    private static final String BASE =

            "https://apxrmkdegjnblkbyjsbp.supabase.co";


    private static final String KEY =

            "sb_publishable_htgEX8HiRGAjpCVhPw1gfg_tOPxkJoI";


    private volatile String code = "";

    private volatile String accessToken = "";

    private volatile String refreshToken = "";

    private volatile String clientName = "";

    private volatile long expiresAtMillis = 0L;


    private SharedPreferences prefs;

    private LocationManager lm;

    private Location last;

    private PowerManager.WakeLock wakeLock;


    private long lastOk = 0L;

    /*
     * B14 PRUEBA:
     * reloj local de inicio de transmisión.
     * lastOk queda reservado para confirmación/salud del servidor.
     */
    private long lastSendStarted = 0L;

    private static final long MIN_SEND_GUARD_MS = 1500L;

    private long lastRemoteCheck = 0L;


    private final Handler handler =

            new Handler(

                    Looper.getMainLooper()
            );


    private final AtomicBoolean sending =

            new AtomicBoolean(
                    false
            );


    private final AtomicBoolean checking =

            new AtomicBoolean(
                    false
            );


    private volatile boolean ending =
            false;

private static final long DND_ENTER_BEFORE_ARRIVAL_MS =
        2L * 60L * 1000L;

private static final long DND_EXIT_BEFORE_ARRIVAL_MS =
        4L * 60L * 1000L;

private static final long TRACKING_AFTER_ARRIVAL_MS =
        5L * 60L * 1000L;

private volatile long clientArrivalMillis = 0L;
private volatile boolean dndHandled = false;

private volatile long arrivalReachedAtMillis =
        0L;

private static final long ETA_REFRESH_NORMAL_MS =
        60L * 1000L;

private static final long ETA_REFRESH_FINAL_MS =
        15L * 1000L;

private static final long ETA_FINAL_WINDOW_MS =
        3L * 60L * 1000L;

/*
 * B15 - PREAPROXIMACION ETA
 * Entramos antes de la ventana histórica de 3 minutos para que
 * client_arrival llegue fresco a la fase final.
 */
private static final long ETA_PREAPPROACH_WINDOW_MS =
        5L * 60L * 1000L;

private static final float ETA_PREAPPROACH_DISTANCE_M =
        1200.0f;

private static final long ETA_RETRY_MS =
        15L * 1000L;

private volatile double destinationLat =
        Double.NaN;

private volatile double destinationLon =
        Double.NaN;

private volatile long lastEtaSuccessAt =
        0L;

private volatile long lastEtaAttemptAt =
        0L;

private final AtomicBoolean etaRefreshing =
        new AtomicBoolean(false);

/*
 * El enclavamiento evita ping-pong 15 s -> 60 s si una nueva ETA
 * de Google corrige la llegada hacia atrás durante la aproximación.
 */
private volatile boolean etaPreapproachLatched =
        false;

private volatile String etaPreapproachCode =
        "";


    private final Runnable heartbeat =

            new Runnable() {


                @Override
                public void run() {


                    if (ending) {


                        return;
                    }


                    ensureWakeLock();


                    long now =

                            System.currentTimeMillis();

      maybeEnableDnd(now);

      maybeRefreshRouteEta(now);



      maybeLatchArrivalAndFinish(now);

      if (ending) {

          return;
      }


                    if (

                            now - lastRemoteCheck >= 5000L

                    ) {


                        validateRemoteAsync();
                    }


                    if (

                            last != null

                            && now - lastOk >= 10000L

                    ) {


                        sendAsync(
                                last
                        );
                    }


                    handler.postDelayed(

                            this,

                            2000L
                    );
                }
            };


    @Override
    public void onCreate() {


        super.onCreate();


        prefs =

                getSharedPreferences(

                        "pioca_tracking",

                        MODE_PRIVATE
                );


        NotificationManager nm =

                getSystemService(

                        NotificationManager.class
                );


        nm.createNotificationChannel(

                new NotificationChannel(

                        CH,

                        "Seguimiento GPS piOca",

                        NotificationManager.IMPORTANCE_LOW
                )
        );
    }


    @Override
    public int onStartCommand(

            Intent i,

            int flags,

            int startId) {


        ending =
                false;


        boolean loaded =
                false;


        if (i != null) {


            String incoming =

                    norm(

                            i.getStringExtra(

                                    "tracking"
                            )
                    );


            if (

                    !incoming.isEmpty()

            ) {


                code =
                        incoming;


                accessToken =

                        nz(

                                i.getStringExtra(

                                        "access_token"
                                )
                        );


                refreshToken =

                        nz(

                                i.getStringExtra(

                                        "refresh_token"
                                )
                        );


                clientName =

                        nz(

                                i.getStringExtra(

                                        "client_name"
                                )
                        );


                expiresAtMillis =

                        parseTime(

                                i.getStringExtra(

                                        "expires_at"
                                )
                        );

clientArrivalMillis =
        expiresAtMillis > TRACKING_AFTER_ARRIVAL_MS
                ? expiresAtMillis - TRACKING_AFTER_ARRIVAL_MS
                : 0L;

arrivalReachedAtMillis =
        0L;


                saveActiveConfig();


                loaded =
                        true;
            }
        }


        if (!loaded) {


            loaded =
                    restoreActiveConfig();
        }


        if (

                !loaded

                || code.isEmpty()

        ) {


            stopSelf();


            return START_NOT_STICKY;
        }


dndHandled = prefs.getBoolean(
        "dnd_activated_by_pioca",
        false
);


        Notification n =

                new Notification.Builder(

                        this,

                        CH
                )

                .setContentTitle(

                        "piOca • Seguimiento GPS activo"
                )

                .setContentText(

                        clientName == null

                        || clientName.trim().isEmpty()

                                ? "La ubicación se está enviando al cliente"

                                : "Enviando ubicación a " + clientName
                )

                .setSmallIcon(

                        android.R.drawable.ic_menu_mylocation
                )

                .setOngoing(true)

                .setOnlyAlertOnce(true)

                .build();


        startForeground(

                1001,

                n
        );


        /*
         * Mantiene la CPU activa con la pantalla apagada.
         * Es un PARTIAL_WAKE_LOCK: NO mantiene la pantalla encendida.
         */
        ensureWakeLock();


        startLocations();


        handler.removeCallbacks(

                heartbeat
        );


        handler.postDelayed(

                heartbeat,

                1000L
        );


        return START_STICKY;
    }


    private void ensureWakeLock() {


        try {


            if (

                    wakeLock != null

                    && wakeLock.isHeld()

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


            wakeLock =

                    pm.newWakeLock(

                            PowerManager.PARTIAL_WAKE_LOCK,

                            "pioca:tracking"
                    );


            wakeLock.setReferenceCounted(

                    false
            );


            wakeLock.acquire();


        } catch (Exception ignored) {
        }
    }


    private void releaseWakeLock() {


        try {


            if (

                    wakeLock != null

                    && wakeLock.isHeld()

            ) {


                wakeLock.release();
            }


        } catch (Exception ignored) {


        } finally {


            wakeLock =
                    null;
        }
    }


    private void saveActiveConfig() {


        prefs.edit()

                .putBoolean(

                        "service_active",

                        true
                )

                .putString(

                        "tracking_code",

                        code
                )

                .putString(

                        "access_token",

                        accessToken
                )

                .putString(

                        "refresh_token",

                        refreshToken
                )

                .putString(

                        "client_name",

                        clientName
                )

                .putLong(

                        "expires_at",

                        expiresAtMillis
                )

        .putLong(
                "client_arrival",
                clientArrivalMillis
        )

                .apply();
    }


    private boolean restoreActiveConfig() {


        if (

                !prefs.getBoolean(

                        "service_active",

                        false
                )

        ) {


            return false;
        }


        code =

                norm(

                        prefs.getString(

                                "tracking_code",

                                ""
                        )
                );


        accessToken =

                nz(

                        prefs.getString(

                                "access_token",

                                ""
                        )
                );


        refreshToken =

                nz(

                        prefs.getString(

                                "refresh_token",

                                ""
                        )
                );


        clientName =

                nz(

                        prefs.getString(

                                "client_name",

                                ""
                        )
                );


        expiresAtMillis =

                prefs.getLong(

                        "expires_at",

                        0L
                );


clientArrivalMillis = prefs.getLong(
        "client_arrival",
        0L
);

if (clientArrivalMillis <= 0
        && expiresAtMillis > TRACKING_AFTER_ARRIVAL_MS) {

    clientArrivalMillis =
            expiresAtMillis -
            TRACKING_AFTER_ARRIVAL_MS;
}


        return !code.isEmpty();
    }


    private void clearActiveConfig() {


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

        .remove("client_arrival")

                .apply();
    }


    private void startLocations() {


        lm =

                (LocationManager)

                        getSystemService(

                                LOCATION_SERVICE
                        );


        if (

                checkSelfPermission(

                        Manifest.permission.ACCESS_FINE_LOCATION)

                != PackageManager.PERMISSION_GRANTED

        ) {


            stopSelf();


            return;
        }


        try {


            lm.requestLocationUpdates(

                    LocationManager.GPS_PROVIDER,

                    2000L,

                    0f,

                    this,

                    Looper.getMainLooper()
            );


        } catch (Exception ignored) {
        }


        try {


            lm.requestLocationUpdates(

                    LocationManager.NETWORK_PROVIDER,

                    10000L,

                    0f,

                    this,

                    Looper.getMainLooper()
            );


        } catch (Exception ignored) {
        }
    }


    @Override
    public void onLocationChanged(
            Location l
    ) {


        if (ending) {


            return;
        }


        last =
                l;



                  long arrivalNow =
                          System.currentTimeMillis();


                  maybeLatchArrivalAndFinish(
                          arrivalNow
                  );


                  if (ending) {

                      return;
                  }


        long nowLocation =
                System.currentTimeMillis();

        if (

                !sending.get()

                && (

                        lastSendStarted == 0L

                        || nowLocation - lastSendStarted >= MIN_SEND_GUARD_MS

                )

        ) {


            lastSendStarted =
                    nowLocation;


            sendAsync(
                    l
            );
        }
    }


    private void validateRemoteAsync() {


        if (

                ending

                || code.isEmpty()

                || accessToken.isEmpty()

        ) {


            return;
        }


        if (

                !checking.compareAndSet(

                        false,

                        true
                )

        ) {


            return;
        }


        lastRemoteCheck =

                System.currentTimeMillis();


        new Thread(() -> {


            try {


                RemoteResult r =

                        loadRemoteState(

                                accessToken
                        );


                if (

                        r.state == RemoteState.UNAUTHORIZED

                        && refresh()

                ) {


                    r =

                            loadRemoteState(

                                    accessToken
                            );
                }


                if (

                        r.state == RemoteState.ACTIVE

                ) {


    long arrival =
            r.expiresAt > TRACKING_AFTER_ARRIVAL_MS
                    ? r.expiresAt - TRACKING_AFTER_ARRIVAL_MS
                    : 0L;

    if (arrival > 0) {
        clientArrivalMillis = arrival;
        saveActiveConfig();
    }


                    if (

                            r.expiresAt > 0

                    ) {


                        expiresAtMillis =

                                r.expiresAt;


                        saveActiveConfig();
                    }


                    if (

                            r.clientName != null

                            && !r.clientName.trim().isEmpty()

                    ) {


                        clientName =

                                r.clientName;


                        saveActiveConfig();
                    }


                } else if (

                        r.state == RemoteState.FINISHED

                        || r.state == RemoteState.INVALID

                ) {


                    finishExpired();
                }


            } finally {


                checking.set(
                        false
                );
            }


        }).start();
    }


    private RemoteResult loadRemoteState(
            String token
    ) {


        HttpURLConnection c =
                null;


        try {


            URL url =

                    new URL(

                            BASE

                            + "/rest/v1/rpc/get_tracking_runtime_eta_state"
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

                    status == 401

            ) {


                return new RemoteResult(

                        RemoteState.UNAUTHORIZED,

                        0L,

                        ""
                );
            }


            if (

                    status < 200

                    || status >= 300

            ) {


                return new RemoteResult(

                        RemoteState.UNKNOWN,

                        0L,

                        ""
                );
            }


            String raw =

                    readBody(

                            c.getInputStream()
                    );


            JSONArray arr =

                    new JSONArray(
                            raw
                    );


            if (

                    arr.length() == 0

            ) {


                return new RemoteResult(

                        RemoteState.INVALID,

                        0L,

                        ""
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


            long exp =

                    parseTime(

                            row.optString(

                                    "expires_at",

                                    ""
                            )
                    );


            String name =

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


            if (

                    "active".equalsIgnoreCase(

                            state
                    )

            ) {


                return new RemoteResult(

                        RemoteState.ACTIVE,

                        exp,

                        name
                );
            }


            if (

                    "finished".equalsIgnoreCase(

                            state
                    )

            ) {


                return new RemoteResult(

                        RemoteState.FINISHED,

                        exp,

                        name
                );
            }


            return new RemoteResult(

                    RemoteState.INVALID,

                    exp,

                    name
            );


        } catch (Exception e) {


            return new RemoteResult(

                    RemoteState.UNKNOWN,

                    0L,

                    ""
            );


        } finally {


            if (c != null) {


                c.disconnect();
            }
        }
    }


    



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




    long remaining =
            clientArrivalMillis > 0
                    ? clientArrivalMillis - now
                    : Long.MAX_VALUE;


    /*
     * B15: el régimen rápido se arma por DOS señales independientes:
     * ETA <= 5 min o cercanía física <= 1200 m en línea recta.
     * La distancia sólo decide la frecuencia de consulta de ETA;
     * NO participa de MUY CERCA, T0 ni HEMOS LLEGADO.
     */
    if (!code.equals(etaPreapproachCode)) {

        etaPreapproachCode =
                code;

        etaPreapproachLatched =
                false;
    }


    float distanciaDirectaDestino =
            Float.POSITIVE_INFINITY;


    try {

        float[] distanciaResultado =
                new float[1];

        Location.distanceBetween(
                last.getLatitude(),
                last.getLongitude(),
                destinationLat,
                destinationLon,
                distanciaResultado
        );

        if (
                distanciaResultado.length > 0
                && Float.isFinite(distanciaResultado[0])
                && distanciaResultado[0] >= 0.0f
        ) {

            distanciaDirectaDestino =
                    distanciaResultado[0];
        }

    } catch (Exception ignored) {
    }


    boolean debeEntrarPreaproximacion =
            remaining <= ETA_PREAPPROACH_WINDOW_MS
            || distanciaDirectaDestino <= ETA_PREAPPROACH_DISTANCE_M;


    if (debeEntrarPreaproximacion) {

        etaPreapproachLatched =
                true;
    }


    long interval =
            etaPreapproachLatched
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


private void sendAsync(
            Location l
    ) {


        if (

                ending

                || code.isEmpty()

                || accessToken.isEmpty()

        ) {


            return;
        }


        if (

                !sending.compareAndSet(

                        false,

                        true
                )

        ) {


            return;
        }


        new Thread(() -> {


            try {


                SendResult r =

                        send(

                                l,

                                accessToken
                        );


                if (

                        r.status == 401

                        && refresh()

                ) {


                    r =

                            send(

                                    l,

                                    accessToken
                            );
                }


                if (

                        r.ok

                ) {


                    lastOk =

                            System.currentTimeMillis();


                } else if (

                        r.status == 400

                        || r.status == 403

                        || r.status == 404

                        || r.explicitFalse

                ) {


                    validateRemoteAsync();
                }


            } finally {


                sending.set(
                        false
                );
            }


        }).start();
    }


    private SendResult send(

            Location l,

            String token
    ) {


        HttpURLConnection c =
                null;


        try {


            c =

                    (HttpURLConnection)

                            new URL(

                                    BASE

                                    + "/rest/v1/rpc/push_tracking_position"
                            )

                            .openConnection();


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


            JSONObject b =

                    new JSONObject();


            b.put(

                    "p_code",

                    code
            );


            b.put(

                    "p_lat",

                    l.getLatitude()
            );


            b.put(

                    "p_lon",

                    l.getLongitude()
            );


            b.put(

                    "p_accuracy",

                    l.getAccuracy()
            );


            try (

                    OutputStream os =

                            c.getOutputStream()

            ) {


                os.write(

                        b.toString()

                                .getBytes(

                                        StandardCharsets.UTF_8
                                )
                );
            }


            int status =

                    c.getResponseCode();


            String body =

                    readBody(

                            status >= 400

                                    ? c.getErrorStream()

                                    : c.getInputStream()
                    );


            boolean explicitFalse =
                    false;


            if (

                    status >= 200

                    && status < 300

            ) {


                String t =

                        body == null

                                ? ""

                                : body.trim()

                                        .toLowerCase();


                explicitFalse =

                        "false".equals(
                                t
                        )

                        || "null".equals(
                                t
                        );


                return new SendResult(

                        !explicitFalse,

                        status,

                        explicitFalse
                );
            }


            return new SendResult(

                    false,

                    status,

                    false
            );


        } catch (Exception e) {


            return new SendResult(

                    false,

                    0,

                    false
            );


        } finally {


            if (c != null) {


                c.disconnect();
            }
        }
    }


    private boolean refresh() {


        if (

                refreshToken.isEmpty()

        ) {


            return false;
        }


        HttpURLConnection c =
                null;


        try {


            c =

                    (HttpURLConnection)

                            new URL(

                                    BASE

                                    + "/auth/v1/token?grant_type=refresh_token"
                            )

                            .openConnection();


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

                    "Content-Type",

                    "application/json"
            );


            JSONObject b =

                    new JSONObject();


            b.put(

                    "refresh_token",

                    refreshToken
            );


            try (

                    OutputStream os =

                            c.getOutputStream()

            ) {


                os.write(

                        b.toString()

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


                return false;
            }


            JSONObject r =

                    new JSONObject(

                            readBody(

                                    c.getInputStream()
                            )
                    );


            accessToken =

                    r.optString(

                            "access_token",

                            accessToken
                    );


            refreshToken =

                    r.optString(

                            "refresh_token",

                            refreshToken
                    );


            saveActiveConfig();


            return !accessToken.isEmpty();


        } catch (Exception e) {


            return false;


        } finally {


            if (c != null) {


                c.disconnect();
            }
        }
    }


    private synchronized void finishExpired() {


        if (ending) {


            return;
        }


        ending =
                true;


        handler.removeCallbacks(

                heartbeat
        );


        if (lm != null) {


            try {


                lm.removeUpdates(
                        this
                );


            } catch (Exception ignored) {
            }
        }


        releaseWakeLock();


        clearActiveConfig();


        prefs.edit()

                .putBoolean(

                        "pending_finished_dialog",

                        true
                )

                          .putBoolean(
                                  "dnd_restore_after_real_expiry",
                                  true
                          )

                .putString(

                        "finished_client_name",

                        clientName == null

                                ? ""

                                : clientName
                )

                .apply();


        try {


            stopForeground(

                    STOP_FOREGROUND_REMOVE
            );


        } catch (Exception ignored) {
        }


        stopSelf();
    }


    private static long parseTime(
            String value
    ) {


        if (

                value == null

                || value.trim().isEmpty()

        ) {


            return 0L;
        }


        try {


            return Instant.parse(

                    value.trim()
            )

            .toEpochMilli();


        } catch (Exception e) {


            return 0L;
        }
    }


    private static String readBody(

            InputStream in

    ) throws Exception {


        if (in == null) {


            return "";
        }


        StringBuilder sb =

                new StringBuilder();


        int x;


        while (

                (x = in.read()) != -1

        ) {


            sb.append(

                    (char)x
            );
        }


        return sb.toString();
    }


    private static String norm(
            String s
    ) {


        return s == null

                ? ""

                : s.trim()

                        .toUpperCase();
    }


    private static String nz(
            String s
    ) {


        return s == null

                ? ""

                : s;
    }


    @Override
    public void onDestroy() {


        handler.removeCallbacks(

                heartbeat
        );


        if (lm != null) {


            try {


                lm.removeUpdates(
                        this
                );


            } catch (Exception ignored) {
            }
        }


        releaseWakeLock();


        super.onDestroy();
    }


    @Override
    public IBinder onBind(
            Intent i
    ) {


        return null;
    }


    private enum RemoteState {

        ACTIVE,

        FINISHED,

        INVALID,

        UNAUTHORIZED,

        UNKNOWN
    }


    private static class RemoteResult {


        final RemoteState state;

        final long expiresAt;

        final String clientName;


        RemoteResult(

                RemoteState state,

                long expiresAt,

                String clientName) {


            this.state =
                    state;


            this.expiresAt =
                    expiresAt;


            this.clientName =
                    clientName;
        }
    }

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





    private static class SendResult {


        final boolean ok;

        final int status;

        final boolean explicitFalse;


        SendResult(

                boolean ok,

                int status,

                boolean explicitFalse) {


            this.ok =
                    ok;


            this.status =
                    status;


            this.explicitFalse =
                    explicitFalse;
        }
    }
}

