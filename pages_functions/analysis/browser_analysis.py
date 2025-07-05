from PyQt5.QtWidgets import QWidget

from ui.pages.analysis_ui.browser_analysis_ui import Ui_Form

class BrowserAnalysis(QWidget):
    def __init__(self):
        super(BrowserAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)