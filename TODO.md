## TODO
------------------------------------
### Minor Features
1. Aggiustare orario del dettaglio di container, per ora riporta orario Z
------------------------------------
### Main Features
##### 1. Monitoraggio dettagliato dei container
###### Descrizione Feature

Al click su un container attivo si visualizzeranno il consumo cpu, ram, disco e rete del singolo container con dettagli sullo storico degli utlimi 7 giorni rappresentati su un grafico.
Se possibile sarà possibile vedere anche in tempo reale gli utlimi 5-10 log del container.

###### Step di sviluppo
- Recupero e storicizzazione delle performance
- Creazione di volumi per lo storage 
- Popolamento grafici
- Sezione della pagina dedicata ai log

------------------------------------
##### 2. Crezione container docker plug-and-play
###### Descrizione Feature

L'intero applicativo deve essere pacchettizato in un container docker con Dockerfile in modo da poter essere aggangiato ad un docker-compose.

###### Step di sviluppo
- Creazione Dockerfile
- Test di integrazione in un docker-compose
------------------------------------
