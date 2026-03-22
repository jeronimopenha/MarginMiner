import pandas as pd

from PyQt6 import QtCore, QtWidgets

from src.common.Parse import Parse
from src.ui.frmFiiScreen import Ui_Frame
from src.ui.fii_detail_view import FiiDetailView
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
            "LIQ_DIARIA",
            "PERC_CAIXA",
            "CAGR DIV. 3 A",
            "CAGR VAL 3 A",
            "PATRIMONIO",
            "N COTISTAS",
            "GESTAO",
            "N COTAS",
            "SEG",
            "RDY",
            "RPVP",
            "RANK"
        ]

        self.formats = {
            "TICKER": "text",
            "PRECO": "brl",
            "DIV": "brl",
            "DY": "pct",
            "VPC": "brl",
            "P/VP": ("float", 2),
            "LIQ_DIARIA": "brl",
            "PERC_CAIXA": "pct",
            "CAGR DIV. 3 A": "pct",
            "CAGR VAL 3 A": "pct",
            "PATRIMONIO": "brl",
            "N COTISTAS": "int",
            "GESTAO": "text",
            "N COTAS": "int",
            "SEG": "text",
            "RDY": "int",
            "RPVP": "int",
            "RANK": "int",
        }

        self.df_all = pd.DataFrame()
        self._updating_papeis = False

        self.setupUi(self)

        self.read_data()

        self.model = PandasTableModel(
            self.df_all,
            headers=self.headers,
            formats=self.formats
        )
        self.tableView.setModel(self.model)
        self.tableView.horizontalHeader().setSectionsMovable(True)

        self.tableView.setColumnHidden(4, True)
        self.tableView.setColumnHidden(8, True)
        self.tableView.setColumnHidden(9, True)
        self.tableView.setColumnHidden(11, True)
        self.tableView.setColumnHidden(12, True)
        self.tableView.setColumnHidden(15, True)
        self.tableView.setColumnHidden(16, True)

        self.tableView.setAlternatingRowColors(True)

        self.tableView.doubleClicked.connect(self.open_detail_from_index)

        self.ancTijolo()

        self.update_cmb_segmentos()
        self.update_lst_papeis()

        self.cmbSegmento.currentIndexChanged.connect(self.on_segmento_changed)

        self.btnUpdate.clicked.connect(self.update_data)
        self.btnClear.clicked.connect(self.clear_input)
        self.btnCrescPapel.clicked.connect(self.crescPapel)
        self.btnAncPapel.clicked.connect(self.ancPapel)
        self.btnCrescTijolo.clicked.connect(self.crescTijolo)
        self.btnAncTijolo.clicked.connect(self.ancTijolo)

        self.chkSomenteSelecionados.toggled.connect(self.update_data)
        self.btnMarcarTodos.clicked.connect(self.marcar_todos_papeis)
        self.btnLimparSelecao.clicked.connect(self.limpar_selecao_papeis)
        self.lstPapeis.itemChanged.connect(self.on_lst_papeis_changed)

        self.update_data()

    def read_data(self):
        data_dir = Util.get_data_dir()
        files = Util.get_files_list_by_extension(str(data_dir), ".csv")

        if not files:
            QtWidgets.QMessageBox.warning(
                self,
                "Sem CSVs",
                f"Não encontrei arquivos .csv em:\n{data_dir}\n\n"
                "Crie/coloque os CSVs nessa pasta e clique em Atualizar."
            )
            self.df_all = pd.DataFrame()
            return

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

        df_all = pd.concat(dfs, ignore_index=True)

        # Normalizações
        if "DY" in df_all.columns:
            df_all["DY"] = pd.to_numeric(df_all["DY"], errors="coerce")

        if "P/VP" in df_all.columns:
            df_all["P/VP"] = pd.to_numeric(df_all["P/VP"], errors="coerce")

        # Ranking
        df_all["RDY"] = df_all["DY"].rank(
            ascending=False,
            method="min",
            na_option="bottom"
        )

        df_all["RPVP"] = df_all["P/VP"].rank(
            ascending=True,
            method="min",
            na_option="bottom"
        )

        df_all["RPVP"] = df_all["RPVP"].round().astype("Int64")
        df_all["RDY"] = df_all["RDY"].round().astype("Int64")
        df_all["RANK"] = (df_all["RPVP"] + df_all["RDY"]).astype("Int64")

        self.df_all = df_all

    def update_cmb_segmentos(self):
        self.cmbSegmento.clear()
        self.cmbSegmento.addItem("Todos", None)

        if self.df_all.empty:
            return

        segmentos = sorted(self.df_all["SEGMENTO"].dropna().unique())

        for seg in segmentos:
            self.cmbSegmento.addItem(seg, seg)

    def on_segmento_changed(self):
        self.update_lst_papeis()
        self.update_data()

    def get_df_segmento(self):
        seg = self.cmbSegmento.currentData()

        if seg is None:
            return self.df_all.copy()

        return self.df_all[self.df_all["SEGMENTO"] == seg].copy()

    def update_lst_papeis(self):
        self._updating_papeis = True

        selecionados_antes = set(self.get_selected_tickers())

        self.lstPapeis.clear()

        df = self.get_df_segmento()
        if df.empty or "TICKER" not in df.columns:
            self._updating_papeis = False
            return

        tickers = sorted(df["TICKER"].dropna().unique())

        for t in tickers:
            item = QtWidgets.QListWidgetItem(str(t))
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)

            if t in selecionados_antes:
                item.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)

            self.lstPapeis.addItem(item)

        self._updating_papeis = False

    def get_selected_tickers(self):
        selecionados = []

        for i in range(self.lstPapeis.count()):
            item = self.lstPapeis.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                selecionados.append(item.text())

        return selecionados

    def marcar_todos_papeis(self):
        self._updating_papeis = True

        for i in range(self.lstPapeis.count()):
            item = self.lstPapeis.item(i)
            item.setCheckState(QtCore.Qt.CheckState.Checked)

        self._updating_papeis = False
        self.update_data()

    def limpar_selecao_papeis(self):
        self._updating_papeis = True

        for i in range(self.lstPapeis.count()):
            item = self.lstPapeis.item(i)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)

        self._updating_papeis = False
        self.update_data()

    def on_lst_papeis_changed(self, item):
        if self._updating_papeis:
            return

        if self.chkSomenteSelecionados.isChecked():
            self.update_data()

    def update_data(self):
        if self.df_all.empty:
            self.model.set_df(pd.DataFrame(columns=self.headers))
            return

        df = self.get_df_segmento()

        pvp_max = Parse.float(self.txtPvpMax.text())
        pvp_min = Parse.float(self.txtPvpMin.text())
        df = apply_min_max(df, "P/VP", pvp_min, pvp_max)

        dy_min = Parse.percent(self.txtDyMin.text())
        dy_max = Parse.percent(self.txtDyMax.text())
        df = apply_min_max(df, "DY", dy_min, dy_max)

        pcx_min = Parse.percent(self.txtCaixaMin.text())
        pcx_max = Parse.percent(self.txtCaixaMax.text())
        if "PERC.CAIXA" in df.columns:
            df = apply_min_max(df, "PERC.CAIXA", pcx_min, pcx_max)

        cot_max = Parse.float(self.txtCotMax.text())
        cot_min = Parse.float(self.txtCotMin.text())
        df = apply_min_max(df, "PRECO", cot_min, cot_max)

        liq_max = Parse.float(self.txtLiqMax.text())
        liq_min = Parse.float(self.txtLiqMin.text())
        if "LIQUIDEZ MEDIA DIARIA" in df.columns:
            df = apply_min_max(df, "LIQUIDEZ MEDIA DIARIA", liq_min, liq_max)

        # filtra apenas os tickers selecionados, se marcado
        if self.chkSomenteSelecionados.isChecked():
            selecionados = self.get_selected_tickers()
            if selecionados:
                df = df[df["TICKER"].isin(selecionados)]
            else:
                df = df.iloc[0:0]

        self.model.set_df(df)

        if "RANK" in self.headers:
            self.tableView.sortByColumn(
                self.headers.index("RANK"),
                QtCore.Qt.SortOrder.AscendingOrder
            )

    def clear_input(self):
        for le in self.findChildren(QtWidgets.QLineEdit):
            le.clear()

        self.chkSomenteSelecionados.setChecked(False)
        self.limpar_selecao_papeis()
        self.update_data()

    def ancPapel(self):
        self.txtPvpMax.setText("100")
        self.txtPvpMin.setText("090")
        self.txtDyMin.setText("1200")
        self.txtLiqMin.setText("0100000000")
        self.update_data()

    def ancTijolo(self):
        self.txtPvpMax.setText("105")
        self.txtPvpMin.setText("094")
        self.txtDyMin.setText("0900")
        self.txtLiqMin.setText("0100000000")
        self.update_data()

    def crescPapel(self):
        self.txtPvpMax.setText("100")
        self.txtPvpMin.setText("085")
        self.txtDyMin.setText("1300")
        self.txtLiqMin.setText("0080000000")
        self.update_data()

    def crescTijolo(self):
        self.txtPvpMax.setText("105")
        self.txtPvpMin.setText("080")
        self.txtDyMin.setText("1000")
        self.txtLiqMin.setText("0080000000")
        self.update_data()

    def open_detail_from_index(self, index):
        if not index.isValid():
            return

        row = index.row()
        df = self.model._df  # assumindo que seu PandasTableModel guarda o DataFrame atual em _df

        if df is None or df.empty:
            return

        if row < 0 or row >= len(df):
            return

        row_data = df.iloc[row].to_dict()

        # manter referência para não fechar instantaneamente
        self.detail_window = FiiDetailView(row_data, self)
        self.detail_window.show()
