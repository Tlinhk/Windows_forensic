from PyQt5.QtWidgets import QWidget, QHeaderView, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt
from database.db_manager import db

from ui.pages.case_management_ui import Ui_Form

class Case(QWidget):
    def __init__(self):
        super(Case, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Cấu hình table để headers trải dài hết bảng
        #self.setup_table()
       
      
    '''    
    def setup_table(self):
        table = self.ui.table_case
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)  # Tất cả cột sẽ tự động chia đều
        
        table.verticalHeader().setDefaultSectionSize(40)
        table.verticalHeader().setVisible(False)
        # Cho phép chọn cả dòng
        table.setSelectionBehavior(table.SelectRows)
        # Chỉ chọn một dòng tại một thời điểm
        table.setSelectionMode(table.SingleSelection)
     '''   
