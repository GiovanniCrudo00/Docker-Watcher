#!/bin/sh

# Aggiungi il tuo utente al gruppo docker
sudo usermod -aG docker $USER

# Riavvia il servizio Docker
sudo systemctl restart docker

# IMPORTANTE: Fai logout e login per applicare le modifiche
# Oppure usa questo comando per aggiornare i gruppi nella sessione corrente
newgrp docker

# Verifica che funzioni
docker ps