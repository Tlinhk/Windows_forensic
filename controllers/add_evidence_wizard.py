import os
import sys
import hashlib
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QTableWidgetItem,
    QButtonGroup,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5 import QtWidgets
from views.pages.add_evidence_wizard_ui import Ui_AddEvidenceWizard
from models.db_manager import DatabaseManager


# ========================================
# THREAD XỬ LÝ HASH CALCULATION
# ========================================

class HashCalculatorThread(QThread):
    """Thread để tính hash SHA256 không block UI"""
    
    progress = pyqtSignal(int)      # Signal báo tiến độ tính hash
    finished = pyqtSignal(str)      # Signal báo hoàn thành với hash value
    error = pyqtSignal(str)         # Signal báo lỗi

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        """Chạy thread tính hash"""
        try:
            sha256_hash = hashlib.sha256()
            with open(self.file_path, "rb") as f:
                file_size = os.path.getsize(self.file_path)
                bytes_read = 0

                # Đọc file theo chunks 4KB để tránh tốn RAM
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
                    bytes_read += len(byte_block)
                    progress = int((bytes_read / file_size) * 100)
                    self.progress.emit(progress)

            self.finished.emit(sha256_hash.hexdigest())
        except Exception as e:
            self.error.emit(str(e))


# ========================================
# MAIN WIZARD CLASS
# ========================================

class AddEvidenceWizard(QDialog):
    """
    Wizard thêm evidence vào case
    Hỗ trợ 2 mode:
    - Import Mode: Import file/folder có sẵn
    - Collect Mode: Thu thập evidence từ hệ thống
    """
    
    # Signal phát khi thêm evidence thành công
    evidence_added = pyqtSignal(dict)

    def __init__(self, case_id=None, parent=None):
        super().__init__(parent)
        self.ui = Ui_AddEvidenceWizard()
        self.ui.setupUi(self)

        # ===== KHỞI TẠO BIẾN CƠ BẢN =====
        self.case_id = case_id
        self.current_step = 0
        self.total_steps = 4  # Sẽ được cập nhật dựa trên mode

        # Sử dụng DatabaseManager instance
        self.db_manager = DatabaseManager()
        self.db_manager.connect()

        # ===== KHỞI TẠO STATE CHO COLLECT MODE =====
        self.collection_state = {
            "volatile_completed": False,        # Đã hoàn thành thu thập volatile
            "nonvolatile_completed": False,     # Đã hoàn thành thu thập non-volatile
            "volatile_started": False,          # Đã bắt đầu thu thập volatile
            "nonvolatile_started": False,       # Đã bắt đầu thu thập non-volatile
            "output_path": "",                  # Đường dẫn output
            "collected_files": [],              # Danh sách file đã thu thập
        }

        # ===== KHỞI TẠO TIMER KIỂM TRA COLLECTION =====
        from PyQt5.QtCore import QTimer
        self.collection_check_timer = QTimer()
        self.collection_check_timer.timeout.connect(self.check_collection_status)
        self.collection_check_timer.setSingleShot(False)

        # ===== SETUP UI COMPONENTS =====
        self._setup_initial_ui()

        # Center dialog nếu có parent
        if parent:
            self.setModal(True)

    def _setup_initial_ui(self):
        """Khởi tạo các component UI ban đầu"""
        self.setup_button_groups()
        self.setup_table_widget()
        self.setup_connections()
        self.update_step_display()
        self.update_step_labels()


# ========================================
# SETUP UI COMPONENTS
# ========================================

    def setup_button_groups(self):
        """Tạo button groups cho radio buttons"""
        # Group cho mode selection (Import/Collect)
        self.modeGroup = QButtonGroup()
        self.modeGroup.addButton(self.ui.importModeRadio, 0)
        self.modeGroup.addButton(self.ui.collectModeRadio, 1)
        
        # Group cho evidence type (Volatile/Non-volatile)
        self.typeGroup = QButtonGroup()
        self.typeGroup.addButton(self.ui.volatileTypeRadio, 0)
        self.typeGroup.addButton(self.ui.nonvolatileTypeRadio, 1)

    def setup_table_widget(self):
        """Setup table widget hiển thị danh sách file"""
        # Thiết lập độ rộng cột
        self.ui.fileListWidget.setColumnWidth(0, 50)   # Cột Type (icon)
        self.ui.fileListWidget.setColumnWidth(1, 250)  # Cột Name
        # Cột Path sẽ tự động stretch
        
        # Không cho phép sửa trực tiếp (chỉ chọn)
        self.ui.fileListWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def setup_connections(self):
        """Thiết lập signal connections"""
        # ===== NAVIGATION BUTTONS =====
        self.ui.nextBtn.clicked.connect(self.next_step)
        self.ui.backBtn.clicked.connect(self.previous_step)
        self.ui.finishBtn.clicked.connect(self.finish_wizard)
        self.ui.cancelBtn.clicked.connect(self.reject)

        # ===== FILE MANAGEMENT (IMPORT MODE) =====
        self.ui.addFilesBtn.clicked.connect(self.add_files)
        self.ui.addFoldersBtn.clicked.connect(self.add_folders)
        self.ui.removeFileBtn.clicked.connect(self.remove_selected_file)
        self.ui.clearAllBtn.clicked.connect(self.clear_all_files)

        # ===== COLLECTION BUTTONS (COLLECT MODE) =====
        self.ui.startVolatileBtn.clicked.connect(self.start_volatile_collection)
        self.ui.startNonvolatileBtn.clicked.connect(self.start_nonvolatile_collection)

        # ===== MODE CHANGE HANDLERS =====
        self.modeGroup.buttonClicked.connect(self.on_mode_changed)
        self.typeGroup.buttonClicked.connect(self.on_type_changed)


