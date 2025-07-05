from PyQt5.QtWidgets import QWidget

from ui.pages.report_ui.report_ui import Ui_Form

class Report(QWidget):
    def __init__(self):
        super(Report, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)