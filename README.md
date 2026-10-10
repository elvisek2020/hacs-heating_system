# Hydronic Heating Controller

Vlastní integrace pro Home Assistant, která řídí teplovodní ústřední topení: kotel spínaný beznapěťovým kontaktem, radiátory a termoelektrické hlavice NO/NC. Staví jen na obecných entitách HA, takže výměna hardwaru (dnes Loxone přes PyLoxone) znamená jen přemapovat entity v nastavení.

## Stav

**Fáze F0: jen konfigurace.** Integrace se nainstaluje, projde nastavením a uloží všechny parametry systému i místností. Zatím nic neřídí a nevytváří žádné entity. Řízení přijde ve fázi F1.

| Fáze | Obsah |
|---|---|
| **F0** ✅ | kostra, config flow, nastavení systému, místnosti, ikona, CI |
| F1 | místnosti, ventily, kotel, arbitr, ochrana kotle, manuál, režimy, shadow |
| F2 | okna, mráz, léto, protáčení, notifikace, diagnostika |
| F3 | ekviterm: topná křivka, omezení střídy |

## Instalace přes HACS

1. HACS → tři tečky vpravo nahoře → **Vlastní repozitáře**.
2. Repozitář `https://github.com/elvisek2020/hacs-heating_system`, typ **Integrace**.
3. Nainstalovat **Hydronic Heating Controller** a restartovat Home Assistant.
4. Nastavení → Zařízení a služby → **Přidat integraci** → Hydronic Heating Controller.

Vyžaduje Home Assistant 2026.3 nebo novější.

## Nastavení

- **Průvodce při přidání:** název, režim shadow, zdroj tepla (spínač, dvojice akcí nebo select), venkovní teplota a hlavní ochrana kotle.
- **Místnosti:** v integraci tlačítko **Přidat místnost**. Průvodce projde název a teploty, čidla, ventily (u každého NO/NC a doby přestavení), okenní kontakty, rozvrh a regulaci. Místnost jde kdykoli upravit.
- **Ostatní parametry:** v integraci **Konfigurovat**. Menu je rozdělené na obecné, zdroj tepla, venkovní teplotu, kotel a požadavky, bezpečnost, ventily, okna, manuál, ekviterm a mráz.

Všechno se mění jen v nastavení, bez úprav kódu a bez restartu HA.

### Příprava v Loxone

Kotel a každá hlavice musí být v Loxone Config jako stavový blok **Switch**, ne Pushbutton, a výstup smí řídit jen jeden vlastník: buď Loxone, nebo tato integrace. Doporučený je i watchdog v Loxone: když integrace přestane přepínat výstup heartbeat, Loxone vypne kotel a odpojí napájení NO hlavic.

## Vývoj

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt ruff
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Validace stejná jako v CI:

```bash
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest
```
