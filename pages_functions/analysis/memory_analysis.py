from PyQt5.QtWidgets import QWidget

from ui.pages.analysis_ui.memory_analysis_ui import Ui_Form

class MemoryAnalysis(QWidget):
    def __init__(self):
        super(MemoryAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)