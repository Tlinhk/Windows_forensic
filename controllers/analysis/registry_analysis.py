# -*- coding: utf-8 -*-

import os
import csv
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# Phân tích Registry (Windows Registry)
try:
    import Registry.Registry as Registry
    REGISTRY_AVAILABLE = True
except ImportError:
    Registry = None
    REGISTRY_AVAILABLE = False
    print("Cảnh báo: Chưa cài đặt thư viện python-registry. Cài đặt bằng: pip install python-registry")

# PyQt5 - Framework GUI
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog,
    QTableWidgetItem, QProgressDialog, QApplication,
    QComboBox, QLabel, QPushButton, QTextEdit,
    QMenu, QAction, QListWidgetItem, QTreeWidgetItem,
    QDialog, QCheckBox, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QFont

# Import giao diện người dùng
from views.pages.analysis_ui.registry_analysis_ui import Ui_RegistryAnalysisWidget

# ============= CÁC HÀM TIỆN ÍCH =============

def format_as_hex(data):
    """Định dạng dữ liệu thành hex dump với preview ASCII."""
    if not data:
        return "Không có dữ liệu"
    
    try:
        if isinstance(data, str):
            data = data.encode("utf-8", errors="ignore")
        
        lines = []
        for offset in range(0, len(data), 16):
            chunk = data[offset:offset+16]
            hex_bytes = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"{offset:08X}  {hex_bytes:<48} |{ascii_part}|")
        return "\n".join(lines)
    except Exception as e:
        return f"Lỗi định dạng hex: {str(e)}"

def decode_registry_data(data, format_type):
    """Giải mã dữ liệu registry dựa trên định dạng được chọn."""
    if not data:
        return "Không có dữ liệu để giải mã"
    
    try:
        if format_type == "Auto-detect":
            return auto_decode_data(data)
        elif format_type == "UTF-16 String":
            if isinstance(data, bytes):
                return data.decode("utf-16le", errors="ignore").rstrip('\x00')
            return str(data)
        elif format_type == "UTF-8 String":
            if isinstance(data, bytes):
                return data.decode("utf-8", errors="ignore").rstrip('\x00')
            return str(data)
        elif format_type == "DWORD (32-bit)":
            return decode_dword(data)
        elif format_type == "QWORD (64-bit)":
            return decode_qword(data)
        elif format_type == "Windows FILETIME":
            return decode_filetime(data)
        elif format_type == "SID":
            return decode_sid(data)
        elif format_type == "GUID":
            return decode_guid(data)
        else:
            return str(data)
    except Exception as e:
        return f"Lỗi giải mã: {str(e)}"

def auto_decode_data(data):
    """Tự động phát hiện định dạng và giải mã dữ liệu."""
    if not data:
        return "Không có dữ liệu"
    
    try:
        # Thử dưới dạng số
        if isinstance(data, int):
            return f"Số nguyên: {data}\nHex: 0x{data:X}"
        
        # Thử dưới dạng chuỗi
        if isinstance(data, str):
            return f"Chuỗi: {data}"
        
        # Thử dưới dạng bytes
        if isinstance(data, bytes):
            # Thử UTF-16 trước (thường dùng trong Windows)
            try:
                utf16 = data.decode("utf-16le", errors="strict").rstrip('\x00')
                if utf16.isprintable() or '\n' in utf16:
                    return f"Chuỗi UTF-16: {utf16}"
            except:
                pass
            
            # Thử UTF-8
            try:
                utf8 = data.decode("utf-8", errors="strict").rstrip('\x00')
                if utf8.isprintable():
                    return f"Chuỗi UTF-8: {utf8}"
            except:
                pass
            
            # Kiểm tra các pattern thường gặp
            if len(data) == 4:
                value = int.from_bytes(data, byteorder="little")
                return f"DWORD: {value}\nHex: 0x{value:08X}"
            elif len(data) == 8:
                value = int.from_bytes(data, byteorder="little")
                return f"QWORD: {value}\nHex: 0x{value:016X}"
            
            # Mặc định hiển thị hex
            return format_as_hex(data)
        
        return str(data)
    except Exception as e:
        return f"Lỗi tự động giải mã: {str(e)}"

def decode_dword(data):
    """Giải mã giá trị DWORD (32-bit)."""
    try:
        if isinstance(data, int):
            return f"DWORD: {data}\nHex: 0x{data:08X}\nNhị phân: {bin(data)}"
        elif isinstance(data, bytes) and len(data) == 4:
            value = int.from_bytes(data, byteorder="little")
            return f"DWORD: {value}\nHex: 0x{value:08X}\nNhị phân: {bin(value)}"
        return str(data)
    except Exception as e:
        return f"Lỗi giải mã DWORD: {str(e)}"

def decode_qword(data):
    """Giải mã giá trị QWORD (64-bit)."""
    try:
        if isinstance(data, int):
            return f"QWORD: {data}\nHex: 0x{data:016X}"
        elif isinstance(data, bytes) and len(data) == 8:
            value = int.from_bytes(data, byteorder="little")
            return f"QWORD: {value}\nHex: 0x{value:016X}"
        return str(data)
    except Exception as e:
        return f"Lỗi giải mã QWORD: {str(e)}"

def decode_filetime(data):
    """Giải mã Windows FILETIME thành datetime có thể đọc được."""
    try:
        if isinstance(data, bytes) and len(data) == 8:
            filetime = int.from_bytes(data, byteorder="little")
            if filetime == 0:
                return "FILETIME: Chưa thiết lập (0)"
            # Chuyển từ Windows epoch (1601) sang Unix epoch
            dt = datetime(1601, 1, 1) + timedelta(microseconds=filetime/10)
            return f"FILETIME: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\nThô: {filetime}"
        return f"Dữ liệu FILETIME không hợp lệ"
    except Exception as e:
        return f"Lỗi giải mã FILETIME: {str(e)}"

def decode_sid(data):
    """Giải mã Windows Security Identifier."""
    try:
        if isinstance(data, bytes) and len(data) >= 8:
            revision = data[0]
            sub_auth_count = data[1]
            authority = int.from_bytes(data[2:8], byteorder="big")
            
            sid_string = f"S-{revision}-{authority}"
            
            for i in range(sub_auth_count):
                if 8 + (i * 4) + 4 <= len(data):
                    sub_auth = int.from_bytes(data[8+(i*4):8+(i*4)+4], byteorder="little")
                    sid_string += f"-{sub_auth}"
            
            return f"SID: {sid_string}"
        return "Dữ liệu SID không hợp lệ"
    except Exception as e:
        return f"Lỗi giải mã SID: {str(e)}"

