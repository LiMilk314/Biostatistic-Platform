from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

d=Document(); sec=d.sections[0]; sec.orientation=WD_ORIENT.LANDSCAPE; sec.page_width=Inches(11); sec.page_height=Inches(8.5); sec.left_margin=sec.right_margin=Inches(.5); sec.top_margin=sec.bottom_margin=Inches(.5)
normal=d.styles['Normal']; normal.font.name='Arial'; normal.font.size=Pt(10); normal.paragraph_format.space_after=Pt(5)
t=d.add_paragraph('Biostat 619 Homework 3',style='Title'); t.runs[0].font.color.rgb=RGBColor(0,0,0); t.runs[0].font.size=Pt(15)
d.add_paragraph('1. Phase 1 trial comparison')
rows=[
['Gaudinski et al. (2017)', 'Assess safety and tolerability of two Zika DNA vaccine candidates.', 'Healthy adults, 18–35 years in VRC 319 and 18–50 in VRC 320, with acceptable history, examination and laboratory tests.', 'Two randomized, open-label trials; all injections 4 mg. VRC 319: four schedules (weeks 0/8, 0/12, 0/4/8, 0/4/20); VRC 320: weeks 0/4/8, single or split injection by needle or split needle-free.', '125 total: 80 in VRC 319 (20/group); 45 in VRC 320 (15/group).', 'Safety: local and systemic reactions within 7 days and adverse events within 28 days after each injection; serious events throughout follow-up.'],
['Kantarjian et al. (2017)', 'Evaluate AMG 900 safety, tolerability, pharmacokinetics, dosing schedule and maximum tolerated dose (MTD).', 'Adults with documented AML, relapsed/refractory or declining standard treatment; ECOG performance status 0–2 and life expectancy >3 months.', 'Open-label, sequential modified 3+3+3 escalation; oral dosing on 4 days on/10 off or 7 days on/7 off. Cohorts expand after DLTs and escalation stops at three DLTs.', '35 treated: 22 on 4/10 and 13 on 7/7.', 'Adverse events, DLTs, clinically important changes in clinical measures and labs, and pharmacokinetics (Cmax, Tmax, AUC).'],
['Muler et al. (2004)', 'Determine the MTD of cisplatin combined with full-dose gemcitabine and radiotherapy.', 'Adults with pathologically confirmed unresectable pancreatic cancer, with or without metastases; adequate organ function and performance status; no prior abdominal radiotherapy or pancreatic chemotherapy.', 'TITE-CRM began cisplatin at 30 mg/m² and assigned subsequent doses using accrued, time-weighted toxicity data, targeting a 20% DLT rate; gemcitabine and radiotherapy doses were fixed.', '19 treated; 18 assessable for toxicity.', 'Acute dose-limiting toxicity through the 9-week observation period, used to identify the target dose.'],
['Glass et al. (2012)', 'Assess the safety of lumbar spinal injection of human neural stem cells in ALS.', 'Adults with probable or definite ALS who could consent, undergo surgery and immunosuppression, and meet group-specific mobility and respiratory criteria.', 'Open-label risk escalation: nonambulatory then ambulatory participants received five unilateral or ten bilateral lumbar injections, 100,000 cells per injection; surgeries were at least one month apart.', '12 patients.', 'Safety of surgery, transplantation and immunosuppression, including adverse events and neurological function.'],
['Skrahin et al. (2014)', 'Assess safety of autologous mesenchymal stromal cells (MSCs) added to treatment for drug-resistant tuberculosis.', 'Adults >21–65 years with microbiologically confirmed pulmonary MDR/XDR tuberculosis; excluded pregnancy, HIV, hepatitis B/C and certain malignancy or extrapulmonary disease.', 'Open-label, single-arm phase 1: one autologous MSC infusion targeted at 1 million cells/kg within 4 weeks of starting antituberculosis treatment.', '30 treated; a separate matched historical cohort was used for exploratory comparisons.', 'Safety: infusion-related events, worsening tuberculosis, and clinical or laboratory adverse events over 6 months.']]
headers=['Trial','Primary objective','Eligibility criteria','Study design and dose assignment','Sample size','Primary endpoint']
table=d.add_table(rows=1, cols=6); table.style='Table Grid'; table.autofit=False
widths=[1.02,1.46,1.75,2.45,1.08,1.75]
for c,w,h in zip(table.rows[0].cells,widths,headers): c.width=Inches(w); c.text=h
for row in rows:
 cells=table.add_row().cells
 for c,w,s in zip(cells,widths,row): c.width=Inches(w); c.text=s
for ri,row in enumerate(table.rows):
 for cell in row.cells:
  for p in cell.paragraphs:
   p.paragraph_format.space_after=Pt(0); p.paragraph_format.line_spacing=1.0
   for run in p.runs: run.font.name='Arial'; run.font.size=Pt(8); run.bold=(ri==0)
 trpr=row._tr.get_or_add_trPr(); el=OxmlElement('w:cantSplit'); trpr.append(el)
d.add_page_break(); d.add_paragraph('2. Biased coin design')
items=[('a)', 'dose_assignment[, 1] selects the entire first column: the dose assigned to patient 1 in each simulated trial. With start = 1, every element is 1.'),('b)', 'true_probs[dose_assignment[, 1]] returns the true DLT probability corresponding to patient 1’s assigned dose in each trial. Here it is a vector of 100 values, each equal to 0.05.'),('c)', 'Let p = 0.05 and q = q_esc = 0.5. Before applying dose boundaries: P(decision = −1) = p = 0.05; P(decision = 0) = (1 − p)(1 − q) = 0.475; P(decision = 1) = (1 − p)q = 0.475. A decision of −1 at dose 1 would otherwise produce dose 0, which is not available.'),('d)', 'pmax compares corresponding elements and returns the larger value; pmax(1, dose + decision) enforces the lower boundary. To enforce both boundaries use pmin(length(true_probs), pmax(1, dose + decision)). The decision can indicate de-escalation at dose 1 or escalation at the highest dose, but the actual dose stays within the available range.'),('e)–g)', 'Each scenario below uses 1,000 trials of 30 patients, true probabilities (0.1, 0.2, 0.3, 0.4), starting dose 1, and set.seed(123) reset for each scenario. The entries are simulated proportions over all 30,000 assignments; results are subject to Monte Carlo variation.')]
for label,s in items: d.add_paragraph(label+'  '+s)
t=d.add_table(rows=1,cols=6); t.style='Table Grid'
for c,s in zip(t.rows[0].cells,['q_esc','Dose 1','Dose 2','Dose 3','Dose 4','Overall DLT rate']): c.text=s
for row in [['0.25','0.404100','0.331333','0.187700','0.076867','0.191800'],['0.50','0.189633','0.272800','0.299500','0.238067','0.256733'],['1.00','0.067600','0.147100','0.302400','0.482900','0.318600']]:
 for c,s in zip(t.add_row().cells,row): c.text=s
for c in t.rows[0].cells:
 for r in c.paragraphs[0].runs: r.bold=True
d.add_paragraph('Increasing q_esc shifts more patients toward higher doses and increases the overall DLT rate in these simulations.')
d.save('Homework_3_Answers.docx')
