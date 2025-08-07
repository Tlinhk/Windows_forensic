import os
from pydoc import visiblename
import subprocess
import mimetypes
import webbrowser
from datetime import datetime, timedelta

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
import csv
from PyQt5.QtWidgets import (
    QWidget,
    QMessageBox,
    QTreeWidgetItem,
    QFileDialog,
    QHBoxLayout,
    QScrollArea,
)
from PyQt5.QtCore import QMetaEnum, Qt
from PyQt5.QtWidgets import QTableWidgetItem
from ui.pages.analysis_ui.browser_analysis_ui import Ui_BrowserAnalysisWindow
from database.db_manager import DatabaseManager
from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QMessageBox,
    QMenu,
    QInputDialog,
)
from PyQt5.QtGui import QBrush, QColor


class BrowserAnalysis(QWidget):
    def __init__(self, main_window=None):
        super(BrowserAnalysis, self).__init__()
        self.ui = Ui_BrowserAnalysisWindow()
        self.ui.setupUi(self)

        self.main_window = main_window
        self.current_case_id = None
        self.db = DatabaseManager()
        self.db.connect()
        self.ui.browseProfileButton.clicked.connect(self.browse_path)
        self.ui.startAnalysisButton.clicked.connect(self.start_analysis)
        self.ui.cacheTable.cellDoubleClicked.connect(self.show_cache_properties)
        self.ui.historyTable.cellDoubleClicked.connect(self.show_history_properties)
        self.ui.cookiesTable.cellDoubleClicked.connect(self.show_cookies_properties)
        self.ui.cacheFilterCombo.currentIndexChanged.connect(self.filter_by_type)
        self.ui.cacheSearchEdit.textChanged.connect(self.filter_cache_combined)
        self.ui.cacheTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.cacheTable.customContextMenuRequested.connect(
            self.show_cache_context_menu
        )
        self.ui.pushButton_3.clicked.connect(self.extract_cache_files)
        self.ui.historySearchEdit.textChanged.connect(self.filter_history_combined)
        self.ui.historyTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.historyTable.customContextMenuRequested.connect(
            self.show_history_context_menu
        )
        self.ui.historyFilterCombo.currentIndexChanged.connect(
            self.on_history_filter_changed
        )
        self.ui.cookiesSearchEdit.textChanged.connect(self.filter_cookies_combined)
        self.ui.treeWidget.currentItemChanged.connect(self.on_current_item_changed)

    def on_current_item_changed(self, current, previous):
        if current:
            self.ui.profilePathEdit.setText(current.text(3))
            top = current
            while top.parent() is not None:
                top = top.parent()
            browser_name = top.text(0)
            idx = self.ui.browserTypeCombo.findText(browser_name, Qt.MatchContains)
            if idx != -1:
                self.ui.browserTypeCombo.setCurrentIndex(idx)

            self.ui.cacheCheckBox.setChecked(False)
            self.ui.historyCheckBox.setChecked(False)
            self.ui.cookiesCheckBox.setChecked(False)
            self.ui.downloadsCheckBox.setChecked(False)

            path = current.text(3).lower()
            if "cache" in path:
                self.ui.cacheCheckBox.setChecked(True)
            elif "history" in path:
                self.ui.historyCheckBox.setChecked(True)
            elif "cookies" in path:
                self.ui.cookiesCheckBox.setChecked(True)
            elif "downloads" in path:
                self.ui.downloadsCheckBox.setChecked(True)

    def filter_by_type(self, index):
        self.filter_cache_combined()

    def filter_cookies_combined(self):
        keyword = self.ui.cookiesSearchEdit.text().strip().lower()
        headers = self.cookies_headers
        data = self.cookies_data
        table = self.ui.cookiesTable
        headers_lower = [h.lower() for h in self.cookies_headers]
        # Xác định cột Domain/Host và Name
        try:
            domain_idx = headers_lower.index("host name")
            name_idx = headers_lower.index("name")
        except ValueError:
            # nếu tiêu đề khác, in ra headers để debug
            print("Cookies headers:", self.cookies_headers)
            domain_idx = name_idx = None

        # Lọc
        filtered = []
        for row in data:
            text_to_search = ""
            if domain_idx is not None and domain_idx < len(row):
                text_to_search += row[domain_idx].lower()
            if name_idx is not None and name_idx < len(row):
                text_to_search += row[name_idx].lower()
            if keyword in text_to_search:
                filtered.append(row)

        # Cập nhật bảng
        table.setRowCount(len(filtered))
        for r, row_vals in enumerate(filtered):
            for c, cell in enumerate(row_vals):
                table.setItem(r, c, QTableWidgetItem(cell))

        self.update_cookies_count()

    def on_history_filter_changed(self, idx):
        """
        idx:
        0=All Time, 1=Today, 2=Last 7 Days, 3=Last 30 Days, 4=Custom Range
        """
        tbl = self.ui.historyTable
        today = datetime.now().date()

        if idx == 0:
            start_date = end_date = None
        elif idx == 1:
            start_date = end_date = today
        elif idx == 2:
            start_date = today - timedelta(days=7)
            end_date = today
        elif idx == 3:
            start_date = today - timedelta(days=30)
            end_date = today
        else:
            # ask user for a custom date range
            txt, ok = QInputDialog.getText(
                self,
                "Custom Range",
                "Enter start and end dates (dd/MM/yyyy - dd/MM/yyyy):",
            )
            if not ok or "-" not in txt:
                return
            s, e = [d.strip() for d in txt.split("-", 1)]
            try:
                start_date = datetime.strptime(s, "%d/%m/%Y").date()
                end_date = datetime.strptime(e, "%d/%m/%Y").date()
            except ValueError:
                return
        # find the “Visited On” column index
        headers = [tbl.horizontalHeaderItem(c).text() for c in range(tbl.columnCount())]
        date_col = None

        if "Visited On" in headers:
            date_col = headers.index("Visited On")

        elif "Last Visit Date" in headers:
            date_col = headers.index("Last Visit Date")

        else:
            return
        # iterate rows
        for r in range(tbl.rowCount()):
            item = tbl.item(r, date_col)
            if not item or item.text().upper().startswith("N/A"):
                tbl.setRowHidden(r, False)
                continue
            # parse only the date portion
            raw = item.text().split()[0]
            try:
                dt = datetime.strptime(raw, "%d/%m/%Y").date()
            except ValueError:
                tbl.setRowHidden(r, False)
                continue

            # decide visibility
            if start_date and end_date:
                show = start_date <= dt <= end_date
            else:
                show = True

            tbl.setRowHidden(r, not show)
        self.update_history_count()

    def show_history_context_menu(self, pos):
        table = self.ui.historyTable
        item = table.itemAt(pos)
        if not item:
            return

        row = item.row()
        # find the URL column index (assuming header text is "URL")
        headers = [
            table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
        ]
        try:
            url_idx = headers.index("URL")
        except ValueError:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy cột URL.")
            return

        url = table.item(row, url_idx).text()
        if not url:
            QMessageBox.warning(self, "Lỗi", "Không có URL để mở.")
            return

        menu = QMenu(self)
        open_action = menu.addAction("🌐 Open Link In Web Browser")
        chosen = menu.exec_(table.viewport().mapToGlobal(pos))
        if chosen == open_action:
            webbrowser.open(url)

    def filter_history_combined(self):
        keyword = self.ui.historySearchEdit.text().strip().lower()
        headers = self.history_headers
        data = self.history_data
        table = self.ui.historyTable
        headers_lower = [h.lower() for h in self.history_headers]
        # Xác định cột URL và Title
        try:
            url_idx = headers_lower.index("url")
            title_idx = headers_lower.index("title")
        except ValueError:
            # nếu tiêu đề khác, in ra headers để debug
            print("History headers:", self.history_headers)
            url_idx = title_idx = None

        # Lọc
        filtered = []
        for row in data:
            text_to_search = ""
            if url_idx is not None and url_idx < len(row):
                text_to_search += row[url_idx].lower()
            if title_idx is not None and title_idx < len(row):
                text_to_search += row[title_idx].lower()
            if keyword in text_to_search:
                filtered.append(row)

        # Cập nhật bảng
        table.setRowCount(len(filtered))
        for r, row_vals in enumerate(filtered):
            for c, cell in enumerate(row_vals):
                table.setItem(r, c, QTableWidgetItem(cell))

        self.update_history_count()

    def extract_cache_files(self):
        from PyQt5.QtWidgets import QFileDialog

        # 1) phải chạy Analyze để có cache_output_dir
        if not hasattr(self, "cache_output_dir"):
            QMessageBox.warning(self, "Lỗi", "Bạn hãy chạy Analyze trước.")
            return
        cache_path = self.ui.profilePathEdit.text().strip()
        if not os.path.isdir(cache_path):
            QMessageBox.warning(self, "Lỗi", "Thư mục cache không hợp lệ.")
            return
        # 2) tạo sẵn thư mục extracted_cache_files bên trong cache_output_dir
        default_out_dir = os.path.join(self.cache_output_dir, "extracted_cache_files")
        os.makedirs(default_out_dir, exist_ok=True)

        # 3) Mở Folder Picker, bắt đầu ở default_out_dir, cho phép đổi tên/tạo mới
        out_dir = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục lưu kết quả",
            self.cache_output_dir,
            QFileDialog.ShowDirsOnly,
        )
        if not out_dir:
            # User bấm Cancel
            return

        browser = self.ui.browserTypeCombo.currentText().lower()
        if "firefox" in browser:
            exe_path = os.path.abspath("tools/mzcacheview/MZCacheView.exe")
        else:
            exe_path = os.path.abspath("tools/chromecacheview/ChromeCacheView.exe")
        if not os.path.exists(exe_path):
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không tìm thấy: {exe_path}",
            )
            return

        try:
            subprocess.run(
                [
                    exe_path,
                    "-folder",
                    cache_path,
                    "/copycache",
                    "",
                    "",
                    "/CopyFilesFolder",
                    out_dir,
                    "/UseWebSiteDirStructure",
                    "0",
                ],
                check=True,
            )
            QMessageBox.information(
                self,
                "Thành công",
                f"Đã trích xuất cache của {browser.title()} vào:\n{out_dir}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi khi trích xuất", str(e))

    def show_cache_context_menu(self, pos):
        from PyQt5.QtWidgets import QMenu, QMessageBox
        import subprocess

        table = self.ui.cacheTable
        item = table.itemAt(pos)
        if not item:
            return

        row = item.row()
        headers = [
            table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
        ]
        row_data = {headers[i]: table.item(row, i).text() for i in range(len(headers))}

        filename = row_data.get("Filename")
        if not filename:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy tên file cache.")
            return

        # Tìm đường dẫn file thật
        search_root = os.path.join(self.cache_output_dir, "extracted_cache_files")
        matching_file = None
        for root, _, files in os.walk(search_root):
            for f in files:
                if f == filename or f.startswith(filename):
                    matching_file = os.path.join(root, f)
                    break
            if matching_file:
                break

        if not matching_file or not os.path.exists(matching_file):
            QMessageBox.warning(
                self,
                "Chưa extract cache",
                f"Extract files để trích xuất cache trước khi mở file",
            )
            return

        # Hiển thị menu chuột phải
        menu = QMenu(self)
        open_action = menu.addAction("🗂 Open Selected Cache File")
        open_with_action = menu.addAction(" 📂Open Selected Cache File With...")
        selected_action = menu.exec_(table.viewport().mapToGlobal(pos))

        try:
            if selected_action == open_action:
                os.startfile(matching_file)  # Mở với chương trình mặc định

            elif selected_action == open_with_action:
                subprocess.Popen(
                    ["rundll32", "shell32.dll,OpenAs_RunDLL", matching_file]
                )  # Hiển thị Open With
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở file: {str(e)}")

    def filter_cache_combined(self):
        keyword = self.ui.cacheSearchEdit.text().strip().lower()
        selected_type = self.ui.cacheFilterCombo.currentText()
        table = self.ui.cacheTable

        if not hasattr(self, "cache_data") or not hasattr(self, "cache_headers"):
            return

        try:
            type_idx = self.cache_headers.index("Content Type")
            name_idx = self.cache_headers.index("Filename")
        except ValueError:
            return

        def matches_type(ct, group):
            group = (group or "").strip().lower()
            if group == "all types":
                return True
            if not ct:
                return False
            ct = ct.strip().lower()
            if group == "images":
                return ct.startswith("image/")
            elif group == "scripts":
                return ct in [
                    "application/javascript",
                    "application/x-javascript",
                    "text/javascript",
                ]
            elif group == "stylesheets":
                return ct == "text/css"
            elif group == "documents":
                return ct in ["text/html", "application/pdf"]
            elif group == "fonts":
                return ct.startswith("font/")
            return False

        filtered = []
        for row in self.cache_data:
            if len(row) <= max(type_idx, name_idx):
                continue
            content_type = row[type_idx]
            filename = row[name_idx].lower()

            if matches_type(content_type, selected_type) and keyword in filename:
                filtered.append(row)

        # Cập nhật bảng
        table.setRowCount(len(filtered))
        table.setColumnCount(len(self.cache_headers))
        table.setHorizontalHeaderLabels(self.cache_headers)

        for row_idx, row_data in enumerate(filtered):
            for col_idx, cell in enumerate(row_data):
                table.setItem(row_idx, col_idx, QTableWidgetItem(cell))

        # Cập nhật số lượng
        self.update_cache_count()

    def update_cache_count(self):
        row_count = self.ui.cacheTable.rowCount()
        self.ui.label_4.setText(f"Tổng số lượng cache: {row_count}")

    def update_history_count(self):
        table = self.ui.historyTable
        visible = sum(not table.isRowHidden(r) for r in range(table.rowCount()))
        self.ui.label_3.setText(f"Tổng số lượng history: {visible}")

    def show_cookies_properties(self, row, column):
        table = self.ui.cookiesTable
        headers = [
            table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
        ]
        entry = {}
        for col in range(table.columnCount()):
            key = headers[col]
            value = table.item(row, col).text() if table.item(row, col) else ""
            entry[key] = value

        dialog = EntryDialog(entry, self)
        dialog.exec_()

    def show_cache_properties(self, row, column):
        table = self.ui.cacheTable
        headers = [
            table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
        ]

        entry = {}
        for col in range(table.columnCount()):
            key = headers[col]
            value = table.item(row, col).text() if table.item(row, col) else ""
            entry[key] = value

        dialog = EntryDialog(entry, self)
        dialog.exec_()

    def show_history_properties(self, row, column):
        table = self.ui.historyTable
        headers = [
            table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
        ]

        entry = {}
        for col in range(table.columnCount()):
            key = headers[col]
            value = table.item(row, col).text() if table.item(row, col) else ""
            entry[key] = value

        dialog = EntryDialog(entry, self)
        dialog.exec_()

    def start_analysis(self):
        browser = self.ui.browserTypeCombo.currentText().lower()
        do_cache = self.ui.cacheCheckBox.isChecked()
        do_history = self.ui.historyCheckBox.isChecked()
        do_downloads = self.ui.downloadsCheckBox.isChecked()
        do_cookies = self.ui.cookiesCheckBox.isChecked()
        if not any([do_cache, do_history, do_downloads, do_cookies]):
            QMessageBox.warning(
                self, "Chưa chọn mục nào", "Hãy chọn ít nhất một mục để phân tích."
            )
            return
        # chạy lần lượt từng mục
        if do_cache:
            if browser.lower() in ("google chrome", "microsoft edge"):
                self.analyze_chrome_edge_cache()
            elif browser.lower() in ("mozilla firefox"):
                self.analyze_firefox_cache()
            else:
                QMessageBox.information(
                    self, "Chưa hỗ trợ", f"Cache của {browser} chưa được xử lý"
                )
        if do_history:
            if browser.lower() in ("google chrome", "microsoft edge"):
                self.analyze_chrome_edge_history()
            elif browser.lower() in ("mozilla firefox"):
                self.analyze_firefox_history()
            else:
                QMessageBox.information(
                    self, "Chưa hỗ trợ", f"History của {browser} chưa được xử lý"
                )
        if do_cookies:
            if browser.lower() in ("google chrome", "microsoft edge"):
                self.analyze_chrome_edge_cookies()
            elif browser.lower() in ("mozilla firefox"):
                self.analyze_firefox_cookies()
            else:
                QMessageBox.information(
                    self, "Chưa hỗ trợ", f"Cookies của {browser} chưa được xử lý"
                )

    def analyze_chrome_edge_cookies(self):
        profile_path = self.ui.profilePathEdit.text().strip()
        cookie_file = os.path.join(profile_path, "Network", "Cookies")
        if not os.path.exists(cookie_file):
            QMessageBox.warning(
                self, "Lỗi", f"Không tìm thấy file Cookies:\n{cookie_file}"
            )
            return
        # File đầu ra
        print(f"[Cookies] Start: {cookie_file}")
        b = self.ui.browserTypeCombo.currentText().lower()
        if "chrome" in b:
            browser_type = "chrome"
        elif "edge" in b:
            browser_type = "edge"
        else:
            browser_type = b.replace(" ", "_")
        # Tạo thư mục output
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_dir = os.path.join(
            os.getcwd(), "analysis_results", f"{browser_type}_cookies_{timestamp}"
        )
        os.makedirs(out_dir, exist_ok=True)
        output_csv = os.path.join(out_dir, f"{browser_type}_cookies.csv")
        self.cookies_output_dir = out_dir

        # Đường dẫn đến ChromeCookiesView.exe trong thư mục tools/
        exe = os.path.abspath("tools/chromecookiesview-x64/ChromeCookiesView.exe")
        if not os.path.exists(exe):
            QMessageBox.critical(self, "Lỗi", f"Không tìm thấy:\n{exe}")
            return

        try:
            subprocess.run(
                [
                    exe,
                    "/CookiesFile",
                    cookie_file,
                    "/sort",
                    "Host Name",
                    "/scomma",
                    output_csv,
                ],
                check=True,
            )
        except Exception as e:
            print(f"[Cookies] Error: {e}")
            QMessageBox.critical(self, "Lỗi chạy ChromeCookiesView", str(e))
            return
        print(f"[Cookies] Done, output at {output_csv}")
        self.load_cookies_results(output_csv, delimiter=",")

    def analyze_firefox_cookies(self):
        profile_path = self.ui.profilePathEdit.text().strip()
        cookie_file = os.path.join(profile_path, "cookies.sqlite")
        if not os.path.exists(cookie_file):
            QMessageBox.warning(
                self, "Lỗi", f"Không tìm thấy file cookies.sqlite:\n{cookie_file}"
            )
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_dir = os.path.join(
            os.getcwd(), "analysis_results", f"firefox_cookies_{timestamp}"
        )
        os.makedirs(out_dir, exist_ok=True)
        output_csv = os.path.join(out_dir, "firefox_cookies.tsv")
        self.cookies_output_dir = out_dir

        exe = os.path.abspath("tools/mzcv-x64/mzcv.exe")
        if not os.path.exists(exe):
            QMessageBox.critical(self, "Lỗi", f"Không tìm thấy:\n{exe}")
            return

        try:
            subprocess.run(
                [exe, "/stab", output_csv, "-cookiesfile", cookie_file, "/nosort"],
                check=True,
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chạy MZCookiesView", str(e))
            return
        # --- CHỖ NÀY: tự thêm header vào đầu file TSV ---
        headers = [
            "Host Name",
            "Path",
            "Name",
            "Value",
            "Expiration Date",
            "Secure",
            "Domain Access",
            "Line/ID",
            "Last Accessed",
            "Created Time",
        ]
        with open(output_csv, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        with open(output_csv, "w", encoding="utf-8", errors="ignore") as f:
            f.write("\t".join(headers) + "\n")
            f.writelines(lines)
        self.load_cookies_results(output_csv, delimiter="\t")

    def load_cookies_results(self, csv_path, delimiter=","):
        if not os.path.exists(csv_path):
            QMessageBox.warning(
                self, "Không có dữ liệu", f"Không tìm thấy file kết quả:\n{csv_path}"
            )
            return

        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

        if not rows:
            QMessageBox.information(self, "Trống", "Không có dữ liệu cookie.")
            return

        headers = rows[0]
        data_rows = rows[1:]
        self.cookies_headers = headers
        self.cookies_data = data_rows

        table = self.ui.cookiesTable
        table.clear()
        table.setColumnCount(len(headers))
        table.setRowCount(len(data_rows))
        table.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(data_rows):
            for c, cell in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(cell))

        self.ui.mainTabWidget.setCurrentWidget(self.ui.cookiesTab)
        self.filter_cookies_combined()

    def update_cookies_count(self):
        row_count = self.ui.cookiesTable.rowCount()
        self.ui.label_5.setText(f"Tổng số lượng cookies: {row_count}")

    def analyze_firefox_history(self):
        import datetime

        history_path = self.ui.profilePathEdit.text().strip()

        if not os.path.exists(history_path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file history.")
            return

        browser_type = "firefox"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(
            os.getcwd(), "analysis_results", f"{browser_type}_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)

        output_csv = os.path.join(output_dir, f"{browser_type}_history_output.csv")
        self.history_output_dir = output_dir
        # Đường dẫn đến ChromeCacheView.exe (bạn nên để trong thư mục project, ví dụ: tools/)
        mozilla_history_view_path = os.path.abspath(
            "tools/mozillahistoryview-x64/MozillaHistoryView.exe"
        )

        if not os.path.exists(mozilla_history_view_path):
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không tìm thấy MozillaHistoryView.exe tại:\n{mozilla_history_view_path}",
            )
            return

        # Gọi ChromeCacheView
        try:
            subprocess.run(
                [
                    mozilla_history_view_path,
                    "-file",
                    history_path,
                    "/scomma",
                    output_csv,
                ],
                check=True,
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chạy MozillaHistoryView", str(e))
            return
        # Load kết quả CSV
        self.load_history_results(output_csv)

    def analyze_chrome_edge_history(self):
        import datetime

        history_path = self.ui.profilePathEdit.text().strip()

        if not os.path.exists(history_path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file history.")
            return

        # File đầu ra
        b = self.ui.browserTypeCombo.currentText().lower()
        if "chrome" in b:
            browser_type = "chrome"
        elif "edge" in b:
            browser_type = "edge"
        else:
            browser_type = b.replace(" ", "_")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(
            os.getcwd(), "analysis_results", f"{browser_type}_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)

        output_csv = os.path.join(output_dir, f"{browser_type}_history_output.csv")
        self.history_output_dir = output_dir
        # Đường dẫn đến ChromeCacheView.exe (bạn nên để trong thư mục project, ví dụ: tools/)
        chrome_history_view_path = os.path.abspath(
            "tools/chromehistoryview/ChromeHistoryView.exe"
        )

        if not os.path.exists(chrome_history_view_path):
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không tìm thấy ChromeHistoryView.exe tại:\n{chrome_history_view_path}",
            )
            return

        # Gọi ChromeCacheView
        try:
            subprocess.run(
                [
                    chrome_history_view_path,
                    "/UseHistoryFile",
                    "1",
                    "/HistoryFile",
                    history_path,
                    "/scomma",
                    output_csv,
                ],
                check=True,
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chạy ChromeHistoryView", str(e))
            return
        # Load kết quả CSV
        self.load_history_results(output_csv)

    def load_history_results(self, csv_path):
        if not os.path.exists(csv_path):
            QMessageBox.warning(
                self, "Không có dữ liệu", f"Không tìm thấy file kết quả: {csv_path}"
            )
            return

        with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            QMessageBox.information(self, "Trống", "Không có dữ liệu history.")
            return

        headers = rows[0]
        data_rows = rows[1:]
        # Lưu vào bộ nhớ để filter
        self.history_headers = headers
        self.history_data = data_rows

        # Tạo bảng
        table = self.ui.historyTable
        table.clear()
        table.setColumnCount(len(headers))
        table.setRowCount(len(data_rows))
        table.setHorizontalHeaderLabels(headers)

        for row_idx, row_data in enumerate(data_rows):
            for col_idx, cell in enumerate(row_data):
                table.setItem(row_idx, col_idx, QTableWidgetItem(cell))

        self.ui.mainTabWidget.setCurrentWidget(self.ui.historyTab)
        self.filter_history_combined()

    def analyze_firefox_cache(self):
        import datetime

        cache_path = self.ui.profilePathEdit.text().strip()

        if not os.path.isdir(cache_path):
            QMessageBox.warning(self, "Lỗi", "Thư mục cache không hợp lệ.")
            return
        browser_type = "firefox"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(
            os.getcwd(), "analysis_results", f"{browser_type}_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)
        output_csv = os.path.join(output_dir, f"{browser_type}_cache_output.csv")
        self.cache_output_dir = output_dir
        # Đường dẫn đến FirefoxCacheView.exe (bạn nên để trong thư mục project, ví dụ: tools/)
        firefox_cacheview_path = os.path.abspath("tools/mzcacheview/MZCacheView.exe")
        if not os.path.exists(firefox_cacheview_path):
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không tìm thấy MZCacheView.exe tại:\n{firefox_cacheview_path}",
            )
            return
        try:
            subprocess.run(
                [firefox_cacheview_path, "-folder", cache_path, "/scomma", output_csv],
                check=True,
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chạy MZCacheView", str(e))
            return
        # load CSV vào table chung
        self.load_cache_results(output_csv)

    def analyze_chrome_edge_cache(self):
        import datetime

        cache_path = self.ui.profilePathEdit.text().strip()

        if not os.path.isdir(cache_path):
            QMessageBox.warning(self, "Lỗi", "Thư mục cache không hợp lệ.")
            return

        # File đầu ra
        b = self.ui.browserTypeCombo.currentText().lower()
        if "chrome" in b:
            browser_type = "chrome"
        elif "edge" in b:
            browser_type = "edge"
        else:
            browser_type = b.replace(" ", "_")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(
            os.getcwd(), "analysis_results", f"{browser_type}_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)

        output_csv = os.path.join(output_dir, f"{browser_type}_cache_output.csv")
        self.cache_output_dir = output_dir
        # Đường dẫn đến ChromeCacheView.exe (bạn nên để trong thư mục project, ví dụ: tools/)
        chrome_cacheview_path = os.path.abspath(
            "tools/chromecacheview/chromecacheview.exe"
        )

        if not os.path.exists(chrome_cacheview_path):
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không tìm thấy chromecacheview.exe tại:\n{chrome_cacheview_path}",
            )
            return

        # Gọi ChromeCacheView
        try:
            subprocess.run(
                [chrome_cacheview_path, "-folder", cache_path, "/scomma", output_csv],
                check=True,
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chạy ChromeCacheView", str(e))
            return
        # Load kết quả CSV
        self.load_cache_results(output_csv)

    def load_cache_results(self, csv_path):
        if not os.path.exists(csv_path):
            QMessageBox.warning(
                self, "Không có dữ liệu", f"Không tìm thấy file kết quả: {csv_path}"
            )
            return

        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            QMessageBox.information(self, "Trống", "Không có dữ liệu cache.")
            return

        headers = rows[0]
        data_rows = rows[1:]
        # Lưu vào bộ nhớ để filter
        self.cache_headers = headers
        self.cache_data = data_rows

        # Tạo bảng
        table = self.ui.cacheTable
        table.clear()
        table.setColumnCount(len(headers))
        table.setRowCount(len(data_rows))
        table.setHorizontalHeaderLabels(headers)

        for row_idx, row_data in enumerate(data_rows):
            for col_idx, cell in enumerate(row_data):
                table.setItem(row_idx, col_idx, QTableWidgetItem(cell))

        self.ui.mainTabWidget.setCurrentWidget(self.ui.cacheTab)
        self.filter_cache_combined()

    def browse_path(self):
        # Tạo QMessageBox với các nút tùy chỉnh
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Chọn loại đường dẫn")
        msg_box.setText("📂 Bạn muốn chọn tệp hay thư mục?")
        msg_box.setIcon(QMessageBox.Question)

        file_button = msg_box.addButton("📄 Chọn Tệp", QMessageBox.ActionRole)
        folder_button = msg_box.addButton("📁 Chọn Thư Mục", QMessageBox.ActionRole)
        cancel_button = msg_box.addButton("❌ Huỷ", QMessageBox.RejectRole)

        msg_box.exec_()

        clicked = msg_box.clickedButton()
        # 2) Lấy thư mục mặc định (lần chọn trước hoặc cwd)
        default_dir = getattr(self, "last_browse_dir", os.getcwd())

        if clicked == file_button:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Chọn tệp evidence", default_dir, "Tất cả các tệp (*)"
            )
            if file_path:
                self.ui.profilePathEdit.setText(file_path)
                self.last_browse_dir = os.path.dirname(file_path)

        elif clicked == folder_button:
            folder_path = QFileDialog.getExistingDirectory(
                self, "Chọn thư mục evidence", default_dir, QFileDialog.ShowDirsOnly
            )
            if folder_path:
                self.ui.profilePathEdit.setText(folder_path)
                self.last_browse_dir = folder_path
        else:
            return

    def load_case_data(self, case_id):
        """Load case data and populate browser evidence tree"""
        self.current_case_id = case_id
        self.ui.treeWidget.clear()
        if not case_id:
            return
        try:
            # Lấy tất cả artifact của case
            artifacts = self.db.get_artifacts_by_case(case_id)
            # Lọc evidence trình duyệt - kiểm tra cả evidence_type, name và source_path
            browser_keywords = ["chrome", "firefox", "edge", "ie", "browser", "safari"]
            browser_artifacts = [
                a
                for a in artifacts
                if (
                    a.get("evidence_type")
                    and any(k in a["evidence_type"].lower() for k in browser_keywords)
                )
                or (
                    a.get("name")
                    and any(k in a["name"].lower() for k in browser_keywords)
                )
                or (
                    a.get("source_path")
                    and any(k in a["source_path"].lower() for k in browser_keywords)
                )
            ]
            if not browser_artifacts:
                root_item = QTreeWidgetItem(self.ui.treeWidget)
                root_item.setText(0, "Không có evidence trình duyệt cho case này")
                return

            # Nhóm theo browser type
            browser_groups = {}
            for artifact in browser_artifacts:
                etype = artifact.get("evidence_type", "Unknown")
                name = artifact.get("name", "Unknown")
                source_path = artifact.get("source_path", "Unknown")
                # Lấy tên browser từ evidence_type, name hoặc source_path
                browser_type = "Unknown"
                for k in browser_keywords:
                    if (
                        k in etype.lower()
                        or k in name.lower()
                        or k in source_path.lower()
                    ):
                        browser_type = k.capitalize()
                        break
                if browser_type not in browser_groups:
                    browser_groups[browser_type] = []
                browser_groups[browser_type].append(artifact)

            # Tạo tree: browser -> evidence path
            for browser_type, artifacts in browser_groups.items():
                browser_item = QTreeWidgetItem(self.ui.treeWidget)
                browser_item.setText(0, f"{browser_type}")
                browser_item.setBackground(0, QBrush(QColor(200, 220, 240)))

                # Nhóm theo đường dẫn evidence
                path_groups = {}
                for artifact in artifacts:
                    source_path = artifact.get("source_path", "")
                    if source_path:
                        # Lấy thư mục gốc của evidence
                        if os.path.isdir(source_path):
                            root_path = source_path
                        else:
                            root_path = os.path.dirname(source_path)

                        if root_path not in path_groups:
                            path_groups[root_path] = []
                        path_groups[root_path].append(artifact)

                # Tạo tree từ đường dẫn evidence
                for root_path, artifacts in path_groups.items():
                    if os.path.exists(root_path):
                        # Tạo item cho thư mục gốc
                        root_item = QTreeWidgetItem(browser_item)
                        root_item.setText(0, os.path.basename(root_path))
                        root_item.setText(1, "Evidence Path")
                        root_item.setText(2, "")
                        root_item.setText(3, root_path)

                        # Mở rộng cấu trúc thư mục
                        self._add_folder_structure(root_item, root_path, max_depth=3)
                    else:
                        # Nếu đường dẫn không tồn tại, hiển thị artifact trực tiếp
                        for artifact in artifacts:
                            art_item = QTreeWidgetItem(browser_item)
                            art_item.setText(0, artifact.get("name", "Unknown"))
                            art_item.setText(1, artifact.get("evidence_type", ""))
                            size = artifact.get("size")
                            if size is not None:
                                art_item.setText(2, self._format_size(size))
                            else:
                                art_item.setText(2, "?")
                            art_item.setText(3, artifact.get("source_path", ""))

            self.ui.treeWidget.collapseAll()
            self.ui.treeWidget.expandToDepth(0)

            for i in range(self.ui.treeWidget.topLevelItemCount()):
                root = self.ui.treeWidget.topLevelItem(i)
                root.setBackground(0, QBrush(QColor(200, 220, 240)))

        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Lỗi khi load evidence trình duyệt: {str(e)}"
            )

    def _add_folder_structure(
        self, parent_item, folder_path, max_depth=3, current_depth=0
    ):
        """Add folder structure to tree, simplified version"""
        if current_depth >= max_depth:
            return
        try:
            items = os.listdir(folder_path)
            folders = []
            files = []

            for item in items:
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path):
                    folders.append(item)
                else:
                    files.append(item)

            # Thêm thư mục trước
            for folder_name in sorted(folders):
                folder_path_full = os.path.join(folder_path, folder_name)
                folder_item = QTreeWidgetItem(parent_item)
                folder_item.setText(0, folder_name)
                folder_item.setText(1, "Folder")
                folder_item.setText(2, "")
                folder_item.setText(3, folder_path_full)

                # Đệ quy thêm nội dung thư mục
                self._add_folder_structure(
                    folder_item, folder_path_full, max_depth, current_depth + 1
                )

            # Thêm file sau
            for file_name in sorted(files):
                file_path_full = os.path.join(folder_path, file_name)
                file_item = QTreeWidgetItem(parent_item)
                file_item.setText(0, file_name)
                file_item.setText(1, "File")
                try:
                    file_size = os.path.getsize(file_path_full)
                    file_item.setText(2, self._format_size(file_size))
                except:
                    file_item.setText(2, "?")
                file_item.setText(3, file_path_full)

        except PermissionError:
            error_item = QTreeWidgetItem(parent_item)
            error_item.setText(0, "Access Denied")
            error_item.setText(1, "Error")
            error_item.setText(2, "")
            error_item.setText(3, "")
        except Exception as e:
            error_item = QTreeWidgetItem(parent_item)
            error_item.setText(0, f"Error: {str(e)}")
            error_item.setText(1, "Error")
            error_item.setText(2, "")
            error_item.setText(3, "")

    def _format_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class EntryDialog(QDialog):
    def __init__(self, entry_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Properties")
        self.setWindowIcon(parent.windowIcon() if parent else None)

        # Thiết lập kích thước và style
        self.setMinimumSize(1000, 700)
        self.setMaximumSize(1400, 900)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            QLabel {
                color: #495057;
                font-size: 12px;
            }
            
                         QLabel[class="label"] {
                 font-weight: bold;
                 color: #495057;
                 background-color: #e3f2fd;
                 padding: 6px 10px;
                 border-left: 3px solid #2196f3;
                 border-radius: 4px;
                 margin-right: 8px;
                 font-size: 13px;
             }
             QLabel[class="value"] {
                 background-color: white;
                 border: 1px solid #dee2e6;
                 border-radius: 4px;
                 padding: 6px 10px;
                 color: #212529;
                 font-family: 'Segoe UI', 'Arial', sans-serif;
                 font-size: 13px;
                 min-height: 20px;
             }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
                         QPushButton:pressed {
                 background-color: #004085;
             }
             QScrollArea {
                 border: none;
                 background-color: transparent;
             }
             QWidget#scrollAreaWidgetContents {
                 background-color: transparent;
             }
             
         """
        )

        # Layout chính
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Scroll area cho nội dung
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Widget chứa nội dung
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(6)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Tạo bảng key-value ngang
        for label, value in entry_dict.items():
            # Container cho mỗi dòng
            row_container = QWidget()
            row_layout = QHBoxLayout(row_container)
            row_layout.setSpacing(8)
            row_layout.setContentsMargins(0, 2, 0, 2)

            # Label (cột trái)
            label_widget = QLabel(f"🔹 {label}:")
            label_widget.setProperty("class", "label")
            label_widget.setMinimumWidth(140)
            label_widget.setMaximumWidth(180)
            label_widget.setWordWrap(True)
            row_layout.addWidget(label_widget)

            # Value (cột phải)
            value_widget = QLabel(value if value else "N/A")
            value_widget.setProperty("class", "value")
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_widget.setWordWrap(True)
            value_widget.setMinimumHeight(22)
            row_layout.addWidget(value_widget)

            # Tỷ lệ 1:3 cho label:value
            row_layout.setStretch(0, 1)  # Label
            row_layout.setStretch(1, 3)  # Value

            content_layout.addWidget(row_container)

        # Thêm content widget vào scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)

        # Spacer để đẩy button về bên phải
        button_layout.addStretch()

        # OK button
        ok_btn = QPushButton("✅ OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        main_layout.addWidget(button_container)

        self.setLayout(main_layout)

        # Đặt focus vào OK button
        ok_btn.setFocus()
