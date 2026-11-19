"""Builds the "TerraRisk Resilience Certificate" PDF.

build_pdf(data, images) -> bytes
  data    the analysis (see app.py for the fields; everything except a few core fields is optional)
  images  {layer: jpeg bytes} for truecolor / ndvi / heat / water; a missing picture becomes a labelled placeholder
"""
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .charts import LEVEL_COLORS, factor_bars, line_chart, placeholder
from .text import num, plain, t

INK = colors.HexColor("#0a1422")
MUTED = colors.HexColor("#64748b")
GREEN = colors.HexColor("#16a34a")
LINE = colors.HexColor("#e2e8f0")
LEVEL_LABELS = {"low": "Low Risk", "medium": "Moderate Risk", "high": "High Risk"}

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=INK)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=INK, spaceBefore=10, spaceAfter=5)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK)
SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED)
CAPTION = ParagraphStyle("cap", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED, spaceBefore=2)

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
WIDTH = PAGE_W - 2 * MARGIN

LAYER_INFO = {
    "truecolor": ("True-colour view", "What the area looks like from space. The yellow line is the analysed area."),
    "ndvi": ("Vegetation (NDVI)", "Green is healthy plant cover; yellow and red mean sparse or bare ground, which sheds water faster."),
    "heat": ("Land surface heat", "Red is the hottest ground, blue the coolest. Hot spots mean less shade and more heat stress."),
    "water": ("Water and low ground", "Blue marks permanent water and ground low enough to flood first."),
}


def _level(data, key="level"):
    value = data.get(key)
    return value if value in LEVEL_COLORS else "medium"


def _picture(images, layer, width_mm, ratio=0.625):
    """A ReportLab flowable for one layer picture (1600x1000 source => ratio 0.625)."""
    w, h = width_mm * mm, width_mm * mm * ratio
    blob = images.get(layer)
    if blob:
        try:
            return Image(BytesIO(blob), width=w, height=h)
        except Exception:  # corrupt image: do not fail the whole report
            pass
    return placeholder(w, h)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(MARGIN, 16 * mm, PAGE_W - MARGIN, 16 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 11 * mm, f"TerraRisk Resilience Certificate  |  {plain(doc.report_id)}  |  Generated {doc.generated}")
    canvas.drawRightString(PAGE_W - MARGIN, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _header(data):
    logo = Table([[Paragraph('<font color="white"><b>TR</b></font>', ParagraphStyle("l", fontSize=13, alignment=TA_CENTER))]],
                 colWidths=[11 * mm], rowHeights=[11 * mm])
    logo.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    right = Paragraph(f'<font color="#64748b" size="8">Report {t(data["parcel_id"])}<br/>{t(data.get("date", ""))}</font>',
                      ParagraphStyle("r", alignment=2, leading=11))
    head = Table([[logo, Paragraph("<b>TerraRisk AI</b>", ParagraphStyle("b", fontSize=14, textColor=INK)), right]],
                 colWidths=[15 * mm, WIDTH / 2 - 15 * mm, WIDTH / 2])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return head


def _first_page(data, images):
    story = [_header(data), Spacer(1, 8), Paragraph("TerraRisk Resilience Certificate", H1)]
    place = data.get("place") or data.get("nickname")
    if place:
        story.append(Paragraph(f'<font color="#64748b">{t(place)}</font>', ParagraphStyle("sub", fontName="Helvetica", fontSize=11, leading=15)))
    story.append(Spacer(1, 6))

    hero = Table([[_picture(images, "truecolor", WIDTH / mm)]], colWidths=[WIDTH])
    hero.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1"))]))
    story += [hero, Paragraph("Satellite view of the analysed area (yellow outline). " + t(data.get("imagery_note", "")), CAPTION), Spacer(1, 5)]

    area = f"{data['area_ha']} ha" if data.get("area_ha") else "Point location"
    rows = [("Parcel ID", f"<b>{t(data['parcel_id'])}</b>"), ("Name", t(data.get("nickname", ""))),
            ("Coordinates", t(data.get("coords", "-"))), ("Area", t(area)), ("Hazard buffer", f"{t(data.get('buffer_km', '-'))} km"),
            ("Assessed for", t(data.get("persona", "-"))), ("Assessment date", t(data.get("date", "-")))]
    facts = Table([[Paragraph(k, SMALL), Paragraph(v, BODY)] for k, v in rows], colWidths=[28 * mm, WIDTH * 0.52 - 28 * mm])
    facts.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("TOPPADDING", (0, 0), (-1, -1), 1),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    level = _level(data)
    score_cell = [
        Paragraph(f'<font color="white"><b>{t(data["score"])}%</b></font>', ParagraphStyle("s1", fontName="Helvetica-Bold", fontSize=32, leading=36, alignment=TA_CENTER)),
        Paragraph(f'<font color="white">{t(LEVEL_LABELS[level])}</font>', ParagraphStyle("s2", fontName="Helvetica", fontSize=11, leading=14, alignment=TA_CENTER)),
        Paragraph('<font color="white">Composite risk score</font>', ParagraphStyle("s3", fontName="Helvetica", fontSize=7.5, leading=10, alignment=TA_CENTER)),
    ]
    hl = data.get("headline") or {}
    hl_cell = [
        Paragraph(t(hl.get("label", "")), SMALL),
        Paragraph(f'<font color="{LEVEL_COLORS.get(hl.get("level"), "#64748b")}"><b>{t(hl.get("value", ""))}</b></font>',
                  ParagraphStyle("hl", fontName="Helvetica-Bold", fontSize=22, leading=27)),
        Paragraph(t(hl.get("note", "")), SMALL),
    ]
    tile = Table([[score_cell], [hl_cell]], colWidths=[WIDTH * 0.46], rowHeights=[30 * mm, 21 * mm])
    tile.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor(LEVEL_COLORS[level])), ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#f1f5f9")),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 1), (0, 1), 14), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    top = Table([[facts, tile]], colWidths=[WIDTH * 0.52, WIDTH * 0.48])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [top, Spacer(1, 2)]

    verdict = data.get("verdict")
    if verdict:
        story += [Paragraph(f'<font color="{LEVEL_COLORS[_level(verdict)]}"><b>{t(verdict.get("title", ""))}</b></font>', H2),
                  Paragraph(t(verdict.get("text", "")), BODY)]
    return story


