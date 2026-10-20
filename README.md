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
2. V integraci přidejte místnosti tlačítkem **Přidat místnost** (čidla, ventily, okna, rozvrh). Pole **Pořadí** určuje pořadí místností na dashboardu a ve schématu (0 = podle názvu za ostatními).
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
- **Chybné hodnoty čidel** (nastavení místnosti, krok Teplotní čidla):
  - Krátký výpadek čidla nebo hodnota mimo platný rozsah: 5 min se počítá s poslední platnou hodnotou (atribut `held_sources`), pak teprve s dalšími čidly.
  - Skok o víc než 3 K (Skok hodnoty čidla, 0 = vypnuto) se použije až po potvrzení dalším blízkým vzorkem nebo po 1 min (atribut `filtered_sources`). Odfiltruje 0,0 nebo hodnotu s posunem, kterou pošlou čidla Matter/Thread po obnovení spojení.
  - Po skoku čeká detekce větrání jedno okno (5 min), aby návrat čidla z posunu nevypadal jako větrání.
- **Kotel:** zapne se, když vážený požadavek místností překročí práh (s hysterezí), nebo když volá dost místností. Nejdřív se zavřou ventily místností, které teplo nechtějí, a otevřou ty, které ho chtějí. Kotel startuje až po době přestavení, aby voda netekla tam, kde se netopí. Hlídá minimální dobu běhu, minimální pauzu a počet startů za hodinu.
- **Minimální běh a doběh:** když teplo už nikdo nechce, ale kotel ještě musí běžet minimální dobu, a pak během doběhu čerpadla, zůstávají otevřené ventily místností, kam se při běhu topilo. Ostatní jsou zavřené. Když žádná taková místnost není (třeba se v ní mezitím začalo větrat), dobíhá voda jen obtokem u kotle. Teď, logbook i důvod kotle říkají, kam teplo jde: „Kotel je vypnutý, čerpadlo dobíhá do 22:59:34 do místností Kuchyně a Obývák.“
- **Ruční topení** (tlačítka 30 až 180 min) otevře ventily všech místností bez ohledu na jejich požadavek (Konfigurovat → Manuální režim → Manuál otevírá ventily, výchozí Všechny místnosti). Platí to i pro minimální běh a doběh po ručním topení, také po předčasném Stop. Místnost s otevřeným oknem nebo větráním a vypnutá místnost zůstanou zavřené.
- **Ventily v klidu:** když kotel stojí a nikdo nechce teplo, jdou všechny hlavice do klidové polohy (výchozí bez proudu, u NO hlavic otevřeno). Hlavice tak nehřejí a neberou proud zbytečně celé hodiny. Proud dostanou jen hlavice místností bez požadavku, a jen během běhu kotle a doběhu.
- **Priority:** porucha > protimrazová ochrana > manuál > blokace okny > mimo topnou sezónu > zvolený režim (vypnuto, pryč, automaticky).
- **Okna:** po zpoždění zavřou ventily místnosti. Při otevření oken ve více místnostech (globální práh) se zastaví kotel, kromě manuálu.
- **Ruční větrání:** přepínač **Větrání** pro celý dům, každé patro a každou místnost (ta ve výchozím nastavení větrá celé své patro).
  - Místnosti netopí a ventily jsou zavřené 15 min, další zapnutí čas přidá („+15 min“ na dashboardu), vypnutí větrání ukončí.
  - Na Přehledu je větrání patra odznak v nadpisu patra (klepnutí zapne nebo vypne, za běhu je vidět konec a vedle odznak +15), větrání celého domu je v bloku Topení.
  - Patra se berou z oblastí Home Assistantu: přiřaďte zařízení místnosti oblast s patrem.
  - Pro automatizace (tlačítko na zdi, zkratka v telefonu) jsou služby `hydronic_heating.ventilate` a `hydronic_heating.stop_ventilation`.
  - Když místnost pozná větrání podle poklesu teploty, přestane topit celé její patro (vypínatelné v Konfigurovat → Okna).
