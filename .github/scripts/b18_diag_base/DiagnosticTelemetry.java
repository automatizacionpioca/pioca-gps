package ar.com.pioca.seguimiento;

import android.content.Context;
import android.content.SharedPreferences;
import android.location.Location;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Process;
import android.os.SystemClock;
import android.webkit.JavascriptInterface;
import org.json.JSONArray;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Instrumentación pasiva B17-DIAG. Sin coordenadas, URLs, nombres ni mensajes. */
public final class DiagnosticTelemetry {
    private static final String URL_API = "https://apxrmkdegjnblkbyjsbp.supabase.co/rest/v1/pioca_diag_metrics";
    private static final String API_KEY = "__API_KEY_FROM_B17_SOURCE__";
    private static final Object LOCK = new Object();
    private static final Map<String, Stat> STATS = new HashMap<>();
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();
    private static final String STORE="pioca_b17_diag";
    private static Context context;
    private static String token="";
    private static String runId;
    private static boolean sending=false;
    private static long periodStart = SystemClock.elapsedRealtime();
    private static long lastGpsAt=0L;
    private static long lastHeartbeatAt=0L;
    private static long prevCpuAt=0L;
    private static long lastSampleAt=0L;
    private static String networkCached="unknown";
    private static long networkCheckedAt=0L;