def _measurements(features):
    f = features or {}
    rows = [
        ("Upstream slope", num(f.get("upstream_slope_deg"), 1, " deg")),
        ("Distance to river", num(f.get("dist_to_river_m"), 0, " m")),
        ("Height above channel", num(f.get("hand_m"), 1, " m")),
        ("Upstream catchment", num(f.get("upstream_area_km2"), 1, " km2")),
        ("Plant cover trend", num(f.get("ndvi_trend_pct"), 1, " %", signed=True)),
        ("Peak land temperature", num(f.get("lst_peak_c"), 1, " C")),
        ("Heat vs normal", num(f.get("lst_anomaly_c"), 1, " C", signed=True)),
        ("Soil moisture change", num(f.get("soil_moisture_change_pct"), 1, " %", signed=True)),
        ("Rain, last 12 months", num(f.get("rain_12m_mm"), 0, " mm")),
        ("Rain vs normal", num(f.get("rain_anomaly_pct"), 1, " %", signed=True)),
        ("Water index (NDWI)", num(f.get("ndwi_now"), 2)),
        ("Built-up land within 500 m", num(f.get("built_up_pct"), 0, " %")),
    ]
    rows = [r for r in rows if r[1] != "-"]
    if not rows:
        return Paragraph("Detailed measurements were not available for this analysis.", SMALL)
    table = Table([[Paragraph(plain(k), SMALL), Paragraph(f"<b>{t(v)}</b>", BODY)] for k, v in rows], colWidths=[34 * mm, 18 * mm])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE), ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                               ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    return table


