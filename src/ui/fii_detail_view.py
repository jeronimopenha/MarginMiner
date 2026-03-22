from PyQt6 import QtWidgets

from src.ui.frmFiiDetail import Ui_DlgFiiDetails


def _safe_str(value, default="--"):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


class FiiDetailView(QtWidgets.QDialog, Ui_DlgFiiDetails):
    def __init__(self, fii_data: dict, parent=None):
        super().__init__(parent)

        self.fii_data = fii_data or {}

        self.setupUi(self)

        self.setWindowTitle(f"Detalhes do FII - {_safe_str(self.fii_data.get('TICKER'))}")

        self.btnFechar.clicked.connect(self.close)

        self.fill_basic_data()

    def fill_basic_data(self):
        d = self.fii_data

        # Cabeçalho
        self.lblTicker.setText(_safe_str(d.get("TICKER"), "FII"))
        self.lblNome.setText(_safe_str(d.get("NOME"), _safe_str(d.get("TICKER"))))
        self.lblSegmento.setText(_safe_str(d.get("SEGMENTO"), _safe_str(d.get("SEG"))))
        self.lblDataRef.setText(_safe_str(d.get("DATA_REF")))
        self.lblPrecoAtual.setText(_safe_str(d.get("PRECO"), "R$ 0,00"))

        # Resumos
        self.lblPvp.setText(_safe_str(d.get("P/VP"), "0,00"))
        self.lblVpa.setText(_safe_str(d.get("VPC"), "R$ 0,00"))
        self.lblDy12.setText(_safe_str(d.get("DY"), "0,00%"))

        self.lblVol12.setText("--")
        self.lblBeta.setText("--")
        self.lblSharpe12.setText("--")

        self.lblRet12.setText("--")
        self.lblCagr5.setText("--")
        self.lblMaxDrawdown.setText("--")

        self.lblCapm.setText("--")
        self.lblAlpha.setText("--")
        self.lblTreynor.setText("--")

        # Aba Geral
        self.lblGestao.setText(_safe_str(d.get("GESTAO")))
        self.lblPatrimonio.setText(_safe_str(d.get("PATRIMONIO"), "R$ 0,00"))
        self.lblCotistas.setText(_safe_str(d.get("N COTISTAS"), "0"))
        self.lblNumCotas.setText(_safe_str(d.get("N COTAS"), "0"))
        self.lblPercCaixa.setText(_safe_str(d.get("PERC.CAIXA"), _safe_str(d.get("PERC_CAIXA"), "0,00%")))
        self.lblLiqDiaria.setText(_safe_str(d.get("LIQUIDEZ MEDIA DIARIA"), _safe_str(d.get("LIQ_DIARIA"), "R$ 0,00")))

        self.lblSortino.setText("--")
        self.lblCalmar.setText("--")
        self.lblInformationRatio.setText("--")
        self.lblTrackingError.setText("--")
        self.lblJensenAlpha.setText("--")

        self.txtObservacoes.setPlainText(
            "Janela inicial criada.\n"
            "As métricas quantitativas serão preenchidas nas próximas etapas."
        )