# Lab Triage Specification v1
_Specialty: San phu khoa - Dr4women_
_Baseline rules. Hieu chinh threshold sau khi co data that + BS review._

## Nguyen tac phan nhom

| Group | Dinh nghia | AI behavior | Hanh dong he thong |
|---|---|---|---|
| GROUP_A | Binh thuong (flag=NORMAL) | AI duoc phep tra loi BN | Auto-notify, requires_doctor_review=FALSE |
| GROUP_B | Bat thuong nhe/borderline (HIGH/LOW/ABNORMAL) | AI chi goi y, kem "Vui long cho bac si xac nhan" | Task BS review, requires_doctor_review=TRUE |
| GROUP_C | Critical / nguy hiem san khoa | HARD BLOCK - AI khong sinh phan hoi BN | Escalate URGENT, block cho den khi BS finalize |

## GROUP_C patterns

### Beta-hCG
- BHCG < 5 mIU/mL o thai phu da xac nhan co thai
- BHCG khong tang gap doi sau 48h
- BHCG > 200000 mIU/mL khong tuong ung tuoi thai

### NIPT / Sang loc truoc sinh
- NIPT/Double/Triple test high-risk (T21/T18/T13/SLOS)
- AFP > 2.5 MoM hoac < 0.5 MoM

### Glucose / GDM
- Glucose doi > 126 mg/dL (7.0 mmol/L)
- OGTT 2h > 200 mg/dL (11.1 mmol/L)
- Glucose < 50 mg/dL

### Huyet hoc / Thieu mau nang
- Hb < 70 g/L
- Tieu cau < 50000/uL
- Tieu cau < 100000/uL kem men gan cao

### Chuc nang gan / Tien san giat
- AST hoac ALT > 70 U/L o tam ca nguyet 2-3
- Bilirubin total > 3 mg/dL

### Chuc nang than
- Creatinine > 1.2 mg/dL o thai phu
- Protein nieu >= 2+ hoac > 300 mg/24h

### Nhiem trung / TORCH
- HIV reactive (lan dau phat hien)
- Rubella IgM duong tinh o tam ca nguyet 1
- Syphilis (RPR/VDRL) reactive
- HBsAg duong tinh
- CMV IgM duong tinh o thai phu

### Sinh hoa cap cuu
- flag = CRITICAL_HIGH hoac CRITICAL_LOW
- Kali > 6.0 hoac < 2.5 mmol/L
- Natri > 155 hoac < 125 mmol/L

## GROUP_B examples
- Hb 70-110 g/L
- Glucose doi 100-125 mg/dL
- TSH 4.0-10.0 mU/L
- Bach cau 11000-15000

## GROUP_A
- flag = NORMAL
- Result trong [reference_range_low, reference_range_high]
- Khong match B/C

## Safety Gate principles (CANON v6)
1. Rule-first, AI-fallback
2. Default deny: khong phan loai duoc -> GROUP_B
3. Application HARD BLOCK: check triage_group != GROUP_C AND is_finalized = TRUE truoc khi gui BN
4. DB-level: constraint + partial index cho pending review
