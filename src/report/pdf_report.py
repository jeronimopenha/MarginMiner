from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


class PdfReport:

    @staticmethod
    def generate(fii_view, filepath: str):
        doc = SimpleDocTemplate(filepath)
        styles = getSampleStyleSheet()
        elements = []

        # ===== HEADER =====
        ticker = fii_view.lblTicker.text()
        nome = fii_view.lblNome.text()
        preco = fii_view.lblPrecoAtual.text()

        elements.append(Paragraph(f"<b>{ticker}</b> - {nome}", styles["Title"]))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"Preço atual: {preco}", styles["Normal"]))
        elements.append(Spacer(1, 20))

        # ===== RESUMO =====
        elements.append(Paragraph("Resumo", styles["Heading2"]))

        resumo_data = [
            ["P/VP", fii_view.lblPvp.text()],
            ["VP/Cota", fii_view.lblVpa.text()],
            ["DY 12m", fii_view.lblDy12.text()],
            ["Volatilidade 12m", fii_view.lblVol12.text()],
            ["Sharpe", fii_view.lblSharpe12.text()],
            ["Beta", fii_view.lblBeta.text()],
            ["Retorno 12m", fii_view.lblRet12.text()],
            ["CAGR 5a", fii_view.lblCagr5.text()],
            ["Max Drawdown", fii_view.lblMaxDrawdown.text()],
        ]

        table = Table(resumo_data)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # ===== INDICADORES EXTRAS =====
        elements.append(Paragraph("Indicadores Extras", styles["Heading2"]))

        extra_data = [
            ["Sortino", fii_view.lblSortino.text()],
            ["Calmar", fii_view.lblCalmar.text()],
            ["Information Ratio", fii_view.lblInformationRatio.text()],
            ["Tracking Error", fii_view.lblTrackingError.text()],
            ["Jensen Alpha", fii_view.lblJensenAlpha.text()],
        ]

        table = Table(extra_data)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # ===== CAPM =====
        elements.append(Paragraph("CAPM", styles["Heading2"]))

        capm_data = [
            ["Risk Free", fii_view.lblRiskFree.text()],
            ["Prêmio de mercado", fii_view.lblPremioMercado.text()],
            ["CAPM", fii_view.lblCapmCalc.text()],
            ["Alpha", fii_view.lblAlphaCapm.text()],
            ["Treynor", fii_view.lblTreynorCapm.text()],
        ]

        table = Table(capm_data)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # ===== OBSERVAÇÕES =====
        obs = fii_view.txtObservacoes.toPlainText()

        if obs.strip():
            elements.append(Paragraph("Observações", styles["Heading2"]))
            elements.append(Paragraph(obs, styles["Normal"]))

        # ===== BUILD =====
        doc.build(elements)