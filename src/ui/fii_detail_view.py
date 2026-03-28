from PyQt6 import QtWidgets
import pandas as pd

from src.ui.frmFiiDetail import Ui_DlgFiiDetails
from src.data.fii_downloader import FiiDownloader
from src.metrics.fii_metrics import FiiMetrics
from src.ui.simple_pandas_model import SimplePandasModel


def _is_null(value) -> bool:
    try:
        import pandas as pd
        return pd.isna(value)
    except Exception:
        return value is None


def _safe_str(value, default="--"):
    if _is_null(value):
        return default
    text = str(value).strip()
    return text if text else default


def _fmt_float(value, decimals=2, default="--"):
    if _is_null(value):
        return default
    try:
        v = float(value)
        txt = f"{v:,.{decimals}f}"
        return txt.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return default


def _fmt_brl(value, decimals=2, default="--"):
    txt = _fmt_float(value, decimals=decimals, default=None)
    if txt is None:
        return default
    return f"R$ {txt}"


def _fmt_pct(value, decimals=2, default="--"):
    if _is_null(value):
        return default
    try:
        v = float(value)
        return f"{_fmt_float(v, decimals)}%"
    except Exception:
        return default


def _first_not_null(data: dict, *keys, default=None):
    for key in keys:
        if key in data and not _is_null(data[key]):
            return data[key]
    return default


