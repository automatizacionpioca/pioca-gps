from pathlib import Path

gradle = Path("android-pioca/app/build.gradle")
manifest = Path("android-pioca/app/src/main/AndroidManifest.xml")
main = Path("android-pioca/app/src/main/java/ar/com/pioca/seguimiento/MainActivity.java")
service = Path("android-pioca/app/src/main/java/ar/com/pioca/seguimiento/TrackingService.java")

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ERROR PATCH " + label)
    return text.replace(old, new, 1)

t = gradle.read_text(encoding="utf-8")
t = replace_once(t, 'versionCode 7', 'versionCode 8', 'versionCode')
t = replace_once(t, 'versionName "0.7"', 'versionName "0.8-silencio"', 'versionName')
gradle.write_text(t, encoding="utf-8")

t = manifest.read_text(encoding="utf-8")
marker = '''            <uses-permission
              android:name="android.permission.POST_NOTIFICATIONS"/>
'''
addition = marker + '''
            <uses-permission
              android:name="android.permission.ACCESS_NOTIFICATION_POLICY"/>
'''
t = replace_once(t, marker, addition, 'ACCESS_NOTIFICATION_POLICY')
manifest.write_text(t, encoding="utf-8")

t = main.read_text(encoding="utf-8")

t = replace_once(
    t,
    '''          import android.app.AlertDialog;
''',
    '''          import android.app.AlertDialog;

          import android.app.NotificationManager;
''',
    'import NotificationManager MainActivity'
)

t = replace_once(
    t,
    '''              private boolean batteryDialogVisible = false;

              private long lastBatteryPromptAt = 0L;
''',
    '''              private boolean batteryDialogVisible = false;

              private long lastBatteryPromptAt = 0L;

              private boolean dndDialogVisible = false;
''',
    'campo dndDialogVisible'
)

t = replace_once(
    t,
    '''                  if (!pending) {


                      return;
                  }
''',
    '''                  if (!pending) {


                      showPendingDndRestoreDialog();


                      return;
                  }
''',
    'showPendingEndDialog no pending'
)

t = replace_once(
    t,
    '''                          .setPositiveButton(

                                  "ACEPTAR",

                                  null
                          )

                          .show();
              }
''',
    '''                          .setPositiveButton(

                                  "ACEPTAR",

                                  (d, which) -> showPendingDndRestoreDialog()
                          )

                          .show();
              }


              private void ensureDndAccess() {


                  NotificationManager nm =

                          (NotificationManager)

                                  getSystemService(

                                          NOTIFICATION_SERVICE
                                  );


                  if (

                          nm == null

                          || nm.isNotificationPolicyAccessGranted()

                          || dndDialogVisible

                          || isFinishing()

                  ) {


                      return;
                  }


                  dndDialogVisible = true;


                  AlertDialog dialog =

                          new AlertDialog.Builder(this)

                                  .setTitle(

                                          "Silencio automático al llegar"
                                  )

                                  .setMessage(

                                          "piOca puede activar No molestar cuando falten 3 minutos para llegar.\\n\\n"

                                          + "Este permiso se configura una sola vez en Android.\\n\\n"

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


                  dialog.setOnCancelListener(

                          d -> dndDialogVisible = false
                  );


                  dialog.show();
              }


              private void showPendingDndRestoreDialog() {


                  SharedPreferences prefs =

                          getSharedPreferences(

                                  "pioca_tracking",

                                  MODE_PRIVATE
                          );


                  boolean pending =

                          prefs.getBoolean(

                                  "dnd_restore_pending",

                                  false
                          );


                  if (!pending) {


                      return;
                  }


                  NotificationManager nm =

                          (NotificationManager)

                                  getSystemService(

                                          NOTIFICATION_SERVICE
                                  );


                  if (

                          nm == null

                          || !nm.isNotificationPolicyAccessGranted()

                  ) {


                      return;
                  }


                  if (

                          nm.getCurrentInterruptionFilter()

                          == NotificationManager.INTERRUPTION_FILTER_ALL

                  ) {


                      prefs.edit()

                              .putBoolean(

                                      "dnd_restore_pending",

                                      false
                              )

                              .putBoolean(

                                      "dnd_activated_by_pioca",

                                      false
                              )

                              .apply();


                      return;
                  }


                  new AlertDialog.Builder(this)

                          .setTitle(

                                  "No molestar sigue activo"
                          )

                          .setMessage(

                                  "El seguimiento ya finalizó.\\n\\n"

                                  + "¿Querés quitar el modo No molestar?"
                          )

                          .setPositiveButton(

                                  "QUITAR SILENCIO",

                                  (d, which) -> {


                                      try {


                                          nm.setInterruptionFilter(

                                                  NotificationManager.INTERRUPTION_FILTER_ALL
                                          );


                                          prefs.edit()

                                                  .putBoolean(

                                                          "dnd_restore_pending",

                                                          false
                                                  )

                                                  .putBoolean(

                                                          "dnd_activated_by_pioca",

                                                          false
                                                  )

                                                  .remove(

                                                          "dnd_previous_filter"
                                                  )

                                                  .apply();


                                      } catch (Exception ignored) {
                                      }
                                  }
                          )

                          .setNegativeButton(

                                  "MANTENER SILENCIO",

                                  null
                          )

                          .show();
              }
''',
    'metodos DND MainActivity'
)