# ========================================
# ĐIỀU HƯỚNG VÀ QUẢN LÝ BƯỚC
# ========================================

    def next_step(self):
        """Chuyển đến bước tiếp theo"""
        if self.validate_current_step():
            if self.current_step < self.total_steps - 1:
                self.current_step += 1
                self.update_step_display()

    def previous_step(self):
        """Quay lại bước trước"""
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step_display()

    def validate_current_step(self):
        """Validate bước hiện tại trước khi chuyển tiếp"""
        is_import_mode = self.ui.importModeRadio.isChecked()

        if self.current_step == 0:
            # Bước 1: Chọn mode (luôn valid vì có default selection)
            return True
            
        elif self.current_step == 1:
            if is_import_mode:
                # Import mode Bước 2: Chọn evidence type (luôn valid)
                return True
            else:
                # Collect mode Bước 2: Thu thập volatile data
                if not self.collection_state["volatile_completed"]:
                    self.start_volatile_collection()
                    return False  # Chưa hoàn thành, không chuyển bước
                return True
                
        elif self.current_step == 2:
            if is_import_mode:
                # Import mode Bước 3: Kiểm tra file đã chọn
                if self.ui.fileListWidget.rowCount() == 0:
                    QMessageBox.warning(
                        self, "Lỗi Validation",
                        "Vui lòng chọn ít nhất một file hoặc thư mục evidence."
                    )
                    return False
                    
                # Kiểm tra tất cả file có tồn tại
                for file_path in self.get_selected_files():
                    if not os.path.exists(file_path):
                        QMessageBox.warning(
                            self, "Lỗi Validation",
                            f"File không tồn tại: {file_path}"
                        )
                        return False
                return True
            else:
                # Collect mode Bước 3: Thu thập non-volatile data
                if not self.collection_state["nonvolatile_completed"]:
                    self.start_nonvolatile_collection()
                    return False  # Chưa hoàn thành
                return True
                
        elif self.current_step == 3:
            # Import mode Bước 4: Final step
            return True
            
        return True

    def update_step_display(self):
        """Cập nhật hiển thị UI dựa trên bước hiện tại"""
        is_import_mode = self.ui.importModeRadio.isChecked()

        # ===== CẬP NHẬT TOTAL STEPS VÀ MAPPING =====
        if is_import_mode:
            self.total_steps = 4
            stacked_index = self.current_step  # 0->Step1, 1->Step2, 2->Step3, 3->Step4
        else:
            self.total_steps = 3
            # Collect mode: 0->Step1, 1->Step3 (skip Step2), 2->Step4
            if self.current_step == 0:
                stacked_index = 0  # Bước 1: Chọn Mode
            elif self.current_step == 1:
                stacked_index = 2  # Bước 3: Thu thập Volatile (bỏ qua chọn type)
            else:  # self.current_step == 2
                stacked_index = 3  # Bước 4: Thu thập Non-volatile

        # ===== CẬP NHẬT STACKED WIDGET =====
        self.ui.stackedWidget.setCurrentIndex(stacked_index)

        # ===== CẬP NHẬT VISIBILITY CỦA FRAME =====
        if stacked_index == 2:  # Step 3
            self.update_step3_visibility()
        elif stacked_index == 3:  # Step 4
            self.update_step4_visibility()

        # ===== CẬP NHẬT HIGHLIGHTING CHO STEP LABELS =====
        self._update_step_labels_highlighting(is_import_mode)

        # ===== CẬP NHẬT TITLE VÀ DESCRIPTION =====
        self._update_step_title_description(is_import_mode)

        # ===== CẬP NHẬT NAVIGATION BUTTONS =====
        self._update_navigation_buttons()

    def _update_step_labels_highlighting(self, is_import_mode):
        """Cập nhật highlighting cho step labels"""
        step_labels = [
            self.ui.step1Label, self.ui.step2Label,
            self.ui.step3Label, self.ui.step4Label,
        ]

        for i, label in enumerate(step_labels):
            # Xử lý visibility cho collect mode
            if not is_import_mode and i == 3:  # Step 4 ẩn trong collect mode
                continue

            # Mapping current step sang label index cho collect mode
            if is_import_mode:
                is_current = i == self.current_step
                is_completed = i < self.current_step
            else:
                # Collect mode step mapping: 0->0, 1->1, 2->2 (skip 3)
                if i == 0:
                    is_current = self.current_step == 0
                    is_completed = self.current_step > 0
                elif i == 1:
                    is_current = self.current_step == 1
                    is_completed = self.current_step > 1
                elif i == 2:
                    is_current = self.current_step == 2
                    is_completed = False
                else:
                    continue

            # Áp dụng style dựa trên trạng thái
            if is_current:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 12px; color: white; background-color: #4299e1;
                        padding: 8px; border-radius: 4px; margin: 2px 0; font-weight: bold;
                    }
                """)
            elif is_completed:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 12px; color: #68d391; background-color: #f0fff4;
                        padding: 8px; border-radius: 4px; margin: 2px 0;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 12px; color: #4a5568;
                        padding: 8px; border-radius: 4px; margin: 2px 0;
                    }
                """)

    def _update_step_title_description(self, is_import_mode):
        """Cập nhật title và description cho bước hiện tại"""
        if is_import_mode:
            titles = [
                "Chọn Phương Thức Thêm Evidence",
                "Chọn Loại Evidence", 
                "Chọn Nguồn Evidence",
                "Cấu Hình Evidence",
            ]
            descriptions = [
                "Chọn cách bạn muốn thêm evidence vào case.",
                "Chọn loại evidence bạn muốn thêm.",
                "Chọn nguồn các file evidence của bạn.",
                "Cấu hình và hoàn thiện cài đặt evidence.",
            ]
            title = titles[self.current_step]
            description = descriptions[self.current_step]
        else:
            # Collect mode titles/descriptions
            if self.current_step == 0:
                title = "Chọn Phương Thức Thêm Evidence"
                description = "Chọn cách bạn muốn thêm evidence vào case."
            elif self.current_step == 1:
                title = "Thu Thập Volatile Data"
                description = "Bắt đầu thu thập dữ liệu volatile (Memory, Processes, Network). Phải thực hiện trước vì dữ liệu volatile có thể bị mất."
            else:  # self.current_step == 2
                title = "Thu Thập Non-volatile Data"
                description = "Bắt đầu thu thập dữ liệu non-volatile (Disk, Files, Registry). Dữ liệu này tồn tại lâu dài và có thể thu thập sau volatile data."

        self.ui.titleLabel.setText(title)
        self.ui.descriptionLabel.setText(description)

    def _update_navigation_buttons(self):
        """Cập nhật trạng thái navigation buttons"""
        self.ui.backBtn.setEnabled(self.current_step > 0)

        if self.current_step == self.total_steps - 1:
            self.ui.nextBtn.setVisible(False)
            self.ui.finishBtn.setVisible(True)
        else:
            self.ui.nextBtn.setVisible(True)
            self.ui.finishBtn.setVisible(False)

    def update_step_labels(self):
        """Cập nhật text của step labels dựa trên mode hiện tại"""
        is_import_mode = self.ui.importModeRadio.isChecked()

        if is_import_mode:
            # Import mode steps (4 bước)
            self.ui.step1Label.setText("1. Chọn Mode")
            self.ui.step2Label.setText("2. Chọn Loại Evidence")
            self.ui.step3Label.setText("3. Chọn Nguồn Evidence")
            self.ui.step4Label.setText("4. Thêm Evidence")
            
            # Hiển thị tất cả 4 bước cho import mode
            self.ui.step2Label.setVisible(True)
            self.ui.step4Label.setVisible(True)
        else:
            # Collect mode steps (3 bước - bỏ qua chọn evidence type)
            self.ui.step1Label.setText("1. Chọn Mode")
            self.ui.step2Label.setText("2. Thu Thập Volatile Data")
            self.ui.step3Label.setText("3. Thu Thập Non-volatile Data")
            self.ui.step4Label.setText("4. Hoàn Thành")
            
            # Ẩn step 4 cho collect mode (chỉ cần 3 bước)
            self.ui.step4Label.setVisible(False)

    def update_step3_visibility(self):
        """Cập nhật visibility của frames trong step 3 dựa trên mode và type"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        if is_import_mode:
            # Import mode - luôn hiển thị import source frame
            self.ui.importSourceFrame.setVisible(True)
            self.ui.collectSourceFrame.setVisible(False)
        else:
            # Collect mode - hiển thị collect source frame
            self.ui.importSourceFrame.setVisible(False)
            self.ui.collectSourceFrame.setVisible(True)

    def update_step4_visibility(self):
        """Cập nhật visibility của frames trong step 4 dựa trên lựa chọn trước"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        if is_import_mode:
            # Import mode - hiển thị processing options
            self.ui.importConfigFrame.setVisible(True)
            self.ui.collectConfigFrame.setVisible(False)
        else:
            # Collect mode - hiển thị collection config
            self.ui.importConfigFrame.setVisible(False)
            self.ui.collectConfigFrame.setVisible(True)


