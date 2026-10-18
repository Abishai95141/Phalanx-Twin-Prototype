# Indian Fleet Platform Relevance and Public Systems-Level Documentation (Project Phalanx)

Scope: evidence base for choosing the target aircraft of the Phalanx virtual-aircraft data generator, from the problem owner's perspective (MoD / IAF / DSSC). Special depth on HAL Tejas. Cross-links: engine-health data, airframe modelling, maintenance-record formats, fault/degradation and flight-profile topics are owned by parallel researchers; this note only touches them where they bear on platform choice.

Evidence tags: **[DIRECT]** = about that exact aircraft/engine/system; **[TRANSFER: X]** = from platform X, with reason and limits; **[ASSUMPTION]** = engineering judgement, with a validation route. CAG reports anonymise aircraft with letter codes ('C', 'DD', 'AA'); where I identify the type, the basis is given.

Method notes (affects completeness, read before relying on "not found"):
- The shared WebSearch budget for this run (200 calls across all parallel agents) was exhausted part-way through. After that point I only fetched known primary URLs (CAG CDN, sansad.in committee PDFs, mod.gov.in annual reports, joast.org archive, ada.gov.in pages, pib.gov.in, GE data sheet). No search-engine workarounds were used. Items marked "not found" may exist and need a follow-up search session.
- `publications.drdo.gov.in` (Defence Science Journal) and `nal-ir.nal.res.in` (NAL repository) did not resolve (DNS failure) from this environment, so the DSJ/NAL literature on LCA system identification (J. Singh, G. Girija) could not be read. The Journal of Aerospace Sciences & Technologies (JOAST, Aeronautical Society of India) archive was fully crawled instead (877 article titles, 2003-2026).
- Local copies (read-only, not executed) are in `/Users/abishaikc/Phalanx/research_sources/indian_fleet/` (CAG, committee reports in `ls_committee/`, MoD annual reports in `mod_ar/`, JOAST papers in `joast/`, ADA pages and reports in `ada/`).

---

## KQ1. What do CAG, Parliament, MoD, PIB and credible journalism say about serviceability, maintenance bottlenecks, spares, engines and maintenance-agency fragmentation, per platform?

### Takeaway
The only fighter fleets with **primary, numeric serviceability data in the public domain** are the **Su-30MKI** (CAG: 55.50-59.73% serviceability vs a 75% norm, AOG 10.90-15.32%, flying-task shortfall 31-43%) and the **MiG-21 Bison** (CAG: 41.32-51.52%, AOG 23-37%). Both audits blame the same mechanism the problem statement describes: spares and repair loops split across the IAF, HAL divisions, Base Repair Depots and a foreign OEM. **Tejas** has no published squadron serviceability figure, but it has a dense public record of availability shocks and agency friction (an LRU repair base that was incomplete in 2015, low prototype availability, engine-supply delays from GE, and a fleet-wide grounding of about 2 months in Feb-Apr 2026 over brake-system software).

### Cited Findings

