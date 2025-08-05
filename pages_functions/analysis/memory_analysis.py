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
    QTreeWidgetItem,
    QHeaderView,
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
import subprocess

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
        self.setup_connections()
        self.db = DatabaseManager()
        logging.info(f"Using SQLite DB at: {os.path.abspath(self.db.db_path)}")
        print("DEBUG: DB path =", os.path.abspath(self.db.db_path))
        connected = self.db.connect()
        print("DEBUG: Connected?", connected)
        self.current_results_dir: str = ""
        self.curren_evidence_type: str = ""

        # Thêm CDB UI setup
        self.setup_cdb_ui()

        # Lưu danh sách custom commands
        self.custom_commands = []

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

    def format_info_output(self, json_data, title: str = "") -> str:
        """
        Chuyển json_data của plugin 'info' thành table text:
        Variable           Value
        Kernel Base        0xf8000145e000
        DTB                0x187000
        ...
        """
        # json_data thường là list of dict
        rows = json_data if isinstance(json_data, list) else json_data.get("data", [])
        # Tính độ rộng cột Variable
        max_var = max((len(item.get("Variable", "")) for item in rows), default=8)
        header = f"{'Variable'.ljust(max_var)}   Value"
        lines = [header, "-" * len(header)]
        for item in rows:
            var = item.get("Variable", "")
            val = item.get("Value", "")
            lines.append(f"{var.ljust(max_var)}   {val}")
        return "\n".join(lines)

    def setup_connections(self):
        # Removed browse button connection - no browse button needed
        self.ui.startAnalysisButton.clicked.connect(self.start_analysis)
        self.ui.stopButton.clicked.connect(self.stop_analysis)
        self.ui.evidenceTypeCombo.currentTextChanged.connect(self.evidence_type_changed)
        self.ui.lineEdit_2.textChanged.connect(self.on_search_strings)
        if hasattr(self.ui, "pluginSearchEdit"):
            self.ui.pluginSearchEdit.textChanged.connect(self.filter_plugin_table)

        # Connect evidence combo selection
        if hasattr(self.ui, "evidencecombo"):
            self.ui.evidencecombo.currentIndexChanged.connect(self.on_evidence_selected)
        else:
            print("DEBUG: evidencecombo not found in UI during setup_connections")

        # Add refresh shortcut (Ctrl+R)
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence

        refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut.activated.connect(self.refresh_evidence_combo)

        # Kết nối tree block click
        if hasattr(self.ui, "pagefiletreeWidget"):
            # self.ui.pagefiletreeWidget.itemClicked.connect(
            #    self.on_pagefile_block_clicked
            # )
            self.ui.pagefiletreeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.ui.pagefiletreeWidget.customContextMenuRequested.connect(
                self.show_pagefiletree_context_menu
            )

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
            "info",
            "pslist",
            "pstree",
            "psscan",
            "dlllist",
            "malfind",
            # Network plugins
            "netscan",
            # File plugins
            "filescan",
            "cmdline",
            "hashdump",
            "cachedump",
            "lsadump",
            "consoles",
            "cmdscan",
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
        # Check if case is selected - if so, use case-based evidence selection
        if self.is_case_mode():
            self.show_case_mode_message()
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Memory Evidence File",
            "",
            "Memory Files (*.raw *.mem *.vmem *.dmp);;System Files (*.sys);;All Files (*.*)",
        )
        if file_path:
            import os

            # Validate that selected file is a memory file
            if not self.is_memory_file(file_path):
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Invalid File Type",
                    "Vui lòng chọn file bộ nhớ hợp lệ:\n"
                    "• .raw, .mem, .vmem (Raw Memory)\n"
                    "• .dmp (Crash Dump)\n"
                    "• hiberfil.sys, pagefile.sys (System Files)",
                )
                return

            # Clear kết quả cũ trước khi load file mới
            self.clear_previous_results()

            self.ui.filePathEdit.setText(file_path)
            # Auto-detect type
            detected_type = self.detect_evidence_type(file_path)
            self.curren_evidence_type = detected_type
            self.ui.evidenceTypeCombo.setCurrentText(detected_type)
            self.switch_tab_by_type(detected_type)
            fp = os.path.normpath(file_path)
            if detected_type.startswith("Page File"):
                tool = "Page-brute"
            elif detected_type.startswith("Crash Dump"):
                tool = "CDB"
            else:
                tool = "Volatility 3"
            latest = self.db.get_latest_analysis_result(fp, detected_type, tool)
            if latest:
                rp = latest["result_path"]
                if not os.path.isabs(rp):
                    rp = os.path.abspath(rp)
                if os.path.isdir(rp):
                    self.current_results_dir = rp
                    if detected_type.startswith("Page File"):
                        self.load_page_brute_tree(rp)
                    elif detected_type.startswith("Crash Dump"):
                        self.load_cdb_results(rp)
                    else:
                        self.load_all_plugin_results(rp)
                    self.ui.statusLabel.setText(
                        f"Status: Loaded previous analysis results from {rp}"
                    )
                    return
                else:
                    pass
            else:
                pass

            # Nếu chưa có file kết quả, chỉ báo Selected
            self.ui.statusLabel.setText(
                f"Status: Selected {os.path.basename(file_path)}"
            )
            self.ui.progressBar.setValue(0)

    def is_memory_file(self, file_path):
        """Check if file is a memory dump file"""
        if not file_path:
            return False

        fname = os.path.basename(file_path).lower()
        memory_extensions = [".raw", ".mem", ".vmem", ".dmp"]
        memory_files = ["hiberfil.sys", "pagefile.sys"]

        return fname.endswith(tuple(memory_extensions)) or fname in memory_files

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
        if plugin_name == "info":
            output = self.format_info_output(json_data)
            self.ui.infoText.setText(output)
            return
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

            if plugin == "info":
                output = self.format_info_output(data)
                self.ui.infoText.setText(output)
                continue
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
        self.ui.progressBar.setValue(100)

    def start_analysis(self):
        import os
        import json
        from datetime import datetime
        from PyQt5.QtWidgets import QApplication

        # Check if case is selected and evidence is chosen from case
        if self.is_case_mode():
            current_index = self.ui.evidencecombo.currentIndex()
            if current_index <= 0:  # First item is placeholder
                QMessageBox.warning(
                    self,
                    "Chưa chọn Evidence",
                    "Vui lòng chọn evidence từ dropdown 'Evidence' để phân tích.",
                )
                return
            evidence_path = self.ui.evidencecombo.itemData(current_index)
            if not evidence_path or not os.path.exists(evidence_path):
                QMessageBox.warning(
                    self,
                    "Evidence không tồn tại",
                    "Evidence file không tồn tại. Vui lòng kiểm tra lại.",
                )
                return
            file_path = evidence_path
        else:
            # Fallback to file path edit for non-case analysis
            file_path = self.ui.filePathEdit.text().strip()
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(
                    self, "No File", "Please select a valid evidence file."
                )
                return

        file_path = os.path.normpath(file_path)

        ev_type = self.detect_evidence_type(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = os.path.abspath(
            os.path.join(
                "analysis_results", f"{os.path.basename(file_path)}_{timestamp}"
            )
        )
        os.makedirs(results_dir, exist_ok=True)
        self.current_results_dir = results_dir

        self.ui.statusLabel.setText("Status: Starting analysis...")
        self.ui.progressBar.setValue(0)
        QApplication.processEvents()

        if ev_type.startswith("Page File"):
            self.run_page_brute(file_path, results_dir)
            self.db.save_analysis_result(
                file_path,
                ev_type,
                tool_used="Page-brute",
                result_path=results_dir,
                summary=f"Analysis of {os.path.basename(file_path)}",
            )
            self.load_page_brute_tree(results_dir)
            self.ui.statusLabel.setText("Status: Page-brute analysis completed")
            self.ui.progressBar.setValue(100)
            return
        elif ev_type.startswith("Crash Dump"):
            self.run_basic_cdb_analysis()
            self.ui.progressBar.setValue(100)
            return

        selected = self.get_selected_plugins()
        if not selected:
            QMessageBox.warning(
                self, "No Plugins", "Please select at least one plugin."
            )
            return

        total = len(selected)
        for idx, plugin in enumerate(selected):
            self.ui.statusLabel.setText(f"Status: Running {plugin} ({idx+1}/{total})")
            QApplication.processEvents()
            json_data = run_volatility3_plugin(file_path, plugin)
            self.run_and_display_plugin(plugin, file_path)
            out_put = os.path.join(results_dir, f"{plugin}.json")
            with open(out_put, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            percent = int(((idx + 1) / total) * 100)
            self.ui.progressBar.setValue(percent)
            QApplication.processEvents()
        self.db.save_analysis_result(
            file_path,
            ev_type,
            tool_used="Volatility 3",
            result_path=results_dir,
            summary=f"Analysis of {os.path.basename(file_path)}",
        )
        self.ui.statusLabel.setText("Status: Hoàn thành phân tích")
        self.ui.progressBar.setValue(100)
        QApplication.processEvents()

    def stop_analysis(self):
        if self.analysis_running:
            self.analysis_running = False
            self.ui.statusLabel.setText("Status: Analysis stopped.")
            self.append_log("Analysis stopped by user.")
            self.ui.progressBar.setValue(0)

    def mock_reset_ui(self):
        # Reset all result widgets to default/empty
        # self.ui.osVersionValue.setText("-")
        # self.ui.architectureValue.setText("-")
        # self.ui.timestampValue.setText("-")
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
        self.ui.aiResultsText.clear()
        self.ui.progressBar.setValue(0)
        self.ui.statusLabel.setText("Status: Ready")
        self.ui.logTextEdit.clear()

        # Reset case-related UI elements
        if hasattr(self, "current_case_id"):
            self.current_case_id = None
        self.ui.lineEdit.setText("")
        self.ui.lineEdit.setEnabled(True)

        # Reset evidence dropdown to default
        self.ui.evidenceTypeCombo.clear()
        self.ui.evidenceTypeCombo.addItem("Raw Memory (.raw, .mem, .vmem)")
        self.ui.evidenceTypeCombo.addItem("Hibernation File (hiberfil.sys)")
        self.ui.evidenceTypeCombo.addItem("Page File (pagefile.sys)")
        self.ui.evidenceTypeCombo.addItem("Crash Dump (.dmp)")

        # Reset evidence selection combobox
        if hasattr(self.ui, "evidencecombo"):
            self.ui.evidencecombo.clear()
            self.ui.evidencecombo.addItem("-- Chọn evidence --", None)

        # Clear file path
        self.ui.filePathEdit.clear()

        # Clear CDB results tabs
        if hasattr(self, "cdb_results_tabwidget") and self.cdb_results_tabwidget:
            self.cdb_results_tabwidget.clear()

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
        """Load case data and populate evidence dropdown from case."""
        print(f"DEBUG: load_case_data called with case_id: {case_id}")
        try:
            from database.db_manager import DatabaseManager

            self.current_case_id = case_id
            db = DatabaseManager()
            db.connect()

            # Load case info
            case_info = db.get_case_with_investigator(case_id)
            print(f"DEBUG: case_info: {case_info}")
            if case_info and "title" in case_info:
                self.ui.lineEdit.setText(case_info["title"])
                print(f"DEBUG: Set case name: {case_info['title']}")
            else:
                self.ui.lineEdit.setText("-")
                print("DEBUG: No case info found")
            self.ui.lineEdit.setDisabled(True)

            # Load evidence from case
            evidence_list = db.get_artifacts_by_case(case_id)

            # Populate evidence dropdown (using evidencecombo)
            if hasattr(self.ui, "evidencecombo"):

                self.ui.evidencecombo.clear()
                self.ui.evidencecombo.addItem("-- Chọn evidence --", None)

                for evidence in evidence_list:
                    evidence_name = evidence.get("name", "Unknown")
                    evidence_path = evidence.get("source_path", "")
                    evidence_type = evidence.get("evidence_type", "")

                    # Only add evidence that can be analyzed for memory analysis
                    # File MUST be a memory file (check extension first)
                    is_memory_file = self.is_memory_file(evidence_path)

                    # Also check evidence_type for additional validation
                    is_memory_type = any(
                        keyword in evidence_type.upper()
                        for keyword in [
                            "MEMORY",
                            "DMP",
                            "RAW",
                            "VMEM",
                            "PAGEFILE",
                            "HIBERFIL",
                        ]
                    )

                    # Only add if it's actually a memory file (extension check is primary)
                    if is_memory_file:
                        display_text = f"{evidence_name} ({evidence_type})"
                        self.ui.evidencecombo.addItem(display_text, evidence_path)

                # Check if any memory files were added
                if self.ui.evidencecombo.count() <= 1:  # Only placeholder item
                    self.ui.evidencecombo.addItem(
                        "-- Không có file bộ nhớ nào --", None
                    )

                # Evidence combo connection is now handled in setup_connections()
            else:
                print("DEBUG: evidencecombo not found in UI!")

        except Exception as e:
            print(f"Error loading case data: {e}")
            import traceback

            traceback.print_exc()
            self.ui.lineEdit.setText("-")
            self.ui.lineEdit.setDisabled(True)

    def on_evidence_selected(self, index):
        """Handle evidence selection from dropdown"""
        if index <= 0:  # First item is placeholder
            self.ui.filePathEdit.clear()
            self.ui.statusLabel.setText("Status: Ready")
            self.ui.progressBar.setValue(0)
            return

        evidence_path = self.ui.evidencecombo.itemData(index)
        if evidence_path:
            # Clear previous results
            self.clear_previous_results()

            # Set file path
            self.ui.filePathEdit.setText(evidence_path)

            # Auto-detect type
            detected_type = self.detect_evidence_type(evidence_path)
            self.curren_evidence_type = detected_type
            self.ui.evidenceTypeCombo.setCurrentText(detected_type)
            self.switch_tab_by_type(detected_type)

            # Check for previous analysis results
            fp = os.path.normpath(evidence_path)
            if detected_type.startswith("Page File"):
                tool = "Page-brute"
            elif detected_type.startswith("Crash Dump"):
                tool = "CDB"
            else:
                tool = "Volatility 3"

            latest = self.db.get_latest_analysis_result(fp, detected_type, tool)
            if latest:
                rp = latest["result_path"]
                if not os.path.isabs(rp):
                    rp = os.path.abspath(rp)
                if os.path.isdir(rp):
                    self.current_results_dir = rp
                    if detected_type.startswith("Page File"):
                        self.load_page_brute_tree(rp)
                    elif detected_type.startswith("Crash Dump"):
                        self.load_cdb_results(rp)
                    else:
                        self.load_all_plugin_results(rp)
                    self.ui.statusLabel.setText(
                        f"Status: Loaded previous analysis results"
                    )
                    self.ui.progressBar.setValue(100)
                    return

            self.ui.statusLabel.setText(
                f"Status: Selected {os.path.basename(evidence_path)}"
            )
            self.ui.progressBar.setValue(0)
        else:
            self.ui.statusLabel.setText("Status: No evidence path available")

    def is_case_mode(self):
        """Check if currently in case-based analysis mode"""
        return hasattr(self, "current_case_id") and self.current_case_id is not None

    def refresh_evidence_combo(self):
        """Force refresh evidence combo with memory files only"""
        if hasattr(self, "current_case_id") and self.current_case_id is not None:
            # Reload case data to apply memory file filtering
            self.load_case_data(self.current_case_id)

    def show_case_mode_message(self):
        """Show message about case-based analysis mode"""
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "Chế độ phân tích Case",
            "Bạn đang trong chế độ phân tích case.\n\n"
            "📋 Cách sử dụng:\n"
            "1. Chọn evidence từ dropdown 'Evidence'\n"
            "2. Evidence sẽ được tự động load\n"
            "3. Bắt đầu phân tích\n\n"
            "💡 Để thoát chế độ case, hãy quay lại Case Management.",
        )

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

    def run_page_brute(self, pagefile_path, output_dir, yara_rule=None):
        import subprocess

        cmd = ["page-brute", "-f", pagefile_path, "-o", output_dir]
        if yara_rule:
            cmd += ["-r", yara_rule]
        subprocess.run(cmd, check=True)

    def load_page_brute_tree(self, result_dir):
        from PyQt5.QtWidgets import QTreeWidgetItem
        from PyQt5 import QtCore
        import os

        tree_widget = self.ui.pagefiletreeWidget
        tree_widget.clear()
        tree_widget.setColumnCount(3)
        tree_widget.setHeaderLabels(["Type/Rule", "Block/Offset", "Size (bytes)"])
        for category in os.listdir(result_dir):
            cat_path = os.path.join(result_dir, category)
            if os.path.isdir(cat_path):
                cat_item = QTreeWidgetItem([category, "", ""])
                block_files = [f for f in os.listdir(cat_path) if f.endswith(".block")]
                print(f"Rule {category} có {len(block_files)} block")  # DEBUG
                for fname in sorted(block_files, key=lambda x: int(x.split(".")[0])):
                    block_id = int(fname.split(".")[0])
                    offset = block_id * 4096
                    block_path = os.path.join(cat_path, fname)
                    size = os.path.getsize(block_path)
                    child = QTreeWidgetItem(
                        ["Block", f"{fname} (0x{offset:X})", str(size)]
                    )
                    child.setData(0, QtCore.Qt.UserRole, block_path)
                    cat_item.addChild(child)
                tree_widget.addTopLevelItem(cat_item)
        tree_widget.expandToDepth(0)
        header = tree_widget.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        # Chỉ set 100% nếu thực sự có kết quả phân tích
        if os.path.exists(result_dir) and any(
            os.path.isdir(os.path.join(result_dir, cat))
            for cat in os.listdir(result_dir)
        ):
            self.ui.progressBar.setValue(100)
        else:
            self.ui.progressBar.setValue(0)

    def open_with_hxd(self, file_path):
        import subprocess
        import os

        hxd_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../tools/HxD/HxD.exe")
        )
        si = subprocess.STARTUPINFO()
        si.dwFlags |= 1
        si.wShowWindow = 1

        try:
            subprocess.Popen([hxd_path, file_path], startupinfo=si)
        except Exception as e:
            QMessageBox.warning(self, "HxD Error", f"Không mở được HxD: {e}")

    def on_pagefile_block_clicked(self, item, column):
        # Nếu là block (item.text(0) == 'Block')
        if item.text(0) == "Block":
            file_path = item.data(0, QtCore.Qt.UserRole)
            print(f"Click block: {file_path}")  # DEBUG
            if file_path:
                self.open_with_hxd(file_path)

    def on_extract_strings(self, file_path):
        import re
        from PyQt5 import QtCore, QtWidgets

        # 1) Đọc block
        with open(file_path, "rb") as f:
            data = f.read()

        # 2) Tìm tất cả chuỗi ASCII ≥4 ký tự
        pattern = re.compile(b"[\x20-\x7E]{4,}")
        matches = [
            (m.start(), m.group().decode("ascii")) for m in pattern.finditer(data)
        ]

        # 3) Đổ vào QTableWidget tableStrings (2 cột Offset / String)
        tbl = self.ui.tableStrings
        tbl.clearContents()
        tbl.setRowCount(0)
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["Offset", "String"])
        tbl.setRowCount(len(matches))

        for row, (off, s) in enumerate(matches):
            item_off = QtWidgets.QTableWidgetItem(hex(off))
            item_off.setFlags(item_off.flags() ^ QtCore.Qt.ItemIsEditable)
            item_str = QtWidgets.QTableWidgetItem(s)
            item_str.setFlags(item_str.flags() ^ QtCore.Qt.ItemIsEditable)
            item_off.setTextAlignment(QtCore.Qt.AlignCenter)
            tbl.setItem(row, 0, item_off)
            tbl.setItem(row, 1, item_str)

        tbl.resizeColumnsToContents()
        hdr = tbl.horizontalHeader()
        # hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(QHeaderView.Stretch)

        # 4) Chuyển qua tab chứa tableStrings (nếu bạn xài QTabWidget)
        self.ui.stackedWidget.setCurrentWidget(self.ui.pageExtractStrings)

    def on_search_strings(self, text: str):
        """Lọc tableStrings theo text gõ vào:
        - ẩn row không có chuỗi chứa substring `text`
        """
        tbl = self.ui.tableStrings
        # Duyệt tất cả hàng
        for row in range(tbl.rowCount()):
            item = tbl.item(row, 1)  # cột 1 là String
            if not item:
                tbl.setRowHidden(row, True)
                continue

            # So sánh không phân biệt hoa thường
            cell_text = item.text().lower()
            query = text.lower()
            hide = bool(query) and (query not in cell_text)
            tbl.setRowHidden(row, hide)

    def on_show_yara_details(self, file_path):
        from PyQt5 import QtWidgets

        # Giả sử bạn đã lưu kết quả YARA scan của từng file_path trong dict:
        #   self.yara_matches: { path_str: [(rule_name, [(sig_name, offset, text),...]), ...] }
        matches = getattr(self, "yara_matches", {}).get(file_path, [])

        # 1) Build text
        lines = []
        for rule, items in matches:
            lines.append(f"Rule: {rule}")
            for name, off, txt in items:
                lines.append(f"  {name} @ {hex(off)}: {txt}")
        text = "\n".join(lines) or "(No matches)"

        # 2) Show lên QTextEdit txtYaraMatches
        self.ui.txtYaraMatches.setPlainText(text)
        # 3) Switch tab
        self.ui.stackedAnalysis.setCurrentWidget(self.ui.pageYaraDetails)

    def on_carve_files(self, file_path):
        import subprocess, tempfile, os
        from PyQt5.QtWidgets import QMessageBox

        # 1) Tạo thư mục tạm
        tmpdir = tempfile.mkdtemp(prefix="block_carve_")

        # 2) Gọi foremost để carve
        try:
            subprocess.run(
                ["foremost", "-i", file_path, "-o", tmpdir],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            QMessageBox.warning(self, "Carve Error", f"Không carve được: {e}")
            return

        # 3) Đọc file carved
        carved_dir = os.path.join(tmpdir, "carved")
        items = []
        if os.path.isdir(carved_dir):
            items = sorted(os.listdir(carved_dir))

        # 4) Show lên QListWidget lstCarved
        lst = self.ui.lstCarved
        lst.clear()
        if not items:
            lst.addItem("(No files found)")
        else:
            for name in items:
                lst.addItem(name)

        # 5) Switch tab
        self.ui.stackedAnalysis.setCurrentWidget(self.ui.pageCarveFiles)

    def show_pagefiletree_context_menu(self, pos):
        print("Right click at:", pos)
        tree = self.ui.pagefiletreeWidget
        item = tree.itemAt(pos)
        if not item or item.text(0) != "Block":
            return

        from PyQt5.QtWidgets import QMenu
        from PyQt5 import QtCore

        menu = QMenu(tree)
        menu.setStyleSheet(
            """
        QMenu {
            background-color: white;
            color: black;
            border: 1px solid #dee2e6;
        }
        QMenu::item:selected {
            background-color: #3399DB;
            color: white;
        }
    """
        )
        action_hxd = menu.addAction("Mở bằng HxD")
        action_extract = menu.addAction("Extract Strings")
        action_yara = menu.addAction("Show YARA Details")
        action_carve = menu.addAction("Carve Files")

        chosen = menu.exec_(tree.viewport().mapToGlobal(pos))
        if not chosen:
            return

        file_path = item.data(0, QtCore.Qt.UserRole)
        if not file_path:
            return

        if chosen == action_hxd:
            self.open_with_hxd(file_path)
        elif chosen == action_extract:
            self.on_extract_strings(file_path)
        elif chosen == action_yara:
            self.on_show_yara_details(file_path)
        elif chosen == action_carve:
            self.on_carve_files(file_path)

    def setup_cdb_ui(self):
        """
        Setup CDB UI và kết nối signals
        """
        # Kết nối button Add Custom
        if hasattr(self.ui, "addCustomCommandButton"):
            self.ui.addCustomCommandButton.clicked.connect(self.add_custom_cdb_command)

        # Kết nối Enter key trong custom command edit
        if hasattr(self.ui, "customCommandEdit"):
            self.ui.customCommandEdit.returnPressed.connect(self.add_custom_cdb_command)

        # Kết nối textChanged để real-time update command display
        if hasattr(self.ui, "customCommandEdit"):
            self.ui.customCommandEdit.textChanged.connect(
                self.on_custom_command_text_changed
            )

    def add_custom_cdb_command(self):
        """Thêm lệnh CDB tùy chỉnh"""
        if not hasattr(self.ui, "customCommandEdit"):
            return

        command = self.ui.customCommandEdit.text().strip()
        if not command:
            return

        # Thêm vào danh sách custom commands
        if command not in self.custom_commands:
            self.custom_commands.append(command)

        # Clear input
        self.ui.customCommandEdit.clear()

        # Chạy command ngay lập tức nếu có file
        file_path = self.ui.filePathEdit.text().strip()
        if file_path and os.path.exists(file_path):
            self.run_single_cdb_command(command)

    def on_custom_command_text_changed(self, text: str):
        """Handle khi text trong custom command edit thay đổi"""
        print(f"DEBUG: Custom command text changed: '{text}'")
        self.update_running_command_display(text)

    def update_running_command_display(self, command: str):
        """Cập nhật hiển thị command đang chạy"""
        print(f"DEBUG: update_running_command_display called with: {command}")

        if not hasattr(self.ui, "runningCommandEdit"):
            print(f"DEBUG: runningCommandEdit not found in UI")
            return

        print(f"DEBUG: Found runningCommandEdit widget")

        file_path = self.ui.filePathEdit.text().strip()
        if not file_path:
            print(f"DEBUG: No file path found")
            self.ui.runningCommandEdit.setText("No file selected")
            return

        print(f"DEBUG: File path: {file_path}")

        # Tạo command line string
        cdb_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../tools/debuggers/x64/cdb.exe")
        )
        command_line = f"{cdb_path} -z {file_path} -c {command};q"

        print(f"DEBUG: Command line: {command_line}")

        # Cập nhật QLineEdit
        self.ui.runningCommandEdit.setText(command_line)
        print(f"DEBUG: Updated running command display: {command_line}")

    def clear_running_command_display(self):
        """Xóa hiển thị command đang chạy"""
        if hasattr(self.ui, "runningCommandEdit"):
            self.ui.runningCommandEdit.setText("Ready to run CDB commands...")

    def clear_previous_results(self):

        print("DEBUG: Clearing UI for new file...")

        # Clear CDB result tabs (chỉ UI, không xóa files)
        if hasattr(self, "cdb_results_tabwidget") and self.cdb_results_tabwidget:
            self.cdb_results_tabwidget.clear()
            print("DEBUG: Cleared CDB result tabs")

        # Clear running command display
        self.clear_running_command_display()

        # Clear custom command input
        if hasattr(self.ui, "customCommandEdit"):
            self.ui.customCommandEdit.clear()
            print("DEBUG: Cleared custom command input")

        # Clear custom commands list
        self.custom_commands = []

        # KHÔNG clear current_results_dir - để giữ reference đến files cũ
        # self.current_results_dir = None  # BỎ DÒNG NÀY

        print("DEBUG: UI cleared successfully (files preserved)")

    def create_cdb_result_tab(self, command, tab_title):
        """Tạo tab mới để hiển thị kết quả CDB"""
        from PyQt5.QtWidgets import QTextEdit, QTabWidget

        # Luôn sử dụng cdb_results_tabwidget nếu đã có
        if hasattr(self, "cdb_results_tabwidget") and self.cdb_results_tabwidget:
            target_tabwidget = self.cdb_results_tabwidget
        else:
            # Sử dụng crashAnalysisTabWidget từ UI file
            if hasattr(self.ui, "crashAnalysisTabWidget"):
                target_tabwidget = self.ui.crashAnalysisTabWidget
                # Đặt tab position thành ngang
                target_tabwidget.setTabPosition(QTabWidget.North)
                print(
                    f"DEBUG: Using existing crashAnalysisTabWidget with horizontal tabs"
                )
            else:
                # Fallback: tạo mới QTabWidget với tab ngang
                target_tabwidget = QTabWidget()
                target_tabwidget.setTabPosition(QTabWidget.North)  # Tab ngang ở trên
                print(f"DEBUG: Created new QTabWidget with horizontal tabs")

                # Thêm vào crashDumpLayout nếu có
                if hasattr(self.ui, "crashDumpLayout"):
                    self.ui.crashDumpLayout.addWidget(target_tabwidget)
                    print(f"DEBUG: Added to crashDumpLayout")
                else:
                    # Fallback: thêm vào window chính
                    self.layout().addWidget(target_tabwidget)
                    print(f"DEBUG: Added to main layout")

        # Kiểm tra tab đã tồn tại chưa
        for i in range(target_tabwidget.count()):
            if target_tabwidget.tabText(i) == tab_title:
                target_tabwidget.setCurrentIndex(i)
                print(f"DEBUG: Tab '{tab_title}' already exists, switching to it")
                return i  # Tab đã tồn tại, return index

        # Tạo tab mới
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(
            """
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 16px;
                padding: 10px;
                line-height: 1.4;
            }
        """
        )

        # Thêm tab
        tab_index = target_tabwidget.addTab(text_edit, tab_title)
        target_tabwidget.setCurrentIndex(tab_index)
        print(f"DEBUG: Created new tab '{tab_title}' at index {tab_index}")

        # Lưu reference đến TabWidget
        self.cdb_results_tabwidget = target_tabwidget

        return tab_index

    def run_basic_cdb_analysis(self):
        """Chạy phân tích CDB cơ bản với các lệnh mặc định"""
        # Sửa lệnh - thêm dấu ! cho analyze
        basic_commands = ["version", "lm", "k", "!analyze -v", "vertarget"]

        file_path = self.ui.filePathEdit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "No File", "Please select a valid crash dump file."
            )
            return

        # Tạo thư mục kết quả
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = os.path.abspath(
            os.path.join(
                "analysis_results", f"{os.path.basename(file_path)}_{timestamp}"
            )
        )
        os.makedirs(results_dir, exist_ok=True)
        self.current_results_dir = results_dir

        try:
            self.ui.statusLabel.setText("Status: Running basic CDB analysis...")
            self.append_log("Starting basic CDB analysis...")
            print("DEBUG: Starting CDB analysis with commands:", basic_commands)

            # Chạy từng lệnh và hiển thị kết quả
            for i, command in enumerate(basic_commands):
                print(f"DEBUG: Running command {i+1}/{len(basic_commands)}: {command}")
                self.run_single_cdb_command(command, results_dir)
                print(f"DEBUG: Completed command {i+1}: {command}")

            # Lưu vào database
            ev_type = self.detect_evidence_type(file_path)
            # Normalize file path để tránh path mismatch
            normalized_file_path = os.path.normpath(file_path)
            print(
                f"DEBUG: Saving to database - File: {normalized_file_path}, Type: {ev_type}, Tool: CDB, Result: {results_dir}"
            )
            self.db.save_analysis_result(
                normalized_file_path,
                ev_type,
                tool_used="CDB",
                result_path=results_dir,
                summary="Basic CDB analysis completed",
            )
            print(f"DEBUG: Database save completed")

            self.ui.statusLabel.setText("Status: Basic CDB analysis completed")
            self.append_log("Basic CDB analysis completed.")
            print("DEBUG: CDB analysis completed successfully")

        except Exception as e:
            error_msg = f"CDB analysis failed: {str(e)}"
            self.ui.statusLabel.setText(f"Status: {error_msg}")
            self.append_log(error_msg)
            print(f"DEBUG: CDB analysis failed: {error_msg}")
            QMessageBox.warning(self, "CDB Analysis Error", error_msg)

    def run_single_cdb_command(self, command, results_dir=None):
        """Chạy 1 lệnh CDB và hiển thị kết quả"""
        print(f"DEBUG: run_single_cdb_command called with: {command}")

        file_path = self.ui.filePathEdit.text().strip()
        if not file_path or not os.path.exists(file_path):
            print(f"DEBUG: File not found: {file_path}")
            return

        if not results_dir:
            results_dir = self.current_results_dir or os.path.abspath(
                "analysis_results"
            )

        try:
            print(f"DEBUG: Creating tab for command: {command}")

            # Cập nhật hiển thị command đang chạy
            self.update_running_command_display(command)

            # Tạo tab title
            if command == "!analyze -v":
                tab_title = "Crash Information"
            elif command == "version":
                tab_title = "Version"
            elif command == "lm":
                tab_title = "Loaded Modules"
            elif command == "k":
                tab_title = "Kernel Info"
            elif command == "vertarget":
                tab_title = "Vertical Target"
            else:
                tab_title = command

            # Tạo tab nếu chưa có
            tab_index = self.create_cdb_result_tab(command, tab_title)
            print(f"DEBUG: Tab created with index: {tab_index}")

            # Lấy text edit widget
            if hasattr(self, "cdb_results_tabwidget") and self.cdb_results_tabwidget:
                text_edit = self.cdb_results_tabwidget.widget(tab_index)

                # Hiển thị "Running..."
                text_edit.setText(f"Running command: {command}\nPlease wait...")
                self.cdb_results_tabwidget.setCurrentIndex(tab_index)
                print(f"DEBUG: Set 'Running...' message for command: {command}")

                # Chạy command
                print(f"DEBUG: About to call run_cdb_single_command for: {command}")
                result = self.run_cdb_single_command(file_path, command)
                print(
                    f"DEBUG: run_cdb_single_command returned, length: {len(result) if result else 0}"
                )

                # Hiển thị kết quả
                text_edit.setText(result)
                print(f"DEBUG: Set result text for command: {command}")

                # Xóa hiển thị command đang chạy
                self.clear_running_command_display()

                # Lưu kết quả vào file
                safe_command = command.replace("!", "").replace(" ", "_")
                result_file = os.path.join(results_dir, f"cdb_{safe_command}.txt")
                with open(result_file, "w", encoding="utf-8") as f:
                    f.write(result)
                print(f"DEBUG: Saved result to file: {result_file}")

                self.append_log(f"Completed command: {command}")

        except Exception as e:
            error_msg = f"Error running {command}: {str(e)}"
            print(f"DEBUG: Exception in run_single_cdb_command: {error_msg}")
            if hasattr(self, "cdb_results_tabwidget") and self.cdb_results_tabwidget:
                text_edit = self.cdb_results_tabwidget.widget(tab_index)
                text_edit.setText(f"Error: {error_msg}")
            self.append_log(error_msg)
            # Xóa hiển thị command đang chạy khi có lỗi
            self.clear_running_command_display()

    def run_cdb_single_command(self, crash_dump_path: str, command: str) -> str:
        """Chạy 1 lệnh CDB và trả về kết quả dạng string"""
        import subprocess
        import os

        print(f"DEBUG: run_cdb_single_command called with: {command}")

        # Đường dẫn đến CDB.exe trong thư mục tools
        cdb_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../tools/debuggers/x64/cdb.exe")
        )

        print(f"DEBUG: CDB path: {cdb_path}")

        if not os.path.exists(cdb_path):
            print(f"DEBUG: CDB not found at {cdb_path}")
            # Thử tìm CDB trong Windows SDK hoặc WinDbg
            possible_paths = [
                r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe",
                r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x86\cdb.exe",
                r"C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe",
                r"C:\Program Files\Windows Kits\10\Debuggers\x86\cdb.exe",
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    cdb_path = path
                    print(f"DEBUG: Found CDB at: {cdb_path}")
                    break
            else:
                error_msg = (
                    f"Error: CDB.exe not found. Please install Windows SDK or WinDbg."
                )
                print(f"DEBUG: {error_msg}")
                return error_msg

        if not os.path.exists(crash_dump_path):
            error_msg = f"Error: Crash dump file not found: {crash_dump_path}"
            print(f"DEBUG: {error_msg}")
            return error_msg

        try:
            print(f"DEBUG: Starting CDB execution...")

            # Set working directory to debuggers folder để CDB tìm được DLLs
            debuggers_dir = os.path.dirname(cdb_path)

            # Chạy CDB trực tiếp
            cmd = [
                cdb_path,
                "-z",
                crash_dump_path,  # -z để mở crash dump
                "-c",
                f"{command};q",
            ]

            print(f"DEBUG: Running CDB command: {' '.join(cmd)}")
            print(f"DEBUG: Working directory: {debuggers_dir}")
            print(f"DEBUG: CDB path exists: {os.path.exists(cdb_path)}")
            print(f"DEBUG: Crash dump exists: {os.path.exists(crash_dump_path)}")

            print(f"DEBUG: About to call subprocess.run...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=debuggers_dir,  # Set working directory
            )
            print(f"DEBUG: subprocess.run completed!")

            print(f"DEBUG: CDB return code: {result.returncode}")
            print(f"DEBUG: CDB stdout length: {len(result.stdout)}")
            print(f"DEBUG: CDB stderr length: {len(result.stderr)}")

            # Kết hợp stdout và stderr
            output = result.stdout + "\n" + result.stderr
            print(f"DEBUG: Combined output length: {len(output)}")

            # Clean up output
            lines = output.split("\n")
            cleaned_lines = []

            # Bỏ qua các dòng không cần thiết
            skip_patterns = [
                "Copyright (c) Microsoft Corporation",
                "Loading Dump File",
                "Symbol search path is:",
                "Executable search path is:",
                "Loading Kernel Symbols",
                "Loading User Symbols",
                "PEB is paged out",
                "Loading unloaded module list",
                "For analysis of this file, run !analyze -v",
                "cdb: Reading initial command",
                "quit:",
                "NatVis script unloaded",
                "************* Preparing the environment",
                ">>>>>>>>>>>>> Preparing the environment",
                "************* Waiting for Debugger Extensions",
                ">>>>>>>>>>>>> Waiting for Debugger Extensions",
                "ExtensionRepository :",
                "UseExperimentalFeatureForNugetShare :",
                "AllowNugetExeUpdate :",
                "NonInteractiveNuget :",
                "AllowNugetMSCredentialProviderInstall :",
                "AllowParallelInitializationOfLocalRepositories :",
                "EnableRedirectToV8JsProvider :",
                "-- Configuring repositories",
                "-----> Repository :",
                "Packages count:",
                "Extension DLL search Path:",
                "Extension DLL chain:",
                "wdfkd: image",
                "ELFBinComposition: image",
                "dbghelp: image",
                "exts: image",
                "kext: image",
                "kdexts: image",
            ]

            for line in lines:
                # Kiểm tra xem dòng có chứa pattern cần bỏ không
                should_skip = False
                for pattern in skip_patterns:
                    if pattern in line:
                        should_skip = True
                        break

                # Nếu không phải dòng cần bỏ thì thêm vào
                if not should_skip and line.strip():
                    cleaned_lines.append(line)

            # Trả về output đã clean up
            final_output = "\n".join(cleaned_lines)
            print(f"DEBUG: Final cleaned output length: {len(final_output)}")

            # Nếu không có output sau khi clean up, trả về debug info
            if not final_output.strip():
                final_output = f"DEBUG INFO:\nCDB Path: {cdb_path}\nCrash Dump: {crash_dump_path}\nCommand: {command}\nReturn Code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                print(f"DEBUG: No output after cleanup, returning debug info")

            print(f"DEBUG: Returning final output")
            return final_output

        except subprocess.TimeoutExpired:
            error_msg = f"Error: Command '{command}' timed out. CDB may need more time to analyze large crash dumps."
            print(f"DEBUG: {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"Error running command '{command}': {str(e)}\n\nDEBUG INFO:\nCDB Path: {cdb_path}\nCrash Dump: {crash_dump_path}"
            print(f"DEBUG: Exception: {error_msg}")
            return error_msg

    def load_cdb_results(self, results_dir: str):
        """Load kết quả CDB từ thư mục results"""
        import os

        print(f"DEBUG: load_cdb_results called with: {results_dir}")
        print(f"DEBUG: Directory exists: {os.path.exists(results_dir)}")

        if not os.path.exists(results_dir):
            print(f"DEBUG: CDB results directory does not exist!")
            return

        # Tìm tất cả file .txt trong thư mục results
        files_found = []
        for filename in os.listdir(results_dir):
            if filename.startswith("cdb_") and filename.endswith(".txt"):
                files_found.append(filename)
                print(f"DEBUG: Found CDB file: {filename}")

                # Extract command name từ filename
                command = filename[4:-4].replace(
                    "_", " "
                )  # Remove "cdb_" prefix and ".txt" suffix
                print(f"DEBUG: Extracted command: {command}")

                # Đọc nội dung file
                file_path = os.path.join(results_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    print(
                        f"DEBUG: Read file {filename}, content length: {len(content)}"
                    )

                    # Tạo tab title
                    if command == "analyze -v":
                        tab_title = "Crash Information"
                    elif command == "version":
                        tab_title = "Version"
                    elif command == "lm":
                        tab_title = "Loaded Modules"
                    elif command == "k":
                        tab_title = "Kernel Info"
                    elif command == "vertarget":
                        tab_title = "Vertical Target"
                    else:
                        tab_title = command

                    print(f"DEBUG: Tab title: {tab_title}")

                    # Tạo tab và hiển thị kết quả
                    tab_index = self.create_cdb_result_tab(command, tab_title)
                    if (
                        hasattr(self, "cdb_results_tabwidget")
                        and self.cdb_results_tabwidget
                    ):
                        text_edit = self.cdb_results_tabwidget.widget(tab_index)
                        text_edit.setText(content)
                        print(f"DEBUG: Set content to tab {tab_index}")

                except Exception as e:
                    print(f"Error loading CDB result {filename}: {e}")

        print(f"DEBUG: Total CDB files found: {len(files_found)}")

        # Hiển thị tab đầu tiên nếu có
        if (
            hasattr(self, "cdb_results_tabwidget")
            and self.cdb_results_tabwidget
            and self.cdb_results_tabwidget.count() > 0
        ):
            self.cdb_results_tabwidget.setCurrentIndex(0)
            print(f"DEBUG: Set current tab to index 0")
        else:
            print(f"DEBUG: No CDB tabs created")

        # Chỉ set 100% nếu thực sự có kết quả phân tích
        if files_found:
            self.ui.progressBar.setValue(100)
        else:
            self.ui.progressBar.setValue(0)


# Để sử dụng: tạo instance MemoryAnalysisWindow() và show() trong main app
