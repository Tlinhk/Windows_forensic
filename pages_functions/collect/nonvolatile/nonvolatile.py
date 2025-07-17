# -*- coding: utf-8 -*-
import sys
import os
import json
import subprocess
import threading
import time
import glob
import re
import hashlib
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
        self.imaging_paused = False
        self.block_size = 1024 * 1024  # 1MB block
        
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
        self.load_kape_data()
        self.refresh_devices()
        
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
        self.toolButton_target_destination.clicked.connect(lambda: self.browse_folder(self.lineEdit_target_destination))
        self.toolButton_module_source.clicked.connect(lambda: self.browse_folder(self.lineEdit_module_source))
        self.toolButton_module_destination.clicked.connect(lambda: self.browse_folder(self.lineEdit_module_destination))
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
        
        return True
    
    def update_config_page(self):
        """Update the configuration page based on selected strategy"""
        if self.radioButton_triage.isChecked():
            self.stackedWidget_config.setCurrentWidget(self.page_triage_config)
        else:
            self.stackedWidget_config.setCurrentWidget(self.page_image_config)
    
    def on_strategy_changed(self):
        """Handle strategy selection change"""
        self.update_config_page()
    
    def refresh_devices(self):
        """Quét và hiển thị danh sách ổ cứng"""
        self.tableWidget_devices.setRowCount(0)
        
        try:
            # Sử dụng wmic để lấy thông tin ổ cứng
            result = subprocess.run(
                ['wmic', 'diskdrive', 'get', 'DeviceID,Model,Size,Status,SerialNumber', '/format:csv'],
                capture_output=True, text=True, shell=True
            )
            
            # Lấy ổ cài Windows để đánh dấu
            windows_drive = os.environ.get('SystemDrive', 'C:')
            
            lines = result.stdout.strip().split('\n')[1:]  # Bỏ header
            for line in lines:
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 6:
                        device_id = parts[1].strip()
                        model = parts[2].strip() or "Unknown"
                        size = parts[3].strip()
                        status = parts[4].strip() or "Unknown"
                        serial = parts[5].strip() or "Unknown"
                        
                        # Chuyển size sang GB
                        try:
                            size_gb = int(size) / (1024**3)
                            size_display = f"{size_gb:.1f} GB"
                        except:
                            size_display = "Unknown"
                        
                        # Thêm vào table
                        row = self.tableWidget_devices.rowCount()
                        self.tableWidget_devices.insertRow(row)
                        
                        # Kiểm tra xem có phải ổ Windows không
                        is_windows = device_id.endswith('0') and windows_drive.upper() == 'C:'
                        model_display = f"{model} ({serial})"
                        if is_windows:
                            model_display += " (Windows OS)"
                            
                        self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
                        self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(device_id))
                        self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(size_display))
                        self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(status))
                        self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem(
                            self.check_encryption_status(device_id)
                        ))
                        
                        # Highlight Windows drive
                        if is_windows:
                            for col in range(5):
                                item = self.tableWidget_devices.item(row, col)
                                if item:
                                    item.setBackground(QtGui.QColor(255, 255, 200))

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể lấy danh sách thiết bị: {str(e)}")

    def refresh_devices_fallback(self):
        """Fallback method to get device list using WMIC"""
        try:
            # Get logical drives
            result = subprocess.run(
                ["wmic", "logicaldisk", "where", "drivetype=3", "get", "deviceid,size,filesystem"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        try:
                            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
                            size_gb = size_bytes / (1024**3)
                            size = f"{size_gb:.1f} GB"
                        except:
                            size = "Unknown"
                        
                        row = self.tableWidget_devices.rowCount()
                        self.tableWidget_devices.insertRow(row)
                        
                        self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem("Unknown Device"))
                        self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem("Unknown"))
                        self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(size))
                        self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(device_id))
                        self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem("Unknown"))
                        
                        # Highlight C: drive
                        if device_id == "C:":
                            for col in range(5):
                                item = self.tableWidget_devices.item(row, col)
                                if item:
                                    item.setBackground(QtGui.QColor(255, 255, 200))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể tải danh sách thiết bị: {str(e)}")
    
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
    
    def load_kape_data(self):
        """Load KAPE targets and modules"""
        self.load_targets()
        self.load_modules()
    
    def load_targets(self):
        """Load KAPE targets from .tkape files"""
        self.tableWidget_targets.setRowCount(0)
        
        # Look for KAPE targets directory
        kape_targets_path = self.find_kape_targets_path()
        if not kape_targets_path:
            # Add some dummy targets for demonstration
            self.add_dummy_targets()
            return
        
        try:
            target_files = glob.glob(os.path.join(kape_targets_path, "**", "*.tkape"), recursive=True)
            
            for target_file in target_files[:100]:  # Increase to 100 for more targets
                try:
                    with open(target_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Parse target file (simplified)
                    name = os.path.splitext(os.path.basename(target_file))[0]
                    category = os.path.basename(os.path.dirname(target_file))
                    description = self.extract_description_from_tkape(content)
                    
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
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error loading targets: {e}")
            self.add_dummy_targets()
    
    def find_kape_targets_path(self):
        """Find KAPE targets directory"""
        path = os.path.join(self.tools_dir, "KAPE", "Targets")
        return path if os.path.isdir(path) else None
    
    def add_dummy_targets(self):
        """Add comprehensive dummy targets for demonstration"""
        dummy_targets = [
            # Compound targets
            ("!SANS_Triage", "Compound", "SANS Digital Forensics and Incident Response Triage Collection"),
            ("!BasicCollection", "Compound", "Basic collection for Windows endpoint"),
            ("!EZParser", "Compound", "Collection targets to feed EZ Tools"),
            
            # Applications
            ("Chrome", "Apps", "Chrome browser artifacts"),
            ("Firefox", "Apps", "Firefox browser artifacts"),
            ("Edge", "Apps", "Microsoft Edge browser artifacts"),
            ("InternetExplorer", "Apps", "Internet Explorer artifacts"),
            ("Outlook", "Apps", "Microsoft Outlook artifacts"),
            ("Skype", "Apps", "Skype artifacts"),
            ("Discord", "Apps", "Discord artifacts"),
            ("Teams", "Apps", "Microsoft Teams artifacts"),
            
            # EventLogs
            ("WindowsEventLogs", "EventLogs", "Windows Event Log files"),
            ("PowerShellHistory", "EventLogs", "PowerShell command history"),
            ("ScheduledTasks", "EventLogs", "Windows Scheduled Tasks"),
            
            # Execution
            ("Prefetch", "Execution", "Windows Prefetch files"),
            ("UserAssist", "Execution", "User Assist registry keys"),
            ("JumpLists", "Execution", "Jump Lists"),
            ("RecentFileCache", "Execution", "Recent File Cache"),
            ("Shimcache", "Execution", "Application Compatibility Shimcache"),
            ("Amcache", "Execution", "Amcache.hve file"),
            
            # FileFolderAccess
            ("LnkFilesAndJumpLists", "FileFolderAccess", "Link files and Jump Lists"),
            ("RecentDocs", "FileFolderAccess", "Recent documents"),
            ("SearchHistory", "FileFolderAccess", "Windows Search History"),
            
            # FileSystem
            ("MFT", "FileSystem", "Master File Table"),
            ("LogFile", "FileSystem", "NTFS LogFile"),
            ("USNJournal", "FileSystem", "NTFS USN Journal"),
            ("RecycleBin", "FileSystem", "Recycle Bin"),
            
            # Registry
            ("RegistryHives", "Registry", "All registry hives"),
            ("RegistryHivesSystem", "Registry", "System registry hives"),
            ("RegistryHivesUser", "Registry", "User registry hives"),
            ("RegistryTransactionLogs", "Registry", "Registry transaction logs"),
            
            # Network
            ("NetworkHistory", "Network", "Network connection history"),
            ("NetworkDrives", "Network", "Mapped network drives"),
            ("WiFiProfiles", "Network", "WiFi connection profiles"),
            
            # External
            ("USBDevicesLogs", "External", "USB device connection logs"),
            ("ExternalDevices", "External", "External device artifacts"),
            
            # FileKnowledge
            ("FileDownloadHistory", "FileKnowledge", "File download history"),
            ("ThumbCache", "FileKnowledge", "Thumbnail cache"),
            ("WordWheelQuery", "FileKnowledge", "Word Wheel Query"),
            
            # Communication
            ("MessagingClients", "Communication", "Various messaging clients"),
            
            # LiveResponse
            ("SystemInfo", "LiveResponse", "System information"),
            ("ProcessList", "LiveResponse", "Running processes"),
            ("NetworkConnections", "LiveResponse", "Network connections"),
            ("Services", "LiveResponse", "Windows services"),
            ("Drivers", "LiveResponse", "Installed drivers"),
        ]
        
        for name, category, description in dummy_targets:
            row = self.tableWidget_targets.rowCount()
            self.tableWidget_targets.insertRow(row)
            
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_targets.setItem(row, 0, checkbox)
            
            self.tableWidget_targets.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.tableWidget_targets.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            self.tableWidget_targets.setItem(row, 3, QtWidgets.QTableWidgetItem(description))
    
    def load_modules(self):
        """Load KAPE modules - both from files and dummy data"""
        self.tableWidget_modules.setRowCount(0)
        # Look for KAPE modules directory
        kape_modules_path = os.path.join(self.tools_dir, "KAPE", "Modules")
        if os.path.isdir(kape_modules_path):
            try:
                module_files = glob.glob(os.path.join(kape_modules_path, "**", "*.mkape"), recursive=True)
                for module_file in module_files[:50]:  # Limit for performance
                    try:
                        with open(module_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Parse module file (simplified)
                        name = os.path.splitext(os.path.basename(module_file))[0]
                        category = os.path.basename(os.path.dirname(module_file))
                        description = self.extract_description_from_tkape(content)
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
                    except Exception as e:
                        # Nếu lỗi khi đọc file module, bỏ qua file đó
                        continue
            except Exception as e:
                print(f"Error loading modules: {e}")
        # Add comprehensive dummy modules if no modules loaded or to supplement
        current_count = self.tableWidget_modules.rowCount()
        if current_count < 10:  # Add dummies if we don't have enough real modules
            self.add_dummy_modules()
    
    def add_dummy_modules(self):
        """Add comprehensive dummy modules for demonstration"""
        dummy_modules = [
            # Core parsing modules
            ("!EZParser", "Compound", "Parse multiple artifact types with EZ Tools suite"),
            
            # Browser modules
            ("ChromiumParser", "Browsers", "Parse Chromium-based browser artifacts"),
            ("FirefoxParser", "Browsers", "Parse Firefox browser artifacts"),
            ("EdgeParser", "Browsers", "Parse Microsoft Edge artifacts"),
            ("SafariParser", "Browsers", "Parse Safari browser artifacts"),
            
            # Event Log modules
            ("EvtxECmd", "EventLogs", "Parse Windows Event Log files (.evtx)"),
            ("EventLogParser", "EventLogs", "Parse various Windows event logs"),
            ("PowerShellParser", "EventLogs", "Parse PowerShell event logs"),
            
            # Registry modules
            ("RegRipper", "Registry", "Extract information from Windows Registry"),
            ("RegistryParser", "Registry", "Parse registry hives and extract keys"),
            ("RegistryTransactionLogs", "Registry", "Parse registry transaction logs"),
            
            # Execution modules
            ("PECmd", "Execution", "Parse Windows Prefetch files"),
            ("LECmd", "Execution", "Parse Windows Link files (.lnk)"),
            ("JLECmd", "Execution", "Parse Jump List files"),
            ("AmcacheParser", "Execution", "Parse Amcache.hve file"),
            ("ShimCacheParser", "Execution", "Parse Application Compatibility Shimcache"),
            ("UserAssistParser", "Execution", "Parse UserAssist registry keys"),
            
            # File System modules
            ("MFTECmd", "FileSystem", "Parse Master File Table ($MFT)"),
            ("LogFileParser", "FileSystem", "Parse NTFS $LogFile"),
            ("USNJournalParser", "FileSystem", "Parse NTFS USN Journal"),
            ("RecycleBinParser", "FileSystem", "Parse Recycle Bin artifacts"),
            
            # Timeline modules
            ("WxTCmd", "Timeline", "Parse Windows 10 Timeline database"),
            ("TimelineParser", "Timeline", "Create timeline from various artifacts"),
            ("SuperTimeline", "Timeline", "Comprehensive timeline analysis"),
            
            # Communication modules
            ("SkypeParser", "Communication", "Parse Skype artifacts"),
            ("DiscordParser", "Communication", "Parse Discord artifacts"),
            ("TeamsParser", "Communication", "Parse Microsoft Teams artifacts"),
            ("OutlookParser", "Communication", "Parse Microsoft Outlook artifacts"),
            
            # Network modules
            ("NetworkParser", "Network", "Parse network configuration and history"),
            ("WiFiParser", "Network", "Parse WiFi connection profiles"),
            ("NetworkDrivesParser", "Network", "Parse mapped network drives"),
            
            # External Device modules
            ("USBParser", "ExternalDevices", "Parse USB device connection logs"),
            ("ExternalDeviceParser", "ExternalDevices", "Parse external device artifacts"),
            
            # System modules
            ("SystemInfoParser", "System", "Parse system information"),
            ("ServicesParser", "System", "Parse Windows services information"),
            ("DriversParser", "System", "Parse installed drivers information"),
            
            # File Knowledge modules
            ("ThumbCacheParser", "FileKnowledge", "Parse thumbnail cache"),
            ("WordWheelParser", "FileKnowledge", "Parse Word Wheel Query"),
            ("FileDownloadParser", "FileKnowledge", "Parse file download history"),
            
            # Memory modules
            ("VolatilityParser", "Memory", "Parse memory dumps with Volatility"),
            ("MemoryAnalyzer", "Memory", "Analyze memory artifacts"),
            
            # Malware modules
            ("MalwareParser", "Malware", "Parse malware-related artifacts"),
            ("VirusTotalLookup", "Malware", "Lookup file hashes in VirusTotal"),
            
            # Mobile modules
            ("AndroidParser", "Mobile", "Parse Android device artifacts"),
            ("iOSParser", "Mobile", "Parse iOS device artifacts"),
            
            # Database modules
            ("SQLiteParser", "Database", "Parse SQLite databases"),
            ("ESEParser", "Database", "Parse ESE databases"),
            
            # Cloud modules
            ("OneDriveParser", "Cloud", "Parse OneDrive artifacts"),
            ("DropboxParser", "Cloud", "Parse Dropbox artifacts"),
            ("GoogleDriveParser", "Cloud", "Parse Google Drive artifacts"),
        ]
        
        start_row = self.tableWidget_modules.rowCount()
        
        for name, category, description in dummy_modules:
            row = self.tableWidget_modules.rowCount()
            self.tableWidget_modules.insertRow(row)
            
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_modules.setItem(row, 0, checkbox)
            
            self.tableWidget_modules.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.tableWidget_modules.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            self.tableWidget_modules.setItem(row, 3, QtWidgets.QTableWidgetItem(description))

    def extract_description_from_tkape(self, content):
        """Extract description from .tkape file content"""
        for line in content.split('\n'):
            if line.strip().startswith('Description:'):
                return line.split(':', 1)[1].strip()
        return "No description"
    
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
                cmd.extend(["--tsource", source])
            
            # Destination for targets
            dest = self.lineEdit_target_destination.text() or "C:\\KapeOutput"
            cmd.extend(["--tdest", dest])
            
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
                    
                    # Module destination
                    mdest = self.lineEdit_module_destination.text() or "C:\\KapeOutput\\Modules"
                    cmd.extend(["--mdest", mdest])
            
            # Add zip option
            cmd.append("--zip")
            
            return cmd
        else:
            current_row = self.tableWidget_devices.currentRow()
            if current_row < 0:
                return ["echo", "No device selected"]
            device_id = self.tableWidget_devices.item(current_row, 1).text()
            # Định dạng ảnh
            if hasattr(self, 'radioButton_raw') and self.radioButton_raw.isChecked():
                img_format = "raw"
            elif hasattr(self, 'radioButton_e01') and self.radioButton_e01.isChecked():
                img_format = "encase6"
            elif hasattr(self, 'radioButton_aff') and self.radioButton_aff.isChecked():
                img_format = "aff"
            else:
                img_format = "encase6"  # Mặc định E01
            output_path = self.lineEdit_target_destination.text() or "C:\\ImageOutput"
            if not output_path.endswith((".dd", ".E01", ".raw", ".aff")):
                if img_format == "encase6":
                    output_path += ".E01"
                elif img_format == "aff":
                    output_path += ".aff"
                else:
                    output_path += ".dd"
            if img_format == "encase6" or img_format == "aff":
                ewf_path = os.path.join(self.tools_dir, "ewftools-x64", "ewfacquire.exe")
                cmd = [ewf_path]
                cmd.extend(["-t", output_path])
                cmd.extend(["-C", self.lineEdit_case_id.text() or "Unknown"])
                cmd.extend(["-D", self.lineEdit_case_description.text() or "Unknown"])
                cmd.extend(["-E", self.lineEdit_investigator.text() or "Unknown"])
                # Mức nén
                if hasattr(self, 'comboBox_compression') and self.comboBox_compression.currentIndex() >= 0:
                    compression_level = self.comboBox_compression.currentText()
                    cmd.extend(["-c", str(self.comboBox_compression.currentIndex())])
                # Mã hóa AD
                if hasattr(self, 'checkBox_ad_encryption') and self.checkBox_ad_encryption.isChecked():
                    cmd.append("-e")
                # Kích thước phân mảnh
                frag_size = self.spinBox_fragment_size.value()
                if frag_size > 0:
                    cmd.extend(["-S", f"{frag_size}MiB"])
                # Xác minh
                if hasattr(self, 'checkBox_verify_after_creation') and self.checkBox_verify_after_creation.isChecked():
                    cmd.append("-v")
                if hasattr(self, 'checkBox_precalculate_progress') and self.checkBox_precalculate_progress.isChecked():
                    cmd.append("-p")
                if hasattr(self, 'checkBox_create_directory_listing') and self.checkBox_create_directory_listing.isChecked():
                    cmd.append("-l")
                # Định dạng
                cmd.extend(["-f", img_format])
                cmd.extend(["-u"])
                # Hash
                if self.checkBox_md5.isChecked():
                    cmd.append("-d md5")
                if self.checkBox_sha1.isChecked():
                    cmd.append("-d sha1")
                if self.checkBox_sha256.isChecked():
                    cmd.append("-d sha256")
                cmd.append(device_id)
            else:
                # RAW dùng dd
                cmd = ["dd", f"if={device_id}", f"of={output_path}", "bs=1M", "status=progress"]
            return cmd

    def start_image_collection(self, device_id):
        """Start full disk imaging using ewfacquire or dd"""
        # Get image path
        image_path = self.lineEdit_target_destination.text()
        if not image_path:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn đường dẫn lưu image!")
            return
        # Validate path
        image_dir = os.path.dirname(image_path)
        if not os.path.exists(image_dir):
            try:
                os.makedirs(image_dir, exist_ok=True)
            except Exception:
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Không thể tạo thư mục đích!")
                return
        # Start imaging
        self.imaging_active = True
        self.imaging_paused = False
        
        # Update UI
        self.pushButton_start.setEnabled(False)
        self.pushButton_previous.setEnabled(False)
        self.pushButton_pause.setEnabled(True)
        self.pushButton_stop.setEnabled(True)
        
        # Reset progress
        self.progressBar.setValue(0)
        self.label_errors_val.setText("0")
        self.textBrowser_log.clear()
        self.start_time = time.time()
        
        # Build and log command
        cmd = self.build_command_line()
        self.textBrowser_log.append("<b>🚀 Bắt đầu thu thập Full Image...</b>")
        self.textBrowser_log.append(f"<b>Device:</b> {device_id}")
        self.textBrowser_log.append(f"<b>Output:</b> {image_path}")
        self.textBrowser_log.append(f"<b>Command:</b> {' '.join(cmd)}")
        self.textBrowser_log.append("=" * 50)
        
        # Start imaging process
        if "E01" in self.comboBox_image_format.currentText():
            self.start_ewf_imaging(device_id, image_path)
        else:
            self.start_dd_imaging(device_id, image_path)

    def start_ewf_imaging(self, device_id, image_path):
        """Start EWF imaging using ewfacquire"""
        try:
            ewf_path = os.path.join(self.tools_dir, "ewftools-x64", "ewfacquire.exe")
            
            if not os.path.exists(ewf_path):
                raise FileNotFoundError(f"ewfacquire.exe not found at {ewf_path}")
            
            # Định dạng ảnh
            if hasattr(self, 'radioButton_raw') and self.radioButton_raw.isChecked():
                img_format = "raw"
            elif hasattr(self, 'radioButton_e01') and self.radioButton_e01.isChecked():
                img_format = "encase6"
            elif hasattr(self, 'radioButton_aff') and self.radioButton_aff.isChecked():
                img_format = "aff"
            else:
                img_format = "encase6"
            cmd = [ewf_path]
            cmd.extend(["-t", image_path])
            cmd.extend(["-C", self.lineEdit_case_id.text() or "Unknown"])
            cmd.extend(["-D", self.lineEdit_case_description.text() or "Unknown"])
            cmd.extend(["-E", self.lineEdit_investigator.text() or "Unknown"])
            # Mức nén
            if hasattr(self, 'comboBox_compression') and self.comboBox_compression.currentIndex() >= 0:
                compression_level = self.comboBox_compression.currentText()
                cmd.extend(["-c", str(self.comboBox_compression.currentIndex())])
            # Mã hóa AD
            if hasattr(self, 'checkBox_ad_encryption') and self.checkBox_ad_encryption.isChecked():
                cmd.append("-e")
            # Kích thước phân mảnh
            frag_size = self.spinBox_fragment_size.value()
            if frag_size > 0:
                cmd.extend(["-S", f"{frag_size}MiB"])
            # Xác minh
            if hasattr(self, 'checkBox_verify_after_creation') and self.checkBox_verify_after_creation.isChecked():
                cmd.append("-v")
            if hasattr(self, 'checkBox_precalculate_progress') and self.checkBox_precalculate_progress.isChecked():
                cmd.append("-p")
            if hasattr(self, 'checkBox_create_directory_listing') and self.checkBox_create_directory_listing.isChecked():
                cmd.append("-l")
            # Định dạng
            cmd.extend(["-f", img_format])
            cmd.extend(["-u"])
            # Hash
            if self.checkBox_md5.isChecked():
                cmd.append("-d md5")
            if self.checkBox_sha1.isChecked():
                cmd.append("-d sha1")
            if self.checkBox_sha256.isChecked():
                cmd.append("-d sha256")
            cmd.append(device_id)
            # Start process
            self.imaging_process = QtCore.QProcess(self)
            self.imaging_process.readyReadStandardOutput.connect(self.handle_imaging_stdout)
            self.imaging_process.readyReadStandardError.connect(self.handle_imaging_stderr)
            self.imaging_process.finished.connect(self.imaging_process_finished)
            
            self.textBrowser_log.append("<b>Starting EWF imaging...</b>")
            self.imaging_process.start(cmd[0], cmd[1:])
            
        except Exception as e:
            self.imaging_failed(str(e))

    def start_dd_imaging(self, device_id, image_path):
        """Start DD imaging using custom implementation"""
        try:
            if not WIN32_AVAILABLE:
                raise ImportError("pywin32 required for DD imaging")
            
            # Start DD imaging in thread
            threading.Thread(
                target=self.create_dd_image,
                args=(device_id, image_path),
                daemon=True
            ).start()
            
        except Exception as e:
            self.imaging_failed(str(e))

    def create_dd_image(self, device_path, image_path):
        """Create DD image using low-level disk access"""
        hasher_md5 = hashlib.md5() if self.checkBox_md5.isChecked() else None
        hasher_sha1 = hashlib.sha1() if self.checkBox_sha1.isChecked() else None
        hasher_sha256 = hashlib.sha256() if self.checkBox_sha256.isChecked() else None
        
        try:
            # Open device
            handle = win32file.CreateFile(
                device_path,
                win32file.GENERIC_READ,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            
            # Get device size
            try:
                import win32ioctl
                size_bytes = win32file.DeviceIoControl(
                    handle,
                    win32ioctl.IOCTL_DISK_GET_LENGTH_INFO,
                    None,
                    8
                )
                total_size = int.from_bytes(size_bytes, 'little')
            except:
                total_size = 0
                
            # Open output file
            with open(image_path, 'wb') as image_file:
                read_size = 0
                start_time = time.time()
                
                while self.imaging_active and read_size < total_size:
                    if self.imaging_paused:
                        time.sleep(0.1)
                        continue
                    
                    # Calculate remaining bytes to read
                    remaining = total_size - read_size
                    block_size = min(self.block_size, remaining)
                    
                    # Read block
                    hr, data = win32file.ReadFile(handle, block_size)
                    if not data:
                        break
                    
                    # Write to image file
                    image_file.write(data)
                    
                    # Update hashes
                    if hasher_md5:
                        hasher_md5.update(data)
                    if hasher_sha1:
                        hasher_sha1.update(data)
                    if hasher_sha256:
                        hasher_sha256.update(data)
                    
                    # Update progress
                    read_size += len(data)
                    
                    # Calculate and update UI
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        speed = read_size / (1024 * 1024 * elapsed_time)  # MB/s
                        self.update_ui_progress(read_size, total_size, speed, elapsed_time)
                    
                    # Force UI update every 1MB
                    if read_size % (1024 * 1024) == 0:
                        QtCore.QCoreApplication.processEvents()
            
            handle.close()
            
            # Generate hash summary
            if self.imaging_active:
                hash_summary = []
                if hasher_md5:
                    hash_summary.append(f"MD5: {hasher_md5.hexdigest()}")
                if hasher_sha1:
                    hash_summary.append(f"SHA1: {hasher_sha1.hexdigest()}")
                if hasher_sha256:
                    hash_summary.append(f"SHA256: {hasher_sha256.hexdigest()}")
                
                self.imaging_completed(read_size, total_size, "\n".join(hash_summary))
                
        except Exception as e:
            self.imaging_failed(str(e))

    def handle_imaging_stdout(self):
        """Handle output from imaging process"""
        if hasattr(self, 'imaging_process'):
            output = self.imaging_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            self.textBrowser_log.append(output)
            
            # Try to parse progress
            progress_match = re.search(r'(\d+)%', output)
            if progress_match:
                progress = int(progress_match.group(1))
                self.progressBar.setValue(progress)

    def handle_imaging_stderr(self):
        """Handle errors from imaging process"""
        if hasattr(self, 'imaging_process'):
            error = self.imaging_process.readAllStandardError().data().decode('utf-8', errors='ignore')
            self.textBrowser_log.append(f"<span style='color: red;'>{error}</span>")
            
            current_errors = int(self.label_errors_val.text())
            self.label_errors_val.setText(str(current_errors + 1))

    def imaging_process_finished(self, exit_code, exit_status):
        """Handle imaging process completion"""
        if exit_code == 0:
            self.textBrowser_log.append("<b>✅ EWF imaging completed successfully!</b>")
            self.progressBar.setValue(100)
        else:
            self.textBrowser_log.append(f"<b>❌ EWF imaging failed with exit code: {exit_code}</b>")
        
        self.imaging_active = False
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)

    def update_ui_progress(self, read_size, total_size, speed, elapsed_time):
        """Cập nhật giao diện tiến trình imaging"""
        if total_size > 0:
            percent = (read_size / total_size) * 100
            self.progressBar.setValue(int(percent))
            
            # Cập nhật labels
            bytes_read_gb = read_size / (1024**3)
            total_bytes_gb = total_size / (1024**3)
            self.label_source_progress_val.setText(f"{bytes_read_gb:.1f} GB / {total_bytes_gb:.1f} GB")
            self.label_speed_val.setText(f"{speed:.1f} MB/s")
            
            # Thời gian
            elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
            self.label_time_elapsed_val.setText(elapsed_str)
            
            # ETA
            if speed > 0:
                remaining_bytes = total_size - read_size
                eta_seconds = remaining_bytes / (speed * 1024 * 1024)
                eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))
                self.label_eta_val.setText(eta_str)

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
        
        # Show ready message
        self.textBrowser_log.append("<b>✅ Sẵn sàng thu thập dữ liệu. Nhấn 'Bắt đầu Thu thập' để tiếp tục.</b>")

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
            
        # Kiểm tra phương thức thu thập
        if self.radioButton_triage.isChecked():
            self.start_triage_collection()
        else:
            self.start_image_collection(device_id)

    def start_triage_collection(self):
        """Bắt đầu thu thập triage bằng KAPE"""
        try:
            cmd = self.build_command_line()
            
            # Reset progress
            self.progressBar.setValue(0)
            self.label_errors_val.setText("0")
            self.textBrowser_log.clear()
            
            # Start KAPE process
            self.kape_process = QtCore.QProcess(self)
            self.kape_process.readyReadStandardOutput.connect(self.handle_stdout)
            self.kape_process.readyReadStandardError.connect(self.handle_stderr)
            self.kape_process.finished.connect(self.collection_finished)
            
            # Log command
            self.textBrowser_log.append("<b>🚀 Bắt đầu thu thập KAPE...</b>")
            self.textBrowser_log.append(f"<b>Command:</b> {' '.join(cmd)}")
            
            # Start process
            self.kape_process.start(cmd[0], cmd[1:])
            
            # Update UI
            self.pushButton_start.setEnabled(False)
            self.pushButton_previous.setEnabled(False)
            self.start_time = time.time()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu KAPE: {str(e)}")
            self.collection_finished(1, QtCore.QProcess.CrashExit)

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
            self.imaging_active = False
            self.imaging_paused = False
            self.textBrowser_log.append("<b>⏹️ Thu thập đã bị dừng bởi người dùng</b>")
            self.pushButton_start.setEnabled(True)
            self.pushButton_previous.setEnabled(True)
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
            total_time_str = time.strftime("%H:%M:%S", time.gmtime(total_time))
            self.label_time_elapsed_val.setText(total_time_str)
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
            
            # Update image source field
            device_id = self.tableWidget_devices.item(current_row, 1).text()
            model = self.tableWidget_devices.item(current_row, 0).text()
            self.lineEdit_image_source.setText(f"{model} ({device_id})")
            
            # Update case ID if not set
            if not self.lineEdit_case_id.text():
                self.lineEdit_case_id.setText(f"Case-{timestamp}")
                
            # Update image filename if not set
            if not self.lineEdit_image_filename.text():
                safe_model = re.sub(r'[^\w\-]', '_', model)
                self.lineEdit_image_filename.setText(f"{safe_model}_{timestamp}")
                
    def browse_image_destination(self):
        """Open folder browser for image destination"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục lưu ảnh",
            self.lineEdit_destination_folder.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_destination_folder.setText(folder)
            
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
                
            full_path = os.path.join(folder, filename + ext)
            self.lineEdit_target_destination.setText(full_path)

# Create an alias for backward compatibility
CollectNonvolatileController = NonVolatilePage
