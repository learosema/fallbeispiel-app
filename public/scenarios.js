// Fallbeispiele nach xABCDE. Die "hidden"-Infos kennt nur die Simulation,
// sie werden erst preisgegeben, wenn die Sanitäterin danach fragt bzw. untersucht.
// Alle Fälle sind frei erfunden und dienen nur der Ausbildung.
window.SCENARIOS = [
  {
    id: "basis-sturz",
    letter: "1.",
    title: "Sturz auf nasser Treppe",
    teaser: "Basisfall für die 1. Minute: ansprechbar, Trauma",
    dispatch: "Funkmeldung: Landungsbrücken, Person auf einer Treppe gestürzt, sitzt am Boden und ist ansprechbar.",
    scene: "Nachmittag, Landungsbrücken, Treppe zur Brücke, ca. 5 °C, leichter Regen, Tageslicht, wenige Passanten. Keine akute Gefahr, nur nasse, rutschige Stufen. 1 Betroffener, eine Passantin ist bei ihm. Hergang: auf den nassen Stufen ausgerutscht, die letzten vier Stufen hinuntergestürzt, dabei mit der Stirn kurz am Geländer angeschlagen, dann auf Gesäß und Rücken gelandet.",
    team: "Du bist mit einem Kollegen im Fußtrupp, Sanitätsrucksack dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein.",
    role: "Du spielst den Patienten Herrn Petersen (68, wach, orientiert, ein wenig beschämt und verunsichert, antwortet kurz) und die Passantin, die den Sturz gesehen hat. Dazu den Kollegen.",
    hidden: `Antwortet auf die Begrüßung normal. Sagt auf Nachfrage: ist ausgerutscht und gestürzt. Kein Bewusstseinsverlust laut Passantin, er erinnert sich an alles.
Beschwerden: leichte Nackenschmerzen beim Drehen des Kopfes, Prellung/Beule an der Stirn, Schmerz am Gesäß, rechte Handfläche aufgeschürft. Kribbeln oder Lähmungen: nein.
Schnellcheck: A/B: Luft gut, keine Schmerzen beim Atmen, keine Zyanose, AF 16, SpO2 97 % (nur wenn gemessen). C: Haut leicht blass, kühl, Puls gut tastbar, regelmäßig, ca. 78, Rekap unter 2 Sekunden, RR 145/85 (nur wenn gemessen). Trauma-Check: Bauch weich und schmerzfrei, Becken stabil und schmerzfrei, Oberschenkel unauffällig (nur wenn abgetastet). D: wach, GCS 15, orientiert zu Person, Ort, Zeit, Situation, reagiert angemessen, etwas aufgeregt. E: ihm ist kalt (nass vom Sitzen auf der Treppe, 5 °C), er friert, zittert leicht. Sonst keine Verletzungen.
SAMPLE (nur auf Nachfrage): Allergie keine, nimmt einen Blutverdünner (Apixaban) wegen Vorhofflimmern, außerdem Blutdruckmittel, letzte Mahlzeit vor 3 Std.
Wichtig: Kopfanprall unter Blutverdünner und Nackenschmerzen nach Sturz bedeuten Abklärung in der Klinik/Rettungsdienst, auch wenn es ihm gut geht. Er will zuerst nur »nach Hause«. Ohne Wärmeerhalt friert er zunehmend und zittert; bekommt er eine Decke, wird es spürbar besser (»danke, das tut gut«).`,
    keyActions: "1. Minute: Sicherheit/Lage (nasse Stufen), bedrohliche Blutung, Vorstellung (Wir sind vom DRK, Was ist passiert?), Kollege übernimmt manuelle HWS-Stabilisierung, Luft/Schmerzen beim Atmen/Zyanose, Hautfarbe, Puls, Rekap, Trauma-Check Bauch/Becken/Oberschenkel, Reaktion/Orientierung, Hergang, Frieren (Wärmeerhalt), Teambesprechung: Lage (Sturz, Kopfanprall, Nackenschmerz), Verdacht E-Problem/Trauma, Rettungsdienst/Notarzt nachfordern (Blutverdünner), SAMPLE, Immobilisation."
  },
  {
    id: "x-kettensaege",
    letter: "x",
    title: "Kettensägen-Unfall",
    teaser: "Extreme Blutung am Bein",
    scene: "Waldstück, Nachmittag, nasskalt, Tageslicht. Kettensäge ist ausgeschaltet, keine akute Gefahr für Einsatzkräfte, aber unebener, rutschiger Boden und Äste in Hanglage. 1 Betroffener, Kollege Jens vor Ort. Hergang: Säge ist abgerutscht.",
    dispatch: "Einsatzmeldung: Forstarbeiten, Person mit Schnittverletzung am Bein, stark blutend. Ein Kollege ist vor Ort.",
    role: "Du spielst abwechselnd den Patienten (Markus, 45, Forstarbeiter, ansprechbar, panisch, wird mit der Zeit blasser und schwächer) und seinen Kollegen Jens, der die Wunde mit bloßen Händen abdrückt.",
    hidden: `Tiefe Schnittwunde Oberschenkel links, innen. Hellrotes, pulsierendes Blut im Strahl, Kleidung durchtränkt, große Blutlache.
Zeit seit Unfall: ca. 4 Minuten. Ohne Blutstillung (Tourniquet/Druckverband) verschlechtert sich der Patient merklich innerhalb weniger Minuten (Schock).
A: frei, spricht. B: AF 24, Atemgeräusch beidseits normal, SpO2 97 %. C: Radialispuls schnell und schwach, HF 124, RR 100/60, Haut blass, kühl, schweißig, Rekap-Zeit 4 s. D: wach, ängstlich, GCS 15, wird unruhig. E: sonst keine Verletzungen, Kopf unverletzt, Temperatur normal, es ist kühl und nass.
Vorerkrankungen: keine, Allergien: keine, Medikamente: keine. Letzte Mahlzeit: Frühstück vor 3 Std.`,
    keyActions: "x zuerst: Tourniquet oder Druckverband/Druckpunkt, bevor irgendetwas anderes passiert; Notruf/Nachforderung; Schocklage/Wärmeerhalt; Reevaluation; zügiger Transport."
  },
  {
    id: "a-bolus",
    letter: "A",
    title: "Bolusgeschehen im Restaurant",
    teaser: "Atemwegsverlegung",
    scene: "Restaurant, Abend, gut beleuchtet, viele Gäste, keine akute Gefahr. 1 Betroffener, sitzt am Tisch, Umstehende drängen sich heran. Hergang: hat beim Essen (Steak) plötzlich gewürgt.",
    dispatch: "Einsatzmeldung: Restaurant, Mann (62) hat sich beim Essen verschluckt, kann nicht mehr richtig atmen.",
    role: "Du spielst den Patienten Herrn Weber (62, kann zunächst kaum sprechen, nur Gesten/Würgelaute) und aufgeregte Umstehende. Die Mitarbeiterin des Restaurants berichtet.",
    hidden: `Hat Steak gegessen, plötzlich Würgen, Hände am Hals, kann nicht sprechen, nur noch pfeifende Atemgeräusche/Husten mit wenig Effekt (inkomplette Verlegung, kippt bei ineffektivem Husten in komplette Verlegung).
Wird bei ausbleibender Hilfe zyanotisch, dann bewusstlos (dann Reanimationspflicht: 30:2, Atemweg kontrollieren).
Effektiver Husten: dazu auffordern. Ineffektiv: 5 Schläge zwischen die Schulterblätter, dann 5 Heimlich-Handgriffe im Wechsel. Wenn Fremdkörper gelöst: Husten, Atemnot bessert sich, SpO2 steigt.
Vitalwerte erst nach Lösung: AF 22, SpO2 92 % → 97 %, HF 110, RR 150/90, GCS 15. E: sonst unauffällig. Vorerkrankungen: Bluthochdruck, Medikament: ein Betablocker. Allergien keine.`,
    keyActions: "Beurteilung effektiv/ineffektiv Husten, Rückenschläge, Oberbauchkompression, Notruf, bei Bewusstlosigkeit Reanimation, auch bei Erfolg Nachkontrolle/Transport (Verletzungen durch Heimlich)."
  },
  {
    id: "b-asthma",
    letter: "B",
    title: "Asthmaanfall",
    teaser: "Atemnot beim jungen Patienten",
    scene: "Wohnung 2. OG, Abend, hell, aufgeräumt, keine Gefahr. 1 Betroffene, Mitbewohnerin vor Ort. Hergang: Atemnot nach Besuch bei Freunden mit Katze und Treppensteigen.",
    dispatch: "Einsatzmeldung: Wohnung, 19-jährige Frau mit akuter Atemnot, bekannte Asthmatikerin.",
    role: "Du spielst die Patientin Lena (19), sitzt vornübergebeugt, spricht nur in Halbsätzen, hat Angst. Ihre Mitbewohnerin ist auch da.",
    hidden: `Seit 30 Min zunehmende Atemnot nach Treppensteigen und Kontakt mit Katze bei Freunden. Eigenes Spray (Salbutamol) ohne Effekt, hat es 4x genommen.
A: frei. B: AF 30, Halbsätze, Einsatz der Atemhilfsmuskulatur, Auskultation: beidseits exspiratorisches Pfeifen/Giemen, verlängertes Exspirium, SpO2 90 % ohne O2 (nach O2-Gabe 94–95 %). C: HF 125, RR 130/80, Haut warm, Rekap 2 s. D: wach, GCS 15, ängstlich. E: keine Auffälligkeiten, kein Exanthem, keine Schwellung der Lippen/Zunge.
SAMPLER: Asthma seit Kindheit, Salbutamol + Kortison-Spray, Allergie auf Katzenhaare, keine Medikamentenallergie, letzte Mahlzeit vor 2 Std.
Ohne Intervention (Oberkörper hoch, beruhigen, O2, ggf. Bronchodilatator nach Kompetenz) wird sie erschöpft, SpO2 fällt Richtung 85 %.`,
    keyActions: "Sitzende Position, beruhigen, O2 nach Sättigung, Auskultation, Differenzialdiagnose Anaphylaxie ausschließen (E: Haut, Schwellung), Notarzt nachfordern, Reevaluation."
  },
  {
    id: "c-gib",
    letter: "C",
    title: "Schwäche und schwarzer Stuhl",
    teaser: "Hypovolämer Schock",
    scene: "Wohnung, Vormittag, hell, keine Gefahr, Patient liegt im Flur vor dem Bad. 1 Betroffener, Ehefrau vor Ort. Hergang: kurze Ohnmacht im Bad, Schwindel.",
    dispatch: "Einsatzmeldung: Wohnung, 71-jähriger Mann, Schwindel und Schwäche, kurzzeitig ohnmächtig gewesen.",
    role: "Du spielst den Patienten Herrn Krüger (71, schwach, blass, leicht verlangsamt) und seine Ehefrau, die berichtet.",
    hidden: `Seit 2 Tagen schwarzer, übelriechender Stuhl (Teerstuhl), heute einmal Erbrechen von kaffeesatzartigem Material. Schwindel beim Aufstehen, kurze Synkope im Badezimmer.
A: frei. B: AF 22, Lunge frei, SpO2 95 %. C: Puls flach und schnell, HF 116, RR 90/55, Haut kalt, blass, Rekap 4 s, Venen kollabiert. Bauch weich, leichter Druckschmerz Oberbauch. D: wach, GCS 15, etwas matt, BZ 118 mg/dl. E: Temperatur 36,1 °C, keine äußeren Blutungen.
SAMPLER: Medikamente: ASS 100, Ibuprofen bei Rückenschmerzen seit Wochen, Blutdruckmittel. Allergien: Penicillin. Vorerkrankungen: Hypertonie, Magengeschwür vor Jahren. Letzte Mahlzeit gestern Abend.
Wenn er aufgestellt/hingesetzt wird, droht erneute Synkope. Ohne Flachlagerung, Wärmeerhalt, Volumenmanagement (Zugang nach Kompetenz) verschlechtert er sich.`,
    keyActions: "Schockerkennung, Flachlagerung/Schocklage, Wärmeerhalt, nicht aufstehen lassen, O2 nach Bedarf, Notarzt/zügiger Transport, SAMPLER inkl. Medikation (Blutverdünner), Reevaluation."
  },
  {
    id: "d-hypo",
    letter: "D",
    title: "Verwirrte Person auf der Straße",
    teaser: "Neurologie / Hypoglykämie",
    scene: "Fußgängerzone, Vormittag, hell, viele Passanten und Schaulustige, kein Fahrzeugverkehr. 1 Betroffene sitzt auf einer Bank, abwehrend, aber nicht gefährlich. Hergang: wirkte plötzlich verwirrt und schwitzt.",
    dispatch: "Einsatzmeldung: Fußgängerzone, Frau (54) verwirrt, wirkt betrunken, schwitzt stark.",
    role: "Du spielst die Patientin Frau Demir (54, desorientiert, aggressiv-abwehrend, antwortet teils unpassend) und eine Passantin, die sie gefunden hat.",
    hidden: `Typ-1-Diabetikerin, hat Insulin gespritzt, wegen Termin nichts gegessen. Blutzucker 38 mg/dl (nur bekannt, wenn gemessen).
A: frei. B: AF 18, SpO2 98 %, Lunge frei. C: HF 108, RR 140/85, Haut feucht, kaltschweißig, Rekap 2 s. D: GCS 13 (Augen 4, verbal 4, motorisch 5), Pupillen isokor, reagieren prompt, keine Halbseitenlähmung, Gesicht symmetrisch, Sprache verwaschen/unpassend, Armvorhalteversuch o. B. E: Insulin-Pen und Diabetikerausweis in der Tasche, Einstichstellen am Bauch, Alkoholgeruch nein.
SAMPLER: Allergie keine; letzte Mahlzeit gestern Abend.
Wenn sie noch schlucken kann und wach genug ist: orale Glukose (Traubenzucker, Saft) bessert sich in 5–10 Min. Wenn Bewusstsein weiter sinkt: stabile Seitenlage, Notarzt, keine orale Gabe.
Wenn kein BZ gemessen wird, bleibt es ein Rätsel; Schlaganfall/Intoxikation sind Differenzialdiagnosen (BE-FAST prüfen).`,
    keyActions: "Blutzucker messen bei jeder Bewusstseinsstörung (D), GCS, Pupillen, FAST, Eigenschutz/Beruhigung, Glukosegabe nur bei erhaltenen Schutzreflexen, Notruf, Reevaluation."
  },
  {
    id: "e-unterkuehlung",
    letter: "E",
    title: "Unterkühlter Wanderer",
    teaser: "Exposure / Wärmeerhalt",
    scene: "Waldweg, November, Dämmerung, 3 °C, nasses Laub, rutschiger Boden, es wird bald dunkel. Keine akute Gefahr außer Sturz-/Auskühlungsrisiko für Einsatzkräfte. 1 Betroffener liegt am Wegrand, Wanderer vor Ort. Hergang unbekannt, vermutlich Sturz.",
    dispatch: "Einsatzmeldung: Waldweg, November, Wanderer (68) liegt im nassen Laub, ist ansprechbar aber verlangsamt, zittert kaum noch.",
    role: "Du spielst den Patienten Herrn Hartmann (68, verlangsamt, lallend, apathisch) und einen Wanderer, der ihn gefunden hat und per Handy berichtet.",
    hidden: `Ist vermutlich gestürzt und konnte nicht mehr aufstehen, ca. 2–3 Std. im nassen Laub bei 3 °C. Kleidung durchnässt.
A: frei. B: AF 10, flach, SpO2 nicht messbar (schlechte Perfusion der Finger). C: HF 52, Puls schwach, RR 105/70, Haut kalt, Extremitäten blass-livide, Rekap 4 s. D: GCS 14, verlangsamt, verwaschene Sprache, BZ 95 mg/dl. E: Körpertemperatur 31,8 °C (nur mit Thermometer messbar), Prellung linkes Handgelenk und Hüfte (Sturz), keine offenen Wunden.
SAMPLER: Betablocker, Herzinsuffizienz, Allergie keine, letzte Mahlzeit morgens.
Wichtig: Schonender Umgang (Kammerflimmern-Gefahr), horizontal lagern, nasse Kleidung entfernen/aufschneiden, isolieren (Rettungsdecke, Decken), keine aktive Bewegung, keine heißen Getränke/Alkohol, Notarzt, Transport. Bei Pulsfehlen länger prüfen (bis 1 Min) vor Reanimation.`,
    keyActions: "Rettung aus Kälte, Schonung, nasse Kleidung entfernen, Isolation von unten/Wärmeerhalt, Temperaturmessung, Vitalzeichenkontrolle länger, Notruf, kein Aufstehenlassen, SAMPLER, Transport."
  },

  // ---------- Bewusstlosigkeit ----------
  // Bei Sprachsteuerung nur eingeschränkt prüfbar: Die Nutzerin beschreibt, was sie tut.
  {
    id: "bw-seitenlage",
    group: "Bewusstlosigkeit",
    letter: "SL",
    title: "Bewusstlos, atmet normal",
    teaser: "Stabile Seitenlage",
    dispatch: "Meldung: Sonntagmorgen am Hamburger Fischmarkt, Passant meldet einen Mann, der reglos auf einer Bank liegt und nicht reagiert.",
    scene: "Sonntagmorgen, Fischmarkt Altona, ca. 6 °C, leichter Nieselregen, Tageslicht, viele Passanten, nasse Bank/Pflaster. Keine akute Gefahr, Verkehr in der Nähe, Gaffer. 1 Betroffener, Passant ist bei ihm. Hergang unbekannt, Passant hat ihn so gefunden. Der Rettungsdienst ist noch nicht alarmiert.",
    team: "Du bist mit einer Kollegin im Fußtrupp unterwegs, Sanitätsrucksack dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein.",
    role: "Du spielst den Passanten (Uwe, 40, unsicher) und beschreibst auf Nachfrage, was du siehst. Der Patient (Mann, ca. 58) ist bewusstlos und spricht nicht. Beschreibe seine Reaktionen nüchtern in Klammern, z. B. (stöhnt kurz).",
    hidden: `Bewusstlos: reagiert nicht auf lautes Ansprechen und leichtes Rütteln an den Schultern, auf Schmerzreiz nur ungezielte Abwehrbewegung (GCS 8). Alkoholgeruch, Flasche daneben, keine äußere Verletzung erkennbar. Er liegt auf dem Rücken.
Wenn Atemwege nicht freigemacht werden: schnarchende Atmung, Zunge fällt zurück. Nach Kopf überstrecken/Kinn anheben: Atemwege frei.
Atemkontrolle (sehen, hören, fühlen, bis 10 s): normale Atmung, ca. 14/min, regelmäßig, kräftig. Pulskontrolle: kräftig tastbar, HF 76 (nur auf Nachfrage).
Wenn flach auf dem Rücken belassen: nach ca. 2 Minuten wieder schnarchend, dann Erbrechen mit Aspiration. In stabiler Seitenlage: freie Atemwege, leichter Speichelfluss, Erbrochenes läuft ab.
Weitere Maßnahmen nur auf Nachfrage: Absaugbereitschaft, Guedel/Wendl (nach Kompetenz), BZ 96 mg/dl, SpO2 95 %, AF 14, RR 145/90, Rekap 2 s, Temperatur 35,4 °C (kühl, nass), Pupillen isokor, reagieren träge. Wärmeerhalt (Rettungsdecke) nötig. Keine Anzeichen für Trauma am Kopf.
Er kommt nicht zu sich innerhalb des Einsatzes, RD übernimmt.
WICHTIG FÜR DIE SIMULATION: Die Nutzerin beschreibt, was sie tut. Wenn sie nur "Seitenlage" sagt, frage knapp nach den Schritten (Arm, Bein, Kopf überstrecken, Atemkontrolle danach). Antworte nicht für sie.`,
    keyActions: "Eigenschutz/Lage, Ansprechen/Schmerzreiz, Atemwege frei machen (Kopf überstrecken, Kinn anheben), Atemkontrolle sehen/hören/fühlen max. 10 s, Atmung normal: stabile Seitenlage (Schritte korrekt benennen), Notruf/Nachforderung, Atemkontrolle wiederholen, Absaugbereitschaft, Wärmeerhalt, BZ/SpO2/Puls, SAMPLE von Passanten, Reevaluation, nicht allein lassen, Übergabe."
  },
  {
    id: "bw-reanimation",
    group: "Bewusstlosigkeit",
    letter: "HLW",
    title: "Bewusstlos, keine Atmung",
    teaser: "Reanimation mit AED",
    dispatch: "Funkmeldung: Laufveranstaltung an der Außenalster, Läufer zusammengebrochen und reagiert nicht, Umstehende haben nichts unternommen.",
    scene: "Vormittag, trocken, 12 °C, Tageslicht, Fuß-/Radweg direkt am Wasser, etwa 20 Zuschauer und Läufer, die Strecke ist an dieser Stelle gesperrt. Keine akute Gefahr, aber nahe Läufer und Gaffer, Platz muss freigehalten werden. 1 Betroffener liegt auf dem Weg. Hergang laut Zeugin: ist mitten im Lauf plötzlich umgefallen, ohne Sturz mit Kopfanprall, keine Bewegung mehr.",
    team: "Du bist mit einer Kollegin im Fußtrupp unterwegs, Sanitätsrucksack mit AED, Beatmungsbeutel und Absaugpumpe dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein. Umstehende können auf Anweisung helfen (z. B. Notruf, Platz freihalten, Wechsel).",
    role: "Du spielst die Zeugin (Frauke, 35, aufgelöst) und den AED (Sprachansagen). Der Patient (Mann, ca. 52) reagiert nicht. Beschreibe nüchtern in Klammern, was beobachtbar ist.",
    hidden: `Kein Ansprechen, kein Reagieren auf Rütteln. Atemwege: nach Kopf überstrecken frei. Atemkontrolle (sehen, hören, fühlen, bis 10 s): keine normale Atmung, nur vereinzelt Schnappatmung (agonal), das gilt als NICHT normal. Haut blass-livide, Pupillen weit.
Soll die Nutzerin einen Puls tasten, kann sie das; das Ergebnis ist kein tastbarer Puls (Pulskontrolle darf Beginn der HLW nicht verzögern).
Ablauf: sofortige HLW 30:2, Druckpunkt Mitte Brustkorb, Tiefe 5–6 cm, Frequenz 100–120/min. Fordert sie Notruf/AED nicht, erinnere sie nicht, sondern lass die Zeit vergehen.
AED: Elektroden (rechts unterhalb Schlüsselbein, links seitlich unter der Achsel) kleben, Brust trocken/ggf. rasieren, Ansage: "Analyse, nicht berühren." 1. Analyse: "Schock empfohlen." Sie muss laut warnen (alle weg, Sauerstoff weg) und Schock auslösen. Danach sofort 2 Min HLW. 2. Analyse nach 2 Min: "Schock empfohlen", zweiter Schock. 3. Analyse nach weiteren 2 Min: "Kein Schock empfohlen", kurz wird Puls/Atmung gesucht: nach der Analyse hustet er, atmet wieder, Puls tastbar (ROSC). Wenn HLW unzureichend (zu flach/langsam) oder Pausen lang: kein ROSC, Rettungsdienst übernimmt.
Nach ROSC: Atmung normal 16/min, SpO2 90 %, HF 110, RR 100/60, GCS 5, BZ 140, kühl. Stabile Seitenlage/ABCDE, Wärmeerhalt, O2, Reevaluation (Atmung kann wieder aussetzen), Elektroden dranlassen, Rettungsdienst/Notarzt.
Vorerkrankungen laut Zeugin: Freund sagt, er hatte Brustschmerzen am Morgen, hat Medikamente gegen Bluthochdruck.
Einsatz wird von RD nach ca. 8 Minuten übernommen: strukturierte Übergabe erwartet (Zeit des Kollaps, Beginn HLW, Schocks, ROSC-Zeit).
WICHTIG FÜR DIE SIMULATION: Die Nutzerin beschreibt, was sie tut. Wenn sie nur "HLW" sagt, frage knapp nach Druckpunkt, Tiefe, Frequenz, Verhältnis 30:2. Gib alle zwei Minuten kurz die vergangene Zeit an ("Zwei Minuten sind um, der AED fordert zur Analyse auf"). Antworte nicht für sie.`,
    keyActions: "Eigenschutz/Lage, Ansprechen/Schmerzreiz, Atemwege frei machen, Atemkontrolle max. 10 s, Schnappatmung als nicht normal erkennen, Notruf/AED veranlassen (Aufgaben delegieren), sofortige HLW 30:2 (Druckpunkt, 5–6 cm, 100–120/min, Entlastung), AED früh, Sicherheit beim Schock, Pausen minimieren, Wechsel nach ca. 2 Min, Nachforderung, nach ROSC ABCDE/Wärmeerhalt/Atemkontrolle wiederholen, strukturierte Übergabe."
  },

  {
    id: "bw-sommer",
    group: "Bewusstlosigkeit",
    letter: "SL",
    title: "Bewusstlos am Elbstrand",
    teaser: "Seitenlage im Sommer: Wärmeerhalt trotzdem",
    dispatch: "Funkmeldung: Elbstrand, Sommerabend, ein Mann liegt reglos im Sand, Freunde sind bei ihm.",
    scene: "Sommerabend, Elbstrand, 29 °C, tiefstehende Sonne, Wind vom Wasser, viele Badegäste, Gaffer. Keine akute Gefahr; der Mann liegt oberhalb der Wasserlinie auf feuchtem, kühlem Sand im Schatten eines Strandkorbs. 1 Betroffener, sein Freund Nils ist bei ihm. Hergang laut Nils: trinkt seit Mittag Alkohol, ist plötzlich eingeschlafen und nicht mehr wach zu bekommen.",
    role: "Du spielst den Freund Nils (22, ängstlich, redet schnell) und beschreibst das Beobachtbare am Patienten (Mann, ca. 30, bewusstlos) nüchtern als Befund.",
    hidden: `Bewusstlos: reagiert nicht auf lautes Ansprechen und Rütteln, auf Schmerzreiz nur ungezielte Abwehr (GCS 8). Leere Bierflaschen und eine Schnapsflasche neben ihm, deutlicher Alkoholgeruch. Er liegt auf dem Rücken.
Atemwege: schnarchend, solange er auf dem Rücken liegt; nach Kopf überstrecken/Kinn anheben frei. Atemkontrolle (sehen, hören, fühlen, bis 10 s): normale Atmung, ca. 14/min. Puls kräftig, 70.
Auf Nachfrage: SpO2 94 %, BZ 88 mg/dl, RR 120/75, Rekap 2 s, Pupillen isokor. Haut warm, trocken, sandig. Körpertemperatur 35,9 °C (Alkohol erweitert die Gefäße, Wärmeverlust).
Auf Rücken belassen: nach ca. 2 Minuten Erbrechen mit Aspiration, SpO2 fällt. In Seitenlage ok.
Wärmeerhalt: Er liegt bewusstlos auf feuchtem Sand und Wind weht, deshalb verliert er Wärme, wenn auch langsamer als bei Kälte. Ohne Decke/Rettungsdecke und Isolation vom Boden sinkt die Temperatur über ca. 10 Minuten langsam auf ca. 35,4 °C, die Haut wird kühler. Mit Decke und Isolation bleibt sie stabil.
Wird er zugedeckt, wundert sich Nils: »Zudecken? Es sind doch 29 Grad!«. Antworte darauf nur als Nils, ohne sie zu bestätigen oder zu korrigieren.
SAMPLE auf Nachfrage bei Nils: keine Allergien bekannt, nimmt keine Medikamente soweit er weiß, Mittagessen: eine Bratwurst, Alkohol seit Mittag, ca. 10 Bier und mehrere Schnäpse. Keine Verletzungen, keine Sturzbeobachtung.
Der Mann wird innerhalb des Einsatzes nicht wach, RD übernimmt.
WICHTIG FÜR DIE SIMULATION: Die Nutzerin beschreibt, was sie tut. Wenn sie nur »Seitenlage« oder »Wärmeerhalt« sagt, frage knapp nach den Schritten bzw. wie (Decke, Isolation vom Boden). Antworte nicht für sie.`,
    keyActions: "Eigenschutz (Wasser, Gaffer, Sonne), Ansprechen/Schmerzreiz, Atemwege frei machen, Atemkontrolle max. 10 s, normale Atmung: stabile Seitenlage, Notruf/Nachforderung, Absaugbereitschaft, BZ/SpO2/Puls/Temperatur, Wärmeerhalt trotz Sommer (Decke/Rettungsdecke, Isolation vom feuchten Boden), SAMPLE vom Freund, Atemkontrolle wiederholen, Übergabe."
  },

  // ---------- Hamburger DOM (Heiligengeistfeld) ----------
  // Einsatz als Fußtrupp (2 Personen, Sanitätsrucksack), Rettungsdienst muss nachgefordert werden.
  {
    id: "dom-krampf",
    group: "Hamburger DOM",
    letter: "D",
    title: "Krampfanfall am Winter-DOM",
    teaser: "Anfall in der Warteschlange",
    dispatch: "Funkmeldung DOM: Person hat bei den Autoscootern gekrampft, liegt am Boden, Umstehende sind bei ihr. Ihr seid der nächste Fußtrupp.",
    scene: "Winter-DOM, Abend, ca. 2 °C, nasses Pflaster, Lichter, laute Musik, dichtes Gedränge, viele Schaulustige. Keine akute Gefahr, aber Gedränge und kalter nasser Boden. 1 Betroffener, Freundin und Fremde stehen daneben. Hergang laut Freundin: ist plötzlich umgefallen und hat am ganzen Körper gezuckt.",
    team: "Du bist mit einer Kollegin im Fußtrupp, Sanitätsrucksack dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein.",
    role: "Du spielst den Patienten Jonas (24) und seine Freundin Lea, die aufgeregt berichtet. Bei Eintreffen krampft Jonas noch (ca. 1 Minute seit Beginn). Danach ist er postiktal: schläfrig, verwirrt, desorientiert.",
    hidden: `Bekannte Epilepsie (Levetiracetam), heute Medikament vergessen, 3 Glühwein, wenig geschlafen. Beim Sturz mit dem Hinterkopf aufgeschlagen, Platzwunde Hinterkopf, blutet mäßig.
Krampf endet nach ca. 2,5 Minuten insgesamt (wenn die Zeit gestoppt wird: Dauer erfragbar). Während des Anfalls: nichts in den Mund stecken, Umfeld sichern, Kopf polstern.
Nach dem Anfall: A: Atemwege frei, Blut und Schaum im Mund (Zungenbiss), schnarchende Atmung zu Beginn. B: AF 22, SpO2 91 % → 96 % nach Lagerung/Ruhe (ggf. O2 nach Bedarf). C: HF 112, RR 140/85, Rekap 2 s, Haut warm/schweißig. D: GCS 12 anfangs (Augen 3, verbal 4, motorisch 5), nach 10 Min GCS 14, desorientiert zu Zeit und Ort, Pupillen isokor, reagieren prompt, keine Halbseitensymptome, BZ 102 mg/dl. E: eingenässt, durchnässt vom Boden, Auskühlung beginnt, Platzwunde Hinterkopf, sonst keine Verletzungen, Alkoholgeruch.
SAMPLE: Allergie keine, Medikament s. o., Vorerkrankung Epilepsie, letzte Mahlzeit Bratwurst vor 3 Std.
Wegen Sturz mit Kopfanprall, Alkohol und noch verändertem Bewusstsein ist Nachforderung des Rettungsdienstes sinnvoll. Er will anfangs "nur nach Hause".`,
    keyActions: "Sicherheit/Gedränge, Zeit des Anfalls erfassen, nichts in den Mund, Umfeld sichern/Kopf schützen; nach dem Anfall Atemkontrolle, Seitenlage bzw. Atemweg frei halten, Absaugbereitschaft, bei Kopfanprall an HWS denken, BZ messen, GCS/Orientierung, Wärmeerhalt (nass, kalt), Platzwunde versorgen, SAMPLE, Rettungsdienst nachfordern, Reevaluation."
  },
  {
    id: "dom-nase",
    group: "Hamburger DOM",
    letter: "A",
    title: "Faustschlag auf die Nase",
    teaser: "Blut im Rachen, Alkohol, Gedränge",
    dispatch: "Funkmeldung DOM: Schlägerei vor einem Imbiss, ein Mann blutet stark im Gesicht. Polizei ist informiert.",
    scene: "DOM, spät abends, laute Musik, viele Alkoholisierte. Die Beteiligten sind nicht mehr handgreiflich, aber die Stimmung ist aufgeheizt, Freunde des Patienten drängeln. Der andere Beteiligte ist weggerannt. 1 Betroffener, sitzt auf einer Bordsteinkante. Polizei noch nicht vor Ort, Streife kommt in ca. 5 Minuten.",
    team: "Du bist mit einem Kollegen im Fußtrupp, Sanitätsrucksack mit Absaugpumpe dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein.",
    role: "Du spielst den Patienten Kevin (28, alkoholisiert, genervt, unkooperativ, will nur »weiter feiern«) und seinen Kumpel Dennis, der dazwischenredet.",
    hidden: `Faustschlag ins Gesicht vor ca. 10 Minuten. Nase deformiert und stark geschwollen, starkes Nasenbluten, Blut läuft in den Rachen, er schluckt und hustet, ihm ist übel. Er spuckt Blut. Zahn locker oben.
Wird er flach gelagert oder bewusstseinsgetrübt, droht Aspiration; bei fehlendem Absaugen und Erbrechen verschlechtert sich der Atemweg (Gurgeln, SpO2 sinkt).
A: frei, aber Blut im Mund/Rachen, gurgelnde Atmung bei Lagerung nach hinten. B: AF 20, SpO2 95 %, Lunge frei. C: HF 100, RR 135/80, Rekap 2 s, Haut warm. D: GCS 14 (verbal 4: leicht verwirrt, wiederholt Fragen), Pupillen isokor, kurze Erinnerungslücke zum Schlag, BZ 130. E: sonst nur Schürfung am Handrücken, Alkoholgeruch deutlich (ca. 2 Promille geschätzt), keine weiteren Verletzungen.
SAMPLE: Allergie keine, Medikamente keine, Vorerkrankungen keine, letzte Mahlzeit vor 4 Std., viel Bier.
Er will teils wegrennen/ablehnen. Eigenschutz und Deeskalation sind wichtig.`,
    keyActions: "Eigenschutz/Deeskalation, Polizei, Lage; A-Problem erkennen: sitzend mit leicht vorgeneigtem Oberkörper, Absaugbereitschaft/Absaugen, Blutung stillen (Nasenflügel/Kühlen), Aspirationsrisiko beachten; GCS/Orientierung, an SHT/HWS denken bei Gewalt gegen Kopf, Alkohol als Fehlerquelle; Rettungsdienst nachfordern; Einwilligungsfähigkeit/Ablehnung sauber klären und dokumentieren."
  },
  {
    id: "dom-fahrgeschaeft-kollaps",
    group: "Hamburger DOM",
    letter: "C",
    title: "Kollaps nach der Achterbahn",
    teaser: "Schwarz vor Augen nach der Fahrt",
    dispatch: "Funkmeldung DOM: Jugendliche ist nach dem Aussteigen aus einem Fahrgeschäft zusammengesackt, ansprechbar.",
    scene: "Sommer-DOM, Nachmittag, 28 °C, sonnig, sehr voll, laute Musik. Das Fahrgeschäft ist angehalten, das Personal hat die Betroffene auf eine Bank neben den Ausgang gesetzt. 1 Betroffene, Freundinnen dabei. Keine akute Gefahr, aber Gedränge am Ausgang. Hergang: nach der Fahrt kurz schwarz vor Augen, ist zur Seite gesackt, dabei nicht aufgeschlagen.",
    team: "Du bist mit einer Kollegin im Fußtrupp, Sanitätsrucksack dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein.",
    role: "Du spielst die Patientin Mira (17, blass, benommen, peinlich berührt) und ihre Freundin Ayla, die erzählt, was vorher war.",
    hidden: `Hat heute nur einen Energy-Drink und Zuckerwatte gehabt, wenig getrunken, vorher 2x Fahrgeschäfte. Bei Aufstehen Schwindel und "Sterne sehen". Kein Herzrasen, kein Brustschmerz, keine Vorerkrankungen bekannt, keine Krampfzeichen. Kurze Bewusstlosigkeit ca. 10 Sekunden, schnell wieder wach (vasovagal bei Kreislaufbelastung/Hitze/wenig Trinken).
A: frei. B: AF 20, SpO2 98 %, Lunge frei, keine Atemnot. C: Puls 58 regelmäßig, nach 3 Min Beine hoch/flach 76, RR 95/55 → 110/70, Rekap 3 s → 2 s, Haut blass, kühl, feucht. Stehen oder Aufsetzen löst erneut Schwindel aus. D: wach, GCS 15 nach kurzer Ansprache, orientiert, BZ 78 mg/dl. E: heiß, enge Kleidung, keine Verletzungen, keine Zeichen für Sturzfolgen.
SAMPLE: Allergie keine, Medikamente keine (nimmt Pille), keine Vorerkrankungen, Familienanamnese: ein Onkel hatte "etwas mit dem Herzen". Letzte Mahlzeit heute früh.
Wenn sie flach liegt/Beine hoch, Trinken und Zucker, erholt sie sich in ca. 10 Min. Auch bei Erholung: Abklärung beim Arzt empfehlen, bei Unsicherheit Rettungsdienst/Telefonberatung.`,
    keyActions: "Sicherheit/Lage, flach lagern bzw. Beine hoch (Schocklage), nicht aufstehen lassen, Puls und Rekap-Zeit, RR, BZ messen, Trinken/Zucker anbieten, Hitze reduzieren, SAMPLE inkl. Familienanamnese und Herzsymptomen, Reevaluation, Abklärung/Übergabe-Entscheidung begründen (Rettungsdienst oder ärztliche Abklärung), nicht allein lassen."
  },
  {
    id: "dom-sturz-fahrgeschaeft",
    group: "Hamburger DOM",
    letter: "B",
    title: "Sturz aus dem Fahrgeschäft",
    teaser: "Polytrauma, du bist zuerst da",
    dispatch: "Funkmeldung DOM: Person aus einem Fahrgeschäft gestürzt, liegt am Boden, nicht ansprechbar wie vorher. Fahrgeschäft wurde per Not-Aus gestoppt. Rettungsdienst ist alarmiert, ihr seid als Erste da.",
    scene: "DOM, Abend, dunkel, grelle Lichter, laute Musik (Betreiber hat sie abgestellt), große Menschentraube. Fahrgeschäft ist per Not-Aus gestoppt, trotzdem ist der Bereich um die Gondeln nicht sicher, bis das Personal bestätigt. 1 Betroffener liegt auf dem Pflaster neben der Absperrung, ca. 4 m tief gestürzt. Betreiber-Mitarbeiter und Freund vor Ort.",
    team: "Du bist mit einer Kollegin im Fußtrupp, Sanitätsrucksack dabei. Der Rettungsdienst ist bereits alarmiert und trifft in ca. 8 Minuten ein; Nachforderung ist trotzdem zu bestätigen, auch ob Notarzt benötigt wird.",
    role: "Du spielst den Patienten Marco (31, Schmerzen, ängstlich, stöhnt, antwortet mühsam) und seinen Freund Tim, der geschockt ist.",
    hidden: `Sturz aus ca. 4 m auf Pflaster, landete auf rechter Körperseite. Rechter Brustkorb schmerzt stark, Schmerzen beim Atmen, Becken schmerzt, linker Oberschenkel geschwollen und verformt, kein offener Bruch. Kopfplatzwunde rechts, kurzer Gedächtnisverlust.
Zu Beginn: A: frei, spricht in kurzen Sätzen. B: AF 30, flach, rechts abgeschwächtes Atemgeräusch, Prellmarke rechter Thorax, SpO2 88 % → 93 % unter O2, Halsvenen zunehmend gestaut ab Minute 6. C: HF 126, RR 95/60 sinkend, Haut blass, kaltschweißig, Rekap 4 s, Bauch weich aber druckschmerzhaft, Becken: Druckschmerz (nur einmal vorsichtig prüfen, nicht wiederholt komprimieren), Oberschenkel links geschwollen und kurz. D: GCS 14, orientiert, Pupillen isokor, BZ 118, Schmerz 9/10. E: kalt, 8 °C, durchnässt vom Boden, Prellungen, Platzwunde Kopf, keine weiteren offenen Verletzungen.
SAMPLE: Allergie Penicillin, Medikament keine, Vorerkrankung keine, letzte Mahlzeit vor 2 Std., Glühwein 1 Becher.
Ohne Wärmeerhalt, Immobilisation und O2 verschlechtert er sich (Schockzeichen, Sättigung fällt). Bewegt man ihn grob, schreit er und der Blutdruck fällt weiter. Rettungsdienst trifft ca. 8 Minuten nach Beginn ein, dann Übergabe.`,
    keyActions: "Sicherheit/Betreiber-Not-Aus bestätigen, Lage, Nachforderung bestätigen (Notarzt/RTW/ggf. Schockraum), manuelle HWS-Immobilisation, B-Problem erkennen (einseitig abgeschwächt, Schmerzen beim Atmen, gestaute Halsvenen, Schockzeichen, Spannungspneumothorax denken), O2, Pulsoxi, C: Schockzeichen, Trauma-Check Bauch/Becken/Oberschenkel, Becken nur einmal vorsichtig prüfen, Wärmeerhalt, schonende Rettung (Schaufeltrage/Vakuummatratze), Schienen nach Kompetenz, strukturierte Übergabe, Reevaluation."
  },

  // ---------- FC St. Pauli, Millerntor-Stadion ----------
  // Sanitätsdienst bei Heimspielen: fast immer Besucher, nicht Spieler.
  {
    id: "mil-alkohol",
    group: "Millerntor (FC St. Pauli)",
    letter: "D",
    title: "Besucher nach dem Spiel, stark alkoholisiert",
    teaser: "Ist es wirklich nur der Alkohol?",
    dispatch: "Funkmeldung Millerntor: Ordner meldet einen Besucher auf der Treppe im Stehplatzbereich, reagiert kaum, hat erbrochen.",
    scene: "Heimspiel, Spielende vor 15 Minuten, Stadionausgang, viele Menschen strömen vorbei, Kälte (ca. 4 °C), Treppe aus Beton, nasse Stufen. Keine akute Gefahr, aber Gedränge und Rutschgefahr. 1 Betroffener sitzt zusammengesackt an der Wand, Ordner und ein Freund sind bei ihm. Hergang laut Freund: hat seit Mittag getrunken, ist auf der Treppe gestürzt, danach noch gelaufen, dann zusammengesackt.",
    team: "Du bist mit einer Kollegin als Fußtrupp des Sanitätsdienstes im Stadion unterwegs, Sanitätsrucksack dabei. Über Funk ist die Einsatzleitung/der Rettungsdienst im Stadion erreichbar. Ein RTW braucht durch die Menschenmenge ca. 8 Minuten.",
    role: "Du spielst den Patienten Torben (34, lallt, schläfrig, reagiert nur auf lauten Anruf) und seinen Freund Hendrik, der meint, er habe nur zu viel getrunken.",
    hidden: `Alkoholgeruch, ca. 2,5 Promille geschätzt, seit Mittag Bier und Schnaps, kaum gegessen. Nach Treppensturz ca. 30 Minuten vor Eintreffen. Hat ein Mal erbrochen.
A: frei, aber Erbrochenes im Mund, schwaches Schlucken, Aspirationsgefahr wenn er flach liegt. B: AF 12, flach, SpO2 94 %, Lunge frei. C: HF 62, RR 150/90, Rekap 2 s, Haut kalt. D: GCS 11 (Augen 2, verbal 4, motorisch 5), reagiert auf Ansprache, Pupillen isokor aber träge, BZ 52 mg/dl (Alkohol ohne Essen), Orientierung nicht möglich. E: Hämatom am Hinterkopf (Sturz), kalt (Auskühlung), nasse Hose, keine weiteren Verletzungen.
SAMPLE: Allergie keine, Medikamente unbekannt (Freund weiß nichts), letzte Mahlzeit gestern.
Ohne Seitenlage/Absaugen droht erneutes Erbrechen mit Aspiration. Wird der BZ nicht gemessen, bleibt die Hypoglykämie unentdeckt. Wird er flach auf den Rücken gelegt, verschlechtert sich der Atemweg. Bei Verschlechterung der Bewusstseinslage trotz Maßnahmen: Hinweis auf SHT, Rettungsdienst/Notarzt.`,
    keyActions: "Eigenschutz/Gedränge, Ansprache/Schmerzreiz, A: Atemwege freimachen, Seitenlage/Absaugbereitschaft bei Erbrechen, B/C Messwerte, D: GCS/Orientierung/Pupillen, BZ messen (Alkohol nicht als alleinige Erklärung annehmen), HWS bei Sturz mit Kopfanprall bedenken, Wärmeerhalt, SAMPLE, Rettungsdienst nachfordern, nicht allein lassen, Reevaluation."
  },
  {
    id: "mil-pyro-asthma",
    group: "Millerntor (FC St. Pauli)",
    letter: "B",
    title: "Pyro-Rauch im Block, Atemnot",
    teaser: "Asthma + dichter Rauch",
    dispatch: "Funkmeldung Millerntor: Im Stehplatzblock wurde Pyrotechnik gezündet, eine Frau hat starke Atemnot und hustet.",
    scene: "Heimspiel, Stehplatzblock, dichte Rauchwolke, Rauch zieht langsam über den Block, schlechte Sicht, laute Stimmung. Bengalische Feuer sind teils noch aktiv, Funkenflug in Block-Nähe, Menschen drängeln. Für Einsatzkräfte: Rauch, Funken, Gedränge, nicht länger als nötig im Rauch bleiben. 1 Betroffene wurde von Umstehenden an den Rand gebracht, sitzt auf einer Stufe.",
    team: "Du bist mit einem Kollegen als Fußtrupp des Sanitätsdienstes im Stadion unterwegs, Sanitätsrucksack mit Pulsoxymeter und Sauerstoff dabei. Funkkontakt zur Einsatzleitung/zum Rettungsdienst im Stadion. Ein RTW braucht ca. 8 Minuten.",
    role: "Du spielst die Patientin Sophie (29, hustet, ringt nach Luft, spricht nur Halbsätze, panisch) und ihren Freund Ole, der ihr Spray sucht.",
    hidden: `Asthma seit Kindheit, Spray (Salbutamol) im Auto vergessen. Bei Rauch sofort starker Hustenreiz, Engegefühl, pfeifende Atmung. Kein Brustschmerz. Kein bekannter Funkenflug auf Haut/Haare, keine Verbrennungen.
A: frei, aber Husten, leichte Heiserkeit, leichte Rußspuren am Mundwinkel. B: AF 30, Einsatz der Atemhilfsmuskulatur, Halbsätze, exspiratorisches Giemen beidseits, SpO2 91 % (bei Rauch evtl. trügerisch, Gabe von O2 nach Bedarf, mit O2 94 %). C: HF 122, RR 135/85, Rekap 2 s, Haut warm, feucht. D: wach, GCS 15, ängstlich, BZ 104. E: Augen tränen, gerötet, keine Verbrennungen.
SAMPLE: Allergie keine, Medikament Salbutamol, Vorerkrankung Asthma, letzte Mahlzeit vor 3 Std., Bier 2.
Wird sie aus dem Rauch gebracht (frische Luft), aufrecht gelagert und beruhigt, wird es etwas besser, aber Atemnot bleibt. Bleibt sie im Rauch, verschlechtert sich die Atmung deutlich (SpO2 sinkt, Erschöpfung). Wenn eigenes Spray nicht verfügbar ist, Rettungsdienst/Notarzt nachfordern (Bronchodilatator nur nach Kompetenz).`,
    keyActions: "Eigenschutz (Rauch, Funken, Gedränge), Patientin aus dem Rauch bringen, B-Problem: aufrecht/Oberkörper hoch, Atemanweisungen, O2, Pulsoxi (bei Rauch mit Vorsicht deuten), Auskultation, A: Heiserkeit/Rußspuren als Warnzeichen (Inhalationstrauma?), SAMPLE inkl. Spray, Rettungsdienst nachfordern, Reevaluation."
  },
  {
    id: "mil-pyro-brand",
    group: "Millerntor (FC St. Pauli)",
    letter: "E",
    title: "Funkenflug: Verbrennungen",
    teaser: "Brandwunden an Arm und Gesicht",
    dispatch: "Funkmeldung Millerntor: Besucher hat sich bei Pyrotechnik verbrannt, hält sich Gesicht und Arm.",
    scene: "Heimspiel, Stehplatzbereich, kühl (ca. 5 °C), Rauchreste, Geruch nach verbranntem Kunststoff, ein Rest der Pyrotechnik liegt noch qualmend am Boden. Gedränge, Ordner sichern ab. Für Einsatzkräfte: Rest-Pyro noch heiß, Funken, Gedränge. 1 Betroffener sitzt am Rand, Freunde und Ordner dabei. Hergang: Fackel ist aus der Hand gerutscht, Funken und heiße Partikel trafen Arm und Gesicht.",
    team: "Du bist mit einer Kollegin als Fußtrupp des Sanitätsdienstes im Stadion unterwegs, Sanitätsrucksack dabei (u. a. Verbandmaterial, steriles Wasser, Wasserflaschen, Rettungsdecke). Funkkontakt zur Einsatzleitung/zum Rettungsdienst im Stadion. Ein RTW braucht ca. 8 Minuten.",
    role: "Du spielst den Patienten Leon (22, Schmerzen, entsetzt, hält sich das linke Auge zu, will seine Jacke nicht ausziehen) und seinen Freund Finn.",
    hidden: `Verbrennungen 2. Grades am linken Unterarm (Rötung, Blasen, nässend, ca. 4–5 % KOF), Funkenlöcher in der Jacke, Kunststoffjacke teilweise angeschmolzen am Ärmel. Leichte Verbrennungen am Kinn, angesengte Augenbrauen. Linkes Auge: Fremdkörpergefühl, Brennen, Tränenfluss, Lidspalte zugekniffen, kann schlecht sehen, Funkenpartikel im Auge möglich.
A: frei, leichte Heiserkeit, kein Ruß in Mund/Nase sichtbar, Atmung unauffällig. B: AF 20, SpO2 98 %, Lunge frei. C: HF 108, RR 140/85, Rekap 2 s, sonst Haut warm. D: wach, GCS 15, Schmerz 8/10, Gesicht symmetrisch. E: Unterarm links verbrannt, Augenbrauen angesengt, Auge gerötet, Hand ok, keine weiteren Verletzungen, durch Kühlung/Auskleiden droht Auskühlung bei 5 °C.
SAMPLE: Allergie keine, Medikamente keine, Tetanusimpfung unklar, letzte Mahlzeit vor 2 Std., Bier 3.
Wenn die angeschmolzene Kleidung grob abgerissen wird, verstärken sich Schmerzen und Gewebeschaden. Wird nicht gekühlt, bleiben Schmerzen hoch. Das Auge ist ein Notfall: nicht reiben, sauber abdecken/spülen nach Anweisung, zügiger Transport zur Augenabklärung. Bei Heiserkeit/Husten im Verlauf: Atemweg beobachten.`,
    keyActions: "Eigenschutz (Rest-Pyro), Verbrennung beenden/Kleidung nicht grob abreißen (angeschmolzenes Material belassen), Kühlen (lauwarmes Wasser, nicht eiskalt, zeitlich begrenzt, auf Auskühlung achten), steriler Verband, Auge: nicht reiben, vorsichtig spülen bzw. abdecken, Visus/Schmerz erfragen, A: Heiserkeit/Ruß beobachten (Inhalationstrauma), Schmerzen, Wärmeerhalt, SAMPLE inkl. Tetanus, Rettungsdienst nachfordern/Augenabklärung, Reevaluation."
  }
];
