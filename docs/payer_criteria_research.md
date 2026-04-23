# Payer criteria research — lumbar MRI (CPT 72148)

Research date: 2026-04-23
Researcher: Claude (web research session)
Purpose: Feeds `mcp_server/data/criteria/*.json` encoding in Week 2.

## Cigna (via eviCore)

- **Policy title**: Cigna Spine Imaging Guidelines (CIGNA MEDICAL COVERAGE POLICIES – RADIOLOGY), developed by EviCore by EVERNORTH
- **Version / effective date**: V1.0.2026, effective February 3, 2026 (published October 29, 2025) ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf))
- **Source URL**: https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf
- **Last verified**: 2026-04-23

### 1. Conservative-care duration
For uncomplicated low back pain without neurological features (SP-5.1) and for lower-extremity pain with neurological features (radiculopathy/radiculitis) with or without low back pain (SP-6.1), the policy requires documented failure of clinical improvement following a **six-week trial of provider-directed treatment** that begins after the current episode of symptoms or exam findings started or changed. The threshold is expressed as "failed therapy" duration rather than pure "symptoms" duration — the six-week clock starts when the current symptom episode begins and treatment is instituted. A clinical re-evaluation after that six-week trial is also required before MRI is authorized ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)).

### 2. Conservative-therapy composition
The General Guidelines (SP-1.0) describe "provider-directed treatment" as an **open "may include" list** rather than a strict AND/OR set. Components listed include: education, activity modification, NSAIDs, narcotic and non-narcotic analgesic medications, oral or injectable corticosteroids, a provider-directed home exercise/stretching program, cross-training, avoidance of aggravating activities, physical/occupational therapy, spinal manipulation, and interventional pain procedures or other pain-management techniques. No specific number of PT sessions, no minimum number of modalities, and no N-of-M threshold is stated — the policy does not require that the clinician combine any specific subset. What must be documented is that a six-week trial occurred and failed. Re-evaluation can be documented by in-person encounter or by other meaningful contact (phone, email, telemedicine, messaging) ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)).

### 3. Prior-imaging window
The policy does not state a bright-line lookback window (e.g., "no MRI within 12 months") that automatically disqualifies a new MRI. Instead, SP-1.0 states that the need for repeat advanced imaging "should be carefully considered and may not be medically necessary if prior advanced diagnostic imaging has been performed," that serial surveillance imaging is not supported by evidence for most spinal disorders, and that advanced imaging is generally unnecessary for resolved or improving spinal pain/radiculopathy or for stable longstanding pain without clinically significant changes in symptoms or exam. Repeat imaging may be considered case-by-case (examples given: concern for delayed/non-union of fracture, pseudoarthrosis of fusion). Separately, the Definitions section (SP-1.3) uses a **12-month window** as the validity period for a prior MRI/CT or EMG/NCV that is being used to establish the "radiculopathy" definition — i.e., a prior concordant imaging study within the prior 12 months can support the radiculopathy diagnosis ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)).

### 4. Red-flag bypass
Red Flag Indications (SP-1.2) are defined as clinical situations likely to reflect serious underlying spinal or non-spinal disease and warrant exception to the six-week conservative-therapy requirement. The seven enumerated categories and the policy's own phrasing for each are below ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)):

