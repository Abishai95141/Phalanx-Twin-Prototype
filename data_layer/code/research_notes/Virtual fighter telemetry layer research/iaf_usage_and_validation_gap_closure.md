# IAF / Tejas operating usage, released replacements for restricted phase values, structural and engine usage spectra, and validation-method gap closure (Project Phalanx)

**Purpose.** This note builds on `flight_profiles_and_usage.md`, `f404_in20_engine_model.md`, `validation_and_calibration.md`, `indian_fleet_platform_relevance.md`, `tejas_airframe_aero_fcs.md` and `maintenance_records_and_events.md`. It does not repeat their settled content except where a value is replaced, corrected or needed for the end tables. It aims to give the virtual Tejas-class fighter (HAL Tejas Mk1A, GE F404-GE-IN20) defensible operating-usage statistics and phase values from officially released sources, and to close the open quantitative gaps in the validation methodology.

**Evidence tags (on every claim).**
- **[DIRECT]** = about the IAF or the Tejas / F404-IN20 itself.
- **[TRANSFER: X]** = from force or platform X. The reason it transfers and its limits are stated.
- **[ASSUMPTION]** = engineering judgement or my own arithmetic, with a validation route.
- "(secondary)" = news or aggregator reporting of an official statement; "(search excerpt)" = a figure seen only in a search-engine excerpt because the page or PDF could not be parsed here. Treat both as weaker.

**How the work was done (read first).**
- **WebSearch:** about 61 calls, within this researcher's share of about 100. Everything else came from direct fetches and from reading PDFs.
- **Access:** PIB pages, Business Standard, HAL, archive.org DTIC mirrors, NTRS, NLR, VTT, arXiv, FAA and gov.uk all worked with curl. These sites blocked automated access: pib.gov.in (WebFetch only; curl worked), media.defense.gov, afjag.af.mil, sto.nato.int, eparlib/rsdebate (Parliament Q&A archives), cag.gov.in/calm.cag.gov.in, rosap.ntl.bts.gov and gao.gov PDFs. As a result, no Lok Sabha / Rajya Sabha answer text could be read. IAF Parliament evidence below comes from the Standing Committee reports already saved locally.
- **New downloads** (read only, nothing executed) are in `/Users/abishaikc/Phalanx/research_sources/usage_validation_gaps/`:
  - AGARD-R-815 (1997)
  - NLR TP-1998-172 and TP-2002-309 (RNLAF F-16 loads and usage)
  - FINAF ICAF national reviews 2007, 2011, 2015, 2017 and VTT-CR-00252-23 (2023)
  - White et al. 2015 (RAAF F/A-18 fatigue tracking)
  - USAF Air Emissions Guide (DTIC ADA577276)
  - USAF IERA engine emissions testing Vol. 1 and Vol. 3 (ADA361474, ADA361473)
  - NADC-91027-60 (ADA239511)
  - ASD-TR-72-113 text (AD0761491)
  - NASA TM-88943 (UETP)
  - FAA AC 43-207
  - UK MAA RA 2375 Issue 5
  - NLR GM-VV overview (TP-2013-598)
  - TU Delft AEE thesis; ERF 2024 helicopter time-domain ID paper
  - arXiv 1711.10010, 2506.23302, 2604.20293; SESAR SIDs 2024 paper 054
  - HAL analyst-call transcript (15 May 2026)
- **Source restrictions honoured.** Nothing in `research_sources/_restricted_do_not_cite/` was opened. The values that sibling notes took from the F/A-18 NATOPS (Distribution C) and the Hellenic AF F-16 manual (foreign-disclosure restricted) were identified by grepping the sibling note `flight_profiles_and_usage.md` (lines 44–766). They are listed in Q3 and table (c) with their replacement status. Local USAF Accident Investigation Board (AIB) reports saved by the sibling texture/fault researcher under `research_sources/texture_fault_gaps/` were read. They are officially released USAF reports.

---

## Q1. IAF and Tejas operational usage: hours per aircraft and per pilot, flying-task shortfalls, exercise sortie rates, basing and climate, sortie lengths and mission mix, seasonal and night flying

### Takeaway
- **What is public:** no officially released source gives IAF flying hours per fighter, per pilot, or for Tejas squadrons, and Parliament Q&A archives could not be reached. What is public falls into five groups:
  1. **The IAF "flying task" mechanism.** MoD fixes a task per squadron in its "Policy Page". The audited shortfalls run 29–56 % for Su-30MKI, MiG-21 Bison and AWACS units, mainly because of low serviceability [DIRECT].
  2. **Whole-IAF flying volume.** The Standing Committee's accident-rate table implies about **2.4–2.6 lakh flying hours a year**, roughly constant from 1990 to 2018 [DIRECT data, INFERENCE].
  3. **Exercise surge.** In Gagan Shakti 2018 the IAF flew **>11,000 sorties (≈9,000 by fighters) in 15 days**, with 80 % aircraft serviceability. **Tejas generated 6 sorties per aircraft per day with 8 aircraft** [DIRECT; Tejas rate via ANI].
  4. **Tejas development flying.** CAG and ADA give per-aircraft data: **average sortie 30–51 min** (fleet mean ≈38 min) and **1–5 sorties per month** to IOC. In FY 2018-19 the developmental fleet averaged ≈40 min per sortie and 49–123 sorties per aircraft per year [DIRECT, test flying, not squadron usage].
  5. **Basing and status.** There are two operational Tejas Mk1 squadrons (No. 45 and No. 18) against 31 active fighter squadrons (42 authorised). As of 15 May 2026 HAL had **delivered no Mk1A**; it targets about 20 in FY 2026-27 [DIRECT].
- **Western/Nordic peacetime transfer anchors:** Finnish F/A-18 ≈130–150 FH per aircraft per year with ≈52-min sorties (BOS2); RAAF F/A-18 ≈1.2 FH per flight; USAF fighter pilots ≈16 h per month (search excerpt) [TRANSFER].

### Cited Findings

**IAF flying-task mechanism and audited shortfalls**
- [DIRECT] "Flying task for each type of aircraft is fixed by the Ministry and prescribed in the policy pages of the squadrons." The prescribed serviceability norm is 75 %. Source: [CAG Report No. 38 of 2015 (Air Force), §2 (Su-30 'C' and MiG-21 Bison 'D' paras), pp. ~61–62, 75](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf).
- [DIRECT] **Su-30MKI ('C'), six operating units.** MoD-allotted task against hours achieved (Table 2.8, same CAG report):

  | Year | Task (h) | Achieved (h) | Shortfall |
  |---|---|---|---|
  | 2004-05 | 2,400 | 1,373:55 | 42.77 % |
  | 2005-06 | 3,840 | 2,644:57 | 31.13 % |
  | 2006-07 | 5,520 | 3,149:30 | 42.95 % |
  | 2007-08 | 8,640 | 5,032:30 | 41.76 % |
  | 2008-09 | 12,960 | "7381:70" (sic) | 43.05 % |

  Serviceability was 55.50–59.73 % and AOG 10.90–15.32 % (2006–10). A squadron stated that "non availability of serviceable aircraft was the main reason". Source: same CAG report, Table 2.8.
- [DIRECT] **MiG-21 Bison ('D').** The Government task was 12,698–13,631 h per year (2004-05 to 2008-09). Air HQ revised it to 5,000–5,292 h. Hours achieved were 5,626–9,533, a shortfall of 29.09–55.70 % against the Government task. Serviceability was 41.32–51.52 %. The task "was due to reasons that actual strength of aircraft at the squadrons during the particular year was taken into account" (footnote 95). Source: [CAG 38/2015, Table 2.9, p. 75](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf).
- [DIRECT] **AWACS ('AA', 3 aircraft).** The Policy Page (June 2007) set 1,500 FH per year, i.e. about 500 h per aircraft. The planned task was 844–1,088 h and the achieved 766–926 h, a 43 % average shortfall. The plan assumed 75 % availability against an actual ≈66 %. Air HQ blamed "un-serviceability of any one or more sub-systems … just prior to mission launch, non-availability of participant force and the environmental factors such as bad weather, bird activity". Source: [CAG 38/2015, §2.1.2.1, Table 2.1, pp. 11–12](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf).
- [DIRECT] **Whole-IAF accident rates per 10,000 FH, by five-year block.** "Accident rate = (No. of Accidents x 10,000)/ Flying Hours". Source: [Standing Committee on Defence, 47th Report (16th LS, 2018-19), action-taken annexure on accidents](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_47.pdf?source=loksabhadocs) (local copy `indian_fleet/ls_committee/LS16_Defence_47.txt`, lines 1888–1901).

  | Block | Accidents per year | Rate |
  |---|---|---|
  | 1990-95 | 27 | 1.07 |
  | 1995-00 | 25 | 0.95 |
  | 2000-05 | 22 | 0.93 |
  | 2005-10 | 12 | 0.49 |
  | 2010-15 | 10 | 0.41 |
  | 2015-18 | 7.33 | 0.28 |

