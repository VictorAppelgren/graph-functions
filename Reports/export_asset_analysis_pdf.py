import sys, os
import datetime
from fpdf import FPDF

# --- Canonical project root import pattern ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph_utils.get_topic_id_by_name import get_topic_id_by_name
from func_analysis.report_aggregator import aggregate_reports
from utils import minimal_logging

logger = minimal_logging.get_logger(__name__)

# --- CONFIG ---
ASSET = "S&P 500"
PDF_DIR = os.path.join(os.path.dirname(__file__), "PDFs")
DATE = datetime.datetime.now().strftime("%Y_%m_%d")

# Minimal text sanitizer for latin-1 PDF backend
def sanitize_text(s: str) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    # Replace common unicode punctuation with ascii equivalents
    replacements = {
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2026": "...",  # ellipsis
        "\u00a0": " ",  # nbsp
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    # Final guard: drop any remaining non-latin1 glyphs
    return s.encode("latin-1", errors="ignore").decode("latin-1")

def get_topic_id_and_analysis(topic_name):
    """
    Deprecated wrapper. Use get_topic_id_by_name() and aggregate_reports().
    """
    logger.info(f"exporter | resolve_topic_id | name={topic_name}")
    topic_id = get_topic_id_by_name(topic_name)
    logger.info(f"exporter | resolved | name={topic_name} -> id={topic_id}")
    analysis_fields = aggregate_reports(topic_id)
    logger.info(f"exporter | aggregated | sections={list(analysis_fields.keys())}")
    if not analysis_fields:
        raise RuntimeError(f"No analysis fields found for topic '{topic_name}' (id={topic_id})")
    return topic_id, analysis_fields

def get_next_pdf_path(asset, date):
    base = os.path.join(PDF_DIR, f"{asset}_{date}.pdf")
    if not os.path.exists(base):
        return base
    # Versioning: _v2, _v3, ...
    i = 2
    while True:
        path = os.path.join(PDF_DIR, f"{asset}_{date}_v{i}.pdf")
        if not os.path.exists(path):
            return path
        i += 1

def export_pdf(asset, analysis_fields, pdf_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(0, 12, f"{asset} Analysis Report", ln=True, align='C')
    pdf.ln(10)
    logger.info(f"exporter | writing_pdf | sections={len(analysis_fields)} | path={pdf_path}")
    # Place executive_summary at the top if present
    ordered_sections = []
    if 'executive_summary' in analysis_fields:
        ordered_sections.append(('executive_summary', analysis_fields['executive_summary']))
    # Place movers_scenarios immediately after executive_summary if present
    if 'movers_scenarios' in analysis_fields:
        ordered_sections.append(('movers_scenarios', analysis_fields['movers_scenarios']))
    # Then place swing_trade_or_outlook if present
    if 'swing_trade_or_outlook' in analysis_fields:
        ordered_sections.append(('swing_trade_or_outlook', analysis_fields['swing_trade_or_outlook']))
    for k, v in analysis_fields.items():
        if k not in ('executive_summary', 'movers_scenarios', 'swing_trade_or_outlook'):
            ordered_sections.append((k, v))
    for title, text in ordered_sections:
        length = len(str(text)) if text is not None else 0
        logger.info(f"exporter | section | title={title} | length={length}")
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, title.replace("_", " ").title(), ln=True)
        pdf.set_font("Arial", '', 12)
        safe_text = sanitize_text(text)
        if len(safe_text) != length:
            logger.info(
                f"exporter | sanitized | title={title} | before_len={length} | after_len={len(safe_text)}"
            )
        pdf.multi_cell(0, 6, safe_text)
        pdf.ln(2)
    pdf.output(pdf_path)
    logger.info(f"exporter | saved | path={pdf_path}")
    print(f"PDF saved to: {pdf_path}")

if __name__ == "__main__":
    os.makedirs(PDF_DIR, exist_ok=True)
    logger.info(f"exporter | start | asset={ASSET} | date={DATE}")
    topic_id, analysis_fields = get_topic_id_and_analysis(ASSET)
    pdf_path = get_next_pdf_path(ASSET, DATE)
    export_pdf(ASSET, analysis_fields, pdf_path)
