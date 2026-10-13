# Laboratorio Raspberry Pi 3 + Webcam + YOLO

Progetto didattico per esporre da Raspberry Pi 3 una pagina web con vista realtime della webcam e rettangoli di riconoscimento oggetti generati da YOLO.

Il progetto include:

- streaming video MJPEG con bounding box;
- API REST per frame, predizioni, classi, configurazione e stato;
- frontend web leggero adatto al Raspberry Pi 3;
- struttura modulare per cambiare modello YOLO o sorgente video;
- guida di installazione e attività didattiche.

## Sostituzione della webcam

La sorgente predefinita e' `--camera auto`: il server cerca i dispositivi Linux
`/dev/video*` e usa il primo che produce un fotogramma valido. Se la webcam viene
scollegata, cancella il frame corrente e riprova ogni due secondi. Il server puo'
partire anche senza webcam. Al collegamento di una nuova webcam riprende senza
riavvio, azzerando i rilevamenti della sessione precedente.

`/api/health` espone `camera_state` (`connected` o `waiting`), `camera_source` e
`camera_generation`. Senza webcam, `/api/detections` restituisce una lista vuota,
`/api/frame.jpg` risponde 503 e lo stream invia un'immagine vuota. La pagina mostra
"Webcam non collegata". Un frame senza aggiornamenti per due secondi non viene
piu' considerato valido.

Per fissare una sorgente usare `--camera 0` oppure `--camera /dev/video2`:
in questo caso la riconnessione riguarda soltanto quella sorgente.
Servono webcam USB supportate dal driver Linux; risoluzione e FPS effettivi
dipendono dal dispositivo. Un driver che blocca una lettura puo' ritardare la
riconnessione; i tempi devono essere verificati con le webcam del laboratorio.

## Architettura

```text
Webcam USB
   |
OpenCV VideoCapture
   |
YOLODetector
   |
FastAPI
   |-- GET /                    pagina web
   |-- GET /stream.mjpg         video realtime annotato
   |-- GET /api/detections      ultime predizioni JSON
   |-- GET /api/frame.jpg       frame annotato singolo
   |-- GET /api/classes         classi del modello
   |-- GET /api/config          configurazione corrente
   |-- POST /api/config         aggiorna soglia/confidenza
   |-- GET /api/health          stato dispositivo
```

## Requisiti hardware

- Raspberry Pi 3 Model B/B+.
- Alimentatore stabile, preferibilmente 5V 2.5A.
- Webcam USB compatibile UVC.
- MicroSD da almeno 16 GB.
- Rete Wi-Fi o Ethernet.

## Installazione rapida su Raspberry Pi OS

Per clonare e configurare da SSH seguire [la guida completa](docs/installazione_ssh.md).
Configurazione prevista: Raspberry Pi OS Lite Bookworm o Trixie **64 bit**, Python 3.10-3.13.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libopenblas-dev libjpeg-dev zlib1g-dev libgl1 libglib2.0-0

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-rpi.txt
```

Per avviare:

```bash
source .venv/bin/activate
python -m app.main --host 0.0.0.0 --port 8000
```

Poi apri dal browser:

```text
http://<ip-del-raspberry>:8000
```

La documentazione API interattiva è disponibile su:

```text
http://<ip-del-raspberry>:8000/docs
```

## Scelta del modello

Il Raspberry Pi 3 è limitato. Per il laboratorio conviene partire con:

- risoluzione 320x240;
- intervallo minimo configurabile tra le inferenze; FPS effettivi da misurare;
- modello YOLO piccolo, per esempio `yolov8n`;
- se possibile modello convertito in formato NCNN/OpenVINO/TFLite.

Di default il codice usa `yolov8n.pt`, scaricato dalla libreria Ultralytics al primo uso se il Raspberry ha rete. Per un laboratorio offline, copia il modello in `models/yolov8n.pt` e avvia con:

```bash
python -m app.main --model models/yolov8n.pt
```

## API principali

### Stato

```bash
curl http://<ip>:8000/api/health
```

### Ultime rilevazioni

```bash
curl http://<ip>:8000/api/detections
```

Risposta esempio:

```json
{
  "timestamp": 1791816000.0,
  "width": 320,
  "height": 240,
  "detections": [
    {
      "class_id": 0,
      "label": "person",
      "confidence": 0.82,
      "box": {"x1": 35, "y1": 41, "x2": 180, "y2": 220}
    }
  ]
}
```

### Modifica soglia di confidenza

```bash
curl -X POST http://<ip>:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"confidence": 0.45}'
```

## Attività didattiche suggerite

1. Vedere come cambia il numero di rilevazioni al variare della soglia di confidenza.
2. Misurare FPS e latenza con risoluzioni diverse.
3. Salvare le rilevazioni in CSV e costruire un grafico.
4. Usare `/api/detections` da Scratch, Node-RED, Python o JavaScript.
5. Confrontare modelli diversi e discutere accuratezza, velocità e bias.

## Struttura del progetto

```text
app/
  main.py              server FastAPI
  camera.py            acquisizione webcam
  detector.py          wrapper YOLO
  schemas.py           modelli API
  templates/index.html interfaccia web
  static/app.css       stile
  static/app.js        logica frontend
docs/
  laboratorio.md       scheda didattica
scripts/
  install_service.sh   installazione servizio systemd
requirements-rpi.txt
```

## Avvio automatico con systemd

Dopo aver verificato che il server funzioni:

```bash
bash scripts/install_service.sh
sudo systemctl status rasp3-yolo
```
