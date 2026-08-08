# Gebruikershandleiding (niet-technisch)

Deze tool maakt elke week automatisch een aantal campusrondleidingen en verdeelt
alle studenten over die rondleidingen. Je hoeft niets van wiskunde of
programmeren te weten. Deze handleiding legt uit wat je invult en wat elke knop
doet.

Namen tussen aanhalingstekens, zoals "Number of tours", verwijzen naar een
specifieke knop of instelling in het scherm.

---

## In het kort: de 3 stappen

1. Upload het Excel-bestand met de studenten en hun keuzes.
2. Zet de schuifknoppen naar wat jij deze week belangrijk vindt.
3. Klik op "Optimize". Je krijgt de rondleidingen, de indeling van studenten, en
   een Excel om te downloaden.

Elke rondleiding begint en eindigt bij de Aula.

---

## Het Excel-bestand

Eén rij per student, met deze kolommen:

| Student      | Choice1 | Choice2 | Choice3 |
|--------------|---------|---------|---------|
| Jan Jansen   | Werktuigbouwkunde | Electrical Engineering | Bouwkunde |

- "Choice1" is de eerste keuze (belangrijkst), "Choice3" de laatste.
- Studenten vullen bacheloropleidingen in (bijvoorbeeld "Werktuigbouwkunde").
  De tool vertaalt die zelf naar de bijbehorende faculteit; jij hoeft niets om te
  zetten.
- Kiest een student drie opleidingen die bij dezelfde faculteit horen, dan telt
  die faculteit één keer mee (op de hoogste plek waarop de student hem noemde).
- Typefouten of onbekende opleidingen worden overgeslagen; de tool meldt om welke
  het gaat, zodat je ze kunt nakijken.

Er zit een voorbeeldbestand bij ("sample_students.xlsx") waarmee je alles kunt
uitproberen zonder eigen data.

---

## De schuifknoppen

### Bovenaan: hoe de rondleidingen eruitzien

| Knop | Wat het doet |
|------|--------------|
| "Number of tours" | Hoeveel rondleidingen er deze week zijn (bijvoorbeeld 3). Meer rondleidingen betekent kleinere groepen. |
| "Max tour duration" | De maximale lengte van een rondleiding in minuten (standaard 150). Rondleidingen die langer zouden duren, worden nooit gekozen. |
| "Faculties per tour (min–max)" | Hoeveel faculteiten er minimaal en maximaal in één rondleiding mogen (standaard 2–3). |
| "Time spent per faculty" | Hoelang je gemiddeld binnen bent bij een faculteit (standaard 20 min). |
| "Time spent per extra building" | Hetzelfde, maar voor de extra gebouwen ("X", "DreamHall", "Library"). |
| "Exactly one extra building per tour" | Aangevinkt (standaard): elke rondleiding krijgt precies één extra gebouw. Uitgevinkt: de tool kiest zelf hoeveel (0, 1, 2 of 3). |
| "Max tours a faculty may appear in" | In hoeveel rondleidingen dezelfde faculteit maximaal mag zitten (standaard 2, dus niet in alle drie). |
| "Max tours an extra building may appear in" | In hoeveel rondleidingen hetzelfde extra gebouw maximaal mag zitten (standaard 1, dus elke rondleiding een ander extra gebouw). |

### Daaronder: wat vind je deze week belangrijk?

Deze vijf knoppen bepalen de afweging. Ze zijn onderling vergelijkbaar: staat één
knop twee keer zo hoog als een andere, dan telt dat onderdeel twee keer zo zwaar.
Je hoeft ze niet "goed" te zetten — de standaardwaarden werken prima. Draai eraan
als je het resultaat wilt bijsturen.

| Knop | Hoger zetten betekent... |
|------|--------------------------|
| "Student preferences" | Studenten krijgen vaker de faculteiten die ze zelf kozen. Dit is meestal het belangrijkst. |
| "Faculty combinations" | Faculteiten die logisch bij elkaar horen komen vaker samen in één rondleiding. |
| "Undervisited faculties" | Faculteiten die je (rechts, zie hieronder) een bonus geeft worden vaker meegenomen. |
| "Shorter tours" | De tool kiest kortere rondleidingen, ook al zien studenten dan iets minder. |
| "Equal group sizes" | De groepen worden gelijker in aantal studenten. |

> Vuistregel. Wil je dat zoveel mogelijk studenten hun keuze krijgen? Zet
> "Student preferences" hoog. Klagen mensen dat groepen te ongelijk zijn? Zet
> "Equal group sizes" hoger. Duren rondleidingen te lang? Zet "Shorter tours"
> hoger of verlaag "Max tour duration".

