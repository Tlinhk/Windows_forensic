from PyQt5.QtWidgets import QApplication, QMainWindow,QMessageBox
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from datetime import datetime


from login_window import LoginWindow
from ui.main_window_ui import Ui_MainWindow
from pages_functions.dashboard import Dashboard
from pages_functions.case_management import Case
from pages_functions.user_management import UserManagement
from pages_functions.collect.volatile.volatile import Volatile
from pages_functions.collect.nonvolatile.nonvolatile import Nonvolatile
from pages_functions.analysis.memory_analysis import MemoryAnalysis
from pages_functions.analysis.registry_analysis import RegistryAnalysis
from pages_functions.analysis.browser_analysis import BrowserAnalysis
from pages_functions.analysis.file_analysis import FileAnalysis
from pages_functions.analysis.metadata_analysis import MetadataAnalysis
from pages_functions.analysis.eventlog_analysis import EventlogAnalysis
from pages_functions.report.report import Report

class MyWindow(QMainWindow):
    logout_requested = pyqtSignal()
    def __init__(self):
        super(MyWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        #self.ui.menu_widget.setMinimumWidth(100)
        #self.ui.toolBox.setMinimumWidth(100)
        self.ui.splitter.setSizes([130, 900])
        ## Get all the objects from the ui
        self.dashboard_btn = self.ui.pushButton
        self.case_btn = self.ui.pushButton_2
        self.user_management_btn = self.ui.pushButton_3
        self.volatile_btn = self.ui.pushButton_4
        self.nonvolatile_btn = self.ui.pushButton_5
        self.memory_btn = self.ui.pushButton_6
        self.registry_btn = self.ui.pushButton_7
        self.browser_btn = self.ui.pushButton_8
        self.file_btn = self.ui.pushButton_9
        self.metadata_btn = self.ui.pushButton_10
        self.eventlog_btn = self.ui.pushButton_11
        self.report_btn = self.ui.pushButton_14
        #self.logout_btn = self.ui.page_8
        self.user_label = self.ui.user_label
        
        # Thêm reference cho timestamp và username labels
        self.timestamp_label = self.ui.timestamp_label
        self.username_label = self.ui.username_label

        # Setup timer cho timestamp
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)  # Update mỗi giây

        # Update timestamp và user info ngay lập tức
        self.update_timestamp()
        self.update_user_info()
        
        
        ## Create dict for menu buttons and tab windows
        
        self.menu_btns_list = {
            self.dashboard_btn: Dashboard(),
            self.case_btn: Case(),
            self.user_management_btn: UserManagement(),
            self.volatile_btn: Volatile(),
            self.nonvolatile_btn: Nonvolatile(),
            self.memory_btn: MemoryAnalysis(),
            self.registry_btn: RegistryAnalysis(),
            self.browser_btn: BrowserAnalysis(),
            self.file_btn: FileAnalysis(),
            self.metadata_btn: MetadataAnalysis(),
            self.eventlog_btn: EventlogAnalysis(),
            self.report_btn: Report(),         
        }
        
        
        ##Show home window when start app
        self.show_case_management_window()
        
        self.ui.tabWidget.setTabsClosable(True)
        self.ui.tabWidget.tabCloseRequested.connect(self.close_tab)
        
        self.dashboard_btn.clicked.connect(self.show_selected_window)
        self.case_btn.clicked.connect(self.show_selected_window)
        self.user_management_btn.clicked.connect(self.show_selected_window)
        self.volatile_btn.clicked.connect(self.show_selected_window)
        self.nonvolatile_btn.clicked.connect(self.show_selected_window)
        self.memory_btn.clicked.connect(self.show_selected_window)
        self.registry_btn.clicked.connect(self.show_selected_window)
        self.browser_btn.clicked.connect(self.show_selected_window)
        self.file_btn.clicked.connect(self.show_selected_window)
        self.metadata_btn.clicked.connect(self.show_selected_window)
        self.eventlog_btn.clicked.connect(self.show_selected_window)
        self.report_btn.clicked.connect(self.show_selected_window)
        
        self.user_label.mousePressEvent = self.user_label_clicked
        #self.logout_btn.clicked.connect(self.confirm_logout)
    
    def switch_to_volatile_tab(self, case_id=None):
        """Chuyển sang tab volatile và set case_id với thông tin case đầy đủ"""
        # Chuyển sang tab volatile
        self.volatile_btn.click()
        
        # Đợi một chút để tab được tạo
        from PyQt5.QtCore import QTimer
        
        def set_case_data():
            # Tìm volatile widget trong tab hiện tại
            current_tab_index = self.ui.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.ui.tabWidget.widget(current_tab_index)
                if hasattr(current_widget, 'set_case_data') and case_id:
                    # Lấy thông tin case đầy đủ từ database
                    from database.db_manager import DatabaseManager
                    db = DatabaseManager()
                    db.connect()
                    
                    case_info = db.get_case_with_investigator(case_id)
                    if case_info:
                        case_data = {
                            'case_id': case_info['case_code'] or f"CASE-{case_id}",
                            'case_name': case_info['title'],
                            'investigator': case_info.get('full_name', 'Unknown'),
                            'created_date': case_info.get('created_at', ''),
                            'archive_path': case_info.get('archive_path', '')
                        }
                        current_widget.set_case_data(case_data)
                elif hasattr(current_widget, 'set_case_id') and case_id:
                    # Fallback cho old method
                    current_widget.set_case_id(case_id)
        
        # Delay để đảm bảo tab đã được tạo
        QTimer.singleShot(100, set_case_data)
        
    def switch_to_nonvolatile_tab(self, case_id=None):
        """Chuyển sang tab non-volatile và set case_id với thông tin case đầy đủ"""
        # Chuyển sang tab non-volatile
        self.nonvolatile_btn.click()
        
        # Đợi một chút để tab được tạo
        from PyQt5.QtCore import QTimer
        
        def set_case_data():
            # Tìm nonvolatile widget trong tab hiện tại
            current_tab_index = self.ui.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = self.ui.tabWidget.widget(current_tab_index)
                if hasattr(current_widget, 'set_case_data') and case_id:
                    # Lấy thông tin case đầy đủ từ database
                    from database.db_manager import DatabaseManager
                    db = DatabaseManager()
                    db.connect()
                    
                    case_info = db.get_case_with_investigator(case_id)
                    if case_info:
                        case_data = {
                            'case_id': case_info['case_code'] or f"CASE-{case_id}",
                            'case_name': case_info['title'],
                            'investigator': case_info.get('full_name', 'Unknown'),
                            'created_date': case_info.get('created_at', ''),
                            'archive_path': case_info.get('archive_path', '')
                        }
                        current_widget.set_case_data(case_data)
                elif hasattr(current_widget, 'set_case_id') and case_id:
                    # Fallback cho old method
                    current_widget.set_case_id(case_id)
        
        # Delay để đảm bảo tab đã được tạo
        QTimer.singleShot(100, set_case_data)
        
    def show_case_management_window(self):
        """
        Function for showing case management window as default
        :return:
        """
        result = self.open_tab_flag(self.case_btn.text())
        self.set_btn_checked(self.case_btn)

        if result[0]:
            self.ui.tabWidget.setCurrentIndex(result[1])
        else:
            title = self.case_btn.text()
            curIndex = self.ui.tabWidget.addTab(Case(), title)
            self.ui.tabWidget.setCurrentIndex(curIndex)
            self.ui.tabWidget.setVisible(True)
            
    def show_dashboard_window(self):
        """
        Function for showing dashboard window
        :return:
        """
        result = self.open_tab_flag(self.dashboard_btn.text())
        self.set_btn_checked(self.dashboard_btn)

        if result[0]:
            self.ui.tabWidget.setCurrentIndex(result[1])
        else:
            title = self.dashboard_btn.text()
            curIndex = self.ui.tabWidget.addTab(Dashboard(), title)
            self.ui.tabWidget.setCurrentIndex(curIndex)
            self.ui.tabWidget.setVisible(True)
        
    def show_selected_window(self):
        """
        Function for showing selected window
        :return:
        """
        button = self.sender()

        result = self.open_tab_flag(button.text())
        self.set_btn_checked(button)

        if result[0]:
            self.ui.tabWidget.setCurrentIndex(result[1])
        else:
            title = button.text()
            curIndex = self.ui.tabWidget.addTab(self.menu_btns_list[button], title)
            self.ui.tabWidget.setCurrentIndex(curIndex)
            self.ui.tabWidget.setVisible(True)

        
    def close_tab(self, index):
        """
        Function for close tab in tabWidget
        :param index: index of tab
        :return:
        """
        self.ui.tabWidget.removeTab(index)

        if self.ui.tabWidget.count() == 0:
            self.ui.toolBox.setCurrentIndex(0)
            self.show_case_management_window()
            
    def set_btn_checked(self, btn):
        """
        Set the status of selected button checked and set other buttons' status unchecked
        :param btn: button object
        :return:
        """
        for button in self.menu_btns_list.keys():
            if button != btn:
                button.setChecked(False)
            else:
                button.setChecked(True)
    def open_tab_flag(self,tab):
        """
        Check if selected window showed or not
        :param tab: tab title
        :return: bool and index
        """
        open_tab_count = self.ui.tabWidget.count()

        for i in range(open_tab_count):
            tab_name = self.ui.tabWidget.tabText(i)
            if tab_name == tab:
                return True, i
            else:
                continue

        return False,
    def user_label_clicked(self, event):
        """Xử lý khi click vào user icon"""
        from PyQt5.QtWidgets import QMenu, QAction
        from PyQt5.QtCore import QPoint
        from PyQt5.QtGui import QCursor
        
        # Tạo context menu
        menu = QMenu(self)
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
        
        # Thêm các action
        profile_action = QAction("👤 Thông tin tài khoản", self)
        profile_action.triggered.connect(self.show_user_profile)
        
        change_password_action = QAction("🔑 Đổi mật khẩu", self)
        change_password_action.triggered.connect(self.show_change_password)
        
        menu.addSeparator()
        
        settings_action = QAction("⚙️ Cài đặt", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        
        logout_action = QAction("🚪 Đăng xuất", self)
        logout_action.triggered.connect(self.confirm_logout)
        
        menu.addAction(profile_action)
        menu.addAction(change_password_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addAction(logout_action)
        
        # Hiển thị menu tại vị trí con trỏ
        menu.exec_(QCursor.pos())
        
    def show_user_profile(self):
        """Hiển thị thông tin tài khoản"""
        QMessageBox.information(
            self,
            "👤 Thông tin tài khoản",
            "📋 Thông tin người dùng:\n\n"
            "🆔 Tên đăng nhập: admin\n"
            "👨‍💼 Vai trò: Quản trị viên hệ thống\n"
            "🏢 Phòng ban: Điều tra số\n"
            "📅 Đăng nhập lần cuối: Hôm nay\n"
            "🔐 Quyền hạn: Toàn quyền\n\n"
            "💡 Để thay đổi thông tin, vui lòng liên hệ quản trị viên!"
        )
    
    def show_change_password(self):
        """Hiển thị dialog đổi mật khẩu"""
        QMessageBox.information(
            self,
            "🔑 Đổi mật khẩu",
            "Tính năng đổi mật khẩu đang được phát triển.\n\n"
            "📞 Để đổi mật khẩu, vui lòng liên hệ:\n"
            "👨‍💻 Quản trị viên hệ thống\n"
            "📱 Số điện thoại: 0357857581\n"
            "🕐 Thời gian hỗ trợ: 8:00 - 17:00 (T2-T6)\n\n"
            "🔒 Vì lý do bảo mật, việc đổi mật khẩu cần xác thực qua admin."
        )
        
    def show_settings_dialog(self):
        """Hiển thị dialog cài đặt hệ thống"""
        from PyQt5.QtWidgets import QMessageBox
        
        QMessageBox.information(
            self,
            "⚙️ Cài đặt hệ thống",
            "Tính năng cài đặt hệ thống đang được phát triển.\n\n"
            "Các tùy chọn sẽ bao gồm:\n"
            "• 🎨 Giao diện và theme\n"
            "• 🗄️ Cấu hình cơ sở dữ liệu\n"
            "• 📁 Đường dẫn lưu trữ\n"
            "• 🔐 Cài đặt bảo mật\n"
            "• 📊 Tùy chọn báo cáo\n\n"
            "Vui lòng đợi phiên bản tiếp theo!"
        )
    def update_timestamp(self):
        """Update timestamp mỗi giây"""
        try:
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.timestamp_label.setText(f"🕒 {current_time}")
        except:
            pass

    def update_user_info(self, full_name="Administrator"):
        """Update user information"""
        try:
            self.username_label.setText(f"👋 {full_name}")
        except:
            self.username_label.setText("👋 Guest")

    def set_current_user(self, user_data):
        """Set current user data"""
        if user_data and 'full_name' in user_data:
            self.update_user_info(user_data['full_name'])
        elif user_data and 'username' in user_data:
            self.update_user_info(user_data['username'])
        else:
            self.update_user_info("Guest")
    
    def switch_mode(self, mode):
        """Chuyển đổi giữa collection mode và investigation mode"""
        self.current_mode = mode
        self.set_mode_visibility(mode)
        
    def set_mode_visibility(self, mode):
        """Ẩn/hiện các menu button theo mode"""
        if mode == 'collection':
            # Hiện collection buttons
            for btn in self.collection_buttons:
                btn.setVisible(True)
                
            # Ẩn investigation buttons (trừ dashboard và case management)
            buttons_to_hide = [
                self.user_management_btn,
                self.memory_btn,
                self.registry_btn,
                self.browser_btn,
                self.file_btn,
                self.metadata_btn,
                self.eventlog_btn,
                self.report_btn
            ]
            for btn in buttons_to_hide:
                btn.setVisible(False)
                
            # Update toolbox tab titles
            self.ui.toolBox.setItemText(0, "📊 Thu thập dữ liệu")
                
        elif mode == 'investigation':
            # Hiện investigation buttons
            for btn in self.investigation_buttons:
                btn.setVisible(True)
                
            # Ẩn collection buttons (trừ dashboard)
            buttons_to_hide = [
                self.volatile_btn,
                self.nonvolatile_btn
            ]
            for btn in buttons_to_hide:
                btn.setVisible(False)
                
            # Update toolbox tab titles  
            self.ui.toolBox.setItemText(0, "🔍 Điều tra & phân tích")
    
    def confirm_logout(self):
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Xác nhận đăng xuất", "Bạn có chắc chắn muốn đăng xuất không?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logout_requested.emit()
    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Xác nhận đăng xuất", "Bạn có chắc chắn muốn thoát ứng dụng không?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logout_requested.emit()
            event.accept()
        else:
            event.ignore()
    
    def switch_to_case_tab(self, case_id=None):
        """Chuyển đến tab Case Management và chọn case nếu có case_id"""
        # Chuyển đến tab Case Management
        self.ui.tabWidget.setCurrentWidget(self.case_page)
        
        # Nếu có case_id, tìm và chọn case đó trong bảng
        if case_id and hasattr(self.case_page, 'ui'):
            table = self.case_page.ui.casesTable
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == case_id:
                    table.selectRow(row)
                    break


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    # Biến global để giữ reference main window
    main_window = None
    
    # Hiển thị login window trước
    login_window = LoginWindow()
    
    def show_main_window():
        """Hiển thị main window sau khi đăng nhập thành công"""
        global main_window
        login_window.hide()
        main_window = MyWindow()
        
        # Lấy thông tin user thực tế từ login
        user_data = login_window.get_logged_in_user()
        if user_data:
            # Import db để set current user
            from database.db_manager import db
            db.set_current_user(user_data['user_id'])
            main_window.set_current_user(user_data)
        
        main_window.showMaximized()
        
        # Kết nối signal logout từ main window
        main_window.logout_requested.connect(show_login_window)
        
        # Hiển thị Welcome Dialog sau khi main window ready
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(500, show_welcome_dialog)
    
    def show_welcome_dialog():
        """Hiển thị Welcome Dialog với 3 lựa chọn"""
        global main_window
        if not main_window:
            return
            
        from pages_functions.welcome_dialog import WelcomeDialog
        
        welcome = WelcomeDialog(main_window)
        welcome.new_case_requested.connect(lambda: handle_new_case(main_window))
        welcome.open_recent_requested.connect(lambda: handle_open_recent(main_window, welcome))
        welcome.case_management_requested.connect(lambda: handle_case_management(main_window))
        
        welcome.exec_()
    
    def handle_new_case(main_window):
        """Xử lý tạo case mới"""
        # Switch to case management tab và hiện dialog tạo case
        main_window.case_btn.click()
        
        # Delay để tab được tạo
        from PyQt5.QtCore import QTimer
        def show_create_dialog():
            current_tab = main_window.ui.tabWidget.currentWidget()
            if hasattr(current_tab, 'show_create_case_dialog_with_workflow'):
                current_tab.show_create_case_dialog_with_workflow()
        
        QTimer.singleShot(200, show_create_dialog)
    
    def handle_open_recent(main_window, welcome_dialog):
        """Xử lý mở case gần đây"""
        case_id = welcome_dialog.get_selected_case_id()
        case_data = welcome_dialog.get_selected_case_data()
        
        if case_id and case_data:
            print(f"Opening recent case: {case_id}")
            
            # Chuyển đến tab Case Management
            main_window.case_btn.click()
            
            # Đợi một chút để tab được tạo rồi load case
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(300, lambda: load_case_in_tab(main_window, case_id, case_data))
    
    def load_case_in_tab(main_window, case_id, case_data):
        """Load case trong case management tab"""
        try:
            # Tìm case management widget trong tab hiện tại
            current_tab_index = main_window.ui.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = main_window.ui.tabWidget.widget(current_tab_index)
                
                # Kiểm tra xem có phải case management tab không
                if hasattr(current_widget, 'load_specific_case'):
                    # Method mới để load case cụ thể
                    current_widget.load_specific_case(case_id, case_data)
                elif hasattr(current_widget, 'ui') and hasattr(current_widget.ui, 'caseComboBox'):
                    # Fallback: set case trong combobox và load
                    current_widget.set_current_case(case_id)
                    current_widget.load_evidence()
                    
                    # Hiển thị thông báo thành công
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(
                        main_window,
                        "✅ Mở Case thành công",
                        f"📁 Case đã được mở:\n\n"
                        f"🆔 ID: {case_data.get('case_id', 'N/A')}\n"
                        f"📝 Tên: {case_data.get('title', 'N/A')}\n"
                        f"👨‍💼 Điều tra viên: {case_data.get('investigator', 'N/A')}\n"
                        f"📅 Ngày tạo: {case_data.get('created_at', 'N/A')}\n\n"
                        f"✨ Bạn có thể bắt đầu làm việc với case này!"
                    )
                else:
                    print("Case management widget không có method load case")
        except Exception as e:
            print(f"Lỗi khi load case: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                main_window,
                "❌ Lỗi mở Case",
                f"Không thể mở case:\n{str(e)}\n\nVui lòng thử lại."
            )
    
    def handle_case_management(main_window):
        """Xử lý chuyển đến case management"""
        main_window.case_btn.click()
    
    def show_login_window():
        """Hiển thị lại login window khi logout"""
        global main_window
        if main_window:
            main_window.hide()
        
        # Reset trạng thái login
        login_window.login_success = False
        login_window.ui.username_input.clear()
        login_window.ui.password_input.clear()
        login_window.ui.error_label.hide()
        login_window.ui.username_input.setFocus()
        
        # Hiển thị login window
        login_window.show()
    
    # Kết nối signal đăng nhập thành công với việc hiển thị main window
    login_window.login_successful.connect(show_main_window)
    
    # Hiển thị login window
    login_window.show()

    sys.exit(app.exec())