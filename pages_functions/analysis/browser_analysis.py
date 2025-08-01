import os
import subprocess
import mimetypes

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
import csv
from PyQt5.QtWidgets import (
    QWidget,
    QMessageBox,
    QTreeWidgetItem,
    QFileDialog,
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
)


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
        self.ui.cacheFilterCombo.currentIndexChanged.connect(self.filter_by_type)
        self.ui.cacheSearchEdit.textChanged.connect(self.filter_cache_combined)
        self.ui.cacheTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.cacheTable.customContextMenuRequested.connect(
            self.show_cache_context_menu
        )
        self.ui.pushButton_3.clicked.connect(self.extract_cache_files)

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

    def filter_by_type(self):
        self.filter_cache_combined()

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

        dialog = CacheEntryDialog(entry, self)
        dialog.exec_()

    def start_analysis(self):
        browser = self.ui.browserTypeCombo.currentText()
        if browser.lower() in ("google chrome", "microsoft edge"):
            self.analyze_chrome_edge_cache()
        elif browser.lower() in ("mozilla firefox"):
            self.analyze_firefox_cache()
        else:
            QMessageBox.information(
                self, "Chưa hỗ trợ", f"Trình duyệt {browser} chưa được xử lý"
            )

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
            # Tạo tree: browser -> category -> artifact
            for browser_type, artifacts in browser_groups.items():
                browser_item = QTreeWidgetItem(self.ui.treeWidget)
                browser_item.setText(0, f"{browser_type}")
                # Nhóm theo category (history, cookies, cache...)
                category_groups = {}
                for artifact in artifacts:
                    etype = artifact.get("evidence_type", "Unknown")
                    # Tìm category
                    cat = "Other"
                    for c in [
                        "history",
                        "cookie",
                        "cache",
                        "download",
                        "bookmark",
                        "password",
                        "session",
                        "extension",
                        "form",
                    ]:
                        if c in etype.lower():
                            cat = c.capitalize()
                            break
                    if cat not in category_groups:
                        category_groups[cat] = []
                    category_groups[cat].append(artifact)
                for cat, cat_artifacts in category_groups.items():
                    for artifact in cat_artifacts:
                        source_path = artifact.get("source_path", "")
                        # Kiểm tra xem có phải là folder không
                        if os.path.isdir(source_path):
                            self._add_browser_profile_structure(
                                browser_item, source_path
                            )
                        else:
                            cat_item = QTreeWidgetItem(browser_item)
                            cat_item.setText(0, cat)
                            art_item = QTreeWidgetItem(cat_item)
                            art_item.setText(0, artifact.get("name", "Unknown"))
                            art_item.setText(1, artifact.get("evidence_type", ""))
                            size = artifact.get("size")
                            if size is not None:
                                art_item.setText(2, self._format_size(size))
                            else:
                                art_item.setText(2, "?")
                            art_item.setText(3, source_path)
            self.ui.treeWidget.expandAll()
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Lỗi khi load evidence trình duyệt: {str(e)}"
            )

    def _add_browser_profile_structure(self, parent_item, browser_path):
        try:
            items = os.listdir(browser_path)
            profiles = []
            other_items = []
            for item in items:
                item_path = os.path.join(browser_path, item)
                if os.path.isdir(item_path):
                    if (
                        item.lower() == "default"
                        or item.lower().startswith("profile")
                        or item.lower().startswith("user data")
                    ):
                        profiles.append(item)
                    else:
                        other_items.append(item)
            for profile_name in sorted(profiles):
                profile_path = os.path.join(browser_path, profile_name)
                profile_item = QTreeWidgetItem(parent_item)
                profile_item.setText(0, profile_name)
                profile_item.setText(1, "Profile")
                profile_item.setText(2, "")
                profile_item.setText(3, profile_path)
                self._add_folder_contents(
                    profile_item, profile_path, max_depth=2, current_depth=0
                )
            for item_name in sorted(other_items):
                item_path = os.path.join(browser_path, item_name)
                if os.path.isdir(item_path):
                    item_tree_item = QTreeWidgetItem(parent_item)
                    item_tree_item.setText(0, item_name)
                    item_tree_item.setText(1, "Folder")
                    item_tree_item.setText(2, "")
                    item_tree_item.setText(3, item_path)
                    self._add_folder_contents(
                        item_tree_item, item_path, max_depth=2, current_depth=0
                    )
        except Exception as e:
            error_item = QTreeWidgetItem(parent_item)
            error_item.setText(0, f"Error loading profiles: {str(e)}")
            error_item.setText(1, "Error")
            error_item.setText(2, "")
            error_item.setText(3, "")

    def _add_folder_contents(
        self, parent_item, folder_path, max_depth=3, current_depth=0
    ):
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
            for folder_name in sorted(folders):
                folder_path_full = os.path.join(folder_path, folder_name)
                folder_item = QTreeWidgetItem(parent_item)
                folder_item.setText(0, folder_name)
                folder_item.setText(1, "Folder")
                folder_item.setText(2, "")
                folder_item.setText(3, folder_path_full)
                self._add_folder_contents(
                    folder_item, folder_path_full, max_depth, current_depth + 1
                )
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


class CacheEntryDialog(QDialog):
    def __init__(self, entry_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Properties")

        layout = QVBoxLayout()
        grid = QGridLayout()

        for i, (label, value) in enumerate(entry_dict.items()):
            label_widget = QLabel(f"{label}:")
            value_widget = QLabel(value)
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(label_widget, i, 0)
            grid.addWidget(value_widget, i, 1)

        layout.addLayout(grid)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

        self.setLayout(layout)
        self.setMinimumWidth(500)
