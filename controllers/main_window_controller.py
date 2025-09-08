# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QMessageBox, QMenu, QAction
from PyQt5.QtCore import pyqtSignal, QTimer, Qt, QPoint, QObject
from PyQt5.QtGui import QCursor
from datetime import datetime
import os

from views.main_window_ui import Ui_MainWindow
from controllers.case_management import Case
from controllers.user_management import UserManagement
from controllers.dashboard import Dashboard
from controllers.collect.volatile.volatile import Volatile
from controllers.collect.nonvolatile.nonvolatile import NonVolatilePage
from controllers.analysis.memory_analysis import MemoryAnalysisWindow
from controllers.analysis.registry_analysis import RegistryAnalysis
from controllers.analysis.browser_analysis import BrowserAnalysis
from controllers.analysis.file_analysis import FileAnalysis
from controllers.analysis.metadata_analysis import MetadataAnalysis
from controllers.analysis.eventlog_analysis import EventlogAnalysis
from controllers.report.report import Report
from models.db_manager import DatabaseManager


class MainController(QObject):
    """Main controller for the application - handles business logic and coordinates between view and models"""

    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Create main window
        from PyQt5.QtWidgets import QMainWindow
        self.main_window = QMainWindow()
        self.view = Ui_MainWindow()
        self.view.setupUi(self.main_window)
        self.current_case_id = None
        self.opened_windows = {}

        # Setup UI elements first
        self._setup_ui_elements()

        # Setup connections
        self._setup_connections()
        self._setup_menu_buttons()
        self._setup_initial_state()

    def _setup_connections(self):
        """Setup signal connections"""
        # Tab management
        self.view.tabWidget.setTabsClosable(True)
        self.view.tabWidget.tabCloseRequested.connect(self.close_tab)
        self.view.tabWidget.currentChanged.connect(self.on_tab_changed)

        # Menu buttons
        menu_buttons = self.get_menu_buttons()
        for button in menu_buttons.keys():
            button.clicked.connect(self.show_selected_window)

        # User label
        self.view.user_label.mousePressEvent = self.user_label_clicked

        # Timer for timestamp
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)

        # Initial updates
        self.update_timestamp()
        self.update_user_info()

    def _setup_menu_buttons(self):
        """Setup menu buttons dictionary"""
        self.menu_btns_list = {
            self.view.dashboard_btn: ("Dashboard", lambda: Dashboard()),
            self.view.case_btn: ("Quản lý vụ án", lambda: Case(main_window=self)),
            self.view.user_management_btn: ("User Management", lambda: UserManagement()),
            self.view.volatile_btn: ("Volatile", lambda: Volatile()),
            self.view.nonvolatile_btn: ("Thu thập dữ liệu bất biến", lambda: NonVolatilePage()),
            self.view.memory_btn: ("Phân tích bộ nhớ", lambda: MemoryAnalysisWindow()),
            self.view.registry_btn: ("Registry", lambda: RegistryAnalysis(main_window=self)),
            self.view.browser_btn: ("Browser", lambda: BrowserAnalysis(main_window=self)),
            self.view.file_btn: ("File", lambda: FileAnalysis(main_window=self)),
            self.view.metadata_btn: ("Metadata", lambda: MetadataAnalysis()),
            self.view.eventlog_btn: ("Event Log", lambda: EventlogAnalysis()),
            self.view.report_btn: ("Report", lambda: Report(main_window=self)),
        }

    def _setup_initial_state(self):
        """Setup initial application state"""
        # Setup UI styling
        self._setup_ui_styling()
        self.show_case_management_window()

    def _setup_ui_styling(self):
        """Setup UI styling and appearance"""
        from PyQt5.QtWidgets import QSizePolicy

        # Tab widget styling
        self.view.tabWidget.tabBar().setElideMode(Qt.ElideNone)
        self.view.tabWidget.tabBar().setUsesScrollButtons(True)
        self.view.tabWidget.setStyleSheet("""
        QTabWidget::pane {
            border: 1px solid #ddd;
            background-color: white;
        }

        QTabBar::tab {
            background-color: #ecf0f1;
            padding: 6px 12px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            color: #2c3e50;
            font-size: 14px;
            font-family: "Segoe UI", "Arial", sans-serif;
            min-width: 120px;
        }

        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 2px solid #3498db;
            color: #3498db;
        }

        QTabBar::tab:hover {
            background-color: #dfe6e9;
        }

        QTabBar::close-button {
            subcontrol-position: right;
            margin-left: 8px;
        }
        """)

        self.view.tabWidget.tabBar().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_ui_elements(self):
        """Setup UI elements and references"""
        # Menu buttons
        self.view.dashboard_btn = self.view.pushButton
        self.view.case_btn = self.view.pushButton_2
        self.view.user_management_btn = self.view.pushButton_3
        self.view.volatile_btn = self.view.pushButton_4
        self.view.nonvolatile_btn = self.view.pushButton_5
        self.view.memory_btn = self.view.pushButton_6
        self.view.registry_btn = self.view.pushButton_7
        self.view.browser_btn = self.view.pushButton_8
        self.view.file_btn = self.view.pushButton_9
        self.view.metadata_btn = self.view.pushButton_10
        self.view.eventlog_btn = self.view.pushButton_11
        self.view.report_btn = self.view.pushButton_14

        # Other UI elements
        self.view.user_label = self.view.user_label
        self.view.timestamp_label = self.view.timestamp_label
        self.view.username_label = self.view.username_label

        # Splitter
        self.view.splitter.setSizes([130, 900])

    def get_tab_widget(self):
        """Get tab widget for controller to manage"""
        return self.view.tabWidget

    def get_menu_buttons(self):
        """Get all menu buttons for controller"""
        return {
            self.view.dashboard_btn: "Dashboard",
            self.view.case_btn: "Quản lý vụ án",
            self.view.user_management_btn: "User Management",
            self.view.volatile_btn: "Volatile",
            self.view.nonvolatile_btn: "Thu thập dữ liệu bất biến",
            self.view.memory_btn: "Phân tích bộ nhớ",
            self.view.registry_btn: "Registry",
            self.view.browser_btn: "Browser",
            self.view.file_btn: "File",
            self.view.metadata_btn: "Metadata",
            self.view.eventlog_btn: "Event Log",
            self.view.report_btn: "Report",
        }

    def show_main_window(self):
        """Show the main window"""
        self.main_window.showMaximized()

    def get_or_create_window(self, key, widget_factory):
        """Get or create window instance to avoid re-creation"""
        if key not in self.opened_windows:
            self.opened_windows[key] = widget_factory()
        return self.opened_windows[key]

    def show_case_management_window(self):
        """Show case management window as default"""
        key = self.view.case_btn
        title, factory = self.menu_btns_list[key]

        is_open, index = self.open_tab_flag(title)
        self.set_btn_checked(self.view.case_btn)

        if is_open:
            self.view.tabWidget.setCurrentIndex(index)
        else:
            widget = self.get_or_create_window(title, factory)
            curIndex = self.view.tabWidget.addTab(widget, title)
            self.view.tabWidget.setCurrentIndex(curIndex)
            self.view.tabWidget.setVisible(True)

    def show_selected_window(self):
        """Handle showing selected window"""
        sender_btn = self.sender()

        # Check if case is required
        require_case = {
            self.view.volatile_btn,
            self.view.nonvolatile_btn,
            self.view.memory_btn,
            self.view.registry_btn,
            self.view.browser_btn,
            self.view.file_btn,
            self.view.metadata_btn,
            self.view.eventlog_btn,
        }
        if sender_btn in require_case and not self.current_case_id:
            QMessageBox.warning(
                self.main_window,
                "Cảnh báo",
                "Vui lòng chọn một case trước khi thực hiện thao tác này!",
            )
            return

        if (
            sender_btn
            and isinstance(sender_btn, type(self.view.dashboard_btn))
            and sender_btn in self.menu_btns_list
        ):
            title, factory = self.menu_btns_list[sender_btn]

            is_open, index = self.open_tab_flag(title)
            self.set_btn_checked(sender_btn)

            if is_open:
                self.view.tabWidget.setCurrentIndex(index)
            else:
                # Special handling for volatile/nonvolatile
                if sender_btn in {self.view.nonvolatile_btn, self.view.volatile_btn}:
                    try:
                        widget = self.get_or_create_window(title, lambda: factory().__class__(main_window=self))
                    except Exception:
                        widget = self.get_or_create_window(title, factory)
                else:
                    widget = self.get_or_create_window(title, factory)
                curIndex = self.view.tabWidget.addTab(widget, title)
                self.view.tabWidget.setCurrentIndex(curIndex)
                self.view.tabWidget.setVisible(True)

        # Special handling for browser analysis
        if sender_btn == self.view.browser_btn and self.current_case_id:
            current_tab_index = self.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.view.tabWidget.widget(current_tab_index)
                if current_widget and hasattr(current_widget, "load_case_data"):
                    current_widget.load_case_data(self.current_case_id)

    def switch_to_browser_analysis_tab(self, case_id=None):
        """Switch to browser analysis tab and set case_id"""
        self.view.browser_btn.click()

        def set_case_data():
            current_tab_index = self.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.view.tabWidget.widget(current_tab_index)
                if (
                    current_widget
                    and isinstance(current_widget, BrowserAnalysis)
                    and hasattr(current_widget, "load_case_data")
                ):
                    if case_id:
                        current_widget.load_case_data(case_id)

        QTimer.singleShot(100, set_case_data)

    def switch_to_memory_analysis_tab(self, case_id=None):
        """Switch to memory analysis tab and set case_id"""
        self.view.memory_btn.click()

        def set_case_data():
            current_tab_index = self.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.view.tabWidget.widget(current_tab_index)
                if (
                    current_widget
                    and isinstance(current_widget, MemoryAnalysisWindow)
                    and hasattr(current_widget, "load_case_data")
                ):
                    if case_id:
                        current_widget.load_case_data(case_id)

        QTimer.singleShot(100, set_case_data)

    def switch_to_volatile_tab(self, case_id=None):
        """Switch to volatile tab and set case data"""
        self.view.volatile_btn.click()

        def set_case_data():
            current_tab_index = self.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.view.tabWidget.widget(current_tab_index)

                if (
                    current_widget
                    and hasattr(current_widget, "set_case_data")
                    and case_id
                ):
                    db = DatabaseManager()
                    db.connect()
                    case_info = db.get_case_with_investigator(case_id)
                    if case_info:
                        case_data = {
                            "case_id": case_id,
                            "case_name": case_info["title"],
                            "investigator": case_info.get("full_name", "Unknown"),
                            "created_date": case_info.get("created_at", ""),
                            "archive_path": case_info.get("archive_path", ""),
                        }
                        current_widget.set_case_data(case_data)
                elif (
                    current_widget
                    and hasattr(current_widget, "set_case_id")
                    and case_id
                ):
                    current_widget.set_case_id(case_id)

        QTimer.singleShot(100, set_case_data)

    def switch_to_nonvolatile_tab(self, case_id=None):
        """Switch to non-volatile tab and set case data"""
        self.view.nonvolatile_btn.click()

        def set_case_data():
            current_tab_index = self.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.view.tabWidget.widget(current_tab_index)

                if (
                    current_widget
                    and hasattr(current_widget, "set_case_data")
                    and case_id
                ):
                    db = DatabaseManager()
                    db.connect()
                    case_info = db.get_case_with_investigator(case_id)
                    if case_info:
                        case_data = {
                            "case_id": case_id,
                            "case_name": case_info["title"],
                            "investigator": case_info.get("full_name", "Unknown"),
                            "created_date": case_info.get("created_at", ""),
                            "archive_path": case_info.get("archive_path", ""),
                        }
                        current_widget.set_case_data(case_data)
                elif (
                    current_widget
                    and hasattr(current_widget, "set_case_id")
                    and case_id
                ):
                    current_widget.set_case_id(case_id)

        QTimer.singleShot(100, set_case_data)

    def switch_to_file_analysis_tab(self, case_id=None, evidence_path=None):
        """Switch to file analysis tab and load evidence if provided"""
        if case_id:
            self.current_case_id = case_id

        self.view.file_btn.click()

        def set_data():
            current_tab_index = self.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.view.tabWidget.widget(current_tab_index)
                if current_widget and isinstance(current_widget, FileAnalysis):
                    if case_id and hasattr(current_widget, "load_case_data"):
                        try:
                            current_widget.load_case_data(case_id)
                        except Exception:
                            pass
                    if evidence_path and os.path.exists(evidence_path):
                        try:
                            current_widget.load_evidence_file(evidence_path)
                        except Exception:
                            pass

        QTimer.singleShot(150, set_data)

    def close_tab(self, index):
        """Close tab"""
        self.view.tabWidget.removeTab(index)

        if self.view.tabWidget.count() == 0:
            self.view.toolBox.setCurrentIndex(0)
            self.set_btn_checked(self.view.case_btn)
            self.show_case_management_window()

    def set_btn_checked(self, btn):
        """Set button checked state"""
        menu_buttons = self.get_menu_buttons()
        for button in menu_buttons.keys():
            if button != btn:
                button.setChecked(False)
            else:
                button.setChecked(True)

    def open_tab_flag(self, tab_title):
        """Check if tab is already open"""
        for i in range(self.view.tabWidget.count()):
            if self.view.tabWidget.tabText(i) == tab_title:
                return True, i
        return False, -1

    def on_tab_changed(self, index):
        """Handle tab change"""
        if index < 0 or index >= self.view.tabWidget.count():
            return

        current_tab_title = self.view.tabWidget.tabText(index)
        menu_buttons = self.get_menu_buttons()

        button_found = False
        for button, title in menu_buttons.items():
            if title == current_tab_title:
                self.set_btn_checked(button)
                button_found = True
                self.expand_section_for_button(button)
                break

        if not button_found:
            for button in menu_buttons.keys():
                button.setChecked(False)

    def expand_section_for_button(self, target_button):
        """Expand section for button"""
        for i in range(self.view.toolBox.count()):
            page = self.view.toolBox.widget(i)
            if page:
                for child in page.findChildren(type(self.view.dashboard_btn)):
                    if child == target_button:
                        self.view.toolBox.setCurrentIndex(i)
                        return

    def update_timestamp(self):
        """Update timestamp"""
        try:
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.view.timestamp_label.setText(f"🕒 {current_time}")
        except:
            pass

    def update_user_info(self, full_name="Administrator"):
        """Update user info"""
        try:
            self.view.username_label.setText(f"{full_name}")
        except:
            self.view.username_label.setText("Guest")

    def set_current_user(self, user_data):
        """Set current user data"""
        if user_data and "full_name" in user_data:
            self.update_user_info(user_data["full_name"])
        elif user_data and "username" in user_data:
            self.update_user_info(user_data["username"])
        else:
            self.update_user_info("Guest")

        if user_data and "role" in user_data:
            self.view.user_management_btn.setVisible(user_data["role"] == "ADMIN")
        else:
            self.view.user_management_btn.setVisible(False)

    def user_label_clicked(self, ev):
        """Handle user label click"""
        menu = QMenu(self.main_window)
        menu.setStyleSheet("""
        QMenu {
            background-color: white;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            padding: 8px;
            font-size: 14px;
        }
        QMenu::item {
            padding: 8px 20px;
            border-radius: 4px;
            margin: 2px;
        }
        QMenu::item:selected {
            background-color: #edf2f7;
            color: #2d3748;
        }
        """)

        profile_action = QAction("👤 Thông tin tài khoản", self.view)
        profile_action.triggered.connect(self.show_user_profile)

        change_password_action = QAction("🔑 Đổi mật khẩu", self.view)
        change_password_action.triggered.connect(self.show_change_password)

        menu.addSeparator()

        settings_action = QAction("⚙️ Cài đặt", self.view)
        settings_action.triggered.connect(self.show_settings_dialog)

        logout_action = QAction("🚪 Đăng xuất", self.view)
        logout_action.triggered.connect(self.confirm_logout)

        menu.addAction(profile_action)
        menu.addAction(change_password_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addAction(logout_action)

        menu.exec_(QCursor.pos())

    def show_user_profile(self):
        """Show user profile"""
        QMessageBox.information(
            self.main_window,
            "👤 Thông tin tài khoản",
            "📋 Thông tin người dùng:\n\n"
            "🆔 Tên đăng nhập: admin\n"
            "👨‍💼 Vai trò: Quản trị viên hệ thống\n"
            "🏢 Phòng ban: Điều tra số\n"
            "📅 Đăng nhập lần cuối: Hôm nay\n"
            "🔐 Quyền hạn: Toàn quyền\n\n"
            "💡 Để thay đổi thông tin, vui lòng liên hệ quản trị viên!",
        )

    def show_change_password(self):
        """Show change password dialog"""
        QMessageBox.information(
            self.main_window,
            "🔑 Đổi mật khẩu",
            "Tính năng đổi mật khẩu đang được phát triển.\n\n"
            "📞 Để đổi mật khẩu, vui lòng liên hệ:\n"
            "👨‍💻 Quản trị viên hệ thống\n"
            "📱 Số điện thoại: 0357857581\n"
            "🕐 Thời gian hỗ trợ: 8:00 - 17:00 (T2-T6)\n\n"
            "🔒 Vì lý do bảo mật, việc đổi mật khẩu cần xác thực qua admin.",
        )

    def show_settings_dialog(self):
        """Show settings dialog"""
        QMessageBox.information(
            self.main_window,
            "⚙️ Cài đặt hệ thống",
            "Tính năng cài đặt hệ thống đang được phát triển.\n\n"
            "Các tùy chọn sẽ bao gồm:\n"
            "• 🎨 Giao diện và theme\n"
            "• 🗄️ Cấu hình cơ sở dữ liệu\n"
            "• 📁 Đường dẫn lưu trữ\n"
            "• 🔐 Cài đặt bảo mật\n"
            "• 📊 Tùy chọn báo cáo\n\n"
            "Vui lòng đợi phiên bản tiếp theo!",
        )

    def confirm_logout(self):
        """Confirm logout"""
        reply = QMessageBox.question(
            self.main_window,
            "Xác nhận đăng xuất",
            "Bạn có chắc chắn muốn đăng xuất không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.logout_requested.emit()

    def closeEvent(self, event):
        """Handle close event"""
        reply = QMessageBox.question(
            self.main_window,
            "Xác nhận đăng xuất",
            "Bạn có chắc chắn muốn thoát ứng dụng không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.logout_requested.emit()
            event.accept()
        else:
            event.ignore()

    def switch_to_case_tab(self, case_id=None):
        """Switch to case tab and select case if case_id provided"""
        self.view.tabWidget.setCurrentWidget(self.case_page)

        if case_id and hasattr(self.case_page, "ui"):
            table = self.case_page.ui.casesTable
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == case_id:
                    table.selectRow(row)
                    break
