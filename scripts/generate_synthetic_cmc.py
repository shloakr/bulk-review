"""Generate 40 synthetic CMC PDFs with page-level ground truth.

Ground truth comes from the pre-rendered structured data object, never from
re-reading the PDF. Evidence pages are recorded at render time via zero-size
PageMarker flowables placed around each fact.

Outputs (staging — build_dataset.py shuffles/renames into the final corpus):
    data/_staging/synthetic/SYN-001.pdf ... SYN-040.pdf
    data/_staging/synthetic_ground_truth.json   (keyed by SYN id)
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SEED = 20260831
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "_staging" / "synthetic"
GT_PATH = ROOT / "data" / "_staging" / "synthetic_ground_truth.json"

N_DOCS = 40

# --------------------------------------------------------------------------
# Domain pools
# --------------------------------------------------------------------------

EXCIPIENTS = [
    ("Microcrystalline cellulose", ["Avicel PH-101", "Avicel PH-102", "Avicel PH-200"], "filler-binder"),
    ("Lactose monohydrate", ["FlowLac 100", "Tablettose 80", "Pharmatose 200M"], "diluent"),
    ("Magnesium stearate", ["Ligamed MF-2-V", "Kosher Passover grade HyQual"], "lubricant"),
    ("Croscarmellose sodium", ["Ac-Di-Sol SD-711", "Solutab Type A"], "disintegrant"),
    ("Povidone", ["Kollidon 30", "Kollidon 90F", "Plasdone K-29/32"], "binder"),
    ("Hypromellose", ["Methocel K4M Premium CR", "Methocel K100M Premium CR", "Methocel E5 Premium LV"], "release-controlling polymer"),
    ("Colloidal silicon dioxide", ["Aerosil 200 Pharma", "Cab-O-Sil M-5P"], "glidant"),
    ("Crospovidone", ["Kollidon CL", "Polyplasdone XL-10"], "disintegrant"),
    ("Mannitol", ["Pearlitol 100SD", "Pearlitol 200SD", "Parteck M200"], "diluent"),
    ("Sodium starch glycolate", ["Explotab", "Primojel"], "disintegrant"),
]

GUIDANCE_POOL = [
    "ICH Q8(R2)",
    "ICH Q6A",
    "USP-NF",
    "Ph. Eur. general monograph 2034",
    "ICH Q3D",
    "FDA Guidance for Industry: Immediate Release Solid Oral Dosage Forms",
    "IPEC Excipient Qualification Guide",
]

PRODUCT_NAMES = [
    "Zelvaritin", "Cormalent", "Dexpirona", "Aluvextra", "Tribenzalol",
    "Mavolutide", "Perquinolone", "Sertavance", "Klorvatran", "Ibexolimod",
    "Fenoprazil", "Lumateperax", "Ostivarene", "Quenzafil", "Ravolexin",
    "Tegravance", "Vilmodrine", "Xanthovar", "Brivalemer", "Cindrapect",
]

JUSTIFICATIONS = [
    "improved flowability during high-speed compression",
    "superior compactibility at low compression forces",
    "reduced sticking and picking observed during tableting trials",
    "tighter particle size distribution supporting content uniformity",
    "improved blend uniformity in geometric dilution studies",
    "lower moisture content mitigating hydrolytic degradation of the drug substance",
    "consistent dissolution performance across registration batches",
    "compatibility with the active ingredient demonstrated in binary stress studies",
    "robust tablet hardness across the compression force design space",
    "reduced lot-to-lot variability reported by the qualified supplier",
]

SECTION_HEADINGS = [
    "3.2.P.4 Control of Excipients",
    "P.4 Control of Excipients",
    "Control of Excipients (3.2.P.4)",
    "3.2.P.4 Excipient Control Strategy",
    "Section 3.2.P.4 — Excipients",
]

RATIONALE_HEADINGS = [
    "Grade Selection Rationale",
    "Basis for Selection",
    "Selection Justification",
    "Formulation Development Rationale",
    "Justification of Material Grade",
    "Excipient Grade Selection",
]

SPEC_HEADINGS = [
    "Current Commercial Specification",
    "Approved Drug Product Specification",
    "Registered Specification",
    "Commercial Control Strategy — Excipients",
]

FILLER_SECTIONS = [
    ("Manufacturing Process Overview",
     "The drug product is manufactured by a conventional wet granulation process comprising dispensing, "
     "high-shear granulation, fluid-bed drying, milling, blending, compression, and film coating. "
     "In-process controls are applied at each unit operation, including loss on drying after fluid-bed "
     "drying and blend uniformity prior to compression. Process parameters were established during "
     "process performance qualification and are maintained under the site quality system."),
    ("Container Closure System",
     "The commercial packaging configuration consists of high-density polyethylene bottles with "
     "child-resistant polypropylene closures and induction seal liners. Container closure integrity "
     "was demonstrated by dye ingress testing. The packaging components comply with applicable "
     "food-contact regulations and compendial requirements for plastic packaging systems."),
    ("Stability Summary",
     "Primary stability studies were conducted under ICH long-term (25°C/60% RH) and accelerated "
     "(40°C/75% RH) conditions on three registration batches. All quality attributes remained "
     "within acceptance criteria through the tested intervals. Photostability testing per ICH Q1B "
     "confirmed that the product is not photolabile in the commercial pack."),
    ("Batch Formula",
     "The representative commercial batch formula is provided for a nominal batch size of 400,000 "
     "tablets. Quantities of all components are expressed per tablet and per batch. Purified water "
     "is used as granulation fluid and is removed during processing; it does not appear in the "
     "final composition."),
    ("Control of Drug Product",
     "The drug product specification includes tests for description, identification, assay, "
     "uniformity of dosage units, dissolution, related substances, water content, and microbial "
     "limits. Analytical procedures are compendial where available; non-compendial procedures "
     "were validated in accordance with ICH Q2(R1)."),
    ("Analytical Method Validation Summary",
     "The assay and related-substances procedures employ reversed-phase high performance liquid "
     "chromatography with ultraviolet detection. Validation demonstrated acceptable specificity, "
     "linearity, accuracy, precision, and robustness. Forced degradation studies confirmed the "
     "stability-indicating capability of the related-substances method."),
    ("Reference Standards",
     "Primary reference standards for the drug substance and specified impurities are qualified "
     "against compendial standards where available. Working standards are qualified against the "
     "primary standard under an approved protocol and are stored under controlled conditions."),
    ("Facilities and Equipment",
     "Manufacturing is performed at the approved commercial site using dedicated product-contact "
     "equipment trains. Equipment qualification and cleaning validation are maintained under the "
     "site validation master plan. No changes to the approved facility registration are proposed."),
    ("Process Validation Summary",
     "Process performance qualification was executed on three consecutive commercial-scale batches. "
     "All predefined acceptance criteria for critical process parameters and critical quality "
     "attributes were met, supporting a conclusion of a validated state of control."),
    ("Regional Information",
     "No excipients of human or animal origin are used in the drug product with the exception of "
     "lactose monohydrate, for which a TSE/BSE compliance declaration is provided in Module 3.2.A.2. "
     "Certificates of suitability are maintained where applicable."),
]

# --------------------------------------------------------------------------
# Data model (ground truth is derived from this, never from the PDF)
# --------------------------------------------------------------------------

@dataclass
class SynDoc:
    internal_id: str
    product: str
    formulation_id: str
    excipient: str
    function: str
    excipient_grade: str
    justification: str            # canonical short phrase
    guidance_cited: list[str]
    current_spec_grade: str
    spec_id: str
    contradicts_current_spec: bool
    template: int
    hard_cases: list[str] = field(default_factory=list)
    # optional extra grades for hard cases
    historical_grade: str | None = None
    screening_grade: str | None = None
    obsolete_spec_grade: str | None = None
    justification_absent: bool = False
    # filled at render time: field_key -> set of pages
    evidence_pages: dict = field(default_factory=dict)


def build_docs(rng: random.Random) -> list[SynDoc]:
    docs: list[SynDoc] = []
    products = rng.sample(PRODUCT_NAMES, len(PRODUCT_NAMES))
    # contradiction labels: 20 true / 20 false, shuffled deterministically
    labels = [True] * 20 + [False] * 20
    rng.shuffle(labels)
    # hard cases assigned to specific doc indices (spread across both labels)
    hard_assignments = {
        0: ["historical_grade_first"],
        3: ["screening_grade_differs"],
        6: ["distant_spec_page"],
        9: ["guidance_in_table_footnote"],
        12: ["justification_absent"],
        15: ["multiple_grade_references"],
        18: ["indirect_rationale"],
        21: ["obsolete_spec_alongside"],
        24: ["distant_spec_page", "multiple_grade_references"],
        27: ["historical_grade_first", "obsolete_spec_alongside"],
        30: ["guidance_in_table_footnote"],
        33: ["indirect_rationale", "distant_spec_page"],
    }

    for i in range(N_DOCS):
        exc_name, grades, function = EXCIPIENTS[i % len(EXCIPIENTS)]
        contradicts = labels[i]
        selected = rng.choice(grades)
        others = [g for g in grades if g != selected]
        if contradicts:
            spec_grade = rng.choice(others) if others else selected + " (superseded)"
        else:
            spec_grade = selected

        hard = hard_assignments.get(i, [])
        n_guid = 1 if rng.random() < 0.35 else rng.randint(2, 3)
        guidance = rng.sample(GUIDANCE_POOL, n_guid)

        product = products[i % len(products)]
        doc = SynDoc(
            internal_id=f"SYN-{i + 1:03d}",
            product=product,
            formulation_id=f"F-{rng.randint(100, 999)}/{rng.choice(['A', 'B', 'C'])}",
            excipient=exc_name,
            function=function,
            excipient_grade=selected,
            justification=rng.choice(JUSTIFICATIONS),
            guidance_cited=guidance,
            current_spec_grade=spec_grade,
            spec_id=f"SPEC-EX-{rng.randint(1000, 9999)} Rev {rng.randint(1, 9):02d}",
            contradicts_current_spec=contradicts,
            template=i % 10,
            hard_cases=hard,
        )
        if "historical_grade_first" in hard and others:
            doc.historical_grade = others[0]
        if "screening_grade_differs" in hard and others:
            doc.screening_grade = others[-1]
        if "multiple_grade_references" in hard and others:
            doc.historical_grade = others[0]
            if len(others) > 1:
                doc.screening_grade = others[1]
        if "obsolete_spec_alongside" in hard:
            pool = [g for g in grades if g not in (selected, spec_grade)]
            doc.obsolete_spec_grade = pool[0] if pool else selected + " (pre-2019)"
        if "justification_absent" in hard:
            doc.justification_absent = True
        docs.append(doc)
    return docs


# --------------------------------------------------------------------------
# Render-time page tracking
# --------------------------------------------------------------------------

class PageMarker(Flowable):
    """Zero-size flowable that records the page it is drawn on."""

    def __init__(self, store: dict, key: str):
        super().__init__()
        self.store = store
        self.key = key
        self.width = 0
        self.height = 0

    def draw(self):
        self.store.setdefault(self.key, set()).add(self.canv.getPageNumber())


def marked(store: dict, key: str, *flowables):
    """Wrap flowables with start/end markers so mid-flowable page breaks are caught."""
    return [PageMarker(store, key), *flowables, PageMarker(store, key)]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def make_styles(rng: random.Random):
    base = getSampleStyleSheet()
    serif = rng.random() < 0.4
    body_font = "Times-Roman" if serif else "Helvetica"
    bold_font = "Times-Bold" if serif else "Helvetica-Bold"
    body = ParagraphStyle(
        "body", parent=base["BodyText"], fontName=body_font,
        fontSize=rng.choice([9.5, 10, 10.5]), leading=14, spaceAfter=8,
    )
    h1 = ParagraphStyle(
        "h1", parent=base["Heading1"], fontName=bold_font, fontSize=14, spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "h2", parent=base["Heading2"], fontName=bold_font, fontSize=11.5, spaceAfter=6,
    )
    small = ParagraphStyle(
        "small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#333333"),
    )
    return body, h1, h2, small


FILLER_SENTENCES = [
    "Change control procedures ensure that any modification to materials, methods, or equipment is assessed for regulatory impact prior to implementation.",
    "Supplier qualification includes periodic audits, review of certificates of analysis, and trending of incoming material test results.",
    "Risk assessments were performed in accordance with ICH Q9 principles, and residual risks were judged acceptable.",
    "Data supporting these conclusions are maintained at the manufacturing site and are available for inspection.",
    "Annual product quality reviews evaluate batch trends, deviations, complaints, and stability data to confirm the continued state of control.",
    "Environmental monitoring of the manufacturing areas is performed per the site monitoring program, with alert and action limits established from historical data.",
    "Hold-time studies established acceptable storage durations for intermediate blends and cores under defined conditions.",
    "Statistical evaluation of batch release data demonstrates process capability well within specification limits.",
    "Deviations observed during the campaign were investigated and closed with no impact to product quality.",
    "The control strategy links critical quality attributes to critical process parameters identified during development.",
    "Analytical results are trended electronically, and out-of-trend results trigger a documented laboratory investigation.",
    "Training records for personnel involved in manufacturing and testing are maintained under the site quality system.",
    "Cleaning verification swab results were below the health-based exposure limits derived for the product.",
    "No changes to the approved analytical procedures are proposed in this submission.",
    "The finished product is stored and distributed under controlled ambient conditions consistent with the approved label storage statement.",
    "Comparability of pilot- and commercial-scale batches was demonstrated with respect to dissolution and impurity profiles.",
]


def filler_flowables(rng: random.Random, body, h2, n_sections: int):
    out = []
    for title, text in rng.sample(FILLER_SECTIONS, n_sections):
        out.append(Paragraph(title, h2))
        out.append(Paragraph(text, body))
        # 1-2 additional paragraphs of generic regulatory prose per section
        for _ in range(rng.randint(1, 2)):
            sents = rng.sample(FILLER_SENTENCES, rng.randint(4, 6))
            out.append(Paragraph(" ".join(sents), body))
        out.append(Spacer(1, 10))
    return out


def guidance_sentence(doc: SynDoc, rng: random.Random) -> str:
    guid = doc.guidance_cited
    joined = ", ".join(guid[:-1]) + " and " + guid[-1] if len(guid) > 1 else guid[0]
    forms = [
        f"The excipient control strategy was developed in accordance with {joined}.",
        f"Grade selection and control follow the principles of {joined}.",
        f"The approach described herein is consistent with {joined}.",
        f"{doc.excipient} complies with the requirements of {joined}.",
    ]
    return rng.choice(forms)


def rationale_paragraph(doc: SynDoc, rng: random.Random) -> str:
    grade = doc.excipient_grade
    just = doc.justification
    if "indirect_rationale" in doc.hard_cases:
        return (
            f"During formulation development a number of {doc.excipient.lower()} grades were "
            f"evaluated. The development team ultimately proceeded with {grade}; batches "
            f"manufactured with this material consistently exhibited {just}, which the "
            f"alternative grades evaluated did not achieve at comparable levels."
        )
    forms = [
        f"{grade} was selected as the commercial grade of {doc.excipient.lower()} on the basis of {just}.",
        f"The selection of {grade} is justified by {just} observed during development studies.",
        f"The basis for selection of {grade} is {just}, demonstrated across three pilot-scale batches.",
        f"The formulation development rationale for {grade} rests on {just}.",
    ]
    return rng.choice(forms)


def selection_paragraph(doc: SynDoc, rng: random.Random) -> str:
    parts = []
    if doc.historical_grade and "historical_grade_first" in doc.hard_cases:
        parts.append(
            f"Early clinical formulations F-01 through F-03 employed {doc.historical_grade}. "
        )
    parts.append(
        f"For the commercial formulation {doc.formulation_id}, {doc.excipient_grade} "
        f"({doc.excipient}, {doc.function}) is used."
    )
    if doc.screening_grade:
        parts.append(
            f" {doc.screening_grade} was included in the excipient compatibility screen but was "
            f"not carried forward into the commercial formulation."
        )
    if doc.historical_grade and "multiple_grade_references" in doc.hard_cases:
        parts.append(
            f" References to {doc.historical_grade} elsewhere in this dossier pertain to "
            f"development history only."
        )
    return "".join(parts)


def spec_flowables(doc: SynDoc, rng: random.Random, body, h2, small, ev):
    """Current-specification section; table or prose."""
    heading = rng.choice(SPEC_HEADINGS)
    out = [Paragraph(heading, h2)]
    as_table = rng.random() < 0.5
    key = "contradicts_current_spec"
    if as_table:
        rows = [
            ["Component", "Function", "Grade per current specification"],
            [doc.excipient, doc.function, doc.current_spec_grade],
            ["Reference", "", doc.spec_id],
        ]
        t = Table(rows, colWidths=[2.1 * inch, 1.7 * inch, 2.6 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ]))
        out += marked(ev, key, t)
        out.append(Spacer(1, 6))
    else:
        out += marked(ev, key, Paragraph(
            f"The current approved commercial specification ({doc.spec_id}) lists "
            f"{doc.excipient} as {doc.current_spec_grade}.", body))
    if doc.obsolete_spec_grade:
        out.append(Paragraph(
            f"Note: the superseded specification (pre-2019, withdrawn) listed "
            f"{doc.obsolete_spec_grade}; it is retained here for historical traceability only "
            f"and has no bearing on the current control strategy.", small))
    out.append(Spacer(1, 10))
    return out


def guidance_flowables(doc: SynDoc, rng: random.Random, body, small, ev):
    key = "guidance_cited"
    if "guidance_in_table_footnote" in doc.hard_cases:
        rows = [
            ["Attribute", "Acceptance approach"],
            ["Identity", "Compendial monograph"],
            ["Assay / purity", "Compendial monograph"],
            ["Functionality-related characteristics", "Supplier certificate plus in-house verification*"],
        ]
        t = Table(rows, colWidths=[2.8 * inch, 3.4 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        guid = ", ".join(doc.guidance_cited)
        foot = Paragraph(f"* Control approach per {guid}.", small)
        return [t, *marked(ev, key, foot), Spacer(1, 10)]
    return [*marked(ev, key, Paragraph(guidance_sentence(doc, rng), body)), Spacer(1, 10)]


def render_doc(doc: SynDoc, out_path: Path, rng: random.Random):
    body, h1, h2, small = make_styles(rng)
    ev: dict[str, set] = {}

    story = []
    # Title block
    story.append(Paragraph(f"{doc.product} Film-Coated Tablets", h1))
    story.append(Paragraph(
        f"Module 3 Quality Documentation — Formulation {doc.formulation_id}", body))
    story.append(Spacer(1, 14))

    # Leading filler (varies where the relevant section lands)
    lead_fill = 2 + (doc.template % 3)
    story += filler_flowables(rng, body, h2, lead_fill)
    if doc.template in (2, 5, 8):
        story.append(PageBreak())
        story += filler_flowables(rng, body, h2, 2)

    # ---- Relevant CMC section ----
    story.append(Paragraph(rng.choice(SECTION_HEADINGS), h1))
    story += marked(ev, "excipient_grade", Paragraph(selection_paragraph(doc, rng), body))
    story.append(Spacer(1, 6))

    rationale_first = doc.template % 2 == 0
    rat_head = rng.choice(RATIONALE_HEADINGS)
    rat_flow = []
    if not doc.justification_absent:
        rat_flow = [Paragraph(rat_head, h2),
                    *marked(ev, "justification", Paragraph(rationale_paragraph(doc, rng), body)),
                    Spacer(1, 6)]
    guid_flow = guidance_flowables(doc, rng, body, small, ev)
    if rationale_first:
        story += rat_flow + guid_flow
    else:
        story += guid_flow + rat_flow

    # spec placement: adjacent or distant
    distant = "distant_spec_page" in doc.hard_cases
    if distant:
        story.append(PageBreak())
        story += filler_flowables(rng, body, h2, 4)
        story.append(PageBreak())
        story += filler_flowables(rng, body, h2, 3)
        story.append(PageBreak())
    story += spec_flowables(doc, rng, body, h2, small, ev)

    # trailing filler for length variation
    tail = rng.randint(2, 4) + (2 if doc.template in (4, 9) else 0)
    story.append(PageBreak())
    story += filler_flowables(rng, body, h2, tail)

    def footer(canv, docT):
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.drawString(0.75 * inch, 0.5 * inch,
                        f"{doc.product} — {doc.formulation_id} — Confidential")
        canv.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch,
                             f"Page {canv.getPageNumber()}")
        canv.restoreState()

    pdf = SimpleDocTemplate(
        str(out_path), pagesize=letter,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title=f"{doc.product} Module 3 Quality Documentation",
    )
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)

    # contradiction evidence = grade selection pages + spec pages
    ev.setdefault("contradicts_current_spec", set())
    ev["contradicts_current_spec"] |= ev.get("excipient_grade", set())
    doc.evidence_pages = {k: sorted(v) for k, v in ev.items()}


def expected_pages(pages: list[int]) -> list[int]:
    """Fill gaps caused by mid-flowable page breaks (start/end markers)."""
    if not pages:
        return []
    return list(range(min(pages), max(pages) + 1))


def ground_truth_entry(doc: SynDoc) -> dict:
    ev = doc.evidence_pages
    fields = {
        "excipient_grade": {
            "value": doc.excipient_grade,
            "status": "found",
            "expected_pages": expected_pages(ev.get("excipient_grade", [])),
        },
        "justification": {
            "value": None if doc.justification_absent else doc.justification,
            "status": "not_found" if doc.justification_absent else "found",
            "expected_pages": expected_pages(ev.get("justification", [])),
        },
        "guidance_cited": {
            "value": doc.guidance_cited,
            "status": "found",
            "expected_pages": expected_pages(ev.get("guidance_cited", [])),
        },
        "contradicts_current_spec": {
            "value": doc.contradicts_current_spec,
            "status": "found",
            # spec + grade pages; keep raw union (no gap filling across the doc)
            "expected_pages": sorted(set(ev.get("contradicts_current_spec", []))),
        },
    }
    return {
        "relevant": True,
        "product": doc.product,
        "excipient": doc.excipient,
        "template": doc.template,
        "hard_cases": doc.hard_cases,
        "fields": fields,
    }


def main():
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs = build_docs(rng)
    gt = {}
    for d in docs:
        out = OUT_DIR / f"{d.internal_id}.pdf"
        # per-doc rng so layout choices are deterministic per document
        doc_rng = random.Random(f"{SEED}:{d.internal_id}")
        render_doc(d, out, doc_rng)
        gt[d.internal_id] = ground_truth_entry(d)
        print(f"rendered {out.name}  pages_ev={d.evidence_pages}")
    GT_PATH.write_text(json.dumps(gt, indent=2))
    n_true = sum(1 for d in docs if d.contradicts_current_spec)
    print(f"\n{len(docs)} docs; contradiction true={n_true} false={len(docs) - n_true}")
    print(f"ground truth -> {GT_PATH}")


if __name__ == "__main__":
    main()
