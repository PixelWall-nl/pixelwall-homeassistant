# Pixelwall — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/PixelWall-nl/pixelwall-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/PixelWall-nl/pixelwall-homeassistant/actions/workflows/validate.yml)

Bedien je [Pixelwall](https://pixelwall.nl)-scherm vanuit Home Assistant en stuur er meldingen naartoe.
Home Assistant praat alleen met het scherm in je eigen netwerk. Het scherm haalt zijn beelden wel
van pixelwall.nl en geeft daarom door wat je stuurt (meldingen, helderheid, pagina's en de waarden
erop) aan pixelwall.nl, dat de beelden tekent.

## Wat krijg je?

Per scherm één apparaat met:

| Entiteit | Wat |
|---|---|
| `light.<scherm>` | Aan/uit en helderheid. Geldt tot het helderheidsschema de volgende keer verandert. |
| `select.<scherm>_app` | De app die nu in beeld is; kies er een om hem direct te tonen. |
| `switch.<scherm>_<app>_in_rotatie` | Per app: in de rotatie of niet. Zet bijvoorbeeld Qmusic uit zolang de radio iets anders speelt. Firmware 0.13.0-beta.7+. |
| `update.<scherm>_firmware` | Geïnstalleerde en nieuwste firmware; **Installeren** werkt het scherm direct bij (dat doet het anders zelf binnen een paar minuten). Firmware 0.13.2+. |
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
Kan het scherm pixelwall.nl even niet bereiken, dan tekent het de melding zelf (firmware 0.13.2+).

## Eigen pagina's

Met **`pixelwall.set_page`** zet je je eigen gegevens op het scherm. Een pagina draait mee in de
rotatie (als de app *Home Assistant*) en heeft één van vijf indelingen:

| `layout` | Wat |
|---|---|
| `grid` | 2×2 tegels (of 3×2 bij 5–6 items): waarde, icoon, label |
| `value` | één grote waarde met label |
| `list` | regels "label … waarde", bijvoorbeeld een afvalkalender |
| `gauge` | één waarde met een balk tussen `min` en `max` (accu, regenton, CO2) |
| `chart` | grafiek van de laatste waarden van het eerste item |

```yaml
action: pixelwall.set_page
data:
  device_id: 1234abcd…
  page: thuis                     # dezelfde naam opnieuw vervangt de pagina
  title: Thuis                    # optioneel, klein bovenaan
  layout: grid
  items:                          # maximaal 6
    - entity: sensor.woonkamer_temperatuur
      label: Binnen
      icon: thermometer
    - entity: sensor.buiten_temperatuur
      label: Buiten
      color: [136, 204, 255]
    - entity: sensor.zonnepanelen_vermogen
      label: Zon
      icon: sun
    - entity: sensor.thuisaccu
      label: Accu
      unit: "%"                   # standaard de eenheid van de entiteit
```

**Items met een `entity` volgen die vanzelf.** Je hoeft de pagina maar één keer in te stellen
(bijvoorbeeld vanuit Ontwikkelhulpmiddelen → Acties). Elke wijziging gaat daarna binnen een
seconde rechtstreeks naar het scherm, dat de waarde zelf invult: snel, zonder op pixelwall.nl te
wachten, en het blijft werken als pixelwall.nl even weg is. Daarna geeft het scherm de waarden ook
door aan pixelwall.nl, dat de pagina tekent; het ontwerp van je pagina's en de stand van de
entiteiten erop komen dus ook daar terecht. De integratie onthoudt de pagina's, ook na een herstart.

Items zonder entiteit krijgen een vaste `value`; die zet je later bij met **`pixelwall.set_values`**,
bijvoorbeeld vanuit een template:

```yaml
action: pixelwall.set_values
data:
  device_id: 1234abcd…
  page: afval
  values:
    gft: "{{ states('sensor.afval_gft') }}"
```

Een pagina weghalen: **`pixelwall.delete_page`** met `page`. Per scherm passen 8 pagina's.
Pagina's en lokale waarden hebben firmware 0.13.2 of nieuwer nodig.

## Installatie

1. Het scherm moet firmware **0.9.0** of nieuwer hebben (werkt zichzelf automatisch bij).
2. HACS → ⋮ → *Custom repositories* → `https://github.com/PixelWall-nl/pixelwall-homeassistant`, type *Integration*.
3. Installeer **Pixelwall** en herstart Home Assistant.
4. Het scherm wordt vanzelf gevonden (*Instellingen → Apparaten & diensten*). Zo niet: *Integratie toevoegen → Pixelwall*, met `pixelwall-<id>.local` of het IP-adres.
5. Vul de **koppelsleutel** in: [pixelwall.nl](https://pixelwall.nl) → Schermen → je scherm → tab *Home Assistant*.

Maak je daar een nieuwe sleutel, dan vraagt Home Assistant vanzelf om de nieuwe.

Krijgt het scherm een ander adres, dan volgt de integratie het alleen als het scherm op het nieuwe
adres aantoont dat het de koppelsleutel kent, zonder dat Home Assistant die sleutel daarheen stuurt
(firmware 0.13.5+). Zo kan een ander apparaat in je netwerk zich niet als je scherm voordoen. Bij
oudere firmware blijft het oude adres staan; voeg het scherm dan opnieuw toe met het nieuwe adres.

## Lokale API

De integratie gebruikt de API op het scherm zelf; die kun je ook direct aanroepen (header `X-Pixelwall-Key`):

| | |
|---|---|
| `GET /api/info` | id, model, firmware, naam (zonder sleutel) |
| `GET /api/info?nonce=<32 hex>` | idem, plus `proof` = HMAC-SHA256(sleutel, `"pixelwall-proof:" + nonce`) in hex (firmware 0.13.5+) |
| `GET /api/state` | helderheid, aan/uit, huidige app, apps (met `enabled`), wifi |
| `POST /api/brightness?value=0..100[&minutes=N]` | helderheid |
| `POST /api/power?state=on\|off\|toggle` | aan/uit |
| `POST /api/auto` | terug naar het schema |
| `POST /api/next`, `/api/previous` | volgende/vorige app |
| `POST /api/show` `{"app": "weather"}` | app tonen |
| `POST /api/enable` `{"app": "weather", "enabled": false}` | app uit (of weer in) de rotatie |
| `POST /api/update` | nu naar een firmware-update zoeken en installeren |
| `POST /api/page` `{page, title, layout, items}` | pagina instellen (`{page, delete: true}` haalt hem weg) |
| `POST /api/values` `{page, values: {key: tekst}}` | waarden van een pagina, direct in beeld |
| `POST /api/notify` `{"title", "message", "icon", "color", "duration"}` | melding |

## Licentie

MIT
