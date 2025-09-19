from PyQt5.QtWidgets import QWidget, QMessageBox, QDialog, QTableWidgetItem
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import sys
import os
from typing import Dict, List, Optional, Tuple

# Import UI và database
from views.pages.user_management_ui import Ui_Form
from views.dialogs.add_user_dialog_ui import Ui_AddUserDialog
from views.dialogs.delete_confirm_dialog_ui import Ui_DeleteConfirmDialog
from models.db_manager import DatabaseManager


class UserService:
    """Service xử lý business logic - thuần backend"""
    
    def __init__(self):
        self.db_manager = None
    
    def _get_db_connection(self) -> bool:
        """Lấy kết nối database"""
        try:
            self.db_manager = DatabaseManager()
            return self.db_manager.connect()
        except Exception:
            return False
    
    def create_user(self, username: str, password: str, email: str, role: str, 
                   full_name: str = None, phone_number: str = None) -> Tuple[bool, str]:
        """Tạo user mới - Returns: (success, message)"""
        if not username.strip():
            return False, "Tên đăng nhập không được rỗng!"
        
        if not password.strip():
            return False, "Mật khẩu không được rỗng!"
        
        if not full_name or not full_name.strip():
            full_name = username
        
        try:
            if not self._get_db_connection():
                return False, "Không thể kết nối database!"
            
            success = self.db_manager.create_user(username, password, email, role, full_name, phone_number)
            return (True, "Tạo user thành công!") if success else (False, "Có lỗi khi tạo user!")
        except Exception as e:
            return False, f"Có lỗi xảy ra: {str(e)}"
    
    def update_user(self, user_id: int, username: str, full_name: str, 
                   phone_number: str, email: str, role: str) -> Tuple[bool, str]:
        """Cập nhật user - Returns: (success, message)"""
        if not username.strip():
            return False, "Tên đăng nhập không được rỗng!"
        
        if not full_name or not full_name.strip():
            full_name = username
        
        try:
            if not self._get_db_connection():
                return False, "Không thể kết nối database!"
            
            query = "UPDATE Users SET username=?, full_name=?, phone_number=?, email=?, role=? WHERE user_id=?"
            cursor = self.db_manager.execute_query(query, (username, full_name, phone_number, email, role, user_id))
            
            success = cursor is not None
            return (True, "Cập nhật user thành công!") if success else (False, "Có lỗi khi cập nhật user!")
        except Exception as e:
            return False, f"Có lỗi xảy ra: {str(e)}"
    
    def get_users(self) -> Tuple[bool, List[Dict], str]:
        """Lấy danh sách users - Returns: (success, users_list, message)"""
        try:
            if not self._get_db_connection():
                return False, [], "Không thể kết nối database!"
            
            users = self.db_manager.get_users()
            return True, users, "List users successfully"
        except Exception as e:
            return False, [], f"Cannot load list users: {str(e)}"
    
    def get_user_by_id(self, user_id: int) -> Tuple[bool, Optional[Dict], str]:
        """Lấy user theo ID - Returns: (success, user_data, message)"""
        try:
            if not self._get_db_connection():
                return False, None, "Không thể kết nối database!"
            
            user = self.db_manager.fetch_one(
                "SELECT user_id, username, full_name, phone_number, email, role FROM Users WHERE user_id = ?", 
                (user_id,)
            )
            
            if user:
                return True, user, "Lấy thông tin user thành công"
            else:
                return False, None, "Không tìm thấy user"
        except Exception as e:
            return False, None, f"Lỗi khi lấy thông tin user: {str(e)}"
    
    def toggle_user_status(self, user_id: int) -> Tuple[bool, str]:
        """Đổi trạng thái user - Returns: (success, message)"""
        try:
            if not self._get_db_connection():
                return False, "Không thể kết nối database!"
            
            current_user = self.db_manager.fetch_one("SELECT is_active, username FROM Users WHERE user_id = ?", (user_id,))
            if not current_user:
                return False, "Không tìm thấy user trong database!"
            
            new_status = not current_user['is_active']
            success = self.db_manager.update_user(user_id, is_active=new_status)
            
            if success:
                status_text = "kích hoạt" if new_status else "vô hiệu hóa"
                return True, f"Đã {status_text} user '{current_user['username']}'"
            else:
                return False, "Có lỗi khi cập nhật trạng thái user!"
        except Exception as e:
            return False, f"Có lỗi xảy ra: {str(e)}"
    
    def can_delete_user(self, user_id: int, current_user_username: str) -> Tuple[bool, str]:
        """Kiểm tra có thể xóa user không - Returns: (can_delete, reason)"""
        try:
            if not self._get_db_connection():
                return False, "Không thể kết nối database!"
            
            user = self.db_manager.fetch_one("SELECT username FROM Users WHERE user_id = ?", (user_id,))
            if not user:
                return False, "Không tìm thấy user!"
            
            if user['username'] == current_user_username:
                return False, "Bạn không thể xóa chính tài khoản của mình!"
            
            case_count = self.db_manager.fetch_one("SELECT COUNT(*) as count FROM Cases WHERE user_id = ?", (user_id,))
            if case_count and case_count['count'] > 0:
                return False, f"User đang được gán vào {case_count['count']} case(s)! Vui lòng remove user khỏi tất cả cases trước."
            
            return True, "Có thể xóa user"
        except Exception as e:
            return False, f"Lỗi khi kiểm tra: {str(e)}"
    
    def hard_delete_user(self, user_id: int) -> Tuple[bool, str, Dict]:
        """Xóa vĩnh viễn user - Returns: (success, message, stats)"""
        try:
            if not self._get_db_connection():
                return False, "Không thể kết nối database!", {}
            
            user = self.db_manager.fetch_one("SELECT username FROM Users WHERE user_id = ?", (user_id,))
            if not user:
                return False, "Không tìm thấy user!", {}
            
            activity_count = self.db_manager.fetch_one("SELECT COUNT(*) as count FROM Activity_Logs WHERE user_id = ?", (user_id,))
            success = self.db_manager.hard_delete_user(user_id)
            
            stats = {
                'username': user['username'],
                'activity_logs_deleted': activity_count['count'] if activity_count else 0
            }
            
            if success:
                return True, f"Đã XÓA VĨNH VIỄN user '{user['username']}'!", stats
            else:
                return False, f"Có lỗi nghiêm trọng khi xóa vĩnh viễn user '{user['username']}'!", {}
        except Exception as e:
            return False, f"Có lỗi nghiêm trọng: {str(e)}", {}

