from PyQt5.QtWidgets import (QDialog, QMessageBox, QVBoxLayout, QHBoxLayout, 
                              QTableWidget, QTableWidgetItem, QPushButton, 
                              QLabel, QHeaderView, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal
from views.pages.welcome_dialog_ui import Ui_WelcomeDialog
from models.db_manager import DatabaseManager



class RecentCaseDialog(QDialog):
    """Hộp thoại mở Case gần đây nội tuyến"""

    def __init__(self, recent_cases, parent=None):
        super().__init__(parent)
        self.recent_cases = recent_cases
        self.selected_case = None

        self.setWindowTitle("Mở Case Gần Đây")
        self.setFixedSize(600, 400)
        self.setup_ui()
        self.setup_connections()
        self.load_recent_cases()

    def setup_ui(self):
        """Thiết lập giao diện người dùng nội tuyến"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Tiêu đề
        header = QLabel("Recent Cases")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #2d3748;")
        layout.addWidget(header)

        # Bảng
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Case Name", "Path"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Cấu hình tiêu đề bảng
        header_view = self.table.horizontalHeader()
        if header_view:
            header_view.setStretchLastSection(True)

        layout.addWidget(self.table)

        # Nút bấm
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.open_btn = QPushButton("Open")
        self.cancel_btn = QPushButton("Cancel")

        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # Phong cách
        self.setStyleSheet(
            """
            QDialog { background-color: #f8f9fa; }
            QTableWidget {
                background-color: white;
                border: 1px solid #e2e8f0;
                selection-background-color: #3182ce;
            }
            QPushButton {
                background-color: #4299e1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #3182ce; }
            QPushButton#cancel_btn {
                background-color: #e2e8f0;
                color: #4a5568;
            }
            /* Nút hủy */
        """)
    

    def setup_connections(self):
        """Thiết lập các kết nối"""
        self.open_btn.clicked.connect(self.open_selected_case)
        self.cancel_btn.clicked.connect(self.reject)
        self.table.itemDoubleClicked.connect(self.open_selected_case)
    
    def load_recent_cases(self):
        """Tải các case vào bảng"""
        self.table.setRowCount(len(self.recent_cases))
        
        for row, case in enumerate(self.recent_cases):
            # Tên case
            name_item = QTableWidgetItem(case.get('title', f"Case {case.get('case_id')}"))
            name_item.setData(Qt.ItemDataRole.UserRole, case.get('case_id'))
            self.table.setItem(row, 0, name_item)
            
            # Đường dẫn
            path_item = QTableWidgetItem(case.get('archive_path', 'N/A'))
            self.table.setItem(row, 1, path_item)
        
        if self.recent_cases:
            self.table.selectRow(0)
    

    def open_selected_case(self):
        """Mở case đã chọn"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            name_item = self.table.item(current_row, 0)
            if name_item:
                case_id = name_item.data(Qt.ItemDataRole.UserRole)
                self.selected_case = {

                    "case_id": case_id,
                    "case_data": self.recent_cases[current_row],
                }
                self.accept()

    def get_selected_case(self):
        """Lấy case đã chọn"""
        return self.selected_case


class WelcomeDialog(QDialog):
    """Welcome dialog với 3 lựa chọn chính"""

    # Các tín hiệu cho các hành động khác nhau
    new_case_requested = pyqtSignal()
    open_recent_requested = pyqtSignal()
    case_management_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_WelcomeDialog()
        self.ui.setupUi(self)


        # Thiết lập thuộc tính hộp thoại
        self.setModal(True)

        # Lưu trữ các case gần đây
        self.recent_cases = []

        # Tải các case gần đây
        self.load_recent_cases()

        # Kết nối signals
        self.ui.newCaseBtn.clicked.connect(self.handle_new_case)
        self.ui.openRecentBtn.clicked.connect(self.handle_open_recent)
        self.ui.openCaseBtn.clicked.connect(self.handle_case_management)
        self.ui.closeBtn.clicked.connect(self.reject)
                           
    def load_recent_cases(self):
        """Tải các case gần đây từ cơ sở dữ liệu"""
        try:
            db_instance = DatabaseManager()
            db_instance.connect()
            all_cases = db_instance.get_cases()


            # Lấy 5 case gần đây nhất
            self.recent_cases = sorted(
                all_cases, key=lambda x: x.get("created_at", ""), reverse=True
            )[:10]

            # Bật/tắt nút dựa trên tính khả dụng của case gần đây
            if not self.recent_cases:
                self.ui.openRecentBtn.setEnabled(False)

        except Exception as e:
            print(f"Lỗi tải case gần đây: {e}")
            self.ui.openRecentBtn.setEnabled(False)

    def handle_new_case(self):
        """Xử lý tạo case mới"""
        self.accept()
        self.new_case_requested.emit()
                           
    def handle_open_recent(self):
        """Xử lý mở case gần đây"""
        if not self.recent_cases:
            QMessageBox.information(
                self,
                "Thông báo",
                "Chưa có case nào được tạo.\nVui lòng tạo case mới hoặc quản lý case.",
            )
            return


        # Hiển thị hộp thoại mở case gần đây (nội tuyến)
        recent_dialog = self.create_recent_case_dialog()
        if recent_dialog.exec_() == QDialog.Accepted:
            selected_case = recent_dialog.get_selected_case()
            if selected_case:
                # Lưu trữ case đã chọn để cửa sổ chính truy cập

                self.selected_case_id = selected_case["case_id"]
                self.selected_case_data = selected_case["case_data"]

                # Đóng hộp thoại chào mừng và phát tín hiệu
                self.accept()
                self.open_recent_requested.emit()

    def create_recent_case_dialog(self):
        """Tạo hộp thoại mở case gần đây nội tuyến"""
        dialog = RecentCaseDialog(self.recent_cases, self)
        return dialog

    def handle_case_management(self):
        """Xử lý quản lý case"""
        self.accept()
        self.case_management_requested.emit()


    def get_selected_case_id(self):
        """Lấy ID case đã chọn để mở case gần đây"""
        return getattr(self, "selected_case_id", None)

    def get_selected_case_data(self):
        """Lấy dữ liệu case đã chọn để mở case gần đây"""
        return getattr(self, "selected_case_data", None)