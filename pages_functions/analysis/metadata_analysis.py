from PyQt5.QtWidgets import QWidget

from ui.pages.analysis_ui.metadata_analysis_ui import Ui_Form

class MetadataAnalysis(QWidget):
    def __init__(self):
        super(MetadataAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)