- **Větrání bez kontaktů:** když teplota místnosti rychle klesne (výchozí 1 K za 5 min), místnost se chová jako s otevřeným oknem: netopí a ventil je zavřený.
  - Topí zase nejdřív po 20 min, až teplota začne stoupat, nejpozději po 45 min.
  - Do blokace celého kotle se větrání nepočítá.
  - Nastavení je v místnosti, krok Okna. Začátek i konec se zapíšou do deníku.
- **Mráz:** místnost pod protimrazovou teplotou topí vždy, i při otevřeném okně a mimo topnou sezónu. Tuto ochranu nejde vypnout. Spustí se až po dvou vzorcích pod hranicí nebo po 1 min, jeden chybný vzorek ji nezapne.
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
- Vlastní rozvrh místnosti je na dashboardu dole v kartě jako upravitelná dlaždice.
- Pod blokem Provoz kotle je přehled **Kdo je doma**: každá osoba se stavem a časem poslední změny, takže je vidět, kdo právě odešel.
  - Jen osoby, žádné skupiny ani počty. Skupina HA se rozbalí na členy (atribut `entity_id`). Skupina nebo počet z modulu přítomnosti (atributy `people`, `count`) se rozbalí na osoby téže integrace.
  - Jméno je název zařízení osoby („ElvisEK“, ne „ElvisEK Doma“), jinak název entity.
- Když místnost změní cíl kvůli přítomnosti nebo rozvrhu, zapíše se to do logbooku, například „Kuchyně: útlum 19 °C, nikdo doma (Rodiče doma).“

## Dashboard

Služba `hydronic_heating.generate_dashboard` vrátí dashboard pro tuto instalaci (vložit přes ⋮ → Upravit → ⋮ → Editor kódu YAML).

- **Nahoře jedna řada:**
  - Topení: systém, režim, topná sezóna, rozvrh domu, manuál.
  - Kotel: proč, další změna, celkový požadavek proti pravidlům startu („0,6 % z 30 % nebo 0 z 2 místností“, při běžícím kotli s prahem vypnutí), měřená teplota vody, venku a 4h průměr s hranicí topné sezóny v názvu (jako čára v Grafech).
  - Provoz kotle podle priority: povel kotli, skutečný stav kotle (se zpětnou vazbou), požadavek na teplo, venku (průměr 4 h), porucha, topná sezóna, starty dnes, střída 24 h, omezení střídy. Pod tím Kdo je doma.
- **Odznak Kotel** v horní liště ukazuje se zpětnou vazbou skutečný stav kotle, bez ní povel.
- **Pod řadou** upozornění na shadow režim přes celou šířku, v demu blok Demo.
- **Místnosti – individuální nastavení:**
  - nahoře ovládání: tlačítka Automaticky a Vypnuto, cílová teplota, předvolba. Ruční režim se jmenuje **Ručně** a má ikonu ruky. Je vidět v textu stavu, zpět na automatiku jedním dotykem.
  - pak požadavek (příčina, „75 % z 50 %“ = od 50 % místnost volá) a ventil (následek). S čidlem trubky má ventil vedle sebe dlaždici Trubka a ukazuje výsledek kontroly.
  - pod nimi **Komfort** a **ECO** s tlačítky −/+, tedy trvalé teploty místnosti pro automatiku. Teplota Pryč se nastavuje v nastavení místnosti. Pozor: −/+ na termostatu nastaví jen ruční cíl a místnost přepne na ručně.
  - dole vlastní rozvrh.
- **Vysvětlivky** otevře odznak vpravo v horní liště. Jsou na samostatném skrytém pohledu: každá dlaždice a každý odznak se stejnou ikonou a jednou až dvěma větami, co znamená.
- **Jen nastavené funkce.** Okna, blokace okny, omezení střídy, žádaná teplota z křivky, teplota vody ani rozvrh domu se negenerují, když je nepoužíváte. Po změně nastavení dashboard přegenerujte.
- **Barvy podle významu:** kotel oranžově, požadavky a sezóna jantarově, voda a porucha červeně, venek modře, ventily a okna tyrkysově, osoby zeleně. Dvoustavové dlaždice svítí jen v aktivním stavu, termostaty mají barvy HA.

