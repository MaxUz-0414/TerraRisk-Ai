"""Small ReportLab drawings used in the certificate: line charts, factor bars, placeholders."""
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors

from .text import plain

LEVEL_COLORS = {"low": "#16a34a", "medium": "#d97706", "high": "#dc2626"}


def fill_gaps(values):
    """Replace missing points (None) by the nearest known value so a chart has no holes."""
    known = [v for v in values if v is not None]
    if not known:
        return [0] * len(values)
    out, last = [], known[0]
    for v in values:
        last = v if v is not None else last
        out.append(last)
    return out


def line_chart(labels, series, w=165, h=100):
    """series: [(name, values, '#hex')]"""
    d = Drawing(w, h)
    chart = HorizontalLineChart()
    chart.x, chart.y, chart.width, chart.height = 28, 18, w - 38, h - 28
    chart.data = [fill_gaps(s[1]) for s in series]
    chart.categoryAxis.categoryNames = [plain(label)[:3] for label in labels]
    chart.categoryAxis.labels.fontSize = 5.5
    chart.valueAxis.labels.fontSize = 6
    chart.valueAxis.gridStrokeColor = colors.HexColor("#e2e8f0")
    chart.valueAxis.visibleGrid = True
    for i, s in enumerate(series):
        chart.lines[i].strokeColor = colors.HexColor(s[2])
        chart.lines[i].strokeWidth = 1.5
    d.add(chart)
    return d


def factor_bars(factors, width, row_h=14):
    """Horizontal 0-100 bars, one per risk factor, coloured by level."""
    d = Drawing(width, max(row_h * len(factors), 1))
    label_w, value_w = 110, 34
    track_w = width - label_w - value_w - 6
    for i, f in enumerate(factors):
        y = row_h * (len(factors) - 1 - i)
        value = max(0, min(100, float(f.get("value") or 0)))
        color = colors.HexColor(LEVEL_COLORS.get(f.get("level"), "#64748b"))
        d.add(String(0, y + 4, plain(f.get("label", ""))[:34], fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#0a1422")))
        d.add(Rect(label_w, y + 3, track_w, 7, fillColor=colors.HexColor("#e2e8f0"), strokeColor=None))
        d.add(Rect(label_w, y + 3, max(track_w * value / 100, 1.5), 7, fillColor=color, strokeColor=None))
        d.add(String(label_w + track_w + 6, y + 4, f"{value:.0f}%", fontName="Helvetica-Bold", fontSize=8, fillColor=color))
    return d


def placeholder(w, h, text="Satellite picture unavailable"):
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, fillColor=colors.HexColor("#f1f5f9"), strokeColor=colors.HexColor("#cbd5e1"), strokeDashArray=[3, 3]))
    d.add(String(w / 2, h / 2 - 3, plain(text), fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#64748b"), textAnchor="middle"))
    return d
