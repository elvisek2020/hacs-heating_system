# Hydronic Heating Controller

Vlastní integrace pro Home Assistant, která řídí teplovodní ústřední topení: kotel spínaný beznapěťovým kontaktem, radiátory a termoelektrické hlavice NO/NC. Staví jen na obecných entitách HA, takže výměna hardwaru (dnes Loxone přes PyLoxone) znamená jen přemapovat entity v nastavení.

## Stav

| Fáze | Obsah |
|---|---|
| **F0** ✅ | kostra, config flow, nastavení systému, místnosti, ikona, CI |
| **F1** ✅ | místnosti, čidla, ventily NO/NC, kotel, arbitr požadavků, sekvence ventily → kotel → doběh, ochrana kotle proti cyklování, manuál s odpočtem, režimy, rozvrh, shadow, ukládání stavu |
| **F2** ✅ | okna a globální práh, protimrazová ochrana, venkovní teplota a mez vytápění (léto), protáčení ventilů, notifikace, repair issues, diagnostika |
| **F3** ✅ | ekviterm: topná křivka (virtuální teplota vody), omezení střídy kotle, předpověď počasí |
| F5 | modulované řízení (OpenTherm/eBUS) – až s kotlem, který ho umí |

## Instalace přes HACS

1. HACS → tři tečky vpravo nahoře → **Vlastní repozitáře**.
2. Repozitář `https://github.com/elvisek2020/hacs-heating_system`, typ **Integrace**.
3. Nainstalovat **Hydronic Heating Controller** a restartovat Home Assistant.
4. Nastavení → Zařízení a služby → **Přidat integraci** → Hydronic Heating Controller.

Vyžaduje Home Assistant 2026.3 nebo novější.

## Jak začít

1. Přidejte integraci. **Režim shadow** nechte zapnutý: integrace všechno počítá, ale nic nespíná.
2. V integraci přidejte místnosti tlačítkem **Přidat místnost** (čidla, ventily, okna, rozvrh).
3. Nechte systém běžet vedle stávající regulace. Na `climate.hh_system` ukazují atributy `would_command_boiler` a `would_command_valves`, co by integrace udělala.
4. Až rozhodnutí sedí, vypněte `switch.hh_shadow_mode`. Od té chvíle integrace spíná kotel a hlavice.

Všechno se mění jen v nastavení, bez úprav kódu a bez restartu HA. Změna místností nebo délek manuálu integraci krátce znovu načte, ostatní změny se projeví hned.

## Demo režim: ověření před přepnutím z Loxone

V **Konfigurovat → Obecné → Demo režim** jsou dvě možnosti. Obě běží v reálném čase.

- **Virtuální výstupy:** teploty a okna se berou ze skutečných čidel, ale povely jdou do virtuálního kotle `switch.hh_demo_boiler` a virtuálních hlavic `switch.hh_<místnost>_demo_valve_<n>`. Projde celá cesta povelů včetně ověření stavu, opakování a poruchy. Skutečný kotel a hlavice dál řídí Loxone a na dashboardu je vidíte vedle virtuálních.
- **Virtuální dům:** navíc simulované teploty místností s tepelným modelem (topení otápí, okno ochlazuje), simulovaná okna, výpadky čidel a venkovní teplota `number.hh_demo_outdoor_temperature`. Hodí se na vyzkoušení událostí od stolu.

Ve virtuálních výstupech i ve virtuálním domě lze přes `select.hh_demo_boiler_behavior` nasimulovat kotel, který je nedostupný nebo ignoruje povely.

**Pojistka:** v demo režimu integrace odmítne poslat povel jakékoli entitě, která jí nepatří. Ani případná chyba v konfiguraci tak nemůže sepnout skutečný kotel nebo hlavici. Heartbeat a zrcadlový časovač se v demu nespínají, notifikace mají v titulku `[Demo]`. Demo si ukládá stav zvlášť, takže se nemíchá s historií skutečného kotle.

**Dashboard:** Nástroje pro vývojáře → Akce → `hydronic_heating.generate_dashboard` → Provést akci. Odpověď je hotový dashboard pro vaši instalaci: systém, manuál, demo, každá místnost se skutečnými i virtuálními hlavicemi a grafy. Vložíte ho takto: Nastavení → Řídicí panely → Přidat řídicí panel → Nový od začátku, otevřít, ⋮ → Upravit → ⋮ → Editor kódu YAML, obsah nahradit odpovědí a uložit.

### Doporučený postup přepnutí

