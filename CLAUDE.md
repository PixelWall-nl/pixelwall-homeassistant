# Pixelwall Home Assistant — ontwikkelnotities

De integratie praat alleen met de lokale API van het scherm (firmware 0.9+, `firmware/src/localapi.cpp`
in de Pixelwall-monorepo). Nieuwe endpoints daar eerst bouwen, dan hier gebruiken.

## Nieuwe versie uitbrengen

HACS detecteert alleen GitHub releases, niet losse commits of tags. Altijd alle drie stappen uitvoeren:

1. Versienummer ophogen in `custom_components/pixelwall/manifest.json`
2. Committen en pushen naar `main`
3. GitHub release aanmaken:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
```
