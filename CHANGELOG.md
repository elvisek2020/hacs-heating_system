# Changelog

Poznámky k vydání. Sekce `## vX.Y.Z` se při releasu automaticky použije jako
text vydání na GitHubu — a ten Home Assistant / HACS ukazuje v okně aktualizace.

Nejnovější verze je nahoře. Starší historie je v [GitHub releases](https://github.com/elvisek2020/hacs-heating_system/releases).

## v0.11.0 — 2026-10-13

### ✨ Novinky

- **Komfort a ECO přímo v kartě místnosti.** Pod ventilem jsou dvě pole s tlačítky −/+ pro trvalou komfortní a útlumovou teplotu. Místnost při jejich změně zůstává v automatice. −/+ na termostatu dál nastavuje jen ruční cíl a místnost přepne na ručně.
- **Teplota Pryč:** nová entita `number.hh_<místnost>_away`. V kartě místnosti je jen tehdy, když se používá (dlouhodobá nepřítomnost, nebo předvolba nepřítomnosti Pryč).
- Pole hlídají stejná pravidla jako nastavení místnosti: ECO nejde nad komfort, ECO ani Pryč nejdou na protimrazovou teplotu nebo pod ni.
- **Skutečný stav kotle.** Se zpětnou vazbou je v Provozu kotle hned za povelem dlaždice „Kotel (skutečný stav)“. Odznak Kotel v horní liště ukazuje, jestli kotel opravdu běží, a v Grafech je skutečný stav jako čára pod povelem.

### 🎨 Vzhled

- Karta místnosti: termostat, požadavek, ventil, Komfort a ECO, vlastní rozvrh.
- Vysvětlivky popisují i odznaky horní lišty (Doma, Dlouhodobě pryč, Okna). Ikony odznaků odpovídají legendě.

Po aktualizaci dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.10.0 — 2026-10-13

### ✨ Novinky

- **Měřená teplota vody.** Nové volitelné čidlo v Konfigurovat → Zdroj tepla, například na stoupačce od kotle. Dashboard ukazuje skutečnou teplotu vody místo teploty podle topné křivky.
- **Kontrola, že kotel opravdu topí** (Konfigurovat → Bezpečnost):
  - když kotel běží 15 min a teplota vody nestoupne aspoň o 5 °C, ohlásí se porucha „Kotel běží, ale netopí“ (oznámení, Opravy, Porucha),
  - doba i nárůst jdou nastavit, doba 0 kontrolu vypne; se zpětnou vazbou hořáku se počítá jen doba, kdy hořák běží,
  - kotel se nevypíná, porucha zmizí sama, až voda při běhu kotle zase ohřeje.
- **Skutečná venkovní teplota:** nová entita `sensor.hh_outdoor_temperature`. Na dashboardu je vedle ní 4h průměr s hranicí topné sezóny.

### 🎨 Vzhled

- **Jen to, co používáš.** Okna, blokace okny, omezení střídy, teplota podle křivky ani tlumená teplota se na dashboardu neukazují, když je nemáš nastavené.
- **Barvy podle významu:** kotel oranžově, požadavky a sezóna jantarově, voda a porucha červeně, venek modře, ventily tyrkysově, osoby zeleně.
- **Provoz kotle podle priority:** povel kotli, požadavek na teplo, venku (průměr 4 h), porucha, topná sezóna, starty dnes, střída 24 h.
- **Karta místnosti:** termostat, požadavek, ventil, vlastní rozvrh. Text pod termostatem je pryč, důvod cíle je v atributech termostatu a v logbooku.
- **Kdo je doma** ukazuje jen osoby, bez skupin a počtů, a jménem bez přípony „Doma“.
- **Vysvětlivky** otevře odznak v horní liště, jsou na samostatném skrytém pohledu.

Po aktualizaci nastav čidlo teploty vody (Konfigurovat → Zdroj tepla) a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.9.0 — 2026-10-13

### ✨ Novinky

- **Hlavice bez proudu, když kotel stojí.**
  - Když nikdo nechce teplo a kotel stojí, jsou všechny hlavice v klidové poloze (výchozí bez proudu, NO = otevřeno). Nehřejí a neberou proud zbytečně celé hodiny.
  - Při požadavku se nejdřív zavřou ventily místností, které teplo nechtějí, a teprve pak naskočí kotel. Start se tím zpozdí zhruba o dobu přestavení hlavic. „Proč“ mezitím ukazuje „Zavírají se ventily“.
- **Topná sezóna podle průměru venkovní teploty za 4 hodiny.**
  - Začne hned, jakmile 4h průměr klesne pod hranici (výchozí 13 °C). Skončí po 3 celých dnech po sobě, kdy průměr ani jednou neklesl pod ni.
  - Nový výběr **Topná sezóna**: Automaticky / Topná sezóna / Mimo sezónu.
  - Nové entity `binary_sensor.hh_heating_season` a `sensor.hh_outdoor_mean_4h`.
  - Začátek a konec sezóny se zapíše do logbooku.
- **Rozvrh místnosti podle domu, nebo vlastní.** V nastavení místnosti (Překonfigurovat → Rozvrh). Úprava vlastního plánu mění jen tuto místnost.
- **Vlastní očekávaný návrat místnosti.** Místnost s vlastní přítomností předtápí jen podle svého návratu, ne podle návratu domácnosti.

### 🎨 Vzhled

- **Karta místnosti:**
  - nahoře ovládání: přepínač automaticky / ručně / vypnuto pro rychlý návrat na automatiku, cílová teplota, předvolba,
  - uprostřed zobrazení: proč, **kdo je doma jménem**, ventil, požadavek,
  - dole vlastní rozvrh.
- Pod blokem Provoz kotle je přehled **Kdo je doma**: každá osoba se stavem a časem poslední změny.
- Nad místnostmi je oddělovač „Místnosti – individuální nastavení“, úplně dole **Vysvětlivky** ke každé dlaždici.

### ⚠️ Změny, které vyžadují zásah

- Režim systému **Léto** je zrušený, nahrazuje ho výběr Topná sezóna. Uložený režim Léto se převede na Mimo sezónu.
- Zrušené jsou i volby „Hystereze meze vytápění“, „Zpoždění přechodu do léta“ a entita `binary_sensor.hh_summer`. Automatizace, které ji používaly, přepni na `binary_sensor.hh_heating_season`.
- Hranice 13 °C je výchozí jen pro nové instalace. Zkontroluj ji v Konfigurovat → Ekviterm → **Hranice topné sezóny**.

Po aktualizaci restartuj Home Assistant a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.8.0 — 2026-10-13

### ✨ Novinky

- **U místnosti je vidět, proč má zrovna komfort nebo útlum.**
  - Pod termostatem je věta, například „Útlum 19 °C: nikdo doma (Rodiče doma).“, „Komfort 21 °C podle rozvrhu (Topení dům) do 22:30.“ nebo „Předtápění na 21 °C do 14:30.“
  - Termostat má atributy `target_reason`, `target_until`, `target_detail`, `presence_entity` a `presence_source` (vlastní přítomnost místnosti, nebo celého domu).
- **Přítomnost a rozvrh místnosti na dashboardu.**
  - U místnosti jsou dlaždice přítomnosti a rozvrhu, podle kterých jede. Je u nich poznat, jestli jde o vlastní nastavení, nebo o celý dům.
  - Když je přítomnost místnosti skupina, ukážou se i její členové. Entita se seznamem jmen (atribut `people`) je ukáže rovnou na dlaždici.
- **Deník:** když místnost změní cíl kvůli přítomnosti nebo rozvrhu, zapíše se věta do logbooku, například „Kuchyně: útlum 19 °C, nikdo doma (Rodiče doma).“

### 🎨 Vzhled

- **Přehled má pevné pořadí.**
  - Nahoře je jedna řada: Topení, Kotel a Provoz kotle.
  - Pod ní je přes celou šířku upozornění na shadow režim, v demu blok Demo.
  - Teprve potom jsou místnosti. Místnosti se už nemíchají mezi bloky řízení.
- **Kotel je rozdělený na dva bloky:**
  - *Kotel*: proč, další změna, vysvětlení, celkový požadavek, teplota vody a venku,
  - *Provoz kotle*: povel, požadavek na teplo, střída, starty, omezení střídy, léto, blokace okny a porucha.

Po aktualizaci restartuj Home Assistant a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

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