class AddUserDialog(QDialog):
    """Dialog thêm/sửa người dùng - Bridge giữa UI và Service"""
    def __init__(self, parent=None, user_data=None):
        super(AddUserDialog, self).__init__(parent)
        self.user_data = user_data  # None = thêm mới, có data = sửa
        self.user_service = UserService()
        
        # Setup UI từ file đã tạo
        self.ui = Ui_AddUserDialog()
        self.ui.setupUi(self)
        
        # Setup dialog behavior
        self.setup_dialog()
        
        # Connect signals
        self.connect_signals()
        
        # Populate fields nếu đang sửa
        if user_data:
            self.populate_fields()
    
    def setup_dialog(self):
        """Thiết lập dialog properties"""
        if self.user_data:
            self.setWindowTitle("Sửa người dùng")
            # Ẩn password fields khi sửa user
            self.ui.passwordLabel.setVisible(False)
            self.ui.passwordEdit.setVisible(False)
        else:
            self.setWindowTitle("Thêm người dùng mới")
    
    def connect_signals(self):
        """Connect UI signals"""
        self.ui.saveBtn.clicked.connect(self.save_user)
        self.ui.cancelBtn.clicked.connect(self.reject)
    
    def populate_fields(self):
        """Fill fields với data"""
        if self.user_data:
            self.ui.usernameEdit.setText(self.user_data.get('username', ''))
            self.ui.fullNameEdit.setText(self.user_data.get('full_name', ''))
            self.ui.phoneEdit.setText(self.user_data.get('phone_number', ''))
            self.ui.emailEdit.setText(self.user_data.get('email', ''))
            role = self.user_data.get('role', 'ANALYST')
            index = self.ui.roleCombo.findText(role)
            if index >= 0:
                self.ui.roleCombo.setCurrentIndex(index)
    
    def get_form_data(self):
        """Lấy dữ liệu từ form"""
        data = {
            'username': self.ui.usernameEdit.text().strip(),
            'full_name': self.ui.fullNameEdit.text().strip(),
            'phone_number': self.ui.phoneEdit.text().strip(),
            'email': self.ui.emailEdit.text().strip(),
            'role': self.ui.roleCombo.currentText()
        }
        
        if not self.user_data:  # Thêm password nếu không phải edit mode
            data['password'] = self.ui.passwordEdit.text().strip()
        return data
    
    def save_user(self):
        """Bridge method - gọi service và hiển thị kết quả"""
        form_data = self.get_form_data()
        
        if self.user_data:  # Edit mode
            success, message = self.user_service.update_user(
                self.user_data['user_id'],
                form_data['username'],
                form_data['full_name'],
                form_data['phone_number'],
                form_data['email'],
                form_data['role']
            )
        else:  # Add mode
            success, message = self.user_service.create_user(
                form_data['username'],
                form_data['password'],
                form_data['email'],
                form_data['role'],
                form_data['full_name'],
                form_data['phone_number']
            )
        
        # Hiển thị kết quả
        if success:
            QMessageBox.information(self, "Thành công", message)
            self.accept()
        else:
            QMessageBox.warning(self, "Lỗi", message)

