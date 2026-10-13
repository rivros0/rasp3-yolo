# Installazione tramite SSH

Preparare Raspberry Pi OS Lite Bookworm a 64 bit, con Python 3.11, su microSD.
In Raspberry Pi Imager configurare utente, rete e SSH. Collegare la webcam USB.
Questi comandi installano il progetto sul Raspberry; non sono stati eseguiti su hardware reale.

Dal computer, sostituire UTENTE e IP_RASPBERRY:

```bash
ssh UTENTE@IP_RASPBERRY
```

Nella sessione SSH:

```bash
set -e
uname -m
python3 --version
sudo apt-get update
sudo apt-get install -y git
mkdir -p "$HOME/laboratori"
cd "$HOME/laboratori"
git clone https://github.com/rivros0/rasp3-yolo.git
cd rasp3-yolo
bash scripts/setup_raspberry.sh
bash scripts/install_service.sh
sudo systemctl status rasp3-yolo --no-pager
curl --fail --retry 12 --retry-connrefused --retry-delay 5 http://localhost:8000/api/health
hostname -I
```

Aprire `http://IP_RASPBERRY:8000` oppure `/docs` per le API interattive.
Il servizio parte anche dopo il riavvio. Il gruppo video viene aggiunto prima
della creazione del servizio; per l'avvio manuale aprire una nuova sessione SSH.

## Diagnostica

```bash
journalctl -u rasp3-yolo -n 100 --no-pager
v4l2-ctl --list-devices
ls -l /dev/video*
curl --fail http://localhost:8000/api/classes
curl --fail http://localhost:8000/api/detections
```

Se la webcam non e' l'indice 0, fermare il servizio e provare l'indice corretto:

```bash
sudo systemctl stop rasp3-yolo
cd "$HOME/laboratori/rasp3-yolo"
.venv/bin/python -m app.main --camera 1 --width 320 --height 240
```

Per renderlo permanente usare `sudo systemctl edit rasp3-yolo` e sostituire
ExecStart con il percorso assoluto corretto, preceduto da una riga `ExecStart=`
vuota, poi eseguire `sudo systemctl daemon-reload` e `sudo systemctl restart rasp3-yolo`.

## Aggiornamenti

```bash
set -e
cd "$HOME/laboratori/rasp3-yolo"
sudo systemctl stop rasp3-yolo
git pull --ff-only
.venv/bin/python -m pip install -r requirements-rpi.txt
sudo systemctl restart rasp3-yolo
```

## Prestazioni

La configurazione iniziale usa YOLOv8n in PyTorch. Installazione e primo avvio
possono richiedere tempo e memoria sul Pi 3. Il video annotato attende l'inferenza:
la risoluzione della webcam non determina la dimensione interna del modello,
e non si garantisce un particolare numero di FPS. Misurare sul dispositivo.
La guida Ultralytics consiglia NCNN per ARM, ma i benchmark ufficiali riguardano
Pi 4/5: https://docs.ultralytics.com/guides/raspberry-pi/.
