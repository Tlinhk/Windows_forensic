from PyQt5.QtWidgets import QWidget

from ui.pages.collect_ui.collect_volatile_ui import Ui_Form

class Volatile(QWidget):
    def __init__(self):
        super(Volatile, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