## Schéma topení

Dashboard má pohled **Schéma**: animované schéma s kotlem, přívodem a zpátečkou a radiátory po patrech.

- Voda proudí jen tam, kam opravdu teče, v doběhu pomaleji. Kotel při běhu svítí a hoří, hlavice v pohybu bliká a radiátor je teplý, jen když jím teče voda.
- Pod schématem je pruh fází **Klid → Ventily → Kotel topí → Doběh** s odpočtem („kotel zapne za 1:12“, „doběh ještě 2:10“) a se štítkem, když kotel něco drží (minimální pauza, mimo sezónu, porucha…).
- **Teď** říká, proč je to tak (kdo chce teplo, které ventily se zavírají). **Pak** vypisuje příští události s časy: start a vypnutí kotle, konec doběhu a manuálu, předtápění, změny rozvrhu, návrat a konec větrání.
- Klepnutím na místnost se otevře její termostat, klepnutím na kotel důvod jeho stavu.
- **Patra** se berou z oblastí Home Assistantu. Přiřaďte zařízení místnosti oblast s patrem, nebo pojmenujte oblast stejně jako místnost. Bez pater jsou všechny místnosti v jedné řadě.
- Kartu `custom:hydronic-heating-flow-card` přináší integrace, nic dalšího se neinstaluje. Integrace ji sama zapíše mezi zdroje dashboardů (Nastavení → Řídicí panely → ⋮ → Zdroje, `/hydronic_heating/hydronic-heating-flow-card.js?v=<verze>`), takže se načte dřív než dashboard. Po aktualizaci verzi v adrese přepíše, po odebrání integrace zdroj smaže. Po aktualizaci integrace stačí obnovit stránku. Se zdroji v YAML se karta načítá na každé stránce jako dřív.

### Karta na jiném dashboardu

Schéma jde dát i na hlavní dashboard, třeba vedle kamer. Entity a patra do karty vkládá služba `generate_dashboard`, proto kartu zkopírujte z pohledu Schéma:

1. Na pohledu Schéma: Upravit dashboard → upravit kartu schématu → Zobrazit editor kódu, zkopírovat YAML.
2. Na jiném dashboardu: Přidat kartu → Ruční, vložit a doplnit volby, například `layout: compact` a `interactive: false`, aby se na mobilu při posouvání omylem nespustilo větrání patra.

```yaml
type: custom:hydronic-heating-flow-card
layout: compact
interactive: false
tap_action:
  action: navigate
  navigation_path: /dashboard-topeni/schema
boiler: binary_sensor.hh_boiler_command
reason: sensor.hh_boiler_reason
outdoor: sensor.hh_outdoor_temperature
floors:
  - name: Přízemí
    ventilation: switch.hh_ventilation_prizemi
    rooms:
      - name: Obývák
        climate: climate.hh_obyvak
        demand: sensor.hh_obyvak_demand
        valve: sensor.hh_obyvak_valve_state
```

| Volba | Výchozí | Co dělá |
|---|---|---|
| `layout` | `full` | `compact` = nižší schéma bez textů Teď a Pak |
| `show_text` | `true`, u `compact` `false` | oba sloupce Teď a Pak |
| `show_now`, `show_upcoming` | podle `show_text` | jen sloupec Teď, jen sloupec Pak |
| `upcoming_max` | všechny | nejvýš tolik řádků v Pak |
| `show_phases` | `true` | pruh fází (Klid, Ventily, Kotel topí, Doběh) se štítkem a odpočtem |
| `show_outdoor` | `true` | venkovní teplota vpravo nahoře |
| `interactive` | `true` | `false` = prvky nejdou klepnout: místnost neotevře termostat, kotel důvod a patro nepřepne větrání |
| `tap_action` | nic | standardní akce Home Assistantu po klepnutí na kartu, například `navigate` na pohled Schéma. S `interactive: true` mají přednost prvky. |
| `title` | bez nadpisu | nadpis karty |

