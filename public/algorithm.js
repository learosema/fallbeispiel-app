// Referenz-Algorithmus für die Auswertung, zusammengefasst nach dem DRK-SANmemo (2024).
// Bewusst nur als knappe Checkliste, nicht als Abschrift des Memos.
window.ALGORITHM = `
1. MINUTE
- Sicherheit: akute Gefahr für Einsatzkräfte, Betroffene, andere Personen?
- Lage: Zahl der Betroffenen, Hergang erkennbar, Umfeld (Gelände, Wetter, Licht, Uhrzeit)?
- Bedrohliche Blutung? Dann sofort Blutstillung (x).
- Vorstellen und ansprechen (Name/Organisation, "Was ist passiert?").
- Patient:in bewusstlos: Atemwege frei machen, Atemkontrolle (sehen, hören, fühlen, max. 10 s). Atmung nicht normal: HLW und AED. Atmung eindeutig normal: Seitenlage. Wärmeerhalt (Decke/Rettungsdecke) immer, unabhängig von der Außentemperatur (bei Kälte friert die Person nur schneller). Ggf. Guedel/Wendl, Absaugbereitschaft.
- Patient:in wach: Schnellcheck. Trauma: ggf. manuelle HWS-Immobilisierung. A/B: "Bekommen Sie gut Luft?", Schmerzen beim Atmen, Zyanose. C: Hautfarbe, Puls (nicht zählen), Rekap-Zeit, bei Trauma innere Blutung (Bauch, Becken, Oberschenkel abtasten). D: angemessene Reaktion, Gemütslage. E: Verletzungsmechanismus, Umfeld, Frieren. Friert die Person, bekommt sie sofort eine Decke (Wärmeerhalt); Nachfragen allein reicht nicht.
- Teambesprechung/Rückmeldung: Lage, Verdachtsdiagnose (A/B/C/D/E-Problem), Notarzt/Notärztin nötig?
- Funkspruch/Statusmeldung an die Leitstelle (Abschluss der 1. Minute, Praxis DRK Hamburg):
  1. Anruf mit beiden Rufnamen: "<Leitstelle> von <eigener Rufname>, kommen." Dann auf "Hier <Leitstelle>" warten.
  2. Meldung kurz und strukturiert: Patient (Geschlecht, Alter ungefähr), Ereignis, Verdachtsdiagnose, Nachforderung (z. B. RTW und/oder NEF), Abschluss "kommen". Nachforderung muss zur Lage passen.
  3. Die Leitstelle wiederholt die Nachforderung ("RTW NEF kommt, verstanden").
  4. Abschluss: "<eigener Rufname> Ende."
  Beispiel: "RotkreuzHamburg von EVT1 kommen." – "Hier RotkreuzHamburg." – "Wir haben hier eine Patientin, weiblich, Mitte 40, gestürzt, Verdacht auf Unterschenkelfraktur, wir brauchen einmal RTW und NEF, kommen." – "RTW NEF kommt, verstanden." – "EVT1 Ende."

ABCDE (jeweils "Immer richtig" plus Maßnahmen bei Problem)
A Airway: Trauma? Ggf. HWS-Stützkragen. Problem: Lagerung mit erhöhtem Oberkörper; Bolusaspiration: Rückenschläge, dann Oberbauchkompressionen; Schwellung Mund/Rachen: kühlen.
B Breathing: Atmung beurteilen, Pulsoximetrie (mind. 94 %), O2-Gabe erwägen. Problem: Oberkörper hoch, Atemanweisungen, gestaute Halsvenen/Schockzeichen (Spannungspneumothorax?), Brustkorb-/Lungenverletzung: ggf. Lagerung auf verletzte Seite.
C Circulation: Puls (80–100/min), Rekap-Zeit (max. 2 s), Blutdruck (ca. 120/80 mmHg). Problem: Ursache bekämpfen; Herzprobleme: Oberkörper hoch; akutes Abdomen: Beine angezogen; Volumenmangel: Schocklage; ggf. Infusion/Medikamente vorbereiten.
D Disability: Bewusstsein (wach / Ansprache / Schmerzreiz / bewusstlos), Orientierung zu Person, Situation, Ort, Zeit. Problem: Lagerung i. d. R. Oberkörper hoch; Schlaganfall? FAST (Face, Arm, Speech, Time).
E Exposure/Environment: SAMPLE-Anamnese, Ganzkörperuntersuchung inkl. DMS, Wärmeerhaltung (immer richtig, unabhängig von der Außentemperatur: wichtig für stabile Vitalwerte; bei Kälte friert die Person nur schneller; Isolation vom Boden). Problem: Schaufeltrage/Spineboard/Vakuummatratze; Extremitätenverletzung: Immobilisieren (Schiene); Wunde: steriler Verband.
Nach Abschluss von E wieder bei A beginnen: Diagnostik und Maßnahmen fortführen (Reevaluation).
`.trim();
