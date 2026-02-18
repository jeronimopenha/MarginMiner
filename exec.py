import sys
from src.ui.fii_view import FiiView

from PyQt6 import QtWidgets

if __name__ == "__main__":

    if __name__ == "__main__":
        app = QtWidgets.QApplication(sys.argv)

        window = FiiView()
        window.show()

        sys.exit(app.exec())