Volby jdou naklikat i ve vizuálním editoru karty, entity a patra editor nemění. Zkopírovaná karta se sama neaktualizuje: po změně místností nebo pater ji zkopírujte znovu z přegenerovaného pohledu Schéma.

## Teplota vody a kontrola topení

Volitelné čidlo **Teplota vody** (Konfigurovat → Zdroj tepla), například na stoupačce od kotle:

- Dashboard ukazuje měřenou teplotu vody místo žádané teploty z topné křivky. Ta se u kotle spínaného kontaktem neuplatní, proto je vidět jen se zapnutým omezením střídy podle křivky.
- **Kontrola topení** (Konfigurovat → Bezpečnost): když kotel běží 15 min a teplota vody nestoupne aspoň o 5 °C nad nejnižší hodnotu běhu, ohlásí se porucha „Kotel běží, ale netopí“ (oznámení, Opravy, `binary_sensor.hh_problem`). Příčinou může být porucha kotle, nízký tlak vody, zavřený okruh nebo vzduch v systému.
  - Doba a nárůst se dají nastavit, doba 0 kontrolu vypne.
  - Se zpětnou vazbou hořáku se počítá jen doba, kdy hořák opravdu běží. Ve shadow režimu a v demu se nekontroluje.
  - Kotel se kvůli tomu nevypíná. Porucha zmizí sama, až teplota vody při běhu kotle zase stoupne.
  - Stav kontroly ukazuje atribut `flow_check` u `binary_sensor.hh_boiler_command`.

## Kontrola ventilů podle trubky

Termoelektrické hlavice neříkají, jestli ventil opravdu otevřely. Čidlo teploty na trubce u ventilu (např. DS18B20 na 1-Wire sběrnici Loxone) to pozná. Nastavuje se u každého ventilu (Překonfigurovat místnost → ventil), prahy v Konfigurovat → Ventily.

- Kontroluje se jen, když kotel topí a voda je teplá (měřená voda aspoň 40 °C, bez čidla vody po 5 min topení), a jen u ventilu, který je celý otevřený nebo celý zavřený.
- **Otevřený ventil** musí trubku do 10 min ohřát aspoň o 5 K (nebo nad 40 °C). Jinak porucha „Ventil asi neotvírá“.
- **Zavřený ventil** nesmí trubku ohřát o víc než 3 K. Jinak „Ventil asi nezavírá“.
- Je to jen hlášení (oznámení, Opravy, deník). Řízení se nemění a hlášení zmizí samo, až kontrola projde.
- Výsledek je v atributech `valve_check` a `valve_temp` termostatu místnosti a na dashboardu u Ventilu. Ve shadow režimu a v demu se nekontroluje.

## Proč kotel topí nebo stojí

Ochrana kotle někdy drží kotel v chodu nebo ve stání i proti tomu, co zrovna chcete. Například po **Stop** kotel doběhne svou minimální dobu běhu. Proto integrace vždy ukazuje, proč je kotel v aktuálním stavu a kdy se to změní:

