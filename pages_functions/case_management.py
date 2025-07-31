from PyQt5.QtWidgets import (
    QWidget,
    QHeaderView,
    QTableWidgetItem,
    QMessageBox,
    QDialog,
    QFileDialog,
    QAbstractItemView,
    QPushButton,
    QHBoxLayout,
)
from PyQt5.QtCore import Qt, QDateTime, QTimer
from PyQt5.QtGui import QIcon
from database.db_manager import db
import os
import hashlib
from datetime import datetime

from ui.pages.case_management_ui import Ui_Form
from ui.pages.create_case_dialog_ui import Ui_CreateCaseDialog
from ui.pages.edit_case_dialog_ui import Ui_EditCaseDialog
from ui.pages.import_evidence_dialog_ui import Ui_ImportEvidenceDialog
from pages_functions.add_evidence_wizard import AddEvidenceWizard


class CreateCaseDialog(QDialog):
    """Dialog để tạo case mới"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_CreateCaseDialog()
        self.ui.setupUi(self)
        self.created_case_id = None  # Store created case ID for workflow

        # Kết nối signals
        self.ui.cancelBtn.clicked.connect(self.reject)
        self.ui.createBtn.clicked.connect(self.create_case)
        self.ui.caseNameEdit.textChanged.connect(self.update_case_path)

        # Set initial path
        self.update_case_path("")

    def update_case_path(self, case_name):
        """Cập nhật đường dẫn khi tên case thay đổi"""
        if case_name.strip():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            case_name_clean = (
                case_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            )
            case_folder_name = f"{case_name_clean}_{timestamp}"
            case_path = f"E:/Cases/{case_folder_name}"
            self.ui.casePathEdit.setText(case_path)
        else:
            self.ui.casePathEdit.setText("E:/Cases/[tên_case_với_timestamp]")

    def create_case(self):
        """Tạo case mới"""
        case_name = self.ui.caseNameEdit.text().strip()
        if not case_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên case!")
            return

        # Lấy đường dẫn từ UI (đã được tạo tự động)
        case_folder = self.ui.casePathEdit.text()

        try:
            # Tạo thư mục case nếu chưa có
            os.makedirs(case_folder, exist_ok=True)

            # Lưu vào database (investigator_id sẽ tự động được set từ current_user_id)
            case_data = {
                "title": case_name,
                "archive_path": case_folder,
                "status": "OPEN",
            }

            case_id = db.create_case(**case_data)

            if case_id:
                self.created_case_id = case_id  # Store for workflow

                # Đóng create dialog trước
                self.accept()

                # Hiển thị Add Evidence Wizard trực tiếp (không có dialog trung gian)
                self.show_evidence_wizard_directly(case_id)
            else:
                QMessageBox.critical(
                    self, "Lỗi", "Không thể tạo case. Vui lòng thử lại!"
                )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi tạo case: {str(e)}")

    def show_evidence_wizard_directly(self, case_id):
        """Hiển thị Add Evidence Wizard trực tiếp sau khi tạo case"""
        from PyQt5.QtCore import QTimer

        def show_wizard():
            # Hiển thị Add Evidence Wizard trực tiếp
            wizard = AddEvidenceWizard(case_id=case_id, parent=self.parent())
            wizard.evidence_added.connect(
                lambda data: self.on_evidence_added_from_wizard_direct(data)
            )
            wizard.exec_()

        # Delay một chút để create dialog đóng hoàn toàn
        QTimer.singleShot(100, show_wizard)

    def on_evidence_added_from_wizard_direct(self, evidence_data):
        """Xử lý khi wizard thêm evidence thành công (từ luồng tạo case trực tiếp)"""
        print(f"Evidence added from direct wizard: {evidence_data}")
        # Refresh case management nếu cần
        if hasattr(self.parent(), "load_cases"):
            self.parent().load_cases()

    def show_workflow_options(self, case_name):
        """Hiển thị lựa chọn workflow sau khi tạo case thành công"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Add evidence")
        msg.setText(f"Add evidence?")
        # msg.setInformativeText("Lựa chọn?")

        # Create custom buttons
        import_btn = msg.addButton("Import Evidence", QMessageBox.AcceptRole)
        if import_btn:
            import_btn.setToolTip("Import evidence có sẵn vào case")

        collect_btn = msg.addButton("Thu thập Evidence", QMessageBox.AcceptRole)
        if collect_btn:
            collect_btn.setToolTip("Thu thập dữ liệu volatile và non-volatile")

        # later_btn = msg.addButton("⏳ Để sau", QMessageBox.RejectRole)
        # if later_btn:
        #    later_btn.setToolTip("Quay lại case management để làm việc khác")

        msg.exec_()

        if msg.clickedButton() == import_btn:
            self.start_import_workflow()
            return "accept"
        elif msg.clickedButton() == collect_btn:
            self.start_collection_workflow()
            return "accept"
        else:
            return "accept"  # Just close and go back to case management

    def start_import_workflow(self):
        """Bắt đầu workflow import evidence"""
        if not self.created_case_id:
            return

        # Show Add Evidence Wizard thay vì import dialog cũ
        wizard = AddEvidenceWizard(case_id=self.created_case_id, parent=self)
        wizard.evidence_added.connect(self.on_evidence_added_from_wizard)
        if wizard.exec_() == QDialog.Accepted:
            # After successful import, ask about analysis
            self.ask_for_analysis_after_import()

    def on_evidence_added_from_wizard(self, evidence_data):
        """Xử lý khi wizard thêm evidence thành công"""
        print(f"Evidence added from wizard: {evidence_data}")
        # Có thể refresh case management nếu cần

    def start_collection_workflow(self):
        """Bắt đầu workflow thu thập evidence"""
        if not self.created_case_id:
            return

        # Find main window to start collection
        main_window = self.find_main_window()
        if main_window:
            # Start with volatile collection first
            QMessageBox.information(
                self,
                "🚀 Bắt đầu thu thập",
                "📋 Luồng thu thập sẽ bắt đầu:\n\n"
                "1️⃣ Thu thập dữ liệu Volatile (RAM, processes...)\n"
                "2️⃣ Thu thập dữ liệu Non-volatile (disk, files...)\n"
                "3️⃣ Tự động thêm evidence vào case\n"
                "4️⃣ Lựa chọn phân tích\n\n"
                "Bắt đầu với Volatile Data...",
            )
            # Store case info for collection workflow - use safer method
            if hasattr(main_window, "__dict__"):
                main_window.__dict__["workflow_case_id"] = self.created_case_id
                main_window.__dict__["workflow_stage"] = "volatile"

            if hasattr(main_window, "switch_to_volatile_tab"):
                main_window.switch_to_volatile_tab(self.created_case_id)
        else:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Không thể khởi động workflow thu thập. Vui lòng sử dụng menu chính.",
            )

    def ask_for_analysis_after_import(self):
        """Hỏi có muốn phân tích sau khi import xong"""
        reply = QMessageBox.question(
            self,
            "🔬 Phân tích Evidence",
            "✅ Import evidence thành công!\n\n"
            "🤔 Bạn có muốn bắt đầu phân tích ngay không?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            self.start_analysis_workflow()

    def start_analysis_workflow(self):
        """Bắt đầu workflow phân tích"""
        if not self.created_case_id:
            return

        # Get evidence types from the case to suggest appropriate analysis
        evidence_list = db.get_artifacts_by_case(self.created_case_id)

        if not evidence_list:
            QMessageBox.information(
                self, "📋 Không có Evidence", "Case này chưa có evidence để phân tích."
            )
            return

        # Suggest analysis types based on evidence
        analysis_suggestions = self.get_analysis_suggestions(evidence_list)

        msg = QMessageBox(self)
        msg.setWindowTitle("🔬 Chọn loại phân tích")
        msg.setText("📊 Chọn loại phân tích phù hợp với evidence:")
        msg.setInformativeText(
            f"📁 Case có {len(evidence_list)} evidence\n{analysis_suggestions}"
        )

        # Add analysis buttons based on evidence types
        buttons = {}
        if any("VOLATILE" in e.get("evidence_type", "") for e in evidence_list):
            buttons["memory"] = msg.addButton(
                "🧠 Memory Analysis", QMessageBox.AcceptRole
            )

        if any("NON-VOLATILE" in e.get("evidence_type", "") for e in evidence_list):
            buttons["registry"] = msg.addButton(
                "📝 Registry Analysis", QMessageBox.AcceptRole
            )
            buttons["file"] = msg.addButton("📁 File Analysis", QMessageBox.AcceptRole)
            buttons["browser"] = msg.addButton(
                "🌐 Browser Analysis", QMessageBox.AcceptRole
            )

        buttons["later"] = msg.addButton("⏳ Phân tích sau", QMessageBox.RejectRole)

        msg.exec_()

        # Handle analysis choice
        clicked = msg.clickedButton()
        main_window = self.find_main_window()

        if main_window:
            if clicked == buttons.get("memory") and hasattr(main_window, "memory_btn"):
                main_window.memory_btn.click()
            elif clicked == buttons.get("registry") and hasattr(
                main_window, "registry_btn"
            ):
                main_window.registry_btn.click()
            elif clicked == buttons.get("file") and hasattr(main_window, "file_btn"):
                main_window.file_btn.click()
            elif clicked == buttons.get("browser") and hasattr(
                main_window, "browser_btn"
            ):
                main_window.browser_btn.click()

    def get_analysis_suggestions(self, evidence_list):
        """Đề xuất loại phân tích dựa trên evidence có sẵn"""
        suggestions = []

        volatile_count = sum(
            1 for e in evidence_list if "VOLATILE" in e.get("evidence_type", "")
        )
        nonvolatile_count = sum(
            1 for e in evidence_list if "NON-VOLATILE" in e.get("evidence_type", "")
        )

        if volatile_count > 0:
            suggestions.append(
                f"🔴 {volatile_count} Volatile evidence → Memory Analysis"
            )

        if nonvolatile_count > 0:
            suggestions.append(
                f"🔵 {nonvolatile_count} Non-volatile evidence → File/Registry/Browser Analysis"
            )

        return "\n".join(suggestions) if suggestions else "📋 Các loại phân tích có sẵn"

    def find_main_window(self):
        """Tìm main window để điều hướng"""
        widget = self
        while widget:
            parent = widget.parent()
            if parent and hasattr(parent, "switch_to_volatile_tab"):
                return parent
            if hasattr(widget, "window") and hasattr(
                widget.window(), "switch_to_volatile_tab"
            ):
                return widget.window()
            widget = parent
        return None


class EditCaseDialog(QDialog):
    """Dialog để sửa case"""

    def __init__(self, case_id, parent=None):
        super().__init__(parent)
        self.ui = Ui_EditCaseDialog()
        self.ui.setupUi(self)
        self.case_id = case_id

        # Kết nối signals
        self.ui.cancelBtn.clicked.connect(self.reject)
        self.ui.saveBtn.clicked.connect(self.save_case)

        # Load thông tin case hiện tại
        self.load_case_info()

    def load_case_info(self):
        """Load thông tin case hiện tại"""
        try:
            case = db.get_case_by_id(self.case_id)
            if case:
                self.ui.caseNameEdit.setText(case.get("title", ""))
                self.ui.casePathEdit.setText(case.get("archive_path", ""))

                # Set status
                status = case.get("status", "OPEN")
                index = self.ui.statusCombo.findText(status)
                if index >= 0:
                    self.ui.statusCombo.setCurrentIndex(index)

        except Exception as e:
            QMessageBox.critical(
                self, "Lỗi", f"Không thể load thông tin case: {str(e)}"
            )

    def save_case(self):
        """Lưu thay đổi case"""
        case_name = self.ui.caseNameEdit.text().strip()
        if not case_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên case!")
            return

        status = self.ui.statusCombo.currentText()

        try:
            # Cập nhật case trong database
            case_data = {"title": case_name, "status": status}

            if db.update_case(self.case_id, **case_data):
                QMessageBox.information(
                    self,
                    "Thành công",
                    f"✅ Đã cập nhật case thành công!\n\n"
                    f"📂 Tên case: {case_name}\n"
                    f"📊 Trạng thái: {status}",
                )
                self.accept()
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể cập nhật case!")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi cập nhật case: {str(e)}")