### Wat betekent een gewicht precies?

Zie de vijf knoppen als een verdeling van je aandacht. Ze staan allemaal op
dezelfde schaal (elk onderdeel wordt intern omgerekend naar een getal tussen 0
en 1), dus je vergelijkt ze direct met elkaar. Alleen de verhoudingen tellen: de
combinatie 1,0 / 0,5 geeft exact hetzelfde resultaat als 2,0 / 1,0 — in beide
gevallen weegt het eerste onderdeel twee keer zo zwaar als het tweede.

Praktisch werkt een gewicht als een wisselkoers. Staat "Student preferences" op 1
en "Shorter tours" op 0,3, dan is de tool bereid een rondleiding langer te maken
zolang dat genoeg extra tevredenheid oplevert; wordt de winst in tevredenheid
kleiner dan wat de extra looptijd "kost", dan houdt hij de tour korter. Je hoeft
dus geen exacte getallen te kiezen — je stelt alleen in wat je belangrijker vindt
dan wat. Begin met de standaardwaarden en draai één knop tegelijk als je het
resultaat wilt bijsturen; dan zie je meteen het effect.

### Op welke schaal gebruik je de "Bonus"?

De "Bonus"-kolom rechts werkt met relatieve getallen, niet met minuten of
percentages. 0 betekent "geen voorkeur". Een faculteit met bonus 2 wordt twee
keer zo sterk aangemoedigd als één met bonus 1. De absolute grootte maakt niet
uit, alleen de verhouding tussen de bonussen — dus houd het simpel: gebruik een
kleine schaal, bijvoorbeeld 0, 1, 2, 3, waarbij het getal aangeeft hoe graag je
die faculteit deze week terugziet. Hoe hard deze bonussen meewegen tegenover
tevredenheid en looptijd bepaal je met de knop "Undervisited faculties": staat
die op 0, dan doen de bonussen niets; hoger betekent dat de tool harder zijn best
doet om de aangevinkte faculteiten in te plannen.

### Rechts: onderbezochte faculteiten

Een tabel met alle faculteiten en een kolom "Bonus". Zet een getal groter dan 0
bij een faculteit die je deze week extra wilt laten bezoeken (bijvoorbeeld omdat
die vorige week niet aan bod kwam). 0 betekent geen voorkeur.

### Onder "Advanced" (meestal niet nodig)

Fijnafstelling: het exacte gewicht van de 1e, 2e en 3e keuze, de bonus voor
gepaarde faculteiten, en een tijdslimiet voor de berekening. Laat dit gerust op
de standaardwaarden staan.

---

## Het resultaat lezen

- Bovenaan staat of de oplossing bewezen optimaal is: de best mogelijke indeling
  voor jouw instellingen.
- Studenten zonder gewenste keuze. Als er studenten zijn die géén van hun drie
  faculteiten op hun rondleiding hebben, worden ze apart en duidelijk getoond,
  met hun keuzes en toegewezen rondleiding, zodat je ze kunt nakijken. Meestal
  zijn dit er nul.
- Per rondleiding zie je de route ("Aula -> ... -> Aula"), de duur en de lijst
  studenten.
- De grafiek laat zien hoe tevreden studenten zijn (0 betekent geen enkele keuze
  gehonoreerd, hoger betekent betere keuzes gehonoreerd).
- De kaart toont op de echte gebouwlocaties waar de rondleidingen langslopen
  (noord boven). De rode ster is de Aula. De lijnen zijn rechte verbindingen
  tussen gebouwen, niet de exacte looproutes.

Onderaan staat een knop "Download result (Excel)" met drie tabbladen: de
rondleidingen, de volledige indeling, en een aparte lijst met studenten die geen
enkele keuze kregen.

---

## Veelgestelde vragen

De rondleidingen zijn te lang. Verlaag "Max tour duration", of zet "Shorter
tours" hoger, of verlaag "Faculties per tour".

Eén groep is veel groter dan de andere. Zet "Equal group sizes" hoger.

Een faculteit komt nooit voor. Geef die faculteit rechts een "Bonus", of zet
"Undervisited faculties" hoger.

De berekening duurt lang. Bij veel rondleidingen kan het even duren. Je kunt
onder "Advanced" de tijdslimiet aanpassen; de tool geeft dan de beste oplossing
die het binnen die tijd kon bewijzen.

Kloppen de looptijden? De looptijden tussen alle gebouwen (en van/naar de Aula)
zijn gemeten waarden. Wil je een tijd aanpassen, dan kan de beheerder die in het
bestand "travel_times.csv" wijzigen.
