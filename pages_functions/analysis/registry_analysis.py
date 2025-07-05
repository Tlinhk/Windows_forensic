from PyQt5.QtWidgets import QWidget

from ui.pages.analysis_ui.registry_analysis_ui import Ui_Form

class RegistryAnalysis(QWidget):
    def __init__(self):
        super(RegistryAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)