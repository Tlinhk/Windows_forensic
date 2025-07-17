from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal
from ui.pages.welcome_dialog_ui import Ui_WelcomeDialog
from database.db_manager import db


class RecentCaseDialog(QDialog):
    """Inline Recent Case Dialog"""

    def __init__(self, recent_cases, parent=None):
        super().__init__(parent)
        self.recent_cases = recent_cases
        self.selected_case = None

        self.setWindowTitle("Open Recent Case")
        self.setFixedSize(600, 400)
        self.setup_ui()
        self.setup_connections()
        self.load_recent_cases()

    def setup_ui(self):
        """Setup UI inline"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("Recent Cases")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #2d3748;")
        layout.addWidget(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Case Name", "Path"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)

        # Configure table headers
        header_view = self.table.horizontalHeader()
        if header_view:
            header_view.setStretchLastSection(True)

        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.open_btn = QPushButton("Open")
        self.cancel_btn = QPushButton("Cancel")

        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # Style
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
        """
        )

    def setup_connections(self):
        """Setup connections"""
        self.open_btn.clicked.connect(self.open_selected_case)
        self.cancel_btn.clicked.connect(self.reject)
        self.table.itemDoubleClicked.connect(self.open_selected_case)

    def load_recent_cases(self):
        """Load cases into table"""
        self.table.setRowCount(len(self.recent_cases))

        for row, case in enumerate(self.recent_cases):
            # Case Name
            name_item = QTableWidgetItem(
                case.get("title", f"Case {case.get('case_id')}")
            )
            name_item.setData(Qt.ItemDataRole.UserRole, case.get("case_id"))
            self.table.setItem(row, 0, name_item)

            # Path
            path_item = QTableWidgetItem(case.get("archive_path", "N/A"))
            self.table.setItem(row, 1, path_item)

        if self.recent_cases:
            self.table.selectRow(0)

    def open_selected_case(self):
        """Open selected case"""
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
        """Get selected case"""
        return self.selected_case


class WelcomeDialog(QDialog):
    """Welcome dialog với 3 lựa chọn chính"""

    # Signals for different actions
    new_case_requested = pyqtSignal()
    open_recent_requested = pyqtSignal()
    case_management_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_WelcomeDialog()
        self.ui.setupUi(self)

        # Set dialog properties
        self.setModal(True)

        # Store recent cases
        self.recent_cases = []

        # Load recent cases
        self.load_recent_cases()

        # Kết nối signals
        self.ui.newCaseBtn.clicked.connect(self.handle_new_case)
        self.ui.openRecentBtn.clicked.connect(self.handle_open_recent)
        self.ui.openCaseBtn.clicked.connect(self.handle_case_management)
        self.ui.closeBtn.clicked.connect(self.reject)

    def load_recent_cases(self):
        """Load recent cases from database"""
        try:
            all_cases = db.get_cases()

            # Get top 5 most recent cases
            self.recent_cases = sorted(
                all_cases, key=lambda x: x.get("created_at", ""), reverse=True
            )[:10]

            # Enable/disable button based on recent cases availability
            if not self.recent_cases:
                self.ui.openRecentBtn.setEnabled(False)

        except Exception as e:
            print(f"Error loading recent cases: {e}")
            self.ui.openRecentBtn.setEnabled(False)

    def handle_new_case(self):
        """Handle new case creation"""
        self.accept()
        self.new_case_requested.emit()

    def handle_open_recent(self):
        """Handle opening recent case"""
        if not self.recent_cases:
            QMessageBox.information(
                self,
                "Thông báo",
                "Chưa có case nào được tạo.\nVui lòng tạo case mới hoặc quản lý case.",
            )
            return

        # Show Open Recent Case dialog (inline)
        recent_dialog = self.create_recent_case_dialog()
        if recent_dialog.exec_() == QDialog.Accepted:
            selected_case = recent_dialog.get_selected_case()
            if selected_case:
                # Store selected case for main window to access
                self.selected_case_id = selected_case["case_id"]
                self.selected_case_data = selected_case["case_data"]

                # Close welcome dialog and emit signal
                self.accept()
                self.open_recent_requested.emit()

    def create_recent_case_dialog(self):
        """Create inline Open Recent Case dialog"""
        dialog = RecentCaseDialog(self.recent_cases, self)
        return dialog

    def handle_case_management(self):
        """Handle case management"""
        self.accept()
        self.case_management_requested.emit()

    def get_selected_case_id(self):
        """Get selected case ID for recent case opening"""
        return getattr(self, "selected_case_id", None)

    def get_selected_case_data(self):
        """Get selected case data for recent case opening"""
        return getattr(self, "selected_case_data", None)