# ========================================
# XỬ LÝ MODE CHANGE
# ========================================

    def on_mode_changed(self):
        """Xử lý khi thay đổi mode - Cập nhật step labels và UI visibility"""
        is_import_mode = self.ui.importModeRadio.isChecked()

        # Reset về step 0 khi thay đổi mode
        self.current_step = 0

        # Cập nhật step labels dựa trên mode mới
        self.update_step_labels()

        # Cập nhật UI visibility cho Step 3 và Step 4
        self.update_step3_visibility()
        self.update_step4_visibility()

        # Reset collection state khi chuyển sang collect mode
        if not is_import_mode:
            self.reset_collection_state()

        # Cập nhật hiển thị step hiện tại
        self.update_step_display()

    def on_type_changed(self):
        """Xử lý khi thay đổi evidence type"""
        self.update_step3_visibility()

    def reset_collection_state(self):
        """Reset collection state cho collect mode"""
        self.collection_state = {
            "volatile_completed": False,
            "nonvolatile_completed": False,
            "volatile_started": False,
            "nonvolatile_started": False,
            "output_path": "",
            "collected_files": [],
        }


# ========================================
# QUẢN LÝ FILE (IMPORT MODE)
# ========================================

    def add_files(self):
        """Thêm files vào danh sách cho import mode"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn Evidence Files", "", "All Files (*.*)"
        )

        for file_path in file_paths:
            if file_path and file_path not in self.get_selected_files():
                self.add_file_to_table(file_path)

    def add_folders(self):
        """Thêm folders vào danh sách cho import mode"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Chọn Evidence Folder", ""
        )

        if folder_path and folder_path not in self.get_selected_files():
            self.add_file_to_table(folder_path, is_folder=True)

    def add_file_to_table(self, file_path, is_folder=False):
        """Thêm file hoặc folder vào table widget"""
        filename = os.path.basename(file_path)

        # Thêm vào table widget
        row = self.ui.fileListWidget.rowCount()
        self.ui.fileListWidget.insertRow(row)

        # Cột Type (icon)
        type_item = QTableWidgetItem("📁" if is_folder else "📄")
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)  # Read-only
        self.ui.fileListWidget.setItem(row, 0, type_item)

        # Cột Name (có thể edit)
        name_item = QTableWidgetItem(filename)
        self.ui.fileListWidget.setItem(row, 1, name_item)

        # Cột Path (read-only)
        path_item = QTableWidgetItem(file_path)
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)  # Read-only
        self.ui.fileListWidget.setItem(row, 2, path_item)

    def remove_selected_file(self):
        """Xóa file đã chọn khỏi danh sách"""
        current_row = self.ui.fileListWidget.currentRow()
        if current_row >= 0:
            self.ui.fileListWidget.removeRow(current_row)

    def clear_all_files(self):
        """Xóa tất cả files khỏi danh sách"""
        self.ui.fileListWidget.setRowCount(0)

    def get_selected_files(self):
        """Lấy danh sách đường dẫn file đã chọn"""
        files = []
        for row in range(self.ui.fileListWidget.rowCount()):
            path_item = self.ui.fileListWidget.item(row, 2)  # Path ở cột 2
            if path_item:
                files.append(path_item.text())
        return files

    def get_evidence_names(self):
        """Lấy tên tùy chỉnh cho mỗi evidence"""
        names = {}
        for row in range(self.ui.fileListWidget.rowCount()):
            path_item = self.ui.fileListWidget.item(row, 2)  # Path ở cột 2
            name_item = self.ui.fileListWidget.item(row, 1)  # Name ở cột 1
            if path_item and name_item:
                path = path_item.text()
                custom_name = name_item.text().strip()
                if custom_name:
                    names[path] = custom_name
        return names


