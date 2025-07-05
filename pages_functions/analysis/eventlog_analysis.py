from PyQt5.QtWidgets import QWidget

from ui.pages.analysis_ui.eventlog_analysis_ui import Ui_Form

class EventlogAnalysis(QWidget):
    def __init__(self):
        super(EventlogAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)