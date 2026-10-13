# Scheda laboratorio: object detection con Raspberry Pi 3

## Obiettivi

- Capire il flusso acquisizione immagine, inferenza, visualizzazione.
- Usare un modello YOLO come servizio locale.
- Consumare API REST da altri programmi.
- Ragionare su confidenza, falsi positivi, prestazioni e limiti hardware.

## Durata

2 o 3 ore, modulabile.

## Preparazione docente

1. Installare il progetto sul Raspberry.
2. Verificare che la webcam sia riconosciuta:

   ```bash
   ls /dev/video*
   ```

3. Avviare il server e provare la pagina web.
4. Annotare l'indirizzo IP del Raspberry.

## Percorso studenti

### Esperimento 1: osservare il modello

Gli studenti aprono la pagina web e provano oggetti diversi davanti alla webcam. Annotano:

- oggetto;
- classe rilevata;
- confidenza;
- eventuali errori.

### Esperimento 2: soglia di confidenza

Gli studenti modificano la soglia dalla pagina web e osservano come cambia la risposta.

Domande guida:

- A soglia bassa compaiono più oggetti o meno oggetti?
- A soglia alta si riducono anche alcune rilevazioni corrette?
- Che differenza c'è tra un falso positivo e un falso negativo?

### Esperimento 3: usare le API

Da un altro computer:

```bash
curl http://<ip-raspberry>:8000/api/detections
```

Poi con Python:

```python
import requests

data = requests.get("http://<ip-raspberry>:8000/api/detections", timeout=2).json()
for detection in data["detections"]:
    print(detection["label"], detection["confidence"])
```

### Esperimento 4: prestazioni

Provare avvii con risoluzioni diverse:

```bash
python -m app.main --width 320 --height 240
python -m app.main --width 640 --height 480
```

Gli studenti confrontano FPS e qualità del riconoscimento.

## Estensioni

- Accendere un LED quando viene rilevata una persona.
- Salvare un log CSV delle rilevazioni.
- Integrare Node-RED.
- Costruire una dashboard con grafici.
- Addestrare o usare un modello con classi specifiche per il laboratorio.