# ========================================
# QUẢN LÝ COLLECTION (COLLECT MODE)
# ========================================

    def start_volatile_collection(self):
        """Bắt đầu thu thập volatile data - Liên kết với interface thu thập volatile thực tế"""
        try:
            # Lấy reference đến main window
            main_window = self.get_main_window()
            if main_window:
                # Ẩn wizard tạm thời
                self.hide()

                # Chuyển đến tab thu thập volatile trong main interface
                if hasattr(main_window, "switch_to_volatile_tab"):
                    main_window.switch_to_volatile_tab(self.case_id)
                elif hasattr(main_window, "volatile_btn"):
                    # Fallback: Click volatile button để mở tab
                    main_window.volatile_btn.click()

                # Lấy volatile page và lưu reference
                if (hasattr(main_window, "menu_btns_list") and 
                    hasattr(main_window, "volatile_btn") and 
                    main_window.volatile_btn in main_window.menu_btns_list):
                    
                    title, factory = main_window.menu_btns_list[main_window.volatile_btn]
                    volatile_page = main_window.get_or_create_window(title, factory)
                    self.volatile_page = volatile_page

                    # Set case data nếu method tồn tại
                    if hasattr(volatile_page, "set_case_data") and self.case_id:
                        case_info = self.db_manager.get_case_by_id(self.case_id)
                        if case_info:
                            case_data = {
                                "case_id": case_info.get("case_id"),
                                "case_name": case_info.get("title", "Unknown Case"),
                                "investigator": "Current User",
                            }
                            volatile_page.set_case_data(case_data)

                    print("✅ Đã liên kết thành công với volatile collection interface")

                    # Đánh dấu đã bắt đầu thu thập volatile
                    self.collection_state["volatile_started"] = True

                    # Kết nối signals trong volatile page
                    self.connect_volatile_signals()

                    # Bắt đầu timer kiểm tra trạng thái collection
                    self.collection_check_timer.start(2000)  # Kiểm tra mỗi 2 giây
                else:
                    print("❌ Không tìm thấy volatile page trong main window")
            else:
                QMessageBox.warning(
                    self, "Lỗi",
                    "Không tìm thấy main window để chuyển đến volatile collection"
                )

        except Exception as e:
            print(f"❌ Lỗi khi bắt đầu volatile collection: {e}")
            QMessageBox.warning(
                self, "Lỗi", f"Không thể bắt đầu volatile collection: {e}"
            )

    def start_nonvolatile_collection(self):
        """Bắt đầu thu thập non-volatile data - Liên kết với interface thu thập non-volatile thực tế"""
        try:
            # Lấy reference đến main window
            main_window = self.get_main_window()
            if main_window:
                # Ẩn wizard tạm thời
                self.hide()

                # Chuyển đến tab thu thập non-volatile trong main interface
                if hasattr(main_window, "switch_to_nonvolatile_tab"):
                    main_window.switch_to_nonvolatile_tab(self.case_id)
                elif hasattr(main_window, "nonvolatile_btn"):
                    # Fallback: Click nonvolatile button để mở tab
                    main_window.nonvolatile_btn.click()

                # Lấy nonvolatile page và lưu reference
                if (hasattr(main_window, "menu_btns_list") and 
                    hasattr(main_window, "nonvolatile_btn") and 
                    main_window.nonvolatile_btn in main_window.menu_btns_list):
                    
                    title, factory = main_window.menu_btns_list[main_window.nonvolatile_btn]
                    nonvolatile_page = main_window.get_or_create_window(title, factory)
                    self.nonvolatile_page = nonvolatile_page

                    # Set case data nếu method tồn tại
                    if hasattr(nonvolatile_page, "set_case_data") and self.case_id:
                        case_info = self.db_manager.get_case_by_id(self.case_id)
                        if case_info:
                            case_data = {
                                "case_id": case_info.get("case_code", f"CASE-{self.case_id}"),
                                "case_name": case_info.get("title", "Unknown Case"),
                                "investigator": "Current User",
                                "database_case_id": self.case_id,
                            }
                            nonvolatile_page.set_case_data(case_data)

                    print("✅ Đã liên kết thành công với non-volatile collection interface")

                    # Bắt đầu timer kiểm tra trạng thái collection
                    self.collection_check_timer.start(2000)  # Kiểm tra mỗi 2 giây
                else:
                    print("❌ Không tìm thấy non-volatile page trong main window")
            else:
                QMessageBox.warning(
                    self, "Lỗi",
                    "Không tìm thấy main window để chuyển đến non-volatile collection"
                )

        except Exception as e:
            print(f"❌ Lỗi khi bắt đầu non-volatile collection: {e}")
            QMessageBox.warning(
                self, "Lỗi", f"Không thể bắt đầu non-volatile collection: {e}"
            )

    def connect_volatile_signals(self):
        """Kết nối signals từ volatile collection page"""
        try:
            if hasattr(self, "volatile_page"):
                volatile_page = self.volatile_page
                print("🔗 Đang kết nối volatile page signals...")

                # Set reference đến wizard này trong volatile page
                volatile_page.wizard_reference = self
                print("✅ Đã set wizard reference trong volatile page")

                # Kết nối signal collection_finished nếu có
                if hasattr(volatile_page, "collection_finished"):
                    try:
                        volatile_page.collection_finished.connect(
                            self.on_volatile_collection_complete
                        )
                        print("✅ Đã kết nối volatile page collection_finished signal")
                    except Exception as e:
                        print(f"❌ Không thể kết nối signal: {e}")

                # Monkey patch collection_finished method
                if hasattr(volatile_page, "collection_finished"):
                    original_method = volatile_page.collection_finished

                    def patched_collection_finished(success, message, package_path):
                        print(f"🔄 Collection finished detected: {success}, {message}, {package_path}")
                        # Gọi method gốc
                        if callable(original_method):
                            original_method(success, message, package_path)
                        # Gọi handler của chúng ta
                        self.on_volatile_collection_complete(success, message, package_path)

                    volatile_page.collection_finished = patched_collection_finished
                    print("✅ Đã monkey patch collection_finished method")

        except Exception as e:
            print(f"❌ Lỗi khi kết nối volatile signals: {e}")
            import traceback
            traceback.print_exc()

    def check_collection_status(self):
        """Kiểm tra trạng thái collection và xử lý tương ứng"""
        try:
            # Kiểm tra volatile collection - chỉ khi đã start và chưa complete
            if (hasattr(self, "volatile_page") and 
                self.collection_state["volatile_started"] and 
                not self.collection_state["volatile_completed"]):

                volatile_page = self.volatile_page

                # Kiểm tra collection đã finished bằng cách xem UI state VÀ collection thực sự đã xảy ra
                if (hasattr(volatile_page, "ui") and 
                    hasattr(volatile_page.ui, "startCollectionBtn")):

                    button_enabled = volatile_page.ui.startCollectionBtn.isEnabled()

                    # Kiểm tra collection thực sự đã xảy ra bằng cách xem evidence log
                    evidence_log_has_content = False
                    if hasattr(volatile_page.ui, "evidenceLogText"):
                        log_content = volatile_page.ui.evidenceLogText.toPlainText()
                        # Tìm dấu hiệu collection đã hoàn thành
                        evidence_log_has_content = (
                            "SHA-256:" in log_content or
                            "Package:" in log_content or
                            "Collection completed:" in log_content
                        )

                    # Chỉ trigger completion khi button enabled VÀ có evidence của collection thực tế
                    if button_enabled and evidence_log_has_content:
                        self.collection_check_timer.stop()

                        # Lấy đường dẫn output thực tế từ volatile page
                        output_path = "E:/ForensicCollection/volatile_collection/"
                        if hasattr(volatile_page.ui, "outputPathEdit"):
                            output_path = volatile_page.ui.outputPathEdit.text() or output_path

                        self.on_volatile_collection_complete(
                            True, "Thu thập volatile hoàn tất!", output_path
                        )
                        return

            # Kiểm tra non-volatile collection
            if (hasattr(self, "nonvolatile_page") and 
                not self.collection_state["nonvolatile_completed"]):
                
                nonvolatile_page = self.nonvolatile_page
                # Kiểm tra collection đã finished bằng cách xem UI state
                if (hasattr(nonvolatile_page, "ui") and 
                    hasattr(nonvolatile_page.ui, "startCollectionBtn") and 
                    nonvolatile_page.ui.startCollectionBtn.isEnabled()):
                    
                    self.collection_check_timer.stop()

                    # Lấy đường dẫn output thực tế từ nonvolatile page
                    output_path = "E:/ForensicCollection/nonvolatile_collection/"
                    if hasattr(nonvolatile_page.ui, "outputPathEdit"):
                        output_path = nonvolatile_page.ui.outputPathEdit.text() or output_path

                    self.on_nonvolatile_collection_complete(output_path)
                    return

        except Exception as e:
            print(f"❌ Lỗi khi kiểm tra collection status: {e}")
            import traceback
            traceback.print_exc()

    def on_volatile_collection_complete(self, success, message, package_path):
        """Được gọi khi volatile collection hoàn thành"""
        print(f"🎯 on_volatile_collection_complete: success={success}, message={message}, path={package_path}")

        # Tránh gọi nhiều lần
        if self.collection_state["volatile_completed"]:
            print("⚠️ Volatile collection đã hoàn thành, bỏ qua duplicate call")
            return

        self.collection_state["volatile_completed"] = True
        if success and package_path:
            self.collection_state["output_path"] = package_path
        else:
            self.collection_state["output_path"] = "E:/ForensicCollection/volatile_collection/"

        print(f"📊 Collection state updated: {self.collection_state}")

        # Dừng timer để tránh gọi thêm
        if hasattr(self, "collection_check_timer"):
            self.collection_check_timer.stop()

        # Hiển thị dialog completion từ collection interface
        if success:
            print("✅ Hiển thị completion dialog...")
            QMessageBox.information(
                None,  # Hiển thị dưới dạng independent dialog
                "Hoàn thành Thu thập Forensic",
                f"✅ {message}\n\n"
                f"📦 Evidence Package: {os.path.basename(package_path) if package_path else 'volatile_collection.zip'}\n"
                f"📁 Đường dẫn: {package_path}\n\n"
                f"🔐 Đã tính toán hash SHA-256\n"
                f"📋 Chain of custody đã được ghi lại",
            )
        else:
            print("❌ Hiển thị error dialog...")
            QMessageBox.warning(
                None,
                "Lỗi Thu thập Forensic",
                f"❌ {message}\n\n"
                f"Quá trình thu thập gặp lỗi. Vui lòng kiểm tra:\n"
                f"• Tên case không chứa ký tự đặc biệt\n"
                f"• Đường dẫn lưu trữ hợp lệ\n"
                f"• Đủ quyền truy cập\n\n"
                f"Thử lại với case name bằng tiếng Anh.",
            )

        # Hiển thị wizard lại sau khi user click OK
        print("🔄 Hiển thị wizard lại...")
        self.show()
        self.raise_()  # Đưa lên foreground
        self.activateWindow()

        # Cập nhật status display với thông tin collection
        print("📊 Cập nhật collection status...")
        self.update_collection_status(volatile_done=True)

        # Cập nhật step display
        print("🎯 Cập nhật step display...")
        self.update_step_display()

        print(f"✅ Volatile collection completed: {message}, wizard hiển thị với completion status")

    def on_nonvolatile_collection_complete(self, output_path=None):
        """Được gọi khi non-volatile collection hoàn thành"""
        # Tránh gọi nhiều lần
        if self.collection_state["nonvolatile_completed"]:
            print("⚠️ Non-volatile collection đã hoàn thành, bỏ qua duplicate call")
            return

        self.collection_state["nonvolatile_completed"] = True
        if output_path:
            self.collection_state["output_path"] = output_path

        # Dừng timer để tránh gọi thêm
        if hasattr(self, "collection_check_timer"):
            self.collection_check_timer.stop()

        # Hiển thị completion dialog từ collection interface
        QMessageBox.information(
            None,  # Hiển thị dưới dạng independent dialog
            "Hoàn thành Thu thập Forensic",
            f"✅ Thu thập Non-volatile hoàn tất!\n\n"
            f"📦 Evidence Package: {os.path.basename(output_path) if output_path else 'nonvolatile_collection.zip'}\n"
            f"📁 Đường dẫn: {output_path}\n\n"
            f"🔐 Đã tính toán hash SHA-256\n"
            f"📋 Chain of custody đã được ghi lại\n\n"
            f"🎉 Thu thập Evidence hoàn tất!",
        )

        # Hiển thị wizard lại sau khi user click OK
        self.show()
        self.raise_()  # Đưa lên foreground
        self.activateWindow()

        # Cập nhật status display với thông tin collection
        self.update_collection_status(nonvolatile_done=True)

        # Cập nhật step display để hiển thị completion - sẽ enable Finish button
        self.update_step_display()

        print("✅ Non-volatile collection completed, wizard hiển thị với completion status")

    def wizard_collection_finished(self, collection_type, success, message, package_path):
        """Method được gọi trực tiếp từ collection pages"""
        print(f"🎯 wizard_collection_finished: {collection_type}, {success}, {message}, {package_path}")

        if collection_type == "volatile":
            self.on_volatile_collection_complete(success, message, package_path)
        elif collection_type == "nonvolatile":
            self.on_nonvolatile_collection_complete(package_path)

    def update_collection_status(self, volatile_done=False, nonvolatile_done=False):
        """Cập nhật hiển thị trạng thái collection"""
        if volatile_done:
            output_path = self.collection_state.get("output_path", "E:/Evidence/volatile_collection/")
            package_name = os.path.basename(output_path) if output_path else "volatile_collection.zip"

            self.ui.volatileInfoLabel.setText(
                f"✅ HOÀN THÀNH THU THẬP VOLATILE DATA\n\n"
                f"📦 Package: {package_name}\n"
                f"📁 Đường dẫn: {output_path}\n"
                f"🔐 Hash SHA-256 đã được tính toán\n"
                f"📋 Chain of custody đã được ghi lại\n\n"
                f"➡️ Bấm Next để tiếp tục thu thập Non-volatile data"
            )
            self.ui.volatileInfoLabel.setStyleSheet("""
                QLabel {
                    font-size: 13px; font-weight: bold; color: #2d5016; background-color: #ecfdf5;
                    border: 3px solid #22c55e; border-radius: 10px; padding: 20px;
                    text-align: left; line-height: 1.4;
                }
            """)
            self.ui.volatileInfoLabel.setWordWrap(True)
            self.ui.volatileInfoLabel.setMaximumWidth(650)
            self.ui.startVolatileBtn.setText("✅ Volatile Collection Complete")
            self.ui.startVolatileBtn.setEnabled(False)

            # Cập nhật description cho step hiện tại
            if self.current_step == 1:  # Collect mode step 2 (volatile collection)
                self.ui.descriptionLabel.setText(
                    "✅ Thu thập volatile data hoàn thành thành công! "
                    "Tất cả volatile evidence đã được thu thập và đóng gói. "
                    "Click Next để tiếp tục thu thập Non-volatile data."
                )

        if nonvolatile_done:
            output_path = self.collection_state.get("output_path", "E:/Evidence/nonvolatile_collection/")
            package_name = os.path.basename(output_path) if output_path else "nonvolatile_collection.zip"

            self.ui.nonvolatileInfoLabel.setText(
                f"✅ HOÀN THÀNH THU THẬP NON-VOLATILE DATA\n\n"
                f"📦 Package: {package_name}\n"
                f"📁 Đường dẫn: {output_path}\n"
                f"🔐 Hash SHA-256 đã được tính toán\n"
                f"📋 Chain of custody đã được ghi lại\n\n"
                f"🎉 TẤT CẢ EVIDENCE ĐÃ THU THẬP HOÀN TẤT!\n"
                f"➡️ Bấm Finish để hoàn thành wizard"
            )
            self.ui.nonvolatileInfoLabel.setStyleSheet("""
                QLabel {
                    font-size: 13px; font-weight: bold; color: #1e3a8a; background-color: #eff6ff;
                    border: 3px solid #3b82f6; border-radius: 10px; padding: 20px;
                    text-align: left; line-height: 1.4;
                }
            """)
            self.ui.nonvolatileInfoLabel.setWordWrap(True)
            self.ui.nonvolatileInfoLabel.setMaximumWidth(650)
            self.ui.startNonvolatileBtn.setText("✅ Non-volatile Collection Complete")
            self.ui.startNonvolatileBtn.setEnabled(False)

            # Cập nhật description cho step hiện tại
            if self.current_step == 2:  # Collect mode step 3 (non-volatile collection)
                self.ui.descriptionLabel.setText(
                    "🎉 Tất cả thu thập evidence hoàn thành thành công! "
                    "Cả volatile và non-volatile data đã được thu thập và đóng gói. "
                    "Click Finish để hoàn thành wizard và tiến hành phân tích."
                )