class FiiDetailView(QtWidgets.QDialog, Ui_DlgFiiDetails):
    def __init__(self, fii_data: dict, parent=None):
        super().__init__(parent)

        self.fii_data = fii_data or {}

        self.setupUi(self)
        self.setWindowTitle(
            f"Detalhes do FII - {_safe_str(self.fii_data.get('TICKER'), 'FII')}"
        )

        self.btnAtualizarDados.clicked.connect(self.update_market_data)
        self.btnRecalcularMetricas.clicked.connect(self.recalculate_metrics)

        self.btnFechar.clicked.connect(self.close)

        self.selic_df = self.load_selic_cache()

        self.fill_basic_data()
        self.init_empty_tables()

    def fill_basic_data(self):
        d = self.fii_data

        ticker = _first_not_null(d, "TICKER", default="FII")
        segmento = _first_not_null(d, "SEGMENTO", "SEG", default="--")
        preco = _first_not_null(d, "PRECO")
        pvp = _first_not_null(d, "P/VP")
        vpc = _first_not_null(d, "VALOR PATRIMONIAL COTA")
        dy = _first_not_null(d, "DY")
        gestao = _first_not_null(d, "GESTAO")
        patrimonio = _first_not_null(d, "PATRIMONIO")
        cotistas = _first_not_null(d, "N COTISTAS")
        n_cotas = _first_not_null(d, "N COTAS")
        perc_caixa = _first_not_null(d, "PERCENTUAL EM CAIXA")
        liq_diaria = _first_not_null(d, "LIQUIDEZ MEDIA DIARIA")

        # Cabeçalho
        self.lblTicker.setText(_safe_str(ticker, "FII"))
        self.lblNome.setText(_safe_str(ticker, "FII"))
        self.lblSegmento.setText(_safe_str(segmento))
        self.lblDataRef.setText("--")
        self.lblPrecoAtual.setText(_fmt_brl(preco))
        self.lblPrecoObs.setText("Métricas históricas ainda não carregadas")

        # Cards resumo
        self.lblPvp.setText(_fmt_float(pvp))
        self.lblVpa.setText(_fmt_brl(vpc))
        self.lblDy12.setText(_fmt_pct(dy))

        self.lblVol12.setText("--")
        self.lblBeta.setText("--")
        self.lblSharpe12.setText("--")

        self.lblRet12.setText("--")
        self.lblCagr5.setText("--")
        self.lblMaxDrawdown.setText("--")

        self.lblCapm.setText("--")
        self.lblAlpha.setText("--")
        self.lblTreynor.setText("--")

        # Aba geral
        self.lblGestao.setText(_safe_str(gestao))
        self.lblPatrimonio.setText(_fmt_brl(patrimonio, decimals=2))
        self.lblCotistas.setText(_fmt_float(cotistas, decimals=0))
        self.lblNumCotas.setText(_fmt_float(n_cotas, decimals=0))
        self.lblPercCaixa.setText(_fmt_pct(perc_caixa))
        self.lblLiqDiaria.setText(_fmt_brl(liq_diaria, decimals=2))

        self.lblSortino.setText("--")
        self.lblCalmar.setText("--")
        self.lblInformationRatio.setText("--")
        self.lblTrackingError.setText("--")
        self.lblJensenAlpha.setText("--")

        self.lblRiskFree.setText("--")
        self.lblPremioMercado.setText("--")
        self.lblBetaCapm.setText("--")
        self.lblCapmCalc.setText("--")
        self.lblRetornoRealizado.setText("--")

        self.lblAlphaCapm.setText("--")
        self.lblTreynorCapm.setText("--")
        self.lblInfoRatioCapm.setText("--")
        self.lblTrackingCapm.setText("--")
        self.lblJensenCapm.setText("--")

        self.txtObservacoes.setPlainText(
            "Dados básicos carregados a partir dos CSVs.\n"
            "Histórico, dividendos e métricas quantitativas serão preenchidos depois."
        )

    def init_empty_tables(self):
        self.tblRetornoRisco.setVerticalHeaderLabels([
            "Retorno total",
            "CAGR",
            "Volatilidade",
            "Sharpe",
            "Sortino",
            "Max Drawdown",
            "Calmar",
            "Beta",
            "Alpha",
        ])

        self.tblRetornoRisco.setHorizontalHeaderLabels([
            "12m",
            "3 anos",
            "5 anos",
            "10 anos",
            "Desde o início",
            ""
        ])

        for r in range(self.tblRetornoRisco.rowCount()):
            for c in range(self.tblRetornoRisco.columnCount()):
                item = QtWidgets.QTableWidgetItem("--")
                self.tblRetornoRisco.setItem(r, c, item)

    def get_ticker(self) -> str:
        return _safe_str(self.fii_data.get("TICKER"), "").upper().strip()

    def update_market_data(self):
        ticker = self.get_ticker()
        if not ticker:
            QtWidgets.QMessageBox.warning(self, "Ticker inválido", "Não foi possível identificar o ticker.")
            return

        self.btnAtualizarDados.setEnabled(False)
        try:
            df = FiiDownloader.update_history(ticker)
            if df.empty:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Sem dados",
                    f"Não foi possível baixar histórico para {ticker}."
                )
                return

            self.market_df = df
            self.fill_market_tables()
            self.recalculate_metrics()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao atualizar",
                f"Erro ao atualizar dados de {ticker}:\n{e}"
            )
        finally:
            self.btnAtualizarDados.setEnabled(True)

    def recalculate_metrics(self):
        df = getattr(self, "market_df", None)
        if df is None or df.empty:
            return

        tr = FiiMetrics.prepare_total_return_df(df)
        if tr.empty:
            return

        self.lblDataRef.setText(
            tr["Date"].max().strftime("%d/%m/%Y")
        )

        self.fill_window_metrics(tr)

    def fill_window_metrics(self, tr: pd.DataFrame):
        windows = [
            ("12m", FiiMetrics.window_slice(tr, months=12)),
            ("3 anos", FiiMetrics.window_slice(tr, years=3)),
            ("5 anos", FiiMetrics.window_slice(tr, years=5)),
            ("10 anos", FiiMetrics.window_slice(tr, years=10)),
            ("Desde o início", tr.copy()),
        ]

        row_map = {
            "Retorno total": 0,
            "CAGR": 1,
            "Volatilidade": 2,
            "Sharpe": 3,
            "Sortino": 4,
            "Max Drawdown": 5,
            "Calmar": 6,
            "Beta": 7,
            "Alpha": 8,
            "SELIC média": 9,
        }

        for col_idx, (_, wdf) in enumerate(windows):
            total_ret = FiiMetrics.total_return(wdf)
            cagr = FiiMetrics.cagr(wdf)
            vol = FiiMetrics.volatility_annualized(wdf)
            rf_annual = FiiMetrics.avg_selic_for_window(wdf)
            sharpe = FiiMetrics.sharpe(wdf, rf_annual=rf_annual)
            mdd = FiiMetrics.max_drawdown(wdf)

            self._set_metric_item(row_map["Retorno total"], col_idx, self._fmt_metric_pct(total_ret))
            self._set_metric_item(row_map["CAGR"], col_idx, self._fmt_metric_pct(cagr))
            self._set_metric_item(row_map["Volatilidade"], col_idx, self._fmt_metric_pct(vol))
            self._set_metric_item(row_map["Sharpe"], col_idx, self._fmt_metric_num(sharpe))
            self._set_metric_item(row_map["Sortino"], col_idx, "--")
            self._set_metric_item(row_map["Max Drawdown"], col_idx, self._fmt_metric_pct(mdd))
            self._set_metric_item(row_map["Calmar"], col_idx, "--")
            self._set_metric_item(row_map["Beta"], col_idx, "--")
            self._set_metric_item(row_map["Alpha"], col_idx, "--")

        # cards principais
        df12 = windows[0][1]
        df5 = windows[2][1]

        self.lblRet12.setText(self._fmt_metric_pct(FiiMetrics.total_return(df12)))
        self.lblCagr5.setText(self._fmt_metric_pct(FiiMetrics.cagr(df5)))
        self.lblVol12.setText(self._fmt_metric_pct(FiiMetrics.volatility_annualized(df12)))
        rf12 = FiiMetrics.average_rf_annual_for_window(df12, self.selic_df)
        self.lblSharpe12.setText(self._fmt_metric_num(FiiMetrics.sharpe(df12, rf_annual=rf12)))
        self.lblMaxDrawdown.setText(self._fmt_metric_pct(FiiMetrics.max_drawdown(df12)))

    def fill_market_tables(self):
        df = getattr(self, "market_df", None)
        if df is None or df.empty:
            return

        # tabela de dividendos
        div_df = df.copy()
        div_df["Date"] = pd.to_datetime(div_df["Date"], errors="coerce")
        div_df = div_df.dropna(subset=["Date"])

        if "Dividends" in div_df.columns:
            div_df = div_df[div_df["Dividends"].fillna(0) != 0].copy()
            div_df = div_df[["Date", "Dividends"]].sort_values("Date", ascending=False)
        else:
            div_df = pd.DataFrame(columns=["Date", "Dividends"])

        div_model = SimplePandasModel(div_df)
        self.tableDividendos.setModel(div_model)
        self._div_model = div_model

        # tabela de preços
        price_cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]
        price_df = df[price_cols].copy().sort_values("Date", ascending=False)

        price_model = SimplePandasModel(price_df)
        self.tablePrecos.setModel(price_model)
        self._price_model = price_model

    def load_selic_cache(self) -> pd.DataFrame:
        path = Path(self.base_path) / "data" / "cache" / "macro" / "selic.parquet"

        if not path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_parquet(path)
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()

            df["selic_annual"] = pd.to_numeric(df["selic_annual"], errors="coerce")
            df = df.dropna(subset=["selic_annual"])

            # se estiver em percentual, descomente:
            # df["selic_annual"] = df["selic_annual"] / 100.0

            return df
        except Exception:
            return pd.DataFrame()

    def _set_metric_item(self, row, col, text):
        item = QtWidgets.QTableWidgetItem(text)
        self.tblRetornoRisco.setItem(row, col, item)

    def _fmt_metric_pct(self, value):
        if value is None:
            return "--"
        return _fmt_pct(value * 100.0)

    def _fmt_metric_num(self, value):
        if value is None:
            return "--"
        return _fmt_float(value, decimals=2)
