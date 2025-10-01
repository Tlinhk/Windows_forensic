import sys
import os

# Thêm thư mục hiện tại vào đường dẫn Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from controllers.login_window import LoginWindow

# Import with absolute paths for main module
import controllers.main_window_controller as main_controller
import controllers.welcome_dialog as welcome_dialog


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Biến toàn cục để lưu tham chiếu cửa sổ chính
    main_window = None

    # Hiển thị cửa sổ đăng nhập trước
    login_window = LoginWindow()

    def show_main_window():
        """Hiển thị cửa sổ chính sau khi đăng nhập thành công"""
        global main_window
        login_window.hide()
        main_window = main_controller.MainController()

        # Lấy thông tin người dùng thực từ đăng nhập
        user_data = login_window.get_logged_in_user()
        if user_data:
            # Import db để thiết lập người dùng hiện tại
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.set_current_user(user_data["user_id"])
            main_window.set_current_user(user_data)

        main_window.show_main_window()

        # Kết nối tín hiệu đăng xuất từ cửa sổ chính
        main_window.logout_requested.connect(show_login_window)

        # Hiển thị Dialog Chào mừng sau khi cửa sổ chính sẵn sàng
        QTimer.singleShot(500, show_welcome_dialog)

    def show_welcome_dialog():
        """Hiển thị Dialog Chào mừng với 3 tùy chọn"""
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
        """Xử lý tạo vụ án mới"""
        # Chuyển sang tab quản lý vụ án và hiển thị dialog tạo vụ án
        main_window.view.case_btn.click()

        # Trì hoãn để cho phép tab được tạo
        def show_create_dialog():
            current_tab = main_window.view.tabWidget.currentWidget()
            if hasattr(current_tab, "show_create_case_dialog_with_workflow"):
                current_tab.show_create_case_dialog_with_workflow()

        QTimer.singleShot(200, show_create_dialog)

    def handle_open_recent(main_window, welcome_dialog):
        """Xử lý mở vụ án gần đây"""
        case_id = welcome_dialog.get_selected_case_id()
        case_data = welcome_dialog.get_selected_case_data()

        if case_id and case_data:
            print(f"Opening recent case: {case_id}")

            # Switch to Case Management tab
            main_window.view.case_btn.click()

            # Wait a bit for tab to be created then load case
            QTimer.singleShot(
                300, lambda: load_case_in_tab(main_window, case_id, case_data)
            )

    def load_case_in_tab(main_window, case_id, case_data):
        """Tải vụ án trong tab quản lý vụ án"""
        try:
            # Tìm widget quản lý vụ án trong tab hiện tại
            current_tab_index = main_window.view.tabWidget.currentIndex()
            if current_tab_index >= 0:
                current_widget = main_window.view.tabWidget.widget(current_tab_index)

                # Kiểm tra xem có phải tab quản lý vụ án không
                if hasattr(current_widget, "load_specific_case"):
                    # Phương thức mới để tải vụ án cụ thể
                    current_widget.load_specific_case(case_id, case_data)
                elif hasattr(current_widget, "ui") and hasattr(
                    current_widget.ui, "caseComboBox"
                ):
                    # Dự phòng: thiết lập vụ án trong combobox và tải
                    current_widget.set_current_case(case_id)
                    current_widget.load_evidence()

                    # Hiển thị thông báo thành công
                    from PyQt5.QtWidgets import QMessageBox

                    QMessageBox.information(
                        main_window.main_window,
                        "Case Opened Successfully",
                        f"Case has been opened:\n\n"
                        f"ID: {case_data.get('case_id', 'N/A')}\n"
                        f"Name: {case_data.get('title', 'N/A')}\n"
                        f"Investigator: {case_data.get('investigator', 'N/A')}\n"
                        f"Created: {case_data.get('created_at', 'N/A')}\n\n"
                        f"You can now start working with this case!",
                    )
                else:
                    print("Widget quản lý vụ án không có phương thức tải vụ án")
        except Exception as e:
            print(f"Error loading case: {e}")
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(
                main_window.main_window,
                "Error Opening Case",
                f"Cannot open case:\n{str(e)}\n\nPlease try again.",
            )

    def handle_case_management(main_window):
        """Xử lý chuyển sang quản lý vụ án"""
        main_window.view.case_btn.click()

    def show_login_window():
        """Hiển thị lại cửa sổ đăng nhập khi đăng xuất"""
        global main_window
        if main_window:
            main_window.main_window.hide()

        # Đặt lại trạng thái đăng nhập
        login_window.login_success = False
        login_window.ui.username_input.clear()
        login_window.ui.password_input.clear()
        login_window.ui.error_label.hide()
        login_window.ui.username_input.setFocus()

        # Hiển thị cửa sổ đăng nhập
        login_window.show()

    # Kết nối tín hiệu đăng nhập thành công để hiển thị cửa sổ chính
    login_window.login_successful.connect(show_main_window)

    # Show login window
    login_window.show()

    sys.exit(app.exec_())