class UserManagement(QWidget):
    def __init__(self):
        super(UserManagement, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Initialize service
        self.user_service = UserService()
        self.users_data = []  # Cache for users data
        
        # Get current user info
        self.current_user = self.get_current_user()
        
        # Setup UI
        self.setup_table()
        self.connect_signals()
        
        # Check permissions
        self.check_permissions()
        
        # Load data
        self.load_users()
        
        # Setup search timer (để tránh search liên tục khi typing)
        self.search_timer = QTimer()
        self.search_timer.timeout.connect(self.filter_users)
        self.search_timer.setSingleShot(True)
    
    def get_current_user(self):
        """Lấy thông tin user hiện tại từ main window"""
        try:
            # Tìm main window
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            
            # Tìm login window để lấy logged_in_user
            for widget in app.allWidgets():
                if hasattr(widget, 'logged_in_user') and widget.logged_in_user:
                    return widget.logged_in_user
                    
            # Fallback: assume admin for now
            return {'role': 'ADMIN', 'username': 'admin'}
        except:
            # Default to admin for safety
            return {'role': 'ADMIN', 'username': 'admin'}
    
    def check_permissions(self):
        """Kiểm tra quyền truy cập User Management"""
        if not self.current_user or self.current_user.get('role') != 'ADMIN':
            # Disable tất cả chức năng nếu không phải admin
            if hasattr(self.ui, 'addUserBtn'):
                self.ui.addUserBtn.setEnabled(False)
                self.ui.addUserBtn.setToolTip("Chỉ Admin mới có quyền thêm người dùng")
            
            if hasattr(self.ui, 'editUserBtn'):
                self.ui.editUserBtn.setEnabled(False)
                self.ui.editUserBtn.setToolTip("Chỉ Admin mới có quyền sửa thông tin người dùng")
            
            if hasattr(self.ui, 'deleteUserBtn'):
                self.ui.deleteUserBtn.setEnabled(False)
                self.ui.deleteUserBtn.setToolTip("Chỉ Admin mới có quyền xóa người dùng")
            
            if hasattr(self.ui, 'toggleStatusBtn'):
                self.ui.toggleStatusBtn.setEnabled(False)
                self.ui.toggleStatusBtn.setToolTip("Chỉ Admin mới có quyền thay đổi trạng thái người dùng")
            
        else:
            self.update_status("Admin có đầy đủ quyền quản lý người dùng")
            return True
    
    
    def setup_table(self):
        """Thiết lập bảng users"""
        # Chỉ hiển thị khi có UI elements (tránh lỗi khi UI chưa có table)
        if hasattr(self.ui, 'usersTable'):
            # Ẩn cột ID 
            self.ui.usersTable.setColumnHidden(0, True)
            
            # Set column widths
            header = self.ui.usersTable.horizontalHeader()
            header.setStretchLastSection(True)
            
            # Set selection behavior
            self.ui.usersTable.setSelectionBehavior(self.ui.usersTable.SelectRows)
    
    def connect_signals(self):
        """Kết nối signals với slots"""
        # Nếu UI chưa có các elements, tạm thời skip
        if hasattr(self.ui, 'addUserBtn'):
            self.ui.addUserBtn.clicked.connect(self.add_user)
        
        if hasattr(self.ui, 'editUserBtn'):
            self.ui.editUserBtn.clicked.connect(self.edit_user)
        
        if hasattr(self.ui, 'deleteUserBtn'):
            self.ui.deleteUserBtn.clicked.connect(self.delete_user)
        
        if hasattr(self.ui, 'toggleStatusBtn'):
            self.ui.toggleStatusBtn.clicked.connect(self.toggle_user_status)
        
        if hasattr(self.ui, 'refreshBtn'):
            self.ui.refreshBtn.clicked.connect(self.load_users)
        
        if hasattr(self.ui, 'searchEdit'):
            self.ui.searchEdit.textChanged.connect(self.on_search_changed)
        
        if hasattr(self.ui, 'usersTable'):
            self.ui.usersTable.itemSelectionChanged.connect(self.on_selection_changed)
    
    def load_users(self):
        """Load danh sách users từ service"""
        success, users, message = self.user_service.get_users()
        
        if success:
            self.users_data = users  # Cache data
            self.populate_table(users)
            self.update_statistics(users)
            self.update_status(message)
        else:
            QMessageBox.critical(self, "Lỗi", message)
    
    def populate_table(self, users):
        """Fill data vào table"""
        if not hasattr(self.ui, 'usersTable'):
            return
            
        self.ui.usersTable.setRowCount(len(users))
        
        for row, user in enumerate(users):
            # ID (ẩn)
            self.ui.usersTable.setItem(row, 0, QTableWidgetItem(str(user['user_id'])))
            
            # Username (hiển thị full_name nếu có)
            display_name = user.get('full_name', '') or user['username']
            self.ui.usersTable.setItem(row, 1, QTableWidgetItem(f"{display_name} ({user['username']})"))
            
            # Email
            email = user.get('email', '') or 'N/A'
            self.ui.usersTable.setItem(row, 2, QTableWidgetItem(email))
            
            # Role - chỉ hiển thị text thuần túy
            role = user['role']
            self.ui.usersTable.setItem(row, 3, QTableWidgetItem(role))
            
            # Created date
            created_at = user.get('created_at', '')
            if created_at:
                # Format ngày đẹp hơn
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%d/%m/%Y")
                except:
                    formatted_date = created_at[:10] if len(created_at) >= 10 else "N/A"
            else:
                formatted_date = "N/A"
            self.ui.usersTable.setItem(row, 4, QTableWidgetItem(formatted_date))
            
            # Status - chỉ hiển thị text thuần túy
            status = "Hoạt động" if user['is_active'] else "Không hoạt động"
            self.ui.usersTable.setItem(row, 5, QTableWidgetItem(status))
    
    def update_statistics(self, users):
        """Cập nhật thống kê UI"""
        # Tính toán thống kê từ service logic (nhưng không cần tách riêng vì đơn giản)
        total = len(users)
        active = len([u for u in users if u.get('is_active', True)])
        inactive = total - active
        admin = len([u for u in users if u.get('role') == 'ADMIN'])
        analyst = len([u for u in users if u.get('role') == 'ANALYST'])
        
        # Cập nhật UI - loại bỏ emoji
        if hasattr(self.ui, 'statsLabel'):
            self.ui.statsLabel.setText(f"Total: {total} users")

        if hasattr(self.ui, 'activeUsersLabel'):
            self.ui.activeUsersLabel.setText(f"Active: {active}")

        if hasattr(self.ui, 'inactiveUsersLabel'):
            self.ui.inactiveUsersLabel.setText(f"Inactive: {inactive}")

        if hasattr(self.ui, 'adminUsersLabel'):
            self.ui.adminUsersLabel.setText(f"Admin: {admin}")

        if hasattr(self.ui, 'analystUsersLabel'):
            self.ui.analystUsersLabel.setText(f"Analyst: {analyst}")
    
    def update_status(self, message):
        """Cập nhật status bar"""
        if hasattr(self.ui, 'statusLabel'):
            self.ui.statusLabel.setText(message)
    
    def on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        if not hasattr(self.ui, 'usersTable'):
            return
            
        has_selection = len(self.ui.usersTable.selectedItems()) > 0
        is_admin = self.current_user and self.current_user.get('role') == 'ADMIN'
        
        # Chỉ enable buttons nếu có selection và là admin
        if hasattr(self.ui, 'editUserBtn'):
            self.ui.editUserBtn.setEnabled(has_selection and is_admin)
        
        if hasattr(self.ui, 'deleteUserBtn'):
            self.ui.deleteUserBtn.setEnabled(has_selection and is_admin)
        
        if hasattr(self.ui, 'toggleStatusBtn'):
            self.ui.toggleStatusBtn.setEnabled(has_selection and is_admin)
    
    def get_selected_user(self):
        """Lấy user được chọn"""
        if not hasattr(self.ui, 'usersTable'):
            return None
            
        selected_rows = set()
        for item in self.ui.usersTable.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            return None
        
        row = list(selected_rows)[0]
        user_id = int(self.ui.usersTable.item(row, 0).text())
        
        # Lấy thông tin từ service
        success, user, message = self.user_service.get_user_by_id(user_id)
        return user if success else None
    
    def add_user(self):
        """Thêm user mới"""
        dialog = AddUserDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_users()
    
    def edit_user(self):
        """Sửa user"""
        user = self.get_selected_user()
        if not user:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn user để sửa!")
            return
        
        dialog = AddUserDialog(self, user)
        if dialog.exec_() == QDialog.Accepted:
            self.load_users()
    
    def delete_user(self):
        """Xóa vĩnh viễn user khỏi hệ thống"""
        user = self.get_selected_user()
        if not user:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn user để xóa!")
            return
        
        # Kiểm tra quyền admin
        if not self.current_user or self.current_user.get('role') != 'ADMIN':
            QMessageBox.warning(self, "Quyền truy cập", "Chỉ Admin mới có quyền xóa người dùng!")
            return
        
        # Kiểm tra có thể xóa user không từ service
        can_delete, reason = self.user_service.can_delete_user(user['user_id'], self.current_user.get('username'))
        
        if not can_delete:
            QMessageBox.warning(self, "Không thể xóa", reason)
            return
        
        # Kiểm tra nếu user đang hoạt động - gợi ý dùng toggle status
        if user.get('is_active', True):
            QMessageBox.information(
                self,
                "Gợi ý",
                f"User '{user['username']}' đang ở trạng thái hoạt động.\n\n"
                f"GỢI Ý: Nếu bạn chỉ muốn ngăn user đăng nhập,\n"
                f"hãy sử dụng nút 'Đổi trạng thái' thay vì xóa vĩnh viễn.\n\n"
                f"Nút 'Xóa' sẽ XÓA VĨNH VIỄN user khỏi hệ thống."
            )
        
        # Hiển thị dialog xác nhận xóa vĩnh viễn
        delete_dialog = DeleteTypeDialog(self, user)
        
        if delete_dialog.exec_() == QDialog.Accepted:
            if delete_dialog.is_confirmed():
                self.perform_hard_delete(user)
            else:
                QMessageBox.information(self, "Thông báo", "Bạn đã hủy xóa vĩnh viễn user.")
    
    def perform_hard_delete(self, user):
        """Thực hiện hard delete sử dụng service"""
        # Gọi service để hard delete
        success, message, stats = self.user_service.hard_delete_user(user['user_id'])
        
        if success:
            # Thông báo thành công với thống kê
            success_msg = f"{message}\n\n"
            success_msg += f"User đã bị xóa hoàn toàn khỏi hệ thống.\n"

            activity_count = stats.get('activity_logs_deleted', 0)
            if activity_count > 0:
                success_msg += f"{activity_count} activity logs đã bị xóa vĩnh viễn.\n"
            else:
                success_msg += f"Không có activity logs nào bị mất.\n"

            success_msg += f"\nThao tác đã hoàn tất và không thể hoàn tác."

            QMessageBox.information(self, "Xóa vĩnh viễn thành công", success_msg)
            self.load_users()  # Refresh table
        else:
            QMessageBox.critical(
                self,
                "Hard delete thất bại",
                f"{message}\n\n"
                f"Nguyên nhân có thể:\n"
                f"User là admin cuối cùng trong hệ thống\n"
                f"Có ràng buộc dữ liệu chưa được xử lý\n"
                f"Lỗi kết nối database"
            )
    
    def toggle_user_status(self):
        """Đổi trạng thái user"""
        user = self.get_selected_user()
        if not user:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn user để thay đổi trạng thái!")
            return
        
        # Gọi service để toggle status
        success, message = self.user_service.toggle_user_status(user['user_id'])
        
        if success:
            QMessageBox.information(self, "Thành công", message)
            self.load_users()  # Refresh data
        else:
            QMessageBox.warning(self, "Lỗi", message)
    
    def on_search_changed(self):
        """Xử lý khi search text thay đổi"""
        self.search_timer.stop()
        self.search_timer.start(500)  # Delay 500ms
    
    def filter_users(self):
        """Lọc users theo search term"""
        if not hasattr(self.ui, 'searchEdit') or not hasattr(self.ui, 'usersTable'):
            return
        
        search_text = self.ui.searchEdit.text().lower()
        
        for row in range(self.ui.usersTable.rowCount()):
            show_row = False
            
            # Tìm trong username (cột 1) và email (cột 2)
            for col in [1, 2]:  # Username/Full_name và Email columns
                item = self.ui.usersTable.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            
            self.ui.usersTable.setRowHidden(row, not show_row)

class DeleteTypeDialog(QDialog):
    """Dialog xác nhận xóa vĩnh viễn người dùng - Bridge giữa UI và logic"""
    
    def __init__(self, parent=None, user_info=None):
        super(DeleteTypeDialog, self).__init__(parent)
        self.user_info = user_info or {}
        self.confirmed = False
        
        # Setup UI từ file đã tạo
        self.ui = Ui_DeleteConfirmDialog()
        self.ui.setupUi(self)
        
        # Setup dialog
        self.setup_dialog()
        
        # Connect signals
        self.connect_signals()
        
        # Populate user info
        self.populate_user_info()
        
    def setup_dialog(self):
        """Thiết lập dialog properties"""
        self.setWindowTitle("Xác nhận xóa vĩnh viễn")
        self.setModal(True)
    
    def connect_signals(self):
        """Connect UI signals"""
        self.ui.cancelBtn.clicked.connect(self.reject)
        self.ui.deleteBtn.clicked.connect(self.confirm_delete)
        self.ui.confirmInput.textChanged.connect(self.check_confirmation)
    
    def populate_user_info(self):
        """Điền thông tin user vào UI"""
        username = self.user_info.get('username', 'N/A')
        full_name = self.user_info.get('full_name', 'N/A')
        role = self.user_info.get('role', 'N/A')
        email = self.user_info.get('email', 'N/A')
        
        # Cập nhật thông tin user
        user_info_text = f"""Username: {username} Full Name: {full_name} Role: {role} Email: {email}"""
        
        self.ui.userInfoLabel.setText(user_info_text)
        self.ui.instructionLabel.setText(f"Type '{username}' to confirm:")
        self.ui.confirmInput.setPlaceholderText(f"Type '{username}' here to confirm...")
    
    def check_confirmation(self):
        """Kiểm tra input confirmation - UI logic"""
        entered_text = self.ui.confirmInput.text().strip()
        expected_username = self.user_info.get('username', '')
        
        if entered_text == expected_username:
            self.ui.deleteBtn.setEnabled(True)
        else:
            self.ui.deleteBtn.setEnabled(False)
    
    def confirm_delete(self):
        """Final confirmation dialog"""
        final_warning = QMessageBox.critical(
            self,
            "XÁC NHẬN CUỐI CÙNG",
            f"CẢNH BÁO CUỐI CÙNG!\n\n"
            f"Bạn THỰC SỰ muốn XÓA VĨNH VIỄN user '{self.user_info.get('username', '')}'?\n\n"
            f"User sẽ bị xóa hoàn toàn khỏi database\n"
            f"KHÔNG THỂ HOÀN TÁC!\n\n"
            f"Nhấn 'Yes' để XÓA VĨNH VIỄN ngay lập tức.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if final_warning == QMessageBox.Yes:
            self.confirmed = True
            self.accept()
    
    def is_confirmed(self):
        """Trả về True nếu user đã xác nhận xóa"""
        return self.confirmed