class CreateCaseDialogWithAutoWorkflow(QDialog):
    """Dialog để tạo case mới với workflow tự động - chỉ hiện Add Evidence sau khi tạo xong"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_CreateCaseDialog()
        self.ui.setupUi(self)
        self.created_case_id = None

        # Kết nối signals
        self.ui.cancelBtn.clicked.connect(self.reject)
        self.ui.createBtn.clicked.connect(self.create_case)
        self.ui.caseNameEdit.textChanged.connect(self.update_case_path)

        # Set initial path
        self.update_case_path("")

    def update_case_path(self, case_name):
        """Cập nhật đường dẫn khi tên case thay đổi"""
        if case_name.strip():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            case_name_clean = (
                case_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            )
            case_folder_name = f"{case_name_clean}_{timestamp}"
            case_path = f"E:/Cases/{case_folder_name}"
            self.ui.casePathEdit.setText(case_path)
        else:
            self.ui.casePathEdit.setText("E:/Cases/[tên_case_với_timestamp]")

    def create_case(self):
        """Tạo case mới và tự động hiện Add Evidence dialog"""
        case_name = self.ui.caseNameEdit.text().strip()
        if not case_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên case!")
            return

        case_folder = self.ui.casePathEdit.text()

        try:
            # Tạo thư mục case nếu chưa có
            os.makedirs(case_folder, exist_ok=True)

            # Lưu vào database
            case_data = {
                "title": case_name,
                "archive_path": case_folder,
                "status": "OPEN",
            }

            case_id = db.create_case(**case_data)

            if case_id:
                self.created_case_id = case_id

                # Đóng create case dialog trước
                self.accept()

                # Hiển thị Add Evidence Wizard trực tiếp (bỏ thông báo và dialog nhỏ)
                self.show_evidence_wizard_directly(case_id)

            else:
                QMessageBox.critical(
                    self, "Lỗi", "Không thể tạo case. Vui lòng thử lại!"
                )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi tạo case: {str(e)}")

    def show_add_evidence_dialog(self, case_id):
        """Hiện dialog Add Evidence ngay sau khi tạo case"""
        from PyQt5.QtCore import QTimer

        def show_dialog():
            msg = QMessageBox(self.parent())
            msg.setWindowTitle("Add evidence")
            msg.setText("Add evidence?")

            # Create custom buttons
            import_btn = msg.addButton("Import Evidence", QMessageBox.AcceptRole)
            collect_btn = msg.addButton("Thu thập Evidence", QMessageBox.AcceptRole)

            msg.exec_()

            if msg.clickedButton() == import_btn:
                # Show Add Evidence Wizard thay vì import dialog cũ
                wizard = AddEvidenceWizard(case_id=case_id, parent=self.parent())
                wizard.evidence_added.connect(
                    lambda data: self.on_evidence_added_workflow(data, self.parent())
                )
                if wizard.exec_() == QDialog.Accepted:
                    # Refresh case management if needed
                    if hasattr(self.parent(), "load_cases"):
                        self.parent().load_cases()

            elif msg.clickedButton() == collect_btn:
                # Start collection workflow
                self.start_collection_workflow(case_id)

        # Delay một chút để create dialog đóng hoàn toàn
        QTimer.singleShot(200, show_dialog)

    def show_evidence_wizard_directly(self, case_id):
        """Hiển thị Add Evidence Wizard trực tiếp sau khi tạo case (cho CreateCaseDialogWithAutoWorkflow)"""
        from PyQt5.QtCore import QTimer

        def show_wizard():
            # Hiển thị Add Evidence Wizard trực tiếp
            wizard = AddEvidenceWizard(case_id=case_id, parent=self.parent())
            wizard.evidence_added.connect(
                lambda data: self.on_evidence_added_workflow_direct(data)
            )
            wizard.exec_()

        # Delay một chút để create dialog đóng hoàn toàn
        QTimer.singleShot(100, show_wizard)

    def on_evidence_added_workflow_direct(self, evidence_data):
        """Xử lý khi wizard thêm evidence thành công (từ luồng workflow trực tiếp)"""
        print(f"Evidence added from workflow direct wizard: {evidence_data}")
        # Refresh case management nếu cần
        if hasattr(self.parent(), "load_cases"):
            self.parent().load_cases()

    def on_evidence_added_workflow(self, evidence_data, parent_widget):
        """Helper method xử lý evidence added từ wizard"""
        print(f"Evidence added in workflow: {evidence_data}")
        if hasattr(parent_widget, "load_cases"):
            parent_widget.load_cases()

    def start_collection_workflow(self, case_id):
        """Bắt đầu collection workflow"""
        # Find main window và chuyển đến volatile collection
        main_window = self.find_main_window()
        if main_window:
            # Set workflow data
            if hasattr(main_window, "set_workflow_data"):
                main_window.set_workflow_data(case_id, "volatile")

            # Switch to volatile tab
            if hasattr(main_window, "switch_to_volatile_tab"):
                main_window.switch_to_volatile_tab(case_id)

    def find_main_window(self):
        """Tìm main window"""
        widget = self.parent()
        while widget:
            if hasattr(widget, "switch_to_volatile_tab"):
                return widget
            widget = widget.parent() if hasattr(widget, "parent") else None
        return None


class ImportEvidenceDialog(QDialog):
    """Dialog để import evidence với 2 loại chính: VOLATILE và NON-VOLATILE"""

    def __init__(self, case_id, parent=None):
        super().__init__(parent)
        self.ui = Ui_ImportEvidenceDialog()
        self.ui.setupUi(self)
        self.case_id = case_id
        self.selected_files = []  # Initialize for multiple file selection

        # Kết nối signals
        self.ui.cancelBtn.clicked.connect(self.reject)
        self.ui.importBtn.clicked.connect(self.import_evidence)
        self.ui.browseBtn.clicked.connect(self.browse_evidence_files)

        # Set default to VOLATILE
        self.ui.volatileRadio.setChecked(True)

    def browse_evidence_files(self):
        """Browse và chọn files evidence (luôn cho phép multiple selection)"""
        # Kiểm tra loại evidence được chọn
        is_volatile = self.ui.volatileRadio.isChecked()

        # Định nghĩa file filter dựa vào loại evidence
        if is_volatile:
            file_filter = "VOLATILE Data (*.mem *.vmem *.dmp *.raw *.pcap *.pcapng *.txt *.json *.csv *.zip);;Memory Dumps (*.mem *.vmem *.dmp *.raw);;Network (*.pcap *.pcapng);;Text Files (*.txt *.json *.csv);;ZIP Archives (*.zip);;All Files (*)"
            dialog_title = (
                "Chọn VOLATILE Evidence Files (Ctrl+Click để chọn nhiều files)"
            )
        else:
            file_filter = "NON-VOLATILE Data (*.dd *.e01 *.raw *.img *.001 *.reg *.evtx *.pf);;Disk Images (*.dd *.e01 *.raw *.img *.001);;Registry Files (*.reg *.hiv);;Event Logs (*.evtx);;Prefetch (*.pf);;All Files (*)"
            dialog_title = (
                "Chọn NON-VOLATILE Evidence Files (Ctrl+Click để chọn nhiều files)"
            )

        # Luôn cho phép chọn multiple files
        files, _ = QFileDialog.getOpenFileNames(self, dialog_title, "", file_filter)

        if files:
            # Hiển thị danh sách files được chọn
            file_list = "\n".join([os.path.basename(f) for f in files])
            if len(files) == 1:
                self.ui.filePathEdit.setText(os.path.basename(files[0]))
            else:
                self.ui.filePathEdit.setText(f"{len(files)} files được chọn")
            self.ui.filePathEdit.setToolTip(file_list)

            # Store full paths for later use
            self.selected_files = files

            # Auto-fill tên evidence nếu chưa có
            if not self.ui.evidenceNameEdit.text():
                if len(files) == 1:
                    # Sử dụng tên file (không có extension)
                    filename = os.path.splitext(os.path.basename(files[0]))[0]
                    self.ui.evidenceNameEdit.setText(filename)
                else:
                    # Tạo tên group cho multiple files
                    evidence_type = "VOLATILE" if is_volatile else "NON-VOLATILE"
                    self.ui.evidenceNameEdit.setText(
                        f"{evidence_type} Collection ({len(files)} files)"
                    )

    def calculate_file_hash(self, file_path):
        """Tính toán hash của file"""
        hash_md5 = hashlib.md5()
        hash_sha1 = hashlib.sha1()
        hash_sha256 = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
                    hash_sha1.update(chunk)
                    hash_sha256.update(chunk)

            return {
                "md5": hash_md5.hexdigest(),
                "sha1": hash_sha1.hexdigest(),
                "sha256": hash_sha256.hexdigest(),
            }
        except Exception as e:
            print(f"Error calculating hash: {e}")
            return None

    def calculate_file_hash_with_progress(self, file_path, filename):
        """Tính hash với progress dialog cho file lớn"""
        try:
            file_size = os.path.getsize(file_path)

            # Create progress dialog
            from PyQt5.QtWidgets import QProgressDialog
            from PyQt5.QtCore import Qt

            progress = QProgressDialog(
                f"Calculating hash for {filename}...", "Cancel", 0, 100, self
            )
            progress.setWindowTitle("Calculating Hash")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            hash_md5 = hashlib.md5()
            hash_sha1 = hashlib.sha1()
            hash_sha256 = hashlib.sha256()
            bytes_read = 0

            with open(file_path, "rb") as f:
                while True:
                    # Check if user cancelled
                    if progress.wasCanceled():
                        progress.close()
                        return None

                    chunk = f.read(1024 * 1024)  # Read 1MB chunks
                    if not chunk:
                        break

                    hash_md5.update(chunk)
                    hash_sha1.update(chunk)
                    hash_sha256.update(chunk)
                    bytes_read += len(chunk)

                    # Update progress
                    progress_value = int((bytes_read / file_size) * 100)
                    progress.setValue(progress_value)

                    # Process events to keep UI responsive
                    from PyQt5.QtWidgets import QApplication

                    QApplication.processEvents()

            progress.close()
            return {
                "md5": hash_md5.hexdigest(),
                "sha1": hash_sha1.hexdigest(),
                "sha256": hash_sha256.hexdigest(),
            }

        except Exception as e:
            print(f"Error calculating hash: {e}")
            if "progress" in locals():
                progress.close()
            return None

    def import_evidence(self):
        """Import evidence vào case (single hoặc multiple files)"""
        # Check if we have files selected
        if not hasattr(self, "selected_files") or not self.selected_files:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file(s) evidence!")
            return

        try:
            # Xác định loại evidence
            evidence_type = (
                "VOLATILE" if self.ui.volatileRadio.isChecked() else "NON-VOLATILE"
            )

            imported_count = 0
            total_size = 0

            # Import từng file
            for file_path in self.selected_files:
                if not os.path.exists(file_path):
                    QMessageBox.warning(self, "Lỗi", f"File không tồn tại: {file_path}")
                    continue

                # Xác định tên evidence cho từng file
                custom_name = self.ui.evidenceNameEdit.text().strip()
                if custom_name:
                    # Nếu user nhập tên custom
                    if len(self.selected_files) == 1:
                        file_evidence_name = custom_name
                    else:
                        # Multiple files với custom name
                        base_name = os.path.splitext(os.path.basename(file_path))[0]
                        file_evidence_name = f"{custom_name} - {base_name}"
                else:
                    # Tự động đặt tên theo file
                    file_evidence_name = os.path.splitext(os.path.basename(file_path))[
                        0
                    ]

                # Lấy thông tin file
                file_size = (
                    os.path.getsize(file_path) if os.path.isfile(file_path) else 0
                )
                total_size += file_size

                # Tạo evidence trong database
                evidence_data = {
                    "case_id": self.case_id,
                    "evidence_type": evidence_type,
                    "name": file_evidence_name,
                    "source_path": file_path,
                    "size": file_size,
                    "mime_type": self.get_mime_type(file_path),
                }

                artefact_id = db.add_artifact(**evidence_data)

                if artefact_id and self.ui.calculateHashCheck.isChecked():
                    # Tính hash nếu được yêu cầu
                    if os.path.isfile(file_path):
                        # Use progress dialog for large files
                        if file_size > 100 * 1024 * 1024:  # > 100MB
                            hashes = self.calculate_file_hash_with_progress(
                                file_path, file_evidence_name
                            )
                        else:
                            hashes = self.calculate_file_hash(file_path)

                        if hashes and "sha256" in hashes:
                            # Use HashManager to add origin SHA256 hash
                            from database.hash_types import HashManager

                            hash_manager = HashManager(db)
                            hash_manager.add_origin_hash(artefact_id, hashes["sha256"])

                imported_count += 1

            # Hiển thị kết quả và hỏi về phân tích
            if imported_count > 0:
                # Accept dialog first
                self.accept()

                # Then ask about analysis
                reply = QMessageBox.question(
                    self.parent(),
                    "🔬 Phân tích Evidence",
                    f"✅ Import {imported_count} evidence thành công!\n\n"
                    f"🏷️ Loại: {evidence_type}\n"
                    f"📊 Tổng kích thước: {self.format_file_size(total_size)}\n\n"
                    "🤔 Bạn có muốn bắt đầu phân tích ngay không?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )

                if reply == QMessageBox.Yes:
                    self.start_analysis_workflow()
            else:
                QMessageBox.warning(
                    self, "Lỗi", "Không có file nào được import thành công!"
                )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi import evidence: {str(e)}")

    def start_analysis_workflow(self):
        """Bắt đầu workflow phân tích sau khi import"""
        # Get evidence types from the case to suggest appropriate analysis
        evidence_list = db.get_artifacts_by_case(self.case_id)

        if not evidence_list:
            return

        # Suggest analysis types based on evidence
        analysis_suggestions = self.get_analysis_suggestions(evidence_list)

        msg = QMessageBox(self.parent())
        msg.setWindowTitle("🔬 Chọn loại phân tích")
        msg.setText("📊 Chọn loại phân tích phù hợp với evidence:")
        msg.setInformativeText(
            f"📁 Case có {len(evidence_list)} evidence\n{analysis_suggestions}"
        )

        # Add analysis buttons based on evidence types
        buttons = {}
        if any("VOLATILE" in e.get("evidence_type", "") for e in evidence_list):
            buttons["memory"] = msg.addButton(
                "🧠 Memory Analysis", QMessageBox.AcceptRole
            )

        if any("NON-VOLATILE" in e.get("evidence_type", "") for e in evidence_list):
            buttons["registry"] = msg.addButton(
                "📝 Registry Analysis", QMessageBox.AcceptRole
            )
            buttons["file"] = msg.addButton("📁 File Analysis", QMessageBox.AcceptRole)
            buttons["browser"] = msg.addButton(
                "🌐 Browser Analysis", QMessageBox.AcceptRole
            )

        buttons["later"] = msg.addButton("⏳ Phân tích sau", QMessageBox.RejectRole)

        msg.exec_()

        # Handle analysis choice
        clicked = msg.clickedButton()
        main_window = self.find_main_window()

        if main_window:
            if clicked == buttons.get("memory") and hasattr(main_window, "memory_btn"):
                main_window.switch_to_browser_analysis_tab(self.case_id)
            elif clicked == buttons.get("registry") and hasattr(
                main_window, "registry_btn"
            ):
                main_window.registry_btn.click()
            elif clicked == buttons.get("file") and hasattr(main_window, "file_btn"):
                main_window.file_btn.click()
            elif clicked == buttons.get("browser") and hasattr(
                main_window, "browser_btn"
            ):
                main_window.browser_btn.click()

    def get_analysis_suggestions(self, evidence_list):
        """Đề xuất loại phân tích dựa trên evidence có sẵn"""
        suggestions = []

        volatile_count = sum(
            1 for e in evidence_list if "VOLATILE" in e.get("evidence_type", "")
        )
        nonvolatile_count = sum(
            1 for e in evidence_list if "NON-VOLATILE" in e.get("evidence_type", "")
        )

        if volatile_count > 0:
            suggestions.append(
                f"🔴 {volatile_count} Volatile evidence → Memory Analysis"
            )

        if nonvolatile_count > 0:
            suggestions.append(
                f"🔵 {nonvolatile_count} Non-volatile evidence → File/Registry/Browser Analysis"
            )

        return "\n".join(suggestions) if suggestions else "📋 Các loại phân tích có sẵn"

    def find_main_window(self):
        """Tìm main window để điều hướng"""
        widget = self
        while widget:
            parent = widget.parent()
            if parent and hasattr(parent, "switch_to_volatile_tab"):
                return parent
            if hasattr(widget, "window") and hasattr(
                widget.window(), "switch_to_volatile_tab"
            ):
                return widget.window()
            widget = parent
        return None

    def get_mime_type(self, file_path):
        """Xác định MIME type của file"""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    def format_file_size(self, size_bytes):
        """Format kích thước file"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math

        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"


