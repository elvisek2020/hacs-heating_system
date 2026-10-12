# Changelog

Poznámky k vydání. Sekce `## vX.Y.Z` se při releasu automaticky použije jako
text vydání na GitHubu — a ten Home Assistant / HACS ukazuje v okně aktualizace.

Nejnovější verze je nahoře. Starší historie je v [GitHub releases](https://github.com/elvisek2020/hacs-heating_system/releases).

## v0.7.0 — 2026-10-13

### ✨ Novinky

- **Rozvrh domu:** jeden pomocník Plán pro celý dům místo rozvrhu u každé místnosti. Zapnuto = komfort, vypnuto = útlum (noc, práce, škola).
  - Nastavuje se v **Konfigurovat → Rozvrh, přítomnost a předtápění → Rozvrh domu**.
  - Platí pro všechny místnosti bez vlastního rozvrhu. Vlastní rozvrh místnosti má přednost.
  - Předtápění začne včas před začátkem komfortu v rozvrhu domu.
- Dashboard ukazuje v sekci Topení dlaždici rozvrhu domu se stavem a časem příští změny. Termostat místnosti má atribut `schedule_entity`, podle kterého rozvrhu jede.
- Výchozí útlum nově přidaných místností je 19 °C (dřív 18 °C). Stávající místnosti si nastavení ponechají.

Po aktualizaci restartuj Home Assistant. Dlaždice rozvrhu se na dashboardu objeví po novém vygenerování službou `hydronic_heating.generate_dashboard`.

## v0.6.2 — 2026-10-13

### 🎨 Vzhled

- Dashboard u každé místnosti ukazuje jen **Ventil**: jestli je otevřený, otevírá se, zavírá se nebo je zavřený. Dlaždice hlavic (demo a skutečná) zmizely, protože hlavice je jen pohon ventilu a u hlavic NO „Vypnuto“ znamenalo otevřeno.
- Časová osa v Grafech ukazuje polohu ventilu v každé místnosti místo spínačů hlavic.

Nový vzhled získáš po novém vygenerování dashboardu službou `hydronic_heating.generate_dashboard`.

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
