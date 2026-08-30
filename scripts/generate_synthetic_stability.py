"""Generate 20 synthetic stability-protocol PDFs with page-level ground truth.

Second test set. Six fields per document:
    storage_condition, timepoints, acceptance_criteria, deviations,
    bracketing_justification, post_approval_commitment

Same discipline as the CMC generator: the data object is created before
rendering; ground truth comes from it, never from re-reading the PDF; evidence
pages recorded via PageMarker flowables.

Outputs (staging):
    data/_staging/stability/STB-001.pdf ... STB-020.pdf
    data/_staging/stability_ground_truth.json
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from generate_synthetic_cmc import PageMarker, expected_pages, make_styles, marked

SEED = 20260901
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "_staging" / "stability"
GT_PATH = ROOT / "data" / "_staging" / "stability_ground_truth.json"

N_DOCS = 20

PRODUCTS = [
    "Velmorapt", "Sondrelix", "Quibrantol", "Nexavorin", "Tolzepram",
    "Ardelmax", "Fluventra", "Gravistat", "Helixorin", "Ossivane",
    "Pardolint", "Rimvastex", "Cerulopam", "Dintravel", "Ebrantix",
    "Faldorene", "Gestrinal", "Ilvomida", "Jantreva", "Kolzepine",
]

STORAGE = [
    ("25°C ± 2°C / 60% RH ± 5% RH", "long-term ICH condition"),
    ("30°C ± 2°C / 65% RH ± 5% RH", "intermediate/zone IVa condition"),
    ("30°C ± 2°C / 75% RH ± 5% RH", "zone IVb condition"),
    ("5°C ± 3°C", "refrigerated condition"),
]
ACCELERATED = "40°C ± 2°C / 75% RH ± 5% RH"

TIMEPOINT_SETS = [
    [0, 3, 6, 9, 12, 18, 24],
    [0, 3, 6, 9, 12, 18, 24, 36],
    [0, 1, 3, 6, 9, 12, 18],
    [0, 3, 6, 12, 18, 24, 36, 48],
]

CRITERIA = [
    "Assay: 95.0–105.0% of label claim",
    "Total degradation products: not more than 2.0%",
    "Dissolution: Q = 80% in 30 minutes",
    "Water content: not more than 5.0% w/w",
    "Any individual unspecified degradant: not more than 0.20%",
]

DEVIATIONS = [
    "The {tp}-month timepoint for batch {b} was tested {d} days outside the ±7-day protocol window; a quality assessment concluded no impact on data validity.",
    "The {tp}-month samples for batch {b} were held at ambient conditions for {d} hours during chamber maintenance before testing; trending showed no anomalous results.",
    "Chamber excursion of +3°C for {d} hours affected the {tp}-month interval for batch {b}; mean kinetic temperature remained within limits.",
]

BRACKETING = [
    "In accordance with ICH Q1D, bracketing is applied: the {lo} mg and {hi} mg strengths are tested, and the intermediate {mid} mg strength is covered because all strengths are direct scale-equivalents of a common blend in the same container closure system.",
    "A bracketing design per ICH Q1D tests the extremes of the strength range ({lo} mg and {hi} mg); the {mid} mg strength shares identical formulation composition and packaging and is therefore not tested.",
    "Bracketing is justified under ICH Q1D on the basis that the {lo} mg and {hi} mg presentations bracket the {mid} mg presentation with respect to fill volume and surface-to-volume ratio.",
]

COMMITMENTS = [
    "The first three commercial-scale batches of {p} will be placed on the long-term stability program, with at least one production batch added annually thereafter.",
    "A post-approval commitment is made to enrol one commercial batch of {p} per year into the ongoing stability program and to report confirmed out-of-specification results within 30 days.",
    "As a condition of approval, three consecutive production batches of {p} will be entered into the stability program, and the retest period will be re-evaluated after 36-month data are available.",
]

FILLER = [
    ("Analytical Procedures",
     "Assay and degradation products are determined by the stability-indicating reversed-phase HPLC "
     "procedure described in the analytical methods dossier. Dissolution testing uses USP Apparatus II "
     "at 50 rpm. All procedures were validated in accordance with ICH Q2(R1) prior to protocol initiation."),
    ("Container Closure and Orientation",
     "Samples are stored in the commercial container closure system. Bottles are stored upright; "
     "a subset of inverted samples is included at the initial and final timepoints to assess "
     "closure-liner interaction. Induction seal integrity is verified at each pull."),
    ("Batch Selection",
     "The protocol covers three primary batches manufactured at commercial scale using the approved "
     "process. Batch genealogy, manufacturing dates, and packaging lots are recorded in the batch "
     "appendix. All batches were released against the approved specification prior to set-down."),
    ("Data Evaluation and Reporting",
     "Stability data are evaluated per ICH Q1E. Regression analysis is applied to quantitative "
     "attributes exhibiting change over time; poolability across batches is assessed at the 0.25 "
     "significance level. Annual reports summarize all data generated in the reporting interval."),
    ("Photostability",
     "Confirmatory photostability testing per ICH Q1B was completed during development and is not "
     "repeated in this protocol. The product is labeled for storage in the original container to "
     "protect from light."),
    ("Sample Inventory and Pull Windows",
     "Sample inventory per condition and timepoint is defined in the pull schedule appendix. "
     "Scheduled pulls are performed within ±7 days of the nominal date; pull records are maintained "
     "in the site stability management system."),
]


@dataclass
class StabDoc:
    internal_id: str
    product: str
    protocol_id: str
    storage_condition: str          # canonical long-term condition
    storage_desc: str
    timepoints: list[int]           # long-term months
    acceptance_criteria: str
    deviation: str | None           # None -> explicitly no deviations
    bracketing: str
    commitment: str
    template: int
    evidence_pages: dict = field(default_factory=dict)


def build_docs(rng: random.Random) -> list[StabDoc]:
    docs = []
    dev_flags = [True] * 14 + [False] * 6
    rng.shuffle(dev_flags)
    for i in range(N_DOCS):
        product = PRODUCTS[i]
        storage, desc = STORAGE[i % len(STORAGE)]
        tps = TIMEPOINT_SETS[i % len(TIMEPOINT_SETS)]
        lo, mid, hi = sorted(rng.sample([5, 10, 20, 25, 40, 50, 75, 100], 3))
        dev = None
        if dev_flags[i]:
            dev = rng.choice(DEVIATIONS).format(
                tp=rng.choice(tps[1:-1] or tps), b=f"{rng.randint(1, 3):03d}", d=rng.randint(8, 21))
        docs.append(StabDoc(
            internal_id=f"STB-{i + 1:03d}",
            product=product,
            protocol_id=f"STAB-P-{rng.randint(2019, 2025)}-{rng.randint(10, 99)}",
            storage_condition=storage,
            storage_desc=desc,
            timepoints=tps,
            acceptance_criteria=rng.choice(CRITERIA),
            deviation=dev,
            bracketing=rng.choice(BRACKETING).format(lo=lo, mid=mid, hi=hi),
            commitment=rng.choice(COMMITMENTS).format(p=product),
            template=i % 6,
        ))
    return docs


def render_doc(doc: StabDoc, out_path: Path, rng: random.Random):
    body, h1, h2, small = make_styles(rng)
    ev: dict[str, set] = {}
    story = []

    title = rng.choice(["Stability Protocol", "Stability Study Design",
                        "Commercial Stability Protocol", "Post-Approval Stability Protocol"])
    story.append(Paragraph(f"{doc.product} — {title}", h1))
    story.append(Paragraph(f"Protocol {doc.protocol_id}", body))
    story.append(Spacer(1, 12))

    def filler(n):
        out = []
        for t, txt in rng.sample(FILLER, n):
            out += [Paragraph(t, h2), Paragraph(txt, body), Spacer(1, 8)]
        return out

    story += filler(1 + doc.template % 2)

    # storage conditions (accelerated mentioned as a trap; canonical = long-term)
    story.append(Paragraph(rng.choice(["Storage Conditions", "Study Storage Conditions"]), h2))
    story += marked(ev, "storage_condition", Paragraph(
        f"The primary ({doc.storage_desc}) storage condition for this protocol is "
        f"{doc.storage_condition}. Accelerated studies at {ACCELERATED} were completed "
        f"through six months during development and are not part of this protocol.", body))
    story.append(Spacer(1, 8))

    # timepoints — table on even templates, prose otherwise
    story.append(Paragraph(rng.choice(["Testing Schedule", "Timepoints", "Pull Schedule"]), h2))
    if doc.template % 2 == 0:
        rows = [["Interval (months)"] + [str(t) for t in doc.timepoints],
                ["Long-term testing"] + ["X"] * len(doc.timepoints)]
        t = Table(rows)
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        story += marked(ev, "timepoints", t)
    else:
        tp_words = ", ".join(str(t) for t in doc.timepoints[:-1]) + f" and {doc.timepoints[-1]}"
        story += marked(ev, "timepoints", Paragraph(
            f"Long-term samples are tested at {tp_words} months.", body))
    story.append(Spacer(1, 8))

    mid_sections = []

    sec = [Paragraph(rng.choice(["Acceptance Criteria", "Stability Acceptance Criteria"]), h2)]
    sec += marked(ev, "acceptance_criteria", Paragraph(
        f"The stability acceptance criterion applied at each interval is — {doc.acceptance_criteria}. "
        f"All other registered specification tests apply unchanged.", body))
    sec.append(Spacer(1, 8))
    mid_sections.append(sec)

    sec = [Paragraph(rng.choice(["Bracketing Justification", "Bracketing and Matrixing"]), h2)]
    sec += marked(ev, "bracketing_justification", Paragraph(doc.bracketing, body))
    sec.append(Spacer(1, 8))
    mid_sections.append(sec)

    sec = [Paragraph(rng.choice(["Protocol Deviations", "Deviations"]), h2)]
    dev_text = doc.deviation or "No deviations from this protocol have been recorded to date."
    sec += marked(ev, "deviations", Paragraph(dev_text, body))
    sec.append(Spacer(1, 8))
    mid_sections.append(sec)

    sec = [Paragraph(rng.choice(["Post-Approval Commitments", "Stability Commitments"]), h2)]
    sec += marked(ev, "post_approval_commitment", Paragraph(doc.commitment, body))
    sec.append(Spacer(1, 8))
    mid_sections.append(sec)

    rng.shuffle(mid_sections)
    for j, sec in enumerate(mid_sections):
        if doc.template in (1, 4) and j == 2:
            story.append(PageBreak())
            story += filler(2)
        story += sec

    story.append(PageBreak())
    story += filler(2 + doc.template % 3)

    def footer(canv, docT):
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.drawString(0.75 * inch, 0.5 * inch, f"{doc.protocol_id} — Confidential")
        canv.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {canv.getPageNumber()}")
        canv.restoreState()

    pdf = SimpleDocTemplate(str(out_path), pagesize=letter,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            title=f"{doc.product} {title}")
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    doc.evidence_pages = {k: sorted(v) for k, v in ev.items()}


def ground_truth_entry(doc: StabDoc) -> dict:
    ev = doc.evidence_pages
    def f(key, value, status="found"):
        return {"value": value, "status": status,
                "expected_pages": expected_pages(ev.get(key, []))}
    return {
        "relevant": True,
        "product": doc.product,
        "template": doc.template,
        "fields": {
            "storage_condition": f("storage_condition", doc.storage_condition),
            "timepoints": f("timepoints", doc.timepoints),
            "acceptance_criteria": f("acceptance_criteria", doc.acceptance_criteria),
            "deviations": f("deviations", doc.deviation,
                            "found" if doc.deviation else "not_found"),
            "bracketing_justification": f("bracketing_justification", doc.bracketing),
            "post_approval_commitment": f("post_approval_commitment", doc.commitment),
        },
    }


def main():
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs = build_docs(rng)
    gt = {}
    for d in docs:
        doc_rng = random.Random(f"{SEED}:{d.internal_id}")
        render_doc(d, OUT_DIR / f"{d.internal_id}.pdf", doc_rng)
        gt[d.internal_id] = ground_truth_entry(d)
        print(f"rendered {d.internal_id} ev={ {k: v for k, v in d.evidence_pages.items()} }")
    GT_PATH.write_text(json.dumps(gt, indent=2))
    n_dev = sum(1 for d in docs if d.deviation)
    print(f"\n{len(docs)} docs; with deviations={n_dev}, without={len(docs) - n_dev}")


if __name__ == "__main__":
    main()
