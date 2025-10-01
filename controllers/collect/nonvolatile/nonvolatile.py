# -*- coding: utf-8 -*-
import sys
import os
import json
import subprocess
import time
import glob
import re
import math
import psutil
from datetime import datetime

# Thêm thư mục gốc dự án vào đường dẫn
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from PyQt5 import QtCore, QtGui, QtWidgets
from views.pages.collect_ui.collect_nonvolatile_ui import Ui_CollectNonvolatileForm

# Các import tùy chọn với cờ khả dụng
try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False

try:
    import win32file
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


# ==============================================================================
# CÁC HÀM TIỆN ÍCH
# ==============================================================================

def is_admin():
    """Kiểm tra xem đang chạy với quyền quản trị viên."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# ==============================================================================
# CÁC LỚP WORKER CHO CÁC HOẠT ĐỘNG BẤT ĐỒNG BỘ
# ==============================================================================

class KapeDataLoader(QtCore.QObject):
    """Tải các mục tiêu và mô-đun KAPE trong nền."""
    finished = QtCore.pyqtSignal(list, list)
    
    def __init__(self, tools_dir):
        super().__init__()
        self.tools_dir = tools_dir
        
    def run(self):
        targets = self._load_items(os.path.join(self.tools_dir, "KAPE", "Targets"), "*.tkape")
        modules = self._load_items(os.path.join(self.tools_dir, "KAPE", "Modules"), "*.mkape")
        self.finished.emit(targets, modules)
        
    def _load_items(self, base_path, pattern):
        """Trình tải chung cho mục tiêu/mô-đun."""
        items = []
        if os.path.isdir(base_path):
            try:
                files = glob.glob(os.path.join(base_path, "**", pattern), recursive=True)
                for file in files[:100]:  # Giới hạn để tăng hiệu suất
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        name = os.path.splitext(os.path.basename(file))[0]
                        category = os.path.basename(os.path.dirname(file))
                        description = self._extract_description(content)
                        items.append((name, category, description))
                    except:
                        continue
            except:
                pass
        return items
        
    def _extract_description(self, content):
        """Trích xuất mô tả từ tệp cấu hình KAPE."""
        for line in content.split('\n'):
            if line.strip().startswith('Description:'):
                return line.split(':', 1)[1].strip()
        return "No description"


class DeviceScanner(QtCore.QObject):
    """Quét tìm thiết bị lưu trữ trong nền."""
    devicesFound = QtCore.pyqtSignal(list)
    
    def __init__(self, tools_dir=None, parent=None):
        super().__init__(parent)
        self.tools_dir = tools_dir
    
    def scan(self):
        """Quét tìm thiết bị bằng WMI hoặc phương thức dự phòng."""
        devices = []
        
        if WMI_AVAILABLE:
            try:
                devices = self._scan_wmi()
            except Exception as e:
                print(f"WMI scan failed: {e}")
                devices = self._scan_fallback()
        else:
            devices = self._scan_fallback()
            
        self.devicesFound.emit(devices)
    
    def _scan_wmi(self):
        """Quét bằng WMI để lấy thông tin thiết bị chi tiết."""
        devices = []
        c = wmi.WMI()
        physical_disks = {}
        
        # Lấy thông tin ổ đĩa vật lý
        for disk in c.Win32_DiskDrive():
            disk_id = disk.DeviceID
            physical_disks[disk_id] = {
                'model': disk.Model or "Unknown",
                'serial': (disk.SerialNumber or "Unknown").strip(),
                'size': disk.Size,
                'interface': disk.InterfaceType or "Unknown",
                'logical_drives': []
            }
        
        # Ánh xạ phân vùng tới ổ đĩa logic
        for partition in c.Win32_DiskPartition():
            for disk in partition.associators("Win32_DiskDriveToDiskPartition"):
                disk_id = disk.DeviceID
                if disk_id in physical_disks:
                    for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                        physical_disks[disk_id]['logical_drives'].append({
                            'letter': logical_disk.DeviceID,
                            'filesystem': logical_disk.FileSystem or "Unknown",
                        })
        
        # Định dạng để hiển thị
        for disk_id, info in physical_disks.items():
            drive_letters = []
            filesystems = set()
            is_windows = False
            
            for drive in info['logical_drives']:
                drive_letters.append(drive['letter'])
                filesystems.add(drive['filesystem'])
                if drive['letter'] == "C:":
                    is_windows = True
            
            devices.append({
                'id': disk_id,
                'model': info['model'],
                'serial': info['serial'],
                'size': self._format_size(info['size']),
                'filesystem': ", ".join(sorted(filesystems)),
                'partitions': ", ".join(sorted(drive_letters)),
                'is_windows': is_windows,
                'encryption': "Unknown"
            })
            
        return devices
    
    def _scan_fallback(self):
        """Quét dự phòng bằng lệnh wmic."""
        devices = []
        try:
            result = subprocess.run(
                ["wmic", "logicaldisk", "get", "deviceid,size,filesystem,volumename"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        devices.append({
                            'id': parts[0],
                            'model': parts[0],
                            'serial': "Unknown",
                            'size': self._format_size(int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0),
                            'filesystem': parts[1] if len(parts) > 1 else "Unknown",
                            'partitions': parts[0],
                            'is_windows': parts[0] == "C:",
                            'encryption': "Unknown"
                        })
        except Exception as e:
            print(f"Fallback scan error: {e}")
        return devices
    
    def _format_size(self, size_bytes):
        """Định dạng kích thước theo GB."""
        try:
            return f"{int(size_bytes) / (1024**3):.1f} GB"
        except:
            return "Unknown"


# ==============================================================================
# LỚP BỘ ĐIỀU KHIỂN CHÍNH
# ==============================================================================

class NonVolatilePage(QtWidgets.QWidget):
    """Bộ điều khiển chính cho thu thập dữ liệu không biến đổi."""
    
    def __init__(self, main_window=None):
        super().__init__()
        
        # Thiết lập giao diện người dùng
        self.ui = Ui_CollectNonvolatileForm()
        self.ui.setupUi(self)
        
        # Thuộc tính cốt lõi
        self.main_window = main_window
        self.case_data = None
        self.current_step = 0
        self.kape_process = None
        self.imaging_process = None
        self.paused = False
        self.start_time = None
        self.imaging_active = False
        
        # Đường dẫn công cụ
        from utils.path_utils import get_tools_dir
        self.tools_dir = get_tools_dir()
        self.kape_exe = os.path.join(self.tools_dir, "KAPE", "kape.exe")
        self.dc3dd_exe = os.path.join(self.tools_dir, "dc3dd", "dc3dd.exe")
        
        # Lưu trữ biến cho KAPE
        self.target_variables = {}
        self.module_variables = {}

        # Khởi tạo
        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()
        
        # Tự động tải vụ việc nếu có sẵn
        if self.main_window and getattr(self.main_window, "current_case_id", None):
            self.set_case_id(self.main_window.current_case_id)
    
    # =========================================================================
    # CÁC PHƯƠNG THỨC KHỞI TẠO
    # =========================================================================
    
    def _setup_ui(self):
        """Thiết lập các thành phần giao diện người dùng và trạng thái ban đầu."""
        # Thiết lập cửa sổ
        self.setMinimumSize(1200, 850)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        # Thiết lập các trang
        self.stackedWidget = self.ui.stackedWidget
        self.pages = [
            getattr(self.ui, 'page_step1_setup', None),
            getattr(self.ui, 'page_step2_strategy', None),
            getattr(self.ui, 'page_step3_config', None),
            getattr(self.ui, 'page_step4_overview', None),
            getattr(self.ui, 'page_step5_progress', None)
        ]
        self.pages = [p for p in self.pages if p]  # Remove None values
        
        # Nhóm nút radio chiến lược
        self.strategy_group = QtWidgets.QButtonGroup(self)
        self.strategy_group.addButton(self.ui.radioButton_triage)
        self.strategy_group.addButton(self.ui.radioButton_full_image)
        
        # Thiết lập các giá trị ban đầu
        self._set_defaults()
        
        # Cấu hình các bảng
        for table_name in ['tableWidget_devices', 'tableWidget_targets', 'tableWidget_modules']:
            table = getattr(self.ui, table_name, None)
            if table:
                table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
                table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        # Khởi tạo trang đầu tiên
        self.stackedWidget.setCurrentIndex(0)
        self._update_step_indicators()
        self._update_navigation_buttons()
    
    def _set_defaults(self):
        """Thiết lập các giá trị mặc định cho tất cả các điều khiển."""
        defaults = {
            'lineEdit_case_id': f"Case-{datetime.now().strftime('%Y%m%d-%H%M')}",
            'spinBox_fragment_size': 2048,
            'checkBox_use_targets': True,
            'checkBox_use_modules': True,
            'radioButton_e01': True,
            'comboBox_compression': 1,  # Fast compression
            'checkBox_verify_after_creation': True,
            'checkBox_md5': True,
            'checkBox_sha1': True,
            'checkBox_sha256': True,
            'progressBar': 0,
            'label_errors_val': "0",
            'label_source_progress_val': "0 GB / 0 GB",
            'label_speed_val': "0 MB/s",
            'label_time_elapsed_val': "00:00:00",
            'label_eta_val': "00:00:00",
            'pushButton_start': False  # Initially hidden
        }
        
        for widget_name, value in defaults.items():
            widget = getattr(self.ui, widget_name, None)
            if widget:
                if hasattr(widget, 'setChecked'):
                    widget.setChecked(value)
                elif hasattr(widget, 'setText'):
                    widget.setText(str(value))
                elif hasattr(widget, 'setValue'):
                    widget.setValue(value)
                elif hasattr(widget, 'setCurrentIndex'):
                    widget.setCurrentIndex(value)
                elif hasattr(widget, 'setVisible'):
                    widget.setVisible(value)
    
    def _connect_signals(self):
        """Kết nối tất cả các tín hiệu giao diện người dùng với trình xử lý của chúng."""
        # Điều hướng
        connections = {
            'pushButton_next': self.next_page,
            'pushButton_previous': self.previous_page,
            'pushButton_start': self.start_collection,
            'pushButton_refresh_devices': self.refresh_devices,
            'pushButton_pause': self.pause_collection,
            'pushButton_stop': self.stop_collection,
            'pushButton_save_log': self.save_log,
            'toolButton_target_destination': self.browse_target_destination,
            'pushButton_browse_folder': self.browse_image_destination,
            'pushButton_select_all_targets': self.select_all_targets,
            'pushButton_clear_all_targets': self.clear_all_targets,
            'pushButton_add_variable': self.add_target_variable,
        }
        
        for widget_name, handler in connections.items():
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.clicked.connect(handler)
        
        # Các nút radio
        self.ui.radioButton_triage.toggled.connect(self.on_strategy_changed)
        self.ui.radioButton_full_image.toggled.connect(self.on_strategy_changed)
        
        # Các hộp kiểm  
        if hasattr(self.ui, 'checkBox_use_targets'):
            self.ui.checkBox_use_targets.toggled.connect(self.toggle_target_options)
        if hasattr(self.ui, 'checkBox_use_modules'):
            self.ui.checkBox_use_modules.toggled.connect(self.toggle_module_options)
        
        # Lựa chọn bảng
        if hasattr(self.ui, 'tableWidget_devices'):
            self.ui.tableWidget_devices.itemSelectionChanged.connect(self.on_device_selection_changed)
        
        # Bộ lọc tìm kiếm
        if hasattr(self.ui, 'lineEdit_targets_search'):
            self.ui.lineEdit_targets_search.textChanged.connect(self.filter_targets)
        if hasattr(self.ui, 'lineEdit_modules_search'):
            self.ui.lineEdit_modules_search.textChanged.connect(self.filter_modules)
        
        # Các nút đặt trước
        presets = {
            'toolButton_sans': "!SANS_Triage",
            'toolButton_quick': "Quick_System_Info",
            'toolButton_browser': "Browser_and_Email",
            'toolButton_registry': "Registry_All",
            'toolButton_logs': "EventLogs",
            'toolButton_memory': "Memory_Artefacts",
            'toolButton_persistence': "Persistence"
        }
        
        for button_name, preset in presets.items():
            button = getattr(self.ui, button_name, None)
            if button:
                button.clicked.connect(lambda checked, p=preset: self.select_predefined_targets(p))
    
    def _load_initial_data(self):
        """Tải dữ liệu KAPE và thiết bị một cách bất đồng bộ."""
        QtCore.QTimer.singleShot(100, self._load_data_async)
    
    def _load_data_async(self):
        """Tải dữ liệu trong các luồng nền."""
        # Tải mục tiêu/mô-đun KAPE
        self.kape_thread = QtCore.QThread()
        self.kape_worker = KapeDataLoader(self.tools_dir)
        self.kape_worker.moveToThread(self.kape_thread)
        self.kape_worker.finished.connect(self._on_kape_data_loaded)
        self.kape_thread.started.connect(self.kape_worker.run)
        self.kape_thread.start()
        
        # Quét thiết bị
        self.device_thread = QtCore.QThread()
        self.device_worker = DeviceScanner(self.tools_dir)
        self.device_worker.moveToThread(self.device_thread)
        self.device_worker.devicesFound.connect(self._update_device_list)
        self.device_thread.started.connect(self._scan_devices_threaded)
        self.device_thread.start()
    
    def _scan_devices_threaded(self):
        """Khởi tạo COM và quét thiết bị trong luồng."""
        if WMI_AVAILABLE:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                self.device_worker.scan()
                pythoncom.CoUninitialize()
            except:
                self.device_worker.scan()
        else:
            self.device_worker.scan()
    
    # =========================================================================
    # QUẢN LÝ VỤ VIỆC
    # =========================================================================
    
    def set_case_data(self, case_data):
        """Thiết lập dữ liệu vụ việc và cập nhật giao diện người dùng."""
        self.case_data = case_data or {}
        self._update_case_ui()
        self._ensure_default_paths()
    
    def set_case_id(self, case_id):
        """Tải vụ việc theo ID từ cơ sở dữ liệu."""
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            if db.connect():
                case = db.get_case_with_investigator(case_id)
                if case:
                    self.set_case_data({
                        "case_id": case_id,
                        "case_name": case.get("title", f"CASE-{case_id}"),
                        "investigator": case.get("full_name", "Unknown"),
                        "created_date": case.get("created_at", ""),
                        "archive_path": case.get("archive_path", ""),
                    })
        except Exception as e:
            print(f"Error loading case: {e}")
    
    def _update_case_ui(self):
        """Update UI with case information."""
        if not self.case_data:
            return
        
        mappings = {
            'lineEdit_case_id': 'case_id',
            'lineEdit_investigator': 'investigator',
            'lineEdit_case_description': 'case_name'
        }
        
        for widget_name, data_key in mappings.items():
            widget = getattr(self.ui, widget_name, None)
            if widget and self.case_data.get(data_key):
                widget.setText(str(self.case_data[data_key]))
    
    def _ensure_default_paths(self):
        """Auto-fill destination paths based on case archive path."""
        archive_path = (self.case_data or {}).get("archive_path")
        if not archive_path:
            return
        
        # Create directories
        triage_dir = os.path.join(archive_path, "nonvolatile", "triage")
        imaging_dir = os.path.join(archive_path, "nonvolatile", "imaging")
        
        for directory in [triage_dir, imaging_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Set paths if empty
        path_mappings = {
            'lineEdit_target_destination': triage_dir,
            'lineEdit_module_destination': os.path.join(triage_dir, "ModuleOutput"),
            'lineEdit_destination_folder': imaging_dir
        }
        
        for widget_name, path in path_mappings.items():
            widget = getattr(self.ui, widget_name, None)
            if widget and not widget.text().strip():
                widget.setText(path)
    
    # =========================================================================
    # ĐIỀU HƯỚNG
    # =========================================================================
    
    def next_page(self):
        """Điều hướng đến bước tiếp theo."""
        if self.current_step < len(self.pages) - 1:
            if not self._validate_current_step():
                return
            
            self.current_step += 1
            self.stackedWidget.setCurrentIndex(self.current_step)
            
            # Page-specific updates
            if self.current_step == 2:
                self._update_config_page()
            elif self.current_step == 3:
                self._update_overview()
            elif self.current_step == 4:
                self._prepare_collection()
            
            self._update_step_indicators()
            self._update_navigation_buttons()
    
    def previous_page(self):
        """Navigate to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self.stackedWidget.setCurrentIndex(self.current_step)
            self._update_step_indicators()
            self._update_navigation_buttons()
    
    def _update_step_indicators(self):
        """Update step indicator styles."""
        step_labels = [
            getattr(self.ui, f'label_step{i}', None)
            for i in range(1, 6)
        ]
        
        for i, label in enumerate(step_labels):
            if label:
                if i == self.current_step:
                    style = "background-color: #2196F3; color: white;"
                elif i < self.current_step:
                    style = "background-color: #4CAF50; color: white;"
                else:
                    style = "background-color: #E0E0E0; color: #333;"
                label.setStyleSheet(f"{style} border-radius: 5px; padding: 5px; font-weight: bold;")
    
    def _update_navigation_buttons(self):
        """Update navigation button states."""
        if hasattr(self.ui, 'pushButton_previous'):
            self.ui.pushButton_previous.setEnabled(self.current_step > 0)
        if hasattr(self.ui, 'pushButton_next'):
            self.ui.pushButton_next.setEnabled(self.current_step < len(self.pages) - 1)
            self.ui.pushButton_next.setVisible(self.current_step < len(self.pages) - 1)
        if hasattr(self.ui, 'pushButton_start'):
            self.ui.pushButton_start.setVisible(self.current_step == len(self.pages) - 1)
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    def _validate_current_step(self):
        """Validate current step before proceeding."""
        # Auto-load case if needed
        if not self.case_data and self.main_window and getattr(self.main_window, 'current_case_id', None):
            self.set_case_id(self.main_window.current_case_id)
        
        validators = {
            0: self._validate_setup,
            1: self._validate_strategy,
            2: self._validate_config
        }
        
        validator = validators.get(self.current_step)
        return validator() if validator else True
    
    def _validate_setup(self):
        """Validate step 1: Setup."""
        # Check case ID
        if hasattr(self.ui, 'lineEdit_case_id') and not self.ui.lineEdit_case_id.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Information", "Please enter Case ID!")
            return False
        
        # Check device selection
        if hasattr(self.ui, 'tableWidget_devices') and self.ui.tableWidget_devices.currentRow() < 0:
            QtWidgets.QMessageBox.warning(self, "Missing Device", "Please select a source device!")
            return False
        
        # Check admin rights
        if not is_admin():
            QtWidgets.QMessageBox.warning(
                self, "Admin Required",
                "Administrator privileges required for forensic collection.\n"
                "Please restart the application as Administrator."
            )
            return False
        
        # Check risk acceptance for system drive
        if hasattr(self.ui, 'tableWidget_devices'):
            row = self.ui.tableWidget_devices.currentRow()
            if row >= 0:
                partitions = self.ui.tableWidget_devices.item(row, 3).text()
                if "C:" in partitions and hasattr(self.ui, 'checkBox_accept_risk'):
                    if not self.ui.checkBox_accept_risk.isChecked():
                        QtWidgets.QMessageBox.warning(
                            self, "Risk Warning",
                            "You're selecting the Windows system drive.\n"
                            "Please accept the risk before continuing!"
                        )
                        return False
        return True
    
    def _validate_strategy(self):
        """Validate step 2: Strategy selection."""
        if not (self.ui.radioButton_triage.isChecked() or self.ui.radioButton_full_image.isChecked()):
            QtWidgets.QMessageBox.warning(self, "Missing Selection", "Please select a collection method!")
            return False
        return True
    
    def _validate_config(self):
        """Validate step 3: Configuration."""
        # Auto-fill paths if case data available
        if self.case_data:
            self._ensure_default_paths()
        
        if self.ui.radioButton_triage.isChecked():
            return self._validate_triage_config()
        else:
            return self._validate_imaging_config()
    
    def _validate_triage_config(self):
        """Validate triage configuration."""
        # Check destination
        if hasattr(self.ui, 'lineEdit_target_destination'):
            if not self.ui.lineEdit_target_destination.text():
                QtWidgets.QMessageBox.warning(self, "Missing Information", "Please select destination folder!")
                return False
        
        # Check at least one collection type selected
        use_targets = getattr(self.ui, 'checkBox_use_targets', None)
        use_modules = getattr(self.ui, 'checkBox_use_modules', None)
        
        if use_targets and use_modules:
            if not (use_targets.isChecked() or use_modules.isChecked()):
                QtWidgets.QMessageBox.warning(self, "Missing Selection", "Please select Targets or Modules!")
                return False
        
        # Check targets selection
        if use_targets and use_targets.isChecked():
            if not self._has_selected_items('tableWidget_targets'):
                QtWidgets.QMessageBox.warning(self, "Missing Selection", "Please select at least one Target!")
                return False
        
        # Check modules selection
        if use_modules and use_modules.isChecked():
            if not self._has_selected_items('tableWidget_modules'):
                QtWidgets.QMessageBox.warning(self, "Missing Selection", "Please select at least one Module!")
                return False
        
        return True
    
    def _validate_imaging_config(self):
        """Validate imaging configuration."""
        # Check destination
        if hasattr(self.ui, 'lineEdit_destination_folder'):
            if not self.ui.lineEdit_destination_folder.text():
                QtWidgets.QMessageBox.warning(self, "Missing Information", "Please select destination folder!")
                return False
        
        # Check filename
        if hasattr(self.ui, 'lineEdit_image_filename'):
            if not self.ui.lineEdit_image_filename.text():
                QtWidgets.QMessageBox.warning(self, "Missing Information", "Please enter image filename!")
                return False
        
        # Check disk space
        device_size = self._get_device_size()
        dest_folder = self.ui.lineEdit_destination_folder.text()
        
        if not self._check_disk_space(dest_folder, device_size):
            return False
        
        return True
    
    def _has_selected_items(self, table_name):
        """Check if any items are selected in a table."""
        table = getattr(self.ui, table_name, None)
        if not table:
            return False
        
        for row in range(table.rowCount()):
            checkbox = table.item(row, 0)
            if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                return True
        return False
    
    # =========================================================================
    # DEVICE MANAGEMENT
    # =========================================================================
    
    def refresh_devices(self):
        """Refresh device list using WMI or fallback."""
        table = getattr(self.ui, 'tableWidget_devices', None)
        if not table:
            return
        
        table.setRowCount(0)
        
        try:
            if WMI_AVAILABLE:
                self._refresh_devices_wmi()
            else:
                self._refresh_devices_fallback()
            
            if table.rowCount() == 0:
                self._refresh_devices_fallback()
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to refresh devices: {str(e)}")
            self._refresh_devices_fallback()
    
    def _refresh_devices_wmi(self):
        """Refresh devices using WMI."""
        table = self.ui.tableWidget_devices
        c = wmi.WMI()
        
        for disk in c.Win32_DiskDrive():
            row = table.rowCount()
            table.insertRow(row)
            
            # Get disk info
            model = disk.Model or "Unknown"
            serial = (disk.SerialNumber or "Unknown").strip()
            device_id = disk.DeviceID
            
            # Format size
            try:
                size_gb = float(disk.Size) / (1024**3)
                size_display = f"{size_gb:.1f} GB"
            except:
                size_display = "Unknown"
            
            # Get partitions
            is_windows = False
            filesystems = set()
            partitions = []
            
            for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                    if logical_disk.DeviceID == "C:":
                        is_windows = True
                    if logical_disk.FileSystem:
                        filesystems.add(logical_disk.FileSystem)
                    if logical_disk.DeviceID:
                        partitions.append(logical_disk.DeviceID)
            
            # Format display
            model_display = f"{model} ({serial})"
            if is_windows:
                model_display += " (Windows OS)"
            
            # Add to table
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(", ".join(sorted(filesystems))))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(size_display))
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(", ".join(sorted(partitions))))
            table.setItem(row, 4, QtWidgets.QTableWidgetItem("Unknown"))
            
            # Highlight Windows drives
            if is_windows:
                for col in range(5):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(QtGui.QColor(255, 255, 200))
    
    def _refresh_devices_fallback(self):
        """Fallback device refresh using wmic."""
        table = self.ui.tableWidget_devices
        
        try:
            result = subprocess.run(
                ["wmic", "logicaldisk", "where", "drivetype=3", "get", 
                 "deviceid,size,filesystem,volumename"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        self._add_device_to_table(table, parts)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load devices: {str(e)}")
    
    def _add_device_to_table(self, table, parts):
        """Add device to table from wmic output."""
        device_id = parts[0]
        filesystem = parts[2] if len(parts) >= 3 else "Unknown"
        volume_name = " ".join(parts[3:]) if len(parts) >= 4 else ""
        
        try:
            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
            size = f"{size_bytes / (1024**3):.1f} GB"
        except:
            size = "Unknown"
        
        row = table.rowCount()
        table.insertRow(row)
        
        display_name = f"{volume_name} ({device_id})" if volume_name else device_id
        table.setItem(row, 0, QtWidgets.QTableWidgetItem(display_name))
        table.setItem(row, 1, QtWidgets.QTableWidgetItem(filesystem))
        table.setItem(row, 2, QtWidgets.QTableWidgetItem(size))
        table.setItem(row, 3, QtWidgets.QTableWidgetItem(device_id))
        table.setItem(row, 4, QtWidgets.QTableWidgetItem("Unknown"))
        
        if device_id == "C:":
            for col in range(5):
                item = table.item(row, col)
                if item:
                    item.setBackground(QtGui.QColor(255, 255, 200))
    
    def _update_device_list(self, devices):
        """Update device table from scanner results."""
        table = getattr(self.ui, 'tableWidget_devices', None)
        if not table:
            return
        
        table.setRowCount(0)
        
        for device in devices:
            row = table.rowCount()
            table.insertRow(row)
            
            model_display = f"{device['model']} ({device['serial']})"
            if device['is_windows']:
                model_display += " (Windows OS)"
            
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(device['filesystem']))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(device['size']))
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(device['partitions']))
            table.setItem(row, 4, QtWidgets.QTableWidgetItem(device['encryption']))
            
            if device['is_windows']:
                for col in range(5):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(QtGui.QColor(255, 255, 200))
        
        self.device_thread.quit()
    
    def on_device_selection_changed(self):
        """Handle device selection change."""
        table = getattr(self.ui, 'tableWidget_devices', None)
        if not table:
            return
        
        current_row = table.currentRow()
        if current_row < 0:
            return
        
        # Auto-fill source fields
        model_text = table.item(current_row, 0).text()
        partitions_text = table.item(current_row, 3).text()
        source_drive = partitions_text.split(',')[0]
        
        # Update target source
        if hasattr(self.ui, 'lineEdit_target_source'):
            self.ui.lineEdit_target_source.setText(source_drive)
        
        # Update image source
        if hasattr(self.ui, 'lineEdit_image_source'):
            self.ui.lineEdit_image_source.setText(model_text)
        
        # Auto-generate filename
        if hasattr(self.ui, 'lineEdit_image_filename'):
            if not self.ui.lineEdit_image_filename.text():
                safe_name = re.sub(r'[<>:"/\\|?*]', '_', model_text.split('(')[0].strip())
                timestamp = datetime.now().strftime('%Y%m%d-%H%M')
                self.ui.lineEdit_image_filename.setText(f"{safe_name}_{timestamp}")
    
    # =========================================================================
    # KAPE DATA MANAGEMENT
    # =========================================================================
    
    def _on_kape_data_loaded(self, targets, modules):
        """Handle loaded KAPE data."""
        self._update_table('tableWidget_targets', targets)
        self._update_table('tableWidget_modules', modules)
        self.kape_thread.quit()
    
    def _update_table(self, table_name, items):
        """Update target/module table with items."""
        table = getattr(self.ui, table_name, None)
        if not table:
            return
        
        table.setRowCount(0)
        
        for name, category, description in items:
            row = table.rowCount()
            table.insertRow(row)
            
            # Checkbox column
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked)
            table.setItem(row, 0, checkbox)
            
            # Data columns
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(description))
    
    def filter_targets(self, text):
        """Filter targets table based on search text."""
        self._filter_table('tableWidget_targets', text)
    
    def filter_modules(self, text):
        """Filter modules table based on search text."""
        self._filter_table('tableWidget_modules', text)
    
    def _filter_table(self, table_name, text):
        """Generic table filter."""
        table = getattr(self.ui, table_name, None)
        if not table:
            return
        
        for row in range(table.rowCount()):
            visible = False
            for col in range(1, 4):
                item = table.item(row, col)
                if item and text.lower() in item.text().lower():
                    visible = True
                    break
            table.setRowHidden(row, not visible)
    
    def select_predefined_targets(self, preset_name):
        """Select predefined target sets."""
        presets = {
            "!SANS_Triage": ["!SANS_Triage", "WindowsEventLogs", "RegistryHives", "Prefetch"],
            "Quick_System_Info": ["RegistryHives", "WindowsEventLogs", "Prefetch"],
            "Browser_and_Email": ["BrowserHistory", "Chrome", "Firefox", "Edge"],
            "Registry_All": ["RegistryHives", "RegistryBackups", "AmCache", "Syscache"],
            "EventLogs": ["WindowsEventLogs", "Application Event Logs", "Security Logs"],
            "Memory_Artefacts": ["Memory", "Hibernation", "PageFile"],
            "Persistence": ["AutoStart", "Services", "Scheduled Tasks", "Registry Persistence"]
        }
        
        target_names = presets.get(preset_name, [])
        self._select_items_by_name('tableWidget_targets', target_names)
    
    def _select_items_by_name(self, table_name, names):
        """Select table items by name."""
        table = getattr(self.ui, table_name, None)
        if not table:
            return
        
        # Clear all first
        for row in range(table.rowCount()):
            checkbox = table.item(row, 0)
            if checkbox:
                checkbox.setCheckState(QtCore.Qt.Unchecked)
        
        # Select matching items
        for row in range(table.rowCount()):
            name_item = table.item(row, 1)
            if name_item and name_item.text() in names:
                checkbox = table.item(row, 0)
                if checkbox:
                    checkbox.setCheckState(QtCore.Qt.Checked)
    
    def select_all_targets(self):
        """Select all targets."""
        self._select_all_in_table('tableWidget_targets')
    
    def clear_all_targets(self):
        """Clear all target selections."""
        self._clear_all_in_table('tableWidget_targets')
    
    def _select_all_in_table(self, table_name):
        """Select all checkboxes in table."""
        table = getattr(self.ui, table_name, None)
        if table:
            for row in range(table.rowCount()):
                checkbox = table.item(row, 0)
                if checkbox:
                    checkbox.setCheckState(QtCore.Qt.Checked)
    
    def _clear_all_in_table(self, table_name):
        """Clear all checkboxes in table."""
        table = getattr(self.ui, table_name, None)
        if table:
            for row in range(table.rowCount()):
                checkbox = table.item(row, 0)
                if checkbox:
                    checkbox.setCheckState(QtCore.Qt.Unchecked)
    
    def toggle_target_options(self, enabled):
        """Enable/disable target-related UI elements."""
        widgets = [
            'lineEdit_target_source', 'lineEdit_target_destination',
            'toolButton_target_source', 'toolButton_target_destination',
            'tableWidget_targets', 'lineEdit_targets_search',
            'pushButton_select_all_targets', 'pushButton_clear_all_targets',
            'toolButton_sans', 'toolButton_quick', 'toolButton_browser',
            'toolButton_registry', 'toolButton_logs', 'toolButton_memory',
            'toolButton_persistence', 'checkBox_flush', 'checkBox_add_date',
            'checkBox_add_machine', 'checkBox_deduplicate', 'checkBox_process_vscs'
        ]
        
        for widget_name in widgets:
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setEnabled(enabled)
    
    def toggle_module_options(self, enabled):
        """Enable/disable module-related UI elements."""
        widgets = [
            'lineEdit_module_source', 'lineEdit_module_destination',
            'toolButton_module_source', 'toolButton_module_destination',
            'tableWidget_modules', 'lineEdit_modules_search',
            'radioButton_export_csv', 'radioButton_export_json',
            'radioButton_export_html', 'radioButton_export_default'
        ]
        
        for widget_name in widgets:
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setEnabled(enabled)
    
    def add_target_variable(self):
        """Add target variable for KAPE."""
        key = self.ui.lineEdit_variable_key.text().strip()
        value = self.ui.lineEdit_variable_value.text().strip()
        
        if not key or not value:
            QtWidgets.QMessageBox.warning(self, "Error", "Please enter both key and value!")
            return
        
        if ':' in key or '^' in key:
            QtWidgets.QMessageBox.warning(self, "Error", "Key cannot contain ':' or '^' characters!")
            return
        
        self.target_variables[key] = value
        
        var_list = [f"{k}:{v}" for k, v in self.target_variables.items()]
        QtWidgets.QMessageBox.information(
            self, "Success",
            f"Added variable: {key} = {value}\n\n"
            f"Current variables:\n" + "\n".join(var_list)
        )
        
        self.ui.lineEdit_variable_key.clear()
        self.ui.lineEdit_variable_value.clear()
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def on_strategy_changed(self):
        """Handle collection strategy change."""
        self._update_config_page()
        
        is_triage = self.ui.radioButton_triage.isChecked()
        
        # Enable/disable relevant sections
        triage_widgets = ['frame_targets', 'frame_modules', 'groupBox_modules',
                         'groupBox_module_options', 'groupBox_export_options']
        imaging_widgets = ['groupBox_image_format', 'groupBox_image_settings',
                          'groupBox_verification', 'groupBox_hashing',
                          'groupBox_image_source', 'groupBox_image_destination']
        
        for widget_name in triage_widgets:
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setEnabled(is_triage)
        
        for widget_name in imaging_widgets:
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setEnabled(not is_triage)
        
        # Reload case paths if available
        if self.case_data:
            self._ensure_default_paths()
    
    def _update_config_page(self):
        """Update config page based on strategy."""
        if hasattr(self.ui, 'stackedWidget_config'):
            if self.ui.radioButton_triage.isChecked():
                if hasattr(self.ui, 'page_triage_config'):
                    self.ui.stackedWidget_config.setCurrentWidget(self.ui.page_triage_config)
            else:
                if hasattr(self.ui, 'page_image_config'):
                    self.ui.stackedWidget_config.setCurrentWidget(self.ui.page_image_config)
    
    def _update_overview(self):
        """Update overview page with configuration summary."""
        summary = self._generate_summary()
        self.ui.textBrowser_summary.setHtml(summary)
        
        command = self._build_command()
        self.ui.lineEdit_command_line.setText(' '.join(command))
    
    def _generate_summary(self):
        """Generate HTML configuration summary."""
        html = ["<h3>📋 Configuration Summary</h3>"]
        
        # Case info
        html.append("<h4>🏷️ Case Information</h4>")
        if hasattr(self.ui, 'lineEdit_case_id'):
            html.append(f"<b>Case ID:</b> {self.ui.lineEdit_case_id.text()}<br>")
        if hasattr(self.ui, 'lineEdit_investigator'):
            html.append(f"<b>Investigator:</b> {self.ui.lineEdit_investigator.text()}<br>")
        if hasattr(self.ui, 'lineEdit_case_description'):
            html.append(f"<b>Description:</b> {self.ui.lineEdit_case_description.text()}<br><br>")
        
        # Device info
        html.append("<h4>💾 Source Device</h4>")
        if hasattr(self.ui, 'tableWidget_devices'):
            row = self.ui.tableWidget_devices.currentRow()
            if row >= 0:
                html.append(f"<b>Device:</b> {self.ui.tableWidget_devices.item(row, 0).text()}<br>")
                html.append(f"<b>Partitions:</b> {self.ui.tableWidget_devices.item(row, 3).text()}<br>")
                html.append(f"<b>Size:</b> {self.ui.tableWidget_devices.item(row, 2).text()}<br><br>")
        
        # Collection method
        html.append("<h4>🎯 Collection Method</h4>")
        if self.ui.radioButton_triage.isChecked():
            html.append("<b>Type:</b> Triage Collection<br>")
            html.extend(self._get_triage_summary())
        else:
            html.append("<b>Type:</b> Full Disk Imaging<br>")
            html.extend(self._get_imaging_summary())
        
        return "".join(html)
    
    def _get_triage_summary(self):
        """Get triage configuration summary."""
        html = []
        
        # Selected targets
        if hasattr(self.ui, 'checkBox_use_targets') and self.ui.checkBox_use_targets.isChecked():
            selected = self._get_selected_items('tableWidget_targets')
            html.append(f"<b>Targets:</b> {len(selected)} selected<br>")
            if selected:
                html.append("<ul>")
                for target in selected[:5]:
                    html.append(f"<li>{target}</li>")
                if len(selected) > 5:
                    html.append(f"<li>... and {len(selected) - 5} more</li>")
                html.append("</ul>")
        
        # Selected modules
        if hasattr(self.ui, 'checkBox_use_modules') and self.ui.checkBox_use_modules.isChecked():
            selected = self._get_selected_items('tableWidget_modules')
            html.append(f"<b>Modules:</b> {len(selected)} selected<br>")
        
        return html
    
    def _get_imaging_summary(self):
        """Get imaging configuration summary."""
        html = []
        
        # Format
        if self.ui.radioButton_e01.isChecked():
            format_text = "E01"
        elif self.ui.radioButton_raw.isChecked():
            format_text = "Raw"
        else:
            format_text = "AFF"
        html.append(f"<b>Format:</b> {format_text}<br>")
        
        # Compression
        if format_text != "Raw" and hasattr(self.ui, 'comboBox_compression'):
            html.append(f"<b>Compression:</b> {self.ui.comboBox_compression.currentText()}<br>")
        
        # Fragment size
        if hasattr(self.ui, 'spinBox_fragment_size'):
            size = self.ui.spinBox_fragment_size.value()
            html.append(f"<b>Fragment:</b> {'None' if size == 0 else str(size) + ' MB'}<br>")
        
        # Hash algorithms
        hashes = []
        for algo in ['md5', 'sha1', 'sha256']:
            checkbox = getattr(self.ui, f'checkBox_{algo}', None)
            if checkbox and checkbox.isChecked():
                hashes.append(algo.upper())
        html.append(f"<b>Hash:</b> {', '.join(hashes) if hashes else 'None'}<br>")
        
        return html
    
    def _get_selected_items(self, table_name):
        """Get list of selected items from table."""
        table = getattr(self.ui, table_name, None)
        if not table:
            return []
        
        selected = []
        for row in range(table.rowCount()):
            checkbox = table.item(row, 0)
            if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                name_item = table.item(row, 1)
                if name_item:
                    selected.append(name_item.text())
        return selected
    
    # =========================================================================
    # XÂY DỰNG LỆNH
    # =========================================================================
    
    def _build_command(self):
        """Xây dựng dòng lệnh dựa trên cấu hình."""
        if self.ui.radioButton_triage.isChecked():
            return self._build_kape_command()
        else:
            return self._build_imaging_command()
    
    def _build_kape_command(self):
        """Build KAPE command line."""
        cmd = [self.kape_exe]
        
        # Source
        source = self._get_triage_source()
        if source:
            cmd.extend(["--tsource", source])
        
        # Destination
        dest = self._get_triage_destination()
        if dest:
            cmd.extend(["--tdest", dest])
        
        # Targets
        if self.ui.checkBox_use_targets.isChecked():
            targets = self._get_selected_items('tableWidget_targets')
            if targets:
                cmd.extend(["--target", ",".join(targets)])
        
        # Modules
        if self.ui.checkBox_use_modules.isChecked():
            modules = self._get_selected_items('tableWidget_modules')
            if modules:
                cmd.extend(["--module", ",".join(modules)])
                
                # Module destination
                mdest = getattr(self.ui, 'lineEdit_module_destination', None)
                if mdest and mdest.text():
                    cmd.extend(["--mdest", mdest.text()])
                else:
                    cmd.extend(["--mdest", os.path.join(dest, "ModuleOutput")])
        
        # Options
        if hasattr(self.ui, 'checkBox_flush') and self.ui.checkBox_flush.isChecked():
            cmd.append("--tflush")
        
        if hasattr(self.ui, 'checkBox_process_vscs') and self.ui.checkBox_process_vscs.isChecked():
            cmd.append("--vss")
        
        # Variables
        if self.target_variables:
            tvars = "^".join([f"{k}:{v}" for k, v in self.target_variables.items()])
            cmd.extend(["--tvars", tvars])
        
        if self.module_variables:
            mvars = "^".join([f"{k}:{v}" for k, v in self.module_variables.items()])
            cmd.extend(["--mvars", mvars])
        
        cmd.append("--debug")
        
        return cmd
    
    def _get_triage_source(self):
        """Get triage source path."""
        if hasattr(self.ui, 'lineEdit_target_source'):
            source = self.ui.lineEdit_target_source.text()
            if source:
                return source
        
        # Fallback to selected device
        if hasattr(self.ui, 'tableWidget_devices'):
            row = self.ui.tableWidget_devices.currentRow()
            if row >= 0:
                partitions = self.ui.tableWidget_devices.item(row, 3).text()
                source = partitions.split(',')[0]
                if not source.endswith(':') and not source.endswith('\\'):
                    source = source + ':'
                return source
        
        return None
    
    def _get_triage_destination(self):
        """Get triage destination path with date/machine variables."""
        dest = ""
        if hasattr(self.ui, 'lineEdit_target_destination'):
            dest = self.ui.lineEdit_target_destination.text()
            if dest:
                os.makedirs(dest, exist_ok=True)
        
        if hasattr(self.ui, 'checkBox_add_date') and self.ui.checkBox_add_date.isChecked():
            dest = dest + "_%d"
        
        if hasattr(self.ui, 'checkBox_add_machine') and self.ui.checkBox_add_machine.isChecked():
            dest = dest + "_%m"
        
        return dest
    
    def _build_imaging_command(self):
        """Build imaging command line."""
        device_id = self._get_device_id()
        if not device_id:
            return ["echo", "No device selected"]
        
        if self.ui.radioButton_raw.isChecked():
            return self._build_dd_command(device_id)
        else:
            format_type = "encase6" if self.ui.radioButton_e01.isChecked() else "aff"
            return self._build_ewf_command(device_id, format_type)
    
    def _get_device_id(self):
        """Get physical device ID for imaging."""
        row = self.ui.tableWidget_devices.currentRow()
        if row < 0:
            return None
        
        model_text = self.ui.tableWidget_devices.item(row, 0).text()
        
        # Check for physical drive pattern
        match = re.search(r'(\\\\\.\\PHYSICALDRIVE\d+)', model_text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Convert drive letter to physical drive
        partitions = self.ui.tableWidget_devices.item(row, 3).text()
        if partitions and ':' in partitions:
            return self._get_physical_drive_from_letter(partitions.split(',')[0])
        
        return None
    
    def _get_physical_drive_from_letter(self, drive_letter):
        """Convert drive letter to physical drive path."""
        try:
            if WMI_AVAILABLE:
                c = wmi.WMI()
                for logical_disk in c.Win32_LogicalDisk(DeviceID=drive_letter):
                    for partition in logical_disk.associators("Win32_LogicalDiskToPartition"):
                        for disk in partition.associators("Win32_DiskDriveToDiskPartition"):
                            return disk.DeviceID
        except:
            pass
        return f"\\\\.\\PHYSICALDRIVE0"
    
    def _build_ewf_command(self, device_id, format_type):
        """Build ewfacquire command."""
        ewf_path = os.path.join(self.tools_dir, "ewftools-x64", "ewfacquire.exe")
        
        output_dir = self.ui.lineEdit_destination_folder.text()
        filename = self.ui.lineEdit_image_filename.text()
        output_path = os.path.join(output_dir, filename)
        
        cmd = [
            ewf_path,
            "-t", output_path,
            "-f", format_type,
            "-u", "-v",
            "-b", "64",
        ]
        
        # Add case info
        if self.ui.lineEdit_case_id.text():
            cmd.extend(["-C", self.ui.lineEdit_case_id.text()])
        if self.ui.lineEdit_case_description.text():
            cmd.extend(["-D", self.ui.lineEdit_case_description.text()])
        if self.ui.lineEdit_investigator.text():
            cmd.extend(["-e", self.ui.lineEdit_investigator.text()])
        
        # Compression
        compression_map = {0: "none", 1: "fast", 2: "best"}
        compression = compression_map.get(self.ui.comboBox_compression.currentIndex(), "fast")
        if compression != "none":
            cmd.extend(["-c", compression])
        
        # Fragment size
        frag_size = self.ui.spinBox_fragment_size.value()
        if frag_size > 0:
            cmd.extend(["-S", str(frag_size * 1024 * 1024)])
        
        # Hash
        hashes = []
        if self.ui.checkBox_md5.isChecked(): hashes.append("md5")
        if self.ui.checkBox_sha1.isChecked(): hashes.append("sha1")
        if self.ui.checkBox_sha256.isChecked(): hashes.append("sha256")
        if hashes:
            cmd.extend(["-d", ",".join(hashes)])
        
        cmd.append(device_id)
        
        return cmd
    
    def _build_dd_command(self, device_id):
        """Build dc3dd command."""
        output_path = os.path.join(
            self.ui.lineEdit_destination_folder.text(),
            self.ui.lineEdit_image_filename.text() + ".dd"
        )
        
        log_path = os.path.join(
            self.ui.lineEdit_destination_folder.text(),
            self.ui.lineEdit_image_filename.text() + "_dc3dd.log"
        )
        
        cmd = [
            self.dc3dd_exe,
            f"if={device_id}",
            f"of={output_path}",
            "bufsz=8M",
            "verb=on",
        ]
        
        # Hash options
        if self.ui.checkBox_md5.isChecked():
            cmd.append("hash=md5")
        if self.ui.checkBox_sha1.isChecked():
            cmd.append("hash=sha1")
        if self.ui.checkBox_sha256.isChecked():
            cmd.append("hash=sha256")
        
        cmd.append(f"log={log_path}")
        
        return cmd
    
    # =========================================================================
    # THỰC HIỆN THU THẬP
    # =========================================================================
    
    def _prepare_collection(self):
        """Chuẩn bị thu thập trên trang tiến trình."""
        self.ui.pushButton_pause.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(False)
        self.ui.pushButton_save_log.setEnabled(True)
        
        self.ui.progressBar.setValue(0)
        self.ui.label_errors_val.setText("0")
        self.ui.textBrowser_log.clear()
        
        if self.ui.radioButton_triage.isChecked():
            self.ui.textBrowser_log.append("<b>✅ Ready for Triage Collection</b>")
        else:
            self.ui.textBrowser_log.append("<b>✅ Ready for Disk Imaging</b>")
        
        command = self._build_command()
        self.ui.textBrowser_log.append(f"<br><b>Command:</b><pre>{' '.join(command)}</pre>")
        self.ui.textBrowser_log.append("\nClick 'Start Collection' to begin.")
    
    def start_collection(self):
        """Bắt đầu quá trình thu thập."""
        if not is_admin():
            QtWidgets.QMessageBox.warning(
                self, "Admin Required",
                "Collection requires Administrator privileges.\n"
                "Please restart as Administrator."
            )
            return
        
        row = self.ui.tableWidget_devices.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Please select a source device!")
            return
        
        # Reset and start
        self.ui.progressBar.setValue(0)
        self.start_time = time.time()
        
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self._update_progress_stats)
        self.update_timer.start(1000)
        
        if self.ui.radioButton_triage.isChecked():
            self._start_triage()
        else:
            # Check disk space for imaging
            device_size = self._get_device_size()
            if device_size == 0:
                QtWidgets.QMessageBox.warning(self, "Error", "Cannot determine device size!")
                self.update_timer.stop()
                return
            
            if not self._check_disk_space(self.ui.lineEdit_destination_folder.text(), device_size):
                self.update_timer.stop()
                return
            
            self._start_imaging()
    
    def _start_triage(self):
        """Start KAPE triage collection."""
        try:
            cmd = self._build_command()
            
            self.ui.textBrowser_log.clear()
            self.ui.textBrowser_log.append("<b>🚀 Starting KAPE collection...</b>")
            self.ui.textBrowser_log.append(f"<b>Command:</b> {' '.join(cmd)}")
            
            # Ensure destination exists
            if hasattr(self.ui, 'lineEdit_target_destination'):
                dest = self.ui.lineEdit_target_destination.text().strip()
                if dest:
                    os.makedirs(dest, exist_ok=True)
            
            # Start process
            self.kape_process = QtCore.QProcess(self)
            self.kape_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
            self.kape_process.readyReadStandardOutput.connect(self._handle_kape_output)
            self.kape_process.finished.connect(self._kape_finished)
            
            kape_dir = os.path.dirname(self.kape_exe)
            self.kape_process.setWorkingDirectory(kape_dir)
            
            self.kape_process.start(cmd[0], cmd[1:])
            
            self._enable_collection_controls()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to start KAPE: {str(e)}")
            self.update_timer.stop()
    
    def _start_imaging(self):
        """Start disk imaging process."""
        try:
            cmd = self._build_command()
            output_dir = self.ui.lineEdit_destination_folder.text()
            os.makedirs(output_dir, exist_ok=True)
            
            self.ui.textBrowser_log.clear()
            self.ui.textBrowser_log.append("<b>🚀 Starting disk imaging...</b>")
            self.ui.textBrowser_log.append(f"<b>Command:</b> {' '.join(cmd)}")
            
            # Start process
            self.imaging_process = QtCore.QProcess(self)
            self.imaging_process.readyReadStandardOutput.connect(self._handle_imaging_stdout)
            self.imaging_process.readyReadStandardError.connect(self._handle_imaging_stderr)
            self.imaging_process.finished.connect(self._imaging_finished)
            
            self.imaging_process.start(cmd[0], cmd[1:])
            self.imaging_active = True
            
            self._enable_collection_controls()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to start imaging: {str(e)}")
            self.update_timer.stop()
    
    def _enable_collection_controls(self):
        """Enable collection control buttons."""
        self.ui.pushButton_start.setEnabled(False)
        self.ui.pushButton_previous.setEnabled(False)
        self.ui.pushButton_pause.setEnabled(True)
        self.ui.pushButton_stop.setEnabled(True)
    
    def _disable_collection_controls(self):
        """Disable collection control buttons."""
        self.ui.pushButton_start.setEnabled(True)
        self.ui.pushButton_previous.setEnabled(True)
        self.ui.pushButton_pause.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(False)
    
    # =========================================================================
    # PROCESS OUTPUT HANDLERS
    # =========================================================================
    
    def _handle_kape_output(self):
        """Handle KAPE process output."""
        if self.kape_process:
            output = self.kape_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            self.ui.textBrowser_log.append(output)
            
            # Parse progress
            match = re.search(r'Progress:\s*(\d+)%', output)
            if match:
                self.ui.progressBar.setValue(int(match.group(1)))
    
    def _handle_imaging_stdout(self):
        """Handle imaging stdout."""
        if self.imaging_process:
            output = self.imaging_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            
            if self.ui.radioButton_raw.isChecked():
                # Parse dc3dd output
                match = re.search(r'Current:\s*(\d+)\s*bytes.*copied', output)
                if match:
                    bytes_copied = int(match.group(1))
                    total_bytes = self._get_device_size()
                    if total_bytes > 0:
                        progress = (bytes_copied / total_bytes) * 100
                        self.ui.progressBar.setValue(int(progress))
                        self.ui.label_source_progress_val.setText(
                            f"{bytes_copied/(1024**3):.1f} GB / {total_bytes/(1024**3):.1f} GB"
                        )
            else:
                # Parse ewfacquire output
                if "acquiry_percentage" in output:
                    match = re.search(r'acquiry_percentage:\s*(\d+)', output)
                    if match:
                        self.ui.progressBar.setValue(int(match.group(1)))
            
            if output.strip():
                self.ui.textBrowser_log.append(output.strip())
    
    def _handle_imaging_stderr(self):
        """Handle imaging stderr."""
        if self.imaging_process:
            error = self.imaging_process.readAllStandardError().data().decode('utf-8', errors='ignore')
            
            if self.ui.radioButton_raw.isChecked():
                # Parse dc3dd progress from stderr
                match_sectors = re.search(r'(\d+)\s+sectors in', error)
                if match_sectors:
                    sectors = int(match_sectors.group(1))
                    bytes_copied = sectors * 512
                    total_bytes = self._get_device_size()
                    if total_bytes > 0:
                        progress = (bytes_copied / total_bytes) * 100
                        self.ui.progressBar.setValue(int(progress))
                
                # Parse speed
                speed_match = re.search(r'([\d\.]+)\s+MB/s', error)
                if speed_match:
                    self.ui.label_speed_val.setText(f"{float(speed_match.group(1)):.1f} MB/s")
            
            if error.strip():
                self.ui.textBrowser_log.append(f"<span style='color: red;'>{error}</span>")
    
    # =========================================================================
    # ĐIỀU KHIỂN QUÁ TRÌNH
    # =========================================================================
    
    def pause_collection(self):
        """Tạm dừng/tiếp tục thu thập bằng psutil."""
        process = None
        if hasattr(self, 'kape_process') and self.kape_process:
            if self.kape_process.state() != QtCore.QProcess.NotRunning:
                process = self.kape_process
        elif hasattr(self, 'imaging_process') and self.imaging_process:
            if self.imaging_process.state() != QtCore.QProcess.NotRunning:
                process = self.imaging_process
        
        if not process:
            self.ui.textBrowser_log.append("<b>⚠️ No running process to pause.</b>")
            return
        
        try:
            pid = process.processId()
            ps_proc = psutil.Process(pid)
            
            if not self.paused:
                ps_proc.suspend()
                self.paused = True
                self.ui.pushButton_pause.setText("▶️ Resume")
                self.ui.textBrowser_log.append("<b>⏸️ Process paused.</b>")
            else:
                ps_proc.resume()
                self.paused = False
                self.ui.pushButton_pause.setText("⏸️ Pause")
                self.ui.textBrowser_log.append("<b>▶️ Process resumed.</b>")
                
        except Exception as e:
            self.ui.textBrowser_log.append(f"<b>❌ Error: {e}</b>")
    
    def stop_collection(self):
        """Stop collection process."""
        process = None
        if hasattr(self, 'kape_process') and self.kape_process:
            if self.kape_process.state() != QtCore.QProcess.NotRunning:
                process = self.kape_process
        elif hasattr(self, 'imaging_process') and self.imaging_process:
            if self.imaging_process.state() != QtCore.QProcess.NotRunning:
                process = self.imaging_process
        
        if not process:
            self.ui.textBrowser_log.append("<b>⚠️ No process to stop.</b>")
            return
        
        try:
            pid = process.processId()
            ps_proc = psutil.Process(pid)
            
            ps_proc.terminate()
            gone, alive = psutil.wait_procs([ps_proc], timeout=10)
            
            if alive:
                for p in alive:
                    p.kill()
                self.ui.textBrowser_log.append("<b>⚠️ Force killed process.</b>")
            else:
                self.ui.textBrowser_log.append("<b>✅ Process stopped.</b>")
                
        except Exception as e:
            self.ui.textBrowser_log.append(f"<b>❌ Error: {e}</b>")
        
        self._disable_collection_controls()
    
    # =========================================================================
    # PROCESS COMPLETION
    # =========================================================================
    
    def _kape_finished(self, exit_code, exit_status):
        """Handle KAPE process completion."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        if exit_code == 0:
            self.ui.textBrowser_log.append("<b>✅ KAPE collection completed successfully!</b>")
            self.ui.progressBar.setValue(100)
        else:
            self.ui.textBrowser_log.append(f"<b>❌ KAPE collection failed: {exit_code}</b>")
        
        self._disable_collection_controls()
        
        # Notify wizard if present
        if hasattr(self, 'wizard_reference'):
            dest = ""
            try:
                dest = self.ui.lineEdit_target_destination.text().strip()
            except:
                pass
            
            self.wizard_reference.wizard_collection_finished(
                "nonvolatile",
                exit_code == 0,
                "KAPE completed" if exit_code == 0 else f"KAPE failed: {exit_code}",
                dest or None
            )
    
    def _imaging_finished(self, exit_code, exit_status):
        """Handle imaging process completion."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        self.imaging_active = False
        
        if exit_code == 0:
            self.ui.textBrowser_log.append("<b>✅ Imaging completed successfully!</b>")
            self.ui.progressBar.setValue(100)
        else:
            self.ui.textBrowser_log.append(f"<b>❌ Imaging failed: {exit_code}</b>")
        
        self._disable_collection_controls()
        
        # Notify wizard if present
        if hasattr(self, 'wizard_reference'):
            dest = ""
            try:
                dest = self.ui.lineEdit_destination_folder.text().strip()
            except:
                pass
            
            self.wizard_reference.wizard_collection_finished(
                "nonvolatile",
                exit_code == 0,
                "Imaging completed" if exit_code == 0 else f"Imaging failed: {exit_code}",
                dest or None
            )
    
    def _update_progress_stats(self):
        """Update time and ETA statistics."""
        if not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        self.ui.label_time_elapsed_val.setText(time.strftime("%H:%M:%S", time.gmtime(elapsed)))
        
        progress = self.ui.progressBar.value()
        if progress > 0 and elapsed > 1:
            total_estimated = (elapsed / progress) * 100
            remaining = total_estimated - elapsed
            if remaining > 0:
                self.ui.label_eta_val.setText(time.strftime("%H:%M:%S", time.gmtime(remaining)))
    
    # =========================================================================
    # CÁC PHƯƠNG THỨC TIỆN ÍCH
    # =========================================================================
    
    def save_log(self):
        """Lưu nhật ký vào tệp."""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Log",
            f"collection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.ui.textBrowser_log.toPlainText())
                QtWidgets.QMessageBox.information(self, "Success", f"Log saved to: {filename}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Failed to save log: {str(e)}")
    
    def browse_target_destination(self):
        """Duyệt tìm đích đến cho triage."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Triage Destination",
            self.ui.lineEdit_target_destination.text() or os.path.expanduser("~")
        )
        if folder:
            self.ui.lineEdit_target_destination.setText(folder)
    
    def browse_image_destination(self):
        """Duyệt tìm đích đến cho hình ảnh."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Image Destination",
            self.ui.lineEdit_destination_folder.text() or os.path.expanduser("~")
        )
        if folder:
            self.ui.lineEdit_destination_folder.setText(folder)
    
    def _get_device_size(self):
        """Lấy kích thước thiết bị được chọn theo byte."""
        try:
            row = self.ui.tableWidget_devices.currentRow()
            if row >= 0:
                # Thử từ bảng
                size_text = self.ui.tableWidget_devices.item(row, 2).text()
                if size_text and "GB" in size_text:
                    size_gb = float(size_text.replace("GB", "").strip())
                    return int(size_gb * 1024 * 1024 * 1024)
                
                # Thử WMI
                if WMI_AVAILABLE:
                    device_text = self.ui.tableWidget_devices.item(row, 0).text()
                    match = re.search(r'(\\\\\.\\[A-Za-z0-9]+)', device_text)
                    if match:
                        c = wmi.WMI()
                        for disk in c.Win32_DiskDrive(DeviceID=match.group(1)):
                            return int(disk.Size)
            
            return 0
        except Exception as e:
            print(f"Error getting device size: {e}")
            return 0
    
    def _check_disk_space(self, output_path, source_size):
        """Kiểm tra xem đích đến có đủ dung lượng không."""
        try:
            drive = os.path.splitdrive(output_path)[0]
            if not drive:
                drive = os.path.dirname(os.path.abspath(output_path))
            
            free_space = self._get_free_space(drive)
            
            # Ước tính dung lượng cần thiết
            if self.ui.radioButton_raw.isChecked():
                required_space = source_size * 1.01
            else:
                compression_factors = {0: 1.01, 1: 0.7, 2: 0.5}
                factor = compression_factors.get(self.ui.comboBox_compression.currentIndex(), 1.01)
                required_space = source_size * factor
            
            free_gb = free_space / (1024**3)
            required_gb = required_space / (1024**3)
            
            if free_space < required_space:
                QtWidgets.QMessageBox.critical(
                    self, "Insufficient Space",
                    f"Not enough free space!\n\n"
                    f"Free: {free_gb:.1f} GB\n"
                    f"Required: {required_gb:.1f} GB"
                )
                return False
            
            elif free_space < required_space * 1.1:
                reply = QtWidgets.QMessageBox.warning(
                    self, "Low Space Warning",
                    f"Free space is close to required!\n\n"
                    f"Free: {free_gb:.1f} GB\n"
                    f"Required: {required_gb:.1f} GB\n\n"
                    f"Continue anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                return reply == QtWidgets.QMessageBox.Yes
            
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                f"Cannot check disk space: {str(e)}\n"
                "Please ensure sufficient space before continuing."
            )
            return True
    
    def _get_free_space(self, path):
        """Lấy dung lượng trống cho đường dẫn."""
        try:
            if os.name == 'nt':
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes)
                )
                return free_bytes.value
            else:
                st = os.statvfs(path)
                return st.f_frsize * st.f_bavail
        except:
            return 0


# Alias for compatibility
CollectNonvolatileController = NonVolatilePage