def _evidence(data, images):
    cell_w = (WIDTH - 6 * mm) / 2

    def tile(layer):
        title, text = LAYER_INFO[layer]
        pic = Table([[_picture(images, layer, cell_w / mm)]], colWidths=[cell_w])
        pic.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))]))
        return [Paragraph(f"<b>{t(title)}</b>", BODY), Spacer(1, 2), pic, Paragraph(t(text), CAPTION)]

    measures = [Paragraph("<b>Measured by satellite</b>", BODY), Spacer(1, 3), _measurements(data.get("features"))]
    grid = Table([[tile("ndvi"), tile("heat")], [tile("water"), measures]], colWidths=[cell_w + 3 * mm, cell_w + 3 * mm])
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 6),
                              ("RIGHTPADDING", (1, 0), (1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return [Paragraph("Satellite evidence", H2), grid]


def _hazards(data):
    rows = [[Paragraph("<b>Hazard</b>", SMALL), Paragraph("<b>Value</b>", SMALL), Paragraph("<b>Assessment</b>", SMALL)]]
    for h in data.get("hazards") or []:
        rows.append([Paragraph(t(h.get("label", "")), BODY),
                     Paragraph(f'<font color="{LEVEL_COLORS[_level(h)]}"><b>{t(h.get("value", ""))}</b></font>', BODY),
                     Paragraph(t(h.get("note", "")), BODY)])
    table = Table(rows, colWidths=[WIDTH * 0.32, WIDTH * 0.18, WIDTH * 0.5], repeatRows=1)
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [KeepTogether([Paragraph("Upstream buffer hazards", H2), table])]


def _cards(data):
    cards = data.get("cards") or []
    if not cards:
        return []
    cw = WIDTH / 3
    cells = []
    for c in cards[:6]:
        color = LEVEL_COLORS[_level(c)]
        cells.append([Paragraph(f'<font size="7.5" color="#64748b">{t(c.get("label", ""))}</font>', SMALL),
                      Paragraph(f'<font size="17" color="{color}"><b>{t(c.get("value", ""))}</b></font>', ParagraphStyle("cv", leading=21)),
                      Paragraph(t(c.get("note", "")), SMALL)])
    while len(cells) % 3:
        cells.append("")
    grid = Table([cells[i:i + 3] for i in range(0, len(cells), 3)], colWidths=[cw] * 3)
    grid.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfdff")), ("TOPPADDING", (0, 0), (-1, -1), 6),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    question = data.get("question")
    head = [Paragraph("What this means for you", H2)]
    if question:
        head.append(Paragraph(f"<i>{t(question)}</i>", SMALL))
        head.append(Spacer(1, 4))
    return [KeepTogether(head + [grid])]


def _factors(data):
    factors = data.get("factors") or []
    if not factors:
        return []
    return [KeepTogether([Paragraph("Risk factors at a glance", H2), factor_bars(factors, WIDTH),
                          Paragraph("Each bar is a 0-100 index: how strongly that hazard shows up in the satellite data around the area.", CAPTION)])]


def _charts(data):
    wanted = []
    ndvi = data.get("ndvi") or {}
    if ndvi.get("years"):
        palette = ["#a78bfa", "#38bdf8", "#16a34a"]
        series = [(y, v, palette[i % 3]) for i, (y, v) in enumerate(ndvi["years"].items())]
        wanted.append(("NDVI vegetation index", ndvi["labels"], series))
    lst = data.get("lst") or {}
    if lst.get("average"):
        wanted.append(("Land surface temperature (C)", lst["labels"], [("This year", lst["average"], "#0284c7"), ("Historic", lst["historic"], "#ea580c")]))
    rain = data.get("rain") or {}
    if rain.get("current"):
        wanted.append(("Rainfall (mm per month)", rain["labels"], [("Last 12 months", rain["current"], "#0284c7"), ("Normal", rain["average"], "#94a3b8")]))
    if not wanted:
        return []
    cw = WIDTH / len(wanted)
    cols = []
    for title, labels, series in wanted:
        legend = Paragraph("&nbsp;&nbsp;".join(f'<font color="{c}">&#9632;</font> {t(n)}' for n, _, c in series), SMALL)
        cols.append([Paragraph(f"<b>{t(title)}</b>", BODY), line_chart(labels, series, w=cw / 1 - 8, h=100), legend])
    table = Table([cols], colWidths=[cw] * len(cols))
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [KeepTogether([Paragraph("Satellite trends", H2), table])]


def _flags(data):
    flags = data.get("flags") or []
    out = []
    if flags:
        rows = [[Paragraph("<b>Flag</b>", SMALL), Paragraph("<b>Evidence</b>", SMALL), Paragraph("<b>What to do</b>", SMALL)]]
        for f in flags:
            rows.append([Paragraph(f'<font color="{LEVEL_COLORS[_level(f)]}"><b>{t(f.get("flag", ""))}</b></font>', BODY),
                         Paragraph(t(f.get("evidence", "")), BODY), Paragraph(t(f.get("action", "")), BODY)])
        table = Table(rows, colWidths=[WIDTH * 0.26, WIDTH * 0.28, WIDTH * 0.46], repeatRows=1)
        table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        out.append(KeepTogether([Paragraph("Due-diligence flags", H2), table]))
    scenarios = data.get("scenarios") or []
    if scenarios:
        rows = [[Paragraph("<b>If this happens</b>", SMALL), Paragraph("<b>Change</b>", SMALL), Paragraph("<b>New score</b>", SMALL), Paragraph("<b>Shift</b>", SMALL)]]
        for s in scenarios:
            delta = int(s.get("delta") or 0)
            color = "#dc2626" if delta > 0 else "#16a34a" if delta < 0 else "#64748b"
            rows.append([Paragraph(t(s.get("label", "")), BODY), Paragraph(t(s.get("detail", "")), BODY),
                         Paragraph(f'<font color="{LEVEL_COLORS[_level(s)]}"><b>{t(s.get("score", ""))}%</b></font>', BODY),
                         Paragraph(f'<font color="{color}"><b>{delta:+d} pts</b></font>', BODY)])
        table = Table(rows, colWidths=[WIDTH * 0.3, WIDTH * 0.4, WIDTH * 0.15, WIDTH * 0.15], repeatRows=1)
        table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        out.append(KeepTogether([Paragraph("Climate scenarios (what-if)", H2), table,
                                 Paragraph("Scenarios re-run the same screening model with one input changed. They are sensitivities, not forecasts.", CAPTION)]))
    return out


def _lists(data):
    out = []
    checklist = data.get("checklist") or {}
    if checklist.get("items"):
        block = [Paragraph(t(checklist.get("title", "Next steps")), H2)]
        if checklist.get("subtitle"):
            block.append(Paragraph(t(checklist["subtitle"]), SMALL))
        block += [Paragraph(f"&bull;&nbsp; {t(i)}", BODY) for i in checklist["items"]]
        out.append(KeepTogether(block))
    advisory = data.get("advisory") or []
    if advisory:
        block = [Paragraph("Operational advisory", H2)]
        for a in advisory:
            block += [Paragraph(f"&bull;&nbsp; <b>{t(a.get('label', ''))}:</b> {t(a.get('text', ''))}", BODY), Spacer(1, 3)]
        source = data.get("advisory_source")
        if source:
            block.append(Paragraph(f"Advice written by: {t(source)}", SMALL))
        out.append(KeepTogether(block))
    return out


def _method(data):
    sources = [
        "Imagery: Esri World Imagery (high-resolution base), Sentinel-2 and Landsat 8/9 (analysis layers).",
        "Vegetation and heat: MODIS NDVI and land-surface temperature, Landsat 8/9 surface temperature.",
        "Water and terrain: SRTM elevation, MERIT Hydro (height above nearest channel, catchment), JRC Global Surface Water.",
        "Climate: CHIRPS rainfall, ERA5-Land soil moisture, ESA WorldCover (built-up land).",
        "Scoring: transparent weighted hazard model plus a machine-learning landslide model. Scores are screening indices from 0 to 100 "
        "(below 40 low, 40-64 moderate, 65 and above high).",
    ]
    notes = data.get("notes") or []
    block = [Paragraph("Data and method", H2)] + [Paragraph(f"&bull;&nbsp; {t(s)}", SMALL) for s in sources]
    if notes:
        block += [Spacer(1, 3), Paragraph("Limits of this assessment", ParagraphStyle("h3", parent=BODY, fontName="Helvetica-Bold", spaceBefore=3))]
        block += [Paragraph(f"&bull;&nbsp; {t(n)}", SMALL) for n in notes]
    block += [Spacer(1, 6), Paragraph(
        "This certificate summarizes modelled, satellite-derived indicators for the area above. It is decision support, "
        "not a substitute for a professional survey, engineering assessment or insurance underwriting.", SMALL)]
    return [KeepTogether(block)]


def build_pdf(data, images=None):
    images = images or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=12 * mm, bottomMargin=20 * mm,
                            title=f"TerraRisk Resilience Certificate {plain(data['parcel_id'])}", author="TerraRisk AI",
                            subject=plain(data.get("place") or data.get("nickname") or ""))
    doc.report_id = data["parcel_id"]
    doc.generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story = _first_page(data, images)
    story += _factors(data)
    story.append(PageBreak())
    story += _evidence(data, images)
    story += _hazards(data)
    story += _cards(data)
    story += _charts(data)
    story += _flags(data)
    story += _lists(data)
    story += _method(data)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
