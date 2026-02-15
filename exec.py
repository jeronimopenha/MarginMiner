import sys
from typing import List

import pandas as pd

from PyQt6 import QtCore, QtGui, QtWidgets
from src.ui.frmFiiScreen import Ui_Frame
from src.util import Util


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
            " CAGR VAL 3 A",
            "PATRIMONIO",
            "N COTISTAS",
            "GESTAO",
            "N COTAS"
        ]
        self.df_all = None

        self.setupUi(self)  # MUITO IMPORTANTE

        self.read_data()
        self.update_cmb_segmentos()
        self.update_cmb_papel()
        # conectar eventos
        # self.btnExecute.clicked.connect(self.read_csv)

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


if __name__ == "__main__":

    if __name__ == "__main__":
        app = QtWidgets.QApplication(sys.argv)

        window = FiiView()
        window.show()

        sys.exit(app.exec())
