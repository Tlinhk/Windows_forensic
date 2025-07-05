from PyQt5.QtWidgets import QWidget

from ui.pages.user_management_ui import Ui_Form

class UserManagement(QWidget):
    def __init__(self):
        super(UserManagement, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)