- `sensor.hh_boiler_reason` říká důvod, třeba „Minimální doba běhu“, „Minimální pauza“, „Doběh“ nebo „Topí na požadavek“. Atribut `detail` obsahuje celou větu, například „Teplo už nikdo nechce, ale kotel musí běžet minimální dobu 10 min. Vypne se v 0:55:12, teplo jde do všech místností.“ V atributu `rule` je nastavení, které za tím stojí.
- `sensor.hh_boiler_hold_ends_at` ukazuje, kdy časové pravidlo skončí. Dashboard z něj dělá odpočet „za 4 minuty“.
- **Logbook** (Aktivita) zapisuje každé zapnutí a vypnutí kotle s příčinou a každé odložení povelu s časem. Zapíše i výstup, který někdo přepnul ručně a integrace ho vrátila. Stejné věty jsou v logu Home Assistantu. Ve shadow režimu mají předponu `[Shadow]`, v demu `[Demo]`.
- U ventilů ukazují atributy `reason` a `until` na `sensor.hh_<místnost>_valve_state`, proč je ventil otevřený nebo zavřený (PWM, okno, minimální běh a doběh kotle, protáčení…) a kdy se to změní.

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
| `sensor.hh_outdoor_temperature` | aktuální venkovní teplota (první platné čidlo, jinak počasí) |
| `sensor.hh_outdoor_temperature_damped` | tlumená venkovní teplota pro topnou křivku (atributy: aktuální, předpověď, efektivní) |
| `sensor.hh_outdoor_mean_4h` | průměr venkovní teploty za 4 h, podle něj se řídí topná sezóna |
| `sensor.hh_heating_limit` | hranice topné sezóny z nastavení (v grafu jako čára) |
| `sensor.hh_flow_setpoint` | teplota vody podle topné křivky (virtuální) |
| `sensor.hh_duty_limit` | povolená střída kotle a doba běhu v cyklu |
| `sensor.hh_boiler_duty`, `sensor.hh_boiler_starts_today` | střída kotle za 24 h a počet startů dnes |
| `sensor.hh_open_windows` | počet místností s otevřeným oknem |
| `binary_sensor.hh_heat_demand`, `_boiler_command`, `_window_block`, `_heating_season`, `_problem` | požadavek, povel kotli, blokace okny, topná sezóna, porucha |
| `switch.hh_shadow_mode` | shadow režim |
| `switch.hh_ventilation`, `switch.hh_ventilation_<patro>` | ruční větrání celého domu a patra (atributy `until` a `ends` = konec) |
| `climate.hh_<místnost>` | termostat místnosti s presety komfort, eco, pryč a ruční teplota |
| `sensor.hh_<místnost>_temperature`, `_demand`, `_valve_state` | teplota, požadavek, stav ventilů |
| `number.hh_<místnost>_comfort`, `_eco`, `_away` | komfortní, útlumová a teplota Pryč (útlum nejde nad komfort, útlum a Pryč nejdou na protimrazovou teplotu nebo pod ni) |
| `switch.hh_<místnost>_ventilation` | ruční větrání místnosti, ve výchozím nastavení větrá celé patro (atributy `until`, `ends`, `source`) |
| `binary_sensor.hh_<místnost>_window`, `_problem` | otevřené okno nebo větrání (atribut `state` = `open_manual` ručně, `open_detected` podle poklesu teploty), porucha místnosti |

Ruční změna teploty nebo presetu místnosti v režimu automaticky platí trvale: místnost přejde do režimu topit a rozvrh se ignoruje, dokud ji nevrátíte na automaticky. Atribut `override_active` ukazuje, kde rozvrh neběží.

## Služby

- `hydronic_heating.start_manual` s parametrem `duration` (1–720 min): spustí nebo prodlouží manuální topení.
- `hydronic_heating.stop`: ukončí manuál.
- `hydronic_heating.generate_dashboard`: vrátí dashboard pro tuto instalaci (viz demo režim).
- `hydronic_heating.ventilate` s volitelnými parametry `entity_id` (termostaty místností nebo přepínače Větrání, bez výběru celý dům) a `minutes` (1–240 min): spustí větrání, když už běží, čas přidá.
- `hydronic_heating.stop_ventilation` s volitelným `entity_id`: ukončí větrání.

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
- Dashboard se negeneruje sám: po změně místností nebo po aktualizaci je potřeba znovu spustit službu `hydronic_heating.generate_dashboard` a vložit výsledek.
- Jedna instance integrace na Home Assistant.

## Autor

**[elvisek2020](https://github.com/elvisek2020)** — integrace vznikla jako náhrada regulace Loxone (Intelligent Room Controller a Climate Controller) pro teplovodní topení v rodinném domě. Celý příběh je v článku [Jak jsem přestěhoval topení z Loxone do Home Assistantu](https://www.elvisek.cz/2026/10/topeni-z-loxone-do-home-assistantu/). Licence MIT.
