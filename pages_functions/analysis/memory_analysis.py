from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
    QTableWidgetItem,
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTabWidget,
)
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from ui.pages.analysis_ui.memory_analysis_ui import Ui_MemoryAnalysisWindow
import os
from PyQt5.QtWidgets import QSizePolicy
import glob
import importlib.util
import json, io, sys
from contextlib import redirect_stdout
from datetime import datetime

# Đường dẫn tuyệt đối hoặc tương đối đến thư mục volatility3 (chứa __init__.py)
vol3_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../tools/volatility3")
)
if vol3_path not in sys.path:
    sys.path.insert(0, vol3_path)

from volatility3.framework import contexts, interfaces, exceptions
from volatility3.framework.configuration import requirements
from volatility3.framework import automagic
from volatility3.framework import plugins
from volatility3.framework import constants
from volatility3.framework import renderers
from volatility3.framework import layers
from volatility3.framework import symbols
from volatility3.framework import configuration
from volatility3.framework.automagic import stacker
from volatility3 import cli
from database.db_manager import DatabaseManager

import logging


def run_volatility3_plugin(memory_path: str, plugin_name: str) -> dict:
    """
    Chạy vol.py với JSON renderer, trả về dict parsed từ JSON.
    Nếu không parse được JSON thì fallback: đưa text thành list of {"line":…, "content":…}.
    """
    # 1) Gán lại sys.argv và capture stdout
    sys.argv = ["vol.py", "-f", memory_path, "-r", "json", f"windows.{plugin_name}"]
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            cli.main()
        except SystemExit:
            pass
    out = buf.getvalue().strip()

    # 2) Thử parse JSON
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # fallback: mỗi dòng non-empty thành một record
        lines = out.splitlines()
        data = [{"line": i + 1, "content": l} for i, l in enumerate(lines) if l.strip()]
        return {"data": data, "total": len(data), "plugin": plugin_name}


class MemoryAnalysisWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MemoryAnalysisWindow()
        self.ui.setupUi(self)
        self.db = DatabaseManager()
        logging.info(f"Using SQLite DB at: {os.path.abspath(self.db.db_path)}")
        print("DEBUG: DB path =", os.path.abspath(self.db.db_path))
        connected = self.db.connect()
        print("DEBUG: Connected?", connected)
        self.current_results_dir: str = ""
        self.curren_evidence_type: str = ""
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

        # Lưu lại thông tin các tab (widget, tiêu đề)
        self.all_tabs = [
            (self.ui.rawMemoryTab, "Raw Memory Analysis"),
            (self.ui.hibernationTab, "Hibernation Analysis"),
            (self.ui.pageFileTab, "Page File Analysis"),
            (self.ui.crashDumpTab, "Crash Dump Analysis"),
            (self.ui.aiAnalysisTab, "AI Analysis"),
            (self.ui.analysisOptionsTab, "Analysis Options"),
            (self.ui.logTab, "Analysis Log"),
        ]

        # Gọi cập nhật tab ngay khi mở trang
        default_type = self.ui.evidenceTypeCombo.currentText()
        self.update_tabs_for_evidence(default_type)

    def make_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        # ví dụ: canh giữa
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def parse_json_to_table(self, json_data, table_widget):
        """
        Tự động dò header và data từ JSON trả về của bất kỳ plugin nào,
        sau đó hiển thị lên QTableWidget mà không cần khai báo cột cố định.
        """
        table_widget.clear()
        table_widget.setRowCount(0)

        # Trường hợp lỗi hoặc không có data
        if not json_data or (isinstance(json_data, dict) and "error" in json_data):
            msg = (
                json_data.get("error", "Unknown error")
                if isinstance(json_data, dict)
                else "No data"
            )
            table_widget.setColumnCount(2)
            table_widget.setHorizontalHeaderLabels(["Status", "Message"])
            table_widget.insertRow(0)
            table_widget.setItem(0, 0, self.make_item("Error"))
            table_widget.setItem(0, 1, self.make_item(msg))
            return

        # Nếu là dict chứa list ở một trong các key tiêu chuẩn
        if isinstance(json_data, dict):
            # Các key có thể mang list data
            for key in (
                "processes",
                "connections",
                "files",
                "hashes",
                "findings",
                "data",
            ):
                if key in json_data and isinstance(json_data[key], list):
                    data_list = json_data[key]
                    # Đặc biệt filescan vẫn dùng riêng nếu cần
                    if key == "files":
                        self._setup_filescan_table(table_widget, data_list)
                    else:
                        self._setup_generic_table(table_widget, data_list)
                    return
            # Không tìm thấy list: hiển thị toàn bộ key-value
            self._setup_key_value_table(table_widget, json_data)
            return

        # Nếu JSON là list ngay từ đầu
        if isinstance(json_data, list):
            self._setup_generic_table(table_widget, json_data)
            return

    def _setup_generic_table(self, table_widget, data_list: list):
        """
        Hiển thị bất kỳ list-of-dict nào:
          - Lấy headers từ dict đầu tiên
          - Tạo column và insert từng row
        """
        if not data_list:
            table_widget.setColumnCount(1)
            table_widget.setHorizontalHeaderLabels(["Message"])
            table_widget.insertRow(0)
            table_widget.setItem(0, 0, self.make_item("No items"))
            return

        # Lấy tất cả keys từ phần tử đầu (giả sử dict)
        first = data_list[0] if isinstance(data_list[0], dict) else {}
        headers = list(first.keys()) if isinstance(first, dict) else ["Value"]
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)

        for item in data_list:
            row = table_widget.rowCount()
            table_widget.insertRow(row)
            if isinstance(item, dict):
                for col, key in enumerate(headers):
                    val = item.get(key, "")
                    table_widget.setItem(row, col, self.make_item(str(val)))
            else:
                table_widget.setItem(row, 0, self.make_item(str(item)))

        table_widget.resizeColumnsToContents()

    def _setup_key_value_table(self, table_widget, json_dict: dict):
        """
        Hiển thị dict thuần thành 2 cột Key / Value.
        """
        table_widget.setColumnCount(2)
        table_widget.setHorizontalHeaderLabels(["Key", "Value"])
        for k, v in json_dict.items():
            row = table_widget.rowCount()
            table_widget.insertRow(row)
            table_widget.setItem(row, 0, self.make_item(str(k)))
            if isinstance(v, list):
                table_widget.setItem(row, 1, self.make_item(f"{len(v)} items"))
            else:
                table_widget.setItem(row, 1, self.make_item(str(v)))
        table_widget.resizeColumnsToContents()

    def format_json_output(self, json_data, title: str = "") -> str:
        """
        Format JSON data để hiển thị trong QTextEdit (hoặc QTextBrowser).
        """
        import json

        # Nếu là lỗi
        if isinstance(json_data, dict) and "error" in json_data:
            return f"{title}\nError: {json_data['error']}"

        # Cố gắng stringify đẹp
        try:
            pretty = json.dumps(json_data, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(json_data)

        if title:
            return f"{title}\n\n{pretty}"
        else:
            return pretty

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
            # Process plugins
            if name in {
                "pslist",
                "pstree",
                "psscan",
                "psxview",
                "processghosting",
                "hollowprocesses",
                "threads",
                "thrdscan",
                "suspended_threads",
                "suspicious_threads",
                "memmap",
                "pedump",
                "envars",
                "privileges",
                "handles",
                "dlllist",
                "ldrmodules",
                "getsids",
                "malfind",
                "iat",
                "pe_symbols",
                "svcscan",
                "svclist",
                "getservicesids",
                "callbacks",
                "mutantscan",
                "sessions",
                "modules",
                "modscan",
                "unloadedmodules",
                "driverscan",
                "driverirp",
                "drivermodule",
                "direct_system_calls",
                "indirect_system_calls",
                "unhooked_system_calls",
                "orphan_kernel_threads",
            }:
                ptype = "Process"
            # Network plugins
            elif name in {"netscan", "netstat"}:
                ptype = "Network"
            # File plugins
            elif name in {"filescan", "dumpfiles", "mbrscan", "mftscan"}:
                ptype = "File"
            # Registry plugins
            elif name in {"registry", "hivelist", "hivescan"}:
                ptype = "Registry"
            elif name in {"hashdump", "lsadump", "cachedump"}:
                ptype = "Credential"
            elif name in {"cmdscan", "cmdline", "consoles"}:
                ptype = "Command"
            else:
                ptype = "Other"
            plugins.append({"name": name, "desc": doc, "type": ptype})
        self.all_plugins = plugins
        self.plugin_types = {p["name"]: p["type"] for p in plugins}
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
            # Process plugins
            "pslist",
            "pstree",
            "psscan",
            "dlllist",
            "malfind",
            # Network plugins
            "netscan",
            # File plugins
            "filescan",
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
            import os

            self.ui.filePathEdit.setText(file_path)
            # Auto-detect type
            detected_type = self.detect_evidence_type(file_path)
            self.curren_evidence_type = detected_type
            self.ui.evidenceTypeCombo.setCurrentText(detected_type)
            self.switch_tab_by_type(detected_type)
            # Thử load kết quả cũ nếu có
            fp = os.path.normpath(file_path)
            latest = self.db.get_latest_analysis_result(fp, detected_type)
            if latest:
                rp = latest["result_path"]
                if not os.path.isabs(rp):
                    rp = os.path.abspath(rp)
                if os.path.isdir(rp):
                    self.current_results_dir = rp
                    self.load_all_plugin_results(rp)
                    self.ui.statusLabel.setText(
                        f"Status: Loaded previous analysis results from {rp}"
                    )
                    return

            # Nếu chưa có file kết quả, chỉ báo Selected
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
        self.update_tabs_for_evidence(type_text)
        self.switch_tab_by_type(type_text)

        self.ui.statusLabel.setText(f"Status: Evidence type set to {type_text}")

    def switch_tab_by_type(self, type_text):
        """Chuyển đến tab phù hợp với loại evidence"""
        if type_text.startswith("Raw Memory"):
            # Với Raw Memory, active tab "Analysis Options"
            for i in range(self.ui.mainTabWidget.count()):
                if (
                    self.ui.mainTabWidget.isTabVisible(i)
                    and self.ui.mainTabWidget.tabText(i) == "Analysis Options"
                ):
                    self.ui.mainTabWidget.setCurrentIndex(i)
                    return
            # Fallback nếu không tìm thấy Analysis Options
            for i in range(self.ui.mainTabWidget.count()):
                if self.ui.mainTabWidget.isTabVisible(i):
                    self.ui.mainTabWidget.setCurrentIndex(i)
                    return
        else:
            # Với các loại evidence khác, active tab đầu tiên visible
            for i in range(self.ui.mainTabWidget.count()):
                if self.ui.mainTabWidget.isTabVisible(i):
                    self.ui.mainTabWidget.setCurrentIndex(i)
                    return

    def run_and_display_plugin(self, plugin_name, memory_path):
        """
        Chạy bất kỳ plugin windows.{plugin_name} nào và đổ output lên UI.
        Tự tìm widget: TableWidget, TreeWidget, TextEdit theo tên chuẩn:
        <plugin_name>Table, <plugin_name>Tree, <plugin_name>Text, ...
        Nếu không có sẵn, tạo tab mới với QTableWidget và parse_json_to_table.
        """
        # 1) Chạy plugin
        json_data = run_volatility3_plugin(memory_path, plugin_name)

        # 2) Xác định widget đã được define trong .ui
        cat = self.plugin_types.get(
            plugin_name, "Khác"
        )  # e.g. "Process", "Network", ...
        cat_lower = cat.lower()  # "process", "network", ...
        container_tabwidget_name = f"{cat_lower}TabWidget"

        # 3) Nếu UI đã có widget riêng (Table/Tree/Text), fill vào luôn
        for suffix in ("Table", "Tree", "Text"):
            attr = plugin_name + suffix
            if hasattr(self.ui, attr):
                w = getattr(self.ui, attr)
                if suffix == "Table":
                    self.parse_json_to_table(json_data, w)
                elif suffix == "Tree":
                    self.parse_json_to_tree(json_data, w)
                elif suffix == "Text":
                    w.setText(self.format_json_output(json_data, plugin_name))
                return

        # 4) Fallback: tự sinh 1 tab con trong đúng category
        if hasattr(self.ui, container_tabwidget_name):
            tabs: QTabWidget = getattr(self.ui, container_tabwidget_name)
        else:
            # nếu lỗi, đẩy vào customTabWidget
            tabs = getattr(self.ui, "customTabWidget")

        # tạo 1 bảng chung
        tab = QWidget()
        layout = QVBoxLayout(tab)
        table = QTableWidget()
        layout.addWidget(table)
        self.parse_json_to_table(json_data, table)
        tabs.addTab(tab, plugin_name)

    def load_all_plugin_results(self, results_dir: str):
        import os, json

        for fname in os.listdir(results_dir):
            print(
                f"DEBUG: load_all_plugin_results called, results_dir={results_dir}"
            )  # <- kiểm tra có chạy vào đây không
            print("DEBUG: files in dir:", os.listdir(results_dir))
            if not fname.endswith(".json") or fname == "analysis_info.json":
                continue
            print(f"DEBUG: processing file: {fname}")
            plugin = fname[:-5]  # bỏ ".json"
            print(
                f"DEBUG: plugin='{plugin}' → sẽ tìm widget '{plugin}Table', '{plugin}Tree' hoặc '{plugin}Text'"
            )
            path = os.path.join(results_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # điền vào widget có sẵn hoặc tạo tab mới
            filled = False
            for suffix, filler in (
                ("Table", self.parse_json_to_table),
                ("Text", lambda d, w: w.setText(self.format_json_output(d, plugin))),
            ):
                available = [a for a in dir(self.ui) if plugin.lower() in a.lower()]
                print(f"DEBUG: available UI attrs matching '{plugin}':", available)
                attr = plugin + suffix
                print(f"DEBUG: plugin '{plugin}' filled? {filled}")
                if hasattr(self.ui, attr):
                    widget = getattr(self.ui, attr)
                    filler(data, widget)
                    filled = True
                    break
            if not filled:
                # fallback: tạo tab mới trong container tương ứng
                cat = self.plugin_types.get(plugin, "Other").lower()
                tabw = (
                    getattr(self.ui, f"{cat}TabWidget", None) or self.ui.customTabWidget
                )

                page = QWidget()
                layout = QVBoxLayout(page)
                tbl = QTableWidget()
                layout.addWidget(tbl)
                self.parse_json_to_table(data, tbl)
                tabw.addTab(page, plugin)
                tabw.setCurrentIndex(tabw.count() - 1)

    def start_analysis(self):
        import os
        import json
        from datetime import datetime

        file_path = self.ui.filePathEdit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "No File", "Please select a valid evidence file.")
            return
        file_path = os.path.normpath(file_path)

        # Nếu chưa phân tích, chạy plugin
        ev_type = self.detect_evidence_type(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = os.path.abspath(
            os.path.join(
                "analysis_results", f"{os.path.basename(file_path)}_{timestamp}"
            )
        )
        os.makedirs(results_dir, exist_ok=True)
        self.current_results_dir = results_dir
        selected = self.get_selected_plugins()
        if not selected:
            QMessageBox.warning(
                self, "No Plugins", "Please select at least one plugin."
            )
            return
        # chạy từng plugin và hiển thị lên UI
        for plugin in selected:
            json_data = run_volatility3_plugin(file_path, plugin)
            self.run_and_display_plugin(plugin, file_path)
            out_put = os.path.join(results_dir, f"{plugin}.json")
            with open(out_put, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
        # lưu kết quả vào db
        self.db.save_memory_analysis_result(
            file_path,
            ev_type,
            result_path=results_dir,
            summary=f"Analysis of {os.path.basename(file_path)}",
        )
        self.ui.statusLabel.setText("Status: Hoàn thành phân tích")

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
        self.ui.pslistTable.setRowCount(0)
        self.ui.malfindText.clear()
        self.ui.netscanTable.setRowCount(0)
        self.ui.filescanTable.clear()
        # self.ui.hivelistTable.clear()
        self.ui.dlllistTable.clear()
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
        self.ui.statusLabel.setText("Status: Ready")
        self.ui.logTextEdit.clear()

    def mock_show_raw_memory_result(self):
        self.mock_reset_ui()
        self.ui.osVersionValue.setText("Windows 10 x64")
        self.ui.architectureValue.setText("x64")
        self.ui.timestampValue.setText("2024-06-01 10:00:00")
        # Process Table
        self.ui.pslistTable.setRowCount(2)
        self.ui.pslistTable.setItem(0, 0, self.make_item("4"))
        self.ui.pslistTable.setItem(0, 1, self.make_item("System"))
        self.ui.pslistTable.setItem(0, 2, self.make_item("80"))
        self.ui.pslistTable.setItem(0, 3, self.make_item("200"))
        self.ui.pslistTable.setItem(0, 4, self.make_item("Running"))
        self.ui.pslistTable.setItem(1, 0, self.make_item("5012"))
        self.ui.pslistTable.setItem(1, 1, self.make_item("explorer.exe"))
        self.ui.pslistTable.setItem(1, 2, self.make_item("30"))
        self.ui.pslistTable.setItem(1, 3, self.make_item("100"))
        self.ui.pslistTable.setItem(1, 4, self.make_item("Running"))
        self.ui.malfindText.setText(
            "No malware detected.\nRWX region found in explorer.exe PID 5012."
        )
        # Network Table
        self.ui.netscanTable.setRowCount(1)
        self.ui.netscanTable.setItem(0, 0, self.make_item("127.0.0.1:1234"))
        self.ui.netscanTable.setItem(0, 1, self.make_item("8.8.8.8:80"))
        self.ui.netscanTable.setItem(0, 2, self.make_item("ESTABLISHED"))
        self.ui.netscanTable.setItem(0, 3, self.make_item("5012"))
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

    def load_case_data(self, case_id):
        """Set case name in the Case name QLineEdit and disable it."""
        try:
            from database.db_manager import DatabaseManager

            db = DatabaseManager()
            db.connect()
            case_info = db.get_case_with_investigator(case_id)
            if case_info and "title" in case_info:
                self.ui.lineEdit.setText(case_info["title"])
            else:
                self.ui.lineEdit.setText("-")
        except Exception as e:
            self.ui.lineEdit.setText("-")
        self.ui.lineEdit.setDisabled(True)

    def update_tabs_for_evidence(self, type_text):
        """Ẩn/hiện tab thay vì xóa để giữ nguyên dữ liệu"""

        # Định nghĩa các tab cần hiển thị cho từng loại evidence
        tab_visibility_rules = {
            "Raw Memory": [
                "Raw Memory Analysis",
                "AI Analysis",
                "Analysis Options",
                "Analysis Log",
            ],
            "Hibernation": ["Hibernation Analysis", "Analysis Log"],
            "Page File": ["Page File Analysis", "Analysis Log"],
            "Crash Dump": [
                "Crash Dump Analysis",
                "AI Analysis",
                "Analysis Options",
                "Analysis Log",
            ],
        }

        # Xác định loại evidence
        evidence_type = None
        if type_text.startswith("Raw Memory"):
            evidence_type = "Raw Memory"
        elif type_text.startswith("Hibernation"):
            evidence_type = "Hibernation"
        elif type_text.startswith("Page File"):
            evidence_type = "Page File"
        elif type_text.startswith("Crash Dump"):
            evidence_type = "Crash Dump"
        else:
            evidence_type = "Raw Memory"  # Default

        # Lấy danh sách tab cần hiển thị
        tabs_to_show = tab_visibility_rules.get(evidence_type, ["Analysis Log"])

        # Ẩn/hiện tab dựa trên quy tắc
        for i in range(self.ui.mainTabWidget.count()):
            tab_title = self.ui.mainTabWidget.tabText(i)
            should_show = tab_title in tabs_to_show

            # Ẩn/hiện tab
            self.ui.mainTabWidget.setTabVisible(i, should_show)

        # Đảm bảo có ít nhất 1 tab visible và active tab phù hợp
        visible_tabs = [
            i
            for i in range(self.ui.mainTabWidget.count())
            if self.ui.mainTabWidget.isTabVisible(i)
        ]

        if visible_tabs:
            # Với Raw Memory, ưu tiên active tab "Analysis Options"
            if evidence_type == "Raw Memory":
                analysis_options_index = None
                for i in visible_tabs:
                    if self.ui.mainTabWidget.tabText(i) == "Analysis Options":
                        analysis_options_index = i
                        break
                if analysis_options_index is not None:
                    self.ui.mainTabWidget.setCurrentIndex(analysis_options_index)
                else:
                    self.ui.mainTabWidget.setCurrentIndex(visible_tabs[0])
            else:
                self.ui.mainTabWidget.setCurrentIndex(visible_tabs[0])


# Để sử dụng: tạo instance MemoryAnalysisWindow() và show() trong main app
