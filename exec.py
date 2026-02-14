import sys

from PyQt6 import QtCore, QtGui, QtWidgets
from src.ui.frmFiiScreen import Ui_Frame
from src.util import Util


class FiiView (QtWidgets.QFrame, Ui_Frame):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # MUITO IMPORTANTE

        # conectar eventos
        self.btnExecute.clicked.connect(self.read_csv)

    def read_csv(self):
        rootPath = Util.get_project_root()
        files = Util.get_files_list_by_extension(
            rootPath + "/data/csv/fii/", ".csv"
        )
        print(files)


if __name__ == "__main__":

    if __name__ == "__main__":
        app = QtWidgets.QApplication(sys.argv)

        window = FiiView()
        window.show()

        sys.exit(app.exec())