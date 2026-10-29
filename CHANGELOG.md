# Changelog

Poznámky k vydání. Sekce `## vX.Y.Z` se při releasu automaticky použije jako
text vydání na GitHubu — a ten Home Assistant / HACS ukazuje v okně aktualizace.

Nejnovější verze je nahoře. Starší historie je v [GitHub releases](https://github.com/elvisek2020/hacs-heating_system/releases).

## v0.20.1 — 2026-10-29

### 🎨 Vzhled

- **Ventil ve schématu při přestavování.** Dokud se ventil otevírá nebo zavírá, je kroužek žlutý a páčka se točí pořád dokola ve směru pohybu, takže je hned vidět, že se něco děje. Ve v0.20.0 se páčka natáčela tak pomalu jako skutečná hlavice (90° za asi 2 min) a pohyb skoro nebyl vidět. Když hlavice dojede, páčka se dotočí do koncové polohy.

Po aktualizaci restartuj Home Assistant a obnov stránku prohlížeče.

## v0.20.0 — 2026-10-28

### ✨ Novinky

- **Karta schématu: jedna barva = jeden význam.** Malá i velká karta teď ukazují totéž.
  - **Radiátor** je sytě oranžový, když jím teče teplá voda. Pak ještě hřeje a do 30 min vybledne do šedé, i přes restart.
  - **Ventil** je kulový kohout: páčka podél trubky = otevřeno, napříč = zavřeno. Při přestavování se otáčí podle skutečné doby přestavení hlavice.
  - **Místnost, která volá kotel**, má rámeček, plamínek a pruh požadavku. Pod názvem je „teplota → cíl“, „vypnuto“ nebo „čidlo!“.
  - **Poruchy** místnosti, ventilu, čidla i kotle jsou vidět přímo ve schématu. V shadow režimu je přes kartu pruh SHADOW, v demu DEMO.
  - **Větrání:** okénko nad radiátorem a tyrkysový pás přes patro.
  - **Kompaktní karta** má řádek stavu s barevnou tečkou podle fáze a odpočtem (volba `show_status`). Pruh fází je u ní ve výchozím stavu vypnutý, `show_phases: true` ho vrátí.
  - Vysvětlivky popisují i značky schématu.
- Nové atributy `sensor.hh_<místnost>_valve_state`: `last_flow` (kdy naposledy tekla voda), `moving_since` a `moving_until` (přestavování ventilu).

### 🐛 Opravy

- **Kotel netopí do samých zavřených ventilů.** Místnost s požadavkem aspoň na prahu kotle (výchozí 30 %, při běžícím kotli 20 %) má ventil otevřený celou dobu, dokud kotel topí. Dřív se ventily otevíraly jen na část 30min periody a na jejím konci byly zavřené všechny, takže kotel občas hořel jen do obtoku. Místnosti pod prahem se otevírají na část periody jako dřív. Nový důvod ventilu: „Požadavek nad prahem kotle“.

Po aktualizaci restartuj Home Assistant a obnov stránku prohlížeče. Kartu schématu zkopírovanou na jiný dashboard přegeneruj (služba `generate_dashboard`, pohled Schéma), nové značky potřebují `problem` u místností a `shadow`.

## v0.19.2 — 2026-10-20

### 🐛 Opravy

- **Karta schématu po obnovení stránky.** Občas se místo karty ukázala chyba „Custom element doesn't exist: hydronic-heating-flow-card“, protože se karta načetla až po vykreslení dashboardu. Integrace teď kartu sama zapíše mezi zdroje dashboardů (Nastavení → Řídicí panely → ⋮ → Zdroje), takže se načte dřív. Při aktualizaci přepíše verzi v adrese, zdvojený záznam smaže a po odebrání integrace zdroj odstraní. Se zdroji v YAML se karta načítá jako dřív.
- Karta se nezaregistruje dvakrát a v nabídce karet je jen jednou, ani když se soubor načte dvakrát.

Po aktualizaci restartuj Home Assistant a obnov stránku prohlížeče.

## v0.19.1 — 2026-10-17

### 🐛 Opravy

- **Logbook při změně nastavení.** Uložení nastavení místnosti nebo změna Komfort/ECO už do logbooku znovu nezapíše „komfort podle rozvrhu“ u každé místnosti, která jede podle rozvrhu nebo přítomnosti. Místnost si přes změnu nastavení drží důvod svého cíle.
- Skok čidla, který čeká na potvrzení, zůstane zadržený i přes změnu nastavení.

## v0.19.0 — 2026-10-17

### ✨ Novinky

- **Filtr skoků čidla.** Čidla Matter/Thread po obnovení spojení pošlou 0,0 nebo hodnotu s posunem kolem +3 K, která se pak několik minut vrací. Hodnota, která se od poslední platné liší o víc než 3 K, se teď použije až po potvrzení dalším blízkým vzorkem nebo po 1 min. Do té doby platí poslední platná hodnota (atribut termostatu `filtered_sources`). Nastavení místnosti, krok Teplotní čidla: **Skok hodnoty čidla: potvrdit nad** (0 = vypnuto).
- Po skoku čidla detekce větrání 5 min počká, aby návrat čidla z posunu nevypadal jako větrání. Skutečné větrání se pozná dál.

### 🐛 Opravy

- **Protimrazová ochrana z jednoho chybného vzorku.** Spustí se až po dvou vzorcích pod hranicí nebo po 1 min. Hodnota 0,0 z čidla po obnovení spojení už nespustí start kotle.
- **Hodnota mimo platný rozsah** (Nejnižší / Nejvyšší platná hodnota) se drží jako krátký výpadek čidla: 5 min platí poslední platná hodnota. Dřív místnost hned přešla na záložní čidlo s jiným posunem.

Po aktualizaci restartuj Home Assistant. Filtr skoků je zapnutý ve všech místnostech (3 K).

## v0.18.0 — 2026-10-16

### 🐛 Opravy

- **Ruční topení topí do všech místností až do konce doběhu.** Po ručním topení (i po předčasném Stop) zůstávají ventily všech místností otevřené i během minimálního běhu kotle a doběhu čerpadla. Dřív se po Stopu všechny zavřely a voda dobíhala jen obtokem u kotle. Místnost s otevřeným oknem nebo větráním a vypnutá místnost zůstávají zavřené.
- **Minimální běh a doběh po normálním běhu** drží otevřené ventily místností, kam se topilo. Ostatní zůstávají zavřené.
- **Texty doběhu podle skutečných ventilů.** Teď, logbook i důvod kotle říkají, kam teplo jde: „Kotel je vypnutý, čerpadlo dobíhá do 22:59:34 do místností Kuchyně a Obývák.“, „… do všech místností.“ nebo „… jen obtokem u kotle.“ Dřív psaly „ventily zůstávají otevřené“, i když byly zavřené. Ruční topení: „Ruční topení: topí se do všech místností do 23:21:00.“

### ✨ Novinky

- **Karta schématu bez klikání.** Volba `interactive: false` vypne klepnutí na místnosti, kotel a patra, takže se třeba na hlavním dashboardu omylem nespustí větrání patra. Volba `tap_action` přidá celé kartě standardní akci Home Assistantu, například `navigate` na pohled Schéma. Obojí jde nastavit i ve vizuálním editoru karty.

Po aktualizaci restartuj Home Assistant a obnov stránku prohlížeče.

## v0.17.0 — 2026-10-16

### ✨ Novinky

- **Karta schématu na jiném dashboardu.** Karta `custom:hydronic-heating-flow-card` má volby, takže jde dát i na hlavní dashboard:
  - `layout: compact`: nižší schéma bez textů Teď a Pak,
  - `show_text: false` schová texty Teď a Pak, `show_now` / `show_upcoming` jen jeden z nich, `upcoming_max` omezí počet řádků v Pak,
  - `show_phases: false` schová pruh fází s odpočtem, `show_outdoor: false` venkovní teplotu.
- Volby jdou naklikat ve vizuálním editoru karty. Entity a patra zůstávají, jak je vygeneroval dashboard. Postup a příklad jsou v README v sekci „Karta na jiném dashboardu“.
- Bez voleb vypadá karta stejně jako dřív, pohled Schéma se nemění.
- README popisuje služby a přepínače ručního větrání a odkazuje na článek o projektu na www.elvisek.cz.

Po aktualizaci obnov stránku prohlížeče, ať se načte nová verze karty.

## v0.16.2 — 2026-10-15

### 🎨 Vzhled

- **Větrání patra v nadpisu patra.** Místo řádku s dlaždicemi je větrání patra odznak vpravo v nadpisu patra: vypnuto ukazuje stav, klepnutí zapne nebo vypne, podržení přidá čas. Za běhu odznak ukazuje konec („do 7:15“) a vedle je odznak **+15**.
- Karta místnosti už nemá dlaždici Větrání. Přepínač místnosti zůstává pro služby a automatizace, větrání místnosti ukazuje odznak okna v jejím nadpisu.
- Vysvětlivky popisují větrání domu a patra.

Po aktualizaci dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.16.1 — 2026-10-15

### 🐛 Opravy

- **Kotel už nezapne, když požadavek zmizí během zavírání ventilů.** Nižší práh vypnutí (hystereze) platí až od skutečného zapnutí kotle. Během čekání na ventily se ověřuje plný práh, a když neplatí, start se zruší. V logbooku je „Start zrušen: požadavek během zavírání ventilů zmizel.“ Zrušený start se nepočítá do startů za hodinu ani do minimální pauzy.
- **Krátký výpadek čidla nepřepne místnost na záložní čidlo.** Nedostupné čidlo se ještě 5 minut počítá se svou poslední hodnotou (nastavení místnosti, krok Čidla, 0 = vypnuto). Záložní čidla s jiným posunem tak skokově nemění požadavek. Atribut `held_sources` ukazuje, které čidlo se drží.

## v0.16.0 — 2026-10-15

### ✨ Novinky

- **Ruční větrání.** Přepínač **Větrání** pro celý dům, každé patro a každou místnost. Místnosti netopí a ventily jsou zavřené (výchozí 15 min), další zapnutí čas přidá, vypnutí větrání ukončí.
  - Přepínač místnosti ve výchozím nastavení větrá celé její patro (průvan jde přes víc místností). Jde přepnout na „jen místnost“.
  - **Patra** se berou z oblastí Home Assistantu (oblast zařízení místnosti → patro).
  - Když místnost pozná větrání podle poklesu teploty, přestane topit celé její patro (vypínatelné).
  - Po ručním větrání se 10 minut nevyhodnocuje automatická detekce, aby ochlazená místnost nespustila falešné větrání.
  - Služby `hydronic_heating.ventilate` a `hydronic_heating.stop_ventilation` pro automatizace.
  - Začátek, prodloužení a konec se zapíšou do logbooku, ve schématu jde na patro klepnout.

### 🎨 Vzhled

- Místnosti jsou na Přehledu seskupené po patrech, nad každým patrem je „Větrám …“ s „+15 min“. V bloku Topení je větrání celého domu, v kartě místnosti dlaždice Větrání.

Po aktualizaci restartuj Home Assistant, přiřaď zařízením místností oblasti s patry a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.15.0 — 2026-10-14

### ✨ Novinky

- **Pořadí místností.** V nastavení místnosti (Překonfigurovat → Základní) je pole **Pořadí**. Místnosti s pořadím jsou na dashboardu a ve schématu první, ostatní (0) za nimi podle názvu.
- **Časy ve větách po lidsku.** Důvod kotle, texty Teď a Pak, vysvětlení cíle místnosti i logbook píšou „v 5:30“, „zítra v 5:30“, „ve čtvrtek do 5:30“ nebo „24. 10. v 5:30“, hodiny bez úvodní nuly.

### 🎨 Vzhled

- **Celkový požadavek** v kratší podobě: „0,6 % z 30 % nebo 0 z 2 místností“. Při běžícím kotli s prahem vypnutí: „25 % z 20 % (vypnutí) nebo 2 z 2 místností“.
- **Požadavek místnosti:** „75 % z 50 %“.
- V bloku Kotel je zpět dlaždice **Venku – průměr 4 h** s hranicí v názvu. Hranice jako čára zůstává v Grafech.

Po aktualizaci nastav pořadí místností a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.14.0 — 2026-10-14

### ✨ Novinky

- **Prahy na dashboardu.** Celkový požadavek ukazuje i pravidlo startu kotle, např. „22,4 % · start od 30 % nebo od 2 volajících místností · volá 1“, a při běžícím kotli kdy vypne (s hysterezí).
- **Požadavek místnosti** ukazuje, jestli se místnost počítá jako volající: „75 % · volá (od 50 %)“.
- **Hranice topné sezóny v grafu.** Nová entita `sensor.hh_heating_limit`. V bloku Kotel je graf 4h průměru venkovní teploty s hranicí jako vodorovnou čarou, hranice je i v Grafech.
- **Kdo je doma:** když má osoba časovou entitu `…_since` (čas skutečné změny z modulu přítomnosti), je vedle ní dlaždice **Změna**, která platí i po restartu HA. Jinak zůstává čas poslední změny stavu.

### 🎨 Vzhled

- **Vysvětlivky:** názvy se nezalamují. Přibyla činnost termostatu (Topí, Předehřev, Nečinné) a Předtápění. Pravidla startu kotle a práh volající místnosti jsou s hodnotami z nastavení. Řádek Shadow je jen v shadow režimu.

Po aktualizaci restartuj Home Assistant a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.13.0 — 2026-10-14

### ✨ Novinky

- **Animované schéma topení.** Nový pohled **Schéma** v dashboardu: kotel, přívod a zpátečka a radiátory po patrech.
  - Voda proudí jen tam, kam opravdu teče, v doběhu pomaleji. Kotel při běhu svítí a hoří, hlavice v pohybu bliká, radiátor je teplý, jen když jím teče voda.
  - Pruh fází **Klid → Ventily → Kotel topí → Doběh** s odpočtem („kotel zapne za 1:12“) a štítkem, když kotel něco drží.
  - **Teď** vysvětluje, proč je to tak, **Pak** vypisuje příští události s časy (start a vypnutí kotle, konec doběhu, předtápění, změny rozvrhu).
  - Klepnutím na místnost se otevře termostat, klepnutím na kotel důvod jeho stavu. Na mobilu se radiátory zalomí do více řad.
  - Kartu přináší integrace, přes HACS se nic dalšího neinstaluje.
- **Patra** místností se berou z oblastí Home Assistantu: oblast zařízení místnosti, nebo oblast se stejným názvem jako místnost.
- `sensor.hh_boiler_reason` má nové atributy `now` a `upcoming` (co se děje teď a co se stane dál). Do historie se neukládají.

Po aktualizaci restartuj Home Assistant, obnov stránku v prohlížeči a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

## v0.12.0 — 2026-10-14

### ✨ Novinky

- **Větrání bez okenních kontaktů.** Když teplota místnosti rychle klesne (výchozí 1 K za 5 min), místnost se chová jako s otevřeným oknem: netopí a ventil je zavřený.
  - Topí zase nejdřív po 20 min, až teplota začne stoupat, nejpozději po 45 min.
  - Do blokace celého kotle se větrání nepočítá. Začátek i konec se zapíšou do logbooku.
  - Zapnuté je u všech místností. Citlivost a doby jdou nastavit v místnosti, krok Okna.
- **Kontrola ventilů podle teploty trubky.** U každého ventilu jde nastavit čidlo na trubce (např. DS18B20).
  - Když kotel topí a voda je teplá, otevřený ventil musí trubku ohřát a zavřený ne. Jinak přijde hlášení „Ventil asi neotvírá“ nebo „Ventil asi nezavírá“ (oznámení, Opravy, logbook).
  - Řízení se nemění, hlášení zmizí samo, až kontrola projde. Prahy jsou v Konfigurovat → Ventily.
  - Na dashboardu ukazuje Ventil výsledek kontroly a vedle něj je teplota trubky. V Grafech jsou trubky proti poloze ventilů.

### 🎨 Vzhled

- **Ruční režim místnosti se jmenuje „Ručně“** a má ikonu ruky místo plamene. V kartě místnosti jsou tlačítka jen Automaticky a Vypnuto, protože plamen u tlačítka kreslí Home Assistant napevno. Ruční režim je vidět v textu stavu.
- Systémový termostat ukazuje ruční topení jako „Manuál“.
- Dlaždice **Pryč** z karty místnosti zmizela. Teplota Pryč se nastavuje v nastavení místnosti.

Po aktualizaci restartuj Home Assistant a dashboard znovu vygeneruj službou `hydronic_heating.generate_dashboard`.

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
