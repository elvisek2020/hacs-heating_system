# Heating Controller

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Release](https://img.shields.io/github/v/release/elvisek2020/hacs-heating_system)](https://github.com/elvisek2020/hacs-heating_system/releases)
[![Validate](https://github.com/elvisek2020/hacs-heating_system/actions/workflows/validate.yml/badge.svg)](https://github.com/elvisek2020/hacs-heating_system/actions/workflows/validate.yml)
[![Licence](https://img.shields.io/github/license/elvisek2020/hacs-heating_system)](LICENSE)

[![Otevřít v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=elvisek2020&repository=hacs-heating_system&category=integration)

Integrace pro Home Assistant, která řídí teplovodní ústřední topení: kotel spínaný beznapěťovým kontaktem, radiátory a termoelektrické hlavice NO/NC. Staví jen na obecných entitách HA, takže výměna hardwaru (dnes Loxone přes PyLoxone) znamená jen přemapovat entity v nastavení.

- místnosti s 1..n teplotními čidly a ventily, regulace TPI nebo hystereze, PWM ventilů s ohledem na pomalé hlavice
- kotel se sekvencí ventily → kotel → doběh a s ochranou proti cyklování (minimální běh, pauza, počet startů)
- režimy, manuální topení s odpočtem, rozvrhy, okna, protimrazová ochrana, topná sezóna podle venkovní teploty
- ekviterm: virtuální teplota vody podle topné křivky a volitelné omezení střídy kotle
- přítomnost domácnosti a předtápění, které se učí rychlost ohřevu místností
- vysvětlení, proč kotel topí nebo stojí, a deník rozhodnutí v logbooku
- shadow a demo režim pro bezpečné ověření před přepnutím z jiné regulace, generovaný dashboard

## Předpoklady a závislosti

- Home Assistant 2026.3 nebo novější.
- Kotel jako entita `switch`, `select` nebo dvojice skriptů či tlačítek (zapnout, vypnout). Typicky beznapěťový kontakt.
- Hlavice jako `switch` (NO nebo NC) nebo `valve`, teplotní čidla místností jako `sensor` nebo `climate`.
- Volitelně: venkovní čidlo nebo entita počasí, okenní kontakty, helper `schedule` pro rozvrh, entity přítomnosti, entita pro heartbeat watchdog.
- Výstup kotle a hlavic smí řídit jen jeden vlastník, viz [Příprava v Loxone](#příprava-v-loxone).

## Instalace

### HACS (doporučeno)

1. HACS → tři tečky vpravo nahoře → **Custom repositories**
2. Vlož URL `https://github.com/elvisek2020/hacs-heating_system`, kategorie **Integration**
3. Nainstaluj **Heating Controller**
4. Restartuj Home Assistant a přidej ji v Nastavení → Zařízení a služby → Přidat integraci.

HACS nabízí aktualizace z GitHub releases.

### Ručně

Zkopíruj `custom_components/hydronic_heating` z posledního [release](https://github.com/elvisek2020/hacs-heating_system/releases) do `/config/custom_components/` a restartuj Home Assistant.

## Konfigurace

1. Přidejte integraci. **Režim shadow** nechte zapnutý: integrace všechno počítá, ale nic nespíná.
2. V integraci přidejte místnosti tlačítkem **Přidat místnost** (čidla, ventily, okna, rozvrh).
3. Nechte systém běžet vedle stávající regulace. Na `climate.hh_system` ukazují atributy `would_command_boiler` a `would_command_valves`, co by integrace udělala.
4. Až rozhodnutí sedí, vypněte `switch.hh_shadow_mode`. Od té chvíle integrace spíná kotel a hlavice.

Všechno se mění jen v nastavení, bez úprav kódu a bez restartu HA. Změna místností nebo délek manuálu integraci krátce znovu načte, ostatní změny se projeví hned.

## Demo režim: ověření před přepnutím z Loxone

V **Konfigurovat → Obecné → Demo režim** jsou dvě možnosti. Obě běží v reálném čase.

- **Virtuální výstupy:** teploty a okna se berou ze skutečných čidel, ale povely jdou do virtuálního kotle `switch.hh_demo_boiler` a virtuálních hlavic `switch.hh_<místnost>_demo_valve_<n>`. Projde celá cesta povelů včetně ověření stavu, opakování a poruchy. Skutečný kotel a ventily dál řídí Loxone, skutečný kotel vidíte na dashboardu vedle virtuálního.
- **Virtuální dům:** navíc simulované teploty místností s tepelným modelem (topení otápí, okno ochlazuje), simulovaná okna, výpadky čidel a venkovní teplota `number.hh_demo_outdoor_temperature`. Hodí se na vyzkoušení událostí od stolu.

Ve virtuálních výstupech i ve virtuálním domě lze přes `select.hh_demo_boiler_behavior` nasimulovat kotel, který je nedostupný nebo ignoruje povely.

**Pojistka:** v demo režimu integrace odmítne poslat povel jakékoli entitě, která jí nepatří. Ani případná chyba v konfiguraci tak nemůže sepnout skutečný kotel nebo hlavici. Heartbeat a zrcadlový časovač se v demu nespínají, notifikace mají v titulku `[Demo]`. Demo si ukládá stav zvlášť, takže se nemíchá s historií skutečného kotle.

**Dashboard:** Nástroje pro vývojáře → Akce → `hydronic_heating.generate_dashboard` → Provést akci. Odpověď je hotový dashboard pro vaši instalaci: systém, manuál, demo, každá místnost s termostatem, požadavkem a ventilem a grafy. Vložíte ho takto: Nastavení → Řídicí panely → Přidat řídicí panel → Nový od začátku, otevřít, ⋮ → Upravit → ⋮ → Editor kódu YAML, obsah nahradit odpovědí a uložit.

### Doporučený postup přepnutí

1. **Virtuální dům:** vyzkoušejte otevřené okno, výpadek čidla, nedostupný kotel, manuál a změnu venkovní teploty (topná sezóna). Ověřte, že reakce odpovídají očekávání.
2. **Virtuální výstupy, několik dní:** v grafech porovnávejte virtuální kotel se skutečným, který řídí Loxone.
3. **Loxone:** kotel a hlavice jako bloky **Switch**, odpojit IRC a Climate Controller od výstupů a zavést watchdog na heartbeat.
4. **Přepnutí:** demo režim vypnout, pak vypnout `switch.hh_shadow_mode`. Od té chvíle integrace spíná skutečné výstupy.

## Jak řídí

- **Místnost:** teplota z 1..n čidel (průměr, minimum, maximum, medián nebo první platné). Požadavek 0–100 % počítá algoritmus TPI nebo hystereze. Ventily jedou v PWM (perioda 30 min, synchronní začátek), s minimální dobou stavu kvůli pomalým hlavicím.
- **Kotel:** zapne se, když vážený požadavek místností překročí práh (s hysterezí), nebo když volá dost místností. Nejdřív se zavřou ventily místností, které teplo nechtějí, a otevřou ty, které ho chtějí. Kotel startuje až po době přestavení, aby voda netekla tam, kde se netopí. Hlídá minimální dobu běhu, minimální pauzu a počet startů za hodinu. Po vypnutí drží ventily otevřené po dobu doběhu.
- **Ventily v klidu:** když kotel stojí a nikdo nechce teplo, jdou všechny hlavice do klidové polohy (výchozí bez proudu, u NO hlavic otevřeno). Hlavice tak nehřejí a neberou proud zbytečně celé hodiny. Proud dostanou jen hlavice místností bez požadavku, a jen během běhu kotle a doběhu.
- **Priority:** porucha > protimrazová ochrana > manuál > blokace okny > mimo topnou sezónu > zvolený režim (vypnuto, pryč, automaticky).
- **Okna:** po zpoždění zavřou ventily místnosti. Při otevření oken ve více místnostech (globální práh) se zastaví kotel, kromě manuálu.
- **Mráz:** místnost pod protimrazovou teplotou topí vždy, i při otevřeném okně a mimo topnou sezónu. Tuto ochranu nejde vypnout.
- **Topná sezóna:**
  - Řídí se průměrem venkovní teploty za poslední 4 hodiny (`sensor.hh_outdoor_mean_4h`), ne denním průměrem, který by schoval studené večery po slunečném dni.
  - Začne hned, jakmile 4h průměr klesne pod hranici (výchozí 13 °C, Konfigurovat → Ekviterm → Hranice topné sezóny).
  - Skončí po 3 celých dnech po sobě, kdy 4h průměr ani jednou neklesl pod hranici.
  - Ručně jde přepnout výběrem `select.hh_heating_season`: Automaticky, Topná sezóna, Mimo sezónu.
  - Stav ukazuje `binary_sensor.hh_heating_season` (atributy: 4h průměr, celé dny nad hranicí, od kdy). Začátek a konec se zapíše do logbooku.
- **Ekviterm:** z tlumené venkovní teploty se podle topné křivky počítá teplota vody, kterou by soustava potřebovala (`sensor.hh_flow_setpoint`). U kotle řízeného jen kontaktem je to virtuální hodnota: kotel si vodu drží sám. Z ní a z teploty nastavené na kotli vychází povolená střída (`sensor.hh_duty_limit`). Po zapnutí omezení střídy (Konfigurovat → Ekviterm) kotel v cyklu (výchozí 20 min) běží jen tuto část času, nikdy ale kratší dobu, než je jeho minimální doba běhu. Ve výchozím stavu je omezení vypnuté. U nekondenzačního kotle ho zapínejte až po ověření minimální teploty vody v návodu kotle, protože zkracuje běhy.
- **Předpověď (volitelně):** s entitou počasí se pro topnou křivku bere průměr tlumené teploty a průměrné předpovědi na příštích 24 hodin.
- **Ochrany:** ověření každého povelu s opakováním, keep-alive, obnovení stavu ventilů po výpadku, bezpečný stav při nedostupném kotli, heartbeat pro watchdog v Loxone, upozornění na zastaralá čidla.

## Rozvrh, přítomnost a předtápění

Všechno se nastavuje v **Konfigurovat → Rozvrh, přítomnost a předtápění**.

**Rozvrh domu** je jeden pomocník **Plán** (`schedule`) pro celý dům: zapnuto = komfort, vypnuto = útlum (noc, práce, škola). Plán se zakládá v Nastavení → Zařízení a služby → Pomocníci → Vytvořit pomocníka → Plán.

U každé místnosti jde v Překonfigurovat → Rozvrh zvolit:
- **Podle domu** (výchozí): místnost jede podle rozvrhu domu.
- **Vlastní**: místnost dostane vlastní plán, například když ložnice chce jiné časy. Úprava vlastního plánu mění jen tuto místnost.

Tamtéž jde nastavit **očekávaný návrat** místnosti, třeba návrat osoby, podle které místnost jede. Pro předtápění místnosti s vlastní přítomností platí jen její vlastní návrat. Návrat domácnosti se použije jen u místností bez vlastní přítomnosti.

Přítomnost se nastavuje běžnými entitami, například vlastním modulem přítomnosti, skupinou osob nebo `zone.home` (počet lidí doma).

- **Někdo doma:** zapnuto nebo `home` znamená doma, číslo větší než 0 taky. Když nikdo není doma, místnosti v režimu automaticky jedou na útlum. V nastavení jde místo útlumu zvolit teplotu Pryč. Nedostupná entita drží poslední stav, takže výpadek telefonu dům nevychladí.
- **Dlouhodobě pryč:** zapnuto znamená víkend nebo dovolenou. Celý dům jede na teploty Pryč a stav systému je `away`. Zvolený režim se nemění, po návratu jede topení samo zase normálně.
- **Očekávaný návrat:** časové razítko nejbližšího návratu. Topení podle něj předtápí.
- **Přítomnost v místnosti:** u místnosti jde dál nastavit vlastní entitu, třeba konkrétní osobu pro dětský pokoj.

**Předtápění** se zapíná v nastavení a je zapnuté ve výchozím stavu.
- **Co se učí:** jak rychle se která místnost ohřívá, ve °C za hodinu a podle venkovní teploty. Bere medián posledních 8 ohřevů. Dokud nemá data, počítá s 0,5 °C za hodinu.
- **Kdy začne:** včas před začátkem komfortu v rozvrhu (domu nebo místnosti) nebo před očekávaným návratem. Počítá s dobou přestavení hlavic a náběhem kotle, ale nikdy nezačne dřív než nastavené maximum (výchozí 4 h).
- **Kde je to vidět:** na termostatu místnosti v atributech `preheating`, `preheat_until`, `preheat_planned` a `heat_rate_k_h`. Do logbooku se zapíše věta, například „Předtápění: Obývák na 21 °C do 15:00 (očekávaný návrat), rychlost ohřevu 0,8 K/h.“

Bez nastavené přítomnosti a bez rozvrhu se nic nemění.

**Proč má místnost zrovna komfort nebo útlum:**
- Termostat místnosti má atributy:
  - `target_reason`: důvod cíle, třeba `schedule_eco`, `absent`, `preheat`, `override` nebo `window`,
  - `target_until`: do kdy cíl platí,
  - `target_detail`: celá věta, například „Útlum 19 °C: nikdo doma (Rodiče doma).“,
  - `presence_entity` a `presence_source`: podle čí přítomnosti místnost jede (`room` = vlastní, `house` = celý dům).
- Dashboard ukazuje u místnosti tuhle větu, **kdo je doma jménem** a rozvrh domu. Vlastní rozvrh je dole v kartě jako upravitelná dlaždice.
  - Jména se berou z atributu `people` (modul přítomnosti), u skupin z členů v atributu `entity_id`.
  - Pod blokem Provoz kotle je přehled „Kdo je doma“: každá osoba se stavem a časem poslední změny, takže je vidět, kdo právě odešel.
- Když místnost změní cíl kvůli přítomnosti nebo rozvrhu, zapíše se to do logbooku, například „Kuchyně: útlum 19 °C, nikdo doma (Rodiče doma).“

## Dashboard

Služba `hydronic_heating.generate_dashboard` vrátí dashboard pro tuto instalaci (vložit přes ⋮ → Upravit → ⋮ → Editor kódu YAML).

- **Nahoře jedna řada:**
  - Topení: systém, režim, topná sezóna, rozvrh domu, manuál.
  - Kotel: proč, další změna, celkový požadavek, teplota vody a venku.
  - Provoz kotle: povel, statistiky, sezóna, blokace a porucha, pod tím Kdo je doma.
- **Pod řadou** upozornění na shadow režim přes celou šířku, v demu blok Demo.
- **Místnosti – individuální nastavení:**
  - nahoře ovládání (režim místnosti automaticky / ručně / vypnuto, cílová teplota, předvolba),
  - uprostřed zobrazení (proč, kdo je doma, ventil, požadavek),
  - dole vlastní rozvrh.
- **Vysvětlivky** úplně dole: každá dlaždice se stejnou ikonou a jednou až dvěma větami, co znamená.

## Proč kotel topí nebo stojí

Ochrana kotle někdy drží kotel v chodu nebo ve stání i proti tomu, co zrovna chcete. Například po **Stop** kotel doběhne svou minimální dobu běhu. Proto integrace vždy ukazuje, proč je kotel v aktuálním stavu a kdy se to změní:

- `sensor.hh_boiler_reason` říká důvod, třeba „Minimální doba běhu“, „Minimální pauza“, „Doběh“ nebo „Topí na požadavek“. Atribut `detail` obsahuje celou větu, například „Teplo už nikdo nechce, ale kotel musí běžet minimální dobu 10 min. Vypne se v 00:55:12.“ V atributu `rule` je nastavení, které za tím stojí.
- `sensor.hh_boiler_hold_ends_at` ukazuje, kdy časové pravidlo skončí. Dashboard z něj dělá odpočet „za 4 minuty“.
- **Logbook** (Aktivita) zapisuje každé zapnutí a vypnutí kotle s příčinou a každé odložení povelu s časem. Zapíše i výstup, který někdo přepnul ručně a integrace ho vrátila. Stejné věty jsou v logu Home Assistantu. Ve shadow režimu mají předponu `[Shadow]`, v demu `[Demo]`.
- U ventilů ukazují atributy `reason` a `until` na `sensor.hh_<místnost>_valve_state`, proč je ventil otevřený nebo zavřený (PWM, okno, doběh kotle, protáčení…) a kdy se to změní.

Výstup kotle nebo hlavice, který přepnete ručně, integrace vrátí. Vlastníkem výstupu je ona (ověření povelu). Ručně topit jde přes manuál, ne přepnutím výstupu.

## Entity

| Entita | Popis |
|---|---|
| `climate.hh_system` | souhrn systému; vypnuto / automaticky / topit (= manuál) |
| `select.hh_system_mode` | auto, manual, off, away |
| `select.hh_heating_season` | topná sezóna: automaticky, topná sezóna, mimo sezónu |
| `button.hh_manual_30` … `_180`, `button.hh_stop` | manuální topení a jeho zastavení |
| `sensor.hh_manual_ends_at` | konec manuálu (časové razítko) |
| `sensor.hh_state` | stav automatu (start, auto, pryč, vypnuto, mimo sezónu, manuál, porucha) |
| `sensor.hh_boiler_reason` | proč je kotel v aktuálním stavu (atributy: do kdy, zbývá, pravidlo, vysvětlení) |
| `sensor.hh_boiler_hold_ends_at` | kdy skončí časové pravidlo, které kotel drží (minimální běh, pauza, doběh…) |
| `sensor.hh_demand_total` | vážený požadavek místností |
| `sensor.hh_outdoor_temperature_damped` | tlumená venkovní teplota (atributy: aktuální, předpověď, efektivní) |
| `sensor.hh_outdoor_mean_4h` | průměr venkovní teploty za 4 h, podle něj se řídí topná sezóna |
| `sensor.hh_flow_setpoint` | teplota vody podle topné křivky (virtuální) |
| `sensor.hh_duty_limit` | povolená střída kotle a doba běhu v cyklu |
| `sensor.hh_boiler_duty`, `sensor.hh_boiler_starts_today` | střída kotle za 24 h a počet startů dnes |
| `sensor.hh_open_windows` | počet místností s otevřeným oknem |
| `binary_sensor.hh_heat_demand`, `_boiler_command`, `_window_block`, `_heating_season`, `_problem` | požadavek, povel kotli, blokace okny, topná sezóna, porucha |
| `switch.hh_shadow_mode` | shadow režim |
| `climate.hh_<místnost>` | termostat místnosti s presety komfort, eco, pryč a ruční teplota |
| `sensor.hh_<místnost>_temperature`, `_demand`, `_valve_state` | teplota, požadavek, stav ventilů |
| `number.hh_<místnost>_comfort`, `_eco` | komfortní a útlumová teplota |
| `binary_sensor.hh_<místnost>_window`, `_problem` | blokace oknem, porucha místnosti |

Ruční změna teploty nebo presetu místnosti v režimu automaticky platí trvale: místnost přejde do režimu topit a rozvrh se ignoruje, dokud ji nevrátíte na automaticky. Atribut `override_active` ukazuje, kde rozvrh neběží.

## Služby

- `hydronic_heating.start_manual` s parametrem `duration` (1–720 min): spustí nebo prodlouží manuální topení.
- `hydronic_heating.stop`: ukončí manuál.
- `hydronic_heating.generate_dashboard`: vrátí dashboard pro tuto instalaci (viz demo režim).

## Příprava v Loxone

Kotel a každá hlavice musí být v Loxone Config jako stavový blok **Switch**, ne Pushbutton, a výstup smí řídit jen jeden vlastník: buď Loxone, nebo tato integrace. Doporučený je i watchdog v Loxone: když integrace přestane přepínat výstup heartbeat, Loxone vypne kotel a odpojí napájení NO hlavic.

## Vývoj

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt ruff
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Jádro řízení (`custom_components/hydronic_heating/core/`) je čistý Python bez importů Home Assistantu a testuje se s falešným časem v `tests/core/`.

Validace stejná jako v CI:

```bash
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest
```

## Vydání verze

1. Zvedni verzi v `custom_components/hydronic_heating/manifest.json` a `pyproject.toml` (SemVer).
2. Doplň sekci `## vX.Y.Z — RRRR-MM-DD` do `CHANGELOG.md`.
3. Commit `Release vX.Y.Z: …`, `git tag vX.Y.Z`, push commitu i tagu.
4. GitHub Actions zkontroluje verzi v manifestu a vytvoří release s textem z CHANGELOG. HACS pak nabídne aktualizaci.

## Známá omezení

- Kotel řízený jen kontaktem: Home Assistant ho umí jen zapnout a vypnout. Teplota vody podle topné křivky je proto jen virtuální hodnota, skutečnou teplotu si kotel drží sám. Modulované řízení (OpenTherm, eBUS) zatím není.
- Předtápění se rychlost ohřevu teprve učí. Prvních pár ohřevů počítá s výchozí hodnotou 0,5 °C za hodinu.
- Předtápění podle návratu konkrétní osoby (např. dětský pokoj) zatím není, jen podle návratu domácnosti a podle rozvrhu.
- Dashboard se negeneruje sám: po změně místností nebo po aktualizaci je potřeba znovu spustit službu `hydronic_heating.generate_dashboard` a vložit výsledek.
- Jedna instance integrace na Home Assistant.

## Autor

**[elvisek2020](https://github.com/elvisek2020)** — integrace vznikla jako náhrada regulace Loxone (Intelligent Room Controller a Climate Controller) pro teplovodní topení v rodinném domě. Licence MIT.
