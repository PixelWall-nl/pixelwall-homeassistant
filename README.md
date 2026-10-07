# Pixelwall — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/PixelWall-nl/pixelwall-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/PixelWall-nl/pixelwall-homeassistant/actions/workflows/validate.yml)

Bedien je [Pixelwall](https://pixelwall.nl)-scherm vanuit Home Assistant en stuur er meldingen naartoe.
Alles gaat rechtstreeks naar het scherm in je eigen netwerk (geen cloud ertussen).

## Wat krijg je?

Per scherm één apparaat met:

| Entiteit | Wat |
|---|---|
| `light.<scherm>` | Aan/uit en helderheid. Geldt tot het helderheidsschema de volgende keer verandert. |
| `select.<scherm>_app` | De app die nu in beeld is; kies er een om hem direct te tonen. |
| `button.<scherm>_volgende_app` / `_vorige_app` | Door de apps bladeren (of een melding wegklikken). |
| `button.<scherm>_helderheidsschema_volgen` | Terug naar het schema na een handmatige helderheid. |
| `notify.<scherm>_melding` | Werkt met `notify.send_message`. |
| `binary_sensor.<scherm>_verbonden_met_pixelwall_nl` | Of het scherm zijn beelden kan ophalen. |
| `sensor.<scherm>_wifi_signaal` | Wifi-signaal (standaard uit). |

En de actie **`pixelwall.show_message`**, met titel, icoon, kleur en duur:

```yaml
action: pixelwall.show_message
data:
  device_id: 1234abcd…           # je Pixelwall (meerdere mag)
  title: Deurbel
  message: Er staat iemand voor de deur
  icon: bell                      # bell, info, warning, check, home, door, lock, car, mail,
                                  # thermometer, water, music, heart, sun, bolt
  color: [255, 200, 0]            # kleur van de balk
  duration: 20                    # seconden
```

Meldingen komen na elkaar in beeld, tussen P2000-meldingen (gaan voor) en de gewone apps.

## Installatie

1. Het scherm moet firmware **0.9.0** of nieuwer hebben (werkt zichzelf automatisch bij).
2. HACS → ⋮ → *Custom repositories* → `https://github.com/PixelWall-nl/pixelwall-homeassistant`, type *Integration*.
3. Installeer **Pixelwall** en herstart Home Assistant.
4. Het scherm wordt vanzelf gevonden (*Instellingen → Apparaten & diensten*). Zo niet: *Integratie toevoegen → Pixelwall*, met `pixelwall-<id>.local` of het IP-adres.
5. Vul de **koppelsleutel** in: [pixelwall.nl](https://pixelwall.nl) → Schermen → je scherm → tab *Home Assistant*.

Maak je daar een nieuwe sleutel, dan vraagt Home Assistant vanzelf om de nieuwe.

## Lokale API

De integratie gebruikt de API op het scherm zelf; die kun je ook direct aanroepen (header `X-Pixelwall-Key`):

| | |
|---|---|
| `GET /api/info` | id, model, firmware, naam (zonder sleutel) |
| `GET /api/state` | helderheid, aan/uit, huidige app, apps, wifi |
| `POST /api/brightness?value=0..100[&minutes=N]` | helderheid |
| `POST /api/power?state=on\|off\|toggle` | aan/uit |
| `POST /api/auto` | terug naar het schema |
| `POST /api/next`, `/api/previous` | volgende/vorige app |
| `POST /api/show` `{"app": "weather"}` | app tonen |
| `POST /api/notify` `{"title", "message", "icon", "color", "duration"}` | melding |

## Licentie

MIT
