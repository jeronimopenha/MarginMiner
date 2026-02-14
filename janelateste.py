import sys
from dataclasses import dataclass
from typing import List, Any

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QMessageBox
)


# =========================
# Model / Config
# =========================
@dataclass
class AppConfig:
    risk_free_rate_annual_default: float = 0.13  # 13% a.a.
    period_default: str = "10y"


PERIOD_OPTIONS = [
    ("12m", "12m"),
    ("3 anos", "3y"),
    ("5 anos", "5y"),
    ("10 anos", "10y"),
]


# =========================
# Services (placeholder)
# =========================
class MetricsService:
    """
    Aqui você liga depois no yfinance e nos seus cálculos:
    - baixar preços
    - calcular retornos
    - volatilidade, sharpe etc.
    """
    def compute_metrics_demo(self, risk_free_annual: float, period: str) -> pd.DataFrame:
        # DEMO: cria uma tabelinha fake só para validar GUI e fluxo
        data = [
            {"Ativo": "IVVB11", "Retorno a.a. (est.)": 0.18, "Vol a.a.": 0.22, "Sharpe": (0.18 - risk_free_annual) / 0.22},
            {"Ativo": "BBAS3",  "Retorno a.a. (est.)": 0.16, "Vol a.a.": 0.28, "Sharpe": (0.16 - risk_free_annual) / 0.28},
            {"Ativo": "HGLG11", "Retorno a.a. (est.)": 0.12, "Vol a.a.": 0.10, "Sharpe": (0.12 - risk_free_annual) / 0.10},
        ]
        df = pd.DataFrame(data)

        # Só pra mostrar que o período “passa” no pipeline
        df.insert(1, "Período", period)

        return df


# =========================
# UI Helpers
# =========================
def _safe_float(text: str) -> float:
    """
    Aceita '0.13', '13', '13%' e também vírgula '13,5'.
    Interpretação:
      - Se tiver %, remove e divide por 100
      - Se for >= 1.0 (ex: 13), entende como 13% => 0.13
    """
    t = text.strip().lower().replace(" ", "")
    t = t.replace(",", ".")
    if not t:
        raise ValueError("vazio")

    is_percent = t.endswith("%")
    if is_percent:
        t = t[:-1]

    val = float(t)

    if is_percent:
        return val / 100.0

    # Heurística: 13 => 13% ; 0.13 => 13%
    if val >= 1.0:
        return val / 100.0

    return val


def _fmt_percent(x: Any, digits: int = 2) -> str:
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except Exception:
        return str(x)


def _fmt_float(x: Any, digits: int = 3) -> str:
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)


# =========================
# Main Window
# =========================
class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, service: MetricsService):
        super().__init__()
        self.config = config
        self.service = service

        self.setWindowTitle("marginMiner — Métricas")
        self.resize(980, 560)

        self._build_menu()
        self._build_ui()

        # Estado inicial
        self.selci_edit.setText(str(int(self.config.risk_free_rate_annual_default * 100)))  # mostra "13"
        self._set_period(self.config.period_default)

        # Primeira carga
        self.recalculate()

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Arquivo")
        act_exit = QAction("Sair", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        help_menu = menubar.addMenu("Ajuda")
        act_about = QAction("Sobre", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        # --- Controls (top)
        controls_row = QHBoxLayout()
        root.addLayout(controls_row)

        form = QFormLayout()
        controls_row.addLayout(form, stretch=1)

        self.selci_edit = QLineEdit()
        self.selci_edit.setPlaceholderText("Ex: 13 ou 0.13 ou 13%")
        form.addRow(QLabel("Taxa livre de risco (SELIC, a.a.)"), self.selci_edit)

        self.period_combo = QComboBox()
        for label, value in PERIOD_OPTIONS:
            self.period_combo.addItem(label, userData=value)
        form.addRow(QLabel("Período (histórico)"), self.period_combo)

        self.btn_recalc = QPushButton("Recalcular")
        self.btn_recalc.clicked.connect(self.recalculate)
        controls_row.addWidget(self.btn_recalc)

        # --- Table (middle)
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, stretch=1)

        # --- Status bar
        self.statusBar().showMessage("Pronto.")

    def _about(self):
        QMessageBox.information(
            self,
            "Sobre",
            "marginMiner (protótipo)\nGUI em PySide6/Qt.\n\nPróximo passo: integrar yfinance e suas métricas."
        )

    def _set_period(self, period_value: str):
        for i in range(self.period_combo.count()):
            if self.period_combo.itemData(i) == period_value:
                self.period_combo.setCurrentIndex(i)
                return

    def _read_inputs(self) -> tuple[float, str]:
        rf = _safe_float(self.selci_edit.text())
        period = self.period_combo.currentData()
        return rf, period

    def recalculate(self):
        try:
            rf, period = self._read_inputs()
        except Exception:
            QMessageBox.warning(self, "Entrada inválida", "Informe uma taxa válida (ex: 13, 13% ou 0.13).")
            return

        self.statusBar().showMessage("Calculando…")
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            df = self.service.compute_metrics_demo(rf, period)
            self._fill_table(df)
            self.statusBar().showMessage(f"OK — taxa livre de risco: {_fmt_percent(rf)} — período: {period}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao recalcular:\n\n{e}")
            self.statusBar().showMessage("Erro.")
        finally:
            QApplication.restoreOverrideCursor()

    def _fill_table(self, df: pd.DataFrame):
        # Define colunas
        cols: List[str] = list(df.columns)
        self.table.clear()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(df))

        # Preenche
        for r in range(len(df)):
            for c, col in enumerate(cols):
                val = df.iloc[r, c]

                # Formata algumas colunas comuns (você ajusta depois)
                if "Retorno" in col or "Vol" in col:
                    text = _fmt_percent(val)
                elif "Sharpe" in col:
                    text = _fmt_float(val, 3)
                else:
                    text = str(val)

                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignLeft if c == 0 else Qt.AlignRight))
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()


def main():
    app = QApplication(sys.argv)

    config = AppConfig()
    service = MetricsService()

    w = MainWindow(config, service)
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()