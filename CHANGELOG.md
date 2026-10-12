# Changelog

Poznámky k vydání. Sekce `## vX.Y.Z` se při releasu automaticky použije jako
text vydání na GitHubu — a ten Home Assistant / HACS ukazuje v okně aktualizace.

Nejnovější verze je nahoře. Starší historie je v [GitHub releases](https://github.com/elvisek2020/hacs-heating_system/releases).

## v0.6.1 — 2026-10-12

### ✨ Novinky

- Poznámky k vydání se nově píšou do `CHANGELOG.md` a vydání vytváří GitHub Actions z tagu. Home Assistant je ukáže v okně aktualizace.
- README podle jednotného standardu: předpoklady, instalace přes HACS i ručně, tlačítko „Otevřít v HACS“, známá omezení.

Kód integrace se nemění.

## v0.6.0 — 2026-10-12

### ✨ Novinky

- **Přítomnost:** nový krok **Konfigurovat → Přítomnost a předtápění**. Stačí běžné entity: modul přítomnosti, skupina osob, nebo `zone.home` (počet lidí doma).
  - Když nikdo není doma, místnosti v režimu automaticky jedou na útlum. Místo útlumu jde zvolit teplota Pryč.
  - Dlouhodobá nepřítomnost (víkend, dovolená) přepne celý dům na teploty Pryč. Zvolený režim se přitom nemění.
  - Nedostupná entita drží poslední stav, takže výpadek telefonu dům nevychladí.
  - U místnosti jde nastavit vlastní přítomnost, třeba konkrétní osobu pro dětský pokoj.
- **Předtápění s učením:**
  - Topení se u každé místnosti učí, jak rychle se ohřívá: °C za hodinu podle venkovní teploty, z mediánu posledních 8 ohřevů. Dokud nemá data, počítá s 0,5 °C/h.
  - Začne topit tak, aby byl komfort na čas, kdy rozvrh (helper `schedule`) přepne na komfort, nebo kdy se někdo vrací. Nejdřív začne 4 h předem, maximum jde změnit.
- **Kde to uvidíte:**
  - Logbook zapisuje změny přítomnosti a start předtápění, například „Předtápění: Obývák na 21 °C do 15:00 (očekávaný návrat), rychlost ohřevu 0,8 K/h.“
  - Termostat místnosti a `climate.hh_system` mají nové atributy.
  - Stav ventilu má nový důvod *Předtápění*.
  - Dashboard má odznaky *Doma* a *Dlouhodobě pryč*.

### ⚠️ Změny, které vyžadují zásah

- Nepřítomnost nastavená přímo u místnosti dřív vždy vedla na teplotu Pryč. Teď vede na zvolenou teplotu pro nepřítomnost, výchozí je útlum.
- Bez nastavené přítomnosti a bez rozvrhu se chování nemění.

Po aktualizaci restartuj Home Assistant. Odznaky na dashboardu se objeví až po novém vygenerování službou `hydronic_heating.generate_dashboard`.