    private static class Stat {
        int n,fail;
        double sum,min=Double.MAX_VALUE,max;
        void add(int k,double total,double lo,double hi,int errors){
            n+=k;sum+=total;min=Math.min(min,lo);max=Math.max(max,hi);fail+=errors;
        }
    }
    private DiagnosticTelemetry(){}
    public static void init(Context c){
        if(c==null)return;
        synchronized (LOCK){
            if(context!=null)return;
            context=c.getApplicationContext();
            SharedPreferences p=context.getSharedPreferences(STORE,Context.MODE_PRIVATE);
            runId=p.getString("run_id","");
            if(runId.isEmpty()){
                runId=UUID.randomUUID().toString();
                p.edit().putString("run_id",runId).apply();
            }
        }
    }
    public static void setAuth(Context c,String jwt){
        init(c);
        if(jwt==null||jwt.length()<40||jwt.length()>10000)return;
        synchronized(LOCK){token=jwt;}
        flush();
    }
    private static String network(){
        Context c=context;
        if(c==null)return "unknown";
        long now=SystemClock.elapsedRealtime();
        if(now-networkCheckedAt<10000L)return networkCached;
        networkCheckedAt=now;
        try{
            ConnectivityManager cm=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);
            if(cm==null)return "unknown";
            Network n=cm.getActiveNetwork();
            NetworkCapabilities cap=cm.getNetworkCapabilities(n);
            if(cap==null || !cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED))networkCached="offline";
            else if(cap.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))networkCached="wifi";
            else if(cap.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))networkCached="cellular";
            else if(cap.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))networkCached="ethernet";
            else networkCached="other";
        }catch(Exception e){networkCached="unknown";}
        return networkCached;
    }
    private static String cleanMetric(String name){
        if(name==null)return "";
        String n=name.toLowerCase(java.util.Locale.ROOT);
        return n.length()>=3 && n.length()<=64 && n.matches("[a-z0-9._-]+")?n:"";
    }
    public static void record(String name,double value,boolean failure){aggregate("android",name,1,value,value,value,failure?1:0);}
    public static void aggregate(String source,String name,int n,double total,double lo,double hi,int errors){
        String safe=cleanMetric(name);
        if(context==null||safe.isEmpty()||n<1||n>50000||errors<0||errors>n ||
          !Double.isFinite(total)||!Double.isFinite(lo)||!Double.isFinite(hi)||
          lo<0||hi<lo||hi>120000||total<0||total>600000000)return;
        synchronized(LOCK){
            String key=source+"|"+safe+"|"+network();
            Stat stat=STATS.get(key);
            if(stat==null){
                if(STATS.size()>160)return;
                stat=new Stat();STATS.put(key,stat);
            }
            stat.add(n,total,lo,hi,errors);
        }
        if(SystemClock.elapsedRealtime()-periodStart>60000L)flush();
    }
    public static void gps(Location loc){
        if(loc==null)return;
        long now=SystemClock.elapsedRealtime();
        if(lastGpsAt>0)record("gps.fix_interval_ms",now-lastGpsAt,false);
        lastGpsAt=now;
        if(loc.hasAccuracy())record("gps.accuracy_m",Math.min(120000,Math.max(0,loc.getAccuracy())),false);
        try{
            double age=(SystemClock.elapsedRealtimeNanos()-loc.getElapsedRealtimeNanos())/1e6;
            if(age>=0 && age<=120000)record("gps.fix_age_ms",age,false);
        }catch(Exception ignored){}
        if("gps".equalsIgnoreCase(loc.getProvider()))record("gps.provider_gps",0,false);
        else record("gps.provider_network",0,false);
    }
    public static void heartbeat(){
        long now=SystemClock.elapsedRealtime();
        if(lastHeartbeatAt>0)record("android.heartbeat_lag_ms",Math.min(120000,Math.max(0,(now-lastHeartbeatAt)-2000L)),false);
        lastHeartbeatAt=now;
        if(now-lastSampleAt>=30000L){
            long elapsedSampleMs=lastSampleAt>0?now-lastSampleAt:0;
            lastSampleAt=now;
            Runtime r=Runtime.getRuntime();
            record("android.heap_used_mb",Math.min(120000,(r.totalMemory()-r.freeMemory())/1048576.0),false);
            long cpu=Process.getElapsedCpuTime();
            if(prevCpuAt>0){
                long cpuDelta=Math.max(0,cpu-prevCpuAt);
                record("android.cpu_delta_ms",Math.min(120000,cpuDelta),false);
                if(elapsedSampleMs>0)record("android.cpu_core_pct",Math.min(120000,100.0*cpuDelta/elapsedSampleMs),false);
            }
            prevCpuAt=cpu;
            record("android.network_sample",0,"offline".equals(network()));
        }
        if(now-periodStart>60000L)flush();
    }
    public static void flush(){
        final Context c=context;
        if(c==null)return;
        synchronized(LOCK){
            long now=SystemClock.elapsedRealtime();
            if(STATS.isEmpty() && token.isEmpty())return;
            if(now-periodStart<12000L && STATS.size()<100)return;
            periodStart=now;
            JSONArray rows=new JSONArray();
            for(Map.Entry<String,Stat> e:STATS.entrySet()){
                try{
                    String[] parts=e.getKey().split("\\|",3);
                    Stat s=e.getValue();
                    JSONObject obj=new JSONObject();
                    obj.put("run_id",runId);obj.put("source",parts[0]);obj.put("metric",parts[1]);
                    obj.put("network",parts[2]);obj.put("samples",s.n);
                    obj.put("total_value",s.sum);obj.put("min_value",s.min);
                    obj.put("max_value",s.max);obj.put("failures",s.fail);
                    rows.put(obj);
                }catch(Exception ignored){}
            }
            STATS.clear();
            SharedPreferences p=c.getSharedPreferences(STORE,Context.MODE_PRIVATE);
            try{
                JSONArray queue=new JSONArray(p.getString("queue","[]"));
                for(int i=0;i<rows.length();i++)queue.put(rows.getJSONObject(i));
                if(queue.length()>500){
                    JSONArray last=new JSONArray();
                    for(int i=queue.length()-500;i<queue.length();i++)last.put(queue.getJSONObject(i));
                    queue=last;
                }
                p.edit().putString("queue",queue.toString()).apply();
            }catch(Exception ignored){}
            if(!sending && !token.isEmpty()){
                sending=true;
                IO.execute(DiagnosticTelemetry::upload);
            }
        }
    }
    private static void upload(){
        HttpURLConnection conn=null;
        try{
            final Context c=context;
            if(c==null)return;
            String authorization, original;
            synchronized(LOCK){
                authorization=token;
                original=c.getSharedPreferences(STORE,Context.MODE_PRIVATE).getString("queue","[]");
            }
            if(authorization.isEmpty())return;
            JSONArray queue=new JSONArray(original);
            if(queue.length()==0)return;
            conn=(HttpURLConnection)new URL(URL_API).openConnection();
            conn.setRequestMethod("POST");conn.setDoOutput(true);
            conn.setConnectTimeout(8000);conn.setReadTimeout(10000);
            conn.setRequestProperty("apikey",API_KEY);
            conn.setRequestProperty("Authorization","Bearer "+authorization);
            conn.setRequestProperty("Content-Type","application/json");
            conn.setRequestProperty("Prefer","return=minimal");
            byte[] bytes=original.getBytes(StandardCharsets.UTF_8);
            try(OutputStream out=conn.getOutputStream()){out.write(bytes);}
            int code=conn.getResponseCode();
            if(code>=200&&code<300){
                synchronized(LOCK){
                    SharedPreferences p=c.getSharedPreferences(STORE,Context.MODE_PRIVATE);
                    String latest=p.getString("queue","[]");
                    if(latest.equals(original))p.edit().putString("queue","[]").apply();
                    else{
                        JSONArray arr=new JSONArray(latest), rem=new JSONArray();
                        for(int i=queue.length();i<arr.length();i++)rem.put(arr.getJSONObject(i));
                        p.edit().putString("queue",rem.toString()).apply();
                    }
                }
            } else android.util.Log.w("piOcaDiag","Telemetry HTTP "+code);
        }catch(Exception e){android.util.Log.w("piOcaDiag","Telemetry no enviada; retenida para reintento");}
        finally{
            if(conn!=null)conn.disconnect();
            synchronized(LOCK){sending=false;}
        }
    }
    public static class Bridge {
        @JavascriptInterface public void aggregate(String name,int count,double sum,double min,double max,int fails){
            DiagnosticTelemetry.aggregate("web",name,count,sum,min,max,fails);
        }
        @JavascriptInterface public void metric(String name,double value,int fail){
            DiagnosticTelemetry.aggregate("web",name,1,value,value,value,fail!=0?1:0);
        }
        @JavascriptInterface public void setAuth(String jwt){DiagnosticTelemetry.setAuth(context,jwt);}
    }
}