- **Motor Weakness**: new-onset manual motor weakness graded 3/5 or less of specified muscles; new-onset foot drop; new-onset bilateral lower-extremity weakness; or progressive objective motor/sensory/reflex deficits on re-evaluation — likely ICD: M54.5x with G83.1/G83.2 (monoplegia/paraplegia), R29.898; likely note phrases: "foot drop," "3/5 strength," "progressive weakness," "bilateral leg weakness."
- **Aortic Aneurysm or Dissection**: new-onset back/abdominal pain in a patient with known AAA, or suspicion of acute dissection — spine imaging is not the right study; referred to PVD guideline — likely ICD: I71.x; likely note phrases: "known AAA," "tearing pain," "suspected dissection."
- **Cancer**: clinical suspicion of spinal malignancy plus one or more of night pain, uncontrolled/unintended weight loss, pain unrelieved by position change, age over 70, or severe/worsening spinal pain; or any patient with known cancer history and back pain — likely ICD: C79.51 (secondary malignant neoplasm of bone), C41.2 (malignant neoplasm of vertebral column), Z85.x (personal history of cancer); likely note phrases: "history of malignancy," "night pain," "unexplained weight loss," "pain not relieved by rest," "known metastatic disease."
- **Cauda Equina Syndrome**: acute bilateral sciatica, perineal ("saddle") sensory loss, decreased anal sphincter tone, new bowel/bladder incontinence, or otherwise unexplained acute urinary retention — likely ICD: G83.4; likely note phrases: "saddle anesthesia," "bowel/bladder incontinence," "urinary retention," "bilateral sciatica," "decreased rectal tone."
- **Fracture**: clinical suspicion of pathological fracture, post-trauma fracture, or fracture in ankylosing spondylitis/DISH — likely ICD: S32.0xx (lumbar vertebra fracture), M48.5 (collapsed vertebra), M80.x (osteoporotic fracture); likely note phrases: "suspected fracture," "post-fall pain," "ankylosing spondylitis," "DISH."
- **Infection**: suspicion of disc-space infection, epidural abscess, or spinal osteomyelitis plus any of fever, IV drug use, recent bacterial infection (UTI/pyelonephritis/pneumonia), recent spinal intervention, immunocompromise, long-term systemic glucocorticoids, transplant with anti-rejection medication, diabetes, HIV/AIDS, chronic dialysis, immunosuppressant therapy, neoplastic spine involvement, lab values suggestive of infection (WBC, ESR, CRP, cultures), decubitus ulcer/wound over spine, abnormal x-ray/CT suspicious for infection, new neurologic deficit, or cauda equina — likely ICD: M46.2x–M46.3x (osteomyelitis of vertebra, discitis), G06.1 (intraspinal abscess); likely note phrases: "fever," "IV drug use," "immunocompromised," "on chronic steroids," "elevated ESR/CRP," "history of bacteremia," "recent spinal injection."
- **Severe Radicular Pain**: severe radicular pain in a defined nerve-root distribution (minimum 9/10 VAS), documented significant functional loss, unresponsive to at least seven days of provider-directed treatment, and a documented plan for transforaminal epidural steroid injection (any level), interlaminar epidural steroid injection (cervical or thoracic only), urgent/emergent spine surgery, or urgent/emergent referral to interventional pain or spine surgery — likely ICD: M54.16/M54.17 (lumbosacral radiculopathy), M51.17 (lumbosacral disc disorder with radiculopathy); likely note phrases: "10/10 radicular pain," "unable to work," "planning ESI," "surgical candidate."

### 5. Age / diagnosis gating
There is no explicit adult age cutoff for the adult Spine Imaging Guidelines; pediatric patients are covered by a separate Pediatric and Special Populations Spine Imaging Guidelines document.  Age over 70 is used as a contributory red-flag factor for cancer, and age ≥65 is used as a high-risk factor for cervical trauma. The policy requires an in-person clinical evaluation for the current episode and defines "radiculopathy" narrowly (see SP-1.3) as pain in a specific dermatome with at least one of: concordant motor loss, sensory change, reflex change, concordant imaging (prior 12 months), or EMG/NCV (prior 12 months). Advanced imaging for "stable, longstanding spinal pain without neurological features or without clinically significant or relevant changes in symptoms or physical examination findings" is explicitly deemed not of demonstrated value, and advanced imaging based only on degenerative findings on x-ray in asymptomatic or non-specific axial pain is not generally medically necessary ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)).

### Other rules (if any)
- In-person clinical evaluation for the current episode is mandatory before advanced imaging; telehealth alone does not satisfy this requirement for the initial/recurrent evaluation, though telephone, email, telemedicine, and messaging do count for the required **re-evaluation** after the six-week trial ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)).
- The evaluation must include a relevant history, detailed neurologic exam (manual motor testing with 0–5 grading, dermatomal sensory testing, reflex grading, nerve-root tension signs such as straight-leg raise, slump, and femoral nerve tension tests) and appropriate labs and non-advanced imaging.
- For most lumbar indications, plain x-rays are not a mandatory prerequisite for MRI; however, x-rays are required for specific situations (spinal compression fractures, spondylolysis/spondylolisthesis, inflammatory spondylitis, sacro-iliac pain, coccydynia, and post-operative workup).
- Contrast is generally not needed for most disc, nerve-root, and degenerative indications; non-contrast MRI (CPT 72148) is the default study for uncomplicated lumbar indications.
- Positional/dynamic/weight-bearing MRI is considered not medically necessary.
- Specialty-gating: the "severe radicular pain" red-flag pathway requires a documented plan involving an interventional pain physician or spine surgeon, or an ESI plan, or urgent surgical plan.

