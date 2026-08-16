self.addEventListener(
  "push",
  function(event){

    let data = {};

    try{
      data =
        event.data
          ? event.data.json()
          : {};
    }catch(e){
      data = {
        title:"piOca®",
        body:
          event.data
            ? event.data.text()
            : "Estamos llegando."
      };
    }

    const title =
      data.title ||
      "piOca®";

    const options = {
      body:
        data.body ||
        "Estamos llegando.",

      icon:
        "./logo-pioca.png",

      badge:
        "./logo-pioca.png",

      tag:
        data.tag ||
        "pioca-llegada",

      renotify:true,

      vibrate:[
        180,
        80,
        180
      ],

      data:{
        url:
          data.url ||
          "./cliente.html"
      }
    };

    event.waitUntil(
      self.registration
      .showNotification(
        title,
        options
      )
    );
  }
);

self.addEventListener(
  "notificationclick",
  function(event){

    event.notification.close();

    const url =
      event.notification.data &&
      event.notification.data.url
        ? event.notification.data.url
        : "./cliente.html";

    event.waitUntil(
      clients.matchAll({
        type:"window",
        includeUncontrolled:true
      })
      .then(
        function(ventanas){

          for(
            const ventana of ventanas
          ){

            if(
              "navigate" in
              ventana
            ){
              ventana.navigate(
                url
              );
            }

            if(
              "focus" in
              ventana
            ){
              return ventana.focus();
            }
          }

          if(
            clients.openWindow
          ){
            return clients.openWindow(
              url
            );
          }
        }
      )
    );
  }
);
