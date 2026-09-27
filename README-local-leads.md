# Lietuvos verslų vieši el. paštai

CSV failai saugomi atidaryto darbo aplanko šaknyje, `../leads/lithuania/`, kad juos būtų lengva rasti. `all_leads.csv` turi tik du stulpelius: `Pavadinimas` ir `El. paštas`. Specialybės CSV sukuriami tik radus pirmą adresą tai specialybei, todėl tuščių failų krūvos nėra.

Programa naudoja 238 atrinktas specialybes ir 103 Lietuvos miestus. Ji tikrina viešus verslo svetainių kontaktų puslapius ir `robots.txt`; adresą įrašo, jei jis paskelbtas viešai, o jo domenas turi MX arba A DNS įrašą. DNS patikra patvirtina domeną, bet ne konkrečios pašto dėžutės veikimą. Bendrame CSV el. paštai nedubliuojami.

Mažas bandymas, ne daugiau kaip 10 el. paštų iš viso:

```powershell
& '..\.venv\Scripts\python.exe' fast_leads.py
```

Pirmų dviejų specialybių bandymas per visus Lietuvos miestus, be 10 el. paštų ribos:

```powershell
& '..\.venv\Scripts\python.exe' fast_leads.py --pilot-specialties 2
```

Šis bandymas apima `kirpykla` ir `plaukų salonas`. Jei mieste paieška nieko neranda, programa pereina prie kito miesto. Nepavykusią Maps užklausą pabando dar kartą, po to ją praleidžia, pažymi žurnale ir palieka vėlesniam paleidimui.

Programa nenaudoja modelio API ar AI tokenų. Paieškos progresas saugomas `results/leads.sqlite3`, o el. paštai į CSV įrašomi partijomis. Pilnas visų specialybių rinkimas paleidžiamas tik gavus aiškų patvirtinimą, paslėptame fone:

```powershell
& .\start_overnight.ps1
```

Jis tęsia progresą ir sustoja ties 30 000 el. paštų arba 100 000 verslų riba. Žurnalas yra `results/fast-leads.log`, proceso PID – `results/overnight.pid`. Tvarkingai sustabdyti galima `& .\stop_overnight.ps1`; programa užbaigs pradėtą paiešką, išsaugos CSV ir sustos. Tiesioginė pilno rinkimo komanda pirmame plane yra `& '..\.venv\Scripts\python.exe' fast_leads.py --overnight`.

Prieš rinkodaros siuntimą patikrink gavėjo statusą ir laikykis taikomų tiesioginės rinkodaros taisyklių. VDAI 2026 m. paaiškinime juridinių asmenų laiškams nurodomas paprastas atsisakymas kiekviename laiške, o fiziniams asmenims – išankstinio sutikimo reikalavimas.

Kategorijų failai: `../leads/lithuania/categories/`. Šalių struktūra ir atkūrimas aprašyti `README-campaigns.md`.