t = replace_once(
    t,
    '''                      runOnUiThread(() -> {


                          checkBatteryOptimization();
''',
    '''                      runOnUiThread(() -> {


                          ensureDndAccess();


                          checkBatteryOptimization();
''',
    'ensureDndAccess startTracking'
)

main.write_text(t, encoding="utf-8")

t = service.read_text(encoding="utf-8")

if "import android.app.NotificationManager;" not in t:
    t = replace_once(
        t,
        '''          import android.app.NotificationChannel;
''',
        '''          import android.app.NotificationChannel;

          import android.app.NotificationManager;
''',
        'import NotificationManager service'
    )

t = replace_once(
    t,
    '''              private volatile boolean ending =
                      false;
''',
    '''              private volatile boolean ending =
                      false;


              private static final long DND_BEFORE_EXPIRES_MS =
                      8L * 60L * 1000L;


              private volatile boolean dndHandled =
                      false;
''',
    'campos DND TrackingService'
)

t = replace_once(
    t,
    '''                              long now =

                                      System.currentTimeMillis();


                              if (

                                      expiresAtMillis > 0
''',
    '''                              long now =

                                      System.currentTimeMillis();


                              maybeEnableDnd(
                                      now
                              );


                              if (

                                      expiresAtMillis > 0
''',
    'heartbeat maybeEnableDnd'
)

t = replace_once(
    t,
    '''                  if (

                          !loaded

                          || code.isEmpty()

                  ) {


                      stopSelf();


                      return START_NOT_STICKY;
                  }


                  Notification n =
''',
    '''                  if (

                          !loaded

                          || code.isEmpty()

                  ) {


                      stopSelf();


                      return START_NOT_STICKY;
                  }


                  dndHandled =

                          prefs.getBoolean(

                                  "dnd_activated_by_pioca",

                                  false
                          );


                  Notification n =
''',
    'restore dndHandled'
)

t = replace_once(
    t,
    '''              private void ensureWakeLock() {
''',
    '''              private void maybeEnableDnd(
                      long now
              ) {


                  if (

                          dndHandled

                          || expiresAtMillis <= 0

                  ) {


                      return;
                  }


                  long triggerAt =

                          expiresAtMillis

                          - DND_BEFORE_EXPIRES_MS;


                  if (

                          now < triggerAt

                  ) {


                      return;
                  }


                  NotificationManager nm =

                          (NotificationManager)

                                  getSystemService(

                                          NOTIFICATION_SERVICE
                                  );


                  if (

                          nm == null

                          || !nm.isNotificationPolicyAccessGranted()

                  ) {


                      return;
                  }


                  int current =

                          nm.getCurrentInterruptionFilter();


                  if (

                          current !=

                          NotificationManager.INTERRUPTION_FILTER_ALL

                  ) {


                      dndHandled =
                              true;


                      return;
                  }


                  try {


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

                              .putInt(

                                      "dnd_previous_filter",

                                      current
                              )

                              .apply();


                      dndHandled =
                              true;


                  } catch (Exception ignored) {
                  }
              }


              private void ensureWakeLock() {
''',
    'metodo maybeEnableDnd'
)

service.write_text(t, encoding="utf-8")

print("V8 silencio aplicada correctamente.")