**Fleet-wide (IAF fighters)**
- [DIRECT] The prescribed serviceability norm for IAF fleets is **75%** ("As per these norms the serviceability of aircraft should be maintained at 75 per cent"). Serviceability = airworthy; AOG = not airworthy. Source: CAG Report No. 38 of 2015 (Air Force), paras 2.3.3.1 and 2.4.2.3, pp. 61-62 and 75. [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf), [landing page](https://cag.gov.in/en/audit-report/details/15292)
- [DIRECT] IAF evidence to Parliament (Dec 2014): "the serviceability of the fleet need to improve further ... if I have 100 aircraft available today because of the serviceability level that may mean that I have 125 aircraft to fight." The witness tied this to revenue allocation for spares and upgrades. Source: Standing Committee on Defence, 4th Report (16th Lok Sabha), Demands for Grants 2014-15 (Navy & Air Force), para 2.15, presented 22.12.2014. [PDF](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_4.pdf?source=loksabhadocs)
- [DIRECT] IAF's own "critical areas" slide (2016): "Fighter AC: Production Shortfall, Low serviceability due to inadequate spare support, obsolescence and rate of Phase out higher than induction"; "Way Ahead: ... Increased AC availability through efficient spares procurement." Source: 20th Report (16th LS), DFG 2016-17, para 3.27 annex text, presented 03.05.2016. [PDF](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_20.pdf?source=loksabhadocs)
- [DIRECT] IAF description of its maintenance concept to Parliament (Mar 2018): "the aircraft is maintained on how many hours it has flown and what calendar life a particular part has on the shelf ... A very good log is kept ... considered engineering and technical decision is taken whether a part on the aircraft is to be given an extension." On accidents: "We have used to lose almost 30 to 40 aircrafts a year earlier. We reduced that number close to 10." Source: 41st Report (16th LS), DFG 2018-19, para 3.20. [PDF](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_41.pdf?source=loksabhadocs)
- [DIRECT] Revenue (maintenance) budget shortfall "can be felt in aircraft maintenance, serviceability and training ... older systems require more maintenance" (IAF, Dec 2019). Source: 2nd Report (17th LS), DFG 2019-20, para 2.4. [PDF](https://sansad.in/getFile/lsscommittee/Defence/17_Defence_2.pdf?source=loksabhadocs)
- [DIRECT] Force level: the number of fighter squadrons fell because MiG-21, MiG-23 and MiG-27 were phased out (Dec 2024). Tejas Mk1: "two Squadrons, including 32 fighters LCA Mk I and four twin seater". IAF witness on Tejas Mk1A: "some issues that primarily relate to the availability of the aero engine, delayed deliveries and HAL's ability to maintain the required production rate." Source: 2nd Report (18th LS), DFG 2024-25, paras 2.18-2.24, presented 17.12.2024. [PDF](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs)

**Su-30MKI (CAG code 'C')** (identification: 50 imported from OEM 'V-4' Russia in 1996-98 plus 222 HAL licence-built, 272 total, twin engine; CAG 38/2015 para 2.3.1 p. 56)
- [DIRECT] Serviceability and AOG at six operating units, Table 2.8 (source: Air HQ letter Air HQ/S21577/9/EA1(T)/BM dated 21.3.2011):

  | Year | Serviceability % | AOG % |
  |---|---|---|
  | 2006 | 55.50 | 13.94 |
  | 2007 | 57.45 | 15.32 |
  | 2008 | 58.95 | 11.71 |
  | 2009 | 59.73 | 10.90 |
  | 2010 | 59.16 | 12.28 |

  Flying task achieved vs MoD-allotted: 2004-05 1373:55/2400 h (shortfall 42.77%); 2008-09 7381:70/12960 h (43.05%); the range was 31.13-43.05%. Air HQ (Mar 2011): low serviceability was "mainly non-availability of repair facilities at HAL divisions leading to long repair cycle, as Cat 'D' aggregates were being sent to OEM for repair." MoD (Apr 2015): ROH for the aircraft and all aggregates was set up at HAL "except for four aggregates", and was delayed by late OEM supply of jigs, fixtures and tools. Source: CAG 38/2015 para 2.3.3.1, pp. 61-63. [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)
- [DIRECT] FBW reliability study (Dec 2009, AF Station 'S-12'): **31 aircraft** (15 OEM-built, 16 HAL-built) were grounded between 2007 and Nov 2009 by **111 FBW snags** (33 on OEM-built, 78 on HAL-built aircraft). Downtime was 160 days (HAL-built) and 75 days (OEM-built). Attributed causes: lower quality of HAL-built aircraft vs OEM, lower expertise of IAF technicians vs OEM technicians, non-availability of publications and test equipment, and limited FBW knowledge among maintenance personnel. MoD (Apr 2015): five FBW components classed as "high failure rate" aggregates were studied by the OEM from failure data sent to them, and changes were introduced. Source: CAG 38/2015 para 2.3.2.2(b), pp. 60-61.
- [DIRECT] Software standard churn: OEM aircraft flew software versions 3-I, 7-I and 10-I before the final 11-I standard. As of Apr 2015, 70 of 204 aircraft still awaited 11-I. The RWR R-118 (DARE/BEL, 200 sets) had "inherent design limitations"; the RWR contracts did not provide for I- or D-level maintenance. Source: CAG 38/2015 paras 2.3.2.1 and 2.3.2.2(a), pp. 57-60.
- [DIRECT] Manpower for the Su-30 squadron was "not sanctioned even after 19 years of its induction." Source: CAG 38/2015 para 2.3 summary, p. 56.
- [DIRECT] Earlier CAG reports on the Su-30MKI programme: Report No. 8 of 2000 (para 2); No. 4 of 2006 (ch. I); CA 18 of 2008-09 (para 2.7); No. 35 of 2014 (paras 9.1.2.5 and 9.1.5.6, ROH facilities still incomplete in Dec 2013). Source: CAG 38/2015 Annexure-V, p. 182, and para 2.3.3.1.
- [DIRECT] Press reporting of the same CAG report (tabled 18 Dec 2015): "around 55 percent to 60 percent against the prescribed norm of 75 percent"; an IAF official put 115-126 of 210 aircraft grounded; "around 35 engine failures"; the IAF "changed the Su-30MKI maintenance procedure". [Defense News, 21 Dec 2015](https://www.defensenews.com/home/2015/12/21/india-s-auditing-agency-punches-holes-in-russian-sukhoi/)
- [DIRECT, journalism quoting MoD data] Oct 2014: serviceability rose from 48% to about 55%. Of 193 aircraft, about 106 would be available in war. Breakdown: about 20% in first- and second-line maintenance or inspection (IAF responsibility), 11-12% in major repair and overhaul at HAL, and 13-14% AOG "awaiting major systems". Spares: the norm is about 5% of fleet value per year (≈₹3,450 crore), yet IAF spares orders on HAL were under ₹50 crore. HAL Nashik held ₹400 crore of spares; HAL said the IAF orders "piecemeal after defects arise". HAL offered Performance-Based Logistics; the IAF reportedly opposed it because it would weaken the Base Repair Depot structure. HAL proposed stocking five years of spares at 25 Equipment Depot, Nashik. [Ajai Shukla / Business Standard, Oct 2014](https://www.ajaishukla.com/2014/10/government-takes-note-of-su-30mkis-poor.html); [Business Standard](https://www.business-standard.com/article/economy-policy/govt-takes-note-of-su-30mki-s-poor-serviceability-114102300006_1.html). The article also gives 58% in one place, an internal inconsistency.
- [DIRECT, via secondary reports of a Rajya Sabha reply, Mar 2015] Then-RM Parrikar reported technical problems in 35 AL-31FP engines between Jan 2013 and Dec 2014. "Out of total 69 cases in the past three years, 33 cases are due to finding of chips in the oil, 11 due to vibration in the engine and eight because of low pressure of lubricating oil." He attributed the engine trouble to bearing failure, fixed by "better lubrication ..., better fitment of bearings and better quality of oil." He put serviceability at 56-57%, likely to reach 70%. [Hindustan Times via PressReader, 18 Mar 2015](https://www.pressreader.com/india/hindustan-times-delhi/20150318/281998965941493) (seen only as a search summary); [The Wire, 15 Mar 2026](https://m.thewire.in/article/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions). The primary Rajya Sabha answer text was not retrieved.
- [DIRECT, journalism] The Wire (Mar 2026), citing unnamed industry officials, says early AL-31FP units needed overhaul at 300-500 h against a marketed MTBO of about 1,000 h and a total life of about 3,000 h, and that failure intervals rose from about 500 h to about 900 h after modifications. These are single-source and unverified. [The Wire](https://m.thewire.in/article/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions)
- [DIRECT, journalism] A 5-year spares and technical-assistance agreement between HAL, UAC and UEC was signed 17 Mar 2017; it does not cover licence production of critical spares. Retd AVM V.K. Narang: the main problem is "the rapidity of repairs of line-replaceable units and shop-repairable units", not spares supply, and Russian suppliers are reluctant to do quick repairs (about 25% of new-item cost). HAL's after-sales role covers snag disposition, on-site repair, modification, upgrades and obsolescence management. [Defense News, 22 Mar 2017](https://www.defensenews.com/air/2017/03/22/india-s-sukhoi-fleet-faces-problems-despite-russian-spare-parts-deal/)
- [DIRECT] An India-Russia Inter-Governmental Agreement for manufacturing Russian-origin spares in India was signed 19 Sep 2019. Twenty-four lines were issued to Space Era, Hyderabad (a JV with JSC KRET). Sources: [MoD Annual Report 2023-24, p. 164](https://mod.gov.in/sites/default/files/AR_2023-24-new-23-9-2025_0.pdf); [MoD Annual Report 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf)
- [DIRECT] Mar 2025, IAF to Parliament (Hindi; my translation): the Su-30 is today the IAF's largest fleet and will remain its mainstay. Its capability will be raised through an indigenous upgrade executed by HAL, DRDO and private industry under IAF supervision, and the plan is at the final approval stage. Source: 8th Report (18th LS), DFG 2025-26, para 2.19, presented 17.3.2025. [PDF](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_8.pdf?source=loksabhadocs)
- [DIRECT] A contract for 12 more Su-30MKI was signed with HAL on 12 Dec 2024. Source: 12th Report (18th LS), Action Taken on DFG 2024-25, presented 07.08.2025. [PDF](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_12.pdf?source=loksabhadocs)
- [DIRECT] CAG 34/2014: to avoid Su-30MKI AOG for want of brake parachutes, the IAF imported 100 parachutes in 2011 at about 10x the indigenous (OPF Kanpur) cost. Source: CAG Report No. 34 of 2014 (Air Force & Navy) ch. 3, pp. 52-53. [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014_Chapter_3.pdf)

**HAL Tejas Mk1 / Mk1A**
- [DIRECT] The CAG performance audit of the LCA (Report No. 17 of 2015, tabled 8 May 2015) made the following findings:
  - Prototype and LSP aircraft "had low serviceability due to delay in snags analysis, slow recovery of aircraft from rectification, shortage of critical LRUs at flight hangar, aircraft being used as test rigs, large number of unproductive sorties" (para 4.2.2, pp. vii and 40-41).
  - Average sorties per month were 1-5 against the 22 desired by ADA. Aircraft were not flown for test on 18,891 aircraft-days. From first flight to IOC, the fleet logged 2,441 sorties and 1,560.80 h across 13 aircraft, with average sortie length 30-51 min (Annexure-III, p. 63).
  - IOC came with 53 waivers and concessions: 20 permanent waivers "for ASR parameters which the current configuration of LCA Mk-I with GE-F-404-IN20 engine cannot achieve" and 33 time-bound concessions (para 2.3, pp. 13-14). The fuel-system deficiency is a permanent waiver, so "all the LCA Mk-I would have deficiencies in Fuel System" (para 4.2.3, p. 42).

  [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf), [landing page](https://cag.gov.in/en/audit-report/details/1718)
- [DIRECT] Repair base. "LCA comprises 344 Line Replaceable Units (LRUs). Of these, 90 LRUs were considered non-repairable." ROH capacity existed at HAL for 185; for the remaining 69, HAL planned a Long Term Repair Agreement (LTRA) for 29, ROH establishment for 39, and deletion of one. Completion was promised by Dec 2016, and the work was still incomplete in Jan 2015. The ASR makes the manufacturer responsible for defect investigation and ROH of aircraft, engine and components; "during the interim period ... repair and servicing of all rotables will be manufacturer's responsibility." Source: CAG 17/2015 para 4.4, p. 47.
- [DIRECT] Support package in the 20-aircraft IOC contract (Mar 2006, ₹2,812.91 crore after amendment): spares, Tools, Testers and Ground Equipment (TTGE), training devices and maintenance simulators, **four reserve engines, an engine support package, and an engine test bed** (built at Sulur by Dec 2011 for ₹46 crore). HAL held ₹521.14 crore of warranty-expired inventory (Engine Division ₹443.16 crore). Retro-modification of 20 LRU types by OEMs was needed. Source: CAG 17/2015 para 4.6.1, pp. 52-53.
- [DIRECT] Indigenous content was about 35% against the 70% claimed (Jan 2015). Imports included the engine, MMR, radome, FCS actuators, MFDs, "electrical generators, RLG", and "heat exchangers, pumps, sensors". Source: CAG 17/2015 para 3.1 and Annexure-II, pp. 37 and 62.
- [DIRECT] Engine supply. The contract for 99 F404-IN20 engines for 83 Mk1A (Aug 2021) was about two years late: GE was due to start around Mar/Apr 2023 and promised Mar/Apr 2025. [ThePrint, 29 Oct 2024](https://theprint.in/defence/india-imposes-penalties-on-ge-for-2-yr-delay-in-delivery-of-tejas-engines-delivery-to-start-by-april/2333021/). MoD to Parliament: Mk1A "delivery of aircraft is delayed due to Design and Development (D&D) activities and delivery of GE-404 engines from M/s GE" ([12th Report 18th LS, Aug 2025](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_12.pdf?source=loksabhadocs)). Apr 2026: 20 Mk1A jets ready but "only five" engines delivered; Mk1A deliveries about two years behind ([The Tribune, 2 Apr 2026](https://www.tribuneindia.com/news/india/iafs-grounded-tejas-jets-to-resume-flying-next-week-after-software-fix-says-hal-chairman/)). [Secondary] Wikipedia reports 10 IN20 engines delivered by Aug 2026, one engine failing acceptance parameters on 26 Jun 2026 (citing New Indian Express), and a 7 Nov 2025 deal for 113 more engines ([Wikipedia: GE F404](https://en.wikipedia.org/wiki/General_Electric_F404)).
- [DIRECT] Fleet-wide grounding. After a 7 Feb 2026 take-off/runway excursion, the IAF's **34** Tejas were grounded until about 8 Apr 2026. HAL chairman D.K. Sunil described "a software glitch in the brake system". A joint IAF-HAL-CEMILAC committee cleared the corrected software, and the checks covered undercarriage metallurgy, the "electro-magnetic braking system" and the onboard software. [The Tribune, 2 Apr 2026](https://www.tribuneindia.com/news/india/iafs-grounded-tejas-jets-to-resume-flying-next-week-after-software-fix-says-hal-chairman/); [Aerospace Global News, 19 Mar 2026](https://aerospaceglobalnews.com/news/tejas-incident-software-fault-iaf/). Wikipedia gives 36 jets including 6 trainers and places the event at Naliya; this is unverified and conflicts with the Tribune's 34. [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas)
- [DIRECT] Losses: 12 Mar 2024 near Jaisalmer. Initial reports pointed to engine failure; officials later said an oil-pump failure may have led to engine seizure. The final court-of-inquiry finding was not found. [ANI, 12 Mar 2024](https://www.aninews.in/news/national/general-news/initial-reports-point-towards-engine-failure-as-cause-behind-lca-tejas-crash-in-jaisalmer-defence-officials20240312200621/) (seen as a search summary); [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas). 21 Nov 2025, Dubai Airshow, fatal; the cause was still under investigation in late 2026. [newsonair (AIR)](https://newsonair.gov.in/iaf-tejas-jet-crashes-at-dubai-air-show-pilot-wing-commander-syal-killed/) (search summary)
- [DIRECT] Programme scale: 83 Mk1A contracted 25 Jan 2021 (₹36,468.63 crore); 97 more contracted 25 Sep 2025, with deliveries Sep 2027 to Sep 2033. Planned total of 220 Tejas (Mk1 + Mk1A). A third line at HAL Nashik (8/yr) brings capacity to 24/yr. Sources: [2nd Report 18th LS](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs) para 2.24; [MoD Annual Report 2025-26](https://mod.gov.in/sites/default/files/Annual-report-2025-26_0.pdf) pp. 61 and 146.
- [DIRECT] MoD to Parliament (Dec 2024): Tejas "is designed on LRU concept which facilitates easy maintenance and isolated repair of faulty LRUs without affecting the aircraft's flight line availability." Source: 2nd Report 18th LS, para 2.23(e).

**MiG-21 (including Bison upgrade, CAG code 'DD') and MiG-27**
- [DIRECT] Bison serviceability, Table 2.9:

  | Year | Serviceability % | AOG % | Flying-task shortfall % |
  |---|---|---|---|
  | 2004-05 | 51.52 | 23.02 | 55.70 |
  | 2005-06 | 41.32 | 37.34 | 51.34 |
  | 2006-07 | 42.19 | 25.16 | 36.28 |
  | 2007-08 | 47.16 | 29.41 | 29.09 |
  | 2008-09 | 44.83 | 33.27 | 34.26 |

  Air HQ attributed this to low MTBF of upgraded systems: the 'BB' radar (footnote: KOPYO), VRS, INGPS and the "'LL' B" (footnote: "Flight data acquisition and processing unit"). The OEM's repair support for radar aggregates was poor, and MoD cited "failure of items before their expected life." The HAL 'D'-level facility was "limited to diagnostic and repair"; ToT for ROH of aggregates "could not materialize". Calendar life was extended to 40 years; 125 aircraft were upgraded between 1998 and 2008. Source: CAG 38/2015 para 2.4, pp. 67-83. Identification as MiG-21 Bison: HAL Nasik built 220 'D' to 1987, 'D' inducted 1978, KOPYO radar, and the text names the "Bison aircraft" (p. 77).
- [DIRECT] Of IAF accidents since 1970, 999 aircraft were lost by Aug 2011. Cause shares were technical defect 39.5%, aircrew error 39.0%, servicing error 1.6%, HAL 0.6%, and bird hit 9%. "476 MiG Aircraft so far have met with accidents and the remaining fleet is 470." MoD: "majority of technical defect accidents pertain to old technology aircraft ... especially aero engine malfunction in MiG-21 and MiG-27." IAF: "Russian are extremely reluctant to share certain information ... On the MiG-29 also ... We actually struggle to get the information." Source: 12th Report (15th LS), DFG 2011-12, paras 4.12-4.16, presented 03.08.2011. [PDF](https://sansad.in/getFile/lsscommittee/Defence/15_Defence_12.pdf?source=loksabhadocs); follow-up [14th Report (15th LS)](https://sansad.in/getFile/lsscommittee/Defence/15_Defence_14.pdf?source=loksabhadocs)
- [DIRECT] Over 2010-13 there were 37 flying accidents. Of the 22 fighter accidents, 15 (68%) were MiG variants: MiG-21 T96 (5), MiG-21 Bis (5), MiG-27 (3) and MiG-29 (2). By cause: accidents HE 19 and TD 18; incidents HE 156, **TD 779** and bird strike 357. Incidents rose from 449 (2010-11) to 568 (2012-13). Source: CAG 34/2014 ch. 3 para 3.8.7, pp. 88-92. [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014_Chapter_3.pdf)
- [DIRECT] Accidents in 2017-22 with recorded causes: 34 in total. MiG-21 had 9 (TD present in 5), MiG-27 had 3 (TD 2, HE(S) 1), Jaguar 3 (TD, HE+TD, HE(A)), MiG-29 1 (TD, 08.05.2020), Su-30 2 (both HE(A)) and Mirage 1 (under investigation). The accident rate fell from 0.93 (2000-05) to 0.27 (2017-22) and 0.20 (2020-24). Source: 2nd Report 18th LS, paras 2.35-2.36. [PDF](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs); [ThePrint summary, 20 Dec 2024](https://theprint.in/defence/more-than-50-of-34-iaf-plane-crashes-in-2017-2022-due-to-human-error-says-parliamentary-report/2413245/)

**Jaguar**
- [DIRECT] Against 108 autopilots required (1997), 35 were procured from Thales (Aug 1999, €7.952 M) and only 18 were integrated by Mar 2017, and these work sub-optimally because of Auto Pilot Electronic Unit (APEU) malfunctions. The autopilot specification called for a useful life of at least 25 years and **MTBF 5,000 h**. Four pilots and three Jaguars were lost to disorientation between Jan 2000 and Mar 2008. The IAF held 117 Jaguars in Oct 2016. Source: CAG Report No. 24 of 2017 (Air Force), para 2.2. [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2017/Report_No.24_of_2017_-_Compliance_audit_Union_Government_Air_Force_Reports_of_Defence_Services.pdf)
- [DIRECT, journalism, unverified] Internal IAF assessments put legacy Jaguar serviceability at 50-60%. [The Wire](https://m.thewire.in/article/security/fatal-jaguar-crash-again-raises-concerns-over-iafs-legacy-fleet) (seen only as a search summary)

**Mirage 2000**
- [DIRECT] Contract Oct 1982; squadron service from 1984. A ToT contract for **depot-level maintenance of the M53-P2** (SNECMA) was signed Aug 1993, and ToT for HP turbine blade repair in Aug 2006. An MT-41 grinding machine (€807,395) reached **4 BRD** in Apr 2009, but the repair process was never validated. As a result, 1,820 repairable blades accumulated (2010-13), 788 were shipped to the OEM, and 1,032 were still awaiting repair. Air HQ: the "Mirage fleet is going to be in operation for next 20-30 years." Source: CAG 34/2014 ch. 3 para 3.1, pp. 41-42. [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014_Chapter_3.pdf)
- [DIRECT] Design and development of burner rings for Mirage-2000 engines was contracted to an Indian vendor under TDF. Source: [MoD Annual Report 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf), Atmanirbhar section.
- No primary serviceability figure was found for the Mirage 2000. Press calls it a high-serviceability fleet, which is not audit evidence.

**MiG-29**
- [DIRECT] Russian reluctance to share MiG-29 failure information (2011 testimony above). Accidents: 2 in 2010-13, and 1 TD accident on 08.05.2020. No primary serviceability figure was found.

**Rafale**
- [DIRECT] The 2007 MMRCA RFP required long-term maintenance support "to ensure the operational availability (more than 75 per cent)". The 36-aircraft IGA (2016) bundles an Engineering Support Package (aircraft, engine and avionics spares; 12 spare engines) with **Performance-Based Logistics** for an initial 5 years capped at a flying-hour total. Source: CAG Report No. 3 of 2019 (Performance Audit, Capital Acquisition in IAF), Part B, paras (ii)-(iii), pp. 130-132. [PDF (mirror)](https://www.humanrightsinitiative.org/download/C&AG-AirForce-CapitalAcq-PerfAudit-Report3-2019.pdf); [PRS summary](https://prsindia.org/policy/report-summaries/capital-acquisition-indian-air-force)
- [DIRECT] An IAF Air Commodore (AOC, AF Station Kanpur, 2017) wrote: "In-flight health monitoring systems are the essential feature of all new acquisitions in IAF eg. C130J-30, C-17 and Rafale." [JOAST 69(1A) 2017, BN Kumar](https://joast.org/index.php/joast/article/view/217)

### Inferences
- The audited Su-30MKI pattern of roughly 55-60% serviceability with 11-15% AOG, persisting from 2006 to at least 2015, is the clearest public quantification of the problem statement problem. The audit's causal chain is long repair cycles (Cat 'D' aggregates going to the OEM), ROH capability built late at HAL, and spares bought piecemeal. That chain is a cross-agency data and logistics integration failure, not an aircraft-design failure. [ASSUMPTION: interpretation; validate against later CAG Air Force reports from 2016-2025, not retrieved]
- The 20% / 11-12% / 13-14% breakdown (1st/2nd line, HAL ROH, AOG awaiting systems) is a usable **prior for state-occupancy fractions** in a fleet-availability simulator. [DIRECT for Su-30MKI 2014; TRANSFER to other fleets is an assumption]
- Tejas availability risk is dominated today by **supply-chain and engineering-authority events**: GE engine supply, software defects needing ADA/HAL/CEMILAC clearance, and LRU ROH set-up. Squadron-level wear-out is not the main driver. A Tejas generator should therefore emit software-configuration, modification-state and fleet-grounding events, not only component wear.

### Gaps
- No post-2015 primary serviceability numbers for any fighter fleet were found: no CAG Air Force report 2016-2025 was read, and the Rajya Sabha/Lok Sabha Q&A archive was not reachable by search after the budget ran out. Parrikar's Jan 2017 statement that serviceability had risen to 60% is press-only.
- No public serviceability/MTBF data for Tejas Mk1 squadrons (45 and 18 Sqn).
- No primary serviceability figures for Mirage 2000, MiG-29 or Rafale.

---

## KQ2. Which platform best embodies the PS statement "fragmented and largely reactive maintenance ... data from aircraft health-monitoring systems, technical records, spares and maintenance agencies not adequately integrated"?

### Takeaway
**Su-30MKI** is the strongest documented example of the problem: the largest fleet, CAG-quantified low serviceability, and the most agencies (IAF squadrons, BRDs and EDs, five-plus HAL divisions, Russian UAC/UEC, DARE/BEL and Israeli/French avionics vendors, with OEM data withheld). **Tejas** shows the same fragmentation in an indigenous, data-rich setting (ADA as design authority, ADE, HAL divisions, BEL, GE, Elta/Elbit/Cobham, CEMILAC/RCMA, DGAQA, IAF). Its health-monitoring and BIT architecture is publicly described, which makes "integration of HM, technical records, spares and agencies" demonstrable. For a **data-generator** deliverable, Tejas is the better fit; Su-30MKI is the better *problem narrative*.

### Cited Findings
- [DIRECT, Su-30MKI] Agencies named in primary or credible sources:
  - IAF 1st/2nd line (I-level at squadrons). The CAG footnote reads: "Intermediate maintenance (I-Level) normally under taken at operating squadrons. Depot maintenance (D-Level) are being carried out at Base Repair Depots of IAF or at HAL" (CAG 38/2015 p. 60 fn. 63).
  - HAL divisions for ROH.
  - The Russian OEM for Cat 'D' aggregates (p. 63).
  - DARE/BEL for the RWR (pp. 58-60).
  - HAL Nashik spares and 25 ED Nashik ([Shukla 2014](https://www.ajaishukla.com/2014/10/government-takes-note-of-su-30mkis-poor.html)).
  - UAC/UEC for spares and technical assistance ([Defense News 2017](https://www.defensenews.com/air/2017/03/22/india-s-sukhoi-fleet-faces-problems-despite-russian-spare-parts-deal/)).
  - Space Era/KRET JV under the IGA ([MoD AR 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf)).
  - A 2003 "'C' aircraft Project Development and Monitoring Cell" at Air HQ was set up to be a "single point agency to maintain an interface with all the vendors" (CAG 38/2015 Annexure-V).
- [DIRECT, Su-30MKI] Data-flow evidence of fragmentation:
  - FBW failure data had to be "sent to" the OEM for study (CAG 38/2015 p. 61).
  - Russian reluctance to share failure information ([12th Report 15th LS](https://sansad.in/getFile/lsscommittee/Defence/15_Defence_12.pdf?source=loksabhadocs)).
  - Spares ordered only after defects arise ([Shukla 2014](https://www.ajaishukla.com/2014/10/government-takes-note-of-su-30mkis-poor.html)).
- [DIRECT, Tejas] Agencies:
  - ADA is the nodal design agency, with HAL the principal partner and "various work centres spread across the country" ([ADA LRU indigenisation notice, Dec 2022](https://www.ada.gov.in/images/LRU.pdf)).
  - ADE (FCS/DFCC, ADC) ([JOAST, Kala 2015](https://joast.org/index.php/joast/article/view/317)).
  - BEL (DFCC production) ([Wikipedia, citing New Indian Express 2013](https://en.wikipedia.org/wiki/HAL_Tejas)).
  - HAL Lucknow (hydraulic and fuel-sensor LRUs, actuators), HAL Hyderabad (MMR) and HAL Korwa (MFDs) (CAG 17/2015 pp. 25-26, 33-37).
  - GE (engine and engine support package), Elta (radar), Elbit (MFDS, HMDS), Cobham (radome) and VSSC/DALIA (actuators) (CAG 17/2015).
  - CEMILAC and its RCMAs, and DGAQA ([JOAST, Peter Arun et al. 2015](https://joast.org/index.php/joast/article/view/325)).
  - IAF squadrons.
- [DIRECT, Tejas] Of 344 LRUs, 177 are indigenous and 167 bought out from foreign sources; some bought-out items are common with Mirage and Jaguar ([JOAST, CEMILAC 2015](https://joast.org/index.php/joast/article/view/325)). ROH coverage in 2015 was 185 of 254 repairable LRUs, with the rest split between LTRA with OEMs and HAL ROH set-up (CAG 17/2015 p. 47).
- [DIRECT, Tejas] Health-monitoring and record sources exist on board (detail in KQ3/KQ4):
  - DFCC continuous, pilot-initiated and maintenance BIT.
  - ADC BIT with 90% coverage.
  - An onboard Engine Condition Monitoring System that logs engine usage to compute life-usage indices and tracks vibration ([ADA Propulsion page](https://www.ada.gov.in/images/ps.htm)).
  - USMS with dual-redundant processors.
  - MIL-STD-1553B avionics data.
- [DIRECT] IAF-wide record systems exist but are separate: e-MMS (maintenance records, paperless from Apr 2020), IMMOLS (materials, provisioning and forecasting), and "Havai" (IAF-HAL e-portal). Source: [MoD AR 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf), Air Force chapter (see KQ6).

### Inferences
Problem-embodiment scoring, scale 1-5 (my judgement from the cited material):

| Criterion | Su-30MKI | Tejas Mk1/1A | Mirage 2000 | MiG-29 | Jaguar | Rafale |
|---|---|---|---|---|---|---|
| Fleet size / future weight in IAF | 5 (largest, mainstay) | 5 (220 planned) | 2 | 2 | 1 (phase-out) | 2 |
| Documented low availability | 5 (CAG tables) | 3 (prototype availability, grounding, supply delays) | 1 | 1 | 3 (press, CAG autopilot) | 1 |
| Number of maintenance agencies | 5 | 5 | 3 | 3 | 3 | 2 (OEM PBL) |
| Foreign-OEM data opacity | 5 (Russian) | 3 (GE and Israeli LRUs; core indigenous) | 4 | 5 | 3 | 4 |
| Indian ownership of design data (needed to integrate HM data) | 1 | 5 | 1 | 1 | 2 | 1 |
| Public system-level documentation | 1-2 | 4 | 1-2 | 1-2 | 2 | 1-2 |

- Su-30MKI maximises "problem fit". Tejas maximises "solution fit": a credible integrated HM/records/spares data layer is only buildable, and later fieldable, where Indian agencies own the ICDs, BIT definitions and LRU lists. [ASSUMPTION; validate by asking IAF/DSSC mentors which fleet they want the demo framed around]
- A defensible framing for the problem owner: "Tejas-class virtual fighter (F404-IN20) operated inside an IAF maintenance ecosystem whose agency structure and state-occupancy priors are calibrated on audited Su-30MKI data." [ASSUMPTION]

### Gaps
- No public document maps which Tejas data streams (DFCC BIT logs, ECMS, USMS, FDR) are actually downloaded by squadrons, or where they are stored (e-MMS or elsewhere).
- No public description of Su-30MKI on-board monitoring data paths in IAF service (see KQ3).

---

## KQ3. Public documentation by platform: systems, engine, on-board health monitoring/BIT/recorders, data buses, maintenance concept, agencies

### Takeaway
Tejas is by far the best publicly documented IAF fighter at systems level: a sensor range/frame-rate-level FCS paper, LRU-level ADA lists, CAG LRU/ROH counts, and CEMILAC system/LRU/software counts. The Su-30MKI, Mirage 2000 and MiG-29 have only programme-level public information in Indian sources; their recorder and monitoring systems (Soviet/Russian "Tester"-family heritage, French systems) are essentially undocumented in open English literature found here. The IAF maintenance concept across fleets is three-tier O/I/D (1st, 2nd and 3rd/4th line) with hard-time TBO/calendar lives plus engineering life extensions, per CAG and parliamentary testimony.

### Cited Findings

**IAF maintenance concept (cross-fleet)**
- [DIRECT, IAF] "Ist line servicing ('O' level) ... IInd line servicing ('I' level) ... IIIrd & IVth line servicing ('D' level)". O-level is fault detection and isolation to LRU and LRU replacement at the flight line. I-level is fault isolation to SRU within an LRU at the base lab/shop. D-level is repair or overhaul of SRUs "by vendor or Base Repair Depot (BRD) of IAF"; AMCs supplement this. Source: CAG 38/2015 para 2.1.3, p. 20 (AWACS context; the same tiers are defined for the Su-30 at p. 60 fn. 63). [PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)
- [DIRECT, IAF] Hours- and calendar-life-based maintenance with engineering extensions ([41st Report 16th LS](https://sansad.in/getFile/lsscommittee/Defence/16_Defence_41.pdf?source=loksabhadocs), para 3.20). [DIRECT, GTRE] "Hitherto existing method of preventive maintenance is based on fixed TBO ... or ... Total Accumulated Cycles (TAC) concept", and "an engine under service may have less than 20 sensors". [JOAST 69(1A) 2017, Patnaik & Rao, GTRE](https://joast.org/index.php/joast/article/view/235)
- [DIRECT, IAF engine practice] "Engine log books generally record the life and cycles consumed for every component assigned with finite life". For the low-bypass military turbofan studied, one hour is treated as four cycles and blade technical life equals one TBO. About 25% of the engine population was withdrawn unscheduled over 2008-13 (≈5%/yr). [JOAST 66(1) 2014, RCMA(Engines)/HAL](https://joast.org/index.php/joast/article/view/438). The engine is anonymised; it is a twin-spool 40 kN-class afterburning turbofan with single-stage HP and LP turbines. [ASSUMPTION: likely Adour Mk 811 (Jaguar); validate against Adour architecture]
- [DIRECT] Apache attack helicopters in IAF service follow an "On-Condition based maintenance philosophy and therefore requires no schedule Depot level servicing" (MoD reply quoted in CAG 3/2019, Part A, Apache maintenance-ToT paragraph). This shows on-condition maintenance exists in IAF only on newer Western types. [CAG 3/2019](https://www.humanrightsinitiative.org/download/C&AG-AirForce-CapitalAcq-PerfAudit-Report3-2019.pdf)

**Platform matrix** (one row per platform; Tejas detail is in KQ4)

| Platform | Major systems / engine (public) | On-board HM / BIT / recorders (public) | Data bus (public) | Maintenance agencies (public) | Documentation quality |
|---|---|---|---|---|---|
| **Tejas Mk1/1A** | See KQ4. F404-GE-IN20: 19,000 lb (84 kN) thrust class, 153 lb/s, PR 28:1, 1,072 kg, FADEC ([GE data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf)) [DIRECT] | DFCC CBIT/PBIT/MBIT; ADC BIT 90%; sensors self-test before each flight; onboard ECMS (life-usage indices, vibration); USMS; FTI DAS/telemetry/DRU on prototypes; indigenous HUMS for Mk1A in development (initiated 2018-19, vendor selected 2020-21); Mk2 "Aircraft Maintenance Terminal" (ADA AR 2018-22) [DIRECT] | MIL-STD-1553B from FCS to avionics; RS-422 ADC-DFCC; CCDL between DFCC channels [DIRECT] | ADA, ADE, HAL (LCA Div., Lucknow, Hyderabad, Korwa, Engine Div.), BEL, GE, foreign LRU OEMs, CEMILAC, DGAQA, IAF [DIRECT] | High (sensor ranges, frame time, LRU lists) |
| **Su-30MKI** | AL-31FP, 12,500 kgf with afterburner, TVC nozzles; reported MTBO about 1,000 h, total life about 3,000 h ([Wikipedia](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI); The Wire) [DIRECT, secondary] | Quadruplex FBW with channel comparison ([Wikipedia](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)); Wikipedia mentions an on-board HUMS that "can act as an engineering data recorder" (citation not traced) [DIRECT, unverified]. DRDO completed GAT and EMI/EMC tests of an "Advanced Flight Test Data Unit (AFTDU) on Su-30MKI" ([MoD AR 2025-26](https://mod.gov.in/sites/default/files/Annual-report-2025-26_0.pdf), DRDO chapter) [DIRECT]. Soviet manoeuvrable aircraft have used "Tester"-family recorders since 1974, with automated express-analysis of >200 events today ([ru.wikipedia, Бортовой самописец](https://ru.wikipedia.org/wiki/%D0%91%D0%BE%D1%80%D1%82%D0%BE%D0%B2%D0%BE%D0%B9_%D1%81%D0%B0%D0%BC%D0%BE%D0%BF%D0%B8%D1%81%D0%B5%D1%86)) [TRANSFER: Soviet/Russian fighters; MKI-specific recorder fit not confirmed] | Mixed Russian/Indian/French/Israeli avionics (SAGEM Sigma-95 INS, Elbit HUD, DARE RWR, Elta jammer) per [Wikipedia](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI); bus standard not found [DIRECT, secondary] | IAF sqns/BRDs/25 ED; HAL Nashik (aircraft), Koraput (AL-31FP), Lucknow, Hyderabad, Korwa; UAC/UEC; DARE/BEL; Space Era/KRET [DIRECT] | Low (programme/audit level only) |
| **Mirage 2000** | M53-P2 engine; D-level ToT 1993; HPT blade repair at 4 BRD (CAG 34/2014) [DIRECT] | Not found | Not found | Dassault/SNECMA (Safran)/Thales; 4 BRD; HAL (upgrade) [DIRECT for OEM names in CAG fn. 1] | Low |
| **MiG-29** | Not covered in primary sources found | Not found | Not found | Russian OEM (data opacity per 2011 testimony) [DIRECT] | Very low |
| **MiG-21 Bison** | Upgrade systems: KOPYO radar, INS/GPS, RWR, CMDS, SPJ, HUD/MFD, HMSD, VRS, HOTAS (CAG 38/2015 fn. 79) [DIRECT] | A "Flight data acquisition and processing unit" ('LL'B) had low MTBF (CAG 38/2015 p. 76 fn. 99) [DIRECT] | Not found | OEM (Russia), HAL Nasik, IAF ([CAG 38/2015](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)) [DIRECT] | Low |
| **Jaguar** | Thales autopilot (MTBF requirement 5,000 h); DARIN avionics simulators referenced (CAG 34/2014, 24/2017) [DIRECT] | Not found | Not found | HAL, Thales [DIRECT] | Low |
| **Rafale** | ESP + PBL, 12 spare engines for 36 aircraft (CAG 3/2019) [DIRECT] | "In-flight health monitoring systems" ([JOAST 2017](https://joast.org/index.php/joast/article/view/217)) [DIRECT, qualitative] | Not found | Dassault/Safran/Thales PBL; IAF [DIRECT] | Low (commercially redacted) |

### Inferences
- For any platform other than Tejas, a "high-fidelity" generator would rest mostly on [TRANSFER] (Su-27 family, French Mirage literature) and [ASSUMPTION]. For Tejas, many parameters (sensor ranges, redundancy levels, frame times, LRU names, hydraulic pressure, actuator bandwidth) are [DIRECT].
- The F404 family link (Tejas IN20, F/A-18 A-D -400/402, Gripen RM12) means engine-level health-monitoring practice can be borrowed with stated limits. Examples are the F/A-18 IECMS (in-flight engine condition monitoring, critical malfunctions and parts-life tracking; [Wikipedia: GE F404](https://en.wikipedia.org/wiki/General_Electric_F404), citing Jenkins 2000). Limits: the IN20 has a FADEC and different hot-section materials, and Tejas installs a single engine with its own ECMS. [TRANSFER: F/A-18 A-D; details are owned by the engine researcher]

### Gaps
- The Su-30MKI recorder, HUMS and bus architecture is not publicly documented in any primary source found. The Wikipedia HUMS statement needs its original citation.
- Mirage 2000 and MiG-29 IAF recorder and monitoring fits were not found.
- Whether IAF uses on-condition maintenance for any fighter fleet: no primary statement found.

---

## KQ4. HAL Tejas in depth: what is publicly documented at system level (paper by paper and system by system)

### Takeaway
Open sources give enough [DIRECT] detail to parameterise these Tejas data streams:
- FCS redundancy and BIT;
- inertial sensor ranges, bandwidth and resolution;
- air-data transducer ranges and accuracy;
- DFCC frame time (12.5 ms);
- actuator redundancy, 280 bar hydraulics and 9 Hz bandwidth;
- AMAGB loads (2 hydraulic pumps, 1 generator, 1 starter);
- ECS sensor ranges and leak detection;
- brake and NWS LRUs;
- JFS behaviour and failure modes;
- certification inventory (17 systems, 344 LRUs, 33 software systems);
- FTI scale (about 1,500 parameters, 12 telemetry stations);
- engine ECMS functions;
- fuel-system quirks.

ADA's own annual reports add a Mk1A indigenous HUMS in development (initiated 2018-19), brake-wear test points, hot-soak LRU temperature trials and air-data calibration to M1.6.

Missing from open sources: electrical ratings, hydraulic flows, ECS architecture numbers, the FDR parameter list, and NAL's published LCA derivative sets (not accessible here).

### Cited Findings (by source)

**S1. V. Kala (ADE), "Design and Development of Flight Control System for Light Combat Aircraft - Tejas at ADE", JOAST 67(2A), June 2015, pp. 212-218** ([abstract page](https://joast.org/index.php/joast/article/view/317); PDF galley 317/297). All items [DIRECT]:
- **Architecture.** Full-authority quadruplex DFBW "with no back up". The DFCC has four electrically independent channels with independent power inputs, linked by a high-speed **Cross Channel Data Link (CCDL)**. **Four distributed Air Data Computers**, one per channel, connect via **RS-422**. FCS outputs drive the actuators and provide **1553B avionics data**. Primary actuators use DDV drive via PWM amplifiers.
- **Processors.** The DFCC uses the Intel 80960MC 32-bit (text reads "8096 60MC"), with a serial interface link controller state machine for I/O and a transputer-based Serial Peripheral Interface Link for ground test equipment. The DFCC Mk2 uses the MPC5566 and PowerPC 5556, and replaces MIL-38999/1553B front-panel connectors with ARINC-600 "for ease of maintenance".
- **Timing.** OFP functionality "exceeded the execution time limit of more than 75% of **12.5 msec**", which drove offloading of air data to a new quadruplex ADC (80960MC, Xilinx FPGA, **BIT coverage 90%**, MIL-STD-704D/461C/810E, IEEE 1149.1). A multi-rate scheduler runs tasks at different rates. [ASSUMPTION: 12.5 ms is the base minor frame (80 Hz); validate against other ADE sources]
- **Software.** The OFP is in Ada and covers initialisation, input acquisition, redundancy management, control-law computation, output drive, BIT, synchronisation and executive. Features include autopilot, wake protection and "estimation of attitude based on Kalman filter". "Built-in-test features have been upgraded" for squadron operation and maintenance needs. BIT types are continuous, pilot-initiated and maintenance BIT.
- **Sensor redundancy.** Critical rate, acceleration and pilot-command sensors are **quadruplex**. Air-data sensors are **triplex**. Non-inertial items such as probe heater currents are **simplex**. Sensors run BIT from the DFCC before each flight.
- **Rate Sensor Assembly.** Natural frequency 50 Hz. Range ±300°/s roll and ±60°/s pitch and yaw. Resolution and threshold 0.005°/s.
- **Acceleration Sensor Assembly.** Natural frequency 100 Hz. Range ±13 g normal and ±4.5 g lateral. Thresholds 2 mg normal and 0.2 mg lateral. Force-balanced. The Mk2 ASA adds longitudinal sensing.
- **Air data.** Four pressure transducers per ADC: Ps 35-1300 mbar, Pt 35-2700 mbar, Pα/β differentials 35-1500 mbar, accuracy 0.02% FS. AoA and AoSS vanes have quadruplex LVDTs over ±45°. Mk2 adds a second AoSS vane.
- **Actuators.** Elevons and rudder are quadruplex electrical and **dual hydraulic at 280 bar**, with DDV and automatic BIT from the DFCC. Six leading-edge slat actuators (three types) are single-hydraulic with an EHSV and dual electrical control. Airbrakes are open-loop jacks via electro-selector valves. "These servo actuators have a frequency response of **9 Hz** and ... stall load capability of 2-10 tons."
- **Thermal.** The DFCC is forced-air cooled but designed to run **1 h without cooling air**.
- **Rigs.** Engineering Test Station and Advanced ETS (cPCI, RTOS) with fault insertion; Iron Bird; Mini Bird; AIRDATS and AIRDATS-E (RT-Linux) for four ADCs. A Flight Test Unit is used for flutter and **parametric identification** inputs.
- **Track record.** "3000+ flight trials ... flown by more than 30 test pilots without any real failure in FCS System."

**S2. M. Peter Arun, P. Mahuli, P. Jayapal (CEMILAC), "Airworthiness Certification of Tejas ... IOC ... FOC", JOAST 67(2A) 2015, pp. 253-257** ([page](https://joast.org/index.php/joast/article/view/325)). All items [DIRECT]:
- 17 systems and **344 LRUs**: 177 indigenous, 167 bought out (some shared with Mirage/Jaguar, some taken from the IJT). 43 main military standards. **33 embedded software systems**.
- Avionics: "Open Architecture Computer (OAC) as a heart ... driving the parameters from almost all the other systems"; 53 avionics LRUs.
- Mechanical systems: hydraulics, undercarriage, ECS, fuel, propulsion, secondary power, fire extinguishing, escape and brake parachute, with **>150 LRUs**, "mostly software driven and microprocessor based"; "dual redundant processor based utility services management systems".
- FCS performance studied "through post flight data analysis of its parameters across all the 2500 plus development sorties".
- The Release-to-Service Document records "the life limitation of the LRUs" and closure of "Pilot and Maintenance observations". FMECA and fault-tree analysis were used for weapons.
- FOC challenges: "Clearance of long duration sortie in respect of AMAGB and integration of advanced JFS"; "demonstration of reliability figures and clearance of LRUs for Full Life"; brake and brake-parachute refinement; "Closure of all flight and maintenance RFAs ... completeness of Publications and availability of TTGSEs".

**S3. CEMILAC note, "Initial Operational Clearance (IOC) of LCA-Tejas", JOAST 66(1) 2014, pp. 65-66** ([page](https://joast.org/index.php/joast/article/view/441)). [DIRECT] 13 prototypes, 17 test pilots and more than 2,450 flights before IOC with no accident. IOC envelope: 1,350 km/h, 50,000 ft, 6 g and 22° AoA. Performance proven in "Hot weather, Cold weather, High Altitude, Sea level, Desert, Rain water and Lightning condition". Production target 16 aircraft/yr.

**S4. ADA web pages (current site)** [DIRECT]:
- [General Systems](https://www.ada.gov.in/images/gs.htm):
  - Systems covered: microprocessor-controlled brake management system, ECS, fuel, landing gear, hydraulic, secondary power, life support and escape.
  - The **AMAGB** is a "single input, multi output gear box ... drives 4 aircraft accessories ... 2 Hydraulic pumps, 1 Generator & 1 starter unit".
  - Carbon-carbon brakes; 10 types of compact plate-fin heat exchangers.
  - "Hydraulic System is fitted with **9 filters of 6 types**".
  - Gimbal assembly with venturi rated to 650 °C, 37 bar g and 10 mm movement in three axes.
  - Uplocks lock mechanically and unlock hydraulically; the fire bottle discharges on push-button or crash switch.
- [Propulsion](https://www.ada.gov.in/images/ps.htm):
  - Integration of the F404-F2J3 and IN20; JFS upgrade for Mk1 and GTSU-127 for Mk2.
  - "**The Onboard Engine Condition Monitoring System Provides real time Engine Status in the Cockpit and Logs the Engine Usage Data to Compute Life Usage Indices of Life limited Parts. It also tracks Vibration Monitoring System**."
- [Avionics & weapon systems](https://www.ada.gov.in/images/sys.htm):
  - Avionics integrated with FCS, USMS, ECS and weapons.
  - OAC with mission software; "Computer Controlled Utility System & Management System (USMS) with dual redundant Processor".
  - Ada-95 avionics software (IEEE 12207); digital weapon management compatible with Russian, Western and MIL-STD-1760C weapons.
- [IFCS](https://www.ada.gov.in/images/ifcs.htm): "Fail Operational, Fail Safe DFCS and Fail Operational, Fail Safe Air Data System"; carefree manoeuvring; autopilot; ski-jump.
- [Mk1 page](https://www.ada.gov.in/images/mk1.htm): empty 6,560 kg; take-off clean 9,800 kg; external stores 3,500 kg; +9/-3.5 g; ceiling 15 km; "Flying at Leh"; hot and cold weather trials.
- [Facilities](https://www.ada.gov.in/images/GS%20Integration%20facilities.htm): ECS rig ("First ECS integration facility in India"), electrical system rig ("power generation & distribution"), fuel rig ("all attitudes"), undercarriage drop rig, secondary power supply rig, brake dynamometer, and a low-temperature rig for AMAGB soak and motoring.
- [Propulsion facilities](https://www.ada.gov.in/images/PS%20Integration%20facilities.htm): FADEC; JFS "for ground starts and in-flight relight"; engine test bed for up to 50,000 lb thrust.
- [IFCS & flight test facilities](https://www.ada.gov.in/images/Other%20Integration%20facilities1.htm): Iron Bird with hydraulics, undercarriage, real actuators, DFCC, ADCs, OAC and a 6-DOF model. FTI integration rig "Acquires about **1500 parameters** from various aircraft systems". PCM decommutation and "Playback facility for Flight Data Recorder (FDR)".
- [NFTC](https://www.ada.gov.in/images/nftc.htm): "telemetry ground facility with **twelve real time monitoring stations**". On-board FTI = Data Acquisition System + real-time telemetry "for selected parameters" + Data Recording Unit.
- [IV&V](https://www.ada.gov.in/images/ivv.htm): "**7 safety critical and 23 mission critical software systems**"; DO-178B / IEEE 12207.
- [CEF](https://www.ada.gov.in/images/cef.htm): the ECS cools the pilot and avionics and supplies compressed air for cockpit, radar and fuel-tank pressurisation.

**S5. ADA, "Indigenous development of LRUs for LCA-Tejas" (imported LRUs to be indigenised), Dec 2022** ([PDF](https://www.ada.gov.in/images/LRU.pdf); image-only, read by rendering) [DIRECT]. Named LRUs:

| System | LRUs |
|---|---|
| ECS | Bleed-air inlet pressure switch; pressure switch high/low; **temperature sensors -55 to 100 °C and -55 to 300 °C**; hot-air leak detection control box; hot-air leak sensing element |
| FCS | Nose, left and right air-data probes (NADP/LADP/RADP); AoA sensor; LEVCON servo actuator |
| Hydraulics | Park-brake and U/C emergency control cables; emergency U/C selector valve; flow synchroniser; progressive pressure control valve |
| Landing gear | Brake-feel module input potentiometer; NWS free-castor solenoid valve; NWS input potentiometer; NWS position (feedback) potentiometer; **antiskid brake manifold** |

**S6. ADA Annual Reports 2015-16 and 2017-18** ([2015-16](https://www.ada.gov.in/images/Annual_Report_2015-16.pdf), [2017-18](https://www.ada.gov.in/images/Annual_Report_2017-18.pdf)) [DIRECT]:
- 2017-18 flight test:
  - "High AoA **Parameter Identification** sorties"; PIDs with a 725 L centre-line drop tank; supersonic PIDs on the trainer; PID in heavy stores.
  - Auto Low Speed Recovery trials; Limit Cycle Oscillation evaluation.
  - A fuel-system issue: "fuel drop and low fuel warning being posted when climb is initiated with low fuel and high pitch angle at maximum after burner", fixed by modifying the F1A fuel tank and verified in zoom climbs.
  - Hot refuelling "enhancing sortie generation rate".
  - LSP-2 "on ground for over 02 years" before restoration.
  - Taken together: test-fleet downtime is long-tailed. [ASSUMPTION drawn from these anecdotes]
- 2015-16 technology development: AMAGB bearings; "Advanced Subminiature Telemetry System"; JFS Mk2; MEMS pressure transducers and temperature sensors for hydraulics; OBOGS; Cabin Shut-Off Valve of ECS.
- 2015-16 Navy prototype NP2: fuel dump, pressure and hot refuelling, fuel auto-transfer, "Attitude Compensated Fuel System". "ECFM software ... for Enhanced Fuel gauging, F2 Pump Auto Operation, Fuel dumping and Hot refueling" (acronym not expanded in the source); Ni-Cd battery.
- ADA AR 2018-19 to 2021-22 are image-only PDFs. They were OCR'd locally; see S12.

**S7. CAG Report 17 of 2015** ([PDF](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)) [DIRECT], system items:
- **JFS (GTSU-110, HAL Engine Design Bureau).** "critical particularly while operating in the Himalayan Terrain, where the temperature goes below (–) 16 degrees centigrade". The ASR requires 2 consecutive starts; the IAF later wanted **3** (two engine starts plus a dry rollover). The modified GTSU-110 M1 failed to prove 3 consecutive starts in high-altitude trials at **Leh (Jan 2013)** and cold-weather trials (Jan 2014). "Excessive oil consumption by JFS beyond permitted levels" was seen in Bangalore trials (Jan 2014). An M2 modification followed, and the first two series aircraft were delivered with the original JFS (p. 35).
- **FCS actuators.** 13 actuators: 4 elevon, 1 rudder, 6 LE slat and 2 airbrake. Indigenisation via VSSC "DALIA" and a HAL/MTAR/Godrej consortium was delayed, so imported actuators continued (pp. 36-37). Follow-up [PIB 19 Apr 2024](https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2018282): ADA handed HAL the first indigenous **leading-edge actuators and airbrake control module** ("Servo-Valve based electro-hydraulic servo actuators", "high pressure, redundant"), with production at HAL Accessories Division, Lucknow, for the 83 Mk1A.
- **LSP deficiencies.** "Design deficiencies in fuel system, brake management system, brake parachute, undercarriage system"; "Water seepage ... in critical areas of aircraft including cockpit, radar, DFCC, avionics bay"; "fuel leak, cracking of turkey feathers, de-lamination"; "low reliability of critical LRUs like Jet Fuel Starter (JFS), Cockpit Pressure Transducer (CPTCV)". The footnote says the CPTCV "provid[es] position feedback information of flight control surfaces to the cockpit" (p. 42).
- **Weights.** LSP empty weight 6,682-6,802 kg vs 5,365 kg stipulated; basic weight 9,799-9,949 kg vs 8,485 kg (p. 50).
- **Work-centre delays** (pp. 25-26): DFCC (ADE) 100 months late; hydraulic system LRUs (HAL Lucknow) 93 months; fuel-system sensor and hydraulic LRUs (HAL Lucknow) 58 months.
- **Kaveri (GTRE).** Sanctioned 1989; reached 70 kN vs 81 kN required and 1,235 kg vs 1,100 kg; sanction rose to ₹2,839 crore and ₹2,020 crore had been spent by Jan 2015. ADA "would continue to depend on GE imported engine" (p. 30). Prior audit: Report 16 of 2010-11, para 5.1.

**S8. Other Tejas-relevant items** [DIRECT unless noted]:
- Mk1A DFCC (first flight Feb 2024): "Quadraplex Power PC based Processor, high speed autonomous state machine based I/O controller ... DO178C level-A". [Ajai Shukla quoting MoD, Feb 2024](https://www.ajaishukla.com/2024/02/tejas-fighter-flies-with-new-digital.html)
- Mk1 uses LOX; Mk1A uses OBOGS ([Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas), citing MoD AR 2023-24) [DIRECT, secondary].
- Internal fuel 2,458 kg (3,060 L); drop tanks 2 × 1,200 L, 800 L and 725 L; maximum take-off 13,500 kg. [DIRECT, secondary: Wikipedia specification table, not primary]. ADA AR 2017-18 independently confirms a 13.5 t AUW take-off demonstration and the 1,200 L and 725 L tanks.
- Hot refuelling said to shorten turnaround by 30% ([Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas), citing FlightGlobal 2018/2019) [DIRECT, secondary].
- "Integrated health-monitoring system" ([Wikipedia](https://en.wikipedia.org/wiki/HAL_Tejas), citing K.K. Khera, *Combat Aviation*, 2020) [DIRECT, secondary].
- DIAT Pune developing a HUMS for Tejas Mk-II (Indian Express, 13 Aug 2011, cited by Wikipedia; [URL](http://archive.indianexpress.com/news/diat-system-soon-to-monitor-inflight-health-of-tejas-mkii/831436/), which could not be opened) [DIRECT, unverified].
- **MIL-STD-1553B practice at ADE** ([JOAST 63(4) 2011, Neeta Trivedi, ADE](https://joast.org/index.php/joast/article/view/598)). Uses "data from a typical combat aircraft" from "a developmental programme" with cockpit displays. Example ICD message: LRU → Bus Controller "Gives health status" at **12.5 Hz**, with words for link status, port status, memory status and device temperature; 4 minor frames per major frame. [ASSUMPTION: the programme is LCA (ADE author, glass-cockpit developmental programme); validate with ADA/ADE]

**S9. Engine F404-GE-IN20 and its F404-family link** [DIRECT] from the [GE F404 family data sheet](https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf):

| Variant | Thrust | Airflow | Pressure ratio | Weight |
|---|---|---|---|---|
| IN20 | 19,000 lb / 84 kN | 153 lb/s | 28:1 | 2,365 lb / 1,072 kg |
| RM12 (Gripen) | 18,100 lb / 80.5 kN | 152 lb/s | 27:1 | — |
| -402 (F/A-18C/D) | 17,700 lb / 78.7 kN | 146 lb/s | 26:1 | — |

The IN20 has "GE's latest hot section materials ... as well as a FADEC". Prototypes used ten F404-F2J3 engines ([Wikipedia: GE F404](https://en.wikipedia.org/wiki/General_Electric_F404)) [DIRECT, secondary]. Engine-health data detail is cross-linked to the engine researcher.

**S10. NAL system identification (Jatinder Singh, Girija G., Raol)** [NOT RETRIEVED]. The DSJ and NAL-IR hosts did not resolve, and the search budget was exhausted. Indirect evidence: ADE built a Flight Test Unit "required to evaluate ... parametric identification" (S1), and ADA ran dedicated PID sorties across the envelope (S6). The NAL derivative tables, data-compatibility checks and sampling rates remain unverified.

**S11. Flight test instrumentation** [DIRECT] (S4 NFTC and facilities): about 1,500 parameters; DAS + telemetry + DRU; 12 monitoring stations; PCM decom; FDR playback. ADA AR 2015-16: "Advanced Subminiature Telemetry System". No sampling rates were found. [TRANSFER: the Hansa-3 research aircraft recorded at 50 Hz ([JOAST 67(2A), Kumar & Ghosh](https://joast.org/index.php/joast/article/view/313)); this is not LCA and only indicates Indian flight-test practice]

**S12. ADA Annual Reports 2018-19 to 2021-22** (image-only PDFs, read by local OCR; OCR text in `research_sources/indian_fleet/ada/ADA_AR_*_ocr.txt`). Sources: [2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf), [2019-20](https://www.ada.gov.in/images/Annual_Report_2019-20.pdf), [2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf), [2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf). All items [DIRECT]:
- **Indigenous HUMS for Tejas Mk1A.**
  - 2018-19 and 2019-20, in the LCA AF Mk1A section: "Development of Indigenous HUMS has been initiated. Design studies have been completed."
  - 2020-21: "Commercial process for vendor selection has been completed and Purchase Order is being placed."
  - 2021-22: "HUMS development to meet Mk1A requirements is being initiated."
  - Mk1 public sources describe BIT and ECMS but no HUMS. A HUMS is a Mk1A-era addition, still in development in 2022.
- **Mk2 maintenance data path.** "Model of aircraft maintenance terminal (AMT) has been finalized". Stores coding is configurable through the Large Area Display, Back-up Display Unit or **Aircraft Maintenance Terminal (AMT)**. "Location and envelope of **Environmental Control and Fuel Monitoring (ECFM)** unit was finalised". This expands the ECFM acronym seen in the 2015-16 Navy report (2021-22).
- **Hot-weather trials.** At Jaisalmer, PV-6 and SP-6 hot-soaked at **39-42 °C**, then flew "low level high speed runs to assess the temperature (rise) of specific LRUs" (2018-19).
- **Fuel.** "Zoom climb ... at fuel remaining less than 1200 Kg, pitch up >40° ... towards resolving low fuel warning/drop in F1/F2 tank contents during high pitch climb with max after burner" (2018-19).
- **Higher-capacity DC fuel pump** "for improved performance during in-flight engine wind mill relight", flight-tested on LSP3 (2020-21).
- **Brakes.** Reject-take-off trials at high mass with "50% naturally worn out brake pads ... up to 90%" (2018-19); RTO demonstrated "with brake wear out condition at 70% and 90%" (2020-21). This is useful ground truth for brake-wear degradation modelling.
- **JFS.** "JFS GTSU 110M2 (with self contained lubrication system) ... Each Engine ground run encompassed three successive engine starts ... and oil consumption assessed" (2018-19). It is a continuing project: "JFS with self contained oil tank (GTSU 110M2)" (2019-22).
- **FCS.** "New DFCC Version 7307 featured full envelope Nz clearance 8.5 g subsonic / 6 g supersonic"; -3.5 g flown (2018-19). PID sorties to **24° AoA** (2019-20). "Air data calibration sorties ... on LSP8 aircraft (up to M1.6)"; "Assessment of static port corrections in flight for the Air Data Computer" (2021-22).
- **Reliability work-packages.**
  - "Design Modification of Digital Module of Air Data Computer (ADC) towards improvement in reliability" and its re-qualification (2019-22).
  - "MEMS ... Pressure Transducers & Temperature sensor for Hydraulic system".
  - "Fuel Gauging Probe P/N 188100000, Issue-4".
  - Temperature sensors for ECS.
  - AMAGB bearings and castings; "Cabin Pressure Control System (CPCS) of ECS".
  - Carbon brake disc (needle-punched preform).
  - "Feasibility studies to reduce wiring requirements of telemetry during flight tests".
  - Mk2 propulsion: an "Engine Gear Box (EGB) - Power Take Off (PTO) - AMAGB critical speed margin issue was resolved" (2021-22).
- **Support model.** ADA projects for "Aircraft and Facility Maintenance for LCA AF Mk1 (Tejas)" for its test fleet (2019-22).

### Inferences (what the generator can parameterise directly)

| Stream | Basis |
|---|---|
| FCS sensor channels: 4× rate, 4× acceleration, 3× air data (Ps, Pt, Δp), 4× AoA/AoSS LVDT, with stated ranges, bandwidths and thresholds | [DIRECT] |
| DFCC minor frame 12.5 ms (80 Hz) | [ASSUMPTION; validate] |
| Cross-channel monitoring and voting, CBIT/PBIT/MBIT records | [DIRECT existence; logic is ASSUMPTION] |
| Hydraulics: two systems, 280 bar, AMAGB-driven pumps, 9 filters (delta-P and clog indicators are an ASSUMPTION) | [DIRECT except as noted] |
| AMAGB states: generator, hydraulic pumps and starter; JFS start events with oil consumption, success/failure, and cold/altitude dependence | [DIRECT] |
| ECS temperature and pressure switches, hot-air leak detection | [DIRECT] |
| Brakes: antiskid manifold, brake-feel potentiometer, NWS position | [DIRECT] |
| Engine ECMS: usage logging, life-usage indices, vibration | [DIRECT existence; parameters from engine researcher via TRANSFER] |
| Fuel: tank and pump naming (F1A, F2); attitude-compensated gauging; known low-fuel-warning artefact at high pitch with maximum afterburner | [DIRECT anecdote] |
| 1553B health-status words at 12.5 Hz | [ASSUMPTION re LCA] |
| LRU master list of about 344 entries with repairability classes (90 non-repairable, 185 HAL ROH, about 69 OEM/LTRA); a full list is not public, but the class counts are | [DIRECT counts] |

Still not public, so must come from [TRANSFER: F/A-18 A-D / Gripen C/D / MIL-STDs] or [ASSUMPTION]: electrical system ratings, hydraulic flow and reservoir behaviour, fuel quantities by tank, ECS bleed-pressure schedule, and the FDR parameter list.

### Gaps
- Electrical power system (generator kVA, AC/DC buses, TRUs, battery): not found beyond "generator imported" (CAG Annex II) and the AMAGB drive (ADA).
- Hydraulic system flow, reservoir and accumulator data, and whether there are two fully independent systems: not explicitly stated (the dual-hydraulics statement covers primary actuators only).
- Fuel system tank capacities and layout from primary sources; FADS work on LCA: not found.
- Tejas FDR or crash-survivable recorder type, parameter list and sampling: not found.
- NAL LCA parameter-estimation papers (derivatives, data rates): not accessible (DNS failure; search budget exhausted). This is the highest-value follow-up.
- Shodhganga, IISc and IIT theses on LCA systems: not searched (budget).
- Tejas Mk1A HUMS: scope, sensors, vendor and data format are not public beyond ADA's "initiated / vendor selected / PO being placed" (S12).

---

## KQ5. How do Indian operating conditions (hot/humid coastal bases, high altitude such as Leh/Thoise, desert dust, monsoon, salt) affect maintenance and availability, per public sources?

### Takeaway
Public sources tie Indian conditions to four concrete, modellable effects:
- **cold/high-altitude engine-start capability** (Tejas JFS at Leh);
- **heat soak raising LRU temperatures** (Tejas hot-weather trials at 39-42 °C, Jaisalmer);
- **compressor fouling from dirt/carbon "common ... in the Indian environment"**, recoverable by compressor wash (+3-5% thrust);
- **water ingress** into avionics bays during all-weather trials.

Plus high bird-strike incidence and limited night operations at Leh/Thoise. Salt/coastal corrosion and monsoon effects on fighter availability are documented only generically (qualification standards), not as field statistics.

### Cited Findings
- [DIRECT, Tejas] The JFS is critical "in the Himalayan Terrain, where the temperature goes below (–) 16 degrees centigrade". The JFS failed the 3-consecutive-start requirement in high-altitude trials at **Leh (Jan 2013)** and cold-weather trials (Jan 2014). [CAG 17/2015, p. 35](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf). The GTSU 110M2 later demonstrated three successive starts per ground run ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)). ADA lists "Flying at Leh" ([ADA Mk1 page](https://www.ada.gov.in/images/mk1.htm)).
- [DIRECT, Tejas] Hot-weather trials at Jaisalmer: hot soak to 39-42 °C, then low-level high-speed runs "to assess the temperature (rise) of specific LRUs". [ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf)
- [DIRECT, Tejas] "Water seepage observed during the flight testing to prove all weather clearance, in critical areas ... cockpit, radar, DFCC, avionics bay, etc. which required design solutions." [CAG 17/2015, p. 42](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf)
- [DIRECT, Tejas] System performance was demonstrated in "Hot weather, Cold weather, High Altitude, Sea level, Desert, Rain water and Lightning condition" ([JOAST 66(1) 2014](https://joast.org/index.php/joast/article/view/441)). Outstation trials included hot weather, cold weather, high altitude and sea level ([JOAST 67(2A) 2015, CEMILAC](https://joast.org/index.php/joast/article/view/325)). FOC was still to demonstrate "High altitude Cold weather, High Altitude Hot weather, Low altitude high speed run in hot weather" (same).
- [DIRECT, IAF engine, likely Adour; see KQ3]
  - "The heavy carbon / dirt deposits on compressor aerofoil are a common phenomenon for the engines operated in the Indian environment. Hydraulic oil leak from flap / rear selector bay finding way into the air intake ... aggravated the process." Remedy: compressor wash at regular intervals. 14% of investigated withdrawals were for low thrust; 25% for high JPT; about 8% for surge, including FOD-induced surge. [JOAST 66(1) 2014, RCMA(Engines)/HAL](https://joast.org/index.php/joast/article/view/438)
  - "3-5% improvement in thrust due to compressor wash"; about 15% of premature withdrawals for low thrust and a similar number for not meeting slam acceleration; EGT is "recorded in the Flight Data Recorder" and is the health parameter in the absence of thrust measurement. [JOAST 68(4) 2016, RCMA(Engines)/HAL](https://joast.org/index.php/joast/article/view/344)
  - [TRANSFER: IAF Adour-class engine → F404-IN20] The environmental fouling mechanism is engine-agnostic (dust, ambient). Fouling rates differ with engine design and wash practice. Validate with Tejas/F404 engine shop data if obtainable.
- [DIRECT, Su-30MKI, journalism, single source] Unnamed industry officials say the AL-31FP "was never designed for the extreme heat and demanding operational environments" in India. [The Wire, Mar 2026](https://m.thewire.in/article/security/assam-su30mki-crash-challenge-adapting-fighter-demanding-conditions)
- [DIRECT, IAF] Bird strikes caused no accidents in 2010-13 but 357 incidents (vs 779 technical-defect incidents) ([CAG 34/2014 p. 92](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014_Chapter_3.pdf)). Bird hits accounted for 9% of accidents since 1970 ([12th Report 15th LS](https://sansad.in/getFile/lsscommittee/Defence/15_Defence_12.pdf?source=loksabhadocs)). MoD measures include an ornithology cell, bird surveys and a bird lab at the Institute of Flight Safety (same report, para 4.23).
- [DIRECT, IAF] All 52 operational bases can conduct night landings, but Leh, Thoise and Barrackpore allow only limited night operations with mobile lighting or gooseneck flares. [ThePrint summary of the Standing Committee report, 20 Dec 2024](https://theprint.in/defence/more-than-50-of-34-iaf-plane-crashes-in-2017-2022-due-to-human-error-says-parliamentary-report/2413245/)
- [DIRECT, HAL actuators] HAL Lucknow environmental qualification for flight-control and utility actuators covers high/low temperature, humidity, **salt fog**, altitude, icing/freezing and **blowing sand** (MIL-STD-810F). The cylinder bore and rod are chrome-plated "to resist wear due to accumulated sand and dust through end glands". Rotorcraft actuators must qualify for 20 million endurance cycles (ARP1281) and 1 million impulse cycles (ARP1383); this is a helicopter figure, not Tejas. [JOAST 69(1A) 2017, Agarwal et al., HAL ASE R&DC Lucknow](https://joast.org/index.php/joast/article/view/211)
- [DIRECT, base geography] The 7 Feb 2026 Tejas incident was at Naliya (coastal Kutch); the aircraft overshot into "a mud patch softened by rain". [Wikipedia: HAL Tejas](https://en.wikipedia.org/wiki/HAL_Tejas) [secondary]

### Inferences
- Generator hooks justified by Indian sources:

  | Hook | Basis |
  |---|---|
  | Base-dependent ambient temperature/pressure driving JFS start success and oil consumption | DIRECT, Leh |
  | LRU temperature rise with hot soak | DIRECT, Jaisalmer |
  | Compressor fouling state with periodic wash recovery of 3-5% thrust | TRANSFER from Adour-class |
  | Moisture-ingress fault modes in avionics bays during monsoon | DIRECT anecdote; rates are ASSUMPTION |
  | Bird-strike incident process | DIRECT counts |
  | Salt-fog corrosion as a slow degradation of actuators and connectors at coastal bases | ASSUMPTION; validate with BRD defect data |

- Desert-base dust (Jaisalmer, Naliya, Jodhpur) and high-altitude bases (Leh, Thoise) are the two Indian-specific operating corners most clearly evidenced in public Tejas test literature. [ASSUMPTION about relative importance]

### Gaps
- No public field statistics linking coastal humidity or salt (e.g., Sulur, Naliya, Thanjavur, Jamnagar) or the monsoon to fighter AOG rates.
- No public Tejas or F404 compressor-wash interval or fouling data from Indian service.

---

## KQ6. What public information exists on IAF/MoD maintenance information systems and digitisation (IMMOLS, e-maintenance, AFNET, HAL MRO digitisation, iDEX/DRDO predictive-maintenance challenges, IAF PHM/HUMS initiatives)?

### Takeaway
The IAF runs separate enterprise systems:
- **e-MMS** for maintenance records, paperless since Apr 2020;
- **IMMOLS** for materials, provisioning and 5-year forecasting;
- **"Havai"**, an IAF-HAL e-portal;
- **AFNET** for secure connectivity.

Aircraft-side, health monitoring is fleet-specific: OEM in-flight HM on C-17, C-130J and Rafale; Tejas DFCC BIT and engine ECMS; a Tejas Mk1A indigenous HUMS in development; a reported Su-30MKI HUMS. No public source describes an integration layer joining on-board HM data, e-MMS records, IMMOLS spares and HAL/OEM repair data. That missing integration is exactly the gap the problem statement names. Predictive maintenance appears in IAF and MoD discourse (2017 IAF paper, 2020 DGQA webinar, 2024 IAF-IIT Bombay AI pilots for Su-30MKI) but no fielded IAF fighter PHM system was found.

### Cited Findings
- [DIRECT] "Indian Air Force has taken a giant step in automation of Maintenance Management through implementation of e-Maintenance Management System (e-MMS), which is one of the largest Maintenance Repair Overhaul (MRO) solutions implemented in the world. **Paperless workflow for recording maintenance activities in e-MMS is in effect from April 2020.** This has enhanced efficiency, productivity in decision making and digital enforcement of maintenance policies." [MoD Annual Report 2020-21, Air Force chapter](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf)
- [DIRECT] "Dedication of e-MMS during Aero India - 2023" ([MoD AR 2023-24, p. 165](https://mod.gov.in/sites/default/files/AR_2023-24-new-23-9-2025_0.pdf)). Sharing of e-MMS with the Myanmar Air Force was approved for subject-matter-expert exchanges in 2025 ([MoD AR 2025-26](https://mod.gov.in/sites/default/files/Annual-report-2025-26_0.pdf)).
- [DIRECT] "Integrated Materials Management Online System (IMMOLS): IAF has developed a fully automated Provisioning and Forecasting model through IMMOLS to meet the maintenance Spares requirement for the next five years based on past consumption trend, likely assets to be available in this period and utilisation rate being planned for the weapons systems." A single point of contact for HAL interaction was set up, and "An IAF-HAL e-Portal '**Havai**' has been launched for enabling real time exchange of Information between IAF and HAL." [MoD AR 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf). IMMOLS was already used by CAG for consumption analysis in 2015 ([CAG 38/2015, p. 101](https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf)).
- [DIRECT] AFNET: "IAF has a strong and robust operational network in the form of Air Force Network (AFNET)" ([MoD AR 2023-24](https://mod.gov.in/sites/default/files/AR_2023-24-new-23-9-2025_0.pdf)). CAG 38/2015 describes AFNET as secure voice, data and video over dedicated optical fibre, with SATCOM as standby.
- [DIRECT] IAF enterprise digitisation testimony (Dec 2024): "enterprise level drives have been made in the area of techno-logistics, e-maintenance and automated planning systems." [2nd Report 18th LS, para 2.20](https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs)
- [DIRECT] BRD-centred indigenisation and repair:
  - 11 **Nodal Technology Centres** at major BRDs and 28 Equipment Depot, working with IITs, CSIR and DRDO under DGAQA/CEMILAC (234 projects in PY 2023-24).
  - About 70,000 spare lines indigenised over a decade (saving rose from ₹48 crore to about ₹691 crore a year); 1,763 lines targeted in 2023-24 ([MoD AR 2023-24, p. 164](https://mod.gov.in/sites/default/files/AR_2023-24-new-23-9-2025_0.pdf)).
  - "OEMs have expressed inability to provide ToT for few maintenance activities. BRDs ... have developed the in house ROH technology" (14 items established, 58 in progress) ([MoD AR 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf)).
  - 206 import-range spares listed on the Srijan portal (same).
  - An MoU with NAL was signed 24 Nov 2020 (same).
- [DIRECT] DGQA "webinar on QA Data Aggregation & Big Data Analytics for Predictive Maintenance & Supply Chain Automation" (2020-21; Navy QA context). [MoD AR 2020-21](https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf)
- [DIRECT] IAF officer view (Feb 2017): minimising downtime depends on "Competitive Services, Predictive Maintenance, Effective Collaboration, Technology Utilization and Supply Chain Optimization". "In-flight health monitoring systems are the essential feature of all new acquisitions in IAF eg. C130J-30, C-17 and Rafale. There also exists an extensive scope of incorporating advanced systems ... on existing platforms." "The biggest challenge in IAF is the variety of technology ... Russian, European and American." "IAF has Base Repair Depots, which perform the full range of MRO functions." Restoration via "Repair and Reclamation"; "Lean is an already established philosophy in IAF, especially in BRDs"; references the IAF Indigenisation Roadmap 2016-2025. [JOAST 69(1A) 2017, Air Cmde BN Kumar, AOC AF Stn Kanpur (Aero India seminar AIS-2017-17)](https://joast.org/index.php/joast/article/view/217)
- [DIRECT] GTRE: existing preventive maintenance is "based on fixed TBO ... or ... TAC" and is uneconomical; it calls for an EHMS with sensing, diagnostics/prognostics and decision-making layers within an IVHM framework. [JOAST 69(1A) 2017, Patnaik & Rao](https://joast.org/index.php/joast/article/view/235)
- [DIRECT] Tejas on-board: engine ECMS ([ADA PS page](https://www.ada.gov.in/images/ps.htm)). Mk1A indigenous HUMS initiated 2018-19 with vendor selection in 2020-21 ([ADA AR 2018-19](https://www.ada.gov.in/images/Annual_Report_2018-19.pdf), [2020-21](https://www.ada.gov.in/images/Annual_Report_2020-21.pdf)). Mk2 Aircraft Maintenance Terminal model ([ADA AR 2021-22](https://www.ada.gov.in/images/Annual_Report_2021-22.pdf)).
- [DIRECT, secondary/unverified] Su-30MKI: Wikipedia states an on-board HUMS "monitors almost all systems and can act as an engineering data recorder", and that IIT Bombay is developing AI-based engine and asset maintenance solutions to replace the current electronic maintenance system ([Wikipedia: Su-30MKI](https://en.wikipedia.org/wiki/Sukhoi_Su-30MKI)). It cites The Hindu, "AI big focus of SU-30MKI upgrade; IAF taking up pilot projects with IIT-Mumbai, says officer", 3 Nov 2024 ([URL](https://www.thehindu.com/news/national/ai-big-focus-of-su-30mki-upgrade-iaf-taking-up-pilot-projects-with-iit-mumbai-says-officer/article68826449.ece); the fetch was blocked, so content is unverified).
- [DIRECT] DRDO: GAT and EMI/EMC tests completed on an "Advanced Flight Test Data Unit (AFTDU)" for the Su-30MKI ([MoD AR 2025-26](https://mod.gov.in/sites/default/files/Annual-report-2025-26_0.pdf)).

### Inferences
- The data landscape the problem statement complains about can be mapped to named systems:

  | Data domain | Current home |
  |---|---|
  | On-board HM (DFCC BIT, ECMS, HUMS, FDR) | Aircraft / OEM |
  | Technical records | e-MMS |
  | Spares | IMMOLS |
  | Agency repair status | HAL via Havai; OEM contracts and PBL; BRDs and NTCs |

  A Phalanx data generator should therefore emit **four linked record families with shared keys** (tail number, LRU part and serial number, sortie ID, work-order ID): on-board streams, e-MMS-like maintenance records, IMMOLS-like demand/issue transactions, and repair-agency turnaround records. [ASSUMPTION; schema details belong to the maintenance-records researcher]
- The absence of a public IAF fighter PHM programme (other than ADA's Mk1A HUMS and the Su-30 IIT Bombay pilots) supports framing Phalanx as the missing integration layer, not a replacement for e-MMS or IMMOLS. [ASSUMPTION]

### Gaps
- e-MMS vendor, data model, coverage by fleet, and whether it ingests on-board data: not public in sources found.
- iDEX/DISC challenges on aircraft predictive maintenance: not searched (budget exhausted). Needs a follow-up.
- Details of IAF Maintenance Command / BRD fleet assignments (which BRD overhauls which fighter or engine): only fragments found (4 BRD: Mirage M53 blades; 7 and 11 BRD: SAMAR; 3 BRD: Mi-17 engines; 25 ED Nashik; 28 ED).
- HAL internal MRO digitisation: not found.

---

## Synthesis: which platform should Phalanx target? (a) key findings, (b) ranked recommendation, (c) open questions, (d) source ranking

### (a) Key findings summary
1. **The problem is real and quantified for Russian-origin fleets.** CAG 38/2015 gives Su-30MKI serviceability of 55.50-59.73% (2006-10) vs a 75% norm, AOG 10.90-15.32%, and flying-task shortfalls of 31-43%. It gives the MiG-21 Bison 41.32-51.52% with AOG up to 37.34%. Causes are cross-agency: Cat 'D' aggregates going to the OEM, late HAL ROH, piecemeal spares, Russian data opacity, and technician and publication gaps (111 FBW snags grounding 31 aircraft). [DIRECT]
2. **IAF maintenance is three-tier O/I/D**, hard-time (hours and calendar life) with engineering life extensions, and spread across squadrons, BRDs/EDs, HAL divisions and OEMs. On-condition maintenance appears only on newer Western types (Apache). [DIRECT]
3. **Enterprise records are digitised but siloed**: e-MMS since Apr 2020, IMMOLS, Havai, AFNET. No public integration with on-board health data was found. [DIRECT existence; integration gap is an inference]
4. **Tejas is the best-documented IAF fighter at system level.** It has DFCC architecture and timing, sensor ranges and bandwidths, actuator pressure and bandwidth, 344-LRU and 33-software counts, named ECS/FCS/hydraulic/landing-gear LRUs, an engine ECMS, an FTI of about 1,500 parameters, and a Mk1A HUMS in development. It also displays the problem statement's failure modes: multi-agency repair responsibility (69 LRUs without HAL ROH in 2015), import dependence for 167 LRUs, GE engine supply delays, a two-month software grounding of the whole fleet (2026), JFS cold/altitude issues, and fuel-system quirks. [DIRECT]
5. **Indian operating conditions** with public evidence: cold/altitude engine starting (Leh), heat soak (Jaisalmer, 39-42 °C), dirt/carbon compressor fouling (Indian environment), water ingress, birds. [DIRECT/TRANSFER]

### (b) Ranked recommendation (for the Phalanx virtual-aircraft data generator; not a final lock-in)

| Rank | Platform | Why | Main trade-off |
|---|---|---|---|
| **1** | **HAL Tejas Mk1/Mk1A (F404-GE-IN20)** | (i) Highest future weight in the IAF (220 planned; replaces MiG-21; "LRU concept" maintenance). (ii) Indian design authority (ADA/ADE/HAL), so a demonstrator can credibly propose integrating DFCC BIT, ECMS/HUMS, e-MMS and IMMOLS data. (iii) Most [DIRECT] system parameters of any IAF fighter. (iv) Engine shares the F404 family with F/A-18 A-D and Gripen (RM12), allowing explicit [TRANSFER] for engine-health texture. (v) Recent, well-reported availability events (grounding, engine supply, JFS) provide realistic fault and logistics scenarios. | No public squadron serviceability or MTBF data. Electrical, hydraulic-flow, fuel-tank and FDR-parameter details are absent and need [TRANSFER]/[ASSUMPTION]. Small current fleet (about 34-36). |
| **2** | **Su-30MKI (AL-31FP)** | Strongest audited embodiment of the problem; largest fleet and IAF mainstay to the 2040s via upgrade; most agencies; Russian OEM opacity; IIT Bombay AI pilots indicate IAF interest. Best used to **calibrate the fleet/maintenance-ecosystem layer**: state-occupancy fractions (≈20% line maintenance, 11-12% depot, 13-14% AOG), repair-loop delays, spares behaviour. | Almost no open system-level documentation; recorder and HUMS architecture undocumented. A high-fidelity aircraft model would be mostly [ASSUMPTION]. |
| **3** | **F/A-18 A-D (F404-GE-400/402)** | Not IAF. Value is as a **[TRANSFER] donor** for F404 engine behaviour and US Navy-documented maintenance and monitoring practice (IECMS), which maps onto the Tejas engine. | Zero relevance to IAF fleet-availability narrative; different airframe and twin-engine installation. |
| **4** | **Saab Gripen C/D (RM12)** | Not IAF (former MMRCA contender). F404-derivative engine; single-engine delta-canard fighter, so a closer configuration analogue to Tejas than the F/A-18. | Thin Indian relevance; public system documentation was not assessed here. |
| **5** | **F-16 (F100/F110)** | Not IAF (MRFA contender as F-21). Rich US public literature. | Engine family unrelated to IAF fleet; weakest problem-owner relevance. |

**Recommended framing.** "A **Tejas-class (Mk1A-representative) virtual fighter**. Its on-board streams are parameterised from ADA/ADE/CEMILAC/CAG sources. Its engine-health texture comes by explicit transfer from the F404 family. It operates inside an **IAF O/I/D maintenance ecosystem** (squadron → BRD/HAL → OEM) whose availability priors and agency delays are calibrated on **audited Su-30MKI and MiG-21 Bison data**." This keeps the aircraft model well-documented and the problem framing faithful to the MoD's own audit evidence. [ASSUMPTION; validate with DSSC/IAF mentors before locking in]

### (c) Open questions / gaps (priority order)
1. NAL/ADA published LCA system-identification datasets (derivatives, flight-data channels, sampling rates). DSJ and NAL-IR were unreachable and the search budget was exhausted. **Highest-value follow-up.**
2. Tejas FDR / crash-survivable recorder and Mk1A HUMS: parameter lists, rates, data-download path, and whether data flows into e-MMS.
3. Tejas electrical power system (generator rating, buses), hydraulic flows and reservoirs, fuel tank capacities and layout, ECS architecture: primary sources not found.
4. Post-2015 serviceability figures for any IAF fighter fleet. Read CAG Air Force compliance reports 2016-2025 and PIB/Lok Sabha Q&A (e.g., Parrikar's Jan 2017 "60%" statement; the 2015 Rajya Sabha engine-failure reply text).
5. Tejas Mk1 squadron reliability data (MTBF/MTBUR per LRU, AOG causes), including any HAL "Tejas product support" disclosures.
6. Su-30MKI on-board HUMS/recorder architecture (the Wikipedia claim needs a primary source) and IIT Bombay AI pilot scope.
7. iDEX/DISC predictive-maintenance challenges and e-MMS technical details.
8. Field evidence of coastal salt/humidity and monsoon effects on fighter AOG.
9. Whether the 12.5 ms DFCC frame and the 12.5 Hz 1553B health-status message (ADE paper) correspond to the LCA. Confirm with ADE literature.

### (d) Most valuable sources for later deep reading (ranked)
1. **V. Kala (ADE), "Design and Development of FCS for LCA-Tejas", JOAST 67(2A) 2015**: sensor ranges, redundancy, BIT types, 12.5 ms frame, 280 bar actuators. https://joast.org/index.php/joast/article/view/317
2. **CAG Report No. 17 of 2015 (LCA performance audit)**: 344 LRUs and ROH split, JFS Leh failures, LSP deficiencies, test-fleet availability table, actuator and Kaveri history. https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Performance_Defense_Design__Manufacture_Light_Combat%20Aircraft_17_2015.pdf
3. **CAG Report No. 38 of 2015 (Air Force)**: Su-30MKI ('C') and MiG-21 Bison ('DD') serviceability/AOG tables, FBW snag study, maintenance-level definitions. https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2015/Union_Compliance_Defence_Air_Force_Report_38_2015.pdf
4. **ADA Annual Reports 2015-16 to 2021-22, plus ADA systems pages and the LRU indigenisation list**: PID, hot/cold trials, brake wear, JFS M2, HUMS, AMT, ECFM, fuel issues. https://www.ada.gov.in/images/annual%20reports_2.html ; https://www.ada.gov.in/images/LRU.pdf ; https://www.ada.gov.in/images/gs.htm ; https://www.ada.gov.in/images/ps.htm
5. **CEMILAC, "Airworthiness Certification of Tejas", JOAST 67(2A) 2015**: 17 systems, 344 LRUs, 33 software systems, USMS, FOC open items. https://joast.org/index.php/joast/article/view/325
6. **MoD Annual Reports 2020-21 / 2023-24 / 2025-26**: e-MMS, IMMOLS, Havai, NTCs/BRDs, LCA Mk1A programme. https://mod.gov.in/sites/default/files/2020-2021_Annual%20Report.pdf ; https://mod.gov.in/sites/default/files/AR_2023-24-new-23-9-2025_0.pdf ; https://mod.gov.in/sites/default/files/Annual-report-2025-26_0.pdf
7. **Standing Committee on Defence reports**: 12th (15th LS, 2011) accident-cause shares and MiG data opacity; 4th, 20th and 41st (16th LS) serviceability and maintenance-concept testimony; 2nd (18th LS, Dec 2024) 2017-22 accident list and Tejas engine issues; 8th and 12th (18th LS, 2025) Su-30 mainstay and Mk1A engine delay. https://sansad.in/getFile/lsscommittee/Defence/15_Defence_12.pdf?source=loksabhadocs ; https://sansad.in/getFile/lsscommittee/Defence/18_Defence_2.pdf?source=loksabhadocs
8. **CAG Report No. 34 of 2014, ch. 3**: Mirage M53-P2 blade-repair ToT failure at 4 BRD; flight-safety statistics (TD 779 incidents in 3 years). https://d7i5wg8xwe4hf.cloudfront.net/uploads/download_audit_report/2014/Union_Compliance_Defence_Air_force_Navy_34_2014_Chapter_3.pdf
9. **RCMA(Engines)/HAL defect-trend and deterioration papers, JOAST 66(1) 2014 and 68(4) 2016**: Indian-environment compressor fouling, withdrawal statistics, FDR EGT as health parameter. https://joast.org/index.php/joast/article/view/438 ; https://joast.org/index.php/joast/article/view/344
10. **Air Cmde BN Kumar, "MRO Philosophies for Reduction in Downtime of Fleet", JOAST 69(1A) 2017**: IAF view on predictive maintenance and BRDs. https://joast.org/index.php/joast/article/view/217
11. **GE F404 family data sheet**: IN20, RM12 and -402 parameters (engine-transfer anchor). https://www.geaerospace.com/sites/default/files/2022-01/F404%20Family%20Data%20Sheet_UPDATED.pdf
12. **CAG Report No. 3 of 2019**: Rafale ESP/PBL and >75% availability requirement; Apache on-condition maintenance. https://www.humanrightsinitiative.org/download/C&AG-AirForce-CapitalAcq-PerfAudit-Report3-2019.pdf
13. **Journalism for event timelines**: Tribune (Apr 2026 grounding), ThePrint (Oct 2024 GE delays), Defense News (2015, 2017 Su-30), Ajai Shukla / Business Standard (2014 Su-30 state breakdown). Use only to locate primary sources.
14. **Not yet read but high priority once reachable**: Defence Science Journal (publications.drdo.gov.in) and NAL-IR papers by J. Singh, G. Girija and J.R. Raol on LCA parameter estimation; the IET book *Modelling and Parameter Estimation of Dynamic Systems* (Raol, Girija, Singh) https://digital-library.theiet.org/doi/book/10.1049/pbce065e