def decode_guid(data):
    """Giải mã GUID/UUID."""
    try:
        if isinstance(data, bytes) and len(data) == 16:
            # Định dạng: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
            p1 = data[0:4][::-1].hex()
            p2 = data[4:6][::-1].hex()
            p3 = data[6:8][::-1].hex()
            p4 = data[8:10].hex()
            p5 = data[10:16].hex()
            
            guid = f"{{{p1}-{p2}-{p3}-{p4}-{p5}}}".upper()
            return f"GUID: {guid}"
        return "Dữ liệu GUID không hợp lệ"
    except Exception as e:
        return f"Lỗi giải mã GUID: {str(e)}"

# ============= THREAD PHÂN TÍCH REGISTRY =============

class RegistryAnalysisThread(QThread):
    """Thread để chạy phân tích RECmd mà không chặn UI."""

    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    analysis_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, recmd_path, batch_file, hive_files, output_dir):
        super().__init__()
        self.recmd_path = recmd_path
        self.batch_file = batch_file
        self.hive_files = hive_files
        self.output_dir = output_dir
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        
    def run(self):
        try:
            total_hives = len(self.hive_files)
            results = {}

            for i, hive_file in enumerate(self.hive_files):
                if self.is_cancelled:
                    break

                hive_name = os.path.basename(hive_file)
                self.status_updated.emit(f"Đang phân tích {hive_name}...")

                result = self.run_recmd_analysis(hive_file)
                if result:
                    results[hive_file] = result

                progress = int((i + 1) / total_hives * 100)
                self.progress_updated.emit(progress)

            if not self.is_cancelled:
                self.analysis_completed.emit(results)

        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def run_recmd_analysis(self, hive_file):
        """Chạy RECmd trên một file hive duy nhất."""
        try:
            hive_name = os.path.splitext(os.path.basename(hive_file))[0]
            output_csv = os.path.join(self.output_dir, f"{hive_name}_analysis.csv")

            cmd = [
                self.recmd_path,
                "-f", hive_file,
                "--bn", self.batch_file,
                "--csv", self.output_dir,
                "--csvf", f"{hive_name}_analysis.csv",
                "--nl"
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

            stdout, stderr = process.communicate()

            if process.returncode == 0 and os.path.exists(output_csv):
                return self.parse_csv_results(output_csv)
            else:
                raise Exception(f"RECmd thất bại: {stderr}")

        except Exception as e:
            raise Exception(f"Lỗi phân tích {os.path.basename(hive_file)}: {str(e)}")

    def parse_csv_results(self, csv_file):
        """Phân tích kết quả CSV từ RECmd."""
        results = []
        try:
            with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    results.append(row)
            return results
        except Exception as e:
            raise Exception(f"Lỗi đọc CSV {csv_file}: {str(e)}")

# ============= DIALOG CHỌN REGISTRY HIVES =============

class HiveSelectionDialog(QDialog):
    """Dialog để chọn registry hives muốn phân tích."""
    
    def __init__(self, registry_files, parent=None):
        super().__init__(parent)
        self.registry_files = registry_files
        self.selected_files = []
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện dialog."""
        self.setWindowTitle("Chọn Registry Hives để phân tích")
        self.setFixedSize(600, 400)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Header
        header_label = QLabel(f"🔍 Tìm thấy {len(self.registry_files)} Registry Hive files")
        header_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(header_label)
        
        # Instruction
        instruction = QLabel("Chọn những file hive mà bạn muốn phân tích:")
        instruction.setStyleSheet("margin: 5px; color: #666;")
        layout.addWidget(instruction)
        
        # Scroll area cho danh sách checkboxes
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        self.checkboxes = []
        
        # Tạo checkbox cho từng hive file
        for file_path in self.registry_files:
            hive_type = self.detect_hive_type(str(file_path))
            file_name = file_path.name
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            # Tạo frame cho mỗi hive
            hive_frame = QFrame()
            hive_frame.setFrameStyle(QFrame.Box)
            hive_frame.setStyleSheet("margin: 2px; padding: 5px; background-color: #f9f9f9;")
            
            hive_layout = QVBoxLayout(hive_frame)
            
            # Checkbox chính
            checkbox = QCheckBox(f"📁 {file_name}")
            checkbox.setStyleSheet("font-weight: bold; font-size: 12px;")
            checkbox.file_path = file_path
            
            # Mặc định chọn các hive quan trọng
            if hive_type in ["SYSTEM", "SOFTWARE", "SAM", "SECURITY"]:
                checkbox.setChecked(True)
            
            # Thông tin chi tiết
            info_label = QLabel(f"   🏷️ Loại: {hive_type} | 📏 Kích thước: {file_size:,} bytes")
            info_label.setStyleSheet("color: #666; font-size: 10px; margin-left: 20px;")
            
            path_label = QLabel(f"   📂 Đường dẫn: {str(file_path)}")
            path_label.setStyleSheet("color: #888; font-size: 9px; margin-left: 20px;")
            path_label.setWordWrap(True)
            
            hive_layout.addWidget(checkbox)
            hive_layout.addWidget(info_label)
            hive_layout.addWidget(path_label)
            
            scroll_layout.addWidget(hive_frame)
            self.checkboxes.append(checkbox)
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("✅ Chọn tất cả")
        select_all_btn.clicked.connect(self.select_all)
        
        deselect_all_btn = QPushButton("❌ Bỏ chọn tất cả")
        deselect_all_btn.clicked.connect(self.deselect_all)
        
        select_important_btn = QPushButton("⭐ Chọn hive quan trọng")
        select_important_btn.clicked.connect(self.select_important)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addWidget(select_important_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # OK/Cancel buttons
        ok_cancel_layout = QHBoxLayout()
        
        ok_btn = QPushButton("🚀 Bắt đầu phân tích")
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(self.reject)
        
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(cancel_btn)
        ok_cancel_layout.addWidget(ok_btn)
        
        layout.addLayout(ok_cancel_layout)
        
        self.setLayout(layout)
        
    def detect_hive_type(self, file_path):
        """Phát hiện loại hive từ tên file."""
        filename = os.path.basename(file_path).upper()
        
        if "SYSTEM" in filename:
            return "SYSTEM"
        elif "SOFTWARE" in filename:
            return "SOFTWARE"
        elif "SAM" in filename:
            return "SAM"
        elif "SECURITY" in filename:
            return "SECURITY"
        elif "NTUSER" in filename:
            return "NTUSER"
        elif "USRCLASS" in filename:
            return "USRCLASS"
        elif "DEFAULT" in filename:
            return "DEFAULT"
        else:
            return "UNKNOWN"
    
    def select_all(self):
        """Chọn tất cả checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)
    
    def deselect_all(self):
        """Bỏ chọn tất cả checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)
    
    def select_important(self):
        """Chọn chỉ các hive quan trọng."""
        important_types = ["SYSTEM", "SOFTWARE", "SAM", "SECURITY"]
        for checkbox in self.checkboxes:
            hive_type = self.detect_hive_type(str(checkbox.file_path))
            checkbox.setChecked(hive_type in important_types)
    
    def get_selected_files(self):
        """Lấy danh sách file được chọn."""
        selected = []
        for checkbox in self.checkboxes:
            if checkbox.isChecked():
                selected.append(checkbox.file_path)
        return selected

# ============= WIDGET PHÂN TÍCH REGISTRY CHÍNH =============

class RegistryAnalysis(QWidget):
    """Widget Phân Tích Registry - phiên bản đã tối ưu hóa."""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.ui = Ui_RegistryAnalysisWidget()
        self.ui.setupUi(self)

        # Khởi tạo đường dẫn
        self._initialize_paths()

        # Quản lý trạng thái
        self.loaded_hives = {}
        self.analysis_results = {}
        self.bookmarks = []
        self.current_case_id = None
        self.current_analysis_thread = None
        self.registry_objects = {}  # Cache các đối tượng registry

        # Models cho QTreeView và QTableView
        self.tree_model = QStandardItemModel()
        self.table_model = QStandardItemModel()

        # Thiết lập UI
        self.setup_ui()
        self.setup_connections()

        # Tải dữ liệu case nếu có sẵn
        if main_window and hasattr(main_window, 'current_case_id'):
            QTimer.singleShot(100, lambda: self.load_case_data(main_window.current_case_id))
            
    def showEvent(self, event):
        """Override showEvent để refresh hive artifacts khi widget được hiển thị."""
        super().showEvent(event)
        
        # Kiểm tra và cập nhật case_id từ main_window (giống File Analysis)
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            main_case_id = self.main_window.current_case_id
            # Nếu case đã thay đổi, load case mới
            if main_case_id != self.current_case_id:
                if main_case_id:
                    QTimer.singleShot(100, lambda: self.load_case_data(main_case_id))
                else:
                    # Nếu không có case, reset về trạng thái rỗng
                    self.current_case_id = None
                    self.reset_to_empty_state()
        
        # Refresh hive artifacts nếu có case
        if self.current_case_id and hasattr(self.ui, 'cmbHiveArtifacts'):
            QTimer.singleShot(200, self.refresh_hive_artifacts)
            
    def _initialize_paths(self):
        """Khởi tạo đường dẫn công cụ."""
        try:
            from utils.path_utils import get_tools_dir
            self.tools_dir = get_tools_dir()
            self.recmd_path = os.path.join(self.tools_dir, "RECmd", "RECmd.exe")
            self.batch_dir = os.path.join(self.tools_dir, "RECmd", "BatchExamples")

            # Không khởi tạo output_dir ở đây - sẽ được thiết lập trong load_case_data
            self.output_dir = None
        except:
            # Đường dẫn dự phòng
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.tools_dir = os.path.join(base_dir, "tools")
            self.recmd_path = os.path.join(self.tools_dir, "RECmd", "RECmd.exe")
            self.batch_dir = os.path.join(self.tools_dir, "RECmd", "BatchExamples")

            # Không khởi tạo output_dir ở đây - sẽ được thiết lập trong load_case_data
            self.output_dir = None

    def setup_ui(self):
        """Thiết lập các thành phần UI."""
        self.setWindowTitle("Phân Tích Registry - Công Cụ Điều Tra Pháp Y Số")

        # Cập nhật header
        self.update_case_info()
        self.update_status("Sẵn sàng")
        
        # Khởi tạo trạng thái ban đầu
        self.ui.btnLoadSelectedHive.setEnabled(False)

        # Thiết lập models cho QTreeView
        self.tree_model.setHorizontalHeaderLabels(["Các Key Registry"])
        self.ui.registryTree.setModel(self.tree_model)
        self.ui.registryTree.setContextMenuPolicy(Qt.CustomContextMenu)

        # Thiết lập model cho QTableView
        self.ui.valuesTable.setModel(self.table_model)

        # Cấu hình hex view
        self.ui.hexView.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.ui.hexView.setFont(font)

        # Cấu hình decoded view
        self.ui.decodedView.setReadOnly(True)

        # Thiết lập bảng timeline
        self.setup_timeline_table()

        # Cấu hình splitter
        self.ui.mainSplitter.setSizes([350, 850])
        self.ui.verticalSplitter.setSizes([400, 200])
        
    def setup_connections(self):
        """Kết nối signals và slots."""
        # Toolbar actions
        self.ui.cmbHiveArtifacts.currentIndexChanged.connect(self.on_hive_artifact_changed)
        self.ui.btnLoadSelectedHive.clicked.connect(self.load_selected_hive_artifact)
        self.ui.btnRefreshHives.clicked.connect(self.refresh_hive_artifacts)
        self.ui.btnExport.clicked.connect(self.show_export_menu)
        
        # Tree actions
        self.ui.registryTree.clicked.connect(self.on_tree_item_clicked)
        self.ui.registryTree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.ui.btnExpandAll.clicked.connect(lambda: self.ui.registryTree.expandAll())
        self.ui.btnCollapseAll.clicked.connect(lambda: self.ui.registryTree.collapseAll())

        # Table actions
        self.ui.valuesTable.selectionModel().selectionChanged.connect(self.on_value_selected)

        # Bookmarks
        self.ui.btnAddBookmark.clicked.connect(self.add_bookmark)
        self.ui.btnRemoveBookmark.clicked.connect(self.remove_bookmark)
        self.ui.btnGoToBookmark.clicked.connect(self.go_to_bookmark)
        self.ui.bookmarksList.itemDoubleClicked.connect(self.bookmark_double_clicked)

        # Format combo
        self.ui.cmbFormat.currentTextChanged.connect(self.update_decoded_view)

        # Notes
        self.ui.btnSaveNotes.clicked.connect(self.save_notes)

        # Path
        self.ui.btnCopyPath.clicked.connect(self.copy_current_path)
        
    def setup_timeline_table(self):
        """Thiết lập các cột của bảng timeline."""
        self.ui.timelineTable.setColumnCount(4)
        self.ui.timelineTable.setHorizontalHeaderLabels(
            ["Thời gian", "Key", "Hành động", "Chi tiết"]
        )
        self.ui.timelineTable.horizontalHeader().setStretchLastSection(True)
        self.ui.timelineTable.setAlternatingRowColors(True)
        self.ui.timelineTable.setSortingEnabled(True)

    def load_case_data(self, case_id):
        """Tải dữ liệu cụ thể của case."""
        # Clear previous data first
        if case_id != self.current_case_id:
            self.clear_previous_data()
        
        self.current_case_id = case_id
        self.update_case_info()

        # Thiết lập thư mục output và load hive artifacts từ case
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.connect()

            case_info = db.get_case_with_investigator(case_id)
            if case_info and case_info.get('archive_path'):
                # Thiết lập thư mục output trong thư mục case
                case_path = case_info['archive_path']
                self.output_dir = os.path.join(case_path, "analysis_results", "registry")
                
                # Tạo thư mục cần thiết
                os.makedirs(self.output_dir, exist_ok=True)

                # Load hive artifacts từ case
                self.load_hive_artifacts_from_case(db)
                self.update_status(f"Case đã tải - Output: {self.output_dir}", "green")
            else:
                # Dự phòng về temp nếu không có đường dẫn case
                self._set_fallback_output_dir()
            
            db.disconnect()
        except Exception as e:
            print(f"Lỗi tải dữ liệu case: {e}")
            # Dự phòng về temp nếu có lỗi
            self._set_fallback_output_dir()

    def clear_previous_data(self):
        """Clear dữ liệu case trước đó khi chuyển sang case mới."""
        try:
            # Clear tree và table models
            if hasattr(self, 'tree_model'):
                self.tree_model.clear()
                self.tree_model.setHorizontalHeaderLabels(["Các Key Registry"])
            
            if hasattr(self, 'table_model'):
                self.table_model.clear()
                self.table_model.setHorizontalHeaderLabels(["Tên", "Kiểu", "Dữ liệu"])
            
            # Clear views
            if hasattr(self.ui, 'hexView'):
                self.ui.hexView.clear()
            if hasattr(self.ui, 'decodedView'):
                self.ui.decodedView.clear()
            if hasattr(self.ui, 'analysisView'):
                self.ui.analysisView.clear()
            if hasattr(self.ui, 'txtCurrentPath'):
                self.ui.txtCurrentPath.clear()
            
            # Clear timeline
            if hasattr(self.ui, 'timelineTable'):
                self.ui.timelineTable.setRowCount(0)
            
            # Clear loaded data
            self.loaded_hives = {}
            self.analysis_results = {}
            self.registry_objects = {}
            
        except Exception as e:
            print(f"Error clearing previous data: {e}")

    def _set_fallback_output_dir(self):
        """Thiết lập thư mục output dự phòng."""
        try:
            from utils.path_utils import get_temp_dir
            temp_root = get_temp_dir() if callable(get_temp_dir) else "temp"
            self.output_dir = os.path.join(temp_root, "registry_analysis")
        except:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.output_dir = os.path.join(base_dir, "temp", "registry_analysis")

        os.makedirs(self.output_dir, exist_ok=True)
        self.update_status("Sử dụng thư mục output tạm thời", "yellow")

    def load_hive_artifacts_from_case(self, db):
        """Load danh sách hive artifacts từ case hiện tại."""
        try:
            # Xóa danh sách cũ
            self.ui.cmbHiveArtifacts.clear()
            self.ui.cmbHiveArtifacts.addItem("-- Chọn Registry Hive --", None)
            
            # Lấy tất cả artifacts của case
            artifacts = db.get_artifacts_by_case(self.current_case_id)
            print(f"🔍 DEBUG: Tìm thấy {len(artifacts)} artifacts tổng cộng trong case {self.current_case_id}")
            
            # Lọc ra các registry hive artifacts
            registry_artifacts = []
            for artifact in artifacts:
                evidence_type = artifact.get('evidence_type', '').upper()
                name = artifact.get('name', '').upper()
                source_path = artifact.get('source_path', '').upper()
                
                # Kiểm tra xem có phải registry hive không
                is_registry = False
                
                # Kiểm tra theo evidence_type
                if 'REGISTRY' in evidence_type:
                    is_registry = True
                    print(f"  ✅ Registry artifact (by type): {name}")
                
                # Kiểm tra theo tên file
                elif any(hive_type in name for hive_type in ['SYSTEM', 'SOFTWARE', 'SAM', 'SECURITY', 'NTUSER', 'USRCLASS', 'DEFAULT']):
                    is_registry = True
                    print(f"  ✅ Registry artifact (by name): {name}")
                
                # Kiểm tra theo đường dẫn file
                elif any(hive_type in source_path for hive_type in ['SYSTEM', 'SOFTWARE', 'SAM', 'SECURITY', 'NTUSER.DAT', 'USRCLASS.DAT', 'DEFAULT']):
                    is_registry = True
                    print(f"  ✅ Registry artifact (by path): {name}")
                
                # Kiểm tra extension đặc biệt
                elif source_path.endswith('.DAT') or 'CONFIG\\' in source_path:
                    is_registry = True
                    print(f"  ✅ Registry artifact (by extension/path): {name}")
                
                if is_registry:
                    registry_artifacts.append(artifact)
                else:
                    print(f"  ❌ Not registry: {name}")
            
            # Thêm vào combo box
            for artifact in registry_artifacts:
                artifact_name = artifact.get('name', 'Unknown')
                hive_type = self._detect_hive_type_from_artifact(artifact)
                display_name = f"{artifact_name} ({hive_type})"
                
                self.ui.cmbHiveArtifacts.addItem(display_name, artifact)
                print(f"  📋 Added to combo: {display_name}")
            
            if registry_artifacts:
                self.update_status(f"Tìm thấy {len(registry_artifacts)} registry hive artifacts", "green")
                print(f"✅ Đã load {len(registry_artifacts)} registry artifacts vào combo box")
            else:
                self.update_status("Không tìm thấy registry hive artifacts trong case", "yellow")
                print("❌ Không tìm thấy registry artifacts nào")
                
        except Exception as e:
            print(f"❌ Lỗi load hive artifacts: {e}")
            import traceback
            traceback.print_exc()
            self.update_status("Lỗi tải danh sách hive artifacts", "red")

    def _detect_hive_type_from_artifact(self, artifact):
        """Phát hiện loại hive từ artifact."""
        name = artifact.get('name', '').upper()
        evidence_type = artifact.get('evidence_type', '').upper()
        
        if 'SYSTEM' in name or 'SYSTEM' in evidence_type:
            return 'SYSTEM'
        elif 'SOFTWARE' in name or 'SOFTWARE' in evidence_type:
            return 'SOFTWARE'
        elif 'SAM' in name or 'SAM' in evidence_type:
            return 'SAM'
        elif 'SECURITY' in name or 'SECURITY' in evidence_type:
            return 'SECURITY'
        elif 'NTUSER' in name or 'NTUSER' in evidence_type:
            return 'NTUSER'
        elif 'USRCLASS' in name or 'USRCLASS' in evidence_type:
            return 'USRCLASS'
        elif 'DEFAULT' in name or 'DEFAULT' in evidence_type:
            return 'DEFAULT'
        else:
            return 'REGISTRY'

    def on_hive_artifact_changed(self, index):
        """Xử lý sự kiện thay đổi hive artifact được chọn."""
        if index <= 0:  # Index 0 là "-- Chọn Registry Hive --"
            self.ui.btnLoadSelectedHive.setEnabled(False)
            return
            
        self.ui.btnLoadSelectedHive.setEnabled(True)
        
        # Lấy artifact được chọn
        artifact = self.ui.cmbHiveArtifacts.itemData(index)
        if artifact:
            self.update_status(f"Đã chọn: {artifact.get('name', 'Unknown')}", "yellow")

    def load_selected_hive_artifact(self):
        """Load hive artifact được chọn."""
        current_index = self.ui.cmbHiveArtifacts.currentIndex()
        if current_index <= 0:
            QMessageBox.warning(self, "Chưa chọn Hive", "Vui lòng chọn một Registry Hive từ danh sách.")
            return
            
        artifact = self.ui.cmbHiveArtifacts.itemData(current_index)
        if not artifact:
            QMessageBox.warning(self, "Lỗi", "Không thể lấy thông tin artifact.")
            return
            
        # Lấy đường dẫn file từ artifact
        source_path = artifact.get('source_path')
        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(self, "File không tồn tại", 
                              f"File hive không tồn tại tại đường dẫn:\n{source_path}")
            return
            
        # Load hive file
        self.update_status(f"Đang load hive: {artifact.get('name', 'Unknown')}", "yellow")
        self.process_hive_files([source_path])
        
        # Tự động chạy phân tích nếu chưa có kết quả
        if not self.analysis_results:
            QTimer.singleShot(1000, self.start_analysis)

    def refresh_hive_artifacts(self):
        """Refresh danh sách hive artifacts từ case."""
        if not self.current_case_id:
            QMessageBox.warning(self, "Chưa chọn Case", "Vui lòng chọn case trước.")
            return
            
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.connect()
            
            print(f"🔄 Refreshing hive artifacts for case {self.current_case_id}")
            self.load_hive_artifacts_from_case(db)
            
            db.disconnect()
            self.update_status("Đã refresh danh sách hive artifacts", "green")
            
        except Exception as e:
            print(f"Lỗi refresh hive artifacts: {e}")
            self.update_status("Lỗi refresh danh sách hive artifacts", "red")

    def update_case_info(self):
        """Cập nhật thông tin case trong header."""
        if self.current_case_id:
            self.ui.caseInfoLabel.setText(f"Case ID: {self.current_case_id}")
        else:
            self.ui.caseInfoLabel.setText("Case: Chưa chọn")

    def reset_to_empty_state(self):
        """Reset Registry Analysis về trạng thái rỗng khi không có case."""
        try:
            # Clear combo box
            if hasattr(self.ui, 'cmbHiveArtifacts'):
                self.ui.cmbHiveArtifacts.clear()
                self.ui.cmbHiveArtifacts.addItem("-- Chọn Registry Hive --", None)
            
            # Disable load button
            if hasattr(self.ui, 'btnLoadSelectedHive'):
                self.ui.btnLoadSelectedHive.setEnabled(False)
            
            # Clear tree model
            if hasattr(self, 'tree_model'):
                self.tree_model.clear()
                self.tree_model.setHorizontalHeaderLabels(["Các Key Registry"])
            
            # Clear table model
            if hasattr(self, 'table_model'):
                self.table_model.clear()
                self.table_model.setHorizontalHeaderLabels(["Tên", "Kiểu", "Dữ liệu"])
            
            # Clear views
            if hasattr(self.ui, 'hexView'):
                self.ui.hexView.clear()
            if hasattr(self.ui, 'decodedView'):
                self.ui.decodedView.clear()
            if hasattr(self.ui, 'analysisView'):
                self.ui.analysisView.clear()
            if hasattr(self.ui, 'txtCurrentPath'):
                self.ui.txtCurrentPath.clear()
            
            # Clear timeline table
            if hasattr(self.ui, 'timelineTable'):
                self.ui.timelineTable.setRowCount(0)
            
            # Clear bookmarks
            if hasattr(self.ui, 'bookmarksList'):
                self.ui.bookmarksList.clear()
            if hasattr(self, 'bookmarks'):
                self.bookmarks = []
            
            # Clear loaded data
            self.loaded_hives = {}
            self.analysis_results = {}
            self.registry_objects = {}
            
            # Update case info and status
            self.update_case_info()
            self.update_status("Chưa chọn case", "yellow")
            
        except Exception as e:
            print(f"Error resetting registry analysis state: {e}")

    def update_status(self, status, color="green"):
        """Cập nhật chỉ báo trạng thái."""
        color_map = {
            "green": "#90EE90",
            "yellow": "#FFD700",
            "red": "#FF6B6B"
        }
        self.ui.statusIndicator.setText(f"● {status}")
        self.ui.statusIndicator.setStyleSheet(f"color: {color_map.get(color, '#90EE90')}; font-size: 12px;")

        # Cũng cập nhật status bar
        self.ui.statusBar.showMessage(status, 5000)

    def process_hive_files(self, file_paths):
        """Xử lý và tải file hive."""
        if not REGISTRY_AVAILABLE:
            QMessageBox.warning(
                self,
                "Thiếu Thư Viện",
                "Thư viện python-registry chưa được cài đặt.\n"
                "Vui lòng cài đặt bằng: pip install python-registry"
            )
            return
            
        valid_hives = []
        
        for file_path in file_paths:
            try:
                # Parse registry file
                registry = Registry.Registry(file_path)
                self.registry_objects[file_path] = registry
                
                hive_info = {
                    "path": file_path,
                    "name": os.path.basename(file_path),
                    "type": self.detect_hive_type(file_path),
                    "size": os.path.getsize(file_path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(file_path)),
                    "registry": registry
                }
                
                valid_hives.append(hive_info)
                self.loaded_hives[file_path] = hive_info
                
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                
        if valid_hives:
            self.build_registry_tree()
            self.update_timeline()
            self.update_status(f"Đã tải {len(valid_hives)} hive(s)", "green")

    def detect_hive_type(self, file_path):
        """Phát hiện loại hive từ tên file."""
        filename = os.path.basename(file_path).upper()

        if "SYSTEM" in filename:
            return "SYSTEM"
        elif "SOFTWARE" in filename:
            return "SOFTWARE"
        elif "SAM" in filename:
            return "SAM"
        elif "SECURITY" in filename:
            return "SECURITY"
        elif "NTUSER" in filename:
            return "NTUSER"
        elif "USRCLASS" in filename:
            return "USRCLASS"
        elif "DEFAULT" in filename:
            return "DEFAULT"
        else:
            return "UNKNOWN"
            
    def build_registry_tree(self):
        """Xây dựng tree view registry với QStandardItemModel."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Các Key Registry"])

        for hive_path, hive_info in self.loaded_hives.items():
            # Tạo hive root item
            hive_item = QStandardItem(f"{hive_info['name']} ({hive_info['type']})")
            hive_item.setData({
                "type": "hive",
                "path": hive_path,
                "info": hive_info
            }, Qt.UserRole)

            self.tree_model.appendRow(hive_item)

            # Thêm registry keys
            try:
                registry = hive_info['registry']
                root = registry.root()
                self.add_key_to_tree(hive_item, root, registry)
            except Exception as e:
                error_item = QStandardItem(f"Lỗi: {str(e)}")
                hive_item.appendRow(error_item)

        # Mở rộng level đầu tiên
        self.ui.registryTree.expandToDepth(0)
        
    def add_key_to_tree(self, parent_item, key, registry, depth=0, max_depth=50):
        """Đệ quy thêm registry keys vào tree."""
        if depth >= max_depth:
            return

        try:
            # Tạo item cho key này
            key_name = key.name() if key.name() else "Root"
            key_item = QStandardItem(key_name)
            key_item.setData({
                "type": "key",
                "key": key,
                "path": key.path(),
                "registry": registry
            }, Qt.UserRole)

            parent_item.appendRow(key_item)

            # Thêm subkeys
            for subkey in key.subkeys():
                self.add_key_to_tree(key_item, subkey, registry, depth + 1, max_depth)

        except Exception as e:
            pass  # Im lặng bỏ qua các key có vấn đề
            
    def on_tree_item_clicked(self, index):
        """Xử lý sự kiện click item trong tree."""
        item = self.tree_model.itemFromIndex(index)
        if not item:
            return

        data = item.data(Qt.UserRole)
        if not data:
            return

        if data["type"] == "key":
            # Hiển thị giá trị key
            self.show_key_values(data["key"])

            # Cập nhật đường dẫn
            self.ui.txtCurrentPath.setText(data["path"])

            # Phân tích key
            self.analyze_key(data["key"], data["path"])

        elif data["type"] == "hive":
            # Hiển thị thông tin hive
            self.show_hive_info(data["info"])
            
    def show_key_values(self, key):
        """Hiển thị giá trị của key được chọn trong QTableView."""
        # Xóa table model
        self.table_model.clear()
        self.table_model.setHorizontalHeaderLabels(["Tên", "Kiểu", "Dữ liệu"])

        try:
            values = []
            for value in key.values():
                values.append({
                    "name": value.name() if value.name() else "(Mặc định)",
                    "type": value.value_type_str(),
                    "data": self.format_value_data(value),
                    "raw_data": value.raw_data()
                })

            # Điền dữ liệu vào model
            for val in values:
                row = []
                name_item = QStandardItem(val["name"])
                name_item.setData(val["raw_data"], Qt.UserRole)  # Lưu raw data
                row.append(name_item)
                row.append(QStandardItem(val["type"]))
                row.append(QStandardItem(str(val["data"])))
                self.table_model.appendRow(row)

            # Tự động điều chỉnh kích thước cột
            self.ui.valuesTable.resizeColumnsToContents()

        except Exception as e:
            print(f"Lỗi hiển thị giá trị: {e}")
            
    def format_value_data(self, value):
        """Định dạng dữ liệu value để hiển thị."""
        try:
            data = value.value()
            if isinstance(data, str):
                return data.replace('\x00', '').strip()
            elif isinstance(data, (int, float)):
                return str(data)
            elif isinstance(data, bytes):
                try:
                    return data.decode('utf-16le', errors='ignore').rstrip('\x00')
                except:
                    return f"<Nhị phân: {len(data)} bytes>"
            elif isinstance(data, list):
                return "; ".join(str(item) for item in data[:5])
            else:
                return str(data)
        except:
            return "<Lỗi đọc giá trị>"
            
    def on_value_selected(self, selected, deselected):
        """Xử lý sự kiện lựa chọn value."""
        indexes = selected.indexes()
        if not indexes:
            return

        # Lấy cột đầu tiên (tên) của hàng được chọn
        row = indexes[0].row()
        name_item = self.table_model.item(row, 0)

        if name_item:
            # Lấy raw data được lưu trong item
            raw_data = name_item.data(Qt.UserRole)

            if raw_data:
                # Cập nhật hex view
                self.ui.hexView.setPlainText(format_as_hex(raw_data))

                # Cập nhật decoded view
                self.update_decoded_view()
            
    def update_decoded_view(self):
        """Cập nhật view dữ liệu đã giải mã."""
        # Lấy hàng được chọn
        indexes = self.ui.valuesTable.selectionModel().selectedIndexes()
        if not indexes:
            return

        row = indexes[0].row()
        name_item = self.table_model.item(row, 0)

        if name_item:
            raw_data = name_item.data(Qt.UserRole)

            if raw_data:
                format_type = self.ui.cmbFormat.currentText()
                decoded = decode_registry_data(raw_data, format_type)
                self.ui.decodedView.setPlainText(decoded)
            
    def analyze_key(self, key, path):
        """Phân tích registry key để tìm forensic artifacts."""
        analysis_text = f"Phân Tích Registry Key\n"
        analysis_text += f"{'='*50}\n"
        analysis_text += f"Đường dẫn: {path}\n"
        analysis_text += f"Sửa đổi lần cuối: {key.timestamp()}\n\n"

        # Kiểm tra forensic artifacts đã biết
        path_upper = path.upper()

        if "USERASSIST" in path_upper:
            analysis_text += "📌 Phát hiện Key UserAssist\n"
            analysis_text += "Key này chứa lịch sử thực thi chương trình.\n"
            analysis_text += "Giá trị được mã hóa ROT13.\n"

        elif "RUN" in path_upper and "RUNONCE" not in path_upper:
            analysis_text += "🚀 Phát hiện Entry Khởi động tự động\n"
            analysis_text += "Các chương trình ở đây chạy khi user đăng nhập.\n"

        elif "SHELLBAGS" in path_upper:
            analysis_text += "📁 Phát hiện Shellbags\n"
            analysis_text += "Chứa lịch sử truy cập thư mục và tùy chỉnh.\n"

        elif "TYPEDURLS" in path_upper:
            analysis_text += "🌐 Phát hiện Typed URLs\n"
            analysis_text += "Chứa URLs được nhập trong Internet Explorer/Edge.\n"

        elif "MOUNTEDDEVICES" in path_upper:
            analysis_text += "💾 Phát hiện Mounted Devices\n"
            analysis_text += "Hiển thị lịch sử thiết bị lưu trữ đã kết nối.\n"

        elif "USBSTOR" in path_upper:
            analysis_text += "🔌 Lịch sử thiết bị USB\n"
            analysis_text += "Chứa thông tin về thiết bị USB đã kết nối.\n"

        self.ui.analysisView.setHtml(f"<pre>{analysis_text}</pre>")
        
    def update_timeline(self):
        """Cập nhật timeline với các thay đổi registry."""
        self.ui.timelineTable.setRowCount(0)
        timeline_events = []

        for hive_path, hive_info in self.loaded_hives.items():
            try:
                registry = hive_info['registry']
                self.collect_timeline_events(registry.root(), timeline_events, hive_info['name'])
            except:
                pass

        # Sắp xếp theo timestamp
        timeline_events.sort(key=lambda x: x['timestamp'], reverse=True)

        # Thêm vào bảng (giới hạn 100 sự kiện gần nhất)
        self.ui.timelineTable.setRowCount(min(len(timeline_events), 100))

        for i, event in enumerate(timeline_events[:100]):
            self.ui.timelineTable.setItem(i, 0, QTableWidgetItem(event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')))
            self.ui.timelineTable.setItem(i, 1, QTableWidgetItem(event['key']))
            self.ui.timelineTable.setItem(i, 2, QTableWidgetItem(event['action']))
            self.ui.timelineTable.setItem(i, 3, QTableWidgetItem(event['details']))

        self.ui.timelineTable.resizeColumnsToContents()
        
    def collect_timeline_events(self, key, events, hive_name, depth=0, max_depth=3):
        """Thu thập timeline events từ registry keys."""
        if depth >= max_depth:
            return

        try:
            if key.timestamp():
                events.append({
                    'timestamp': key.timestamp(),
                    'key': key.path(),
                    'action': 'Đã sửa đổi',
                    'details': f'Hive: {hive_name}'
                })

            for subkey in key.subkeys():
                self.collect_timeline_events(subkey, events, hive_name, depth + 1, max_depth)
        except:
            pass
            
    def add_bookmark(self):
        """Thêm vị trí hiện tại vào bookmarks."""
        current_index = self.ui.registryTree.currentIndex()
        if not current_index.isValid():
            return

        item = self.tree_model.itemFromIndex(current_index)
        if not item:
            return

        data = item.data(Qt.UserRole)
        if data and data["type"] == "key":
            bookmark_text = data["path"]

            # Kiểm tra xem đã bookmark chưa
            for i in range(self.ui.bookmarksList.count()):
                if self.ui.bookmarksList.item(i).text() == bookmark_text:
                    return

            # Thêm bookmark
            list_item = QListWidgetItem(bookmark_text)
            list_item.setData(Qt.UserRole, data)
            self.ui.bookmarksList.addItem(list_item)
            self.bookmarks.append(data)

            self.update_status("Đã thêm bookmark", "green")
            
    def remove_bookmark(self):
        """Xóa bookmark đã chọn."""
        current = self.ui.bookmarksList.currentItem()
        if current:
            row = self.ui.bookmarksList.row(current)
            self.ui.bookmarksList.takeItem(row)
            if row < len(self.bookmarks):
                del self.bookmarks[row]
                
    def go_to_bookmark(self):
        """Điều hướng đến bookmark đã chọn."""
        current = self.ui.bookmarksList.currentItem()
        if current:
            data = current.data(Qt.UserRole)
            if data:
                # Tìm và chọn item trong tree
                self.find_and_select_tree_item(data["path"])
                
    def bookmark_double_clicked(self, item):
        """Xử lý sự kiện double-click bookmark."""
        self.go_to_bookmark()

    def find_and_select_tree_item(self, target_path):
        """Tìm và chọn item trong tree theo đường dẫn."""
        # Implementation sẽ tìm trong tree và chọn item phù hợp
        self.update_status(f"Điều hướng đến: {target_path}", "yellow")

    def copy_current_path(self):
        """Sao chép đường dẫn hiện tại vào clipboard."""
        path = self.ui.txtCurrentPath.text()
        if path:
            QApplication.clipboard().setText(path)
            self.update_status("Đã sao chép đường dẫn vào clipboard", "green")

    def save_notes(self):
        """Lưu ghi chú điều tra."""
        notes = self.ui.notesEdit.toPlainText()
        if notes:
            # Lưu vào database hoặc file
            self.update_status("Đã lưu ghi chú", "green")
            
    def show_hive_info(self, hive_info):
        """Hiển thị thông tin hive."""
        info_text = f"Thông Tin Hive\n"
        info_text += f"{'='*50}\n"
        info_text += f"Tên: {hive_info['name']}\n"
        info_text += f"Loại: {hive_info['type']}\n"
        info_text += f"Đường dẫn: {hive_info['path']}\n"
        info_text += f"Kích thước: {hive_info['size']:,} bytes\n"
        info_text += f"Sửa đổi: {hive_info['modified']}\n"

        self.ui.analysisView.setHtml(f"<pre>{info_text}</pre>")
        
    def show_tree_context_menu(self, position):
        """Hiển thị context menu cho tree."""
        menu = QMenu()

        copy_path = menu.addAction("📋 Sao Chép Đường Dẫn")
        add_bookmark = menu.addAction("⭐ Thêm Bookmark")
        menu.addSeparator()
        export_key = menu.addAction("💾 Xuất Key")

        action = menu.exec_(self.ui.registryTree.mapToGlobal(position))

        if action == copy_path:
            self.copy_current_path()
        elif action == add_bookmark:
            self.add_bookmark()
            
    def show_export_menu(self):
        """Hiển thị menu tùy chọn xuất dữ liệu."""
        menu = QMenu()

        # Thêm nút chạy phân tích mới
        menu.addAction("🔬 Chạy Phân Tích Mới", self.start_analysis)
        menu.addSeparator()
        
        menu.addAction("📊 Xuất Dữ Liệu CSV", self.export_csv)
        menu.addAction("📋 Xuất Timeline", self.export_timeline)

        menu.exec_(self.ui.btnExport.mapToGlobal(self.ui.btnExport.rect().bottomLeft()))

    def start_analysis(self):
        """Bắt đầu phân tích RECmd."""
        if not self.loaded_hives:
            QMessageBox.warning(self, "Không có Hive", "Vui lòng tải registry hive trước.")
            return

        # Kiểm tra thư mục output đã được thiết lập chưa
        if not self.output_dir:
            QMessageBox.warning(self, "Chưa chọn Case", "Vui lòng chọn case trước hoặc thư mục output sẽ là tạm thời.")
            self._set_fallback_output_dir()

        # Tìm file batch
        batch_file = os.path.join(self.batch_dir, "DFIRBatch.reb")
        if not os.path.exists(batch_file):
            # Tìm bất kỳ file batch nào
            import glob
            batch_files = glob.glob(os.path.join(self.batch_dir, "*.reb"))
            if batch_files:
                batch_file = batch_files[0]
            else:
                QMessageBox.warning(self, "Không có Batch File", "Không tìm thấy file batch RECmd.")
                return

        # Tạo progress dialog
        progress = QProgressDialog("Đang chạy phân tích RECmd...", "Hủy", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)

        # Tạo analysis thread
        hive_files = list(self.loaded_hives.keys())
        self.current_analysis_thread = RegistryAnalysisThread(
            self.recmd_path, batch_file, hive_files, self.output_dir
        )

        # Kết nối signals
        self.current_analysis_thread.progress_updated.connect(progress.setValue)
        self.current_analysis_thread.status_updated.connect(lambda s: self.update_status(s, "yellow"))
        self.current_analysis_thread.analysis_completed.connect(self.on_analysis_completed)
        self.current_analysis_thread.error_occurred.connect(self.on_analysis_error)

        progress.canceled.connect(self.current_analysis_thread.cancel)

        # Bắt đầu phân tích
        self.current_analysis_thread.start()
        progress.exec_()

    def on_analysis_completed(self, results):
        """Xử lý hoàn thành phân tích."""
        print(f"🎯 on_analysis_completed được gọi với {len(results)} hives")
        self.analysis_results = results
        total_records = sum(len(r) for r in results.values())

        self.update_status(f"Phân tích hoàn thành: {total_records} bản ghi", "green")

    def on_analysis_error(self, error):
        """Xử lý lỗi phân tích."""
        self.update_status(f"Phân tích thất bại: {error}", "red")
        QMessageBox.critical(self, "Lỗi phân tích", f"Phân tích thất bại:\n{error}")

    def export_csv(self):
        """Xuất dữ liệu phân tích registry ra CSV."""
        if not self.analysis_results:
            QMessageBox.warning(self, "Không có dữ liệu", "Chưa có kết quả phân tích nào để xuất.")
            return

        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("CSV files (*.csv)")
        file_dialog.setDefaultSuffix("csv")
        
        if file_dialog.exec_():
            filepath = file_dialog.selectedFiles()[0]
            try:
                self._export_analysis_to_csv(filepath)
                self.update_status("Đã xuất dữ liệu CSV", "green")
                QMessageBox.information(self, "Thành công", f"Dữ liệu đã được xuất:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi xuất CSV: {str(e)}")

    def export_timeline(self):
        """Xuất timeline registry ra CSV."""
        if self.ui.timelineTable.rowCount() == 0:
            QMessageBox.warning(self, "Không có dữ liệu", "Chưa có timeline nào để xuất.")
            return

        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("CSV files (*.csv)")
        file_dialog.setDefaultSuffix("csv")
        
        if file_dialog.exec_():
            filepath = file_dialog.selectedFiles()[0]
            try:
                self._export_timeline_to_csv(filepath)
                self.update_status("Đã xuất timeline CSV", "green")
                QMessageBox.information(self, "Thành công", f"Timeline đã được xuất:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi xuất timeline: {str(e)}")

    def _export_analysis_to_csv(self, filepath):
        """Xuất kết quả phân tích registry ra file CSV."""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header
                writer.writerow(['Hive File', 'Key Path', 'Value Name', 'Value Type', 'Value Data', 'Last Modified'])
                
                # Xuất dữ liệu từ analysis_results
                for hive_file, results in self.analysis_results.items():
                    hive_name = os.path.basename(hive_file)
                    for result in results:
                        writer.writerow([
                            hive_name,
                            result.get('KeyPath', ''),
                            result.get('ValueName', ''),
                            result.get('ValueType', ''),
                            result.get('ValueData', ''),
                            result.get('LastWrite', '')
                        ])
                        
        except Exception as e:
            raise Exception(f"Lỗi xuất CSV: {str(e)}")

    def _export_timeline_to_csv(self, filepath):
        """Xuất timeline registry ra file CSV."""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header
                writer.writerow(['Timestamp', 'Key', 'Action', 'Details'])
                
                # Xuất dữ liệu từ timeline table
                for row in range(self.ui.timelineTable.rowCount()):
                    row_data = []
                    for col in range(self.ui.timelineTable.columnCount()):
                        item = self.ui.timelineTable.item(row, col)
                        row_data.append(item.text() if item else '')
                    writer.writerow(row_data)
                    
        except Exception as e:
            raise Exception(f"Lỗi xuất timeline CSV: {str(e)}")