class Case(QWidget):
    def __init__(self, main_window=None):
        super(Case, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.main_window = main_window
        self.current_case_id = None

        # Setup tables
        self.setup_tables()

        # Kết nối signals
        self.ui.newCaseBtn.clicked.connect(self.show_create_case_dialog)
        self.ui.refreshBtn.clicked.connect(self.load_cases)
        self.ui.editCaseBtn.clicked.connect(self.edit_selected_case)
        self.ui.deleteCaseBtn.clicked.connect(self.delete_selected_case)
        self.ui.importBtn.clicked.connect(self.show_import_evidence_dialog)
        self.ui.removeEvidenceBtn.clicked.connect(self.remove_evidence)
        #        self.ui.collectBtn.clicked.connect(self.show_collect_dialog)
        self.ui.startAnalysisBtn.clicked.connect(self.start_analysis)

        # Table events
        self.ui.casesTable.itemSelectionChanged.connect(self.on_case_selected)
        self.ui.searchCaseEdit.textChanged.connect(self.filter_cases)

        # Load data
        self.load_cases()

    def load_specific_case(self, case_id, case_data):
        """Load specific case"""
        self.current_case_id = case_id
        for r in range(self.ui.casesTable.rowCount()):
            item = self.ui.casesTable.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == case_id:
                self.ui.casesTable.selectRow(r)
                break
        title = case_data.get("title", "N/A")
        self.ui.noSelectionLabel.setText(f"📁 Case hiện tại: {title}")
        self.load_evidence()

    def setup_tables(self):
        """Cấu hình tables"""
        # Cases table
        cases_header = self.ui.casesTable.horizontalHeader()
        if cases_header:
            cases_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ui.casesTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.casesTable.setSelectionMode(QAbstractItemView.SingleSelection)

        # Bỏ grid lines và cải thiện appearance
        self.ui.casesTable.setShowGrid(False)
        self.ui.casesTable.setAlternatingRowColors(True)

        # Set row height cho table
        vertical_header = self.ui.casesTable.verticalHeader()
        if vertical_header:
            vertical_header.setDefaultSectionSize(40)

        # Evidence table
        evidence_header = self.ui.evidenceTable.horizontalHeader()
        if evidence_header:
            evidence_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ui.evidenceTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.evidenceTable.setSelectionMode(QAbstractItemView.SingleSelection)

        # Bỏ grid lines và cải thiện appearance
        self.ui.evidenceTable.setShowGrid(False)
        self.ui.evidenceTable.setAlternatingRowColors(True)

    def show_create_case_dialog(self):
        """Hiển thị dialog tạo case mới"""
        dialog = CreateCaseDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_cases()

    def show_create_case_dialog_with_workflow(self):
        """Hiển thị dialog tạo case mới với workflow tự động từ welcome dialog"""
        dialog = CreateCaseDialogWithAutoWorkflow(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_cases()

    def show_import_evidence_dialog(self):
        """Hiển thị Add Evidence Wizard khi ấn nút Add evidence"""
        if not self.current_case_id:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một case trước!")
            return

        # Sử dụng AddEvidenceWizard thay vì ImportEvidenceDialog, truyền self (QWidget) làm parent
        wizard = AddEvidenceWizard(case_id=self.current_case_id, parent=self)
        wizard.evidence_added.connect(lambda data: self.load_evidence())
        wizard.exec_()

    def load_cases(self):
        """Tải danh sách các case từ database và hiển thị lên bảng"""
        try:
            # Gọi hàm mới để lấy tất cả chi tiết trong một lần query
            cases = db.get_all_cases_details()
            if cases is None:
                cases = []

            self.ui.casesTable.setRowCount(len(cases))

            for row, case in enumerate(cases):
                # Lấy dữ liệu từ kết quả query
                case_id = case.get("case_id")
                title = case.get("title", "N/A")
                investigator = case.get("investigator_name", "N/A")
                created_at = case.get("created_at", "")
                evidence_count = case.get("evidence_count", 0)
                status = case.get("status", "N/A")
                archive_path = case.get("archive_path", "N/A")

                # Định dạng lại ngày tạo
                try:
                    formatted_date = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    ).strftime("%d/%m/%Y")
                except:
                    formatted_date = created_at

                # --- Nạp dữ liệu vào bảng ĐÚNG THỨ TỰ GIAO DIỆN ---
                # Cột 0: Tên Case
                title_item = QTableWidgetItem(title)
                # Lưu case_id vào item này để các chức năng khác sử dụng
                title_item.setData(Qt.ItemDataRole.UserRole, case_id)
                self.ui.casesTable.setItem(row, 0, title_item)

                # Cột 1: Điều tra viên
                self.ui.casesTable.setItem(row, 1, QTableWidgetItem(investigator))
                # Cột 2: Ngày tạo
                self.ui.casesTable.setItem(row, 2, QTableWidgetItem(formatted_date))
                # Cột 3: Evidence (Số lượng)
                self.ui.casesTable.setItem(
                    row, 3, QTableWidgetItem(str(evidence_count))
                )
                # Cột 4: Trạng thái
                self.ui.casesTable.setItem(row, 4, QTableWidgetItem(status))
                # Cột 5: Đường dẫn
                self.ui.casesTable.setItem(row, 5, QTableWidgetItem(archive_path))

        except Exception as e:
            QMessageBox.critical(
                self, "Lỗi Tải Dữ Liệu", f"Không thể tải danh sách case: {e}"
            )

    def on_case_selected(self):
        """Xử lý khi chọn case"""
        current_row = self.ui.casesTable.currentRow()
        if current_row >= 0:
            item = self.ui.casesTable.item(current_row, 0)
            if item:
                self.current_case_id = item.data(Qt.ItemDataRole.UserRole)

                if self.main_window:
                    self.main_window.current_case_id = self.current_case_id
                case_name = item.text()
                self.ui.noSelectionLabel.setText(f"📁 Case hiện tại: {case_name}")
                self.load_evidence()
        else:
            self.current_case_id = None
            self.ui.noSelectionLabel.setText(
                "💡 Chọn một case từ danh sách để xem và quản lý evidence"
            )
            self.ui.evidenceTable.setRowCount(0)

    def load_evidence(self):
        """Load evidence của case được chọn"""
        if not self.current_case_id:
            return

        try:
            evidence_list = db.get_artifacts_by_case(self.current_case_id)
            self.ui.evidenceTable.setRowCount(len(evidence_list))

            for row, evidence in enumerate(evidence_list):
                self.ui.evidenceTable.setItem(
                    row, 0, QTableWidgetItem(evidence.get("name", ""))
                )
                self.ui.evidenceTable.setItem(
                    row, 1, QTableWidgetItem(evidence.get("evidence_type", ""))
                )
                self.ui.evidenceTable.setItem(
                    row, 2, QTableWidgetItem(evidence.get("source_path", ""))
                )

                # Format file size
                size = evidence.get("size", 0)
                size_text = self.format_file_size(size) if size else ""
                self.ui.evidenceTable.setItem(row, 3, QTableWidgetItem(size_text))

                # Get hash
                hashes = db.get_artefact_hashes(evidence["artefact_id"])
                hash_text = hashes[0]["sha256"][:16] + "..." if hashes else ""
                self.ui.evidenceTable.setItem(row, 4, QTableWidgetItem(hash_text))

                # MIME Type
                mime_type = evidence.get("mime_type", "")
                self.ui.evidenceTable.setItem(row, 5, QTableWidgetItem(mime_type))

                # Store evidence_id
                evidence_item = self.ui.evidenceTable.item(row, 0)
                if evidence_item:
                    evidence_item.setData(
                        Qt.ItemDataRole.UserRole, evidence["artefact_id"]
                    )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load evidence: {str(e)}")

    def filter_cases(self, text):
        """Lọc cases theo text search"""
        for row in range(self.ui.casesTable.rowCount()):
            item = self.ui.casesTable.item(row, 0)
            if item:
                case_name = item.text()
                match = text.lower() in case_name.lower()
                self.ui.casesTable.setRowHidden(row, not match)

    def edit_selected_case(self):
        """Sửa case được chọn trong table"""
        current_row = self.ui.casesTable.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn case cần sửa!")
            return

        item = self.ui.casesTable.item(current_row, 0)
        if item:
            case_id = item.data(Qt.ItemDataRole.UserRole)
            self.edit_case(case_id)

    def edit_case(self, case_id):
        """Sửa case"""
        dialog = EditCaseDialog(case_id, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_cases()  # Reload danh sách cases để cập nhật thay đổi

    def delete_selected_case(self):
        """Xóa case được chọn trong table"""
        current_row = self.ui.casesTable.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn case cần xóa!")
            return

        item = self.ui.casesTable.item(current_row, 0)
        if item:
            case_id = item.data(Qt.ItemDataRole.UserRole)
            self.delete_case_by_id(case_id)

    def delete_case_by_id(self, case_id):
        """Xóa case theo ID"""
        case = db.get_case_by_id(case_id)
        if not case:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy case!")
            return

        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa case '{case['title']}'?\n"
            f"Tất cả evidence và dữ liệu liên quan sẽ bị xóa!",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                if db.delete_case(case_id):
                    QMessageBox.information(
                        self, "Thành công", "Đã xóa case thành công!"
                    )
                    # Reset current case if nó là case đang được chọn
                    if self.current_case_id == case_id:
                        self.current_case_id = None
                        self.ui.evidenceTable.setRowCount(0)
                        self.ui.noSelectionLabel.setText(
                            "💡 Chọn một case từ danh sách để xem và quản lý evidence"
                        )
                    self.load_cases()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể xóa case!")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi khi xóa case: {str(e)}")

    def remove_evidence(self):
        """Xóa evidence được chọn"""
        current_row = self.ui.evidenceTable.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn evidence cần xóa!")
            return

        evidence_item = self.ui.evidenceTable.item(current_row, 0)
        if evidence_item:
            evidence_id = evidence_item.data(Qt.ItemDataRole.UserRole)
            evidence_name = evidence_item.text()

            reply = QMessageBox.question(
                self,
                "Xác nhận xóa",
                f"Bạn có chắc chắn muốn xóa evidence '{evidence_name}'?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                try:
                    if db.delete_artifact(evidence_id):
                        QMessageBox.information(
                            self, "Thành công", "Đã xóa evidence thành công!"
                        )
                        self.load_evidence()
                        self.load_cases()  # Refresh case table để cập nhật số lượng evidence
                    else:
                        QMessageBox.critical(self, "Lỗi", "Không thể xóa evidence!")
                except Exception as e:
                    QMessageBox.critical(self, "Lỗi", f"Lỗi khi xóa evidence: {str(e)}")

    def show_collect_dialog(self):
        """Hiển thị dialog chọn loại thu thập dữ liệu"""
        if not self.current_case_id:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một case trước!")
            return

        # Tạo dialog chọn loại thu thập
        msg = QMessageBox(self)
        msg.setWindowTitle("Thu thập dữ liệu")
        msg.setText("🔍 Chọn loại dữ liệu cần thu thập:")
        msg.setInformativeText(
            "Dữ liệu Volatile sẽ mất khi tắt máy, cần thu thập ngay lập tức.\n"
            "Dữ liệu Non-volatile được lưu trữ vĩnh viễn trên ổ cứng."
        )

        volatile_btn = msg.addButton("⚡ Volatile Data", QMessageBox.AcceptRole)
        nonvolatile_btn = msg.addButton("💾 Non-volatile Data", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Hủy", QMessageBox.RejectRole)

        msg.exec_()

        if msg.clickedButton() == volatile_btn:
            self.show_volatile_collect_dialog()
        elif msg.clickedButton() == nonvolatile_btn:
            self.show_nonvolatile_collect_dialog()

    def show_volatile_collect_dialog(self):
        """Chuyển sang tab thu thập dữ liệu volatile"""
        # Tìm main window và chuyển sang tab volatile
        main_window = self.find_main_window()
        if main_window:
            # Truyền database case_id (ID thực) thay vì case_code
            main_window.switch_to_volatile_tab(self.current_case_id)
        else:
            QMessageBox.information(
                self,
                "Thông báo",
                "Vui lòng sử dụng tab 'Volatile' trong menu chính để thu thập dữ liệu.",
            )

    def find_main_window(self):
        """Tìm main window"""
        widget = self
        while widget:
            parent = widget.parent()
            if parent and hasattr(parent, "switch_to_volatile_tab"):
                return parent
            if hasattr(widget, "window") and hasattr(
                widget.window(), "switch_to_volatile_tab"
            ):
                return widget.window()
            widget = parent
        return None

    def show_nonvolatile_collect_dialog(self):
        """Chuyển sang tab thu thập dữ liệu non-volatile"""
        # Tìm main window và chuyển sang tab nonvolatile
        main_window = self.find_main_window()
        if main_window:
            # Simulate click trên nonvolatile button
            if hasattr(main_window, "nonvolatile_btn"):
                main_window.nonvolatile_btn.click()
        else:
            QMessageBox.information(
                self,
                "Thông báo",
                "Vui lòng sử dụng tab 'Non-Volatile' trong menu chính để thu thập dữ liệu.",
            )

    def start_analysis(self):
        """
        Bắt đầu workflow phân tích bằng cách chuyển sang tab phân tích
        cho case đang được chọn.
        """
        selection_model = self.ui.casesTable.selectionModel()
        if selection_model:
            selected_rows = selection_model.selectedRows()
            if not selected_rows:
                QMessageBox.warning(
                    self, "Lỗi", "Vui lòng chọn một case để bắt đầu phân tích!"
                )
                return

            # Lấy case ID từ data role của item ở cột 0 (Tên Case)
            selected_row = selected_rows[0].row()
            case_item = self.ui.casesTable.item(selected_row, 0)
            if case_item:
                case_id = case_item.data(Qt.ItemDataRole.UserRole)

                if self.main_window and hasattr(
                    self.main_window, "switch_to_memory_analysis_tab"
                ):
                    self.main_window.switch_to_memory_analysis_tab(case_id)
                else:
                    QMessageBox.critical(
                        self,
                        "Lỗi Tích Hợp",
                        "Không thể gọi đến cửa sổ chính để chuyển tab phân tích.",
                    )
            else:
                QMessageBox.warning(
                    self, "Lỗi", "Không thể xác định ID của case đã chọn."
                )
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể truy cập selection model.")

    def format_file_size(self, size_bytes):
        """Format kích thước file"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math

        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
