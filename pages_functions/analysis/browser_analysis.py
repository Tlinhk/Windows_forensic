import os
from PyQt5.QtWidgets import (
    QWidget,
    QMessageBox,
    QTreeWidgetItem,
)
from PyQt5.QtCore import Qt

from ui.pages.analysis_ui.browser_analysis_ui import Ui_BrowserAnalysisWindow
from database.db_manager import DatabaseManager


class BrowserAnalysis(QWidget):
    def __init__(self, main_window=None):
        super(BrowserAnalysis, self).__init__()
        self.ui = Ui_BrowserAnalysisWindow()
        self.ui.setupUi(self)

        self.main_window = main_window
        self.current_case_id = None
        self.db = DatabaseManager()
        self.db.connect()

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
