from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
    QTableWidgetItem,
)
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from ui.pages.analysis_ui.memory_analysis_ui import Ui_MemoryAnalysisWindow
import os
from PyQt5.QtWidgets import QSizePolicy
import glob
import importlib.util


class MemoryAnalysisWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MemoryAnalysisWindow()
        self.ui.setupUi(self)

        # —————————————— TabBar: Không cắt chữ, không dàn đều, đủ rộng cho tiêu đề ——————————————
        tabbar = self.ui.mainTabWidget.tabBar()
        if tabbar is not None:
            tabbar.setExpanding(False)
            tabbar.setUsesScrollButtons(True)
        self.ui.mainTabWidget.setStyleSheet(
            """
        QTabBar::tab {
            min-width: 160px;
            padding: 8px 20px;
            font-size: 15px;
        }
        """
        )
        # ————————————————————————————————————————————————
        for gb in (
            self.ui.rawMemoryTab,
            self.ui.hibernationTab,
            self.ui.pageFileTab,
            self.ui.crashDumpTab,
        ):
            gb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.analysis_running = False
        self.mock_reset_ui()
        self.load_volatility_plugins()
        # Kết nối tìm kiếm plugin
        if hasattr(self.ui, "pluginSearchEdit"):
            self.ui.pluginSearchEdit.textChanged.connect(self.filter_plugin_table)

    def setup_connections(self):
        self.ui.browseButton.clicked.connect(self.browse_evidence_file)
        self.ui.startAnalysisButton.clicked.connect(self.start_analysis)
        self.ui.stopButton.clicked.connect(self.stop_analysis)
        self.ui.evidenceTypeCombo.currentTextChanged.connect(self.evidence_type_changed)
        if hasattr(self.ui, "pluginSearchEdit"):
            self.ui.pluginSearchEdit.textChanged.connect(self.filter_plugin_list)

    def load_volatility_plugins(self):
        plugin_dir = r"E:/DATN/Windows_forensic/tools/volatility3/volatility3/framework/plugins/windows"
        import glob, os

        plugin_files = glob.glob(os.path.join(plugin_dir, "*.py"))
        plugins = []
        for pf in plugin_files:
            name = os.path.splitext(os.path.basename(pf))[0]
            if name.startswith("_") or name == "init":
                continue
            doc = ""
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.strip().startswith('"""') or line.strip().startswith(
                            "'''"
                        ):
                            doc = line.strip().strip("\"'")
                            break
            except Exception:
                pass
            # Gán loại plugin đơn giản dựa trên tên
            if name in {"pslist", "pstree", "psscan"}:
                ptype = "Process"
            elif name in {"netscan"}:
                ptype = "Network"
            elif name in {"malfind", "hashdump"}:
                ptype = "Malware"
            elif name in {"filescan"}:
                ptype = "File"
            elif name in {"registry"}:
                ptype = "Registry"
            else:
                ptype = "Khác"
            plugins.append({"name": name, "desc": doc, "type": ptype})
        self.all_plugins = plugins
        self.populate_plugin_table()

    def populate_plugin_table(self, filter_text=""):
        if not hasattr(self.ui, "pluginTableWidget"):
            print(
                "Bạn cần thêm QTableWidget tên pluginTableWidget vào file .ui để hiển thị danh sách plugin Volatility."
            )
            return
        table = self.ui.pluginTableWidget
        table.setRowCount(0)
        default_plugins = {
            "pslist",
            "pstree",
            "psscan",
            "netscan",
            "malfind",
            "filescan",
            "registry",
            "hashdump",
        }
        for p in self.all_plugins:
            if (
                filter_text
                and filter_text.lower() not in p["name"].lower()
                and filter_text.lower() not in p.get("desc", "").lower()
            ):
                continue
            row = table.rowCount()
            table.insertRow(row)
            # Checkbox
            chk = QTableWidgetItem()
            chk.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            if p["name"] in default_plugins:
                chk.setCheckState(QtCore.Qt.Checked)
            else:
                chk.setCheckState(QtCore.Qt.Unchecked)
            table.setItem(row, 0, chk)
            # Name
            table.setItem(row, 1, QTableWidgetItem(p["name"]))
            # Type
            table.setItem(row, 2, QTableWidgetItem(p.get("type", "")))
            # Description
            desc_item = QTableWidgetItem(p.get("desc", ""))
            desc_item.setToolTip(p.get("desc", ""))
            table.setItem(row, 3, desc_item)
        table.resizeColumnsToContents()
        if table.horizontalHeader() is not None:
            try:
                table.horizontalHeader().setStretchLastSection(True)
            except Exception:
                pass

    def filter_plugin_table(self, text):
        self.populate_plugin_table(filter_text=text)

    def get_selected_plugins(self):
        table = self.ui.pluginTableWidget
        selected = []
        for row in range(table.rowCount()):
            item0 = table.item(row, 0)
            item1 = table.item(row, 1)
            if item0 is not None and item0.checkState() == QtCore.Qt.Checked:
                if item1 is not None:
                    selected.append(item1.text())
        return selected

    def browse_evidence_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Memory Evidence File", "", "All Files (*.*)"
        )
        if file_path:
            self.ui.filePathEdit.setText(file_path)
            # Auto-detect type
            detected_type = self.detect_evidence_type(file_path)
            self.ui.evidenceTypeCombo.setCurrentText(detected_type)
            self.switch_tab_by_type(detected_type)
            self.ui.statusLabel.setText(
                f"Status: Selected {os.path.basename(file_path)}"
            )

    def detect_evidence_type(self, file_path):
        fname = os.path.basename(file_path).lower()
        if fname.endswith((".raw", ".mem", ".vmem")):
            return "Raw Memory (.raw, .mem, .vmem)"
        elif fname == "hiberfil.sys":
            return "Hibernation File (hiberfil.sys)"
        elif fname == "pagefile.sys":
            return "Page File (pagefile.sys)"
        elif fname.endswith(".dmp"):
            return "Crash Dump (.dmp)"
        return "Raw Memory (.raw, .mem, .vmem)"

    def evidence_type_changed(self, type_text):
        self.switch_tab_by_type(type_text)

    #        self.ui.statusLabel.setText(f"Status: Evidence type set to {type_text}")

    def switch_tab_by_type(self, type_text):
        tab_map = {
            "Raw Memory (.raw, .mem, .vmem)": self.ui.mainTabWidget.indexOf(
                self.ui.rawMemoryTab
            ),
            "Hibernation File (hiberfil.sys)": self.ui.mainTabWidget.indexOf(
                self.ui.hibernationTab
            ),
            "Page File (pagefile.sys)": self.ui.mainTabWidget.indexOf(
                self.ui.pageFileTab
            ),
            "Crash Dump (.dmp)": self.ui.mainTabWidget.indexOf(self.ui.crashDumpTab),
        }
        idx = tab_map.get(type_text, 0)
        self.ui.mainTabWidget.setCurrentIndex(idx)

    def start_analysis(self):
        file_path = self.ui.filePathEdit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "No File", "Please select a valid evidence file.")
            return
        type_text = self.ui.evidenceTypeCombo.currentText()
        self.ui.statusLabel.setText(
            f"Status: Analyzing {os.path.basename(file_path)}..."
        )
        self.ui.progressBar.setValue(10)
        self.analysis_running = True
        # Mock logic for each type
        if type_text.startswith("Raw Memory"):
            self.mock_show_raw_memory_result()
        elif type_text.startswith("Hibernation"):
            self.mock_show_hibernation_result()
        elif type_text.startswith("Page File"):
            self.mock_show_pagefile_result()
        elif type_text.startswith("Crash Dump"):
            self.mock_show_crashdump_result()
        self.ui.progressBar.setValue(100)
        self.ui.statusLabel.setText(
            f"Status: Analysis complete for {os.path.basename(file_path)}"
        )
        self.append_log(f"Analysis complete for {os.path.basename(file_path)}")

    def stop_analysis(self):
        if self.analysis_running:
            self.analysis_running = False
            self.ui.statusLabel.setText("Status: Analysis stopped.")
            self.append_log("Analysis stopped by user.")
            self.ui.progressBar.setValue(0)

    def mock_reset_ui(self):
        # Reset all result widgets to default/empty
        self.ui.osVersionValue.setText("-")
        self.ui.architectureValue.setText("-")
        self.ui.timestampValue.setText("-")
        self.ui.processTable.setRowCount(0)
        self.ui.malwareResultsText.clear()
        self.ui.networkTable.setRowCount(0)
        self.ui.filescanTree.clear()
        self.ui.registryTree.clear()
        self.ui.hibernationTypeValue.setText("-")
        self.ui.compressedSizeValue.setText("-")
        self.ui.originalSizeValue.setText("-")
        self.ui.hibernationResultsText.clear()
        self.ui.pageFileScanTable.setRowCount(0)
        self.ui.yaraResultsText.clear()
        self.ui.crashReasonValue.setText("-")
        self.ui.bugCheckValue.setText("-")
        self.ui.faultingDriverValue.setText("-")
        self.ui.windbgResultsText.clear()
        self.ui.volatilityCrashText.clear()
        self.ui.aiResultsText.clear()
        self.ui.progressBar.setValue(0)
        #        self.ui.statusLabel.setText("Status: Ready")
        self.ui.logTextEdit.clear()

    def mock_show_raw_memory_result(self):
        self.mock_reset_ui()
        self.ui.osVersionValue.setText("Windows 10 x64")
        self.ui.architectureValue.setText("x64")
        self.ui.timestampValue.setText("2024-06-01 10:00:00")
        # Process Table
        self.ui.processTable.setRowCount(2)
        self.ui.processTable.setItem(0, 0, self.make_item("4"))
        self.ui.processTable.setItem(0, 1, self.make_item("System"))
        self.ui.processTable.setItem(0, 2, self.make_item("80"))
        self.ui.processTable.setItem(0, 3, self.make_item("200"))
        self.ui.processTable.setItem(0, 4, self.make_item("Running"))
        self.ui.processTable.setItem(1, 0, self.make_item("5012"))
        self.ui.processTable.setItem(1, 1, self.make_item("explorer.exe"))
        self.ui.processTable.setItem(1, 2, self.make_item("30"))
        self.ui.processTable.setItem(1, 3, self.make_item("100"))
        self.ui.processTable.setItem(1, 4, self.make_item("Running"))
        self.ui.malwareResultsText.setText(
            "No malware detected.\nRWX region found in explorer.exe PID 5012."
        )
        # Network Table
        self.ui.networkTable.setRowCount(1)
        self.ui.networkTable.setItem(0, 0, self.make_item("127.0.0.1:1234"))
        self.ui.networkTable.setItem(0, 1, self.make_item("8.8.8.8:80"))
        self.ui.networkTable.setItem(0, 2, self.make_item("ESTABLISHED"))
        self.ui.networkTable.setItem(0, 3, self.make_item("5012"))
        # FileScan Tree
        from PyQt5.QtWidgets import QTreeWidgetItem

        file_item = QTreeWidgetItem(
            ["C:/Windows/System32/calc.exe", "123456", "2024-05-30 09:00"]
        )
        self.ui.filescanTree.addTopLevelItem(file_item)
        # Registry Tree
        reg_item = QTreeWidgetItem(["HKLM\\Software\\Microsoft", "Version", "REG_SZ"])
        self.ui.registryTree.addTopLevelItem(reg_item)
        self.append_log("Raw memory analysis mock result loaded.")

    def mock_show_hibernation_result(self):
        self.mock_reset_ui()
        self.ui.hibernationTypeValue.setText("Windows 10 Hibernation")
        self.ui.compressedSizeValue.setText("2.5 GB")
        self.ui.originalSizeValue.setText("8 GB")
        self.ui.hibernationResultsText.setText(
            "Converted to ActiveMemory.bin.\nReady for Volatility analysis."
        )
        self.append_log("Hibernation file analysis mock result loaded.")

    def mock_show_pagefile_result(self):
        self.mock_reset_ui()
        self.ui.pageFileScanTable.setRowCount(1)
        self.ui.pageFileScanTable.setItem(0, 0, self.make_item("0x1000"))
        self.ui.pageFileScanTable.setItem(0, 1, self.make_item("YARA Match"))
        self.ui.pageFileScanTable.setItem(
            0, 2, self.make_item("Suspicious string found")
        )
        self.ui.pageFileScanTable.setItem(0, 3, self.make_item("512"))
        self.ui.yaraResultsText.setText(
            "YARA rule matched: C2 beacon signature\nOffset: 0x1000"
        )
        self.append_log("Pagefile.sys analysis mock result loaded.")

    def mock_show_crashdump_result(self):
        self.mock_reset_ui()
        self.ui.crashReasonValue.setText("KERNEL_SECURITY_CHECK_FAILURE")
        self.ui.bugCheckValue.setText("0x00000139")
        self.ui.faultingDriverValue.setText("ntoskrnl.exe")
        self.ui.windbgResultsText.setText(
            "!analyze -v output: suspected driver corruption."
        )
        self.ui.volatilityCrashText.setText(
            "Volatility: No hidden processes found.\nNo malware detected."
        )
        self.append_log("Crash dump analysis mock result loaded.")

    def append_log(self, text):
        self.ui.logTextEdit.append(text)

    def browse_output_directory(self):
        # Dummy slot for UI connection
        pass

    def clear_log(self):
        self.ui.logTextEdit.clear()
        self.append_log("Log cleared.")

    def save_log(self):
        # Dummy slot for UI connection
        self.append_log("Log saved (mock).")

    def run_ai_analysis(self):
        # Dummy slot for UI connection
        self.append_log("AI analysis started (mock).")


# Để sử dụng: tạo instance MemoryAnalysisWindow() và show() trong main app
