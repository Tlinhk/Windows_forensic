import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from controllers.login_window import LoginWindow

# Import with absolute paths for main module
import controllers.main_window_controller as main_controller
import controllers.welcome_dialog as welcome_dialog


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Biến global để giữ reference main window
    main_window = None

    # Hiển thị login window trước
    login_window = LoginWindow()

    def show_main_window():
        """Hiển thị main window sau khi đăng nhập thành công"""
        global main_window
        login_window.hide()
        main_window = main_controller.MainController()

        # Lấy thông tin user thực tế từ login
        user_data = login_window.get_logged_in_user()
        if user_data:
            # Import db để set current user
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.set_current_user(user_data["user_id"])
            main_window.set_current_user(user_data)

        main_window.show_main_window()

        # Kết nối signal logout từ main window
        main_window.logout_requested.connect(show_login_window)

        # Hiển thị Welcome Dialog sau khi main window ready
        QTimer.singleShot(500, show_welcome_dialog)

    def show_welcome_dialog():
        """Hiển thị Welcome Dialog với 3 lựa chọn"""
        global main_window
        if not main_window:
            return

        welcome = welcome_dialog.WelcomeDialog(main_window.main_window)
        welcome.new_case_requested.connect(lambda: handle_new_case(main_window))
        welcome.open_recent_requested.connect(
            lambda: handle_open_recent(main_window, welcome)
        )
        welcome.case_management_requested.connect(
            lambda: handle_case_management(main_window)
        )

        welcome.exec_()

    def handle_new_case(main_window):
        """Xử lý tạo case mới"""
        # Switch to case management tab và hiện dialog tạo case
        main_window.view.case_btn.click()

        # Delay để tab được tạo
        def show_create_dialog():
            current_tab = main_window.view.tabWidget.currentWidget()
            if hasattr(current_tab, "show_create_case_dialog_with_workflow"):
                current_tab.show_create_case_dialog_with_workflow()

        QTimer.singleShot(200, show_create_dialog)

    def handle_open_recent(main_window, welcome_dialog):
        """Xử lý mở case gần đây"""
        case_id = welcome_dialog.get_selected_case_id()
        case_data = welcome_dialog.get_selected_case_data()

        if case_id and case_data:
            print(f"Opening recent case: {case_id}")

            # Chuyển đến tab Case Management
            main_window.view.case_btn.click()

            # Đợi một chút để tab được tạo rồi load case
            QTimer.singleShot(
                300, lambda: load_case_in_tab(main_window, case_id, case_data)
            )

    def load_case_in_tab(main_window, case_id, case_data):
        """Load case trong case management tab"""
        try:
            # Tìm case management widget trong tab hiện tại
            current_tab_index = main_window.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = main_window.view.tabWidget.widget(current_tab_index)

                # Kiểm tra xem có phải case management tab không
                if hasattr(current_widget, "load_specific_case"):
                    # Method mới để load case cụ thể
                    current_widget.load_specific_case(case_id, case_data)
                elif hasattr(current_widget, "ui") and hasattr(
                    current_widget.ui, "caseComboBox"
                ):
                    # Fallback: set case trong combobox và load
                    current_widget.set_current_case(case_id)
                    current_widget.load_evidence()

                    # Hiển thị thông báo thành công
                    from PyQt5.QtWidgets import QMessageBox

                    QMessageBox.information(
                        main_window.main_window,
                        "✅ Mở Case thành công",
                        f"📁 Case đã được mở:\n\n"
                        f"🆔 ID: {case_data.get('case_id', 'N/A')}\n"
                        f"📝 Tên: {case_data.get('title', 'N/A')}\n"
                        f"👨‍💼 Điều tra viên: {case_data.get('investigator', 'N/A')}\n"
                        f"📅 Ngày tạo: {case_data.get('created_at', 'N/A')}\n\n"
                        f"✨ Bạn có thể bắt đầu làm việc với case này!",
                    )
                else:
                    print("Case management widget không có method load case")
        except Exception as e:
            print(f"Lỗi khi load case: {e}")
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(
                main_window.main_window,
                "❌ Lỗi mở Case",
                f"Không thể mở case:\n{str(e)}\n\nVui lòng thử lại.",
            )

    def handle_case_management(main_window):
        """Xử lý chuyển đến case management"""
        main_window.view.case_btn.click()

    def show_login_window():
        """Hiển thị lại login window khi logout"""
        global main_window
        if main_window:
            main_window.main_window.hide()

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

    sys.exit(app.exec_())