- [DIRECT] Further accident-rate statements:
  - FY 2015-16 rate 0.22, "one of the lowest … in the history of IAF" — [16th LS 25th Report](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_25.pdf?source=loksabhadocs) (local `LS16_Defence_25.txt` l. 3716).
  - FY 2020-21 accident rate "the lowest in last 50 years"; average accidents per year fell from 13 (11th Plan) to 8 (12th Plan) to 6 (13th Plan) — [17th LS 27th Report, §2.17](https://sansad.in/getFile/lsscommittee/Defence/17_Defence_27.pdf?source=loksabhadocs).
  - IAF witness (2011): "for the modern air forces the accident rate is generally around 0.35 and in the last financial year, we were 0.47 … per 10,000 hours" — [15th LS 12th Report, §4.26](https://sansad.in/getFile/lsscommittee/Defence/15_Defence_12.pdf?source=loksabhadocs).
- [DIRECT] **Force structure:**
  - "authorized strength of the IAF is 42 fighter squadrons, however, as on date it has 31 active fighter squadrons."
  - "IAF has received and operationalized two squadrons of Tejas Mk1 ac. The aircraft is being employed for operational roles and participated in … Tarang Shakti."
  - "With these acquisitions, IAF will have 220 LCA Mk-I & Mk-IA ac." (83 Mk1A contracted on 25 Jan 2021; AoN for 97 more on 15 Jan 2024.) Mk1A delivery was "delayed due to Design and Development (D&D) activities and delivery of GE-404 engines".
  - Sources: [18th LS 12th Report (2024-25), Recommendation para 17 and §(h), ≈pp. 20–22](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_12.pdf?source=loksabhadocs); [18th LS 2nd Report, §2.21–2.22, ≈pp. 29–30](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs).
- [DIRECT] **Pilots and night operations:**
  - The sanctioned fighter pilot-to-cockpit ratio is printed as "1:25". This is almost certainly 1:1.25, consistent with secondary reports of "authorised 1:1.25". The current ratio is "of sensitive nature" — [16th LS 47th Report, "Pilot-Cockpit Ratio" (rec. 70)](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_47.pdf?source=loksabhadocs).
  - "Indian Air Force has 52 operational Air Force bases. All can undertake military operational night landing." 48 have Cat II lighting; Leh, Thoise and Barrackpore use mobile lighting or flares — [18th LS 2nd Report, §2.31, ≈p. 33](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs).
- [DIRECT, secondary] **Pilot numbers (no flying hours found):**
  - A 2013 Lok Sabha answer gave pilot strength as 3,410 against 3,925 sanctioned (1 Mar 2013), with ≈440 pilots to be inducted per year. This was seen only as a search excerpt of an eparlib PDF; the archive was not reachable.
  - CAG Report No. 15 of 2024 (pilot training, 2016–21): shortfall grew from 486 (Feb 2015) to ≈596; initial intake 158–204 against 222 planned — [CAG press release (search excerpt)](https://cag.gov.in/uploads/PressRelease/PR-English-Press-Release-on-Audit-Report-No-15-of-2024-0676195177db573-54646160.pdf); [Tribune explainer](https://www.tribuneindia.com/news/india/explainer-what-are-shortcomings-in-training-of-iaf-pilots-that-cag-flagged).
  - None of these gives flying hours per pilot.

**Exercise surge rates**
- [DIRECT] Gagan Shakti 2018 (8–22 Apr 2018; two phases with a 48-h inter-phase redeployment):
  - "more than 11000 sorties were flown, which include approx 9000 sorties by fighter aircraft."
  - "Fighter aircraft undertook surge operations i.e. generating maximum number of sorties in a 24 hours cycle."
  - "IAF was able to achieve 80% serviceability of aircraft while radars and surface to air guided weapons maintained a serviceability of 97% … a dispatch rate of more than 95% for the Combat Assets."
  - "The efficacy and integration of indigenous LCA aircraft … was also checked out."
  - Source: [PIB, "Conclusion of Exercise Gaganshakti-2018", 24 Apr 2018](https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=178885).
- [DIRECT, secondary — ANI quoting an unnamed IAF official] "We were able to generate six sorties per platform per day. In this exercise, we had deployed eight platforms." "On the first day, six of Tejas jets reported 'snag' … we were able to get those rectified soon." The article dates the exercise 8–21 Apr; PIB gives 8–22 Apr. Source: [Business Standard/ANI, 25 Apr 2018](https://www.business-standard.com/article/news-ani/india-made-tejas-acquits-itself-well-at-gagan-shakti-18-118042500151_1.html).
- [DIRECT] Exercises with Tejas:
  - Desert Flag VIII (UAE, 27 Feb–17 Mar 2023) was Tejas's first exercise abroad, with 5 Tejas and 2 C-17 (search excerpt of PIB 25 Feb 2023, via [globalsecurity mirror](https://www.globalsecurity.org/wmd/library/news/india/2023/india-230225-india-pib01.htm)).
  - Tejas was displayed at LIMA-2019, Dubai 2021, Singapore 2022 and Aero India 2017–23 — [PIB, "LCA Tejas completes seven years of service", 30 Jun 2023](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1936373).
  - No sortie counts were found for Tarang Shakti 2024 (Sulur), Gagan Shakti 2024 or Vayu Shakti 2024 (searched).

**Tejas development-fleet sortie statistics (the only Tejas per-aircraft usage numbers in the public domain)**
- [DIRECT] **First flight to IOC (CAG Annexure-III):** 13 aircraft, **2,441 sorties, 1,560.80 h**. Per aircraft:
  - minimum sortie duration 5–16 min
  - maximum 50–112 min
  - average 30–51 min (TD-1 34, TD-2 30, PV-1 40, PV-3 36, LSP-3 47, LSP-5 46, LSP-8 51 min)
  - sorties per month 1–5, against the "minimum of 22 sorties per month desired by ADA"
  - aircraft flown on 2,279 of 21,170 aircraft-days available
  - Source: [CAG Report No. 17 of 2015 (LCA), §4.2.2 and Annexure-III, p. 63](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf).
- [DIRECT] **FY 2018-19 developmental flying (ADA):**
  - "524 sorties were flown on Tejas during 2018-19 FY, of which 401 sorties were on the fighter and 123 sorties on the Trainer"; "overall average of about 45 sorties a month".
  - "In April 2018 and November 2018, over 75 sorties a month was achieved … over 85 sorties were flown in Jaisalmer in Nov/Dec 2018."
  - Per-aircraft sorties/hours for the year: PV-5 49/32, PV-6 74/37, LSP-2 2/0:33, LSP-3 123/75, LSP-4 66/34, LSP-5 72/63, LSP-7 78/54, LSP-8 60/53.
  - Cumulative to 31 Mar 2019: PV-5 246/130, PV-6 225/139, LSP-1 74/40, LSP-2 319/196, LSP-3 491/319, LSP-4 424/280, LSP-5 459/380, LSP-7 354/269, LSP-8 282/211.
  - Source: [ADA Annual Report 2018-19, §7.2 flying summary and aircraft status, pp. 16–17](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) (local OCR `indian_fleet/ada/ADA_AR_2018-19_ocr.txt` l. 799–815, 1478–1660).
- [DIRECT] Other ADA fleet totals:
  - FY 2017-18: "A total of 444 developmental sorties were flown, 355 on the Fighter and 89 on the Trainer" — [ADA AR 2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf).
  - FY 2019-20: 233 sorties (OCR of the fighter/trainer split is garbled) — [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf).
  - FY 2020-21: "A total of 222 developmental test sorties" — [ADA AR 2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf).
  - PV-5 was "handed over to air force station Sulur for pilot training purposes from Oct 2020" — [ADA AR 2020-21, 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf).
- [DIRECT, naval LCA prototype] Turnaround with hot refuelling:
  - NP2 "flew a total of 38 sorties (including 20 hot refueling) … in a span of 19 days".
  - "Ski Jump Take-offs: 05. All of these were achieved in a single day with hot refueling."
  - Taxi-in engagements were run at 50, 80 and 105 kt.
  - NP1/NP2 together completed "152 flights/ 198 sorties (with hot refuelling)".
  - Source: [ADA AR 2018-19, §10 LCA Navy, ≈pp. 30–32](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf).
- [DIRECT, secondary] Air Force LCA hot refuelling (LSP-8, HAL Bengaluru, 26 Feb 2018): "performance … in-line with design requirements"; HAL claimed it cuts refuelling time "by half". No minute-level turnaround figure was published — [airrecognition.com](https://airrecognition.com/index.php/news/defense-aviation-news/global-news-2018/february/4115-india-successful-hot-refueling-trial-of-light-combat-aircraft-tejas.html) (search excerpt).

**Basing, Mk1A status, climate of Tejas bases**
- [DIRECT] Squadrons:
  - No. 45 "Flying Daggers" was the first Tejas squadron (1 Jul 2016). "In May 2020, No 18 Squadron became the second IAF unit to operate the Tejas" — [PIB, 30 Jun 2023](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1936373).
  - No. 45 Sqn moved to Sulur on 1 Jul 2018 (search excerpt, globalsecurity).
  - No. 18 Sqn was re-raised at Sulur on 1 Apr 2020 and later moved to Naliya — [Wikipedia: No. 18 Squadron](https://en.wikipedia.org/wiki/No._18_Squadron_IAF) (secondary). Bharat-Rakshak still lists Sulur — **conflict on the current base; unresolved**.
- [DIRECT] Mk1A status (HAL CMD, 15 May 2026):
  - "we have 6 engines received from GE now, and all these aircraft are flying. There are few tests still undergoing … hopeful that by August or September, we should be able to start the delivery."
  - "We are planning to deliver around 20 LCA … this financial year."
  - LCA inventory ≈₹7,500 crore; "more than 20-plus aircraft are already produced … engine ground run has also happened."
  - Source: [HAL earnings-call transcript, 15 May 2026, pp. 4–6, 9](https://hal-india.co.in/backend/wp-content/uploads/2026/05/Transcript_May15-2026-signed.pdf).
  - A secondary report (Jul 2026) says seven IN20 engines had been received and targets the first complete Mk1A squadron by March 2027 — [indiandefensenews](https://www.indiandefensenews.in/2026/07/india-targets-march-2027-for-first.html). **Conflict: 6 vs 7 engines; whether any Mk1A was delivered by Oct 2026 is unconfirmed.**
  - The Nashik third line (8 Mk1A per year) was inaugurated on 17 Oct 2025 ([PIB PRID 2180339](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2180339), search excerpt; capacity confirmed in the HAL transcript p. 3).
- [DIRECT, secondary — conflicting] First Mk1A unit:
  - 2025 reports: No. 3 Sqn "Cobras", reactivated at Sulur temporarily before moving to Nal (Bikaner) — [Scramble](https://www.scramble.nl/military-news/indian-air-force-to-raise-three-tejas-lca-mk1a-squadrons-by-late-2026); [idrw](https://idrw.org/iaf-reactivates-sulur-air-force-station-to-host-no-3-cobras-squadron-with-tejas-mk1a-jets/).
  - A later idrw report names No. 18 Sqn at Nal.
  - No official IAF statement was found.
- [DIRECT] Climate of Tejas bases. IMD 1991–2020 monthly mean number of days, from the station "Weather Phenomena" pages ([IMD Climatological Tables 1991–2020](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf); PDF pp. Coimbatore 225–226, Naliya 569–570, Bikaner 173–174, Jaisalmer 367–368, Jodhpur 387–388). Rain days are days with ≥0.3 mm precipitation; monthly values are rounded.

  | Station (for base) | Rain days / yr (peak months) | Thunder days / yr (peak) | Fog days / yr (peak) | Dust-storm days / yr (peak) |
  |---|---|---|---|---|
  | Coimbatore (Sulur, 45/18 Sqn; Mk1A interim) | 68.5 (Oct 11.6, Nov 10.5, Jul 8.0) | 45.6 (May 9.2, Oct 9.2, Apr 7.6) | 6.5 (Nov 2.0) | ≈0.9 |
  | Naliya (18 Sqn) | ≈27 (Jul 9.2, Aug 8.8) | ≈4 (Sep 1.3) | 14.9 (Mar 3.7, Feb 3.2, Oct 2.2) | ≈0.1 |
  | Bikaner (Nal; Mk1A) | ≈29 (Jul 6.6, Aug 5.7) | ≈25 (Aug 5.1, Jul 4.9, May 3.8) | ≈6 (Jan 2.7, Dec 2.1) | 7.6 (Jun 2.4, May 1.9) |
  | Jaisalmer (Pokhran ranges) | ≈17 (Aug 4.0) | ≈18 (Jul 3.9) | ≈3 | ≈8 (Jun 2.6) |
  | Jodhpur | ≈32 (Jul 9.0) | ≈23 (Jul 5.7) | ≈1 | 4.1 (Jun 1.5) |

  Temperature and pressure anchors for these stations (May 1200 UTC dry-bulb: Bikaner 40.7 °C at 974.3 hPa, Naliya 32.6 °C at 1,001.9 hPa, Coimbatore 31.3 °C at 960.9 hPa) are already in `flight_profiles_and_usage.md` Q6.

**Transfer anchors for per-aircraft and per-pilot hours, sortie length and sorties per day**
- [TRANSFER: Finnish AF F/A-18C/D; peacetime Nordic usage]
  - Fleet hours: "approximately 72 000 FH" (2007 review), "108 000 FH" (2011), "140 000 FH" (2015), "158 000 FH" (2017) and "approx. 213 000 FH" (2023).
  - Fleet size: 64 aircraft (2010), 62 (2014).
  - Representative spectrum BOS2: "161 selected flights … resulting a total of 140 FH".
  - Usage "noticeably more severe than the last five year's usage".
  - Sources: [ICAF Finland Review 2007](https://sarjaweb.vtt.fi/julkaisut/muut/2007/ICAF_FinlandReview_2007.pdf); [2011](https://publications.vtt.fi/julkaisut/muut/2011/ICAF_Doc2427_FinlandReview_2011.pdf); [2015](https://sarjaweb.vtt.fi/julkaisut/muut/2015/ICAF_Doc_No_2432_FinlandReview_2015_issue_1_21May15.pdf); [2017, §2.2.5, pp. 23–24](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf); [VTT-CR-00252-23 (2023)](https://sarjaweb.vtt.fi/julkaisut/muut/2023/VTT-CR-00252-23.pdf).
- [TRANSFER: RAAF F/A-18A/B] "nearly 250,000 flights have been flown … giving a total duration of over 300,000 flying hours"; fleet of 75 aircraft — [White, Molent et al., HUMS 2015, p. 1](https://www.humsconference.com.au/Papers2015/Non_peer_Reviewed/White01.pdf).
- [TRANSFER: USAF; search excerpts only, GAO PDFs not parsed here]
  - USAF fighter pilots flew "about 16 hours per month" (testimony cited in [GAO-18-113](https://www.gao.gov/products/gao-18-113)).
  - F-15E experienced aircrews need 96 live sorties per year (8 per month) and inexperienced 108; simulator time is capped at 20 % of hours ([GAO-16-864](https://www.gao.gov/assets/gao-16-864.pdf)).
  - The Air Force estimated fighter pilots averaged about 200 h per year in FY2015 ([GAO-17-53](https://www.gao.gov/assets/gao-17-53.pdf)).
  - These need verification against the PDFs.
- [TRANSFER: USAF engine-emissions planning default] Default military-combat landing-and-take-off time-in-mode (USAF):

  | Taxi/idle-out | Take-off | Climb-out | Approach | Taxi/idle-in | Total |
  |---|---|---|---|---|---|
  | 18.5 min | 0.4 min | 0.8 min | 3.5 min | 11.3 min | 34.5 min |

  The USN figure is 15.5 min total. Source: [USAF Air Emissions Guide for Air Force Mobile Sources (AFCEC, 2013), Table 2-4, p. 24](https://archive.org/details/DTIC_ADA577276) (DTIC ADA577276, "Approved for public release, distribution unlimited").

### Inferences
- [INFERENCE] **Whole-IAF flying volume.** Accidents per year × 10,000 ÷ rate gives:

  | Block | FH per year |
  |---|---|
  | 1990-95 | ≈252,000 |
  | 1995-00 | ≈263,000 |
  | 2000-05 | ≈237,000 |
  | 2005-10 | ≈245,000 |
  | 2010-15 | ≈244,000 |
  | 2015-18 | ≈262,000 |

  The IAF therefore flies a roughly constant **≈2.4–2.6 lakh FH per year** across all types. Uncertainty is ±10 % from rounding of the published rates and averages. Dividing by an assumed ≈3,800–3,900 pilots (secondary 2023 figure 3,834; not verified) gives a fleet-wide average of about 60–70 FH per pilot per year, all types and all pilot appointments combined. That figure is **not** a fighter-squadron pilot rate [ASSUMPTION; validate with a Parliament answer or CAG pilot-training report].
- [INFERENCE] **Tejas sortie-length model.**
  - The development data (fleet mean ≈38 min to IOC; ≈40 min in FY 2018-19; per-aircraft averages 30–53 min; extremes 5–112 min) describe *test* sorties, which are short by design.
  - Squadron sorties are plausibly longer: FINAF BOS2 ≈52 min, RAAF ≈72 min, Gripen median ≈74 min (sibling).
  - For a Tejas Mk1A squadron, use a lognormal with **median ≈45–55 min, 5th–95th percentile ≈25–90 min** without drop tanks, shifted up by ≈15–30 min with drop tanks or AAR [ASSUMPTION; validate against squadron authorisation books].
- [INFERENCE] **Exercise surge.** Tejas 6 sorties per aircraft per day (Gagan Shakti 2018) against ≈1 sortie per flying day in development (CAG: 2,441 sorties on 2,279 flown aircraft-days). This gives a defensible range for a sorties-per-aircraft-per-day scenario parameter: **peacetime ≈1–2, surge ≈4–6**. The naval prototype's 5 ski-jump sorties in one day with hot refuelling supports the upper end.
- [INFERENCE] **Flying-task model.** The CAG data show IAF fighter fleets **typically achieve ≈45–70 % of the MoD task** (Su-30MKI 57–69 %; Bison 44–71 %), with shortfalls tied to serviceability. A virtual squadron should therefore generate planned sorties from a task, then cancel or abort a fraction driven by simulated serviceability, weather and bird activity. That is the IAF's own causal chain.
- [INFERENCE] **Seasonal pattern** (climate-driven, not IAF-published):
  - Sulur: thunderstorm and rain peaks in Apr–May and Oct–Nov (NE monsoon).
  - Naliya: winter-morning fog peak in Feb–Mar plus SW-monsoon rain in Jul–Aug.
  - Bikaner/Nal: dust storms in May–Jun, monsoon thunder in Jul–Aug, fog in Dec–Jan.
  - A daily "weather-cancel" probability can be drawn from these monthly day counts [ASSUMPTION].
- [ASSUMPTION] **Night flying fraction.** No IAF figure exists. All 52 operational bases are night-capable, and ADA records night weapon delivery, night HMDS and night conversion/dual checks. Set night sorties at ≈10–20 % of squadron sorties, higher in winter (longer nights) and for operational squadrons. Validate with the squadron flying-order book or the IAF Flight Safety Directorate.

### Gaps
- **No officially released figure** for IAF flying hours per fighter aircraft or per fighter pilot per year, Tejas squadron sortie counts, Tejas squadron mission mix, or Tejas squadron serviceability. Parliament Q&A (eparlib/rsdebate) was unreachable, and the CAG 15/2024 full text could not be downloaded. Next step: retrieve the CAG 15/2024 full report and Rajya/Lok Sabha answers on "flying task", "flying hours", "Tejas serviceability" from a browser session.
- No sortie or serviceability statistics were published for Tarang Shakti 2024, Gagan Shakti 2024, Vayu Shakti 2024, Garuda or Desert Flag Tejas participation.
- Fleet sizes needed to convert the CAG Su-30 and Bison tasks into per-aircraft hours are not in the report.

---

## Q2. Tejas-specific phase values from officially released sources (start, idle, take-off, landing, approach, chute, turnaround)

### Takeaway
Officially released Tejas phase numbers remain sparse:
- **Brake chute** (MoD DDP): 17 m², deploy ≤ 285 km/h normal / 340 km/h emergency.
- **Naval LCA landing gear:** drop-tested to 7.1 m/s sink rate; structure cleared to 5.8 m/s; flight-tested to 3.7–3.9 m/s.
- **Air-to-air refuelling** (NFTC/ADA): closure velocities of 1.7–4.3 kt measured, against a 10 kt design maximum.
- **Taxi-in engagements:** 50/80/105 kt.
- **Hot refuelling and turnaround:** demonstrated (up to 5 sorties per day), but no minute figure.
- **JFS start facts** (GTSU-110; −15 °C triple start) and the IN20 330 h AMT ≈ 1,000 FH equivalence (in sibling notes).

No official take-off/landing distance, rotation or approach speed, approach AoA, climb schedule or IN20 idle/MIL band was found. Physics-based estimates from `tejas_airframe_aero_fcs.md` (lift-off ≈290–325 km/h at 9.8 t; approach ≈260–285 km/h) remain the working values.

### Cited Findings
- [DIRECT] Brake parachute (hybrid, ADRDE design): 17 m²; normal deploy speed up to 285 km/h (≈154 kt); emergency up to 340 km/h (≈184 kt) — [MoD DDP product page](https://www.ddpmod.gov.in/hi/node/8027) (as extracted in `tejas_airframe_aero_fcs.md` Q6).
- [DIRECT, naval prototypes] Landing gear and sink rates:
  - "Main and Nose Landing Gears has successfully completed drop test upto 7.1 m/s sink rate. High Sink Rate landing up to 3.9 m/sec sink rates was carried out."
  - "Structural clearance for higher sink rate (5.8 m/s) has been obtained … Higher sink rate landing tests upto 3.7 m/s were carried out at SBTF."
  - "566 Field Carrier Landing Practices (FCLPs) and 205 High sink rate landings … 77 Taxi in Engagement" (to 2019-20).
  - Navy Mk2: "increase of around 2.5 tons Carrier landing mass … by reduction in approach speed", with Automatic Alpha Hold Control (AAHC) and Direct Lift Control.
  - Sources: [ADA AR 2018-19, §10.1.2, §10.2](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf); [ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf).
- [DIRECT — platform anonymised as "a prototype fighter platform" by NFTC/ADA authors; almost certainly Tejas] Air-to-air refuelling closure velocity:
  - Probe–drogue closure velocities across 12 contacts were 1.71–4.3 kt (video). GPS cross-check agreed within −2.9 % to +3.2 %.
  - The design maximum used was "maximum value of closure rate (10 knot) for impact load of 100 lbs" (ARSAG).
  - "Pilot A was closing in faster compared to Pilot B … attributed to the pilot's experience on AAR and the previously flown aircraft types."
  - Source: [Arunachaleswaran et al., Def. Sci. J. 70(2):140–144 (2020), Table 1](https://www.publicationsdrdo.in/index.php/dsj) (DOI 10.14429/dsj.70.14100; local `tejas_airframe/DSJ_14100.txt`).
- [DIRECT] Advanced ski-jump mode tested "with commanded AOA ranging from 18-22 deg" (naval LCA) — [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf).
- [DIRECT] Air Force Tejas flight-test items with no numbers released:
  - "evaluating a new landing technique while approaching at a higher angle of attack" (LSP-5)
  - "new take-off technique" (LSP-7)
  - cross-wind take-off and landing "in cross winds between 15–20 knots"
  - "Reject take off High speed Taxi trials"
  - "fuel assessment during steep climb pitch up with fuel remaining less than 1200 ltr"
  - Sources: [ADA AR 2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf), [2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf), [2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf), [2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf).
- [DIRECT] GTSU-110 JFS facts, the CAG/HAL cold-start record (three consecutive starts at −15 °C after 18–42 h cold soak) and the GE "330 h AMT ≈ 1,000 flight hours" for the IN20 are already cited in `f404_in20_engine_model.md` Q1/Q7 ([GE press release, 20 Jun 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight)).
- [DIRECT, secondary] First Tejas loss (12 Mar 2024, near Jaisalmer, "during an operational training sortie"): the IAF constituted a Court of Inquiry. Anonymous officials attributed it to "engine seizure … caused by an oil pump malfunction"; an idrw source claim instead blames inadequate oil level. **Unresolved; no CoI outcome published.** Sources: [AIR news](https://www.newsonair.gov.in/iafs-tejas-aircraft-crashes-near-rajasthans-jaisalmer-pilot-ejected-safely); [indiandefensenews](https://www.indiandefensenews.in/2024/07/engine-seizure-led-to-iafs-first-tejas.html); [idrw](https://idrw.org/scoop-iaf-tejas-crash-oil-level-issue-points-to-potential-oversight-lapses/).

### Inferences
- [INFERENCE] Chute deployment logic for the virtual Tejas:
  - Deploy at touchdown when groundspeed ≤ 154 kt (285 km/h).
  - Allow ≤ 184 kt in emergency. Above 184 kt, model canopy failure or separation as a fault.
  - Chute life of 45 streamings / 8 years (sibling utility note) gives a maintenance counter.
- [INFERENCE] Air Force Tejas design sink rate is not public. The naval data bound it: Air Force LCA ≤ naval 5.8 m/s structural clearance. The MIL-A-8866C field-landing distribution (mode 3–4 ft/s ≈ 0.9–1.2 m/s; 0.5 per 1,000 at 10 ft/s ≈ 3.0 m/s; sibling Q1-K) is the defensible synthetic distribution [TRANSFER].
- [INFERENCE] AAR closure velocity should be drawn per pilot, e.g. a pilot-specific mean of 2–3.5 kt with SD ≈0.7 kt, truncated at 10 kt. The NFTC data show a clear pilot effect. This is a useful "pilot technique" latent variable.

### Gaps
- **Not found (officially released):** Tejas take-off and landing distances, rotation and lift-off speeds, approach speed and AoA, touchdown speed, climb schedule, IN20 idle/MIL N2/EGT/fuel-flow bands, oil-pressure bands, start EGT limit, JFS start timeline, turnaround minutes, and Air Force LCA design sink rate.
- No Defence Science Journal / JoAST paper found reports these for the Air Force Tejas. The ADA Operational Data Manual is not public.

---

## Q3. Officially released replacements for flight-phase values taken from restricted manuals (F/A-18 NATOPS; Hellenic AF F-16 manual)

### Takeaway
The best new released anchors, all approved for public release (USAF, USN, NASA, AGARD, NLR, DSJ, MoD DDP), are:
- **A USAF test-cell operating table for the F404-GE-400/F1D2.**
  - Idle: fuel flow 685 lb/h, N2 10,960 rpm (≈65 %), N1 5,159 rpm, 632 lbf.
  - MIL: fuel flow 7,739 lb/h, N2 15,994 rpm (≈95 %), N1 13,167 rpm, 9,608 lbf.
  - Mid-AB: 15,851 lb/h, 12,034 lbf.
  - These **replace the NATOPS idle and MIL fuel-flow bands and give single-point N2 values.**
- **USAF fuel flows for the F110-GE-129 and F100-PW-229 by mode.**
- **USAF AIB reports** for F-16 approach and touchdown speeds (150/138 kt at 22,288 lb), aerobraking attitude (10.5°), idle rpm (~70–80 %) and the 60 % stagnation rule.
- **NASA TP-1538** (F-16 AoA limiter ≈25°; roll-rate restriction above 13° AoA) and **AGARD R-815** (F-16 9 g alpha-g limiter).
- **NADC measured F-18 carrier approach-speed regression** (1.5 kt per 1,000 lb).
- **MoD DDP Tejas brake-chute speeds.**

**Not replaced:** the F404 start EGT limit (815 °C), F404 oil-pressure bands (idle and MIL), the -402 MIL EGT limit (880 °C), the F404 thermal-soak restart rule, the F/A-18 on-speed 8.1° AoA, the F-16 11–13° approach AoA, the F-16 drag-chute speed band, F-16 start FTIT limits and JFS timings, and most F/A-18 take-off, pattern and roll-out specifics.

### Cited Findings
**F404 engine (replaces NATOPS bands)**
- [TRANSFER: F404-GE-400 / F1D2, USAF test cell or hush house, JP-8; the closest released F404 operating points; IN20 is a -402-derived, ≈7 % higher-thrust variant] "Table 4-71 Engine Operating Parameter Summary, F404-GE-F1D2/400 (F-117A & F/A-18C/D)":

  | Parameter | Idle | Approach | Intermediate | Military | AB (zone 3) |
  |---|---|---|---|---|---|
  | Barometric pressure (inHg) | 26.81 | 27.77 | 26.92 | 27.76 | 27.35 |
  | Fuel flow (lb/h) | 685 | 3,111 | 6,464 | 7,739 | 15,851 |
  | Fan speed N1 (rpm) | 5,159 | 10,492 | 12,486 | 13,167 | 13,109 |
  | Core speed N2 (rpm) | 10,960 | 14,176 | 15,414 | 15,994 | 15,876 |
  | Average thrust (lbf) | 632 | 4,057 | 8,305 | 9,608 | 12,034 |
  | % maximum thrust | 6 | 38 | 79 | 91 | 114 |

  All other engines were tested at AB zone 1; the F404 was tested at zone 3 (mid-AB). Source: [USAF IERA, "Aircraft Engine and Auxiliary Power Unit Emissions Testing, Vol. 3: Particulate Matter Results" (IERA-RS-BR-TR-1999-0006, Mar 1999), Table 4-71, PDF p. 184; §1.2 text on AB zones](https://archive.org/details/DTIC_ADA361473) (DTIC ADA361473, "Approved for public release; distribution unlimited").
- [TRANSFER: same data, USAF planning guide] The same F404 numbers appear in the 2013 guide. Note 16: "F404-GE-F1D2 is a non-afterburning version of the F404-GE-400 and uses the same emissions as the F404-GE-400". The guide adds F-18C/D = F404-GE-402. Source: [USAF Air Emissions Guide (2013), Table 2-8 p. ~39, notes p. 52, Table 2-5](https://archive.org/details/DTIC_ADA577276).
- [TRANSFER: F-16 engines, same guide, fuel flow in lb/h per engine with "% thrust"]

  | Engine | Idle | Approach | Intermediate | Military | Afterburner |
  |---|---|---|---|---|---|
  | F110-GE-129 | 961 (4 %) | 4,832 (45 %) | 6,939 (65 %) | 8,611 (76 %) | AB-1 15,564 (99 %) |
  | F100-PW-229 | 1,087 (5 %) | 3,098 (21 %) | 5,838 (49 %) | 11,490 (86 %) | AB-1 20,793 (102 %) |
  | F100-PW-220 | 1,084 (7 %) | 3,837 (30 %) | 5,770 (70 %) | 9,679 (100 %) | AB-5 41,682 |

  Source: [same guide, Table 2-8, pp. ~37–38](https://archive.org/details/DTIC_ADA577276).
- [TRANSFER: F404 percentage scale] 100 % N2 ≈ 280 Hz ≈ 16,800 rpm (DSTO); ARL design fan speed 13,270 rpm (sibling `f404_in20_engine_model.md`, citing [Frith 1985, DTIC ADA164562](https://archive.org/details/DTIC_ADA164562)).

**F-16 (replaces HAF manual values)**
- [TRANSFER: USAF F-16D Block 52, T/N 91-0466, Thunderbirds, 23 Jun 2017] Approach, touchdown and roll-out:
  - "a total MA weight of 22,288 pounds at landing … Computed approach and landing speeds … are 150 and 138 knots respectively."
  - "MP held the nose at a 10.5 degree nose high attitude to aerodynamically slow the MA … At approximately 110 knots, the MP lowered the nose and began maximum differential braking."
  - "landing at 163 knots [on a wet runway] requires between 7,000 feet and 8,100 feet to stop."
  - Source: USAF AIB report, F-16D 91-0466, Dayton OH (ACC; AFI 51-503), pp. 3–5 and Opinion; AF JAG AIB library [https://www.afjag.af.mil/AIB-Reports/](https://www.afjag.af.mil/AIB-Reports/) (local copy `research_sources/texture_fault_gaps/utility_degradation/AIB_2017_Dayton_F-16D.pdf`).
- [TRANSFER: USAF Block 52 F-16CJ 92-3890 (Pratt & Whitney engine; Block 52 = F100-PW-229), Thunderbird, 2 Jun 2016] "(~70 - ~80% RPM indicates idle thrust)". The mishap pilot had "selected idle position 40 times during the flight". The JFS was used to assist the airstart. Source: USAF AIB report (local `texture_fault_gaps/engine_faults/AIB_F-16CJ_92-3890_Thunderbird_cutoff_relight_2Jun2016.pdf`), pp. ~4–6.
- [TRANSFER: USAF F-16 (F100-PW-220), Holloman, 30 Apr 2024] "Engine RPMs decayed below sixty percent within five seconds … Once RPMs are below 60 percent, the engine is fully stagnated, and any attempted restarts are accomplished through a more time-demanding checklist procedure." Source: USAF AIB report (local `texture_fault_gaps/engine_faults/AIB_F-16_Holloman_30Apr2024.pdf`), p. ~4.
- [TRANSFER: F-16A design-era simulation, NASA] The control system attempts "to limit the angle of attack to below 25°". Roll rate is "restricted above α = 13°", so that "maximum commandable roll rate is only about 90°/sec at α = 25°". Source: [NASA TP-1538 (1979)](https://ntrs.nasa.gov/citations/19800005879) (local `airframe_data/NASA_TP-1538_F16_stall.pdf`).
- [TRANSFER: F-16, Lockheed Martin paper in an AGARD report] "An alpha-g limiting algorithm was incorporated into the flight control laws to effectively prevent the aircraft from exceeding 9g during symmetric flight. The limiter did not differentiate between symmetric and asymmetric maneuvers." Source: [Gibson, "Evolution of F-16 Loads and Requirements", AGARD-R-815 (Feb 1997), paper 12, p. 12-3](https://archive.org/details/DTIC_ADA324348) (UNCLASSIFIED/UNLIMITED).

**F/A-18 approach (partial replacement)**
- [TRANSFER: USN F/A-18 carrier landings, NADC film surveys]
  - "The AOA for an 'on speed' approach is indicated on the instrument" and is independent of weight. The value is not given.
  - Regression over **608 F-18 carrier landings**: Approach speed = **90.7 + 0.270 × (wind over deck, kt) + 0.001497 × (landing weight, lb)**.
  - "The typical increase in approach speed with landing weight on a NATOPS approach speed versus weight curve is two (2) knots per thousand pounds. Only the regression curve for the F-18 shows this typical NATOPS variation."
  - Carrier design sink speed (MIL-A-8863A): average = 0.128 × engaging speed (min 11.5 ft/s); SD = 0.015 × engaging speed + 1.667 (min 3.0).
  - Source: [Micklos, NADC-91027-60 (1 Sep 1991), pp. 2–11, regression table p. 10](https://archive.org/details/DTIC_ADA239511) ("Approved for Public Release; Distribution is Unlimited").
- [TRANSFER: RCAF CF-188, official flight-safety epilogue] An overhead break flown at "470 knots … 1500 ft above ground level … set the throttles to idle … bank angle to 81 degrees … pulled up to 6.8g". This was described as non-standard (higher airspeed for deconfliction). Source: [RCAF FSIR epilogue, CF188796 (20 Jun 2017)](https://www.canada.ca/en/air-force/corporate/reports-publications/flight-safety-investigation-reports/cf188796-hornet-epilogue.html).

**Tejas-specific replacements**
- [DIRECT] Brake-chute speeds: 285/340 km/h (Q2). [DIRECT-likely] AAR closure 1.7–4.3 kt measured, 10 kt maximum (Q2).

**Searched and not replaced**
- F404 start EGT limit; -402 MIL EGT limit; oil-pressure bands; thermal-soak restart rule. Searches: NASA/DTIC F404 papers, IERA tables (no EGT or oil columns), Spanish CIAIAM/CITAAM, Canadian FSIRs, Naval Safety Center "Approach", patents.
- F/A-18 8.1° on-speed AoA. Searches: NASA, NPS, NAVAIR "Magic Carpet" releases, NADC; the NADC report only says "on speed" without the number.
- F-16 11–13° AoA and drag-chute 90–170 kt. Searches: USAF AIBs, NSIA/Dutch Safety Board/Taiwan; none states them.

### Inferences
- [INFERENCE] Consistency checks with released data:
  - F404 idle N2 10,960 / 16,800 = **65.2 %**. MIL N2 15,994 / 16,800 = **95.2 %**; intermediate 91.8 %; approach 84.4 %.
  - N1: idle 38.9 %, MIL 99.2 % of 13,270 rpm.
  - MIL SFC = 7,739 / 9,608 = **0.805 lb/(lbf·h)**, consistent with the ARL -400 value of 0.78 (sibling).
  - Measured at ≈27.8 inHg (δ ≈ 0.93). Correct to sea-level static with Wf/(δ√θ) (sibling Q6) before use.
- [INFERENCE] For the IN20 (≈+5–10 % airflow and thrust over the -400/-402):
  - Scale the IERA MIL fuel flow to ≈8,300–8,600 lb/h at SLS MIL.
  - Keep idle fuel flow ≈650–750 lb/h, idle N2 ≈63–67 % and MIL N2 ≈94–97 %.
  - These are [TRANSFER + ASSUMPTION] anchors fully traceable to released sources.
- [INFERENCE] Hot-day temperature-limiting example. Replace the NATOPS -402 880 °C limit in `flight_profiles_and_usage.md` Q6 with the released -400 "T5C steady-state limit 830 °C" (NASA TM-101702 Fig. 6, sibling) as the limiter value. The qualitative conclusion is unchanged: a Jodhpur May afternoon makes the engine temperature-limited at MIL.
- [INFERENCE] F-16 approach and touchdown speeds:
  - About 150/138 kt at ≈22,300 lb is consistent with an 11–13° AoA approach.
  - Synthesise approach speed as V_app(W) ∝ √W through this point; touchdown ≈ V_app − 12 kt [ASSUMPTION].
  - For F/A-18 analogues, use the NADC weight slope (1.5 kt per 1,000 lb measured; 2 kt per 1,000 lb NATOPS-typical as reported by NADC) instead of the restricted "+2.5 kt per 1,000 lb".

### Gaps
- Not replaced (no officially released source found):
  - F404 start EGT limit (815 °C)
  - idle and MIL oil pressure bands and the 180 psi start peak
  - -402 MIL EGT limit (880 °C)
  - thermal-soak restart rule (motor 1 min at 24 % N2 if restarted 15 min–4 h after an uncooled shutdown)
  - F/A-18 8.1° on-speed AoA and ~125 kt at 2,000 lb fuel
  - F-16 11/13° final AoA and 13° touchdown limit
  - F-16 drag-chute 90–170 kt band
  - F-16 start FTIT limits (800/935 °C) and JFS motoring limits
  - FLCS BIT ≈45 s; INS alignment, HMD and OBOGS warm-up timings
  - FUEL HOT 79 °C
  - taxi, take-off trim, rotation and tyre-speed limits
  - climb schedules; F/A-18 cruise AoA (4.2°/5.6°)
- These should be generated from physics or [ASSUMPTION] and labelled as such, or obtained from HAL/IAF under the problem-statement mentoring channel.

---

## Q4. Structural usage spectra: Nz exceedances per 1,000 h, roll-rate statistics, landing sink rates, Tejas/IAF fatigue monitoring

### Takeaway
New released quantitative spectra:
1. **F-16 air-defence operational Nz exceedances per 1,000 h** from the flight-loads recorder, against MIL-spec and modified design spectra (AGARD R-815, Fig. 7). Operational usage is more severe than design in the 4–8.5 g mid-range "most significant for crack growth".
2. **Roll statistics:** rolling-manoeuvre peaks ≈ **13 % of positive Nz peaks**, equal left/right, independent of Nz level (ASD-TR-72-113, public).
3. **Fleet severity factors:** RNLAF F-16 Crack Severity Index 1.03 at home vs **0.31 on an out-of-area deployment**; Finnish and RAAF Hornet usage "more severe than design".
4. **Spectrum-construction conventions** (AFGROW DTDH) and **carrier sink-speed relations** (NADC/MIL-A-8863A).

**IAF/Tejas:** only the IAF's use of a g-exceedance Fatigue Index for the Hawk (Parliament) and ADA/HAL fatigue-test activity are public. No Tejas individual-aircraft-tracking data were found. MIL-A-8866B fighter tables and ASD-TR-82-5012 were not retrievable.

### Cited Findings
- [TRANSFER: USAF F-16A/B, 1990s air-defence operational data; the only modern fighter Nz exceedance curve found in a released source] Gibson (Lockheed Martin), AGARD-R-815 paper 12, Fig. 7 "Vertical Load Factor Exceedances for the F-16", p. 12-12 (PDF p. 136) — [archive.org DTIC ADA324348](https://archive.org/details/DTIC_ADA324348):
  - Text: "the maneuver environment of F-16 operational aircraft was significantly more severe than that predicted through use of military specification and F-4 data … Note the mid-range Nz levels where the operational data is significantly more severe than the design. It is this mid-range that is most significant for crack growth."
  - "For the Block 40 redesign, flight loads recorder data was used exclusively."
  - "two known occurrences of [wake-vortex] damage in over six million flight hours of F-16 operation."
  - Graph-read values, exceedance counts per 1,000 h (±25–30 %, log scale):

  | Nz (g) | F-16 air-defence operational | Original F-16A/B design (MIL spec, modified air-to-air) | F-16 design usage with MIL-spec exceedances |
  |---|---|---|---|
  | 2 | ≈34,000 (plateau ≈40,000 below ~1.6 g) | ≈50,000 | — |
  | 3 | ≈24,000 | ≈24,000 | ≈22,000 |
  | 4 | ≈12,000 | ≈11,000 | ≈7,000 |
  | 5 | ≈7,000 | ≈4,000 | ≈1,800 |
  | 6 | ≈3,600 | ≈1,500 | ≈450 |
  | 7 | ≈1,300 | ≈470 | ≈100 |
  | 7.5 | ≈700 | ≈260 | ≈50 |
  | 8 | ≈350–450 | ≈130 | ≈25 |
  | 8.5 | ≈70–90 | ≈60 | ≈12 |
  | 9 | ≈10 | ≈30 | ≈6 |
  | ≥9.2 | ≈2 (truncates) | ≈10 at 9.75 | ≈2.3 at 9.75 |

- [TRANSFER: 1950s–60s USAF fighters F-5A, F-105D, F-84F, F-102A; methodological and still the public basis cited in JSSG-2006] Rustenburg, "Development of a Rolling Maneuver Spectrum from Statistical Flight Loads Data", ASD-TR-72-113 (Apr 1973), pp. 2–6 — [archive.org DTIC AD0761491](https://archive.org/details/DTIC_AD0761491) ("approved for public release and sale; its distribution is unlimited"):
  - "the probability of encounter of a given rolling velocity is not significantly affected by the normal load factor magnitude."
  - Activity thresholds were Nz 2.0 g and ±30 °/s; a manoeuvre is "truly antisymmetric only when both the rolling velocity and load factor are outside their respective thresholds".
  - "percentage of roll peak occurrences in terms of the positive normal maneuver peak occurrences of (1137/9350) × 100 = 12.2 % for the F-5A and (278/1956) × 100 = 14.2 % for the F-105D … the use of an average value of 13 % is suggested." An F-84F cross-check gave 12.1 %.
  - "an equal number of rolls are performed in either direction."
  - A normalised pb/2V (wing-tip helix angle) exceedance curve "is proposed as the statistical model for the rolling maneuvers of any aircraft". The effect of airplane type is handled by de-normalising with the airplane's maximum pb/2V.
- [TRANSFER: RNLAF F-16, NLR] Crack Severity Index (CSI):
  - "a value of 1.0 means fatigue damage according to the reference usage … used to generate the current inspection schedule."
  - The CSI "takes into account interaction effects between large and small load cycles."
  - Fig. 3 "Exceedance spectra for different usages" gives **323 Sqn CSI 1.03; Goose Bay (low-level training detachment) CSI 1.04; Villafranca (out-of-area operations) CSI 0.31**.
  - Sample monitoring used 3–4 aircraft per squadron; a special programme recorded 10 bridges on 330 operational flights; the cassette was changed every 25 FH (1998) and later every 10 FH.
  - The FACE recorder samples MUX-BUS parameters (accelerations, rates) at up to 50 Hz, DEEC signals at up to 4 Hz, and strain at 1,000 Hz.
  - Sources: [NLR-TP-98172 (Spiekhout 1998), Fig. 3 p. 10](https://reports.nlr.nl/items/654cb62e-1a8f-489f-a987-e47b44d39317/full); [NLR-TP-2002-309 (te Winkel & Spiekhout), pp. 4–9](https://reports.nlr.nl/items/2e0c0e97-5401-4c29-af5a-badad9e47983/full) ("Distribution: Unlimited").
- [TRANSFER: Finnish AF F/A-18C/D]
  - "the aircraft usage is more severe than the design target. The FINAF has updated the target as 4500 FH and 0.75 FLE (simultaneously)" (2011).
  - 2015: "the aircraft usage seems less severe than the design target. However, when compared to other F-18 operators the usage is more severe" (after new OEM software lowered computed life consumption).
  - BOS2 checks used "Nz exceedances, flight time in Vertical Tail/Horizontal Tail/Trailing Edge Flap/Aileron buffet areas (time spent in a proper AoA-Q table bin) and Wing Root FLE Rate".
  - HOLM aircraft record "strain gages @640/1280 Hz, VT accelerometers @ 2560Hz, and all flight parameters @20 Hz".
  - Hawk tracking "relies on counting g level exceedances and calculating a usage index i.e., Fatigue Index (FI) by the variant specific equations on a flight-by-flight basis … current FI tracking does not take buffet loading into account."
  - Sources: [ICAF Finland 2011, §13.1.3, p. 13/8–9](https://publications.vtt.fi/julkaisut/muut/2011/ICAF_Doc2427_FinlandReview_2011.pdf); [2015, p. 13/8](https://sarjaweb.vtt.fi/julkaisut/muut/2015/ICAF_Doc_No_2432_FinlandReview_2015_issue_1_21May15.pdf); [2017, §2.2.5, pp. 23–24](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf); [VTT-CR-00252-23, §2.2.4](https://sarjaweb.vtt.fi/julkaisut/muut/2023/VTT-CR-00252-23.pdf).
- [TRANSFER: RAAF F/A-18A/B]
  - "the usage of the aircraft has … been found to be significantly different from both US Navy usage and the original design usage. It was found that the RAAF usage was typically more severe than the certification baseline."
  - MSDRS strain data feed the ASLMP fatigue tracking. The MSMP2 algorithm "over-predicted the damage due to the small load cycles", leading to MSMP3 (crack-growth based, adopted 2015).
  - Source: [White et al., HUMS 2015, pp. 1–5](https://www.humsconference.com.au/Papers2015/Non_peer_Reviewed/White01.pdf).
- [TRANSFER: USAF damage-tolerance practice] Spectrum construction conventions:
  - blocks of "five hundred or one thousand flight hours"
  - clipping at "10 exceedances per 1,000 flights"
  - truncation at "10^5 to 5 × 10^5 exceedances per 1,000 flights"
  - "8 to 10 positive levels … 4 to 10 negative levels"
  - "Current fighter aircraft practice uses 0.5 g intervals"
  - Source: [AFGROW Damage Tolerant Design Handbook §5.4.2](https://afgrow.net/applications/DTDHandbook/Sections/page5_4_2.aspx).
- [TRANSFER: USN carrier landings] MIL-A-8863A carrier sink-speed relation (Q3). F-14 surveys (1,130 landings): mean sink 10.3–12.9 ft/s (SD 1.97–2.76), engaging speed 109–120 kt, wind over deck 25–34 kt, glide slope 2.8–3.4° (SD 0.6–0.9°), pitch at touchdown 7.5–8.3°. Source: [NADC-91027-60, Table 1, p. 2](https://archive.org/details/DTIC_ADA239511). (Carrier only; the field-landing distribution remains MIL-A-8866C Table I, sibling.)
- [DIRECT] IAF life units:
  - Hawk "Life … is 30 Years/100 Fatigue Index (FI)/6000 flying hours"
  - Kiran Mk I/IA total technical life 8,500 airframe hours; Kiran Mk II 7,500
  - PC-7 Mk II 10,000 airframe hours / 30,000 landings
  - Source: [18th LS 2nd Report, §2.30, ≈p. 33](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs).
- [DIRECT, secondary] Tejas fatigue activity:
  - HAL commenced a Main Airframe Fatigue Test of Tejas Mk1, intended to show the airframe can withstand four times the service life ([Janes, Apr 2022](https://www.janes.com/defence-news/hal-commences-airframe-fatigue-testing-of-tejas-mk1), search excerpt).
  - ADA records a "Fatigue Test Specimen" build ([ADA AR 2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf), sibling).
  - ADA is reportedly developing an OFDR fibre-optic strain/vibration/temperature sensing system aimed at Tejas Mk2/AMCA ([idrw](https://idrw.org/?p=389412), secondary).
  - NAL/ADE flew an onboard SHM system on the Nishant UAV in 2010 (DRDO statement, search excerpt).
  - No Tejas in-service fatigue-meter or individual-aircraft-tracking data are public.
- [TRANSFER: USAF F-16 tyres] Main-tyre life "Very few sorties/tire: F-16 Block 30 … 8–12 landings; F-16 Block 40 & 50 … 4–8 landings" — [Chawla, USAF Wright Lab, NASA NTRS 19960009454, Fig. 1](https://ntrs.nasa.gov/citations/19960009454).

### Inferences
- [INFERENCE] **Target Nz spectrum for the virtual Tejas.** Use the AGARD F-16 operational curve as the *upper-severity* air-defence reference and the "MIL-spec design usage" curve as the *benign* bound. A Tejas Mk1A squadron spectrum should fall between them. Mission-type weights (BFM vs navigation) can be tuned to land within the band:
  - ≈2,000–7,000 exceedances of 5 g per 1,000 h
  - ≈100–1,300 of 7 g
  - ≈5–30 of 9 g
  - Scale down for Tejas's +8 g (IOC) clearance and up to +9 g (FOC) [ASSUMPTION; validate with Tejas DFCC Nz histograms when available].
- [INFERENCE] **Roll generator.** For every 100 positive Nz peaks above 2 g, emit ≈13 rolling manoeuvres (|p| > 30 °/s concurrent with Nz > 2 g), split 50/50 left/right. Draw pb/2V from the ASD-TR-72-113 normalised curve, scaled by the Tejas maximum pb/2V (from the FCS roll-rate limit). Roll-peak probability does not depend on Nz level, which simplifies the joint distribution.
- [INFERENCE] **Fleet and deployment severity scalar.** The RNLAF CSI shows that home-base training (1.03–1.04) can be ≈3× more damaging per hour than operational deployment CAP sorties (0.31). Combined with the earlier range (Chinese fighter 20 % lighter; CF-18, RAAF and FINAF heavier than design), a per-squadron or per-detachment severity multiplier in ≈0.3–1.5 is defensible.
- [INFERENCE] **Recording rates for the structural channel.** FINAF HOLM (20 Hz flight parameters; 640–2,560 Hz strain and vibration) and RNLAF FACE (50 Hz bus, 4 Hz DEEC, 1,000 Hz strain) bracket what a Tejas loads and usage recorder would produce. This is cross-linked to the data-pathway researcher.

### Gaps
- MIL-A-8866B fighter/trainer exceedance tables, ASD-TR-82-5012 and USAF F-16 ASIP/L/ESS tabulations were not retrieved: no everyspec or archive.org copy, and DTIC was unreachable.
- Numeric DSTG/Swiss F/A-18 Nz exceedance tables were not found in released form.
- Measured fighter field-landing sink-rate histograms (land-based) were not found.
- No IAF/Tejas fatigue-meter or IAT data.

---

## Q5. Engine usage: AMT cycle definitions, throttle-excursion and TAC/LCF rates across fleets, stochastic manoeuvre-sequence models

### Takeaway
New released anchors:
- **F110-GE-129 SLEP AMT ("AMT 2003", most severe profile):** 1,148 h, ≈1,333 simulated sorties, 4,639 TACs, 8,253 AB light-offs. That is ≈0.86 AMT-h, 3.5 TAC and 6.2 AB lights per simulated sortie.
- **F135 AMT:** 9,400 TAC ≈ 14 years ≈ 2,000 missions, i.e. ≈4.7 TAC per mission.
- **IN20 (GE):** 330 h AMT ≈ 1,000 FH (≈3 FH per AMT-h).
- **FINAF F404-GE-402 LPT blades:** EOT/EFH = **1.56** (3,890 EOT at 2,496 EFH).

No released F404, RM12 or IN20 AMT cycle definition (segment table) and no fleet throttle-excursion histogram for F404 users were found. No published numeric fighter manoeuvre Markov or semi-Markov transition matrix was found; the public practice remains deterministic master-event sequences or flight-by-flight block sequencing.

### Cited Findings
- [DIRECT-class for F110] "The engine accumulated 1,148 hours of running time during the Accelerated Mission Test … approximately 1,333 simulated sorties, 4,639 TACs, and 8,253 afterburner light-offs … AMT 2003, the most severe endurance profile" (completed 15 Oct 2004) — [GE press release, 17 Nov 2004](https://www.geaerospace.com/news/press-releases/f110-ge-129-slep-engine-achieves-major-milestone).
- [TRANSFER: F135] "9,400 total accumulated cycles (TAC) … approximately fourteen years of operation … approximately 2,000 F-35 missions"; testing included "two hot section intervals" — [AviTrader, 26 Oct 2017 (P&W release)](https://avitrader.com/2017/10/26/pratt-s-f135-engine-cold-section-demonstrates-full-life-capability/).
- [DIRECT] IN20: "330 hours of Accelerated Mission Testing (equivalent to 1,000 flight hours)" — [GE, 20 Jun 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight) (sibling).
- [TRANSFER: F404-GE-102, T-50] Localised-parts durability AMT of "550 cycles, 330 h" (sibling, DTaQ article).
- [TRANSFER: FINAF F/A-18C, F404-GE-402] "The blades #6221 and #6645 were removed after 2496 EFH (Engine Flight Hour) and 3890 EOT (Engine Operation Time) after reaching the end of their nominal life. The blade #6710 had seen 1363 EFH and 2130 EOT" — [ICAF Finland Review 2017, §3.3.2, p. ~52](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf).
- [TRANSFER: USN F404, secondary/search excerpts] GE found "pilots were changing throttle settings far more often than engineers previously expected" — [Wikipedia: GE F404](https://en.wikipedia.org/wiki/General_Electric_F404) (secondary). DoD IG audits (reports 94-041, 95-050) recorded F404 "lower durability than predicted" and GE's "new reduced life limits" (search excerpts; media.defense.gov blocked).
- [TRANSFER: USAF] The sibling note already holds the F-22/F119 design usage, MIL-HDBK-1783B guidance, the F-15E/F110 3.3 TAC/EFH field result, the F414 1.2 ELCF/EOT-h conversion, and the RM12 mission statistics.
- [TRANSFER: USAF/Boeing practice, methodology only] Load-sequence building from an ordered "master event spectrum" of manoeuvres. The AFGROW five-step flight-by-flight sequencing (mission ordering → segment conditions → level counts → in-segment ordering → other sources) is the documented public practice ([AFGROW DTDH §5.4.2](https://afgrow.net/applications/DTDHandbook/Sections/page5_4_2.aspx)). No numeric Markov matrices were found.

### Inferences
- [INFERENCE] **AMT-to-flight ratios** for the generator's life-consumption sanity checks:
  - IN20 ≈3.0 FH per AMT-h. F110 SLEP ≈0.86 AMT-h per simulated sortie, so a sortie ≈2.6 FH of field exposure under the IN20-type ratio, which is consistent with "AMT compresses damaging content".
  - TAC per mission: ≈3.5 (F110 AMT, most severe) and ≈4.7 (F135). Against the F-22 design ≈2.9 TAC per flight and F-15E field ≈3.3 TAC/EFH, a peacetime Tejas squadron should land at **≈2–3.5 TAC per flight-hour-equivalent sortie**, with AB lights ≈4–7 per sortie for A-A training [ASSUMPTION; validate with Tejas ECMS life-usage indices].
- [INFERENCE] **Ground engine time.** FINAF F404-402 EOT/EFH = 1.56. With BOS2's ≈0.87 h per flight this gives ≈0.49 h of ground running per flight, matching the F-22-derived 0.46 h (sibling) and the USAF default LTO idle time of 18.5 + 11.3 ≈ 30 min (Q1).
- [ASSUMPTION] **Manoeuvre sequencing.** Keep the semi-Markov proposal in the sibling note. Calibrate its transition probabilities so that output statistics match:
  - Nz exceedances inside the AGARD F-16 band (Q4)
  - roll/Nz ratio ≈13 %
  - TAC per sortie 2–3.5
  - AB lights 4–7 per A-A sortie
  - EOT/EFH ≈1.4–1.6

  This substitutes calibration-to-statistics for the missing published matrices.

### Gaps
- Released AMT segment definitions (minutes per power level, cycles per AMT-h) for F404/IN20/RM12 were not found.
- Fleet throttle-excursion histograms (excursions per FH, PLA dwell distributions) for F404 operators were not found. DSTO/RAAF ARL ADA164562 and CF-18 ADA347270 are in sibling notes but contain no histograms.
- The full GAO PSAD-80-72 and DoD IG 94-041/95-050 texts were not read (blocked).
- No public numeric Markov/semi-Markov fighter manoeuvre models were found.

---

## Q6. Remaining validation-method gaps: frequency- and time-domain acceptance thresholds, military M&S/simulator qualification, engine test-cell correlation, aerospace discriminator examples

### Takeaway
The open quantitative gaps from `validation_and_calibration.md` can now be filled with sourced numbers:
- **Frequency-domain fidelity:** CIFER/Tischler average cost **J_ave ≤ 100** "acceptable" for flight-dynamics modelling, with individual pairs up to ≈200 (weights W_g = 1.0, W_p = 0.01745, so 1 dB ≈ 7.57°).
- **Time-domain fit:** **J_rms ≤ 1.0–2.0** (helicopter guideline) and **Theil inequality coefficient ≤ 0.25** for accurate prediction (rigid-wing aircraft).
- **Mismatch boundaries:** MUAD/AEE frequency-domain envelopes (Wood & Hodgkinson 1980; Mitchell et al. 2006), narrowest near 1–10 rad/s. Numeric boundaries were not extracted.
- **Military simulator qualification:** the UK MAA (RA 2375) qualifies military training devices against civil CS-FSTD / ICAO 9625 with tolerances "adjusted to suit military usage". **No separate military numeric tolerance standard exists.** GM-VV (SISO/NATO) is a process framework (acceptability criteria, evidence and argument) without numbers.
- **Engine test cells:**
  - correlation tolerances are OEM-specific (FAA AC 43-207, SAE ARP741 paywalled)
  - inlet-momentum drag is 1–10 % of thrust
  - AGARD UETP / NASA measurement uncertainty on a J57 is **±0.7 % airflow, ±0.9 % thrust, ±1.4–1.5 % SFC, ±0.24 % rotor speed** at 82.7 kPa inlet, rising to about ±2.5 / 3.1 / 3.5 % at 20.7 kPa
- **Aerospace discriminator example:** TU Delft (SIDs 2024) used an LSTM real-vs-synthetic discriminator on landing trajectories: accuracy 0.608 overall (TPR 0.947, TNR 0.269), 0.65–0.87 per cluster. No physics-simulator (as opposed to generative-model) flight or engine discriminator validation was found.

### Cited Findings
**Frequency- and time-domain fidelity metrics**
- [TRANSFER: rotorcraft/fixed-wing system-ID practice; US Army/NASA CIFER]
  - J = (20/n_ω) Σ W_γ [W_g(|T̂_c| − |T̂|)² + W_p(∠T̂_c − ∠T̂)²], "first introduced by Hodgkinson and later improved by Tischler".
  - "It is a standard practice to set W_g = 1.0 and W_p = 0.01745 … 1 dB of magnitude error is equivalent to 7.57° of phase error."
  - W_γ weights frequencies by coherence.
  - "According to the guideline in [Tischler & Remple 2012, Ch. 11, p. 280], an average cost function value less than or equal to 100 signifies an acceptable level of accuracy for flight dynamics modeling, even if some individual cost functions reach values of 200."
  - Applied example (UH-60): higher-order model J_ave = 91.8 (accepted), reduced 10th-order J_ave = 117.1, and r/δ_ped J ≈ 240.
  - Source: [arXiv 2506.23302 (2025), eq. 35 and §IV, pp. ~16–18](https://arxiv.org/pdf/2506.23302).
  - The "J ≤ 50 indistinguishable" level often quoted from memory was **not** verified.
- [TRANSFER: rotorcraft time-domain ID] "For helicopters, the guideline for appropriate time domain model fit is given to be RMSE ≤ 1.0 to 2.0 (Ref. 16 = Tischler & Remple 2006)." Identified-model frequency errors are then compared with "maximum unnoticeable added dynamics (MUAD) … and allowable error envelopes (AEE) … In the vicinity of 1 rad/s and 10 rad/s, the bounds get narrower". Source: [Aslandoğan, Gürsoy & Yavrucuk, ERF 2024 paper (NLR ERF repository), pp. 5–6](https://dspace-erf.nlr.nl/bitstreams/f61317ae-2dfc-4b28-99a1-e521d7e8b45e/download).
- [TRANSFER: fixed-wing system ID] TIC = √(mean (ŷ−y)²) / [√(mean ŷ²) + √(mean y²)]. "A value of TIC = 0 denotes a perfect match … TIC = 1 indicates the worst case … Values of TIC ≤ 0.25 correspond to accurate prediction for rigid wing aircraft", citing Tischler & Remple and Jategaonkar, Fischenberg & von Gruenhagen (J. Aircraft 41(4), 2004). Example values: V_T 0.04, α 0.22, θ 0.29, q 0.15 (θ judged "slightly over the limit"). Source: [Licitra et al., arXiv 1711.10010, eq. 26 and Table 8, p. 13](https://arxiv.org/pdf/1711.10010).
- [TRANSFER: flying-qualities research] MUAD envelopes were "defined by Wood and Hodgkinson in 1980"; the AEE of Mitchell, Hoh, He & Strope (AIAA 2006-6492) "define the allowable errors in helicopter simulation validation". AEE "are dependent on the bandwidth frequency of the baseline model … not universally applicable for now". Source: [Li Mengyang, TU Delft MSc thesis (2016), literature review pp. 21–22](https://repository.tudelft.nl/file/File_d2b00f3a-e42b-44d3-9133-07e756845e21).

**Military simulator and M&S qualification**
- [TRANSFER: UK military regulator]
  - "EASA Certification Specifications … CS-FSTD(A) … derived from ICAO Doc 9625 … provide guidance on the construction of a QTG and fidelity levels. However, the guidance is based on civil Air Systems … these may not fully satisfy military usage. Therefore, specific military tasks and capabilities may need to be included in the device QTG … and acceptance criteria and tolerances adjusted to suit military usage."
  - Simulator descriptors "intentionally reflect civil terminology … to allow industry partners to apply recognized civil standards where military standards are not codified."
  - The operator "progressively tests the ATD against the Master QTG over a rolling 12 month period … between annual Approvals."
  - Source: [UK MAA Regulatory Article 2375 Issue 5, ¶¶1, 5–6, 21, 23–24, pp. 1–6](https://assets.publishing.service.gov.uk/media/661cf46208c3be25cfbd3d7a/RA2375_Issue_5.pdf).
- [TRANSFER: NATO/SISO] GM-VV (SISO-GUIDE-001.1-2012 with NATO MSG-073):
  - Five activities: "define a set of concrete and assessable acceptability criteria … collect or generate relevant evidence … assess the evidential quality … develop arguments … compile … an acceptance recommendation."
  - Property areas: utility, validity ("degree of realism (i.e. fidelity)") and correctness.
  - "An acceptance recommendation is not necessarily just a yes or no claim … conditions or restrictions under which the M&S asset can still be used."
  - Source: [Roza, van Emmerik, Voogd et al., NLR-TP-2013-598, §2.2, pp. 11–12](https://reports.nlr.nl/items/d3e9b03e-34ce-42d5-9ac9-f6b3beb8ba29/full). The NATO STO-TR-MSG-073 PDF was blocked.

**Engine test-cell correlation**
- [TRANSFER: FAA civil practice] AC 43-207 (26 Dec 2002), test cell correlation:
  - Inlet momentum drag: "values from 1 to 10 percent of the measured thrust are typical."
  - "Some OEMs specify run-to-run parameter tolerances for engine correlation testing."
  - "engines with a choked core exhaust nozzle generally require that a correlation factor be applied only to thrust. However, engines with unchoked core exhaust nozzles may require additional correlation factors (e.g., exhaust gas temperature (EGT), fuel flow, rotor speeds)."
  - "Correlation factors are usually applied to corrected, not raw, data."
  - Compounding tolerance error through a "one-away" reference facility; trending and recalibration to maintain correlation.
  - Source: [FAA AC 43-207, ¶¶ 3xx–402, pp. 20–31](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC43-207.pdf). SAE ARP741D/AIR4869 numeric tolerances are paywalled (not read).
- [TRANSFER: AGARD Uniform Engine Test Programme, NASA Lewis PSL cells 3 and 4, two J57 turbojets at 8,875 rpm] Total uncertainty (% of reading). Rotor speeds: bias 0.21 %, precision 0.02 %, uncertainty 0.24 %. "Bias error levels were two to three times higher than those of precision errors." Source: [Abdelwahab, Biesiadny & Silver, NASA TM-88943 (1987), Table VI, p. 40](https://ntrs.nasa.gov/api/citations/19870019124/downloads/19870019124.pdf).

  | Condition | Airflow | Net thrust | SFC |
  |---|---|---|---|
  | 82.7 kPa, 288 K, ram 1.0 | 0.68–0.71 % | 0.88–0.90 % | 1.45–1.51 % |
  | 82.7 kPa, ram 1.3 | 0.67–0.71 % | 0.84–0.87 % | 1.41–1.45 % |
  | 20.7 kPa, ram 1.3 | 2.52–2.57 % | 2.96–3.11 % | 3.37–3.49 % |

**Discriminator (real-vs-synthetic) examples in aerospace**
- [TRANSFER: civil terminal-airspace landing trajectories, TU Delft] A discriminator of "three LSTM layers followed by a dense output layer … trained to classify samples as either original or synthetic … evaluated on separate test sets".
  - All landings: accuracy 0.608, TPR 0.947, TNR 0.269, "TSTR vs TRTR −0.473 %", e-distance 1.482.
  - Per cluster: accuracy 0.651–0.869, e.g. SW 0.869 with TSTR −2.401 %.
  - "The mediocre accuracy indicates the trained discriminator is deceived often … the higher TPR indicates that this largely stems from synthetic samples misclassified as real."
  - Source: [Wijnands, Sharpanskykh & Aly, SESAR Innovation Days 2024, paper 054, §III–IV, Tables I–II](https://sesarju.eu/sites/default/files/documents/sid/2024/papers/SIDs_2024_paper_054%20final.pdf).
- [TRANSFER: tabular airline schedule records, TU Delft 2026] "trained seven classifiers to separate real records from synthetic ones"; lower accuracy means more similar. This is generative tabular data, not telemetry — [Aly & Sharpanskykh, arXiv 2604.20293](https://arxiv.org/pdf/2604.20293).
- [TRANSFER: patent, design intent only] A GAN with a discriminator trained on "multiple timeseries of multivariate aircraft performance data of actual aircraft flights" — [EP 4365790 A1 / US 2024/0150034](https://data.epo.org/gpi/EP4365790A1) (search excerpt).

### Inferences
- [INFERENCE] **Phalanx acceptance thresholds** (to add to `validation_and_calibration.md`'s staged protocol):
  - **Frequency domain:** per transfer function (e.g. q/δ_e, Nz/δ_e, p/δ_a, N2/PLA, EGT/PLA), J_ave ≤ 100 across the set and every individual J ≤ 200 over the coherent band (γ² ≥ 0.6 per CIFER practice — this coherence value is [ASSUMPTION], not verified this session).
  - **Time domain:** J_rms ≤ 1–2 (in CIFER's normalised units) and TIC ≤ 0.25 per channel. Report TIC by regime (ground run, take-off, cruise, high-g).
  - **Pilot-relevant dynamics:** confine errors inside MUAD/AEE near 1–10 rad/s for handling-relevant modes, as a qualitative gate.
- [INFERENCE] **Engine-model tolerances.** The UETP measurement uncertainty sets an irreducible floor. Engine-model-vs-test-cell tolerances tighter than ≈±1 % thrust and airflow and ≈±1.5 % SFC at sea-level conditions (≈±3 % at altitude-cell conditions) cannot be demonstrated. Compare in *corrected* parameters (AC 43-207), with EGT and fuel-flow correction only where the nozzle is unchoked (fighter afterburning engines at part power).
- [INFERENCE] **Discriminator reporting.** The TU Delft result shows that a raw accuracy (0.61) can hide an asymmetric failure (TNR 0.27: the discriminator labels most *real* samples as synthetic). Phalanx should report TPR, TNR and balanced accuracy per regime and condition cluster (cf. 0.65–0.87 across clusters), not one global score. This complements the sibling's C2ST protocol.
- [INFERENCE] **Military framing for the deliverable.** Combine:
  - GM-VV acceptance-recommendation structure (claims → arguments → evidence, with conditional acceptance)
  - RA 2375 practice (civil QTG/MQTG structure, tolerances adjusted to the intended use, rolling 12-month MQTG re-test)
  - the numeric gates above

  This yields a defensible "military-style" V&V basis without a non-existent military tolerance standard.

### Gaps
- Numeric MUAD/AEE envelope boundaries (dB and degrees against frequency) were not extracted. The AIAA 2006-6492 paper and the MIL-HDBK-1797 MUAD figures are not in hand.
- The CIFER coherence threshold and the "J ≤ 50" level remain unverified.
- SAE ARP741D / AIR4869 numeric correlation tolerances (paywalled); AGARD AR-248 facility-to-facility differences (not retrieved).
- USAF/USN numeric simulator tolerance documents (e.g., USAF simulator certification instructions) were not found. RA 2375 indicates none separate from civil standards in UK practice.
- No aerospace example of a classifier used to validate a *physics-based* flight or engine simulator was found.

---

## Synthesis for the report writer

### Takeaway
Officially released material now supports these usage parameters for the virtual Tejas: an IAF-style flying-task process with realistic achievement rates; exercise-surge and peacetime sortie rates; Tejas base climates by month; a sortie-length model anchored on Tejas development data plus Nordic and Australian squadron data; and replacement engine operating points for the F404 from USAF test-cell data. Structural spectra and validation thresholds are now quantitative. The biggest residual gaps are IAF per-aircraft and per-pilot hours, Tejas squadron mission mix, F404 start-EGT and oil-pressure limits, and Tejas approach/take-off numbers.

### Cited Findings — (a) Key findings
1. **IAF process and achievement** [DIRECT]: the MoD sets annual flying tasks in squadron "Policy Pages". Audited fighter fleets achieved ≈57–69 % of task (Su-30MKI, 2004–09) and ≈44–71 % (MiG-21 Bison, against the Government task), with low serviceability as the cause; AWACS units saw ≈43 % shortfall from availability (≈66 % vs 75 % planned), weather and bird activity.
2. **IAF volume** [DIRECT → INFERENCE]: ≈2.4–2.6 lakh FH per year across all types (1990–2018); accident rate fell from 1.07 to 0.22–0.28 per 10,000 h.
3. **Surge** [DIRECT]: Gagan Shakti 2018 had >11,000 sorties (≈9,000 fighter) in 15 days with 80 % serviceability and >95 % dispatch; Tejas flew 6 sorties per aircraft per day (8 aircraft, snags on 6 on day 1).
4. **Tejas sortie statistics** [DIRECT, development]: average 30–51 min (fleet mean ≈38–40 min); 1–5 sorties per month to IOC (ADA desired 22); FY 2018-19 32–75 h per aircraft per year; up to 5 sorties per day with hot refuelling (naval prototype).
5. **Tejas status** [DIRECT]: 2 Mk1 squadrons of 31 active (42 authorised); 220 LCA planned; no Mk1A delivered by May 2026 (HAL targets ≈20 in FY 2026-27, from Aug–Sep 2026).
6. **Restricted-value replacement** [TRANSFER]: USAF test-cell F404-400 idle and MIL fuel flow, N1, N2 and thrust; F110-129 and F100-229 fuel flows by mode; F-16 approach and touchdown speeds, aerobrake attitude, idle rpm, 60 % stagnation rule; F-16 AoA limiter 25° and 9 g limiter; F-18 carrier approach-speed regression; Tejas chute speeds. **Not replaced:** F404 start-EGT and oil-pressure bands, -402 880 °C, thermal-soak rule, 8.1° AoA, F-16 11–13° AoA and chute band.
7. **Spectra** [TRANSFER]: F-16 operational Nz exceedances per 1,000 h (≈7,000 at 5 g; ≈1,300 at 7 g; ≈10 at 9 g), more severe than design in the mid-range; roll peaks ≈13 % of Nz peaks; deployment CSI 0.31 vs home 1.03; FINAF and RAAF usage more severe than design.
8. **Engine usage** [TRANSFER/DIRECT]: IN20 330 h AMT ≈ 1,000 FH; F110 AMT 2003 ≈3.5 TAC and 6.2 AB lights per simulated sortie; F135 ≈4.7 TAC per mission; FINAF F404-402 EOT/EFH 1.56.
9. **Validation gates** [TRANSFER]: J_ave ≤ 100 (individual ≤ 200); J_rms ≤ 1–2; TIC ≤ 0.25; UETP uncertainty floor ±0.7/0.9/1.5 % (airflow/thrust/SFC); military qualification = civil QTG structure with tolerances tailored (UK RA 2375); GM-VV acceptance-argument structure.

### Cited Findings — (b) IAF / Tejas usage-statistics table

| Statistic | Value | Tag | Source |
|---|---|---|---|
| Flying-task basis | MoD-fixed per squadron in "Policy Page"; serviceability norm 75 % | DIRECT | [CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf) |
| Su-30MKI task vs achieved | 2,400→12,960 h task; 57–69 % achieved (shortfall 31.13–43.05 %), 2004–09 | DIRECT | CAG 38/2015 Table 2.8 |
| MiG-21 Bison task vs achieved | Govt task 12,698–13,631 h; achieved 5,626–9,533 h (shortfall 29.09–55.70 %) | DIRECT | CAG 38/2015 Table 2.9 |
| AWACS ('AA', 3 ac) | 1,500 h/yr (≈500 h/ac) task; 766–926 h achieved; 43 % shortfall; availability ≈66 % vs 75 % planned | DIRECT | CAG 38/2015 Table 2.1 |
| Whole-IAF flying volume | ≈2.4–2.6 lakh FH/yr (1990–2018) | DIRECT data → INFERENCE | [16th LS 47th Report](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_47.pdf?source=loksabhadocs) |
| IAF accident rate | 1.07 (1990-95) → 0.28 (2015-18); 0.22 (FY 2015-16) per 10,000 FH | DIRECT | 16th LS 47th, 25th Reports |
| Fighter squadrons | 31 active vs 42 authorised; 2 Tejas Mk1 sqns; 220 LCA planned | DIRECT | [18th LS 12th Report](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_12.pdf?source=loksabhadocs) |
| Night-capable bases | 52 operational bases, all night-capable; 48 with Cat II lighting | DIRECT | [18th LS 2nd Report §2.31](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs) |
| Fighter pilot-to-cockpit ratio | sanctioned 1:1.25 (printed "1:25"); actual withheld | DIRECT | 16th LS 47th Report |
| Exercise surge | >11,000 sorties (≈9,000 fighter), 8–22 Apr 2018; 80 % serviceability; >95 % dispatch | DIRECT | [PIB 24 Apr 2018](https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=178885) |
| Tejas surge sortie rate | 6 sorties/aircraft/day; 8 aircraft; snags on 6 on day 1 | DIRECT (secondary, ANI) | [Business Standard/ANI](https://www.business-standard.com/article/news-ani/india-made-tejas-acquits-itself-well-at-gagan-shakti-18-118042500151_1.html) |
| Tejas sortie duration (development, to IOC) | avg 30–51 min per aircraft; min 5–16; max 50–112; fleet mean ≈38 min (2,441 sorties, 1,560.8 h) | DIRECT | [CAG 17/2015 Annex III](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf) |
| Tejas sorties per month (to IOC) | 1–5 per aircraft (ADA desired ≥22); flown on 2,279 of 21,170 aircraft-days | DIRECT | CAG 17/2015 |
| Tejas developmental flying FY 2018-19 | 524 sorties (401 fighter/123 trainer); ≈45/month; peaks >75/month; 85 sorties at Jaisalmer detachment; 32–75 h and 49–123 sorties per aircraft; ≈40 min mean | DIRECT | [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) |
| Tejas developmental sorties other years | 444 (FY17-18), 233 (FY19-20), 222 (FY20-21) | DIRECT | ADA ARs |
| Hot-refuel turnaround | 38 sorties in 19 days incl. 20 hot-refuel; 5 ski-jump sorties in one day (naval prototype); refuel time "halved" (HAL claim) | DIRECT | ADA AR 2018-19; HAL (secondary) |
| Mk1A deliveries | none by 15 May 2026; ≈20 planned FY 2026-27; 6 IN20 engines received (7 per secondary, Jul 2026) | DIRECT | [HAL transcript](https://hal-india.co.in/backend/wp-content/uploads/2026/05/Transcript_May15-2026-signed.pdf) |
| Tejas bases | 45 Sqn Sulur; 18 Sqn Sulur→Naliya (conflict); Mk1A first unit No. 3 (Sulur→Nal) or No. 18 (Nal) (conflict) | DIRECT/secondary | PIB 2023; Wikipedia; Scramble; idrw |
| Base climate (rain/thunder/fog/dust days per yr) | Coimbatore 68.5/45.6/6.5/≈0.9; Naliya ≈27/≈4/14.9/≈0.1; Bikaner ≈29/≈25/≈6/7.6 | DIRECT | [IMD 1991–2020](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf) |
| Per-pilot annual hours (IAF) | **not found** | — | gap |
| Per-aircraft annual hours (IAF fighters) | **not found** (needs fleet size; see Inferences) | — | gap |
| FINAF F/A-18 utilisation | ≈130–150 FH/ac/yr; BOS2 ≈52 min/flight | TRANSFER | [ICAF Finland reviews](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf) |
| RAAF F/A-18 sortie length | ≈1.2 FH/flight (300,000 FH/250,000 flights) | TRANSFER | [White et al. 2015](https://www.humsconference.com.au/Papers2015/Non_peer_Reviewed/White01.pdf) |
| USAF fighter pilot hours | ≈16 h/month; ≈200 h/yr (FY15); F-15E RAP 96–108 sorties/yr; simulator ≤20 % | TRANSFER (search excerpts) | GAO-18-113, GAO-17-53, GAO-16-864 |
| USAF default LTO idle time | taxi-out 18.5 min, taxi-in 11.3 min (combat) | TRANSFER | [USAF Air Emissions Guide Table 2-4](https://archive.org/details/DTIC_ADA577276) |

### Cited Findings — (c) Restricted-value replacement table
(Old source: N = F/A-18 NATOPS, Distribution C; H = Hellenic AF F-16 manual, disclosure-restricted.)

| Value (as used in sibling notes) | Old source | Officially released replacement | Status |
|---|---|---|---|
| F404 ground-idle fuel flow 420–700 / 420–900 pph | N | **685 lb/h** at idle (6 % max thrust), F404-GE-400/F1D2 test cell — [IERA 1999 Vol. 3 Table 4-71](https://archive.org/details/DTIC_ADA361473); [USAF Emissions Guide Table 2-8](https://archive.org/details/DTIC_ADA577276) | **Replaced** (single measured point) |
| F404 ground-idle N2 61–72 / 63–70 % | N | N2 10,960 rpm ≈ **65 %** (IERA); T-50 ≈63–70 % (KSAS, sibling) | **Replaced** (points) |
| F404 MIL-check N2 92–102 / 90–102 % | N | MIL N2 15,994 rpm ≈ **95 %**; intermediate 15,414 ≈ 92 %; N1 13,167 rpm ≈ 99 % (IERA) | Partly replaced (points, not a band) |
| F404 MIL fuel flow 6,000–9,000 / 6,000–12,500 pph | N | **7,739 lb/h** at MIL (9,608 lbf at ≈27.8 inHg); intermediate 6,464 (IERA) | **Replaced** (point) |
| F404 ground-idle EGT 190–590 °C | N | ≈409 °C test-cell idle (NASA CR-191195, sibling) | Partly (single point) |
| F404 MIL EGT 715–830 °C (-400) | N | T5C steady-state limit 830 °C (NASA TM-101702); ≈816 °C at MIL test cell (CR-191195) — sibling | Upper bound replaced |
| -402 MIL steady EGT limit 880 °C | N | none; use -400 830 °C limit in hot-day example | **Not replaced** |
| F404 max start EGT 815 °C | N | none | **Not replaced** |
| F404 idle oil 45–110 psi; start peak < 180 psi falling within 30 s; MIL oil 95–180 psi | N | none (IERA tables lack oil) | **Not replaced** |
| Thermal-soak restart rule (motor 1 min at 24 % N2, 15 min–4 h) | N | none | **Not replaced** |
| Throttle to idle ≥ 15 %; crank off ≈ 60 % | N | T-50: idle at ≈20 % N2, starter cut-out ≈55 % (KSAS); NASA hung-start 60 % rule (sibling) | Partly replaced |
| 5-min idle before shutdown | N | Gripen recorded average 259 s ([Chalmers 2014](https://publications.lib.chalmers.se/records/fulltext/199990/199990.pdf)); NAWCAD test practice 2 min (sibling) | Partly replaced |
| F/A-18 on-speed AoA 8.1° | N | "on speed" AoA concept only (NADC-91027-60); no number | **Not replaced** |
| F/A-18 approach ≈125 kt at 2,000 lb fuel; +2.5 kt per 1,000 lb | N | Measured carrier regression V = 90.7 + 0.270·WOD + 0.001497·W (608 landings); "NATOPS typical 2 kt per 1,000 lb" — [NADC-91027-60](https://archive.org/details/DTIC_ADA239511) | Partly replaced (carrier, weight slope) |
| F/A-18 field break 250 kt | N | CF-188 FSIR break example 470 kt / 1,500 ft AGL / idle / 81° bank / 6.8 g (non-standard) — [RCAF](https://www.canada.ca/en/air-force/corporate/reports-publications/flight-safety-investigation-reports/cf188796-hornet-epilogue.html) | Partly (example, not norm) |
| F/A-18 AAR closure ≤ 5 kt on drogue | N | Tejas-class NFTC data: 1.7–4.3 kt measured; 10 kt design max — [DSJ 70(2) 2020](https://www.publicationsdrdo.in/index.php/dsj) | **Replaced for Tejas** |
| F/A-18 takeoff trim/rotation, tyre 190/210 kt, gear 250 kt, climb 350 kt, cruise 4.2°/5.6° AoA, rollout (stab braking, anti-skid 40 kt, hydroplaning 140/110 kt) | N | none | **Not replaced** |
| F/A-18 hot-weather items (FUEL HOT 79 °C, 103 °F avionics cooling, AMAD 15 min) | N | none | **Not replaced** |
| F-16 idle FF 500–1,500 (PW229) / 700–1,700 pph (GE129) | H | Idle FF 1,087 lb/h (F100-PW-229); 961 lb/h (F110-GE-129) — [USAF Emissions Guide Table 2-8](https://archive.org/details/DTIC_ADA577276) | **Replaced** (points) |
| F-16 idle rpm 65–77 / 62–80 %; flight idle 70–80 % | H | "~70 - ~80% RPM indicates idle thrust" (F100-PW-229) — USAF AIB 92-3890 (2016) | **Replaced** (band) |
| F-16 start FTIT ≤ 625–650 °C; limits 800/935 °C; JFS timings, motoring limits | H | none; AIB confirms JFS-assisted airstart; < 60 % rpm = stagnated (AIB Holloman 2024) | **Not replaced** (FTIT); partly (airstart rule) |
| F-16 final 11/13° AoA, max 13° at touchdown | H | Computed approach 150 kt / touchdown 138 kt at 22,288 lb (F-16D Blk 52) — USAF AIB 91-0466 (2017) | Partly (speeds, not AoA) |
| F-16 aerobraking at ≤ 13° AoA to ~100 kt | H | 10.5° nose-high to ≈110 kt, then nose down and brake (AIB 91-0466) | Partly replaced |
| F-16 drag chute 90–170 kt | H | none for F-16; **Tejas chute ≤ 285 km/h (154 kt) normal, 340 km/h (184 kt) emergency** — [MoD DDP](https://www.ddpmod.gov.in/hi/node/8027) | Replaced for Tejas only |
| F-16 FLCS: +9 g below 15° AoA; ≈25.5° AoA limit; roll-rate limiting | H | AoA limiter "below 25°"; roll rate restricted above 13° AoA (≈90 °/s at 25°) — [NASA TP-1538](https://ntrs.nasa.gov/citations/19800005879); alpha-g limiter "prevent … exceeding 9g" — [AGARD R-815 p. 12-3](https://archive.org/details/DTIC_ADA324348) | **Replaced** (design-era) |
| F-16 over-g report 9.5/−3.2 g; SYM/ROLL split at 20 °/s | H | Roll-activity threshold ±30 °/s with Nz > 2 g (ASD-TR-72-113) — methodological, not the same rule | Not replaced (method substitute) |
| F-16 FLCS BIT ≈ 45 s; EPU check | H | none | **Not replaced** |
| F-16 tyre limits 225/217/235 kt GS | H | none (tyre life 4–12 landings — NASA NTRS 19960009454) | Not replaced |
| F-16 brake energy 23.5 M ft·lb; fuse plugs 3–15 min | H | none | Not replaced |
| F-16 shutdown items (EGI off 20 s, exhaust hazard 5/10 min) | H | none | Not replaced |

### Cited Findings — (d) Usage-spectra table

| Spectrum | Values | Tag | Source |
|---|---|---|---|
| Nz exceedances per 1,000 h, F-16 air-defence operational | ≈34,000 (2 g), 24,000 (3 g), 12,000 (4 g), 7,000 (5 g), 3,600 (6 g), 1,300 (7 g), 700 (7.5 g), 350–450 (8 g), 70–90 (8.5 g), ≈10 (9 g) | TRANSFER (graph-read ±30 %) | [AGARD R-815 Fig. 7](https://archive.org/details/DTIC_ADA324348) |
| Nz exceedances per 1,000 h, original F-16A/B design (MIL spec + modified A-A) | ≈100,000 (1.25 g), 41,000 (2.25), 20,000 (3.25), 9,000 (4.25), 3,200 (5.25), 1,100 (6.25), 350 (7.25), 90 (8.25), 21 (9.25), 10 (9.75) | TRANSFER | same |
| Nz exceedances per 1,000 h, F-16 design usage with MIL-spec exceedances | ≈16,700 (3.25 g), 5,200 (4.25), 1,270 (5.25), 290 (6.25), 70 (7.25), 17 (8.25), 4.4 (9.25), 2.3 (9.75) | TRANSFER | same |
| Rolling manoeuvres | ≈13 % of positive Nz peaks (12.2 % F-5A; 14.2 % F-105D; 12.1 % F-84F); 50/50 L/R; independent of Nz; thresholds 2 g / ±30 °/s | TRANSFER (historical) | [ASD-TR-72-113](https://archive.org/details/DTIC_AD0761491) |
| Fleet severity (CSI) | 323 Sqn 1.03; Goose Bay 1.04; Villafranca deployment 0.31 | TRANSFER (RNLAF F-16) | [NLR-TP-98172](https://reports.nlr.nl/items/654cb62e-1a8f-489f-a987-e47b44d39317/full) |
| Fleet severity (FINAF Hornet) | usage more severe than design; target 4,500 FH & 0.75 FLE | TRANSFER | [ICAF Finland 2011](https://publications.vtt.fi/julkaisut/muut/2011/ICAF_Doc2427_FinlandReview_2011.pdf) |
| Fleet severity (RAAF Hornet) | more severe than certification baseline; MSMP2 over-predicted small-cycle damage → MSMP3 (2015) | TRANSFER | [White et al. 2015](https://www.humsconference.com.au/Papers2015/Non_peer_Reviewed/White01.pdf) |
| Spectrum construction | 500–1,000 FH blocks; clip 10 per 1,000 flights; truncate 1e5–5e5 per 1,000 flights; 0.5 g steps; 8–10 positive / 4–10 negative levels | TRANSFER | [AFGROW DTDH §5.4.2](https://afgrow.net/applications/DTDHandbook/Sections/page5_4_2.aspx) |
| Field-landing sink speed per 1,000 landings | mode 3–4 ft/s; 0.5 at 10 ft/s (MIL-A-8866C Table I) | TRANSFER | sibling, [MIL-A-8866C](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-A/download.php?spec=MIL-A-8866C.019123.PDF) |
| Carrier sink speed | avg = 0.128 × engaging speed (min 11.5 ft/s); SD = 0.015V + 1.667 (min 3.0); F-14 surveys mean 10.3–12.9 ft/s | TRANSFER (USN) | [NADC-91027-60](https://archive.org/details/DTIC_ADA239511) |
| Naval LCA sink-rate clearance | drop test 7.1 m/s; structure cleared 5.8 m/s; flown 3.7–3.9 m/s | DIRECT (naval LCA) | [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf) |
| IAF fatigue index use | Hawk: 30 yr / 100 FI / 6,000 FH; Kiran TTL 8,500/7,500 h; PC-7 10,000 h / 30,000 landings | DIRECT | [18th LS 2nd Report §2.30](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs) |
| Engine AMT equivalence | IN20: 330 h AMT ≈ 1,000 FH | DIRECT | [GE 2008](https://www.geaerospace.com/news/press-releases/defense-engines/f404-ge-in20-powers-tejas-aircraft-successful-first-flight) |
| Engine AMT content | F110-129 AMT 2003: 1,148 h; 1,333 sorties; 4,639 TAC; 8,253 AB lights (3.5 TAC, 6.2 AB lights per sortie) | TRANSFER | [GE 2004](https://www.geaerospace.com/news/press-releases/f110-ge-129-slep-engine-achieves-major-milestone) |
| Engine AMT content | F135: 9,400 TAC ≈ 14 yr ≈ 2,000 missions (≈4.7 TAC/mission) | TRANSFER | [AviTrader/P&W 2017](https://avitrader.com/2017/10/26/pratt-s-f135-engine-cold-section-demonstrates-full-life-capability/) |
| Engine ground time | EOT/EFH 1.56 (FINAF F404-402 LPT blades: 3,890 EOT @ 2,496 EFH) | TRANSFER | [ICAF Finland 2017 §3.3.2](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf) |
| Loads/usage recording rates | FINAF HOLM: flight params 20 Hz, strain 640/1,280 Hz, VT accel 2,560 Hz; RNLAF FACE: bus 50 Hz, DEEC 4 Hz, strain 1,000 Hz | TRANSFER | ICAF Finland 2017; NLR-TP-2002-309 |
| Tyre consumption | F-16 main tyre 8–12 landings (Blk 30), 4–8 (Blk 40/50) | TRANSFER | [NASA NTRS 19960009454](https://ntrs.nasa.gov/citations/19960009454) |

### Cited Findings — (e) Validation-thresholds table

| Metric / practice | Threshold or value | Tag | Source |
|---|---|---|---|
| Frequency-response cost J (CIFER) | J_ave ≤ 100 acceptable; individual J up to ≈200 tolerated; W_g = 1.0, W_p = 0.01745 (1 dB ≡ 7.57°); coherence-weighted | TRANSFER | [arXiv 2506.23302](https://arxiv.org/pdf/2506.23302) citing Tischler & Remple (2012) Ch. 11 p. 280 |
| Time-domain fit J_rms / RMSE | ≤ 1.0–2.0 (helicopter guideline) | TRANSFER | [ERF 2024 (NLR repository)](https://dspace-erf.nlr.nl/bitstreams/f61317ae-2dfc-4b28-99a1-e521d7e8b45e/download) citing Tischler & Remple (2006) |
| Theil inequality coefficient | ≤ 0.25 = accurate prediction (rigid-wing aircraft); 0 perfect, 1 worst | TRANSFER | [Licitra et al., arXiv 1711.10010](https://arxiv.org/pdf/1711.10010) citing Tischler & Remple; Jategaonkar et al. 2004 |
| MUAD / AEE envelopes | frequency-domain upper/lower bounds; narrowest ≈1–10 rad/s; numeric bounds not extracted | TRANSFER | [TU Delft thesis 2016](https://repository.tudelft.nl/file/File_d2b00f3a-e42b-44d3-9133-07e756845e21); ERF 2024 |
| Military training-device qualification | civil CS-FSTD/ICAO 9625 QTG with tolerances "adjusted to suit military usage"; MQTG re-test over rolling 12 months; annual approval | TRANSFER (UK MAA) | [RA 2375 Issue 5](https://assets.publishing.service.gov.uk/media/661cf46208c3be25cfbd3d7a/RA2375_Issue_5.pdf) |
| M&S acceptance framework | acceptability criteria (utility/validity/correctness) → evidence → quality → argument → conditional acceptance recommendation | TRANSFER (NATO/SISO GM-VV) | [NLR-TP-2013-598](https://reports.nlr.nl/items/d3e9b03e-34ce-42d5-9ac9-f6b3beb8ba29/full) |
| Engine test-cell correlation | OEM-specified run-to-run tolerances; inlet momentum 1–10 % of thrust; correct on corrected parameters; thrust-only if choked | TRANSFER (FAA) | [FAA AC 43-207](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC43-207.pdf) |
| Test-cell measurement uncertainty floor | airflow ±0.67–0.71 %, thrust ±0.84–0.90 %, SFC ±1.41–1.51 %, rotor speed ±0.24 % (82.7 kPa); ±2.5 / 3.1 / 3.5 % at 20.7 kPa; bias 2–3 × precision | TRANSFER (AGARD UETP, J57) | [NASA TM-88943 Table VI](https://ntrs.nasa.gov/api/citations/19870019124/downloads/19870019124.pdf) |
| Discriminator (aerospace example) | LSTM real-vs-synthetic accuracy 0.608 (TPR 0.947, TNR 0.269); per cluster 0.651–0.869; TSTR−TRTR −0.12 to −2.4 % MAE | TRANSFER (civil trajectories) | [SIDs 2024 paper 054](https://sesarju.eu/sites/default/files/documents/sid/2024/papers/SIDs_2024_paper_054%20final.pdf) |
| C2ST null (from sibling) | accuracy ~ N(½, 1/(4n_te)) | TRANSFER | `validation_and_calibration.md` §3 |
| Civil FSTD tolerances (from sibling) | Part 60 / CS-FSTD Table A2A values | TRANSFER | `validation_and_calibration.md` §1 |

### Inferences — (f) Remaining gaps (priority order)
1. **IAF per-aircraft and per-pilot annual flying hours, and Tejas squadron sortie counts, lengths, mission mix and serviceability.** No released number was found. Retrieve:
   - Parliament Q&A (eparlib/rsdebate, from a browser)
   - CAG Report 15 of 2024 full text
   - CAG Air Force compliance reports 2016–2025
   - fleet strengths, so that CAG flying tasks can be converted into hours per aircraft
2. **F404 / IN20 start-EGT limit, oil-pressure bands, -402/IN20 MIL EGT limit, thermal-soak restart rule** (not in any released source found). Obtain from HAL/IAF mentors or derive [ASSUMPTION] with explicit labels.
3. **Tejas phase numbers:** take-off and landing distance, rotation and approach speed, approach AoA, climb schedule, turnaround minutes, Air Force design sink rate (ADA Operational Data Manual not public).
4. **F/A-18 8.1° and F-16 11–13° AoA and drag-chute bands.** Unreplaced; drop from deliverables or mark as "restricted-source, sanity-check only".
5. **Modern Nz spectra in tabular form** (MIL-A-8866B, ASD-TR-82-5012, DSTG/Swiss F/A-18 tables) and measured land-based fighter sink-rate histograms.
6. **Engine AMT segment tables and fleet throttle-excursion histograms** for F404-family engines; published fighter manoeuvre Markov matrices.
7. **MUAD/AEE numeric envelopes**, the CIFER coherence threshold, and SAE ARP741/AIR4869 numeric tolerances.
8. **A physics-simulator (not GAN) discriminator validation example** in aerospace.
9. **Conflicts to resolve:**
   - No. 18 Sqn current base (Sulur vs Naliya)
   - first Mk1A unit (No. 3 vs No. 18)
   - IN20 engines received (6 per HAL May 2026 vs 7 per Jul 2026 secondary)
   - Jaisalmer 2024 crash cause (oil pump vs oil level)
   - Gagan Shakti 2018 end date (21 vs 22 Apr)

### Inferences — (g) Ranked sources (most valuable first)
1. **CAG Report 38/2015 (Air Force)** and **CAG Report 17/2015 (LCA)**: the only audited IAF flying-task numbers and the only per-aircraft Tejas sortie statistics. [38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf); [17/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)
2. **USAF IERA engine emissions testing (1999) and Air Emissions Guide (2013)**: released F404/F110/F100 operating points (fuel flow, N1, N2, thrust) and default ground times. [ADA361473](https://archive.org/details/DTIC_ADA361473); [ADA577276](https://archive.org/details/DTIC_ADA577276)
3. **AGARD-R-815 (1997)**: F-16 operational Nz exceedance spectrum and 9 g alpha-g limiter. [ADA324348](https://archive.org/details/DTIC_ADA324348)
4. **ADA Annual Reports 2015-16 to 2021-22**: Tejas developmental sorties and hours, hot refuelling, sink rates, AAHC. [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)
5. **PIB Gagan Shakti 2018 + ANI Tejas statement**: surge sortie rates and serviceability. [PIB](https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=178885)
6. **Standing Committee on Defence reports (15th–18th LS)**: accident-rate table (flying volume), squadron strength, Tejas status, night-capable bases, IAF life units. [18th LS 2nd](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs); [16th LS 47th](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_47.pdf?source=loksabhadocs)
7. **ASD-TR-72-113 (1973)**: public roll-manoeuvre statistics. [AD0761491](https://archive.org/details/DTIC_AD0761491)
8. **FINAF ICAF national reviews and NLR RNLAF F-16 LUMP papers**: utilisation, severity, recording rates, CSI by usage, EOT/EFH. [ICAF FI 2017](https://sarjaweb.vtt.fi/julkaisut/muut/2017/ICAF_Doc2433_Finland_Review_2017.pdf); [NLR-TP-98172](https://reports.nlr.nl/items/654cb62e-1a8f-489f-a987-e47b44d39317/full)
9. **USAF AIB reports (F-16D 91-0466; F-16CJ 92-3890; Holloman 2024)**: released approach/touchdown speeds, aerobraking, idle rpm, stagnation rule. [AF JAG AIB library](https://www.afjag.af.mil/AIB-Reports/) (local copies)
10. **NASA TM-88943 (UETP), FAA AC 43-207, UK MAA RA 2375, NLR GM-VV paper**: engine test and M&S qualification practice. [TM-88943](https://ntrs.nasa.gov/api/citations/19870019124/downloads/19870019124.pdf); [AC 43-207](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC43-207.pdf); [RA 2375](https://assets.publishing.service.gov.uk/media/661cf46208c3be25cfbd3d7a/RA2375_Issue_5.pdf); [GM-VV](https://reports.nlr.nl/items/d3e9b03e-34ce-42d5-9ac9-f6b3beb8ba29/full)
11. **arXiv 2506.23302, arXiv 1711.10010, ERF 2024 paper**: sourced CIFER J, TIC and J_rms thresholds. [2506.23302](https://arxiv.org/pdf/2506.23302); [1711.10010](https://arxiv.org/pdf/1711.10010)
12. **NADC-91027-60 (1991)**: measured F-18 carrier approach-speed regression and carrier sink-speed relations. [ADA239511](https://archive.org/details/DTIC_ADA239511)
13. **HAL analyst-call transcript (15 May 2026)**: authoritative Mk1A delivery status. [HAL](https://hal-india.co.in/backend/wp-content/uploads/2026/05/Transcript_May15-2026-signed.pdf)
14. **IMD Climatological Tables 1991–2020**: monthly weather-phenomena days for Tejas bases. [IMD](https://imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf)
15. **SIDs 2024 TU Delft paper**: the only aerospace real-vs-synthetic discriminator result found. [SIDs 2024](https://sesarju.eu/sites/default/files/documents/sid/2024/papers/SIDs_2024_paper_054%20final.pdf)
16. **GE (F110 SLEP AMT; IN20 AMT) and P&W (F135 AMT) releases**: AMT-to-usage equivalences. [GE 2004](https://www.geaerospace.com/news/press-releases/f110-ge-129-slep-engine-achieves-major-milestone)

### Gaps
- See (f). Also note:
  - Several USAF/GAO figures (GAO-16-864, GAO-17-53, GAO-18-113; DoD IG 94-041/95-050; PIB PRID 2180339) come from search excerpts only, because their PDFs could not be parsed or reached in this environment.
  - AGARD Fig. 7 values are graph-read (±25–30 %).
  - USAF AIB report URLs are given as the AF JAG library root because the exact file URLs could not be verified; local copies are cited.