### Open questions for the engineer
- Whether "symptoms or exam findings started or changed" is intended to reset the six-week clock every time symptoms change is not fully spelled out; policy text suggests yes.
- The policy does not give a single numeric "no repeat MRI within X months" rule, so the engine should encode the softer "repeat generally not medically necessary absent documented new/progressive findings, prior fusion complication concerns, or surgical planning" logic rather than a hard window.
- For radiculopathy specifically, a 12-month validity for a prior imaging study is embedded in the **definition** of radiculopathy (SP-1.3). This is distinct from a lookback rule blocking a new MRI; clarify which semantics the JSON should encode.
- The policy does not enumerate chiropractic care explicitly, but "spinal manipulation" is listed among acceptable provider-directed treatments. Confirm whether unsupervised chiropractic visits count as "provider-directed."

---

## Aetna (CPB 0236)

- **Policy title**: Magnetic Resonance Imaging (MRI) and Computed Tomography (CT) of the Spine — Aetna Clinical Policy Bulletin 0236 ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html))
- **Version / effective date**: The publicly mirrored version of CPB 0236 does not display a single "last reviewed" date stamp in the retrieved HTML, but the reference list includes citations as recent as 2025 (ACR Appropriateness Criteria Acute Spinal Trauma 2024 update published 2025; Ma 2025; Michael 2025) and an "Accessed February 6, 2026" note in one reference, indicating the policy has been updated into early 2026 ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).
- **Source URL (primary)**: https://www.aetna.com/cpb/medical/data/200_299/0236.html — the canonical www host returned an Incapsula bot-challenge error during this session; the es.aetna.com mirror served identical policy text and was used for extraction ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).
- **Cross-reference**: CPB 0743 (Spinal Surgery: Laminectomy and Fusion) was reviewed via search snippets; it governs surgical indications  and refers back to imaging policies rather than re-stating MRI medical-necessity criteria ([Source](https://www.aetna.com/cpb/medical/data/700_799/0743.html)).
- **Last verified**: 2026-04-23

### 1. Conservative-care duration
CPB 0236 uses two different numeric thresholds depending on the clinical presentation:
- **6 weeks** of failed conservative therapy is required for "persistent back or neck pain with radiculopathy as evidenced by pain plus objective findings of motor or reflex changes in the specific nerve root distribution" ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).
- **4 weeks** of failed conservative therapy is required for "spondylolisthesis and degenerative disease of the spine that has not responded to 4 weeks of conservative therapy" ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).

Aetna's threshold is expressed as **"failed therapy" duration**, not pure symptom duration: the text references non-response to conservative treatment. The policy background also cites AAFP's "no imaging within the first six weeks unless red flags are present"  — reinforcing a 6-week baseline for generic non-specific LBP without red flags ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).

### 2. Conservative-therapy composition
Aetna defines conservative therapy narrowly in a footnote on CPB 0236: **"Conservative therapy = moderate activity, analgesics, non-steroidal anti-inflammatory drugs, muscle relaxants."** The construction is listed as an AND-labeled definition of what a "trial" consists of, but the policy does not state that all four elements must be simultaneously tried; in practice it is generally interpreted as a combination of activity modification plus pharmacologic therapy. Physical therapy, gabapentinoids, epidural injections, and chiropractic care are not named in the CPB 0236 conservative-therapy definition itself (they are addressed in the related back-pain invasive-procedures CPB 0016). No session counts, visit counts, or N-of-M structure are specified ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).

### 3. Prior-imaging window
CPB 0236 does not define a numeric prior-imaging lookback window (e.g., 6 or 12 months) that automatically disqualifies a new MRI. The background section cites evidence that repeat or updated imaging does not reduce revision rates in adults with lumbar degenerative disease (Ries et al., 2018; Lee et al., 2019)  and discourages serial imaging for surveillance absent clinical change, but no hard numeric window is published in the policy text. Aetna also deems "repeat MRI scans in different positions (flexion, extension, rotation, lateral bending) and with/without weight-bearing" experimental/investigational  ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).

### 4. Red-flag bypass
The medical-necessity list in CPB 0236 is structured as an "any one of the following" list, so items beyond the radiculopathy/spondylolisthesis clauses effectively function as red-flag bypasses of the conservative-therapy requirement. Enumerated conditions and how they map to likely ICD-10 codes and clinician phrasing ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)):