1. **Virtuální dům:** vyzkoušejte otevřené okno, výpadek čidla, nedostupný kotel, manuál a změnu venkovní teploty (léto). Ověřte, že reakce odpovídají očekávání.
2. **Virtuální výstupy, několik dní:** v grafech porovnávejte virtuální kotel a hlavice se skutečnými, které řídí Loxone.
3. **Loxone:** kotel a hlavice jako bloky **Switch**, odpojit IRC a Climate Controller od výstupů a zavést watchdog na heartbeat.
4. **Přepnutí:** demo režim vypnout, pak vypnout `switch.hh_shadow_mode`. Od té chvíle integrace spíná skutečné výstupy.

## Jak řídí

- **Místnost:** teplota z 1..n čidel (průměr, minimum, maximum, medián nebo první platné). Požadavek 0–100 % počítá algoritmus TPI nebo hystereze. Ventily jedou v PWM (perioda 30 min, synchronní začátek), s minimální dobou stavu kvůli pomalým hlavicím.
- **Kotel:** zapne se, když vážený požadavek místností překročí práh (s hysterezí), nebo když volá dost místností. Nejdřív se otevřou ventily, kotel startuje až po době přestavení (nebo hned, když má soustava obtok). Hlídá minimální dobu běhu, minimální pauzu a počet startů za hodinu. Po vypnutí drží ventily otevřené po dobu doběhu.
- **Priority:** porucha > protimrazová ochrana > manuál > blokace okny > léto > zvolený režim (vypnuto, pryč, automaticky).
- **Okna:** po zpoždění zavřou ventily místnosti. Při otevření oken ve více místnostech (globální práh) se zastaví kotel, kromě manuálu.
- **Mráz:** místnost pod protimrazovou teplotou topí vždy, i při otevřeném okně a v létě. Tuto ochranu nejde vypnout.
- **Léto:** tlumená venkovní teplota nad mezí vytápění po nastavenou dobu přepne systém do léta. Pod mezí mínus hysterezi se vrátí do zimy hned.
- **Ekviterm:** z tlumené venkovní teploty se podle topné křivky počítá teplota vody, kterou by soustava potřebovala (`sensor.hh_flow_setpoint`). U kotle řízeného jen kontaktem je to virtuální hodnota: kotel si vodu drží sám. Z ní a z teploty nastavené na kotli vychází povolená střída (`sensor.hh_duty_limit`). Po zapnutí omezení střídy (Konfigurovat → Ekviterm) kotel v cyklu (výchozí 20 min) běží jen tuto část času, nikdy ale kratší dobu, než je jeho minimální doba běhu. Ve výchozím stavu je omezení vypnuté. U nekondenzačního kotle ho zapínejte až po ověření minimální teploty vody v návodu kotle, protože zkracuje běhy.
- **Předpověď (volitelně):** s entitou počasí se pro mez vytápění i křivku bere průměr tlumené teploty a průměrné předpovědi na příštích 24 hodin.
- **Ochrany:** ověření každého povelu s opakováním, keep-alive, obnovení stavu ventilů po výpadku, bezpečný stav při nedostupném kotli, heartbeat pro watchdog v Loxone, upozornění na zastaralá čidla.

## Entity

| Entita | Popis |
|---|---|
| `climate.hh_system` | souhrn systému; vypnuto / automaticky / topit (= manuál) |
| `select.hh_system_mode` | auto, manual, off, away, summer |
| `button.hh_manual_30` … `_180`, `button.hh_stop` | manuální topení a jeho zastavení |
| `sensor.hh_manual_ends_at` | konec manuálu (časové razítko) |
| `sensor.hh_state` | stav automatu (start, auto, pryč, vypnuto, léto, manuál, porucha) |
| `sensor.hh_demand_total` | vážený požadavek místností |
| `sensor.hh_outdoor_temperature_damped` | tlumená venkovní teplota (atributy: aktuální, předpověď, efektivní) |
| `sensor.hh_flow_setpoint` | teplota vody podle topné křivky (virtuální) |
| `sensor.hh_duty_limit` | povolená střída kotle a doba běhu v cyklu |
| `sensor.hh_boiler_duty`, `sensor.hh_boiler_starts_today` | střída kotle za 24 h a počet startů dnes |
| `sensor.hh_open_windows` | počet místností s otevřeným oknem |
| `binary_sensor.hh_heat_demand`, `_boiler_command`, `_window_block`, `_summer`, `_problem` | požadavek, povel kotli, blokace okny, léto, porucha |
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
