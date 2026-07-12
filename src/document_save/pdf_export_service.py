import os
import logging
from datetime import datetime, date
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from src.document_save.filename_service import FilenameService
from config import FileRepo

logger = logging.getLogger(__name__)

PDF_MAX_ROWS = 500
NIB_BLUE = colors.HexColor("#1E40AF")


class PdfExportService:
    base_path = FileRepo.base_drive

    def save_to_pdf(self, results, query: ExecuteQueryDTO) -> str:
        """Generate PDF report with NIB header, summary stats, and data table."""
        filename = FilenameService.generate_filename(
            user_id=query.user_id,
            query_name=query.name,
            query_params=query.query_params,
            timestamp=datetime.now(),
        ).replace(".csv", ".pdf")

        file_path = os.path.join(
            self.base_path, "query_results",
            str(query.user_id), str(query.query_id), filename,
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "NIBTitle", parent=styles["Title"],
            textColor=NIB_BLUE, fontSize=16, spaceAfter=12,
        )
        subtitle_style = ParagraphStyle(
            "NIBSubtitle", parent=styles["Normal"],
            textColor=colors.gray, fontSize=10, spaceAfter=6,
        )
        # Data-table cells MUST be Paragraphs, not plain strings: ReportLab does
        # not wrap plain-string cells, so long values overflow the (often narrow)
        # column and overlap the neighbouring cell. Paragraphs wrap within the
        # column width and grow the row height instead. wordWrap="CJK" forces a
        # break inside long unbroken tokens (e.g. a 50-char no-space value in a
        # 26pt column) so nothing can spill past the cell edge.
        cell_style = ParagraphStyle(
            "NIBCell", parent=styles["Normal"],
            fontName="Helvetica", fontSize=6, leading=7, wordWrap="CJK",
        )
        header_cell_style = ParagraphStyle(
            "NIBHeaderCell", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=7, leading=8,
            textColor=colors.white, wordWrap="CJK",
        )

        elements = []

        # Header
        elements.append(Paragraph("National Insurance Board", title_style))
        elements.append(Paragraph(f"Query Report: {query.name}", subtitle_style))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            subtitle_style,
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Summary stats
        total_rows = len(results.rows) if results and results.rows else 0
        summary_data = [
            ["Total Rows", str(total_rows)],
        ]

        # Add numeric summaries
        if results and results.rows and results.column_names:
            for col_idx, col_name in enumerate(results.column_names):
                sample = [r[col_idx] for r in results.rows[:100] if r[col_idx] is not None]
                if sample and all(isinstance(v, (int, float, Decimal)) for v in sample):
                    values = [float(v) for v in [r[col_idx] for r in results.rows] if v is not None]
                    if values:
                        summary_data.append([f"{col_name} (Total)", f"{sum(values):,.2f}"])
                        summary_data.append([f"{col_name} (Avg)", f"{sum(values) / len(values):,.2f}"])

        summary_table = Table(summary_data, colWidths=[2.5 * inch, 3 * inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Data table (first 500 rows)
        if results and results.rows:
            truncated = results.rows[:PDF_MAX_ROWS]
            # Wrap every cell (header + body) in a Paragraph so text wraps within
            # the column instead of overflowing/overlapping (see cell_style note).
            header_row = [
                Paragraph(self._escape(str(c)), header_cell_style)
                for c in results.column_names
            ]
            table_data = [header_row] + [
                [Paragraph(self._escape(self._format_value(v)), cell_style) for v in row]
                for row in truncated
            ]

            # Calculate column widths based on content
            num_cols = len(results.column_names)
            page_width = landscape(letter)[0] - 1.5 * inch
            col_width = page_width / num_cols if num_cols > 0 else 2 * inch

            data_table = Table(table_data, colWidths=[col_width] * num_cols, repeatRows=1)
            data_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NIB_BLUE),
                # Fonts/colour for cell text now come from the Paragraph styles;
                # TableStyle keeps background, grid, alignment and padding.
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            elements.append(data_table)

            if total_rows > PDF_MAX_ROWS:
                elements.append(Spacer(1, 0.2 * inch))
                elements.append(Paragraph(
                    f"Showing first {PDF_MAX_ROWS} of {total_rows:,} rows. "
                    "Download the Excel or CSV export for the full dataset.",
                    subtitle_style,
                ))

        try:
            doc = SimpleDocTemplate(
                file_path, pagesize=landscape(letter),
                leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                topMargin=0.5 * inch, bottomMargin=0.5 * inch,
            )
            doc.build(elements)
            logger.info("PDF report saved: %s (%d rows)", file_path, total_rows)
        except Exception as e:
            logger.error("Error saving PDF: %s", e, exc_info=True)
            raise

        return file_path

    @staticmethod
    def _format_value(value) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return f"{float(value):,.2f}" if value % 1 else str(int(value))
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")
        return str(value)[:50]  # Truncate long strings for table cells

    @staticmethod
    def _escape(text: str) -> str:
        # Paragraph parses XML-ish markup, so &, <, > in data must be escaped
        # or they corrupt the cell (or raise). Values like "A & B" or "<null>"
        # would otherwise break rendering.
        from xml.sax.saxutils import escape
        return escape(text)