# ========================================
# TÍNH TOÁN HASH
# ========================================

    def calculate_file_hash(self, file_path):
        """Tính SHA256 hash của một file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"❌ Lỗi tính hash cho {file_path}: {e}")
            return None

    def calculate_file_hash_with_progress(self, file_path, filename):
        """Tính SHA256 hash với progress dialog cho file lớn"""
        try:
            file_size = os.path.getsize(file_path)

            # Tạo progress dialog
            progress = QProgressDialog(
                f"Đang tính hash cho {filename}...", "Hủy", 0, 100, self
            )
            progress.setWindowTitle("Tính Hash")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            sha256_hash = hashlib.sha256()
            bytes_read = 0

            with open(file_path, "rb") as f:
                while True:
                    # Kiểm tra user có cancel không
                    if progress.wasCanceled():
                        progress.close()
                        return None

                    byte_block = f.read(1024 * 1024)  # Đọc chunks 1MB cho file lớn
                    if not byte_block:
                        break

                    sha256_hash.update(byte_block)
                    bytes_read += len(byte_block)

                    # Cập nhật progress
                    progress_value = int((bytes_read / file_size) * 100)
                    progress.setValue(progress_value)

                    # Process events để giữ UI responsive
                    from PyQt5.QtWidgets import QApplication
                    QApplication.processEvents()

            progress.close()
            return sha256_hash.hexdigest()

        except Exception as e:
            print(f"❌ Lỗi tính hash cho {file_path}: {e}")
            if "progress" in locals():
                progress.close()
            return None


# ========================================
# XỬ LÝ DATABASE
# ========================================

    def add_evidence_to_database(self, evidence_data):
        """Thêm evidence vào database"""
        try:
            # Kiểm tra case_id có hợp lệ không
            if not self.case_id:
                return None

            results = []

            if evidence_data["mode"] == "import":
                # Xử lý nhiều file cho import mode
                for file_path in evidence_data["files"]:
                    if not os.path.exists(file_path):
                        continue

                    file_size = os.path.getsize(file_path)
                    filename = os.path.basename(file_path)

                    # Lấy tên tùy chỉnh cho evidence này (nếu có)
                    evidence_names = self.get_evidence_names()
                    evidence_name = evidence_names.get(file_path, filename)

                    # Thêm artifact vào database
                    artifact_id = self.db_manager.add_artifact(
                        case_id=self.case_id,
                        name=evidence_name,
                        source_path=file_path,
                        evidence_type=evidence_data["evidence_type"],
                        size=file_size,
                        mime_type=self.get_mime_type(file_path),
                    )

                    # Tính và lưu hash nếu được yêu cầu
                    hash_value = ""
                    if artifact_id and evidence_data.get("calculate_hash", False):
                        if os.path.isfile(file_path):
                            print(f"🔒 Đang tính hash cho {filename} ({self.format_file_size(file_size)})")

                            # Sử dụng thread-based hash calculation cho file lớn
                            if file_size > 100 * 1024 * 1024:  # > 100MB - hiển thị progress
                                hash_value = self.calculate_file_hash_with_progress(file_path, filename)
                            else:
                                hash_value = self.calculate_file_hash(file_path)

                            if hash_value:
                                print(f"✅ Hash đã tính: {hash_value[:16]}...")
                                # Sử dụng HashManager để thêm origin hash
                                from models.hash_types import HashManager
                                hash_manager = HashManager(self.db_manager)
                                result = hash_manager.add_origin_hash(artifact_id, hash_value)
                                print(f"📊 Kết quả thêm hash: {result}")
                            else:
                                print(f"❌ Không thể tính hash cho {filename}")

                    if artifact_id:
                        evidence_record = {
                            "id": artifact_id,
                            "case_id": self.case_id,
                            "evidence_name": evidence_name,
                            "evidence_type": evidence_data["evidence_type"],
                            "file_path": file_path,
                            "file_size": file_size,
                            "hash_value": hash_value,
                            "collection_method": evidence_data["mode"],
                            "source_type": "import",
                            "status": "imported",
                        }
                        results.append(evidence_record)
            else:
                # Collect mode - tạo placeholder record
                collection_name = f"Collection_{evidence_data['evidence_type']}_{self.case_id}"
                output_path = evidence_data["output_path"]

                # Xác định MIME type dựa trên file đã thu thập thực tế
                mime_type = "application/octet-stream"  # Default
                if output_path and os.path.exists(output_path):
                    mime_type = self.get_mime_type(output_path)
                    file_size = os.path.getsize(output_path)
                else:
                    file_size = 0

                artifact_id = self.db_manager.add_artifact(
                    case_id=self.case_id,
                    name=collection_name,
                    source_path=output_path,
                    evidence_type=evidence_data["evidence_type"],
                    size=file_size,
                    mime_type=mime_type,
                )

                if artifact_id:
                    evidence_record = {
                        "id": artifact_id,
                        "case_id": self.case_id,
                        "evidence_name": collection_name,
                        "evidence_type": evidence_data["evidence_type"],
                        "file_path": output_path,
                        "file_size": file_size,
                        "hash_value": "",
                        "collection_method": evidence_data["mode"],
                        "source_type": "collection_workflow",
                        "status": "collected",
                    }
                    results.append(evidence_record)

            return results if results else None

        except Exception as e:
            print(f"❌ Lỗi thêm evidence vào database: {str(e)}")
            return None


# ========================================
# HOÀN THÀNH WIZARD
# ========================================

    def finish_wizard(self):
        """Hoàn thành wizard"""
        if not self.validate_current_step():
            return

        wizard_data = self.get_wizard_data()

        # Cho import mode với tính hash
        if wizard_data["mode"] == "import" and wizard_data.get("calculate_hash", False):
            # Xử lý files với hash calculation
            self.process_files_with_hash(wizard_data)
        else:
            # Không cần tính hash hoặc collect mode
            self.finalize_evidence_addition(wizard_data)

    def process_files_with_hash(self, wizard_data):
        """Xử lý files với hash calculation"""
        # Sẽ được implement cho hash calculation
        # Hiện tại chỉ finalize không có hash
        self.finalize_evidence_addition(wizard_data)

    def finalize_evidence_addition(self, wizard_data):
        """Hoàn thành quá trình thêm evidence"""
        # Thêm vào database
        evidence_records = self.add_evidence_to_database(wizard_data)

        if evidence_records:
            count = len(evidence_records)
            if wizard_data["mode"] == "import":
                msg = f"✅ Đã import thành công {count} evidence file(s) vào case!"
            else:
                msg = f"✅ Hoàn thành workflow thu thập evidence!\nOutput: {wizard_data['output_path']}"

            QMessageBox.information(self, "Thành Công", msg)

            # Phát signal với evidence data
            for record in evidence_records:
                self.evidence_added.emit(record)

            # Nếu là import và có file ảnh đĩa, tự động chuyển đến File Analysis và nạp tệp
            if wizard_data.get("mode") == "import":
                image_file_path = self.find_first_disk_image_file(wizard_data.get("files", []))
                if image_file_path:
                    main_window = self.get_main_window()
                    if main_window and hasattr(main_window, "switch_to_file_analysis_tab"):
                        try:
                            from PyQt5.QtCore import QTimer
                            QTimer.singleShot(
                                100,
                                lambda: main_window.switch_to_file_analysis_tab(
                                    case_id=self.case_id, evidence_path=image_file_path
                                ),
                            )
                        except Exception:
                            pass

            # Đóng dialog
            self.accept()
        else:
            QMessageBox.critical(
                self, "Lỗi", "Không thể thêm evidence vào database. Vui lòng thử lại."
            )

    def get_wizard_data(self):
        """Thu thập tất cả dữ liệu wizard"""
        is_import_mode = self.ui.importModeRadio.isChecked()

        data = {
            "mode": "import" if is_import_mode else "collect",
            "evidence_type": "volatile" if self.ui.volatileTypeRadio.isChecked() else "nonvolatile",
            "case_id": self.case_id,
        }

        if is_import_mode:
            data.update({
                "files": self.get_selected_files(),
                "calculate_hash": self.ui.calculateHashCheck.isChecked(),
                "verify_integrity": self.ui.verifyIntegrityCheck.isChecked(),
                "create_backup": self.ui.createBackupCheck.isChecked(),
            })
        else:
            data.update({
                "collection_state": self.collection_state,
                "output_path": self.collection_state["output_path"],
                "collected_files": self.collection_state["collected_files"],
            })

        return data


# ========================================
# UTILITY FUNCTIONS
# ========================================

    def get_main_window(self):
        """Lấy reference đến main window"""
        parent = self.parent()
        while parent:
            # Tìm main window có volatile_btn attribute
            if hasattr(parent, "volatile_btn") and hasattr(parent, "menu_btns_list"):
                return parent
            parent = parent.parent()
        return None

    def format_file_size(self, size_bytes):
        """Format file size để hiển thị"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"

    def get_mime_type(self, file_path):
        """Xác định MIME type của file với hỗ trợ forensic file types"""
        import mimetypes
        import os

        # Custom mapping cho các file type forensic thường gặp
        forensic_mime_types = {
            ".log": "text/plain",
            ".txt": "text/plain", 
            ".csv": "text/csv",
            ".raw": "image/RAM",          # Memory dumps (custom forensic MIME type)
            ".mem": "image/RAM",          # Memory dumps
            ".vmem": "image/RAM",         # VMware memory dumps
            ".dmp": "application/octet-stream",  # Windows crash dumps
            ".dd": "image/disk",          # Disk images (custom forensic MIME type)
            ".e01": "image/disk",         # EnCase evidence files
            ".img": "image/disk",         # Disk images
            ".001": "image/disk",         # Split disk images
            ".pcap": "application/vnd.tcpdump.pcap",    # Network captures
            ".pcapng": "application/vnd.tcpdump.pcap",
            ".evtx": "application/x-ms-evtx",           # Windows event logs (custom)
            ".reg": "text/plain",                       # Registry files
            ".hiv": "application/x-registry-hive",      # Registry hives (custom)
            ".pf": "application/x-prefetch",            # Prefetch files (custom)
            ".conf": "text/plain",                      # Config files
        }

        # Lấy extension của file
        _, ext = os.path.splitext(file_path.lower())

        # Kiểm tra custom mapping trước
        if ext in forensic_mime_types:
            return forensic_mime_types[ext]

        # Fallback về mimetypes library
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    def find_first_disk_image_file(self, paths):
        """Tìm file ảnh đĩa đầu tiên trong danh sách theo đuôi mở rộng quen thuộc."""
        try:
            if not paths:
                return None
            supported_exts = {".dd", ".img", ".raw", ".e01", ".001", ".E01"}
            for file_path in paths:
                try:
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(file_path)
                        if ext.lower() in {e.lower() for e in supported_exts}:
                            return file_path
                except Exception:
                    continue
            return None
        except Exception:
            return None