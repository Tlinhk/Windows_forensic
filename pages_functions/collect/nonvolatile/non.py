# -*- coding: utf-8 -*-
import sys
import os
import json
import subprocess
import time
import glob
import re
import math
from datetime import datetime

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from PyQt5 import QtCore, QtGui, QtWidgets
from ui.pages.collect_ui.collect_nonvolatile_ui import Ui_CollectNonvolatileForm

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

def is_admin():
    """Kiểm tra quyền Administrator"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class NonVolatilePage(QtWidgets.QWidget, Ui_CollectNonvolatileForm):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        
        # --- Path to your tools directory ---
        self.tools_dir = r"E:\DoAn\Windows_forensic\tools"
        self.edd_exe = os.path.join(self.tools_dir, "EDDv300.exe")
        self.kape_exe = os.path.join(self.tools_dir, "KAPE", "kape.exe")

        # Initialize variables
        self.current_step = 0
        self.kape_process = None
        self.paused = False
        self.start_time = None
        
        # Imaging variables
        self.imaging_active = False
        self.imaging_paused = False  # TODO: Implement actual pause/resume for imaging processes
        
        # Initialize WMI if available
        if WMI_AVAILABLE:
            try:
                self.c = wmi.WMI()
            except Exception as e:
                self.c = None
                print(f"WMI initialization failed: {e}")
        else:
            self.c = None
        
        # Define wizard pages
        self.pages = [
            self.page_step1_setup,
            self.page_step2_strategy,
            self.page_step3_config,
            self.page_step4_overview,
            self.page_step5_progress
        ]
        
        # Setup initial state
        self.setup_initial_state()
        self.connect_signals()
        
        # Load data in background
        QtCore.QTimer.singleShot(100, self.load_data_async)
        
    def setup_initial_state(self):
        """Initialize the UI to its starting state"""
        # Set wizard to first step
        self.stackedWidget.setCurrentIndex(0)
        self.stackedWidget_config.setCurrentIndex(0)  # Default to triage config
        
        # Update step indicators
        self.update_step_indicators()
        self.update_navigation_buttons()
        
        # Hide start button initially
        self.pushButton_start.setVisible(False)
        
        # Initialize progress values
        self.progressBar.setValue(0)
        self.label_errors_val.setText("0")
        self.label_source_progress_val.setText("0 GB / 0 GB")
        self.label_speed_val.setText("0 MB/s")
        self.label_time_elapsed_val.setText("00:00:00")
        self.label_eta_val.setText("00:00:00")
        
        # Create source size label if it doesn't exist
        if not hasattr(self, 'label_source_size'):
            self.label_source_size = QtWidgets.QLabel(self)
            self.label_source_size.setText("Unknown")
            # Add to layout - assuming there's a layout where device info is shown
            if hasattr(self, 'gridLayout_device_info'):
                self.gridLayout_device_info.addWidget(self.label_source_size, 2, 1)
        
        # Set default values
        self.lineEdit_case_id.setText(f"Case-{datetime.now().strftime('%Y%m%d-%H%M')}")
        self.spinBox_fragment_size.setValue(2048)  # Default to 2GB
        
        # Enable target/module options by default
        self.checkBox_use_targets.setChecked(True)
        self.checkBox_use_modules.setChecked(True)
        
        # Initialize image format options
        self.radioButton_e01.setChecked(True)  # E01 format by default
        self.comboBox_compression.setCurrentIndex(1)  # Fast compression
        
        # Initialize verification options
        self.checkBox_verify_after_creation.setChecked(True)
        self.checkBox_precalculate_progress.setChecked(True)
        self.checkBox_create_directory_listing.setChecked(True)
        self.checkBox_ad_encryption.setChecked(False)
        
        # Initialize hash options
        self.checkBox_md5.setChecked(True)
        self.checkBox_sha1.setChecked(True)
        self.checkBox_sha256.setChecked(True)
        
    def connect_signals(self):
        """Connect all UI signals to their respective slots"""
        # Navigation buttons
        self.pushButton_next.clicked.connect(self.next_page)
        self.pushButton_previous.clicked.connect(self.previous_page)
        self.pushButton_start.clicked.connect(self.start_collection)
        
        # Device management
        self.pushButton_refresh_devices.clicked.connect(self.refresh_devices)
        self.tableWidget_devices.itemSelectionChanged.connect(self.on_device_selection_changed)
        
        # Collection controls
        self.pushButton_pause.clicked.connect(self.pause_collection)
        self.pushButton_stop.clicked.connect(self.stop_collection)
        self.pushButton_save_log.clicked.connect(self.save_log)
        
        # Strategy selection
        self.radioButton_triage.toggled.connect(self.on_strategy_changed)
        self.radioButton_full_image.toggled.connect(self.on_strategy_changed)
        
        # Target/Module options
        self.checkBox_use_targets.toggled.connect(self.toggle_target_options)
        self.checkBox_use_modules.toggled.connect(self.toggle_module_options)
        
        # File browser buttons
        self.toolButton_target_source.clicked.connect(lambda: self.browse_folder(self.lineEdit_target_source))
        self.toolButton_target_destination.clicked.connect(self.browse_target_destination)
        self.pushButton_browse_folder.clicked.connect(self.browse_image_destination)
        
        # Predefined target buttons
        self.toolButton_sans.clicked.connect(lambda: self.select_predefined_targets("!SANS_Triage"))
        self.toolButton_quick.clicked.connect(lambda: self.select_predefined_targets("Quick_System_Info"))
        self.toolButton_browser.clicked.connect(lambda: self.select_predefined_targets("Browser_and_Email"))
        
        # Search functionality
        self.lineEdit_targets_search.textChanged.connect(self.filter_targets)
        self.lineEdit_modules_search.textChanged.connect(self.filter_modules)
        
        # Image format and compression
        self.radioButton_e01.toggled.connect(self.on_format_changed)
        self.radioButton_raw.toggled.connect(self.on_format_changed)
        self.radioButton_aff.toggled.connect(self.on_format_changed)
        self.comboBox_compression.currentIndexChanged.connect(self.on_compression_changed)
        
        # Fragment size and verification options
        self.spinBox_fragment_size.valueChanged.connect(self.on_fragment_size_changed)
        self.checkBox_verify_after_creation.toggled.connect(self.on_verification_option_changed)
        self.checkBox_precalculate_progress.toggled.connect(self.on_verification_option_changed)
        self.checkBox_create_directory_listing.toggled.connect(self.on_verification_option_changed)
        self.checkBox_ad_encryption.toggled.connect(self.on_verification_option_changed)
        
        # Image destination changes
        self.lineEdit_destination_folder.textChanged.connect(self.update_image_path)
        self.lineEdit_image_filename.textChanged.connect(self.update_image_path)
        
    def update_step_indicators(self):
        """Update the visual step indicators at the top"""
        step_labels = [
            self.label_step1, self.label_step2, self.label_step3,
            self.label_step4, self.label_step5
        ]
        
        for i, label in enumerate(step_labels):
            if i == self.current_step:
                # Current step - highlighted
                label.setStyleSheet("background-color: #2196F3; color: white; border-radius: 5px; padding: 5px; font-weight: bold;")
            elif i < self.current_step:
                # Completed step - green
                label.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 5px; padding: 5px; font-weight: bold;")
            else:
                # Future step - gray
                label.setStyleSheet("background-color: #E0E0E0; color: #333; border-radius: 5px; padding: 5px; font-weight: bold;")
    
    def update_navigation_buttons(self):
        """Update navigation button states"""
        self.pushButton_previous.setEnabled(self.current_step > 0)
        self.pushButton_next.setEnabled(self.current_step < len(self.pages) - 1)
        
        # Show start button only on the last step
        self.pushButton_start.setVisible(self.current_step == len(self.pages) - 1)
        self.pushButton_next.setVisible(self.current_step < len(self.pages) - 1)
    
    def next_page(self):
        """Navigate to next page"""
        if self.current_step < len(self.pages) - 1:
            # Validate current step before proceeding
            if not self.validate_current_step():
                return
                
            self.current_step += 1
            self.stackedWidget.setCurrentIndex(self.current_step)
            
            # Handle special cases for certain steps
            if self.current_step == 2:  # Configuration step
                self.update_config_page()
            elif self.current_step == 3:  # Overview step
                self.update_overview()
            elif self.current_step == 4:  # Progress step
                self.prepare_collection()
            
            self.update_step_indicators()
            self.update_navigation_buttons()
    
    def previous_page(self):
        """Navigate to previous page"""
        if self.current_step > 0:
            self.current_step -= 1
            self.stackedWidget.setCurrentIndex(self.current_step)
            self.update_step_indicators()
            self.update_navigation_buttons()
    
    def validate_current_step(self):
        """Validate the current step before proceeding"""
        if self.current_step == 0:  # Step 1: Setup & Source
            if not self.lineEdit_case_id.text().strip():
                QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập mã vụ việc!")
                return False
            if self.tableWidget_devices.currentRow() < 0:
                QtWidgets.QMessageBox.warning(self, "Thiếu thiết bị", "Vui lòng chọn thiết bị nguồn!")
                return False
            # Check if Windows drive is selected and risk is accepted
            current_row = self.tableWidget_devices.currentRow()
            if current_row >= 0:
                partition = self.tableWidget_devices.item(current_row, 3).text()
                if "C:" in partition and not self.checkBox_accept_risk.isChecked():
                    QtWidgets.QMessageBox.warning(self, "Cảnh báo rủi ro", 
                        "Bạn đang chọn ổ hệ thống Windows. Vui lòng chấp nhận rủi ro trước khi tiếp tục!")
                    return False
        
        elif self.current_step == 1:  # Step 2: Strategy
            if not (self.radioButton_triage.isChecked() or self.radioButton_full_image.isChecked()):
                QtWidgets.QMessageBox.warning(self, "Thiếu lựa chọn", "Vui lòng chọn phương pháp thu thập!")
                return False
        
        elif self.current_step == 2:  # Step 3: Configuration
            if self.radioButton_triage.isChecked():
                # Validate triage configuration
                if not self.lineEdit_target_destination.text():
                    QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn thư mục đích cho triage!")
                    return False
                if not (self.checkBox_use_targets.isChecked() or self.checkBox_use_modules.isChecked()):
                    QtWidgets.QMessageBox.warning(self, "Thiếu lựa chọn", "Vui lòng chọn ít nhất một loại thu thập (Targets hoặc Modules)!")
                    return False
            else:
                # Validate imaging configuration
                if not self.lineEdit_destination_folder.text():
                    QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn thư mục đích cho imaging!")
                    return False
                if not self.lineEdit_image_filename.text():
                    QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên file ảnh!")
                    return False
        
        return True
    
    def update_config_page(self):
        """Update the configuration page based on selected strategy"""
        if self.radioButton_triage.isChecked():
            self.stackedWidget_config.setCurrentWidget(self.page_triage_config)
        else:
            self.stackedWidget_config.setCurrentWidget(self.page_image_config)
    
    def on_strategy_changed(self):
        """Handle strategy selection change"""
        # Update the configuration page based on selected strategy
        self.update_config_page()
        
        # Enable/disable appropriate options based on strategy
        if self.radioButton_triage.isChecked():
            # Enable triage options
            self.groupBox_target_options.setEnabled(True)
            self.groupBox_targets.setEnabled(True)
            if hasattr(self, 'groupBox_modules'):
                self.groupBox_modules.setEnabled(True)
            
            # Show triage destination fields
            self.lineEdit_target_source.setEnabled(True)
            self.lineEdit_target_destination.setEnabled(True)
            self.toolButton_target_source.setEnabled(True)
            self.toolButton_target_destination.setEnabled(True)
            
            # Hide imaging fields
            self.lineEdit_destination_folder.setEnabled(False)
            self.lineEdit_image_filename.setEnabled(False)
            self.pushButton_browse_folder.setEnabled(False)
            
            # Disable imaging options
            self.radioButton_e01.setEnabled(False)
            self.radioButton_raw.setEnabled(False)
            self.radioButton_aff.setEnabled(False)
            self.comboBox_compression.setEnabled(False)
            self.spinBox_fragment_size.setEnabled(False)
            
            # Disable verification options
            self.checkBox_verify_after_creation.setEnabled(False)
            self.checkBox_precalculate_progress.setEnabled(False)
            self.checkBox_create_directory_listing.setEnabled(False)
            self.checkBox_ad_encryption.setEnabled(False)
            
            # Hide hash options
            self.checkBox_md5.setEnabled(False)
            self.checkBox_sha1.setEnabled(False)
            self.checkBox_sha256.setEnabled(False)
            
        else:  # Imaging mode
            # Disable triage options
            self.groupBox_target_options.setEnabled(False)
            self.groupBox_targets.setEnabled(False)
            if hasattr(self, 'groupBox_modules'):
                self.groupBox_modules.setEnabled(False)
            
            # Hide triage destination fields
            self.lineEdit_target_source.setEnabled(False)
            self.lineEdit_target_destination.setEnabled(False)
            self.toolButton_target_source.setEnabled(False)
            self.toolButton_target_destination.setEnabled(False)
            
            # Show imaging fields
            self.lineEdit_destination_folder.setEnabled(True)
            self.lineEdit_image_filename.setEnabled(True)
            self.pushButton_browse_folder.setEnabled(True)
            
            # Enable imaging options
            self.radioButton_e01.setEnabled(True)
            self.radioButton_raw.setEnabled(True)
            self.radioButton_aff.setEnabled(True)
            self.comboBox_compression.setEnabled(True)
            self.spinBox_fragment_size.setEnabled(True)
            
            # Enable verification options
            self.checkBox_verify_after_creation.setEnabled(True)
            self.checkBox_precalculate_progress.setEnabled(True)
            self.checkBox_create_directory_listing.setEnabled(True)
            self.checkBox_ad_encryption.setEnabled(True)
            
            # Show hash options
            self.checkBox_md5.setEnabled(True)
            self.checkBox_sha1.setEnabled(True)
            self.checkBox_sha256.setEnabled(True)
            
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()
    
    def refresh_devices(self):
        """Quét và hiển thị danh sách ổ cứng"""
        self.tableWidget_devices.setRowCount(0)
        
        try:
            # Sử dụng WMI để lấy thông tin chi tiết
            if WMI_AVAILABLE:
                c = wmi.WMI()
                for disk in c.Win32_DiskDrive():
                    row = self.tableWidget_devices.rowCount()
                    self.tableWidget_devices.insertRow(row)
                    
                    # Get drive info
                    model = disk.Model or "Unknown"
                    serial = disk.SerialNumber or "Unknown"
                    device_id = disk.DeviceID
                    status = disk.Status or "Unknown"
                    
                    # Convert size to GB
                    try:
                        size_gb = float(disk.Size) / (1024**3)
                        size_display = f"{size_gb:.1f} GB"
                    except:
                        size_display = "Unknown"
                    
                    # Check if Windows drive and get filesystem info
                    is_windows = False
                    filesystems = []
                    partitions = []
                    
                    for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                        for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                            if logical_disk.DeviceID == "C:":
                                is_windows = True
                            
                            # Get filesystem type
                            if logical_disk.FileSystem and logical_disk.FileSystem not in filesystems:
                                filesystems.append(logical_disk.FileSystem)
                            
                            # Get partition letter
                            if logical_disk.DeviceID:
                                partitions.append(logical_disk.DeviceID)
                    
                    # Add to table according to UI column order
                    model_display = f"{model} ({serial})"
                    if is_windows:
                        model_display += " (Windows OS)"
                    
                    # Column 0: Model
                    self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
                    
                    # Column 1: Filesystem
                    filesystem_display = ", ".join(filesystems) if filesystems else "Unknown"
                    self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(filesystem_display))
                    
                    # Column 2: Disk Size
                    self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(size_display))
                    
                    # Column 3: Partitions
                    partition_display = ", ".join(partitions) if partitions else "Unknown"
                    self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(partition_display))
                    
                    # Column 4: Encryption Status
                    self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem(
                        self.check_encryption_status(device_id)
                    ))
                    
                    # Highlight Windows drive
                    if is_windows:
                        for col in range(5):
                            item = self.tableWidget_devices.item(row, col)
                            if item:
                                item.setBackground(QtGui.QColor(255, 255, 200))
            
            # Fallback to simpler method if WMI fails
            if self.tableWidget_devices.rowCount() == 0:
                self.refresh_devices_fallback()
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể lấy danh sách thiết bị: {str(e)}")
            self.refresh_devices_fallback()

    def refresh_devices_fallback(self):
        """Fallback method to get device list using WMIC"""
        try:
            # Get logical drives
            result = subprocess.run(
                ["wmic", "logicaldisk", "where", "drivetype=3", "get", "deviceid,size,filesystem,volumename"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        
                        # Get filesystem if available
                        filesystem = "Unknown"
                        if len(parts) >= 3:
                            filesystem = parts[2]
                        
                        # Get volume name if available
                        volume_name = ""
                        if len(parts) >= 4:
                            volume_name = " ".join(parts[3:])
                        
                        # Calculate size in GB
                        try:
                            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
                            size_gb = size_bytes / (1024**3)
                            size = f"{size_gb:.1f} GB"
                        except:
                            size = "Unknown"
                        
                        row = self.tableWidget_devices.rowCount()
                        self.tableWidget_devices.insertRow(row)
                        
                        # Add to table according to UI column order
                        # Column 0: Model
                        display_name = f"{device_id} ({volume_name})" if volume_name else device_id
                        self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(display_name))
                        
                        # Column 1: Filesystem
                        self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(filesystem))
                        
                        # Column 2: Disk Size
                        self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(size))
                        
                        # Column 3: Partitions
                        self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(device_id))
                        
                        # Column 4: Encryption Status
                        self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem("Unknown"))
                        
                        # Highlight C: drive
                        if device_id == "C:":
                            for col in range(5):
                                item = self.tableWidget_devices.item(row, col)
                                if item:
                                    item.setBackground(QtGui.QColor(255, 255, 200))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể tải danh sách thiết bị: {str(e)}")
            
    def update_device_list(self, devices):
        """Update device list with data from background thread"""
        self.tableWidget_devices.setRowCount(0)
        windows_drive = os.environ.get('SystemDrive', 'C:')
        
        for device in devices:
            row = self.tableWidget_devices.rowCount()
            self.tableWidget_devices.insertRow(row)
            
            # Add device info to table according to UI column order
            model_display = f"{device['model']} ({device['serial']})"
            if device['is_windows']:
                model_display += " (Windows OS)"
                
            # Column 0: Model
            self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
            
            # Column 1: Filesystem
            self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(device['filesystem']))
            
            # Column 2: Disk Size
            self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(device['size']))
            
            # Column 3: Partitions
            self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(device['partitions']))
            
            # Column 4: Encryption Status
            self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem(device['encryption']))
            
            # Highlight Windows drive
            if device['is_windows']:
                for col in range(5):
                    item = self.tableWidget_devices.item(row, col)
                    if item:
                        item.setBackground(QtGui.QColor(255, 255, 200))
                        
        self.device_thread.quit()

    def get_interface_type(self, interface_type):
        """Convert interface type to readable string"""
        interface_map = {
            "IDE": "IDE/PATA",
            "SCSI": "SCSI",
            "USB": "USB",
            "1394": "FireWire",
            "HDC": "Hard Disk Controller"
        }
        return interface_map.get(interface_type, interface_type or "Unknown")
    
    def check_encryption_status(self, drive_letter):
        """Check encryption status of a drive using EDDv300.exe"""
        try:
            out = subprocess.check_output(
                [self.edd_exe, "-path", drive_letter, "-json"],
                stderr=subprocess.DEVNULL, timeout=10
            )
            data = json.loads(out.decode("utf-8", errors="ignore"))
            return "Encrypted" if data.get("Encrypted") else "Unencrypted"
        except subprocess.TimeoutExpired:
            return "Timeout"
        except Exception:
            return "Unknown"
    
    def load_data_async(self):
        """Load KAPE data and refresh devices asynchronously"""
        # Start a thread to load KAPE data
        self.kape_thread = QtCore.QThread()
        self.kape_worker = KapeDataLoader(self.tools_dir)
        self.kape_worker.moveToThread(self.kape_thread)
        self.kape_worker.finished.connect(self.on_kape_data_loaded)
        self.kape_thread.started.connect(self.kape_worker.run)
        self.kape_thread.start()
        
        # Start a thread to refresh devices
        self.device_thread = QtCore.QThread()
        self.device_worker = DeviceScanner()
        self.device_worker.moveToThread(self.device_thread)
        self.device_worker.devicesFound.connect(self.update_device_list)
        self.device_thread.started.connect(self.device_worker.scan)
        self.device_thread.start()
        
    def on_kape_data_loaded(self, targets, modules):
        """Handle KAPE data loaded from background thread"""
        self.update_targets_table(targets)
        self.update_modules_table(modules)
        self.kape_thread.quit()
        
    def update_targets_table(self, targets):
        """Update targets table with loaded data"""
        self.tableWidget_targets.setRowCount(0)
        
        for name, category, description in targets:
            row = self.tableWidget_targets.rowCount()
            self.tableWidget_targets.insertRow(row)
            
            # Add checkbox
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_targets.setItem(row, 0, checkbox)
            
            self.tableWidget_targets.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.tableWidget_targets.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            self.tableWidget_targets.setItem(row, 3, QtWidgets.QTableWidgetItem(description))
    
    def update_modules_table(self, modules):
        """Update modules table with loaded data"""
        self.tableWidget_modules.setRowCount(0)
        
        for name, category, description in modules:
            row = self.tableWidget_modules.rowCount()
            self.tableWidget_modules.insertRow(row)
            
            # Add checkbox
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_modules.setItem(row, 0, checkbox)
            
            self.tableWidget_modules.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.tableWidget_modules.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            self.tableWidget_modules.setItem(row, 3, QtWidgets.QTableWidgetItem(description))

    def toggle_target_options(self, enabled):
        """Enable/disable target options"""
        self.groupBox_target_options.setEnabled(enabled)
        self.groupBox_targets.setEnabled(enabled)
    
    def toggle_module_options(self, enabled):
        """Enable/disable module options"""
        self.groupBox_module_options.setEnabled(enabled)
        self.groupBox_modules.setEnabled(enabled)
        self.groupBox_export_options.setEnabled(enabled)
    
    def browse_folder(self, line_edit):
        """Open folder browser dialog"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if folder:
            line_edit.setText(folder)
    
    def select_predefined_targets(self, target_name):
        """Select predefined target collection"""
        # Clear all selections first
        for row in range(self.tableWidget_targets.rowCount()):
            checkbox = self.tableWidget_targets.item(row, 0)
            if checkbox:
                checkbox.setCheckState(QtCore.Qt.Unchecked)
        
        # Select targets based on predefined collection
        if target_name == "!SANS_Triage":
            target_names = ["!SANS_Triage", "WindowsEventLogs", "RegistryHives", "Prefetch"]
        elif target_name == "Quick_System_Info":
            target_names = ["RegistryHives", "WindowsEventLogs", "Prefetch"]
        elif target_name == "Browser_and_Email":
            target_names = ["BrowserHistory"]
        else:
            target_names = []
        
        # Check matching targets
        for row in range(self.tableWidget_targets.rowCount()):
            name_item = self.tableWidget_targets.item(row, 1)
            if name_item and name_item.text() in target_names:
                checkbox = self.tableWidget_targets.item(row, 0)
                if checkbox:
                    checkbox.setCheckState(QtCore.Qt.Checked)
    
    def filter_targets(self, text):
        """Filter targets table based on search text"""
        for row in range(self.tableWidget_targets.rowCount()):
            visible = False
            for col in range(1, 4):  # Skip checkbox column
                item = self.tableWidget_targets.item(row, col)
                if item and text.lower() in item.text().lower():
                    visible = True
                    break
            self.tableWidget_targets.setRowHidden(row, not visible)
    
    def filter_modules(self, text):
        """Filter modules table based on search text"""
        for row in range(self.tableWidget_modules.rowCount()):
            visible = False
            for col in range(1, 4):  # Skip checkbox column
                item = self.tableWidget_modules.item(row, col)
                if item and text.lower() in item.text().lower():
                    visible = True
                    break
            self.tableWidget_modules.setRowHidden(row, not visible)
    
    def on_format_changed(self):
        """Handle image format selection change"""
        # Enable/disable compression options based on format
        use_compression = self.radioButton_e01.isChecked() or self.radioButton_aff.isChecked()
        self.comboBox_compression.setEnabled(use_compression)
        
        # Update UI based on format
        if self.radioButton_raw.isChecked():
            # Raw format doesn't support compression or encryption
            self.checkBox_ad_encryption.setEnabled(False)
            self.checkBox_ad_encryption.setChecked(False)
        else:
            self.checkBox_ad_encryption.setEnabled(True)
        
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def on_compression_changed(self, index):
        """Handle compression level change"""
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def on_fragment_size_changed(self, value):
        """Handle fragment size change"""
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def on_verification_option_changed(self):
        """Handle verification option changes"""
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def update_overview(self):
        """Update the overview page with current configuration"""
        summary = self.generate_configuration_summary()
        self.textBrowser_summary.setHtml(summary)
        
        command = self.build_command_line()
        self.lineEdit_command_line.setText(' '.join(command))
    
    def generate_configuration_summary(self):
        """Generate HTML summary of current configuration"""
        html = "<h3>📋 Tóm tắt Cấu hình</h3>"
        
        # Case information
        html += "<h4>🏷️ Thông tin Vụ việc</h4>"
        html += f"<b>Mã vụ việc:</b> {self.lineEdit_case_id.text()}<br>"
        html += f"<b>Điều tra viên:</b> {self.lineEdit_investigator.text()}<br>"
        html += f"<b>Mô tả:</b> {self.lineEdit_case_description.text()}<br><br>"
        
        # Source device
        html += "<h4>💾 Thiết bị Nguồn</h4>"
        current_row = self.tableWidget_devices.currentRow()
        if current_row >= 0:
            model = self.tableWidget_devices.item(current_row, 0).text()
            partition = self.tableWidget_devices.item(current_row, 3).text()
            size = self.tableWidget_devices.item(current_row, 2).text()
            html += f"<b>Thiết bị:</b> {model}<br>"
            html += f"<b>Phân vùng:</b> {partition}<br>"
            html += f"<b>Dung lượng:</b> {size}<br><br>"
        
        # Collection strategy
        html += "<h4>🎯 Phương pháp Thu thập</h4>"
        if self.radioButton_triage.isChecked():
            html += "<b>Loại:</b> Thu thập Triage (Nhanh & có Mục tiêu)<br>"
            
            if self.checkBox_use_targets.isChecked():
                selected_targets = []
                for row in range(self.tableWidget_targets.rowCount()):
                    checkbox = self.tableWidget_targets.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        name = self.tableWidget_targets.item(row, 1).text()
                        selected_targets.append(name)
                
                html += f"<b>Targets đã chọn:</b> {len(selected_targets)}<br>"
                if selected_targets:
                    html += "<ul>"
                    for target in selected_targets[:5]:  # Show first 5
                        html += f"<li>{target}</li>"
                    if len(selected_targets) > 5:
                        html += f"<li>... và {len(selected_targets) - 5} targets khác</li>"
                    html += "</ul>"
            
            if self.checkBox_use_modules.isChecked():
                selected_modules = []
                for row in range(self.tableWidget_modules.rowCount()):
                    checkbox = self.tableWidget_modules.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        name = self.tableWidget_modules.item(row, 1).text()
                        selected_modules.append(name)
                
                html += f"<b>Modules đã chọn:</b> {len(selected_modules)}<br>"
        else:
            html += "<b>Loại:</b> Tạo ảnh Toàn bộ (Toàn diện & An toàn)<br>"
            
            # Định dạng ảnh
            format_text = "E01" if self.radioButton_e01.isChecked() else \
                         "Raw" if self.radioButton_raw.isChecked() else \
                         "AFF" if self.radioButton_aff.isChecked() else "Unknown"
            html += f"<b>Định dạng:</b> {format_text}<br>"
            
            # Mức độ nén
            compression_level = self.comboBox_compression.currentText()
            if format_text in ["E01", "AFF"]:
                html += f"<b>Mức nén:</b> {compression_level}<br>"
            
            # Phân mảnh
            frag_size = self.spinBox_fragment_size.value()
            if frag_size == 0:
                html += "<b>Phân mảnh:</b> Không phân mảnh<br>"
            else:
                html += f"<b>Phân mảnh:</b> {frag_size} MB<br>"
            
            # Tùy chọn xác minh
            verification_options = []
            if self.checkBox_verify_after_creation.isChecked():
                verification_options.append("Xác minh sau khi tạo")
            if self.checkBox_precalculate_progress.isChecked():
                verification_options.append("Tính toán trước thống kê tiến trình")
            if self.checkBox_create_directory_listing.isChecked():
                verification_options.append("Tạo danh sách thư mục")
            if verification_options:
                html += "<b>Tùy chọn xác minh:</b><ul>"
                for option in verification_options:
                    html += f"<li>{option}</li>"
                html += "</ul>"
            
            # Mã hóa AD
            if self.checkBox_ad_encryption.isChecked():
                html += "<b>Mã hóa AD:</b> Có<br>"
            
            # Hash options
            hashes = []
            if self.checkBox_md5.isChecked(): hashes.append("MD5")
            if self.checkBox_sha1.isChecked(): hashes.append("SHA-1")
            if self.checkBox_sha256.isChecked(): hashes.append("SHA-256")
            html += f"<b>Hash:</b> {', '.join(hashes) if hashes else 'Không'}<br>"
        
        return html
    
    def build_command_line(self):
        """Build the equivalent command line"""
        if self.radioButton_triage.isChecked():
            # KAPE command for triage
            cmd = [self.kape_exe]
            
            # Source
            current_row = self.tableWidget_devices.currentRow()
            if current_row >= 0:
                source = self.tableWidget_devices.item(current_row, 3).text()
                if source.startswith("\\\\.\\"):  # Convert physical drive to drive letter
                    source = self.get_drive_letter(source)
                cmd.extend(["--tsource", source])
            
            # Destination for targets
            target_dest = os.path.join(
                self.lineEdit_target_destination.text() or "C:\\KapeOutput",
                f"KAPE_Triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            module_dest = os.path.join(target_dest, "ModuleOutput")
            cmd.extend(["--tdest", target_dest])
            
            # Targets
            if self.checkBox_use_targets.isChecked():
                selected_targets = []
                for row in range(self.tableWidget_targets.rowCount()):
                    checkbox = self.tableWidget_targets.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        name = self.tableWidget_targets.item(row, 1).text()
                        selected_targets.append(name)
                
                if selected_targets:
                    cmd.extend(["--target", ",".join(selected_targets)])
            
            # Modules
            if self.checkBox_use_modules.isChecked():
                selected_modules = []
                for row in range(self.tableWidget_modules.rowCount()):
                    checkbox = self.tableWidget_modules.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        name = self.tableWidget_modules.item(row, 1).text()
                        selected_modules.append(name)
                
                if selected_modules:
                    cmd.extend(["--module", ",".join(selected_modules)])
                    cmd.extend(["--mdest", module_dest])
            
            # Add VSS option
            cmd.extend(["--vss"])  # Process Volume Shadow Copies
            
            # Add zip option for output
            cmd.extend(["--zip"])  # Always create ZIP for output
            
            # Add debug option for better progress monitoring
            cmd.extend(["--debug"])
            
            return cmd
        else:
            # For imaging, use the existing build_ewf_command or build_dd_command
            current_row = self.tableWidget_devices.currentRow()
            if current_row < 0:
                return ["echo", "No device selected"]
            device_id = self.tableWidget_devices.item(current_row, 1).text()
            
            # Xác định định dạng ảnh
            if self.radioButton_raw.isChecked():
                return self.build_dd_command(device_id)
            else:
                # Xác định định dạng EWF
                if self.radioButton_e01.isChecked():
                    format_type = "encase6"
                elif self.radioButton_aff.isChecked():
                    format_type = "aff"
                else:
                    format_type = "encase6"  # Mặc định E01
                    
                return self.build_ewf_command(device_id, format_type)

    def get_drive_letter(self, physical_drive):
        """Convert physical drive path to drive letter"""
        try:
            if WMI_AVAILABLE:
                c = wmi.WMI()
                for disk in c.Win32_DiskDrive():
                    if disk.DeviceID == physical_drive:
                        for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                            for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                                return logical_disk.DeviceID
            return "C:"  # Default to C: if conversion fails
        except Exception as e:
            print(f"Error converting physical drive to letter: {e}")
            return "C:"

    def start_triage_collection(self):
        """Bắt đầu thu thập triage bằng KAPE"""
        try:
            cmd = self.build_command_line()
            
            # Reset progress
            self.progressBar.setValue(0)
            self.label_errors_val.setText("0")
            self.textBrowser_log.clear()
            
            # Log command
            self.textBrowser_log.append("<b>🚀 Bắt đầu thu thập KAPE...</b>")
            self.textBrowser_log.append(f"<b>Command:</b> {' '.join(cmd)}")
            
            # Create QProcess
            self.kape_process = QtCore.QProcess(self)
            self.kape_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
            self.kape_process.readyReadStandardOutput.connect(self.handle_kape_output)
            self.kape_process.finished.connect(self.kape_process_finished)
            
            # Set working directory
            kape_dir = os.path.dirname(self.kape_exe)
            self.kape_process.setWorkingDirectory(kape_dir)
            
            # Start process
            self.kape_process.start(cmd[0], cmd[1:])
            
            # Update UI
            self.pushButton_start.setEnabled(False)
            self.pushButton_previous.setEnabled(False)
            self.pushButton_pause.setEnabled(True)
            self.pushButton_stop.setEnabled(True)
            self.start_time = time.time()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu KAPE: {str(e)}")
            self.collection_finished(1, QtCore.QProcess.CrashExit)

    def handle_kape_output(self):
        """Handle KAPE output"""
        if self.kape_process:
            output = self.kape_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            
            # Parse progress information
            if "Progress:" in output:
                try:
                    match = re.search(r'Progress:\s*(\d+)%', output)
                    if match:
                        progress = int(match.group(1))
                        self.progressBar.setValue(progress)
                        # Update time and ETA...
                except Exception as e:
                    print(f"Error parsing KAPE progress: {e}")
            
            # Handle errors
            if "ERROR:" in output or "FAILED:" in output:
                self.textBrowser_log.append(f"<span style='color: red;'>{output}</span>")
                current_errors = int(self.label_errors_val.text())
                self.label_errors_val.setText(str(current_errors + 1))
            else:
                self.textBrowser_log.append(output)

    def kape_process_finished(self, exit_code, exit_status):
        """Handle KAPE process completion"""
        if exit_code == 0:
            self.textBrowser_log.append("<b>✅ Thu thập KAPE hoàn tất thành công!</b>")
            self.progressBar.setValue(100)
        else:
            self.textBrowser_log.append(f"<b>❌ Thu thập KAPE thất bại với mã lỗi: {exit_code}</b>")
        
        # Update UI
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)
        
        # Final time update
        if self.start_time:
            total_time = time.time() - self.start_time
            self.label_time_elapsed_val.setText(time.strftime("%H:%M:%S", time.gmtime(total_time)))
            self.label_eta_val.setText("00:00:00")

    def build_ewf_command(self, device_id, format_type):
        """Build command for EWF imaging"""
        ewf_path = os.path.join(self.tools_dir, "ewftools-x64", "ewfacquire.exe")
        
        # Chuẩn hóa đường dẫn output
        output_dir = self.lineEdit_destination_folder.text()
        output_dir = output_dir.replace('/', '\\')  # Chuyển sang Windows path
        if ' ' in output_dir:  # Nếu có dấu cách, bọc trong dấu nháy kép
            output_dir = f'"{output_dir}"'
            
        # Tạo tên file output
        filename = self.lineEdit_image_filename.text()
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)  # Thay thế ký tự không hợp lệ
        
        # Tạo đường dẫn đầy đủ
        output_path = os.path.join(output_dir, filename)
        
        # Xây dựng lệnh cơ bản
        cmd = [
            ewf_path,
            "-t", output_path,  # Target path
            "-f", format_type,  # Format type
            "-u",  # Unattended mode
            "-v",  # Verbose output
            "-q",  # Quiet mode (minimal status info)
            "-b", "64",  # Number of sectors per chunk
            "-j", "4",  # Number of threads
        ]

        # Thêm thông tin vụ việc
        if self.lineEdit_case_id.text():
            case_id = re.sub(r'[<>:"/\\|?*]', '_', self.lineEdit_case_id.text())
            cmd.extend(["-C", case_id])
        if self.lineEdit_case_description.text():
            desc = re.sub(r'[<>:"/\\|?*]', '_', self.lineEdit_case_description.text())
            cmd.extend(["-D", desc])
        if self.lineEdit_investigator.text():
            investigator = re.sub(r'[<>:"/\\|?*]', '_', self.lineEdit_investigator.text())
            cmd.extend(["-e", investigator])

        # Thêm compression level
        compression_map = {
            0: "none",      # No compression
            1: "fast",      # Fast compression
            2: "best"       # Best compression
        }
        compression_level = compression_map.get(self.comboBox_compression.currentIndex(), "none")
        cmd.extend(["-c", f"deflate:{compression_level}"])

        # Thêm segment size nếu có
        frag_size = self.spinBox_fragment_size.value()
        if frag_size > 0:
            segment_bytes = frag_size * 1024 * 1024  # Convert MB to bytes
            cmd.extend(["-S", str(segment_bytes)])

        # Thêm các tùy chọn hash
        hash_types = []
        if self.checkBox_md5.isChecked():
            hash_types.append("md5")
        if self.checkBox_sha1.isChecked():
            hash_types.append("sha1")
        if self.checkBox_sha256.isChecked():
            hash_types.append("sha256")
        if hash_types:
            cmd.extend(["-d", ",".join(hash_types)])

        # Thêm log file
        log_path = f"{output_path}_ewf.log"
        if ' ' in log_path:  # Nếu có dấu cách, bọc trong dấu nháy kép
            log_path = f'"{log_path}"'
        cmd.extend(["-l", log_path])

        # Thêm thiết bị nguồn
        cmd.append(device_id)
        
        return cmd
        
    def build_dd_command(self, device_id):
        """Build command for RAW imaging using dd"""
        output_path = os.path.join(
            self.lineEdit_destination_folder.text(),
            self.lineEdit_image_filename.text() + ".dd"
        )
        
        # RAW dùng dd
        cmd = ["dd", f"if={device_id}", f"of={output_path}", "bs=1M", "status=progress"]
        return cmd

    def get_free_space(self, path):
        """Get free space of a drive"""
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ret = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(path),
                    ctypes.pointer(free_bytes),
                    ctypes.pointer(total_bytes),
                    None
                )
                if ret == 0:
                    raise ctypes.WinError()
                return free_bytes.value
            else:  # Unix/Linux/macOS
                st = os.statvfs(path)
                return st.f_frsize * st.f_bavail
        except Exception as e:
            print(f"Error getting free space: {e}")
            return 0

    def check_disk_space(self, output_path, source_size):
        """Check if there's enough disk space for imaging"""
        try:
            # Get drive letter from path
            if os.name == 'nt':  # Windows
                drive = os.path.splitdrive(output_path)[0]
                if not drive:
                    drive = os.path.abspath(output_path)
            else:
                drive = os.path.dirname(output_path)

            # Get free space
            free_space = self.get_free_space(drive)
            
            # Calculate required space with overhead
            if self.radioButton_raw.isChecked():
                # RAW format: source size + small overhead
                required_space = source_size * 1.01  # 1% overhead
            else:
                # E01/AFF format: depends on compression
                compression_map = {
                    0: 1.01,  # No compression: source size + 1% overhead
                    1: 0.7,   # Fast compression: ~70% of source size
                    2: 0.5    # Best compression: ~50% of source size
                }
                compression_factor = compression_map.get(
                    self.comboBox_compression.currentIndex(), 1.01
                )
                required_space = source_size * compression_factor

            # Add space for logs and metadata
            required_space += 100 * 1024 * 1024  # 100MB for logs and metadata
            
            # Convert to human readable
            free_gb = free_space / (1024**3)
            required_gb = required_space / (1024**3)
            
            if free_space < required_space:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Không đủ dung lượng",
                    f"Không đủ dung lượng trống trên ổ đích!\n\n"
                    f"Dung lượng trống: {free_gb:.1f} GB\n"
                    f"Dung lượng cần thiết: {required_gb:.1f} GB\n\n"
                    f"Vui lòng chọn ổ đích khác có đủ dung lượng trống."
                )
                return False
                
            # Show warning if free space is close to required
            elif free_space < required_space * 1.1:  # Less than 10% margin
                reply = QtWidgets.QMessageBox.warning(
                    self,
                    "Cảnh báo dung lượng",
                    f"Dung lượng trống trên ổ đích gần với dung lượng cần thiết!\n\n"
                    f"Dung lượng trống: {free_gb:.1f} GB\n"
                    f"Dung lượng cần thiết: {required_gb:.1f} GB\n\n"
                    f"Bạn có muốn tiếp tục không?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                return reply == QtWidgets.QMessageBox.Yes
                
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Lỗi",
                f"Không thể kiểm tra dung lượng ổ đĩa: {str(e)}\n"
                "Vui lòng đảm bảo có đủ dung lượng trống trước khi tiếp tục."
            )
            return False

    def start_collection(self):
        """Bắt đầu thu thập dữ liệu"""
        if not is_admin():
            reply = QtWidgets.QMessageBox.warning(
                self,
                "Yêu cầu quyền Administrator",
                "Thu thập dữ liệu cần quyền Administrator.\nVui lòng chạy lại ứng dụng với quyền Administrator.",
                QtWidgets.QMessageBox.Ok
            )
            return

        # Kiểm tra lựa chọn thiết bị
        current_row = self.tableWidget_devices.currentRow()
        if current_row < 0:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thiết bị nguồn!")
            return
            
        device_id = self.tableWidget_devices.item(current_row, 1).text()
        
        # Kiểm tra ổ Windows và cảnh báo
        if "Windows" in self.tableWidget_devices.item(current_row, 0).text():
            if not self.checkBox_accept_risk.isChecked():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    "Bạn đang chọn ổ cài đặt Windows. Vui lòng chấp nhận rủi ro trước khi tiếp tục!"
                )
                return

        # Kiểm tra đường dẫn đích
        if self.radioButton_triage.isChecked():
            if not self.lineEdit_target_destination.text():
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục đích cho triage!")
                return
        else:
            if not self.lineEdit_destination_folder.text():
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục đích cho imaging!")
                return
            if not self.lineEdit_image_filename.text():
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên file ảnh!")
                return

        try:
            # Kiểm tra dung lượng trống
            source_size = self.get_device_size()
            if source_size == 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Lỗi",
                    "Không thể xác định dung lượng thiết bị nguồn!"
                )
                return
                
            # Kiểm tra dung lượng cho imaging
            if not self.radioButton_triage.isChecked():
                if not self.check_disk_space(
                    self.lineEdit_destination_folder.text(),
                    source_size
                ):
                    return

            # Reset progress
            self.progressBar.setValue(0)
            self.label_errors_val.setText("0")
            self.label_source_progress_val.setText("0 GB / 0 GB")
            self.label_speed_val.setText("0 MB/s")
            self.label_time_elapsed_val.setText("00:00:00")
            self.label_eta_val.setText("00:00:00")
            self.start_time = time.time()
            
            # Start progress update timer
            self.update_timer = QtCore.QTimer()
            self.update_timer.timeout.connect(self.update_progress_stats)
            self.update_timer.start(1000)  # Update every second

            # Xây dựng và thực thi lệnh
            if self.radioButton_triage.isChecked():
                self.start_triage_collection()
            else:
                # Lấy lệnh phù hợp
                cmd = self.build_command_line()
                
                # Tạo thư mục đích nếu chưa tồn tại
                output_dir = self.lineEdit_destination_folder.text()
                os.makedirs(output_dir, exist_ok=True)
                
                # Cập nhật UI
                self.pushButton_start.setEnabled(False)
                self.pushButton_previous.setEnabled(False)
                self.pushButton_pause.setEnabled(True)
                self.pushButton_stop.setEnabled(True)
                
                # Log thông tin
                self.textBrowser_log.clear()
                format_type = "RAW" if self.radioButton_raw.isChecked() else "E01" if self.radioButton_e01.isChecked() else "AFF"
                self.textBrowser_log.append(f"<b>🚀 Bắt đầu tạo ảnh {format_type}...</b>")
                self.textBrowser_log.append(f"<b>Thiết bị:</b> {device_id}")
                self.textBrowser_log.append(f"<b>Đích:</b> {output_dir}")
                self.textBrowser_log.append(f"<b>Lệnh:</b> {' '.join(cmd)}")
                self.textBrowser_log.append("=" * 50)
                
                # Khởi chạy tiến trình
                self.imaging_process = QtCore.QProcess(self)
                self.imaging_process.readyReadStandardOutput.connect(self.handle_imaging_stdout)
                self.imaging_process.readyReadStandardError.connect(self.handle_imaging_stderr)
                self.imaging_process.finished.connect(self.imaging_process_finished)
                
                # Set working directory nếu dùng ewfacquire
                if not self.radioButton_raw.isChecked():
                    ewf_path = os.path.join(self.tools_dir, "ewftools-x64")
                    self.imaging_process.setWorkingDirectory(ewf_path)
                
                # Bắt đầu tiến trình
                self.imaging_process.start(cmd[0], cmd[1:])
                self.imaging_active = True

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu thu thập: {str(e)}")
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            self.imaging_failed(str(e))

    def update_progress_stats(self):
        """Update progress statistics periodically"""
        if not hasattr(self, 'start_time'):
            return
            
        # Update elapsed time
        elapsed = time.time() - self.start_time
        self.label_time_elapsed_val.setText(
            time.strftime("%H:%M:%S", time.gmtime(elapsed))
        )
        
        # Get current progress
        progress = self.progressBar.value()
        
        # Update ETA if we have progress
        if progress > 0:
            total_time = elapsed * 100 / progress
            remaining = total_time - elapsed
            self.label_eta_val.setText(
                time.strftime("%H:%M:%S", time.gmtime(remaining))
            )
            
        # Force UI update
        QtWidgets.QApplication.processEvents()

    def imaging_process_finished(self, exit_code, exit_status):
        """Handle imaging process completion"""
        # Stop progress update timer
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
            
        if exit_code == 0:
            self.textBrowser_log.append("<b>✅ Thu thập image hoàn tất!</b>")
            self.progressBar.setValue(100)
            
            # Update final progress
            if hasattr(self, 'start_time'):
                total_time = time.time() - self.start_time
                self.label_time_elapsed_val.setText(time.strftime("%H:%M:%S", time.gmtime(total_time)))
                self.label_eta_val.setText("00:00:00")
        else:
            self.textBrowser_log.append(f"<b>❌ Thu thập image thất bại với mã lỗi: {exit_code}</b>")
        
        self.imaging_active = False
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)

    def handle_imaging_stdout(self):
        """Handle standard output from imaging process"""
        if hasattr(self, 'imaging_process'):
            output = self.imaging_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            
            # Parse ewfacquire progress
            if "acquiry_percentage" in output:
                try:
                    # Example: "acquiry_percentage: 25"
                    match = re.search(r'acquiry_percentage:\s*(\d+)', output)
                    if match:
                        progress = int(match.group(1))
                        self.progressBar.setValue(progress)
                        
                        # Update elapsed time
                        if self.start_time:
                            elapsed = time.time() - self.start_time
                            self.label_time_elapsed_val.setText(
                                time.strftime("%H:%M:%S", time.gmtime(elapsed))
                            )
                            
                            # Calculate ETA based on progress
                            if progress > 0:
                                total_time = elapsed * 100 / progress
                                remaining = total_time - elapsed
                                self.label_eta_val.setText(
                                    time.strftime("%H:%M:%S", time.gmtime(remaining))
                                )
                except Exception as e:
                    print(f"Error parsing ewfacquire progress: {e}")
                    
            # Parse speed information
            if "bytes_per_second" in output:
                try:
                    # Example: "bytes_per_second: 52428800"
                    match = re.search(r'bytes_per_second:\s*(\d+)', output)
                    if match:
                        bytes_per_sec = int(match.group(1))
                        mb_per_sec = bytes_per_sec / (1024 * 1024)
                        self.label_speed_val.setText(f"{mb_per_sec:.1f} MB/s")
                except Exception as e:
                    print(f"Error parsing speed: {e}")
                    
            # Parse total bytes information
            if "bytes_read" in output:
                try:
                    # Example: "bytes_read: 1073741824"
                    match = re.search(r'bytes_read:\s*(\d+)', output)
                    if match:
                        bytes_read = int(match.group(1))
                        total_size = self.get_device_size()
                        if total_size > 0:
                            gb_read = bytes_read / (1024**3)
                            total_gb = total_size / (1024**3)
                            self.label_source_progress_val.setText(
                                f"{gb_read:.1f} GB / {total_gb:.1f} GB"
                            )
                except Exception as e:
                    print(f"Error parsing bytes read: {e}")
            
            # Log output if it's not just progress information
            if not any(x in output for x in ['acquiry_percentage', 'bytes_per_second', 'bytes_read']):
                self.textBrowser_log.append(output.strip())

    def handle_imaging_stderr(self):
        """Handle errors and progress information from dc3dd"""
        if hasattr(self, 'imaging_process'):
            error = self.imaging_process.readAllStandardError().data().decode('utf-8', errors='ignore')
            
            # Parse dc3dd progress
            if "copied" in error:
                try:
                    # Example: "1234567 bytes (1.2 GB) copied, 123.4 s, 10.5 MB/s"
                    match = re.search(r'(\d+)\s+bytes\s+\(([\d.]+\s+\w+)\)\s+copied,\s+([\d.]+)\s+s,\s+([\d.]+)\s+MB/s', error)
                    if match:
                        bytes_copied = int(match.group(1))
                        human_size = match.group(2)
                        elapsed_seconds = float(match.group(3))
                        speed_mbs = float(match.group(4))
                        
                        # Get total device size
                        total_bytes = self.get_device_size()
                        
                        # Update progress bar
                        if total_bytes > 0:
                            progress = (bytes_copied / total_bytes) * 100
                            self.progressBar.setValue(int(progress))
                            
                            # Update progress information
                            total_gb = total_bytes / (1024**3)
                            copied_gb = bytes_copied / (1024**3)
                            self.label_source_progress_val.setText(f"{copied_gb:.1f} GB / {total_gb:.1f} GB")
                            
                            # Update speed
                            self.label_speed_val.setText(f"{speed_mbs:.1f} MB/s")
                            
                            # Update elapsed time
                            self.label_time_elapsed_val.setText(
                                time.strftime("%H:%M:%S", time.gmtime(elapsed_seconds))
                            )
                            
                            # Calculate and update ETA
                            if speed_mbs > 0:
                                remaining_bytes = total_bytes - bytes_copied
                                eta_seconds = remaining_bytes / (speed_mbs * 1024 * 1024)
                                self.label_eta_val.setText(
                                    time.strftime("%H:%M:%S", time.gmtime(eta_seconds))
                                )
                        
                        # Log progress with color
                        self.textBrowser_log.append(
                            f"<span style='color: #2196F3;'>"
                            f"Đã sao chép: {human_size} ({progress:.1f}%) - "
                            f"Tốc độ: {speed_mbs:.1f} MB/s"
                            f"</span>"
                        )
                except Exception as e:
                    print(f"Error parsing dc3dd progress: {e}")
            
            # Handle errors
            elif "error" in error.lower() or "failed" in error.lower():
                self.textBrowser_log.append(f"<span style='color: red;'>{error}</span>")
                current_errors = int(self.label_errors_val.text())
                self.label_errors_val.setText(str(current_errors + 1))
            
            # Log other messages
            elif error.strip() and not any(x in error.lower() for x in ['copied', 'bytes', 'speed']):
                self.textBrowser_log.append(error.strip())

    def get_device_size(self):
        """Get total size of selected device"""
        try:
            current_row = self.tableWidget_devices.currentRow()
            if current_row >= 0:
                # Get size from table
                size_text = self.tableWidget_devices.item(current_row, 2).text()
                if size_text:
                    # Convert "X.X GB" to bytes
                    size_gb = float(size_text.split()[0])
                    return int(size_gb * 1024 * 1024 * 1024)
                
                # If size not in table, try to get from WMI
                device_id = self.tableWidget_devices.item(current_row, 1).text()
                if WMI_AVAILABLE:
                    c = wmi.WMI()
                    for disk in c.Win32_DiskDrive():
                        if disk.DeviceID == device_id:
                            return int(disk.Size)
                
                # If WMI fails, try direct Windows API
                if WIN32_AVAILABLE and device_id.startswith("\\\\.\\"):
                    try:
                        # Open device
                        hDevice = win32file.CreateFile(
                            device_id,
                            win32file.GENERIC_READ,
                            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                            None,
                            win32file.OPEN_EXISTING,
                            0,
                            None
                        )
                        
                        # Get device size
                        size = win32file.GetFileSize(hDevice)
                        win32file.CloseHandle(hDevice)
                        return size
                    except:
                        pass
            
            return 0
        except Exception as e:
            print(f"Error getting device size: {e}")
            return 0

    def imaging_completed(self, total_bytes, total_size, hash_value):
        """Xử lý khi imaging hoàn tất"""
        # Cập nhật UI
        self.progressBar.setValue(100)
        self.textBrowser_log.append("<b>✅ Thu thập image hoàn tất!</b>")
        self.textBrowser_log.append(f"<b>Tổng dung lượng:</b> {total_bytes / (1024**3):.1f} GB")
        self.textBrowser_log.append(f"<b>Hash values:</b><br>{hash_value}")
        
        # Reset state
        self.imaging_active = False
        self.imaging_paused = False
        
        # Enable controls
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)
        
        # Thông báo
        QtWidgets.QMessageBox.information(
            self,
            "Hoàn thành",
            f"Thu thập image hoàn tất!\n{hash_value}"
        )

    def imaging_failed(self, error):
        """Xử lý khi imaging thất bại"""
        self.textBrowser_log.append(f"<span style='color: red;'><b>❌ Lỗi:</b> {error}</span>")
        self.label_errors_val.setText(str(int(self.label_errors_val.text()) + 1))
        
        # Reset state
        self.imaging_active = False
        self.imaging_paused = False
        
        # Enable controls
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)
        
        # Thông báo
        QtWidgets.QMessageBox.critical(
            self,
            "Lỗi",
            f"Thu thập image thất bại!\nLỗi: {error}"
        )

    def prepare_collection(self):
        """Prepare for collection on step 5"""
        # Enable collection controls
        self.pushButton_pause.setEnabled(True)
        self.pushButton_stop.setEnabled(True)
        self.pushButton_save_log.setEnabled(True)
        
        # Reset progress
        self.progressBar.setValue(0)
        self.label_errors_val.setText("0")
        self.textBrowser_log.clear()
        
        # Check if we're ready to start
        if self.radioButton_triage.isChecked():
            # Check if any targets or modules are selected
            has_targets = False
            has_modules = False
            
            if self.checkBox_use_targets.isChecked():
                for row in range(self.tableWidget_targets.rowCount()):
                    checkbox = self.tableWidget_targets.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        has_targets = True
                        break
            
            if self.checkBox_use_modules.isChecked():
                for row in range(self.tableWidget_modules.rowCount()):
                    checkbox = self.tableWidget_modules.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        has_modules = True
                        break
            
            if not (has_targets or has_modules):
                self.textBrowser_log.append(
                    "<span style='color: red;'>"
                    "⚠️ Vui lòng chọn ít nhất một Target hoặc Module để thu thập!"
                    "</span>"
                )
                self.pushButton_start.setEnabled(False)
                return
            
            # Show selected targets and modules
            self.textBrowser_log.append("<b>✅ Sẵn sàng thu thập Triage</b>")
            self.textBrowser_log.append(f"<b>Thiết bị nguồn:</b> {self.lineEdit_target_source.text()}")
            self.textBrowser_log.append(f"<b>Thư mục đích:</b> {self.lineEdit_target_destination.text()}")
            
            if has_targets:
                self.textBrowser_log.append("\n<b>Targets đã chọn:</b>")
                for row in range(self.tableWidget_targets.rowCount()):
                    checkbox = self.tableWidget_targets.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        name = self.tableWidget_targets.item(row, 1).text()
                        desc = self.tableWidget_targets.item(row, 3).text()
                        self.textBrowser_log.append(f"• {name}: {desc}")
            
            if has_modules:
                self.textBrowser_log.append("\n<b>Modules đã chọn:</b>")
                for row in range(self.tableWidget_modules.rowCount()):
                    checkbox = self.tableWidget_modules.item(row, 0)
                    if checkbox and checkbox.checkState() == QtCore.Qt.Checked:
                        name = self.tableWidget_modules.item(row, 1).text()
                        desc = self.tableWidget_modules.item(row, 3).text()
                        self.textBrowser_log.append(f"• {name}: {desc}")
            
            self.textBrowser_log.append("\nNhấn 'Bắt đầu Thu thập' để tiếp tục.")
            
        else:  # Imaging mode
            # Show imaging information
            self.textBrowser_log.append("<b>✅ Sẵn sàng tạo Image</b>")
            self.textBrowser_log.append(f"<b>Thiết bị nguồn:</b> {self.lineEdit_image_source.text()}")
            self.textBrowser_log.append(f"<b>Thư mục đích:</b> {self.lineEdit_destination_folder.text()}")
            self.textBrowser_log.append(f"<b>Tên file:</b> {self.lineEdit_image_filename.text()}")
            
            # Show format and options
            format_type = "E01" if self.radioButton_e01.isChecked() else "RAW" if self.radioButton_raw.isChecked() else "AFF"
            self.textBrowser_log.append(f"<b>Định dạng:</b> {format_type}")
            
            if not self.radioButton_raw.isChecked():
                compression = self.comboBox_compression.currentText()
                self.textBrowser_log.append(f"<b>Mức nén:</b> {compression}")
            
            # Show hash options
            hash_types = []
            if self.checkBox_md5.isChecked(): hash_types.append("MD5")
            if self.checkBox_sha1.isChecked(): hash_types.append("SHA1")
            if self.checkBox_sha256.isChecked(): hash_types.append("SHA256")
            if hash_types:
                self.textBrowser_log.append(f"<b>Hash:</b> {', '.join(hash_types)}")
            
            self.textBrowser_log.append("\nNhấn 'Bắt đầu Thu thập' để tiếp tục.")

    def pause_collection(self):
        """Tạm dừng/tiếp tục thu thập"""
        if self.imaging_active:
            # Pause/resume imaging
            self.imaging_paused = not self.imaging_paused
            if self.imaging_paused:
                self.pushButton_pause.setText("▶️ Tiếp tục")
                self.textBrowser_log.append("<b>⏸️ Đã tạm dừng thu thập</b>")
            else:
                self.pushButton_pause.setText("⏸️ Tạm dừng")
                self.textBrowser_log.append("<b>▶️ Tiếp tục thu thập</b>")
        elif self.kape_process:
            # Pause/resume KAPE
            if not self.paused:
                self.kape_process.kill()
                self.pushButton_pause.setText("▶️ Tiếp tục")
                self.paused = True
            else:
                self.start_collection()
                self.pushButton_pause.setText("⏸️ Tạm dừng")
                self.paused = False

    def stop_collection(self):
        """Dừng thu thập"""
        if self.imaging_active:
            # Stop imaging
            if hasattr(self, 'imaging_process'):
                self.imaging_process.kill()  # Force stop the process
            self.imaging_active = False
            self.imaging_paused = False
            self.textBrowser_log.append("<b>⏹️ Thu thập đã bị dừng bởi người dùng</b>")
            self.pushButton_start.setEnabled(True)
            self.pushButton_previous.setEnabled(True)
            self.pushButton_pause.setEnabled(False)
            self.pushButton_stop.setEnabled(False)
        elif self.kape_process:
            # Stop KAPE
            self.kape_process.kill()
            self.textBrowser_log.append("<b>⏹️ Thu thập KAPE đã bị dừng bởi người dùng</b>")

    def handle_stdout(self):
        """Handle standard output from KAPE process"""
        if self.kape_process:
            output = self.kape_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            self.textBrowser_log.append(output)
            
            # Parse progress if available
            progress_match = re.search(r'(\d+)%', output)
            if progress_match:
                progress = int(progress_match.group(1))
                self.progressBar.setValue(progress)
    
    def handle_stderr(self):
        """Handle standard error from KAPE process"""
        if self.kape_process:
            error = self.kape_process.readAllStandardError().data().decode('utf-8', errors='ignore')
            self.textBrowser_log.append(f"<span style='color: red;'>{error}</span>")
            
            # Increment error count
            current_errors = int(self.label_errors_val.text())
            self.label_errors_val.setText(str(current_errors + 1))
    
    def collection_finished(self, exit_code, exit_status):
        """Handle collection completion"""
        if hasattr(self, 'timer'):
            self.timer.stop()
        
        # Update UI
        self.pushButton_start.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)
        
        # Show completion message
        if exit_code == 0:
            self.textBrowser_log.append("<b>✅ Thu thập hoàn tất thành công!</b>")
            self.progressBar.setValue(100)
        else:
            self.textBrowser_log.append(f"<b>❌ Thu thập kết thúc với lỗi (mã: {exit_code})</b>")
        
        # Final time update
        if self.start_time:
            total_time = time.time() - self.start_time
            self.label_time_elapsed_val.setText(time.strftime("%H:%M:%S", time.gmtime(total_time)))
            self.label_eta_val.setText("00:00:00")
    
    def save_log(self):
        """Save collection log to file"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Lưu nhật ký", 
            f"collection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.textBrowser_log.toPlainText())
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu nhật ký vào: {filename}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể lưu nhật ký: {str(e)}")

    def on_device_selection_changed(self):
        """Handle device selection change"""
        current_row = self.tableWidget_devices.currentRow()
        if current_row >= 0:
            # Get current timestamp
            timestamp = datetime.now().strftime('%Y%m%d-%H%M')
            
            # Get device info
            device_id = self.tableWidget_devices.item(current_row, 1).text()
            model = self.tableWidget_devices.item(current_row, 0).text()
            size_text = self.tableWidget_devices.item(current_row, 2).text()
            
            # Update image source field
            self.lineEdit_image_source.setText(f"{model} ({device_id})")
            
            # Get drive letter for triage source
            source_drive = device_id
            if source_drive.startswith("\\\\.\\"):
                source_drive = self.get_drive_letter(source_drive)
            self.lineEdit_target_source.setText(source_drive)
            
            # Update case ID if not set
            if not self.lineEdit_case_id.text():
                self.lineEdit_case_id.setText(f"Case-{timestamp}")
                
            # Update image filename if not set
            if not self.lineEdit_image_filename.text():
                safe_model = re.sub(r'[^\w\-]', '_', model)
                self.lineEdit_image_filename.setText(f"{safe_model}_{timestamp}")
            
            # Update source size display
            if hasattr(self, 'label_source_size'):
                if size_text and size_text != "Unknown":
                    self.label_source_size.setText(size_text)
                else:
                    size_bytes = self.get_device_size()
                    if size_bytes > 0:
                        size_gb = size_bytes / (1024**3)
                        self.label_source_size.setText(f"{size_gb:.1f} GB")
                    else:
                        self.label_source_size.setText("Unknown")
    
    def browse_target_destination(self):
        """Browse for triage destination folder"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục đích cho Triage",
            self.lineEdit_target_destination.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_target_destination.setText(folder)

    def browse_image_destination(self):
        """Browse for image destination folder"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục đích cho Image",
            self.lineEdit_destination_folder.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_destination_folder.setText(folder)

    def format_size(self, size_bytes):
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def update_image_path(self):
        """Update full image path when folder or filename changes"""
        folder = self.lineEdit_destination_folder.text()
        filename = self.lineEdit_image_filename.text()
        
        if folder and filename:
            # Add extension based on format
            if self.radioButton_e01.isChecked():
                ext = ".E01"
            elif self.radioButton_aff.isChecked():
                ext = ".aff"
            else:
                ext = ".dd"
                
            # Tạo đường dẫn đầy đủ
            full_path = os.path.join(folder, filename + ext)
            
            # Cập nhật preview path
            self.label_preview_path.setText(f"File sẽ được lưu tại: {full_path}")
            
            # Kiểm tra xem file đã tồn tại chưa
            if os.path.exists(full_path):
                self.label_preview_path.setStyleSheet("color: red;")
                self.label_preview_path.setText(
                    f"⚠️ Cảnh báo: File đã tồn tại tại {full_path}"
                )
            else:
                self.label_preview_path.setStyleSheet("")

# Create an alias for backward compatibility
CollectNonvolatileController = NonVolatilePage

class KapeDataLoader(QtCore.QObject):
    finished = QtCore.pyqtSignal(list, list)
    
    def __init__(self, tools_dir):
        super().__init__()
        self.tools_dir = tools_dir
        
    def run(self):
        """Load KAPE targets and modules in background"""
        targets = self.load_targets()
        modules = self.load_modules()
        self.finished.emit(targets, modules)
        
    def load_targets(self):
        """Load KAPE targets"""
        targets = []
        kape_targets_path = os.path.join(self.tools_dir, "KAPE", "Targets")
        
        if os.path.isdir(kape_targets_path):
            try:
                target_files = glob.glob(os.path.join(kape_targets_path, "**", "*.tkape"), recursive=True)
                for target_file in target_files[:100]:  # Limit for performance
                    try:
                        with open(target_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        name = os.path.splitext(os.path.basename(target_file))[0]
                        category = os.path.basename(os.path.dirname(target_file))
                        description = self.extract_description(content)
                        targets.append((name, category, description))
                    except:
                        continue
            except:
                pass
                
        # Add dummy targets if needed
        if len(targets) < 10:
            targets.extend(self.get_dummy_targets())
            
        return targets
        
    def load_modules(self):
        """Load KAPE modules"""
        modules = []
        kape_modules_path = os.path.join(self.tools_dir, "KAPE", "Modules")
        
        if os.path.isdir(kape_modules_path):
            try:
                module_files = glob.glob(os.path.join(kape_modules_path, "**", "*.mkape"), recursive=True)
                for module_file in module_files[:50]:  # Limit for performance
                    try:
                        with open(module_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        name = os.path.splitext(os.path.basename(module_file))[0]
                        category = os.path.basename(os.path.dirname(module_file))
                        description = self.extract_description(content)
                        modules.append((name, category, description))
                    except:
                        continue
            except:
                pass
                
        # Add dummy modules if needed
        if len(modules) < 10:
            modules.extend(self.get_dummy_modules())
            
        return modules
        
    def extract_description(self, content):
        """Extract description from KAPE file content"""
        for line in content.split('\n'):
            if line.strip().startswith('Description:'):
                return line.split(':', 1)[1].strip()
        return "No description"
        
    def get_dummy_targets(self):
        """Get list of dummy targets"""
        return [
            ("!SANS_Triage", "Compound", "SANS Digital Forensics and Incident Response Triage Collection"),
            ("Chrome", "Apps", "Chrome browser artifacts"),
            ("WindowsEventLogs", "EventLogs", "Windows Event Log files"),
            ("Prefetch", "Execution", "Windows Prefetch files"),
            ("MFT", "FileSystem", "Master File Table"),
            # Add more as needed
        ]
        
    def get_dummy_modules(self):
        """Get list of dummy modules"""
        return [
            ("ChromiumParser", "Browsers", "Parse Chromium-based browser artifacts"),
            ("EvtxECmd", "EventLogs", "Parse Windows Event Log files"),
            ("PECmd", "Execution", "Parse Windows Prefetch files"),
            ("MFTECmd", "FileSystem", "Parse Master File Table"),
            ("RegistryParser", "Registry", "Parse registry hives"),
            # Add more as needed
        ]
        
class DeviceScanner(QtCore.QObject):
    devicesFound = QtCore.pyqtSignal(list)
    
    def scan(self):
        """Scan for storage devices"""
        devices = []
        
        if WMI_AVAILABLE:
            try:
                c = wmi.WMI()
                # Lấy thông tin về các ổ đĩa vật lý
                physical_disks = {}
                
                # Tạo từ điển ánh xạ giữa ổ đĩa vật lý và phân vùng
                disk_to_partitions = {}
                
                # Lấy thông tin về các ổ đĩa vật lý
                for disk in c.Win32_DiskDrive():
                    disk_id = disk.DeviceID
                    physical_disks[disk_id] = {
                        'model': disk.Model or "Unknown",
                        'serial': disk.SerialNumber or "Unknown",
                        'size': disk.Size,
                        'status': disk.Status or "Unknown",
                        'interface': disk.InterfaceType or "Unknown",
                        'partitions': [],
                        'logical_drives': []
                    }
                    
                # Lấy thông tin về các phân vùng và ổ đĩa logic
                for partition in c.Win32_DiskPartition():
                    for disk in c.Win32_DiskDrive():
                        for disk_partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                            if partition.DeviceID == disk_partition.DeviceID:
                                if disk.DeviceID not in disk_to_partitions:
                                    disk_to_partitions[disk.DeviceID] = []
                                
                                partition_info = {
                                    'name': partition.Name,
                                    'size': partition.Size,
                                    'type': partition.Type,
                                    'bootable': partition.Bootable,
                                    'logical_drives': []
                                }
                                
                                # Tìm các ổ đĩa logic liên kết với phân vùng này
                                for logical_disk in c.Win32_LogicalDisk():
                                    for partition_logical in partition.associators("Win32_LogicalDiskToPartition"):
                                        if logical_disk.DeviceID == partition_logical.DeviceID:
                                            drive_info = {
                                                'letter': logical_disk.DeviceID,
                                                'filesystem': logical_disk.FileSystem or "Unknown",
                                                'size': logical_disk.Size,
                                                'free_space': logical_disk.FreeSpace,
                                                'volume_name': logical_disk.VolumeName or ""
                                            }
                                            partition_info['logical_drives'].append(drive_info)
                                            if disk.DeviceID in physical_disks:
                                                physical_disks[disk.DeviceID]['logical_drives'].append(drive_info)
                                
                                if disk.DeviceID in physical_disks:
                                    physical_disks[disk.DeviceID]['partitions'].append(partition_info)
                
                # Chuyển đổi thành danh sách thiết bị
                for disk_id, disk_info in physical_disks.items():
                    # Kiểm tra xem có phải ổ Windows không
                    is_windows = False
                    drive_letters = []
                    filesystems = []
                    
                    for drive in disk_info['logical_drives']:
                        drive_letters.append(drive['letter'])
                        if drive['filesystem'] not in filesystems:
                            filesystems.append(drive['filesystem'])
                        if drive['letter'] == "C:":
                            is_windows = True
                    
                    # Tính toán dung lượng
                    try:
                        size_gb = float(disk_info['size']) / (1024**3)
                        size_display = f"{size_gb:.1f} GB"
                    except:
                        size_display = "Unknown"
                    
                    device = {
                        'id': disk_id,
                        'model': disk_info['model'],
                        'serial': disk_info['serial'],
                        'size': size_display,
                        'filesystem': ", ".join(filesystems) if filesystems else "Unknown",
                        'partitions': ", ".join(drive_letters) if drive_letters else "No logical drives",
                        'is_windows': is_windows,
                        'encryption': self.check_encryption(disk_id)
                    }
                    devices.append(device)
            except Exception as e:
                print(f"Error scanning devices with WMI: {e}")
                devices = self.scan_fallback()
        else:
            # Fallback to simpler method if WMI is not available
            devices = self.scan_fallback()
            
        self.devicesFound.emit(devices)
        
    def format_size(self, size_bytes):
        """Format size in bytes to human readable format"""
        try:
            size_gb = int(size_bytes) / (1024**3)
            return f"{size_gb:.1f} GB"
        except:
            return "Unknown"
            
    def check_encryption(self, drive_id):
        """Check encryption status (simplified)"""
        return "Unknown"  # For better performance, we'll check encryption status on demand
        
    def scan_fallback(self):
        """Fallback method to get device list"""
        devices = []
        try:
            # Get logical disks
            result = subprocess.run(
                ["wmic", "logicaldisk", "get", "deviceid,size,filesystem,volumename,freespace"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        
                        # Extract filesystem if available
                        filesystem = "Unknown"
                        if len(parts) >= 3:
                            filesystem = parts[2]
                        
                        # Extract volume name if available
                        volume_name = ""
                        if len(parts) >= 4:
                            volume_name = " ".join(parts[3:-2])  # Assuming last two parts are size and free space
                        
                        # Calculate size
                        try:
                            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
                            size_gb = size_bytes / (1024**3)
                            size = f"{size_gb:.1f} GB"
                        except:
                            size = "Unknown"
                        
                        device = {
                            'id': device_id,
                            'model': f"{device_id} ({volume_name})" if volume_name else device_id,
                            'serial': "Unknown",
                            'size': size,
                            'filesystem': filesystem,
                            'partitions': device_id,
                            'is_windows': device_id == "C:",
                            'encryption': "Unknown"
                        }
                        devices.append(device)
        except Exception as e:
            print(f"Error in scan_fallback: {e}")
            
        return devices