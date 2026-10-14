# Architettura e stack software

Questa guida descrive l'implementazione **presente nel codice**, non un'architettura futura.
Per l'installazione vedere [installazione SSH](installazione_ssh.md).

## 1. Stack

| Livello | Componente | Ruolo |
| --- | --- | --- |
| Sistema | Raspberry Pi OS 64 bit, Linux | Esecuzione su Raspberry Pi 3 |
| Linguaggio server | Python | Backend e worker |
| Server web | FastAPI 0.118.0, Uvicorn 0.37.0 | Routing HTTP, API, file statici e streaming |
| Validazione | Pydantic 2.11.7 | Schemi e limiti configurazione API |
| Acquisizione | OpenCV 4.12.0.88 | `VideoCapture` webcam e JPEG |
| Inferenza | Ultralytics 8.3.163, PyTorch 2.7.1 | Modello YOLO, predizioni CPU |
| Array | NumPy 2.2.6 | Frame video in memoria |
| Frontend | HTML5, CSS e JavaScript nativo | Pagina web; nessun framework SPA o bundler |
| Trasporto video | MJPEG tramite HTTP multipart | Frame JPEG successivi nello stesso flusso |
| Overlay | SVG nativo nel browser | Rettangoli ed etichette vettoriali |
| Servizio Linux | systemd | Avvio automatico e restart on-failure |

Le versioni elencate sono quelle di `requirements-rpi.txt`, non una verifica delle versioni realmente installate sul dispositivo. Il progetto **non** usa React, Vue, Node.js, WebSocket, Docker o un database.

## 2. Diagramma dei flussi

```text
Webcam USB
    |
    v
app/camera.py : VideoCapture, thread acquisizione, ultimo frame
    |                                      |
    | copia del frame                     | copia del frame
    v                                      v
app/detector.py                         app/main.py
thread YOLO unico                       GET /stream.mjpg?raw=true
imgsz=320, device=cpu                     |
    |                                      | MJPEG non annotato
    v                                      v
ultimo DetectionResponse JSON           browser <img>
    |                                      |
    v                                      |
GET /api/detections                       |
    |                                      |
    +------ polling JS (250 ms) -----------+
                       |
                       v
              SVG sovrapposto al video
              (box + etichette nitide)
```

La webcam e YOLO non attendono il browser: i rispettivi thread lavorano anche senza connessioni web. Il detector legge l'ultimo frame disponibile e non accoda tutti i fotogrammi. Le predizioni possono percio' essere piu' vecchie del video, specie con movimenti rapidi.

## 3. Interfaccia web: come funziona realmente

Il frontend e' servito **dallo stesso processo FastAPI**, non da un server frontend indipendente:

1. `GET /` legge e restituisce `app/templates/index.html` con `HTMLResponse`. Il file e' letto da disco, non renderizzato con un template engine.
2. `app.mount("/static", StaticFiles(...))` pubblica `/static/app.css` e `/static/app.js`.
3. Il CSS realizza layout a due colonne su schermi grandi e una colonna su schermi piccoli; `.video-stage` posiziona l'overlay.
4. L'elemento `<img id="stream">` riceve il flusso `/stream.mjpg?raw=true`. Il browser visualizza direttamente le parti JPEG successive; non sono necessari librerie video JavaScript, player speciali o codec H.264.
5. Un elemento `<svg id="boxOverlay">` assolutamente posizionato sopra l'immagine mostra le annotazioni. Il suo `viewBox` viene impostato con `width` e `height` riportati da `/api/detections`. `app.js` crea elementi SVG `rect` e `text`: contorni e lettere rimangono vettoriali anche se il video viene ingrandito.
6. `app.js` interroga `/api/health` e `/api/detections` in parallelo ogni **250 ms**. La variabile `refreshing` evita richieste di aggiornamento sovrapposte, ma **non** sincronizza temporalmente il frame video con l'inferenza. Aggiorna inoltre barra di stato e lista delle classi rilevate.
7. Il controllo della confidenza legge `GET /api/config` e invia `POST /api/config` quando si preme **Applica**. Modifica la configurazione in memoria, non un file persistente.
8. Se la webcam non e' disponibile, il frontend nasconde video e overlay, mostra il messaggio dedicato e svuota i rettangoli. Al cambio di `camera_generation`, ricrea l'URL dello stream per gestire la nuova sessione.

**Importante:** aumentare la nitidezza dei box SVG non aumenta la precisione delle coordinate prodotte da YOLO. Le coordinate restano ricavate dal frame acquisito. Con oggetti molto mobili, polling e inferenza possono produrre un disallineamento visibile.

### Modalita' video e compatibilita'

| URL | Contenuto | Destinazione |
| --- | --- | --- |
| `/stream.mjpg?raw=true` | Video MJPEG senza box | Frontend con overlay SVG |
| `/stream.mjpg` | Video MJPEG con box OpenCV | Client precedenti / accesso diretto |
| `/api/frame.jpg` | Un frame JPEG annotato | Screenshot/API |
| `/api/detections` | Coordinate, classi e confidenza JSON | Overlay e integrazioni |

La codifica JPEG viene ancora eseguita lato server in streaming e i client non condividono una cache di frame JPEG precodificati. Questo dettaglio e' rilevante se si prevedono molti browser collegati contemporaneamente.

## 4. Componenti Python

### `app/main.py`

Crea l'app FastAPI, monta gli statici, definisce API e streaming e legge gli argomenti CLI. Nel ciclo `lifespan` avvia il thread della webcam e quello dell'inferenza e li arresta alla chiusura. Con `/stream.mjpg` prepara una risposta `StreamingResponse` di tipo `multipart/x-mixed-replace`, con limite nominale di 15 iterazioni/s per connessione. Il valore misurato `video_fps` riguarda l'invio lato server, non la frequenza effettivamente renderizzata nel browser.

