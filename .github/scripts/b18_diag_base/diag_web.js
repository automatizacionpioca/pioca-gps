/* piOca B17-DIAG | perfilador web, solo cuando existe el puente nativo.
   No recoge coordenadas, URLs completas, nombres, tokens ni textos. */
(function(){
  'use strict';
  if (!window.PiocaDiag || typeof window.PiocaDiag.metric !== 'function') return;
  const values = new Map();
  function metric(name, ms, fail){
    try {
      name = String(name).slice(0,64).replace(/[^a-z0-9._-]/gi,'_');
      ms = Number(ms);
      if(!Number.isFinite(ms) || ms < 0 || ms > 120000 || !name) return;
      let v=values.get(name);
      if(!v){v={n:0,sum:0,min:ms,max:0,fail:0};values.set(name,v);}
      v.n++;v.sum+=ms;v.min=Math.min(v.min,ms);v.max=Math.max(v.max,ms);
      if(fail)v.fail++;
    } catch(_){}
  }
  window.__piocaDiagMetric=metric;
  function flush(){
    if(!values.size)return;
    const snapshot=Array.from(values.entries());values.clear();
    for(const [k,v] of snapshot){
      try{window.PiocaDiag.aggregate(k,v.n,v.sum,v.min,v.max,v.fail);}catch(_){}
    }
  }
  setInterval(flush,30000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flush();});
  window.addEventListener('pagehide',flush);

  const started=performance.now();
  window.addEventListener('load',()=>metric('web.window_load',performance.now()-started,0),{once:true});
  try{
    if ('PerformanceObserver' in window){
      new PerformanceObserver(list=>{
        for(const e of list.getEntries())metric('web.long_task',e.duration,0);
      }).observe({entryTypes:['longtask']});
    }
  }catch(_){}
  let lastRaf=0;
  function frame(t){
    if(document.visibilityState==='visible' && lastRaf){
      const d=t-lastRaf;
      if(d>45 && d<120000)metric('web.frame_over_45ms',d,0);
    }
    lastRaf=t;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  let expected=performance.now()+1000;
  setInterval(()=>{
    const now=performance.now(), lag=Math.max(0,now-expected);
    if(lag>50&&lag<120000)metric('web.event_loop_lag',lag,0);
    expected=now+1000;
  },1000);

  // Instrumenta solicitudes sin cambiar ni el valor devuelto ni su contenido.
  if(typeof window.fetch==='function'){
    const originalFetch=window.fetch;
    window.fetch=function(){
      const t=performance.now();
      let cat='web.fetch.other';
      try{
        const arg=arguments[0];const url=typeof arg==='string'?arg:(arg&&arg.url)||'';
        if(/supabase\.co/i.test(url))cat='web.fetch.supabase';
        else if(/__r67\/sector/i.test(url))cat='web.fetch.r67_sector';
        else if(/googleapis|gstatic/i.test(url))cat='web.fetch.google';
      }catch(_){}
      let p;
      try{p=originalFetch.apply(this,arguments);}catch(e){metric(cat,performance.now()-t,1);throw e;}
      if(p&&typeof p.then==='function')p.then(
        r=>metric(cat,performance.now()-t,(!r||!r.ok)?1:0),
        ()=>metric(cat,performance.now()-t,1));
      return p;
    };
  }
  function updateAuth(){
    try{
      const raw=localStorage.getItem('sb-apxrmkdegjnblkbyjsbp-auth-token');
      if(!raw)return;
      const obj=JSON.parse(raw);
      if(obj&&typeof obj.access_token==='string'&&obj.access_token.length>32){
        window.PiocaDiag.setAuth(obj.access_token);
      }
    }catch(_){}
  }
  setTimeout(updateAuth,3000);setInterval(updateAuth,60000);
  window.addEventListener('online',()=>metric('web.online_event',0,0));
  window.addEventListener('offline',()=>metric('web.offline_event',0,1));
  window.addEventListener('error',()=>metric('web.script_error',0,1));
  window.addEventListener('unhandledrejection',()=>metric('web.promise_rejection',0,1));
})();
