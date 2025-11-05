## DOCKER WATCHER
----------------------------------------
#### Descrizione
Docker Watcher è una webapp basata su flask per il monitoraggio dei container docker in esecuzione sull'host.
Tramite la dashboard è possibile monitorare:

- Le immagini docker
- I container in esecuzione
- I container stoppati

Inoltre è possibile monitorare il consumo di CPU e di RAM dell'host.

----------------------------------------
#### Utilizzo

1. Eseguire lo script permit_docker.sh per dare i permessi di accedere del socket docker
```
./permit_docker.sh
```
2. Creare un ambiente virtuale venv
```
python -m venv /path/to/new/virtual/environment
```
3. Attivare l'ambiente virtuale
```
source /path/to/new/virtual/environment/bin/activate
```
4. Installare le dipendenze dal file requirements.txt
```
pip3 install -r requirements.txt
```
5. Lanciare il webserver
```
python3 app.py 
```
6. Collegarsi a http://localhost:5000

----------------------------------------

#### Licenza

Questo progetto è distribuito sotto licenza [GNU GPL v3.0](LICENSE).

Copyright (C) 2025 Giovambattista Crudo
