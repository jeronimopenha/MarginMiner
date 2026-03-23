import pandas as pd
from PyQt6 import QtCore


class SimplePandasModel(QtCore.QAbstractTableModel):
    def __init__(self, df=None):
        super().__init__()
        self._df = df.copy() if df is not None else pd.DataFrame()

    def rowCount(self, parent=None):
        return 0 if parent and parent.isValid() else len(self._df)

    def columnCount(self, parent=None):
        return 0 if parent and parent.isValid() else len(self._df.columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            value = self._df.iat[index.row(), index.column()]

            if pd.isna(value):
                return ""

            if hasattr(value, "strftime"):
                try:
                    return value.strftime("%d/%m/%Y")
                except Exception:
                    pass

            if isinstance(value, float):
                txt = f"{value:,.2f}"
                return txt.replace(",", "X").replace(".", ",").replace("X", ".")

            return str(value)

        return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            try:
                return str(self._df.columns[section])
            except Exception:
                return None

        return str(section + 1)