### `app/camera.py`

Gestisce `cv2.VideoCapture` in un thread separato. In modalita' `auto` cerca i dispositivi `/dev/video*`, prova la connessione e salva soltanto l'ultimo frame sotto lock. I parametri predefiniti richiesti al driver sono **320 x 240, 15 FPS**, ma il driver puo' negoziare valori diversi. Espone copie dei frame tramite `snapshot()`, contatore `camera_generation`, stato e stima FPS. Se la sorgente scompare, ritenta dopo 2 secondi; frame piu' vecchi di 2 secondi non sono considerati validi.

### `app/detector.py`

Carica `YOLO(model_path)` da Ultralytics e gestisce **un thread** di inferenza. Richiama `model.predict(..., imgsz=320, device="cpu")`; converte le predizioni in strutture Pydantic con coordinate `x1,y1,x2,y2` e conserva l'ultimo risultato valido per la generazione della webcam. Tiene metriche di tempo, FPS ed errori. La funzione `process()` continua a disegnare rettangoli raster con OpenCV per gli endpoint legacy; il browser moderno usa invece soltanto il JSON.

### `app/schemas.py`

Definisce `BoundingBox`, `Detection`, `DetectionResponse`, `RuntimeConfig` e `HealthResponse`. Pydantic valida la confidenza nell'intervallo **0,05–0,95** e l'intervallo di inferenza tra **0,05 e 5 secondi**.

## 5. API REST

| Metodo e route | Scopo |
| --- | --- |
| `GET /` | Pagina HTML |
| `GET /static/*` | CSS e JavaScript |
| `GET /stream.mjpg` | Streaming annotato preesistente |
| `GET /stream.mjpg?raw=true` | Streaming pulito per SVG |
| `GET /api/frame.jpg` | Immagine annotata singola; 503 senza webcam |
| `GET /api/detections` | Ultime rilevazioni; lista vuota senza webcam |
| `GET /api/classes` | Associazione ID/nome classi YOLO |
| `GET /api/config` | Configurazione runtime |
| `POST /api/config` | Aggiornamento configurazione runtime |
| `GET /api/health` | Webcam, risoluzione, client e metriche |
| `GET /docs` | Documentazione OpenAPI interattiva FastAPI |

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/detections
curl http://localhost:8000/api/config
```

## 6. Avvio e servizio

Esecuzione manuale, dalla directory della repository:

```bash
.venv/bin/python -m app.main --host 0.0.0.0 --port 8000
```

Opzioni principali: `--camera auto`, `--width 320`, `--height 240`, `--camera-fps 15`, `--model yolov8n.pt`, `--confidence 0.35`, `--inference-interval 0.25`.

`scripts/install_service.sh` crea `/etc/systemd/system/rasp3-yolo.service`: usa il Python del venv, avvia l'app sulla porta 8000, imposta `Restart=on-failure` e `RestartSec=5`. Non installa Nginx o un server frontend distinto.

```bash
sudo systemctl status rasp3-yolo --no-pager
sudo journalctl -u rasp3-yolo -n 100 --no-pager
sudo systemctl restart rasp3-yolo
```

Il server e' esposto sulla rete con `--host 0.0.0.0`. **Le API di configurazione non implementano autenticazione**: utilizzare una rete fidata o proteggere l'accesso prima di pubblicare il servizio su Internet.

## 7. Manutenzione, prestazioni e limiti

- **Modificare l'aspetto:** `app/static/app.css`.
- **Cambiare box/etichette SVG:** funzione `drawBoxes()` in `app/static/app.js`.
- **Cambiare layout e controlli:** `app/templates/index.html`, poi logica in `app/static/app.js`.
- **Cambiare acquisizione:** `app/camera.py`; verificare sempre la risoluzione reale in `/api/health`.
- **Cambiare inferenza:** `app/detector.py`; mantenere le coordinate coerenti con `DetectionResponse.width/height`.
- **Aggiungere endpoint:** `app/main.py` e, dove necessario, schemi in `app/schemas.py`.
- **Eseguire il deploy:** `git pull --ff-only`, eventuale aggiornamento dipendenze e `sudo systemctl restart rasp3-yolo`.
- **Aggiornare la pagina:** forzare il refresh del browser con Ctrl+F5 per bypassare la cache di JS/CSS.

Limiti correnti: MJPEG puo' consumare banda; i box SVG non sono sincronizzati frame-per-frame; polling ogni 250 ms aggiunge richieste HTTP; le configurazioni non sopravvivono al restart; non vi sono autenticazione o storico persistente delle rilevazioni. Gli FPS vanno misurati sul Raspberry reale, non dedotti dalla sola configurazione.

## 8. Mappa dei file

```text
app/
  main.py                 FastAPI, routing, MJPEG, CLI e ciclo di vita
  camera.py               Worker acquisizione e recupero webcam
  detector.py             Inferenza YOLO e annotazioni legacy
  schemas.py              Schemi JSON e validazione API
  templates/index.html    Struttura dell'unica pagina web
  static/app.css          Layout, colori, overlay video
  static/app.js           Polling API, controlli, SVG e stato UI
scripts/
  install_service.sh      Installazione servizio systemd
  setup_raspberry.sh      Preparazione ambiente Raspberry
docs/
  architettura.md         Questa guida
  installazione_ssh.md    Installazione, aggiornamento e debug
  laboratorio.md          Attivita' didattiche
requirements-rpi.txt      Dipendenze Python con versioni
```
