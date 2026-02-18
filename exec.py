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
        self.update_cmb_segmentos()
        self.update_cmb_papel()
        self.cmbSegmento.currentTextChanged.connect(self.update_cmb_papel)
        self.tableView.setModel(self.model)
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
        self.model.set_df(df)


class PandasTableModel(QtCore.QAbstractTableModel):
    def __init__(self, df, headers=None, formats=None):
        super().__init__()
        self._df = df
        self._headers = headers
        # formats pode ser por índice (int) OU por header (str)
        # Ex: {0: "text", 1: "brl", "DY": "pct"}
        self._formats = formats or {}

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._df.columns)

    def _fmt_key(self, col: int):
        # prioridade: formato por índice; senão por header exibido; senão por nome real do df
        if col in self._formats:
            return self._formats[col]
        if self._headers and col < len(self._headers) and self._headers[col] in self._formats:
            return self._formats[self._headers[col]]
        name = str(self._df.columns[col])
        return self._formats.get(name, None)

    def _is_number(self, v):
        return isinstance(v, (int, float)) and v == v  # v==v evita NaN

    def _format_value(self, col: int, v):
        if v is None or (isinstance(v, float) and (v != v)):  # None ou NaN
            return ""

        fmt = self._fmt_key(col)

        # Texto / ticker
        if fmt in (None, "text"):
            return str(v)

        # Percentual (assumindo 12.34 -> "12,34%")
        if fmt == "pct":
            if self._is_number(v):
                return f"{v:.2f}%".replace(".", ",")
            return str(v)

        # Moeda BRL (assumindo 12.34 -> "R$ 12,34")
        if fmt == "brl":
            if self._is_number(v):
                s = f"{v:,.2f}"
                # troca separadores para pt-BR: 1,234.56 -> 1.234,56
                s = s.replace(",", "X").replace(".", ",").replace("X", ".")
                return f"R$ {s}"
            return str(v)

        # Inteiro com milhar (1_234_567 -> "1.234.567")
        if fmt == "int":
            try:
                iv = int(v)
                s = f"{iv:,}".replace(",", ".")
                return s
            except Exception:
                return str(v)

        # Float genérico com N casas (ex: ("float", 2))
        if isinstance(fmt, tuple) and fmt[0] == "float":
            n = int(fmt[1])
            if self._is_number(v):
                s = f"{float(v):,.{n}f}"
                s = s.replace(",", "X").replace(".", ",").replace("X", ".")
                return s
            return str(v)

        return str(v)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        r, c = index.row(), index.column()
        v = self._df.iat[r, c]

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self._format_value(c, v)

        # alinhamento
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            fmt = self._fmt_key(c)
            if fmt in ("brl", "pct", "int") or (isinstance(fmt, tuple) and fmt[0] == "float"):
                return int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight)
            return int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)
        return None


    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            if self._headers and section < len(self._headers):
                return self._headers[section]
            return str(self._df.columns[section])

        return str(section + 1)

    def set_df(self, df):
        self.beginResetModel()
        self._df = df
        self.endResetModel()



if __name__ == "__main__":

    if __name__ == "__main__":
        app = QtWidgets.QApplication(sys.argv)

        window = FiiView()
        window.show()

        sys.exit(app.exec())
