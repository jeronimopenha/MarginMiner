import pandas as pd

from PyQt6 import QtCore, QtGui, QtWidgets

from src.common.Parse import Parse

from src.ui.frmFiiScreen import Ui_Frame
from src.ui.pandas_table_model import PandasTableModel
from src.util import Util


def apply_min_max(df: pd.DataFrame, col, vmin=None, vmax=None):
    if vmin is not None:
        df = df[df[col] >= vmin]
    if vmax is not None:
        df = df[df[col] <= vmax]
    return df


class FiiView(QtWidgets.QFrame, Ui_Frame):
    def __init__(self):
        super().__init__()

        self.headers = [
            "TICKER",
            "PRECO",
            "DIV",
            "DY",
            "VPC",
            "P/VP",
            "LIQ. DIARIA",
            "PERC. CAIXA",
            "CAGR DIV. 3 A",
            "CAGR VAL 3 A",
            "PATRIMONIO",
            "N COTISTAS",
            "GESTAO",
            "N COTAS",
            "SEG"
        ]

        self.formats = {
            "TICKER": "text",
            "PRECO": "brl",
            "DIV": "brl",
            "DY": "pct",
            "VPC": "brl",
            "P/VP": ("float", 2),
            "LIQ. DIARIA": "brl",  # ou ("float", 0) se você quiser sem R$
            "PERC. CAIXA": "pct",
            "CAGR DIV. 3 A": "pct",
            "CAGR VAL 3 A": "pct",
            "PATRIMONIO": "brl",
            "N COTISTAS": "int",
            "GESTAO": "text",
            "N COTAS": "int",
            "SEG": "text",
        }
        self.df_all = None

        self.setupUi(self)  # MUITO IMPORTANTE

        self.read_data()

        self.model = PandasTableModel(self.df_all, headers=self.headers, formats=self.formats)
        self.tableView.setModel(self.model)

        self.ancTijolo()

        self.update_cmb_segmentos()
        self.update_cmb_papel()

        self.cmbSegmento.currentTextChanged.connect(self.update_cmb_papel)

        self.btnUpdate.clicked.connect(self.update_data)
        self.btnClear.clicked.connect(self.clear_input)
        self.btnCrescPapel.clicked.connect(self.crescPapel)
        self.btnAncPapel.clicked.connect(self.ancPapel)
        self.btnCrescTijolo.clicked.connect(self.crescTijolo)
        self.btnAncTijolo.clicked.connect(self.ancTijolo)

    def read_data(self):
        rootPath = Util.get_project_root()
        files = Util.get_files_list_by_extension(
            rootPath + "/data/csv/fii/", ".csv"
        )

        dfs = []

        for file_path, file_name in files:
            df = pd.read_csv(
                file_path,
                sep=";",
                decimal=",",
                thousands="."
            )

            df.columns = df.columns.str.strip()

            segmento = file_name[:-4]
            df["SEGMENTO"] = segmento

            dfs.append(df)

        self.df_all = pd.concat(dfs, ignore_index=True)

    def update_cmb_segmentos(self):
        self.cmbSegmento.clear()
        self.cmbSegmento.addItem("Todos", None)

        segmentos = sorted(self.df_all["SEGMENTO"].unique())

        for seg in segmentos:
            self.cmbSegmento.addItem(seg, seg)

    def update_cmb_papel(self):
        self.cmbPapel.clear()
        self.cmbPapel.addItem("Todos", None)

        seg = self.cmbSegmento.currentData()

        if seg is None:
            df = self.df_all
        else:
            df = self.df_all[self.df_all["SEGMENTO"] == seg]

        tickers = sorted(df["TICKER"].unique())

        for t in tickers:
            self.cmbPapel.addItem(t, t)
        self.update_data()

    def update_data(self):
        seg = self.cmbSegmento.currentData()
        df = self.df_all
        if seg is not None:
            df = self.df_all[self.df_all["SEGMENTO"] == seg]

        pvp_max = Parse.float(self.txtPvpMax.text())
        pvp_min = Parse.float(self.txtPvpMin.text())
        df = apply_min_max(df, "P/VP", pvp_min, pvp_max)

        dy_min = Parse.percent(self.txtDyMin.text())
        dy_max = Parse.percent(self.txtDyMax.text())
        df = apply_min_max(df, "DY", dy_min, dy_max)

        pcx_min = Parse.percent(self.txtCaixaMin.text())
        pcx_max = Parse.percent(self.txtCaixaMax.text())
        df = apply_min_max(df, "PERC. CAIXA", pcx_min, pcx_max)

        cot_max = Parse.float(self.txtCotMax.text())
        cot_min = Parse.float(self.txtCotMin.text())
        df = apply_min_max(df, "PRECO", cot_min, cot_max)

        liq_max = Parse.float(self.txtLiqMax.text())
        liq_min = Parse.float(self.txtLiqMin.text())
        df = apply_min_max(df, "LIQ. DIARIA", liq_min, liq_max)

        tickers = sorted(df["TICKER"].unique())

        for t in tickers:
            self.cmbPapel.addItem(t, t)
        self.model.set_df(df)

    def clear_input(self):
        for le in self.findChildren(QtWidgets.QLineEdit):
            le.clear()
        self.update_data()

    def ancPapel(self):
        self.txtPvpMax.setText("100")
        self.txtPvpMin.setText("090")
        self.txtDyMin.setText("0008")
        self.update_data()

    def ancTijolo(self):
        self.txtPvpMax.setText("105")
        self.txtPvpMin.setText("094")
        self.txtDyMin.setText("0008")
        self.update_data()

    def crescPapel(self):
        self.txtPvpMax.setText("100")
        self.txtPvpMin.setText("085")
        self.txtDyMin.setText("0010")
        self.update_data()

    def crescTijolo(self):
        self.txtPvpMax.setText("105")
        self.txtPvpMin.setText("080")
        self.txtDyMin.setText("0010")
        self.update_data()
