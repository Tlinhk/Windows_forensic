from PyQt5.QtWidgets import (
    QWidget,
    QListWidgetItem,
    QHeaderView,
    QMessageBox,
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5 import QtCore

# Import a a-ui file generated from Designer
from ui.pages.analysis_ui.memory_analysis_ui import Ui_MemoryAnalysisWidget
from ui.pages.analysis_ui.memory_analysis_result_widget_ui import (
    Ui_MemoryAnalysisResultWidget,
)


class MockDBManager:
    """A mock database manager to simulate fetching data."""

    def get_memory_evidence_for_case(self, case_id):
        if case_id == 1:
            return [
                {
                    "id": 101,
                    "name": "memory_dump_2024-01-15.raw",
                    "path": "/evidence/case1/memdump.raw",
                    "size": 2048,
                    "format": ".raw",
                },
                {
                    "id": 102,
                    "name": "hiberfil.sys",
                    "path": "/evidence/case1/hiberfil.sys",
                    "size": 4096,
                    "format": "hiberfil",
                },
                {
                    "id": 103,
                    "name": "crash_dump_01.dmp",
                    "path": "/evidence/case1/crash.dmp",
                    "size": 1024,
                    "format": ".dmp",
                },
            ]
        return []


class AnalysisResultTab(QWidget):
    """
    This widget represents a single analysis results tab for a memory file.
    It contains sub-tabs for different analysis views (Overview, Process Tree, etc.).
    """

    def __init__(self, evidence_name, parent=None):
        super().__init__(parent)
        self.ui = Ui_MemoryAnalysisResultWidget()
        self.ui.setupUi(self)
        self.evidence_name = evidence_name
        self.populate_with_mock_data()

    def populate_with_mock_data(self):
        """Populate the UI with placeholder data for demonstration."""
        self.ui.label_stats.setText(
            f"Analysis summary for: <b>{self.evidence_name}</b>"
        )

        # Overview Tab
        overview_model = QStandardItemModel(4, 2)
        overview_model.setHorizontalHeaderLabels(["Property", "Value"])
        overview_model.setItem(0, 0, QStandardItem("OS Profile"))
        overview_model.setItem(0, 1, QStandardItem("Win10x64_19041"))
        overview_model.setItem(1, 0, QStandardItem("Processes"))
        overview_model.setItem(1, 1, QStandardItem("128"))
        overview_model.setItem(2, 0, QStandardItem("Network Connections"))
        overview_model.setItem(2, 1, QStandardItem("32"))
        overview_model.setItem(3, 0, QStandardItem("Malicious Indicators"))
        overview_model.setItem(3, 1, QStandardItem("2"))
        self.ui.table_overview.setModel(overview_model)
        if self.ui.table_overview.horizontalHeader():
            self.ui.table_overview.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch
            )

        # Process Tree Tab
        process_model = QStandardItemModel()
        process_model.setHorizontalHeaderLabels(["Name", "PID", "PPID", "Path"])
        root_item = process_model.invisibleRootItem()
        p1 = [
            QStandardItem("System"),
            QStandardItem("4"),
            QStandardItem("0"),
            QStandardItem("N/A"),
        ]
        root_item.appendRow(p1)
        p1_child = [
            QStandardItem("smss.exe"),
            QStandardItem("456"),
            QStandardItem("4"),
            QStandardItem("C:\\Windows\\System32"),
        ]
        p1[0].appendRow(p1_child)
        root_item.appendRow(
            [
                QStandardItem("explorer.exe"),
                QStandardItem("5012"),
                QStandardItem("4988"),
                QStandardItem("C:\\Windows"),
            ]
        )
        self.ui.treeView_process.setModel(process_model)
        if self.ui.treeView_process.header():
            self.ui.treeView_process.header().setSectionResizeMode(
                QHeaderView.ResizeToContents
            )

        # User Activity Tab
        self.ui.textedit_cmd.setText(
            "--- CMD History ---\nC:\\> ipconfig /all\nC:\\> netstat -an"
        )


class MemoryAnalysisPage(QWidget):
    """The main logic for the Memory Analysis page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MemoryAnalysisWidget()
        self.ui.setupUi(self)

        # Crucial fix: Ensure tab labels are never truncated.
        if self.ui.tabWidget.tabBar():
            self.ui.tabWidget.tabBar().setElideMode(QtCore.Qt.ElideNone)

        self.db_manager = MockDBManager()
        self.current_case_id = None

        self.setup_connections()
        self.load_case_data(1)  # Mock loading for case ID 1
        self.ui.splitter.setSizes([300, 700])

    def setup_connections(self):
        """Connect UI element signals to corresponding slots."""
        self.ui.btnStart.clicked.connect(self.start_analysis)
        self.ui.listWidgetMemoryFiles.itemSelectionChanged.connect(
            self.update_file_info
        )
        self.ui.tabWidget.tabCloseRequested.connect(self.close_tab)

    def load_case_data(self, case_id):
        """Load data for a specific case, including memory evidence files."""
        self.current_case_id = case_id
        self.ui.label_case_info.setText(f"Case: Test Case {case_id}")

        self.ui.listWidgetMemoryFiles.clear()
        evidence_list = self.db_manager.get_memory_evidence_for_case(case_id)
        for evidence in evidence_list:
            item = QListWidgetItem(f"{evidence['name']} ({evidence['size']}MB)")
            item.setData(QtCore.Qt.UserRole, evidence)
            self.ui.listWidgetMemoryFiles.addItem(item)

    def update_file_info(self):
        """Update the info label based on the selected memory file."""
        selected_items = self.ui.listWidgetMemoryFiles.selectedItems()
        if not selected_items:
            self.ui.labelFileInfo.setText("File info: Select a file from the list")
            return

        evidence = selected_items[0].data(QtCore.Qt.UserRole)
        self.ui.labelFileInfo.setText(
            f"Path: {evidence['path']} | Format: {evidence['format']}"
        )

    def start_analysis(self):
        """Begin the analysis for the selected memory file."""
        selected_items = self.ui.listWidgetMemoryFiles.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "No Selection", "Please select a memory file to analyze."
            )
            return

        evidence = selected_items[0].data(QtCore.Qt.UserRole)
        evidence_name = evidence["name"]

        # Check if a tab for this evidence already exists
        for i in range(self.ui.tabWidget.count()):
            if self.ui.tabWidget.tabText(i) == evidence_name:
                self.ui.tabWidget.setCurrentIndex(i)
                return

        # Remove the initial placeholder tab if it's there
        if self.ui.tabWidget.count() > 0 and self.ui.tabWidget.tabText(0) == "Start":
            self.ui.tabWidget.removeTab(0)

        # Create a new tab for the analysis results
        analysis_widget = AnalysisResultTab(evidence_name=evidence_name)
        index = self.ui.tabWidget.addTab(analysis_widget, evidence_name)
        self.ui.tabWidget.setCurrentIndex(index)

    def close_tab(self, index):
        """Close a specific analysis tab."""
        widget = self.ui.tabWidget.widget(index)
        if widget:
            widget.deleteLater()
        self.ui.tabWidget.removeTab(index)

        # If no tabs are left, add the placeholder back
        if self.ui.tabWidget.count() == 0:
            placeholder = QWidget()
            # You might want to recreate the placeholder UI here if needed
            self.ui.tabWidget.addTab(placeholder, "Start")
