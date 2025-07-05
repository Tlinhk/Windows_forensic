from PyQt5.QtWidgets import QWidget

from ui.pages.analysis_ui.file_analysis_ui import Ui_Form

class FileAnalysis(QWidget):
    def __init__(self):
        super(FileAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)