- **Clinical suspicion of spinal cord or cauda equina compression syndrome**  — ICD: G83.4, G95.2; likely note phrases: "saddle anesthesia," "bowel/bladder incontinence," "perineal numbness," "urinary retention," "bilateral sciatica."
- **Clinical evidence of spinal stenosis**  — ICD: M48.06, M48.07; likely note phrases: "neurogenic claudication," "relieved by sitting," "bilateral leg pain with walking."
- **Congenital anomalies or deformities of the spine**  — ICD: Q05.x, Q76.x; likely note phrases: "tethered cord," "congenital scoliosis."
- **Lumbar epidural lipomatosis (diagnosis and evaluation)**  — ICD: E88.2, D17.79; likely note phrases: "on chronic steroids," "epidural fat," "obesity-related cord compression."
- **Recurrent symptoms after spinal surgery**  — ICD: M96.1 (postlaminectomy syndrome), T84.x; likely note phrases: "post-op recurrent radiculopathy," "failed back surgery syndrome."
- **Evaluation prior to epidural injection (to rule out tumor/infection and localize injection)**  — no single ICD; likely note phrases: "pre-injection planning," "rule out epidural abscess."
- **Follow-up evaluation for spinal malignancy or spinal infection** — ICD: C79.51, C41.2, M46.2x, G06.1; likely note phrases: "known metastatic disease," "treated osteomyelitis."
- **Known or suspected myelopathy (including MS)** — ICD: G35, G95.9; likely note phrases: "hyperreflexia," "Hoffmann sign," "spastic gait."
- **Known or suspected primary spinal cord tumor** — ICD: C72.0, D33.4; likely note phrases: "intradural mass," "progressive myelopathy."
- **Primary spinal bone tumors or suspected vertebral/paraspinal/intraspinal metastases** — ICD: C41.2, C41.4, C79.51; likely note phrases: "history of breast/lung/prostate cancer," "lytic lesion on x-ray," "night pain."
- **Progressively severe symptoms despite conservative management** — ICD: M54.5x, M54.1x with worsening qualifiers; likely note phrases: "worsening despite PT," "failed NSAIDs," "progressive pain."
- **Rapidly progressing neurological deficit, or major motor weakness** — ICD: G83.1/G83.2, R29.898; likely note phrases: "foot drop," "progressive weakness," "unable to walk."
- **Severe back pain (e.g., requiring hospitalization)** — ICD: M54.5x with R52; likely note phrases: "admitted for pain," "intractable pain," "requires IV opioids."
- **Suspected infectious process (osteomyelitis, epidural abscess, soft tissue)** — ICD: M46.2x, G06.1, M46.3x; likely note phrases: "fever," "IV drug use," "elevated ESR/CRP," "positive blood cultures."
- **Suspected spinal cord injury secondary to trauma** — ICD: S14.1xx/S24.1xx/S34.1xx; likely note phrases: "MVA," "fall from height," "new neuro deficit after trauma."
- **Suspected spinal fracture/dislocation secondary to trauma (plain films not conclusive)** — ICD: S32.0xx, S22.0xx, S12.xxx; likely note phrases: "trauma with point tenderness," "x-rays equivocal."
- **Suspected transverse myelitis** — ICD: G37.3; likely note phrases: "sensory level," "acute myelopathy."

### 5. Age / diagnosis gating
CPB 0236 does not specify an age cutoff (adult vs. pediatric) for MRI medical necessity. The policy includes a detailed ICD-10 code table that lists covered diagnoses. Covered codes relevant to lumbar MRI include G83.4 (cauda equina syndrome), M48.00–M48.08 (spinal stenosis), M50.x/M51.x (intervertebral disc disorders), M54.10–M54.18 (radiculopathy/neuritis), M54.30–M54.32 (sciatica), M54.9 (dorsalgia unspecified), C79.51–C79.52 (secondary bone malignancy), M46.2x (osteomyelitis of vertebra), S32.0xx (lumbar vertebral fracture), Q05.x/Q06.x (spina bifida/congenital cord malformations), and related trauma and infection codes. Explicit exclusions (ICD-10 codes not covered) include Z01.818 and Z01.89 (preprocedural/other special exam), Z12.x (screening for malignancy), and Z08 (follow-up after completed malignancy treatment) — i.e., purely screening and asymptomatic surveillance encounters are not covered. CPB 0236 also deems "dynamic-kinetic MRI" of the cervical spine experimental/investigational and routine MRI after a normal cervical CT in obtunded/comatose patients not medically necessary ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).

### Other rules (if any)
- All other indications for spine MRI/CT are considered experimental, investigational, or unproven because clinical value has not been established; the policy text explicitly cites AHCPR, ACP, AAFP, and NASS recommendations against routine imaging for acute non-specific low back pain ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).
- BoneMRI (MRI-based synthetic CT) is experimental/investigational for spine and pelvis pre-operative planning, surgical planning, and tumor assessment.
- Dual-energy CT for bone marrow edema and fracture lines in acute vertebral fractures is experimental/investigational.
- Precertification may be required; the policy points to Aetna's precertification list search tool.
- Aetna's related CPB 0016 (Back Pain: Invasive Procedures) and CPB 0743 (Spinal Surgery) use a **6-week** conservative-therapy threshold for other procedures such as SI joint injections ("Member has tried 6 weeks of adequate forms of conservative treatment with little or no response, including pharmacotherapy (e.g., NSAIDS), activity modification..."), consistent with the 6-week threshold used in CPB 0236 for radiculopathy ([Source](https://www.aetna.com/cpb/medical/data/1_99/0016.html)).

