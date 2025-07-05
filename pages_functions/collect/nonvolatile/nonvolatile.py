from PyQt5.QtWidgets import QWidget

from ui.pages.collect_ui.collect_nonvolatile_ui import Ui_Form

class Nonvolatile(QWidget):
    def __init__(self):
        super(Nonvolatile, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
