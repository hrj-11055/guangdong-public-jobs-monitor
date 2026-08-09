---
name: guangdong-public-jobs-monitor
description: Monitor, verify, classify, and organize current Guangdong public-sector recruitment information, with dense Guangzhou coverage. Use for Guangdong or Guangzhou civil-service exams, selected graduates, public-institution staffing, public-institution contract roles, and state-owned-enterprise recruitment; for daily source scans; for extracting application dates, exam stages, eligibility, official syllabi, and document requirements; and for updating the bundled Excel tracking workbook without mixing different employment types.
---

# Guangdong Public Jobs Monitor

Build a source-grounded recruitment ledger from official notices. Cover Guangdong province broadly and Guangzhou deeply while keeping employment types separate.

## Start here

1. Read [references/source-map.md](references/source-map.md) before changing source coverage.
2. Read [references/verification-rules.md](references/verification-rules.md) before reporting or extracting any notice.
3. Read [references/data-schema.md](references/data-schema.md) before updating the workbook or CSV files.
4. Read [references/operations-plan.md](references/operations-plan.md) when setting up recurring or team operations.
5. Copy [assets/广东公考事业编监控台账.xlsx](assets/广东公考事业编监控台账.xlsx) to a working location. Never overwrite the asset master.
6. Run the deterministic scan from the skill root:

```bash
python3 scripts/monitor.py \
  --sources references/official-sources.json \
  --data-dir data
```

Use `--baseline` only for a new repository or after an intentional state reset. Use `--source-id SOURCE_ID` to diagnose one source.

## Classify before filtering

Assign exactly one primary employment type:

- `公务员`: administrative staffing recruited through a civil-service examination.
- `选调生`: selected-graduate civil-service recruitment.
- `参公`: staff of a public institution managed with reference to the Civil Servant Law. Do not silently merge into ordinary事业编.
- `事业编`: the notice explicitly says事业单位编制、事业编制、编制内 or that hired staff become事业单位在编人员.
- `编外`: auxiliary, employee, labor-contract, dispatched, purchased-service, community-worker, or other non-establishment role.
- `国企`: employment by a state-owned enterprise. This is not公务员 or事业编.
- `待核实`: the notice does not make the employment nature clear.

Preserve useful secondary tags such as `教师`, `医疗卫生`, `高校`, `科研`, `公安司法`, `遴选`, and `急需人才`.

## Daily workflow

### 1. Scan the source layers

Run all enabled A and B sources. The source map uses four layers:

1. statutory or authoritative national/provincial aggregators;
2. competent-authority pages for all 21 Guangdong prefecture-level cities;
3. all 11 Guangzhou district recruitment columns and Guangzhou application systems;
4. education, health, state-owned-assets, and announcement-named employer follow-up pages.

Treat a failed request as a source-health incident, never as evidence that no recruitment exists. Do not bypass CAPTCHA, login, rate limits, or access controls.

### 2. Triage discoveries

Keep links related to announcements, corrections, application, payment or confirmation, admission tickets, written tests, scores, qualification review, physical tests, interviews, medical exams, inspection, supplementary recruitment, and public notice of proposed hires.

Discard procurement, tendering, recruitment-service vendor selection, general news, training advertisements, and third-party reposts unless used only to locate the official original.

### 3. Verify the original

Open the original official notice and its attachments. Record the publishing authority, publication date, original URL, attachment names, and last verification timestamp. When a repost and original conflict, use the competent authority or recruiting unit's latest official version and record the conflict.

Track correction, suspension, cancellation, and supplementary notices as linked versions. Never overwrite history.

### 4. Extract the full candidate journey

Capture all applicable dates and conditions:

- notice date and application start/end;
- qualification-review window;
- payment or exam-confirmation window;
- admission-ticket window;
- written-test date, subjects, syllabus, location rule, and score-query date;
- physical-test, interview, medical-exam, inspection, and proposed-hire dates;
- headcount, job code, employer, department, district, target group, age, education, degree, major code, experience, household registration, political status, licenses, and other restrictions;
- application documents and qualification-review documents;
- original notice, application system, result-query page, and attachment URLs.

If the notice says that no textbook or preparation material is designated, record that sentence as `无指定教材` and do not recommend commercial material as official. Use only the official examination syllabus as the official preparation boundary.

### 5. Update the workbook

Use the workbook as a candidate-facing decision tool:

- update `招考机会` one row per recruitment project or job, depending on the user's requested granularity;
- update `关键时间点` one row per deadline or event;
- keep `信息源地图` synchronized with `references/official-sources.json`;
- mark document readiness in `材料清单` without storing identity numbers or sensitive scans in Git;
- enter personal filters only in a private copy of `个人条件`;
- keep URLs in plain text and preserve formulas, validations, filters, and conditional formatting.

## Completeness controls

Do not claim literal completeness from one scan. Report coverage in auditable terms:

- A-source success rate;
- B-source success rate;
- all 21 Guangdong prefecture-level cities checked automatically or named for manual follow-up;
- all 11 Guangzhou districts checked or named failures;
- announcement attachments opened or still pending;
- items awaiting employment-type verification;
- oldest successful verification time.

Perform a monthly source audit: check redirects, add new official employer follow-up pages discovered inside authoritative notices, disable retired annual portals only after preserving their history, and update `verified_on` in the source registry.

## Privacy and publishing

Never commit identity numbers, phone numbers, personal email, home address, private certificates, application screenshots, or a filled candidate profile. The repository `.gitignore` excludes common private filenames, but still inspect staged changes before publishing.

The bundled GitHub Actions workflow runs at 08:15 and 18:15 Asia/Shanghai time, writes source health and new-link data, commits changed public monitoring data, and opens an Issue only when a post-baseline discovery appears. Scheduled workflows may start late; deadlines must still be checked on the official page.