### Open questions for the engineer
- Whether the 4-week threshold for "spondylolisthesis and degenerative disease of the spine" overlaps or competes with the 6-week threshold for radiculopathy when a patient has both conditions — the policy does not state precedence.
- Whether activity modification alone (without NSAIDs or analgesics) qualifies as a conservative-therapy trial, or whether multiple elements are required — footnote wording is ambiguous.
- Whether PT is required as a component of conservative therapy under CPB 0236 (it is not named in the footnote definition) — many utilization reviewers require PT in practice; engineer may want to flag as ambiguous.
- No numeric prior-imaging lookback window is published; the engine should not invent one. If needed, compare against plan-level clinical guidelines or delegated vendor rules applicable to specific Aetna plans.
- The policy's "progressively severe symptoms despite conservative management" is a red-flag bypass but is undefined in duration or severity; will need clinician-judgment escape hatch in the logic.

---

## ACR Appropriateness Criteria — cross-check

- **Topic**: Low Back Pain (2021 Update; topic originally 1996)
- **URL**: https://acsearch.acr.org/docs/69483/narrative/
- **Last verified**: 2026-04-23 (the ACR document is tagged "New 2021"; no more recent update is listed on the ACR search page for "Low Back Pain") ([Source](https://acsearch.acr.org/docs/69483/narrative/))
- **Variant(s) relevant**: Seven variants are published. Those most directly relevant to the payer questions:
  - Variant 1: Acute low back pain ± radiculopathy, no red flags, no prior management. MRI lumbar spine without IV contrast — **Usually Not Appropriate** ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Variant 2: Subacute or chronic LBP ± radiculopathy, no red flags, no prior management. MRI lumbar spine without IV contrast — **Usually Not Appropriate** ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Variant 3: Subacute/chronic LBP ± radiculopathy, surgery or intervention candidate with persistent or progressive symptoms during or following **6 weeks** of optimal medical management. MRI lumbar spine without IV contrast — **Usually Appropriate** ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Variant 4: LBP with suspected cauda equina syndrome. MRI lumbar spine without and with IV contrast — Usually Appropriate; MRI lumbar spine without IV contrast — Usually Appropriate ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Variant 5: LBP with history of prior lumbar surgery ± radiculopathy, new or progressing symptoms. MRI lumbar spine without and with IV contrast — Usually Appropriate; MRI lumbar spine without IV contrast — Usually Appropriate; radiography — Usually Appropriate ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Variant 6: LBP ± radiculopathy with low-velocity trauma, osteoporosis, elderly, or chronic steroid use. MRI lumbar spine without IV contrast and CT lumbar spine without IV contrast — Usually Appropriate; radiography — Usually Appropriate ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Variant 7: LBP ± radiculopathy with suspicion of cancer, infection, or immunosuppression. MRI lumbar spine without and with IV contrast — Usually Appropriate; MRI lumbar spine without IV contrast — Usually Appropriate ([Source](https://acsearch.acr.org/docs/69483/narrative/)).

- **Key takeaways that agree with Cigna/Aetna**:
  - ACR states uncomplicated acute LBP ± radiculopathy is benign and self-limited and does not warrant imaging studies — consistent with both Aetna's "against routine imaging" stance and Cigna/eviCore's six-week trial requirement ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - ACR's "6 weeks of optimal medical management" threshold for imaging of subacute/chronic LBP (Variant 3) matches Cigna/eviCore's six-week conservative-therapy threshold and Aetna's six-week threshold for persistent radicular back pain ([Source](https://acsearch.acr.org/docs/69483/narrative/), [Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf), [Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).
  - ACR agrees that red flags — cauda equina, malignancy, fracture, infection — justify immediate imaging, matching both payers' red-flag bypass logic ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Non-contrast MRI (CPT 72148) is the preferred modality for most lumbar indications under all three sources; ACR rates MRI without IV contrast as Usually Appropriate for surgical/interventional candidates, cauda equina, post-surgical new symptoms, trauma/osteoporosis, and cancer/infection/immunosuppression.

- **Key takeaways that disagree with Cigna or Aetna**:
  - ACR Variant 3 is framed as imaging **during or following** 6 weeks of management (i.e., 6 weeks is a ceiling on watchful waiting, not a floor on the PA requirement). Cigna/eviCore operationalizes 6 weeks as a strict floor ("failure of a 6-week trial of provider-directed treatment"), and Aetna's CPB 0236 similarly requires non-response to 6 weeks before imaging for radiculopathy. ACR language is more permissive than either payer in the sense that it contemplates imaging at the 6-week mark for surgical/interventional candidates ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - ACR does not require any specific conservative-therapy composition (NSAIDs, PT, activity modification), whereas Aetna's footnote enumerates four named components. Cigna/eviCore's list is broader and more permissive than Aetna's.
  - For cauda equina, ACR lists MRI without and with IV contrast and MRI without IV contrast both as Usually Appropriate; Cigna/eviCore's red-flag table explicitly authorizes CPT 72148 (without contrast) or 72158 (without and with contrast) — consistent. Aetna's general list allows MRI but does not distinguish contrast strategies for this indication.
  - Neither Cigna nor Aetna publishes a quantitative prior-imaging lookback window, while ACR does not address prior-imaging windows at all; there is no direct conflict but also no authoritative numeric guidance.

---

## Conflicts + judgement calls

- **Conservative-therapy duration, radiculopathy vs. mechanical LBP**:
  - Cigna/eviCore V1.0.2026: **6 weeks** uniformly for both axial LBP (SP-5.1) and LBP with neurologic features (SP-6.1) ([Source](https://www.evicore.com/sites/default/files/clinical-guidelines/2025-10/Cigna_Spine%20Imaging%20Guidelines_V1.0.2026_eff02.03.2026_PUB10.29.2025.pdf)).
  - Aetna CPB 0236: **6 weeks** for persistent back/neck pain with radiculopathy, but only **4 weeks** for spondylolisthesis and degenerative disease ([Source](https://es.aetna.com/cpb/medical/data/200_299/0236.html)).
  - ACR: **6 weeks** of optimal medical management as the reference threshold in Variant 3 ([Source](https://acsearch.acr.org/docs/69483/narrative/)).
  - Net: Aetna is more permissive than Cigna for spondylolisthesis/DDD (4 weeks), a real disagreement. Cigna's V1.0.2026 document is the most recent primary source (effective 2026-02-03) and is therefore the most current source for the Cigna side; Aetna's document references 2025 and 2026 ACR/literature citations so is also contemporaneous.

- **Conservative-therapy composition**:
  - Cigna/eviCore: open menu including PT, spinal manipulation, and interventional pain procedures.
  - Aetna: four named items — moderate activity, analgesics, NSAIDs, muscle relaxants — with PT notably absent from the CPB 0236 footnote (though PT is referenced in related CPB 0016 for injections).
  - ACR: does not specify composition.
  - Net: Cigna is more permissive (more therapies count) but imposes a strict duration; Aetna is more prescriptive about what "counts" but shorter duration for some conditions.

- **Prior-imaging lookback**:
  - Neither payer publishes a bright-line numeric rule. Cigna embeds a 12-month window only in the definition of radiculopathy when a prior study is being used to establish that diagnosis, not as a blanket disqualifier for a new MRI. Aetna is silent on numeric lookback. ACR is silent. No direct conflict, but the absence of a bright line means individual reviewers may vary.

- **Red-flag taxonomy**:
  - Cigna/eviCore lists seven explicit red-flag categories with operational criteria and VAS/strength/laboratory thresholds.
  - Aetna's list is flat and covers essentially the same ground (cauda equina, malignancy, infection, trauma, myelopathy, rapidly progressing deficit, severe pain requiring hospitalization, progressive symptoms despite conservative care) but with less operational detail.
  - ACR organizes red flags by variant and adds low-velocity trauma plus osteoporosis/elderly/chronic steroids as a distinct variant (Variant 6). This specific framing is present in Cigna's cervical-trauma high-risk factor list but is less crisp in Aetna's CPB 0236.

- **Recency**: Cigna V1.0.2026 (effective 2026-02-03, published 2025-10-29) is the most recent. Aetna CPB 0236 references literature through 2025 and an accessed-date into 2026 but does not display a single version stamp in the HTML retrieved. ACR Low Back Pain 2021 Update is the most recent ACR publication for this topic. Where the three disagree, the Cigna 2026 document and Aetna 2026 policy are more operationally current than the ACR 2021 document.

---

## Source integrity notes

- The canonical Aetna URL `https://www.aetna.com/cpb/medical/data/200_299/0236.html` returned an Incapsula bot-challenge page (incident ID 1345000620024825391-18399296386830212) during direct fetching on 2026-04-23. The equivalent policy text was retrieved from Aetna's Spanish-portal mirror `https://es.aetna.com/cpb/medical/data/200_299/0236.html`, which served identical English-language policy content (Aetna's es. portal hosts English CPBs for Spanish-speaking user entry). Confirm that the mirrored content is identical to the canonical URL on a future verification pass.
- Aetna CPB 0236 does not display an explicit "Last reviewed" date stamp in the retrieved HTML; recency was inferred from the reference list (most recent citations dated 2025 and an "Accessed February 6, 2026" reference). Engineer should treat the policy date as "unknown exact, recent as of early 2026."
- The eviCore V1.0.2026 PDF is large (~205 KB text-extracted); a single-call fetch exceeded the tool's 200 KB cap. A second fetch with a higher text-content token limit succeeded in returning the full Spine Imaging Guidelines through section SP-10 (Sacro-Iliac Joint Pain/Fibromyalgia) including all lumbar-relevant sections SP-1 through SP-6, which are the sections needed for this task.
- The ACR `acsearch.acr.org/docs/69483/narrative/` page renders as a Preview with the rating tables and variant definitions in full, but the narrative discussion per variant/procedure shows only headings in the extracted markdown (the narrative body is rendered dynamically). Variant tables, panel member list, references, and appropriateness categories are complete; per-procedure prose discussion was not captured and was not needed for the extraction.
- No Wayback Machine fallback was used because primary sources all resolved.
- CPB 0743 (Aetna Spinal Surgery) was verified via search snippets; the full text was not re-fetched because CPB 0743 addresses surgical medical necessity and does not restate MRI-specific thresholds. CPB 0016 (Back Pain Invasive Procedures) was surfaced in passing and confirms Aetna's use of a 6-week conservative-therapy threshold for injection procedures, consistent with CPB 0236's radiculopathy threshold.

---

## Normalized `TherapyTrial.kind` taxonomy

Added in response to [PR #6 review comment](https://github.com/agents-assemble/priorauth-agent/pull/6#pullrequestreview-4166440051) — closes the loop between policy phrasing above and `shared/models.py::TherapyTrial.kind`.

Cigna/eviCore and Aetna use different terms for the same conservative-therapy concepts. The rule engine evaluates against a *single* normalized `kind` string per trial, so each payer JSON's `accepted_kinds: list[str]` must reference these normalized values — NOT the policy's original phrasing. `fetch_patient_context` is responsible for mapping FHIR source codes (RxNorm drug class, SNOMED/CPT procedure codes, free-text note content) into this same normalized space.

| Normalized `TherapyTrial.kind` | Cigna/eviCore phrasing (SP-1.0) | Aetna CPB 0236 phrasing (footnote) | Notes |
|---|---|---|---|
| `ACTIVITY_MODIFICATION` | "activity modification", "avoidance of aggravating activities", "cross-training" | "moderate activity" | Aetna's "moderate activity" treated as equivalent. Self-reported activity change qualifies; no session count. |
| `EDUCATION` | "education" | — | Patient education on posture/body mechanics. Cigna names explicitly; Aetna does not. |
| `NSAID` | "NSAIDs" | "non-steroidal anti-inflammatory drugs" | Direct match. Maps from RxNorm ATC class M01A. |
| `ANALGESIC_NON_OPIOID` | "non-narcotic analgesic medications" | "analgesics" (non-opioid) | Acetaminophen, adjuvant analgesics (non-gabapentinoid). |
| `ANALGESIC_OPIOID` | "narcotic analgesic medications" | "analgesics" (opioid) | Short-course opioids. Presence does NOT imply quality-of-trial; opioid trials are a red-flag-adjacent signal, not a conservative-therapy badge. |
| `MUSCLE_RELAXANT` | (not named; Cigna buckets under broader "non-narcotic analgesic medications") | "muscle relaxants" | Cyclobenzaprine, tizanidine, methocarbamol, metaxalone. Aetna names explicitly — matters for Patient B analysis (see §Conflicts). |
| `GABAPENTINOID` | (not named explicitly; adjuvant analgesic — ambiguous) | — | Gabapentin, pregabalin. Neither policy names; present in `shared/models.py::TherapyTrial.kind` docstring examples. Flagged as gap requiring clinician review before Week 3. |
| `ORAL_CORTICOSTEROID` | "oral corticosteroids" | — | Short-course prednisone / methylprednisolone dose pack. Cigna names; Aetna does not. |
| `EPIDURAL_INJECTION` | "injectable corticosteroids", "interventional pain procedures" | — (addressed in CPB 0016, not 0236) | Transforaminal / interlaminar ESI. Cigna's "severe radicular pain" red-flag bypass requires ESI to be **planned**, not completed — separate semantic from counting ESI as a completed conservative-therapy trial. |
| `PHYSICAL_THERAPY` | "physical therapy" | — (arguably subsumed under "moderate activity", but NOT named) | **Disagreement**: Cigna names PT explicitly and requires "provider-directed" for home exercise; Aetna's CPB 0236 footnote does not name PT at all. Drives Patient B's cross-payer asymmetry. See §Conflicts. |
| `OCCUPATIONAL_THERAPY` | "occupational therapy" | — | Rare for lumbar LBP in practice; included for completeness. Cigna treats as equivalent to PT for conservative-therapy accounting. |
| `SPINAL_MANIPULATION` | "spinal manipulation" | — | Chiropractic care. Cigna explicitly qualifying; Aetna silent — flagged gap for clinician review. |
| `HOME_EXERCISE` | "provider-directed home exercise/stretching program" | — | **Cigna gate**: must be provider-directed. Self-directed (e.g. Patient B's YouTube stretches from `demo/clinical_notes/patient_b.md`) does NOT qualify under Cigna. Aetna silent. |

### Integration implications for the JSON-encoding PR

- Each payer JSON's `accepted_kinds: list[str]` references the normalized column only. Policy phrasing can live in `CriterionCheck.description` for human-readability but never in `accepted_kinds`.
- `fetch_patient_context` must produce `TherapyTrial.kind` values from the normalized set — document the FHIR → normalized mapping in a dedicated `docs/therapy_normalization.md` when the JSON-encoding PR lands (RxNorm class → `NSAID`, SNOMED 91251008 → `PHYSICAL_THERAPY`, CPT 62323 → `EPIDURAL_INJECTION`, free-text "YouTube stretches" → NOT `HOME_EXERCISE` under Cigna, etc.).
- Per AGENTS.md, any change to `shared/models.py` requires both-reviewer approval. Options for the JSON-encoding PR:
  - **Option A (stricter)**: tighten `TherapyTrial.kind` from free-form `str` to `Literal[...]` or `StrEnum` covering the 13 normalized values above. Pro: machine-enforced normalization, IDE autocomplete. Con: every new policy addition requires a `shared/` PR.
  - **Option B (looser)**: keep `kind: str`, add a class-level docstring table listing the canonical 13 values, add a `tests/shared/test_therapy_kind_taxonomy.py` golden-file test that asserts both payer JSONs only reference canonical values. Pro: flexible, `shared/` stays stable. Con: drift possible if future JSONs bypass the lint.
  - Recommendation: Option B for now (avoids a both-reviewer gate on every new payer), revisit at Week 3 if the engine surfaces kind-mismatches.

### Gaps requiring clinician review (Week 3 candidate — per `docs/PLAN.md` §Risk Register)

- **`GABAPENTINOID`**: not named in either payer policy. Is a documented gabapentin trial (common for radicular pain) a qualifying conservative-therapy trial for lumbar MRI authorization, or does it not count?
- **Aetna silence on PT**: does a completed 8-session PT course satisfy CPB 0236's footnote, or does Aetna in practice require all four named items (moderate activity + analgesics + NSAIDs + muscle relaxants)? Utilization-review practice may differ from footnote letter.
- **`SPINAL_MANIPULATION`**: Aetna silent. Does documented chiropractic care count as conservative therapy under Aetna? Cigna says yes.
- **`ANALGESIC_OPIOID`**: neither policy says opioid-only trials are disqualifying, but clinically a pure opioid trial is considered inadequate conservative therapy. Confirm whether the rule engine should weight opioid-only trials differently than NSAID-plus-anything trials.

### Cross-reference to existing artifacts

- `shared/models.py::TherapyTrial.kind` — currently `str` with 5 informal docstring examples (`NSAID`, `MUSCLE_RELAXANT`, `GABAPENTINOID`, `PHYSICAL_THERAPY`, `EPIDURAL_INJECTION`). The taxonomy above is a superset; the JSON-encoding PR is the natural moment to reconcile.
- `demo/clinical_notes/patient_a.md` — documents NSAID (naproxen) + `MUSCLE_RELAXANT` (cyclobenzaprine) + `PHYSICAL_THERAPY` (8 sessions). Expected to pass all conservative-therapy checks on both payers.
- `demo/clinical_notes/patient_b.md` — documents NSAID only (PT incomplete, self-directed YouTube stretches). Under the taxonomy above: clears `NSAID`, fails `PHYSICAL_THERAPY` (Cigna provider-directed gate), fails `HOME_EXERCISE` (Cigna provider-directed gate), potentially clears `ACTIVITY_MODIFICATION` (Aetna "moderate activity" — loose read). Confirms Sanjit's review observation that Patient B is a stronger needs-info signal against Cigna than Aetna under the letter of the policy.
- `demo/clinical_notes/patient_c.md` — red-flag fast-track; conservative-therapy composition does not matter (criteria bypassed under both payers' red-flag provisions).