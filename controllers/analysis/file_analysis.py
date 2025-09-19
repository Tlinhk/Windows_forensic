import sys
import os
import hashlib
import mimetypes
import struct
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import *  # Các widget Qt (QTreeWidget, QTableWidget, QMessageBox, ...)
from PyQt5.QtCore import *  # Core Qt (Qt, QTimer, QModel...)
from PyQt5.QtGui import *  # Đồ họa (QColor, QPixmap, ...)
from PyQt5.QtCore import QTimer  # Import rõ ràng cho QTimer
import pytsk3  # Thư viện forensics: Python binding của The Sleuth Kit (đọc ảnh đĩa/hệ thống tệp)

# Import UI class
from views.pages.analysis_ui.file_analysis_ui import Ui_EvidenceAnalysisWidget

class FileAnalysis(QWidget):
    """Widget phân tích tệp trong vụ án.

    - Kết nối với `Ui_EvidenceAnalysisWidget` để hiển thị giao diện.
    - Quản lý trạng thái vụ án, đường dẫn chứng cứ và cấu trúc hệ thống tệp (pytsk3).
    - Cung cấp duyệt cây, xem chi tiết, tìm kiếm/lọc, timeline và phục hồi tệp đã xóa.
    """
    def __init__(self, main_window=None):
        super().__init__()
        
        self.main_window = main_window  # Cửa sổ chính (để lấy case_id, cập nhật tiêu đề, ...)
        self.current_case_id = None  # ID vụ án hiện tại (nếu có)
        self.current_evidence_path = None  # Đường dẫn ảnh đĩa (chứng cứ) đang làm việc
        
        # Data containers
        self.file_list = []  # Danh sách tệp hiển thị (mỗi phần tử là dict thông tin tệp)
        self.timeline_data = []  # Dữ liệu timeline sinh từ self.file_list
        self.search_results = []  # Kết quả tìm kiếm hiện tại
        self.img_info = None  # pytsk3.Img_Info: đối tượng ảnh đĩa đang mở
        self.volume_info = None  # pytsk3.Volume_Info: thông tin phân vùng (nếu có)
        self.fs_info = None  # pytsk3.FS_Info: hệ thống tệp đang được duyệt
        
        # Database manager for saving analysis results
        self.db_manager = None
        
        # Setup UI
        self.setup_ui()
        self.setup_connections()
        self.initialize_empty_state()
        
        # Load case data if available
        if main_window and hasattr(main_window, 'current_case_id'):
            self.load_case_data(main_window.current_case_id)
    
    def setup_ui(self):
        """Cài đặt giao diện từ file UI đã chuyển đổi (Qt Designer -> PyQt5)."""
        self.ui = Ui_EvidenceAnalysisWidget()
        self.ui.setupUi(self)
        
        # Setup table headers and properties
        self.setup_table_properties()
        
    
    def setup_table_properties(self):
        """Thiết lập thuộc tính các bảng để hiển thị đẹp, dễ đọc và có sắp xếp."""
        
        # File table
        if hasattr(self.ui, 'tableFiles'):
            self.ui.tableFiles.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self.ui.tableFiles.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self.ui.tableFiles.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
            self.ui.tableFiles.setSortingEnabled(True)
            self.ui.tableFiles.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Timeline table
        if hasattr(self.ui, 'tableTimeline'):
            self.ui.tableTimeline.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
            self.ui.tableTimeline.setSortingEnabled(True)
            self.ui.tableTimeline.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Search results table
        if hasattr(self.ui, 'tableSearchResults'):
            self.ui.tableSearchResults.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.ui.tableSearchResults.setSortingEnabled(True)
            self.ui.tableSearchResults.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Metadata and properties tables
        if hasattr(self.ui, 'tableMetadata'):
            self.ui.tableMetadata.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.ui.tableMetadata.setEditTriggers(QAbstractItemView.NoEditTriggers)

        if hasattr(self.ui, 'tableProperties'):
            self.ui.tableProperties.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.ui.tableProperties.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Tree
        if hasattr(self.ui, 'treeInvestigation'):
            self.ui.treeInvestigation.setEditTriggers(QAbstractItemView.NoEditTriggers)
    
    def setup_connections(self):
        """Kết nối các tín hiệu (signal) của UI với các slot xử lý tương ứng."""
        try:
            # Evidence selection controls - truy cập trực tiếp UI
            if hasattr(self.ui, 'cmbEvidenceArtifacts'):
                self.ui.cmbEvidenceArtifacts.currentIndexChanged.connect(self.on_evidence_artifact_changed)
                
            if hasattr(self.ui, 'btnLoadSelectedEvidence'):
                self.ui.btnLoadSelectedEvidence.clicked.connect(self.load_selected_evidence_artifact)
                
            if hasattr(self.ui, 'btnRefreshEvidence'):
                self.ui.btnRefreshEvidence.clicked.connect(self.refresh_evidence_artifacts)
            
            # Tree widget
            if hasattr(self.ui, 'treeInvestigation'):
                self.ui.treeInvestigation.itemClicked.connect(self.on_tree_item_clicked)
                self.ui.treeInvestigation.itemExpanded.connect(self.on_tree_item_expanded)

            # File table
            if hasattr(self.ui, 'tableFiles'):
                self.ui.tableFiles.itemSelectionChanged.connect(self.on_file_selected)
                self.ui.tableFiles.customContextMenuRequested.connect(self.on_files_table_context_menu)

            # Search controls
            if hasattr(self.ui, 'btnSearch'):
                self.ui.btnSearch.clicked.connect(self.perform_search)

            if hasattr(self.ui, 'lineEditSearch'):
                self.ui.lineEditSearch.returnPressed.connect(self.perform_search)

            # Search results table context menu
            if hasattr(self.ui, 'tableSearchResults'):
                self.ui.tableSearchResults.customContextMenuRequested.connect(self.on_search_table_context_menu)

            # Timeline table
            if hasattr(self.ui, 'tableTimeline'):
                self.ui.tableTimeline.itemSelectionChanged.connect(self.on_timeline_selected)
                
        except Exception as e:
            pass  # Bỏ qua lỗi kết nối tín hiệu để tránh làm chết UI khi thiếu thành phần
    
    def initialize_empty_state(self):
        """Khởi tạo trạng thái rỗng: dọn cây dữ liệu, bảng và các vùng hiển thị nội dung."""
        
        # Clear the pre-populated tree completely
        if hasattr(self.ui, 'treeInvestigation'):
            self.ui.treeInvestigation.clear()
            self.ui.treeInvestigation.setHeaderLabel("Data Sources")

        # Clear all tables
        if hasattr(self.ui, 'tableFiles'):
            self.ui.tableFiles.setRowCount(0)

        if hasattr(self.ui, 'tableTimeline'):
            self.ui.tableTimeline.setRowCount(0)

        if hasattr(self.ui, 'tableSearchResults'):
            self.ui.tableSearchResults.setRowCount(0)

        if hasattr(self.ui, 'tableMetadata'):
            self.ui.tableMetadata.setRowCount(0)

        if hasattr(self.ui, 'tableProperties'):
            self.ui.tableProperties.setRowCount(0)

        # Clear text views
        if hasattr(self.ui, 'textHexView'):
            self.ui.textHexView.clear()

        if hasattr(self.ui, 'textContentView'):
            self.ui.textContentView.clear()

        if hasattr(self.ui, 'textAnalysisResults'):
            self.ui.textAnalysisResults.clear()

        if hasattr(self.ui, 'labelPicture'):
            self.ui.labelPicture.clear()

        # Update case info to show no evidence loaded
        if hasattr(self.ui, 'labelCaseInfo'):
            self.ui.labelCaseInfo.setText("File Analysis - No evidence loaded")
            
        # Khởi tạo trạng thái ban đầu
        if hasattr(self.ui, 'btnLoadSelectedEvidence'):
            self.ui.btnLoadSelectedEvidence.setEnabled(False)
    
    def load_case_data(self, case_id):
        """Nạp thông tin vụ án từ cơ sở dữ liệu để hiển thị lên thanh tiêu đề."""
        self.current_case_id = case_id
        
        try:
            from models.db_manager import DatabaseManager
            self.db_manager = DatabaseManager()  # Lưu reference để dùng sau
            self.db_manager.connect()  # Mở kết nối
            
            case_info = self.db_manager.get_case_with_investigator(case_id)  # Lấy thông tin vụ án + điều tra viên
            if case_info:
                text = f"File Analysis - Case: {case_info['title']} (ID: {case_id})"
                if hasattr(self.ui, 'labelCaseInfo'):
                    self.ui.labelCaseInfo.setText(text)
            
            # Load evidence artifacts từ case
            self.load_evidence_artifacts_from_case(self.db_manager)
            
            self.db_manager.disconnect()
                    
        except Exception as e:
            pass
            if self.db_manager:
                self.db_manager.disconnect()
                
    def load_evidence_artifacts_from_case(self, db):
        """Load danh sách evidence artifacts từ case hiện tại."""
        try:
            # Truy cập trực tiếp UI component
            if not hasattr(self.ui, 'cmbEvidenceArtifacts'):
                return
                
            self.ui.cmbEvidenceArtifacts.clear()
            self.ui.cmbEvidenceArtifacts.addItem("-- Chọn Evidence Artifact --", None)
            
            # Lấy tất cả artifacts của case
            artifacts = db.get_artifacts_by_case(self.current_case_id)
            
            # Lọc ra các disk image artifacts
            
            # Lọc ra các disk image artifacts
            evidence_artifacts = []
            for artifact in artifacts:
                evidence_type = artifact.get('evidence_type', '').upper()
                name = artifact.get('name', '').upper()
                source_path = artifact.get('source_path', '').upper()
                
                # Kiểm tra xem có phải disk image không
                is_disk_image = False
                
                # Kiểm tra theo evidence_type
                if any(disk_type in evidence_type for disk_type in ['DISK_IMAGE', 'DD', 'IMG', 'RAW', 'E01']):
                    is_disk_image = True
                
                # Kiểm tra theo tên file
                if any(ext in name for ext in ['.DD', '.IMG', '.RAW', '.E01', '.001']):
                    is_disk_image = True
                    
                # Kiểm tra theo source_path
                if any(ext in source_path for ext in ['.DD', '.IMG', '.RAW', '.E01', '.001']):
                    is_disk_image = True
                
                if is_disk_image:
                    evidence_artifacts.append(artifact)
            
            # Thêm vào combo box
            for artifact in evidence_artifacts:
                display_name = f"{artifact.get('name', 'Unknown')} ({artifact.get('evidence_type', 'Unknown')})"
                self.ui.cmbEvidenceArtifacts.addItem(display_name, artifact)
                
            if not evidence_artifacts:
                self.ui.cmbEvidenceArtifacts.addItem("Không có disk image artifacts", None)
                
        except Exception as e:
            pass  # Silent error handling
    
    def on_evidence_artifact_changed(self, index):
        """Xử lý khi người dùng chọn evidence artifact khác."""
        if hasattr(self.ui, 'cmbEvidenceArtifacts') and hasattr(self.ui, 'btnLoadSelectedEvidence'):
            artifact_data = self.ui.cmbEvidenceArtifacts.itemData(index)
            should_enable = artifact_data is not None and index > 0
            self.ui.btnLoadSelectedEvidence.setEnabled(should_enable)
    
    def load_selected_evidence_artifact(self):
        """Load evidence artifact được chọn."""
        if not hasattr(self.ui, 'cmbEvidenceArtifacts'):
            return
            
        artifact_data = self.ui.cmbEvidenceArtifacts.currentData()
        if not artifact_data:
            QMessageBox.warning(self, "Chưa chọn Evidence", "Vui lòng chọn một evidence artifact để phân tích.")
            return
            
        source_path = artifact_data.get('source_path')
        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(self, "File không tồn tại", f"File evidence không tồn tại: {source_path}")
            return
            
        self.load_evidence_file(source_path)
    
    def refresh_evidence_artifacts(self):
        """Refresh danh sách evidence artifacts từ case."""
        if not self.current_case_id:
            QMessageBox.warning(self, "Chưa chọn Case", "Vui lòng chọn case trước.")
            return
            
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.connect()
            self.load_evidence_artifacts_from_case(db)
            db.disconnect()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi refresh danh sách evidence: {str(e)}")
    
    def showEvent(self, event):
        """Override showEvent để refresh evidence artifacts khi widget được hiển thị."""
        super().showEvent(event)
        
        # Kiểm tra và cập nhật case_id từ main_window (giống Registry Analysis)
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            main_case_id = self.main_window.current_case_id
            # Nếu case đã thay đổi, load case mới
            if main_case_id != self.current_case_id:
                if main_case_id:
                    QTimer.singleShot(100, lambda: self.load_case_data(main_case_id))
                else:
                    # Nếu không có case, reset về trạng thái rỗng
                    self.current_case_id = None
                    self.initialize_empty_state()
        
        # Refresh evidence artifacts nếu có case
        if self.current_case_id and hasattr(self.ui, 'cmbEvidenceArtifacts'):
            QTimer.singleShot(200, self.refresh_evidence_artifacts)
    
    
    def load_evidence_file(self, file_path):
        """Nạp và phân tích tệp chứng cứ.

        - Mở ảnh đĩa bằng `pytsk3.Img_Info` và phát hiện phân vùng (`Volume_Info`).
        - Dựng cây dữ liệu (các phân vùng/hệ thống tệp) để duyệt.
        - Nạp danh sách tệp ban đầu ở thư mục gốc.
        """
        
        try:
            # Show progress
            # Hộp thoại tiến trình để tránh treo UI khi thao tác nặng
            progress = QProgressDialog("Loading evidence file...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)  # Khóa tương tác cửa sổ cho tới khi xong
            progress.show()
            
            # Lưu đường dẫn chứng cứ và tên tệp hiển thị
            self.current_evidence_path = file_path
            file_name = os.path.basename(file_path)
            
            # Clear previous data
            # Xóa sạch dữ liệu hiện có trên UI trước khi nạp ảnh mới
            self.initialize_empty_state()
            
            # Update UI to show loading
            if hasattr(self.ui, 'labelCaseInfo'):
                current_text = self.ui.labelCaseInfo.text()
                if "Case:" in current_text:
                    self.ui.labelCaseInfo.setText(f"{current_text} | Evidence: {file_name}")
                else:
                    self.ui.labelCaseInfo.setText(f"File Analysis | Evidence: {file_name}")
            
            progress.setValue(20)
            QApplication.processEvents()
            
            # Step 1: Open image with pytsk3
            self.img_info = pytsk3.Img_Info(file_path)  # Mở ảnh đĩa chế độ chỉ-đọc
            image_size = self.img_info.get_size()  # Lấy kích thước ảnh (để hiển thị)
            
            progress.setValue(40)
            QApplication.processEvents()
            
            # Step 2: Get volume/partition info
            partitions = []  # Danh sách phân vùng (nếu có)
            try:
                self.volume_info = pytsk3.Volume_Info(self.img_info)  # Đọc bảng phân vùng
                partitions = list(self.volume_info)
            except:
                partitions = [None]  # Không có bảng phân vùng -> 1 hệ thống tệp duy nhất
            
            progress.setValue(60)
            QApplication.processEvents()
            
            # Step 3: Build evidence tree
            self.build_evidence_tree(file_name, partitions)  # Dựng cây dữ liệu cho UI
            
            progress.setValue(80)
            QApplication.processEvents()
            
            # Step 4: Load initial file list
            if partitions and partitions[0] is not None:
                self.load_partition_root(partitions[0])  # Nạp danh sách từ thư mục gốc của phân vùng đầu tiên
            else:
                self.load_single_filesystem_root()  # Ảnh có 1 hệ thống tệp
            
            progress.setValue(100)
            progress.close()

            # Log activity for evidence loading (without saving to database)
            if self.current_case_id:
                self.log_evidence_analysis_activity(file_path, image_size, len(self.file_list), len([f for f in self.file_list if f.get('deleted', False)]))

            # Ask user if they want to save this evidence to the case
            saved_to_db = False
            if self.current_case_id:
                saved_to_db = self.ask_user_to_save_evidence(file_path, image_size, len(self.file_list), deleted_count)

            # Show success message
            deleted_count = len([f for f in self.file_list if f.get('deleted', False)])  # Đếm số tệp đã xóa
            success_msg = (
                f"✅ Successfully loaded evidence file!\n\n"
                f"📁 File: {file_name}\n"
                f"💾 Size: {self.format_file_size(image_size)}\n"
                f"🗂️ Partitions: {len(partitions) if partitions[0] else 1}\n"
                f"📋 Files Found: {len(self.file_list):,}\n"
                f"🗑️ Deleted Files: {deleted_count:,}\n\n"
                f"Use the tree view to navigate and explore the evidence."
            )

            if saved_to_db:
                success_msg += f"\n\n💾 Evidence saved to database as artifact"
            elif self.current_case_id:
                success_msg += f"\n\n💡 Evidence loaded for analysis only (not saved to case)"
            else:
                success_msg += f"\n\n💡 Select a case to save evidence to database"

            QMessageBox.information(self, "Evidence Loaded Successfully", success_msg)
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()  # Đảm bảo đóng tiến trình nếu xảy ra lỗi
            
            error_msg = f"Failed to load evidence file:\n\n{str(e)}"
            QMessageBox.critical(self, "Error Loading Evidence", error_msg)
    
    def save_evidence_to_database(self, file_path, file_size):
        """Save evidence file information to database as artifact"""
        try:
            if not self.db_manager:
                from models.db_manager import DatabaseManager
                self.db_manager = DatabaseManager()
            
            if not self.db_manager.connect():
                pass
                return None
            
            # Calculate file hash for integrity
            file_hash = self.calculate_file_hash(file_path)
            file_name = os.path.basename(file_path)
            
            # Determine evidence type based on file extension
            ext = os.path.splitext(file_name)[1].lower()
            evidence_types = {
                '.dd': 'DISK_IMAGE_DD',
                '.img': 'DISK_IMAGE_IMG', 
                '.raw': 'DISK_IMAGE_RAW',
                '.e01': 'DISK_IMAGE_E01',
                '.001': 'DISK_IMAGE_001'
            }
            evidence_type = evidence_types.get(ext, 'DISK_IMAGE')
            
            # Add artifact to database
            artifact_id = self.db_manager.add_artifact(
                case_id=self.current_case_id,
                name=f"Disk Image - {file_name}",
                source_path=file_path,
                evidence_type=evidence_type,
                size=file_size,
                mime_type="application/octet-stream"
            )
            
            if artifact_id and file_hash:
                # Add hash for integrity verification
                self.db_manager.add_hash(artifact_id, "SHA256", file_hash)
                
                # Log the activity
                self.db_manager.log_activity(
                    case_id=self.current_case_id,
                    artefact_id=artifact_id,
                    action=f"EVIDENCE_LOADED: {file_name}",
                    tool_used="File Analysis",
                    details=f"Loaded disk image: {file_name}, Size: {file_size:,} bytes, SHA256: {file_hash}"
                )
                
                pass
            
            self.db_manager.disconnect()
            return artifact_id
            
        except Exception as e:
            pass
            if self.db_manager:
                self.db_manager.disconnect()
            return None
    
    def calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            pass
            return None
    
    def save_search_results_to_database(self, keyword, search_results):
        """Save search analysis results to database (simplified)"""
        try:
            if not self.current_case_id or not self.db_manager:
                return None
        except Exception as e:
            pass
        return None
    
    def save_deleted_files_analysis(self, deleted_files_count):
        """Save deleted files analysis results (simplified)"""
        return None
    
    def log_file_recovery(self, file_info, save_path, recovered_size):
        """Log file recovery activity (simplified)"""
        pass

    def log_evidence_analysis_activity(self, file_path, image_size, file_count, deleted_count):
        """Log evidence analysis activity to database without creating artifact"""
        try:
            if not self.current_case_id or not self.db_manager:
                from models.db_manager import DatabaseManager
                self.db_manager = DatabaseManager()
                
            if not self.db_manager.connect():
                return
                
            file_name = os.path.basename(file_path)
            activity_details = (
                f"Loaded evidence file for analysis: {file_name}\n"
                f"Size: {self.format_file_size(image_size)}\n"
                f"Files found: {file_count:,}\n"
                f"Deleted files: {deleted_count:,}\n"
                f"Path: {file_path}"
            )
            
            self.db_manager.log_activity(
                case_id=self.current_case_id,
                action=f"EVIDENCE_ANALYZED: {file_name}",
                tool_used="File Analysis",
                details=activity_details
            )
            
            self.db_manager.disconnect()
            
        except Exception as e:
            print(f"Error logging analysis activity: {e}")
            if self.db_manager:
                self.db_manager.disconnect()

    def ask_user_to_save_evidence(self, file_path, image_size, file_count, deleted_count):
        """Ask user if they want to save evidence to case database"""
        try:
            file_name = os.path.basename(file_path)
            
            reply = QMessageBox.question(
                self,
                "💾 Save Evidence to Case?",
                f"📁 File: {file_name}\n"
                f"💾 Size: {self.format_file_size(image_size)}\n"
                f"📋 Files: {file_count:,} (🗑️ {deleted_count:,} deleted)\n\n"
                f"Do you want to save this evidence file as an artifact in the current case?\n\n"
                f"✅ Yes: Save to database for future reference\n"
                f"❌ No: Load for analysis only (temporary)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # Default to No
            )
            
            if reply == QMessageBox.Yes:
                artifact_id = self.save_evidence_to_database(file_path, image_size)
                return artifact_id is not None
            else:
                return False
                
        except Exception as e:
            print(f"Error asking user to save evidence: {e}")
            return False
    
    def build_evidence_tree(self, evidence_name, partitions):
        """Xây dựng cây dữ liệu chứng cứ (giống Autopsy) gồm ảnh đĩa, phân vùng và hệ thống tệp."""
        
        if not hasattr(self.ui, 'treeInvestigation'):
            return
        
        # Clear tree completely
        self.ui.treeInvestigation.clear()
        self.ui.treeInvestigation.setHeaderLabel("Data Sources")
        
        # Node gốc - tên tệp chứng cứ
        root_item = QTreeWidgetItem(self.ui.treeInvestigation, [evidence_name])
        root_item.setData(0, Qt.UserRole, {'type': 'evidence', 'path': self.current_evidence_path})
        root_item.setExpanded(True)
        
        # Build partition structure
        if partitions and partitions[0] is not None:
            # Multiple partitions
            for i, partition in enumerate(partitions):
                try:
                    # Get partition info
                    part_desc = f"Partition {i+1}"  # Nhãn cơ bản cho phân vùng
                    if hasattr(partition, 'desc') and partition.desc:
                        desc_str = partition.desc.decode('utf-8', errors='ignore').strip()  # Mô tả phân vùng (nếu có)
                        if desc_str:
                            part_desc += f" ({desc_str})"
                    
                    part_size = partition.len * 512 if hasattr(partition, 'len') else 0  # Quy đổi sector (512B) -> bytes
                    part_desc += f" - {self.format_file_size(part_size)}"
                    
                    part_item = QTreeWidgetItem(root_item, [part_desc])
                    part_item.setData(0, Qt.UserRole, {
                        'type': 'partition', 
                        'partition': partition,
                        'index': i
                    })
                    
                    # Try to get filesystem info
                    try:
                        offset = partition.start * 512 if hasattr(partition, 'start') else 0  # Tính offset byte bắt đầu phân vùng
                        fs_info = pytsk3.FS_Info(self.img_info, offset=offset)  # Mở hệ thống tệp tại offset
                        
                        fs_type = fs_info.info.ftype_str if hasattr(fs_info.info, 'ftype_str') else "Unknown"
                        fs_item = QTreeWidgetItem(part_item, [f"File System ({fs_type})"])  # Node hệ thống tệp
                        fs_item.setData(0, Qt.UserRole, {
                            'type': 'filesystem',
                            'fs_info': fs_info,
                            'partition': partition
                        })
                        
                        # Thêm các thư mục điều hướng cho FS này
                        self.add_navigation_folders(fs_item, fs_info)
                        
                    except Exception as fs_error:
                        pass  # Không mở được FS tại phân vùng này (có thể phân vùng trống/không hỗ trợ)
                        
                except Exception as part_error:
                    pass  # Bỏ qua phân vùng lỗi để tiếp tục dựng cây các phân vùng còn lại
        else:
            # Single filesystem
            try:
                fs_info = pytsk3.FS_Info(self.img_info)
                fs_type = fs_info.info.ftype_str if hasattr(fs_info.info, 'ftype_str') else "Unknown"
                
                fs_item = QTreeWidgetItem(root_item, [f"File System ({fs_type})"])  # Node hệ thống tệp đơn
                fs_item.setData(0, Qt.UserRole, {
                    'type': 'filesystem',
                    'fs_info': fs_info,
                    'partition': None
                })
                
                # Thêm thư mục điều hướng cho FS đơn
                self.add_navigation_folders(fs_item, fs_info)
                
            except Exception as fs_error:
                pass  # Không mở được hệ thống tệp đơn từ ảnh -> bỏ qua
        
        # Add Views section (like Autopsy)
        views_item = QTreeWidgetItem(self.ui.tree, ["Views"])
        views_item.setExpanded(True)
        
        # Count files by type (including deleted) for display
        file_type_counts = self.count_files_by_type(partitions)
        
        # File Types view
        file_types_item = QTreeWidgetItem(views_item, ["File Types"])
        file_types_item.setExpanded(True)
        
        # Main file type categories with subcategories
        file_categories = [
            ("By Extension", None, [
                ("Images", file_type_counts.get('images', 0), 'images'),
                ("Videos", file_type_counts.get('videos', 0), 'videos'),
                ("Audio", file_type_counts.get('audio', 0), 'audio'),
                ("Archives", file_type_counts.get('archives', 0), 'archives'),
                ("Databases", file_type_counts.get('databases', 0), 'databases')
            ]),
            ("Documents", None, [
                ("HTML", file_type_counts.get('html', 0), 'html'),
                ("Office", file_type_counts.get('office', 0), 'office'),
                ("PDF", file_type_counts.get('pdf', 0), 'pdf'),
                ("Plain Text", file_type_counts.get('plaintext', 0), 'plaintext'),
                ("Rich Text", file_type_counts.get('richtext', 0), 'richtext')
            ]),
            ("Executable", None, [
                (".exe", file_type_counts.get('exe', 0), 'exe'),
                (".dll", file_type_counts.get('dll', 0), 'dll'),
                (".bat", file_type_counts.get('bat', 0), 'bat'),
                (".cmd", file_type_counts.get('cmd', 0), 'cmd'),
                (".com", file_type_counts.get('com', 0), 'com')
            ])
        ]
        
        # Create tree structure for file types
        for main_category, main_count, subcategories in file_categories:
            if main_category == "By Extension":
                # By Extension is a folder containing direct file types
                by_ext_item = QTreeWidgetItem(file_types_item, [main_category])
                by_ext_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
                
                for subcat_name, subcat_count, subcat_type in subcategories:
                    label = f"{subcat_name} ({subcat_count})"
                    subcat_item = QTreeWidgetItem(by_ext_item, [label])
                    subcat_item.setData(0, Qt.UserRole, {
                        'type': 'file_type_filter',
                        'file_type': subcat_type,
                        'include_deleted': True
                    })
                    subcat_item.setIcon(0, self.style().standardIcon(QStyle.SP_FileIcon))
            else:
                # Documents and Executable are expandable categories
                main_item = QTreeWidgetItem(file_types_item, [main_category])
                main_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
                
                for subcat_name, subcat_count, subcat_type in subcategories:
                    label = f"{subcat_name} ({subcat_count})"
                    subcat_item = QTreeWidgetItem(main_item, [label])
                    subcat_item.setData(0, Qt.UserRole, {
                        'type': 'file_type_filter',
                        'file_type': subcat_type,
                        'include_deleted': True
                    })
                    subcat_item.setIcon(0, self.style().standardIcon(QStyle.SP_FileIcon))
        
        # Deleted Files view with count
        deleted_count = file_type_counts.get('deleted', 0)
        deleted_label = f"Deleted Files ({deleted_count})"
        deleted_item = QTreeWidgetItem(views_item, [deleted_label])
        deleted_item.setData(0, Qt.UserRole, {'type': 'deleted_files'})
        deleted_item.setIcon(0, self.style().standardIcon(QStyle.SP_TrashIcon))
    
    def add_navigation_folders(self, parent_item, fs_info):
        """Thêm các thư mục điều hướng vào node hệ thống tệp và nạp nhanh một phần nội dung."""
        
        try:
            # Add root directory and scan its contents
            self.populate_directory_tree(parent_item, fs_info, "/", depth=0, max_depth=2)
            
        except Exception as e:
            pass
    
    def populate_directory_tree(self, parent_item, fs_info, path="/", depth=0, max_depth=2):
        """Simple directory tree population"""
        if depth > max_depth:
            return
        try:
            directory = fs_info.open_dir(path=path)
            subdirs = []
            file_count = 0
            
            for entry in list(directory)[:50]:  # Limit entries
                try:
                    if entry.info.name.name in [b'.', b'..']:
                        continue
                    if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                        continue
                    
                    name = entry.info.name.name.decode('utf-8', errors='ignore')
                    if hasattr(entry.info.meta, 'type') and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        subdirs.append({'name': name, 'path': f"{path.rstrip('/')}/{name}" if path != "/" else f"/{name}"})
                    else:
                        file_count += 1
                except:
                    continue
            
            # Simple tree item
            dir_label = f"Root Directory [{len(subdirs)} folders, {file_count} files]" if path == "/" else os.path.basename(path)
            dir_item = QTreeWidgetItem(parent_item, [dir_label]) if depth == 0 else parent_item
            dir_item.setData(0, Qt.UserRole, {'type': 'directory', 'fs_info': fs_info, 'path': path})
            
            # Add subdirectories (limited)
            for subdir in subdirs[:10]:
                subdir_item = QTreeWidgetItem(dir_item, [subdir['name']])
                subdir_item.setData(0, Qt.UserRole, {'type': 'directory', 'fs_info': fs_info, 'path': subdir['path'], 'lazy_load': True})
                
        except:
            pass
    
    def on_tree_item_expanded(self, item):
        """Simple tree expansion handling"""
        data = item.data(0, Qt.UserRole)
        if not data or not data.get('lazy_load', False):
            return
        
        fs_info = data.get('fs_info')
        path = data.get('path')
        
        if fs_info and path:
            try:
                directory = fs_info.open_dir(path=path)
                subdirs = []
                
                for entry in list(directory)[:20]:  # Limit entries
                    try:
                        if entry.info.name.name in [b'.', b'..']:
                            continue
                        if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                            continue
                        
                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                        if hasattr(entry.info.meta, 'type') and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                            subdirs.append({'name': name, 'path': f"{path.rstrip('/')}/{name}"})
                    except:
                        continue
                
                # Add subdirectories
                for subdir in subdirs[:10]:
                    subdir_item = QTreeWidgetItem(item, [subdir['name']])
                    subdir_item.setData(0, Qt.UserRole, {
                        'type': 'directory',
                        'fs_info': fs_info,
                        'path': subdir['path'],
                        'lazy_load': True
                    })
                
                data['lazy_load'] = False
                item.setData(0, Qt.UserRole, data)
            except:
                pass
    
    def on_tree_item_clicked(self, item, column):
        """Xử lý click trên cây: nạp thư mục, phân vùng, tệp đã xóa hoặc lọc theo loại tệp."""
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        item_type = data.get('type')
        item_text = item.text(0)
        
        try:
            if item_type == 'filesystem':  # Click vào hệ thống tệp -> nạp thư mục gốc
                fs_info = data.get('fs_info')
                if fs_info:
                    self.load_filesystem_root(fs_info)
                    
            elif item_type == 'directory':  # Click vào thư mục -> nạp danh sách tệp trong thư mục đó
                fs_info = data.get('fs_info')
                path = data.get('path', '/')
                if fs_info:
                    self.load_directory_files(fs_info, path)
                    
            elif item_type == 'deleted_files':  # Chế độ xem tệp đã xóa -> quét toàn FS
                # Find the filesystem from the tree structure
                fs_info = self.find_filesystem_info()
                if fs_info:
                    self.load_deleted_files(fs_info)
                    
            elif item_type == 'file_type_filter':  # Lọc theo loại tệp -> duyệt và nạp theo phần mở rộng
                file_type = data.get('file_type')
                fs_info = self.find_filesystem_info()
                if fs_info and file_type:
                    self.load_files_by_type(fs_info, file_type)
                    
            elif item_type == 'partition':  # Click vào phân vùng -> nạp thư mục gốc của phân vùng
                partition = data.get('partition')
                if partition:
                    self.load_partition_root(partition)
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading data: {str(e)}")
    
    def find_filesystem_info(self):
        """Tìm đối tượng `pytsk3.FS_Info` đầu tiên khả dụng từ cây dữ liệu."""
        try:
            if not hasattr(self.ui, 'treeInvestigation'):
                return None

            root = self.ui.treeInvestigation.topLevelItem(0)  # Node tệp chứng cứ (cấp trên cùng)
            if root:
                for i in range(root.childCount()):
                    child = root.child(i)  # Có thể là phân vùng hoặc FS
                    data = child.data(0, Qt.UserRole)
                    if data and data.get('type') == 'filesystem':
                        return data.get('fs_info')  # Trả về FS đầu tiên tìm được

                    # Check partition children
                    for j in range(child.childCount()):
                        grandchild = child.child(j)  # Nếu child là phân vùng, grandchild là FS
                        data = grandchild.data(0, Qt.UserRole)
                        if data and data.get('type') == 'filesystem':
                            return data.get('fs_info')
            return None
        except:
            return None
    
    def load_filesystem_root(self, fs_info):
        """Nạp thư mục gốc của hệ thống tệp."""
        self.load_directory_files(fs_info, "/")
    
    def load_partition_root(self, partition):
        """Nạp thư mục gốc của một phân vùng dựa trên `start` offset."""
        try:
            offset = partition.start * 512 if hasattr(partition, 'start') else 0
            fs_info = pytsk3.FS_Info(self.img_info, offset=offset)
            self.load_directory_files(fs_info, "/")
        except Exception as e:
            pass  # Không mở được FS tại offset phân vùng
    
    def load_single_filesystem_root(self):
        """Nạp thư mục gốc khi ảnh đĩa chỉ có một hệ thống tệp."""
        try:
            fs_info = pytsk3.FS_Info(self.img_info)
            self.load_directory_files(fs_info, "/")
        except Exception as e:
            pass  # Không mở được FS đơn từ ảnh
    
    def load_directory_files(self, fs_info, path="/"):
        """Nạp danh sách tệp trong thư mục chỉ định, kèm phát hiện tệp đã xóa (tại gốc)."""
        
        try:
            self.file_list = []
            
            # Store current fs_info for later use
            self.fs_info = fs_info
            
            # Method 1: Open directory normally for allocated files
            try:
                directory = fs_info.open_dir(path=path)
                
                for entry in directory:
                    try:
                        # Skip . and ..
                        if entry.info.name.name in [b'.', b'..']:  # Bỏ qua 2 entry đặc biệt
                            continue
                        
                        file_info = self.extract_file_info_safe(entry, fs_info, path)  # Trích xuất thông tin tệp
                        if file_info:
                            self.file_list.append(file_info)
                            
                    except Exception as e:
                        continue
            except Exception as e:
                pass  # Không mở được thư mục tại đường dẫn chỉ định
            
            # Method 2: Scan for deleted files in current directory using inode walking
            if path == "/":  # Chỉ quét inode UNALLOC ở gốc để tránh trùng lặp
                try:
                    self.scan_unallocated_inodes(fs_info)
                except Exception as e:
                    pass
            
            # Sort files: directories first, then by name
            self.file_list.sort(key=lambda x: (x['type'] != 'Directory', x['name'].lower()))  # Thư mục trước, rồi theo tên
            
            self.update_file_table()  # Đổ vào bảng
            self.generate_timeline()  # Sinh timeline từ danh sách tệp
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading directory: {str(e)}")
    
    def load_deleted_files(self, fs_info):
        """Nạp toàn bộ tệp đã xóa bằng cách quét inode và duyệt hệ thống tệp (có thanh tiến trình)."""
        
        try:
            self.file_list = []
            self.fs_info = fs_info
            
            # Show progress dialog
            progress = QProgressDialog("Scanning for deleted files...", "Cancel", 0, 100, self)  # Tiến trình quét
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            # Method 1: Scan unallocated inodes
            self.scan_unallocated_inodes(fs_info, show_progress=progress)  # Quét inode UNALLOC
            
            # Method 2: Walk filesystem looking for unallocated entries
            progress.setLabelText("Walking filesystem for deleted entries...")
            self.walk_deleted_entries(fs_info, progress)  # Duyệt thư mục tìm entry UNALLOC
            
            progress.close()
            
            # Remove duplicates based on inode
            unique_files = {}  # Khử trùng lặp theo khóa (inode + tên)
            for file in self.file_list:
                key = f"{file['inode']}_{file['name']}"
                if key not in unique_files:
                    unique_files[key] = file
            self.file_list = list(unique_files.values())
            
            if len(self.file_list) > 0:
                self.update_file_table()
                
                # Save deleted files analysis to database
                if self.current_case_id:
                    self.save_deleted_files_analysis(len(self.file_list))
                
                QMessageBox.information(
                    self,
                    "Deleted Files Found",
                    f"Found {len(self.file_list)} deleted files.\n\n"
                    f"You can attempt to recover these files by selecting them."
                )
            else:
                QMessageBox.information(
                    self,
                    "No Deleted Files",
                    "No deleted files were found in this filesystem."
                )
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()  # Đảm bảo đóng tiến trình khi lỗi
            QMessageBox.warning(self, "Error", f"Error loading deleted files: {str(e)}")
    
    def load_files_by_type(self, fs_info, file_type):
        """Simple file loading by type"""
        try:
            self.file_list = []
            type_extensions = {
                'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
                'videos': ['.mp4', '.avi', '.mov', '.mkv'],
                'audio': ['.mp3', '.wav', '.flac'],
                'archives': ['.zip', '.rar', '.7z'],
                'exe': ['.exe', '.dll'],
                'other': []
            }
            
            target_extensions = type_extensions.get(file_type, [])
            
            # Simple search in root directory only
            try:
                root_dir = fs_info.open_dir(path="/")
                for entry in list(root_dir)[:100]:  # Limit entries
                    try:
                        if entry.info.name.name in [b'.', b'..']:
                            continue
                        if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                            continue
                        
                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                        ext = os.path.splitext(name)[1].lower()
                        
                        if ext in target_extensions:
                            file_info = self.extract_file_info_safe(entry, fs_info, "/")
                            if file_info:
                                self.file_list.append(file_info)
                    except:
                        continue
            except:
                pass
            
            self.update_file_table()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading files by type: {str(e)}")
    
    def extract_file_info_safe(self, entry, fs_info, current_path):
        """Trích xuất an toàn thông tin tệp từ entry của TSK (tên, kích thước, loại, thời gian, inode...)."""
        
        try:
            # Safe check for meta
            if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                return None
            
            # Get file name
            try:
                name = entry.info.name.name.decode('utf-8', errors='ignore')
            except:
                name = f"Unknown_File_{entry.info.meta.addr}"
            
            if not name or name in ['.', '..']:
                return None
            
            # Build full path
            if current_path == "/":
                full_path = f"/{name}"
            else:
                full_path = f"{current_path.rstrip('/')}/{name}"
            
            # Get file size
            size = entry.info.meta.size if hasattr(entry.info.meta, 'size') else 0
            
            # Get file type
            if hasattr(entry.info.meta, 'type') and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                file_type = "Directory"
            else:
                file_type = self.determine_file_type(name)
            
            # Get timestamps
            timestamps = self.extract_timestamps_safe(entry)
            
            # Check if deleted
            is_deleted = False
            if hasattr(entry.info.meta, 'flags'):
                is_deleted = bool(entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)
            
            return {
                'name': name,
                'size': size,
                'type': file_type,
                'path': full_path,
                'created': timestamps.get('created', 'Unknown'),
                'modified': timestamps.get('modified', 'Unknown'),
                'accessed': timestamps.get('accessed', 'Unknown'),
                'changed': timestamps.get('changed', 'Unknown'),
                'deleted': is_deleted,
                'inode': entry.info.meta.addr if hasattr(entry.info.meta, 'addr') else 'Unknown',
                'entry': entry,  # Store for content extraction
                'fs_info': fs_info  # Store fs_info reference for later use
            }
            
        except Exception as e:
            return None
    
    def extract_timestamps_safe(self, entry):
        """Trích xuất an toàn các mốc thời gian (created/modified/accessed/changed) từ entry."""
        
        timestamps = {
            'created': 'Unknown',
            'modified': 'Unknown',
            'accessed': 'Unknown',
            'changed': 'Unknown'
        }
        
        try:
            if (hasattr(entry.info, 'meta') and 
                hasattr(entry.info.meta, 'crtime') and 
                entry.info.meta.crtime):
                timestamps['created'] = datetime.fromtimestamp(entry.info.meta.crtime).strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        
        try:
            if (hasattr(entry.info, 'meta') and 
                hasattr(entry.info.meta, 'mtime') and 
                entry.info.meta.mtime):
                timestamps['modified'] = datetime.fromtimestamp(entry.info.meta.mtime).strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        
        try:
            if (hasattr(entry.info, 'meta') and 
                hasattr(entry.info.meta, 'atime') and 
                entry.info.meta.atime):
                timestamps['accessed'] = datetime.fromtimestamp(entry.info.meta.atime).strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        
        try:
            if (hasattr(entry.info, 'meta') and 
                hasattr(entry.info.meta, 'ctime') and 
                entry.info.meta.ctime):
                timestamps['changed'] = datetime.fromtimestamp(entry.info.meta.ctime).strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        
        return timestamps
    
    def determine_file_type(self, filename):
        """Xác định loại tệp sơ bộ dựa trên đuôi mở rộng (fallback: Unknown)."""
        
        if not filename:
            return "Unknown"
        
        ext = os.path.splitext(filename)[1].lower()
        
        type_map = {
            # Documents
            '.txt': 'Text File', '.doc': 'Word Document', '.docx': 'Word Document',
            '.pdf': 'PDF Document', '.rtf': 'Rich Text', '.odt': 'OpenDocument',
            '.xls': 'Excel Spreadsheet', '.xlsx': 'Excel Spreadsheet',
            '.ppt': 'PowerPoint', '.pptx': 'PowerPoint',
            
            # Images
            '.jpg': 'JPEG Image', '.jpeg': 'JPEG Image', '.png': 'PNG Image',
            '.gif': 'GIF Image', '.bmp': 'Bitmap Image', '.tiff': 'TIFF Image',
            '.svg': 'SVG Image', '.ico': 'Icon File',
            
            # Videos
            '.mp4': 'MP4 Video', '.avi': 'AVI Video', '.mov': 'QuickTime Video',
            '.wmv': 'Windows Media Video', '.mkv': 'Matroska Video', '.flv': 'Flash Video',
            
            # Audio
            '.mp3': 'MP3 Audio', '.wav': 'WAV Audio', '.flac': 'FLAC Audio',
            '.aac': 'AAC Audio', '.ogg': 'OGG Audio', '.wma': 'Windows Media Audio',
            
            # Archives
            '.zip': 'ZIP Archive', '.rar': 'RAR Archive', '.7z': '7-Zip Archive',
            '.tar': 'TAR Archive', '.gz': 'GZIP Archive',
            
            # Executables
            '.exe': 'Executable', '.dll': 'Library', '.sys': 'System File',
            '.msi': 'Installer', '.bat': 'Batch File', '.cmd': 'Command File'
        }
        
        return type_map.get(ext, 'Unknown File')
    
    def update_file_table(self):
        """Đổ dữ liệu danh sách tệp hiện có lên bảng (tô màu hàng nếu là tệp đã xóa)."""

        if not hasattr(self.ui, 'tableFiles'):
            return

        self.ui.tableFiles.setRowCount(len(self.file_list))
        
        for row, file_info in enumerate(self.file_list):
            # Columns: Name, Size, Modified, Accessed, Created, MFT Modified, Type, Path
            name_item = QTableWidgetItem(file_info['name'])
            name_item.setData(Qt.UserRole, file_info)
            self.ui.tableFiles.setItem(row, 0, name_item)
            self.ui.tableFiles.setItem(row, 1, QTableWidgetItem(self.format_file_size(file_info['size'])))
            self.ui.tableFiles.setItem(row, 2, QTableWidgetItem(file_info['modified']))
            self.ui.tableFiles.setItem(row, 3, QTableWidgetItem(file_info['accessed']))
            self.ui.tableFiles.setItem(row, 4, QTableWidgetItem(file_info['created']))
            self.ui.tableFiles.setItem(row, 5, QTableWidgetItem(file_info['changed']))  # Using 'changed' for MFT Modified
            self.ui.tableFiles.setItem(row, 6, QTableWidgetItem(file_info['type']))
            self.ui.tableFiles.setItem(row, 7, QTableWidgetItem(file_info['path']))
            
            # Highlight deleted files
            if file_info.get('deleted', False):
                for col in range(8):
                    item = self.ui.tableFiles.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 200, 200))
                        item.setToolTip("🗑️ Deleted file")
    
    def generate_timeline(self):
        """Simple timeline generation"""
        self.timeline_data = []
        for file_info in self.file_list[:50]:  # Limit to first 50 files
            if file_info['modified'] != 'Unknown':
                self.timeline_data.append({
                    'datetime': file_info['modified'],
                    'source': 'File System',
                    'type': 'File Modified',
                    'description': f"Modified: {file_info['name']}",
                    'artifact': file_info['path']
                })
        self.timeline_data.sort(key=lambda x: x['datetime'])
        self.update_timeline_table()
    
    def update_timeline_table(self):
        """Cập nhật bảng Timeline từ dữ liệu đã tạo."""

        if not hasattr(self.ui, 'tableTimeline'):
            return

        self.ui.tableTimeline.setRowCount(len(self.timeline_data))

        for row, event in enumerate(self.timeline_data):
            self.ui.tableTimeline.setItem(row, 0, QTableWidgetItem(event['datetime']))
            self.ui.tableTimeline.setItem(row, 1, QTableWidgetItem(event['source']))
            self.ui.tableTimeline.setItem(row, 2, QTableWidgetItem(event['type']))
            self.ui.tableTimeline.setItem(row, 3, QTableWidgetItem(event['description']))
            self.ui.tableTimeline.setItem(row, 4, QTableWidgetItem(event['artifact']))
    
    def on_file_selected(self):
        """Xử lý khi người dùng chọn một dòng trong bảng tệp để hiển thị chi tiết."""

        if not hasattr(self.ui, 'tableFiles'):
            return

        current_row = self.ui.tableFiles.currentRow()
        if 0 <= current_row < len(self.file_list):
            file_info = self.file_list[current_row]
            self.show_file_details(file_info)
    
    def show_file_details(self, file_info):
        """Hiển thị chi tiết tệp ở các tab: Thuộc tính, Metadata, Nội dung/Hex/Ảnh xem trước."""
        
        # Update File Properties
        self.update_file_properties(file_info)
        
        # Update Metadata
        self.update_file_metadata(file_info)
        
        # Update Content views
        self.update_file_content(file_info)
    
    def update_file_properties(self, file_info):
        """Cập nhật bảng Thuộc tính (Properties) của tệp đang chọn."""

        if not hasattr(self.ui, 'tableProperties'):
            return

        properties = [
            ("File Name", file_info['name']),
            ("File Size", self.format_file_size(file_info['size'])),
            ("File Type", file_info['type']),
            ("Full Path", file_info['path']),
            ("Created", file_info['created']),
            ("Modified", file_info['modified']),
            ("Accessed", file_info['accessed']),
            ("MFT Changed", file_info['changed']),
            ("Status", "DELETED" if file_info.get('deleted') else "Active"),
            ("Inode", str(file_info.get('inode', 'Unknown'))),
        ]

        self.ui.tableProperties.setRowCount(len(properties))

        for row, (prop, value) in enumerate(properties):
            self.ui.tableProperties.setItem(row, 0, QTableWidgetItem(prop))
            self.ui.tableProperties.setItem(row, 1, QTableWidgetItem(str(value)))
    
    def update_file_metadata(self, file_info):
        """Cập nhật bảng Siêu dữ liệu (Metadata) của tệp đang chọn."""

        if not hasattr(self.ui, 'tableMetadata'):
            return

        metadata = [
            ("File Name", file_info['name']),
            ("MIME Type", self.get_mime_type(file_info['name'])),
            ("File Extension", os.path.splitext(file_info['name'])[1]),
            ("File Size (bytes)", str(file_info['size'])),
            ("Directory", os.path.dirname(file_info['path'])),
            ("Inode Number", str(file_info.get('inode', 'Unknown'))),
            ("Is Deleted", "Yes" if file_info.get('deleted') else "No"),
        ]

        self.ui.tableMetadata.setRowCount(len(metadata))

        for row, (prop, value) in enumerate(metadata):
            self.ui.tableMetadata.setItem(row, 0, QTableWidgetItem(prop))
            self.ui.tableMetadata.setItem(row, 1, QTableWidgetItem(str(value)))
    
    def update_file_content(self, file_info):
        """Cập nhật vùng hiển thị nội dung: văn bản, hex, và ảnh xem trước (nếu là ảnh)."""
        
        # Clear previous content
        if hasattr(self.ui, 'textHexView'):
            self.ui.textHexView.clear()
        if hasattr(self.ui, 'textContentView'):
            self.ui.textContentView.clear()
        if hasattr(self.ui, 'labelPicture'):
            self.ui.labelPicture.clear()
        
        # Try to extract content if file is small enough
        if file_info['size'] > 1024 * 1024:  # > 1MB
            if hasattr(self.ui, 'textContentView'):
                self.ui.textContentView.setText("File too large to display content")
            if hasattr(self.ui, 'textHexView'):
                self.ui.textHexView.setText("File too large to display hex content")
        elif file_info['size'] == 0:
            if hasattr(self.ui, 'textContentView'):
                self.ui.textContentView.setText("Empty file")
            if hasattr(self.ui, 'textHexView'):
                self.ui.textHexView.setText("Empty file")
        else:
            try:
                content = self.extract_file_content_safe(file_info)
                if content:
                    # Text view
                    if hasattr(self.ui, 'textContentView'):
                        self.ui.textContentView.setText(content[:10000])  # First 10KB

                    # Hex view
                    if hasattr(self.ui, 'textHexView'):
                        hex_content = self.generate_hex_view(content[:1000])  # First 1KB
                        self.ui.textHexView.setText(hex_content)
                else:
                    if hasattr(self.ui, 'textContentView'):
                        self.ui.textContentView.setText("Could not extract file content")
                    if hasattr(self.ui, 'textHexView'):
                        self.ui.textHexView.setText("Could not extract file content")
            except Exception as e:
                if hasattr(self.ui, 'textContentView'):
                    self.ui.textContentView.setText(f"Error extracting content: {str(e)}")
                if hasattr(self.ui, 'textHexView'):
                    self.ui.textHexView.setText(f"Error extracting content: {str(e)}")

            # Picture view
            if hasattr(self.ui, 'labelPicture'):
                if 'image' in file_info['type'].lower():
                    # Try to show image preview
                    try:
                        raw_content = self.extract_raw_file_content(file_info)
                        if raw_content and len(raw_content) > 0:
                            pixmap = QPixmap()
                            if pixmap.loadFromData(raw_content):
                                # Scale image to fit label
                                scaled_pixmap = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                self.ui.labelPicture.setPixmap(scaled_pixmap)
                            else:
                                self.ui.labelPicture.setText("🖼️ Image file detected\n\nCould not load image preview")
                        else:
                            self.ui.labelPicture.setText("🖼️ Image file detected\n\nNo image data available")
                    except Exception as e:
                        self.ui.labelPicture.setText(f"🖼️ Image file detected\n\nPreview error: {str(e)}")
                else:
                    self.ui.labelPicture.setText(f"📄 {file_info['type']}\n\nNot an image file")
    
    def extract_file_content_safe(self, file_info):
        """Đọc nội dung tệp một cách an toàn bằng pytsk3 (ưu tiên NTFS, thử nhiều phương pháp đọc)."""
        
        try:
            entry = file_info.get('entry')
            if not entry:
                return None
            
            # Check if it's a directory
            if (hasattr(entry.info, 'meta') and hasattr(entry.info.meta, 'type') and 
                entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR):
                return "Directory - no content to display"
            
            # Read file data
            file_data = b''
            
            # NTFS $DATA attribute type is 128 (0x80)
            NTFS_DATA_ATTRIBUTE = 128
            
            # Method 1: Try to read directly if file has read method
            try:
                if hasattr(entry, 'read_random'):
                    size_to_read = min(file_info['size'], 50000) if file_info['size'] > 0 else 50000
                    file_data = entry.read_random(0, size_to_read)
            except Exception as e:
                pass  # Không đọc được trực tiếp (không hỗ trợ read_random)
            
            # Method 2: Try attribute-based reading for NTFS
            if not file_data:
                try:
                    for attr in entry:
                        if hasattr(attr.info, 'type'):
                            # Check for $DATA attribute (type 128 in NTFS)
                            if attr.info.type == NTFS_DATA_ATTRIBUTE:
                                # Check if it's the default data stream (no name)
                                if not hasattr(attr.info, 'name') or not attr.info.name or attr.info.name == b'':
                                    size_to_read = min(attr.info.size, 50000) if hasattr(attr.info, 'size') else 50000
                                    file_data = attr.read_random(0, size_to_read)
                                    if file_data:
                                        break
                except Exception as e:
                    pass  # Đọc thuộc tính thất bại (không phải NTFS/không có $DATA)
            
            # Method 3: Try filesystem-level reading
            if not file_data and hasattr(entry.info, 'meta') and hasattr(entry.info.meta, 'addr'):
                try:
                    fs_info = self.get_current_fs_info()
                    if fs_info:
                        file_obj = fs_info.open_meta(inode=entry.info.meta.addr)
                        if file_obj:
                            size_to_read = min(file_info['size'], 50000) if file_info['size'] > 0 else 50000
                            file_data = file_obj.read_random(0, size_to_read)
                except Exception as e:
                    pass  # Không mở lại theo inode được (inode không tồn tại/không đọc được)
            
            if file_data:
                # Try to decode as text
                try:
                    text_content = file_data.decode('utf-8', errors='ignore')
                    # Check if content is mostly printable
                    printable_ratio = sum(1 for c in text_content if c.isprintable() or c.isspace()) / len(text_content)
                    if printable_ratio > 0.8:
                        return text_content
                    else:
                        return f"Binary content ({len(file_data)} bytes)\n\n{self.generate_hex_preview(file_data[:500])}"
                except:
                    return f"Binary content ({len(file_data)} bytes)\n\n{self.generate_hex_preview(file_data[:500])}"
            
            return "No content data found (file may be resident in MFT or empty)"
            
        except Exception as e:
            return f"Content extraction error: {str(e)}"
    
    def generate_hex_view(self, content):
        """Generate simple hex view"""
        if isinstance(content, str):
            content = content.encode('utf-8', errors='ignore')
        return ' '.join(f'{b:02x}' for b in content[:100]) + ('...' if len(content) > 100 else '')
    
    def generate_hex_preview(self, content):
        """Generate simple hex preview"""
        if isinstance(content, str):
            content = content.encode('utf-8', errors='ignore')
        preview = ' '.join(f'{b:02x}' for b in content[:64])
        if len(content) > 64:
            preview += f' ... ({len(content)} total bytes)'
        return preview
    
    def get_mime_type(self, filename):
        """Suy đoán kiểu MIME của tệp dựa trên tên/đuôi mở rộng (mimetypes)."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    def perform_search(self):
        """Tìm kiếm theo từ khóa trong danh sách tệp hiện tại (tên và đường dẫn)."""

        if not hasattr(self.ui, 'lineEditSearch'):
            return

        keyword = self.ui.lineEditSearch.text().strip()
        if not keyword:
            QMessageBox.warning(self, "Search", "Please enter a search keyword.")
            return
        
        self.search_results = []
        
        # Search in file names and paths
        for file_info in self.file_list:
            matches = 0
            
            # Search in filename
            if keyword.lower() in file_info['name'].lower():
                matches += file_info['name'].lower().count(keyword.lower())
            
            # Search in path
            if keyword.lower() in file_info['path'].lower():
                matches += file_info['path'].lower().count(keyword.lower())
            
            if matches > 0:
                self.search_results.append({
                    'file_info': file_info,
                    'matches': matches
                })
        
        # Update search results table
        self.update_search_results()
        
        # Switch to search tab
        if hasattr(self.ui, 'tabWorkArea'):
            self.ui.tabWorkArea.setCurrentIndex(2)  # Search tab is index 2
        
        # Save search results to database if case is selected
        if self.current_case_id and len(self.search_results) > 0:
            self.save_search_results_to_database(keyword, self.search_results)
        
        QMessageBox.information(
            self, 
            "Search Complete", 
            f"Found {len(self.search_results)} files matching '{keyword}'"
        )
    
    def update_search_results(self):
        """Cập nhật bảng kết quả tìm kiếm (tô màu nếu là tệp đã xóa)."""

        if not hasattr(self.ui, 'tableSearchResults'):
            return

        self.ui.tableSearchResults.setRowCount(len(self.search_results))

        for row, result in enumerate(self.search_results):
            file_info = result['file_info']

            name_item = QTableWidgetItem(file_info['name'])
            name_item.setData(Qt.UserRole, file_info)
            self.ui.tableSearchResults.setItem(row, 0, name_item)
            self.ui.tableSearchResults.setItem(row, 1, QTableWidgetItem(file_info['path']))
            self.ui.tableSearchResults.setItem(row, 2, QTableWidgetItem(str(result['matches'])))
            self.ui.tableSearchResults.setItem(row, 3, QTableWidgetItem(file_info['modified']))

            # Highlight deleted files
            if file_info.get('deleted', False):
                for col in range(4):
                    item = self.ui.tableSearchResults.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 200, 200))
    
    def on_timeline_selected(self):
        """Xử lý khi chọn một dòng trong Timeline và hiển thị hộp thoại chi tiết sự kiện."""

        if not hasattr(self.ui, 'tableTimeline'):
            return

        current_row = self.ui.tableTimeline.currentRow()
        if 0 <= current_row < len(self.timeline_data):
            event = self.timeline_data[current_row]

            details = f"""Timeline Event Details:

📅 Date/Time: {event['datetime']}
📂 Source: {event['source']}
🔖 Type: {event['type']}
📝 Description: {event['description']}
🗂️ File/Artifact: {event['artifact']}"""

            QMessageBox.information(self, "Timeline Event", details)
    
    def format_file_size(self, size_bytes):
        """Định dạng kích thước (B, KB, MB, GB, TB) để hiển thị thân thiện."""
        
        if size_bytes == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def get_current_fs_info(self):
        """Lấy đối tượng `FS_Info` đang dùng từ danh sách tệp, biến lưu trữ hoặc tìm lại trong cây."""
        # Try to get from current file list
        if self.file_list and len(self.file_list) > 0:
            first_file = self.file_list[0]
            if 'fs_info' in first_file:
                return first_file['fs_info']
        
        # Try to get from stored fs_info
        if hasattr(self, 'fs_info') and self.fs_info:
            return self.fs_info
        
        # Try to find from tree
        return self.find_filesystem_info()
    
    def extract_raw_file_content(self, file_info):
        """Trích xuất dữ liệu nhị phân thô của tệp (ví dụ ảnh) để hiển thị/xuất ra tệp."""
        try:
            entry = file_info.get('entry')
            if not entry:
                return None
            
            # Check if it's a directory
            if (hasattr(entry.info, 'meta') and hasattr(entry.info.meta, 'type') and 
                entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR):
                return None
            
            file_data = b''
            max_size = min(file_info['size'], 5 * 1024 * 1024) if file_info['size'] > 0 else 5 * 1024 * 1024  # Max 5MB for images
            
            # NTFS $DATA attribute type is 128 (0x80)
            NTFS_DATA_ATTRIBUTE = 128
            
            # Method 1: Direct read
            try:
                if hasattr(entry, 'read_random'):
                    file_data = entry.read_random(0, max_size)
                    if file_data:
                        return file_data
            except:
                pass  # Không đọc trực tiếp được
            
            # Method 2: Attribute-based reading
            try:
                for attr in entry:
                    if hasattr(attr.info, 'type') and attr.info.type == NTFS_DATA_ATTRIBUTE:
                        if not hasattr(attr.info, 'name') or not attr.info.name or attr.info.name == b'':
                            size_to_read = min(attr.info.size, max_size) if hasattr(attr.info, 'size') else max_size
                            file_data = attr.read_random(0, size_to_read)
                            if file_data:
                                return file_data
            except:
                pass  # Không đọc theo thuộc tính (không phải NTFS/không có $DATA)
            
            # Method 3: Filesystem-level reading
            if hasattr(entry.info, 'meta') and hasattr(entry.info.meta, 'addr'):
                try:
                    fs_info = file_info.get('fs_info') or self.get_current_fs_info()
                    if fs_info:
                        file_obj = fs_info.open_meta(inode=entry.info.meta.addr)
                        if file_obj:
                            file_data = file_obj.read_random(0, max_size)
                            if file_data:
                                return file_data
                except:
                    pass  # Không thể mở lại theo inode
            
            return None
        except Exception as e:
            return None
    
    def scan_unallocated_inodes(self, fs_info, show_progress=None):
        """Simple unallocated inode scan (limited scope)"""
        try:
            first_inum = fs_info.info.first_inum if hasattr(fs_info.info, 'first_inum') else 0
            last_inum = min(fs_info.info.last_inum if hasattr(fs_info.info, 'last_inum') else 1000, 1000)
            
            deleted_count = 0
            for inode_num in range(first_inum, last_inum):
                try:
                    f = fs_info.open_meta(inode=inode_num)
                    if f and hasattr(f.info, 'meta') and f.info.meta:
                        meta = f.info.meta
                        if hasattr(meta, 'flags') and (meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC):
                            name = f"deleted_file_{inode_num}"
                            file_info = {
                                'name': name,
                                'size': meta.size if hasattr(meta, 'size') else 0,
                                'type': 'Deleted File',
                                'path': f"/$OrphanFiles/{name}",
                                'created': self.format_timestamp(meta.crtime if hasattr(meta, 'crtime') else 0),
                                'modified': self.format_timestamp(meta.mtime if hasattr(meta, 'mtime') else 0),
                                'accessed': self.format_timestamp(meta.atime if hasattr(meta, 'atime') else 0),
                                'changed': self.format_timestamp(meta.ctime if hasattr(meta, 'ctime') else 0),
                                'deleted': True,
                                'inode': inode_num,
                                'entry': f,
                                'fs_info': fs_info
                            }
                            self.file_list.append(file_info)
                            deleted_count += 1
                except:
                    pass
        except:
            pass
    
    def walk_deleted_entries(self, fs_info, progress=None):
        """Simple deleted entries walk"""
        try:
            root_dir = fs_info.open_dir(path="/")
            for entry in list(root_dir)[:100]:  # Limit to first 100 entries
                try:
                    if (hasattr(entry.info, 'meta') and entry.info.meta and 
                        hasattr(entry.info.meta, 'flags') and 
                        (entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)):
                        
                        file_info = self.extract_file_info_safe(entry, fs_info, "/")
                        if file_info:
                            file_info['deleted'] = True
                            self.file_list.append(file_info)
                except:
                    continue
        except:
            pass
    
    def get_file_type_from_meta(self, meta):
        """Suy ra loại tệp từ metadata (DIR/REG/LNK), dùng khi tên tệp không đáng tin cậy."""
        if hasattr(meta, 'type'):
            if meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                return "Directory"
            elif meta.type == pytsk3.TSK_FS_META_TYPE_REG:
                return "Regular File"
            elif meta.type == pytsk3.TSK_FS_META_TYPE_LNK:
                return "Symbolic Link"
        return "Unknown"
    
    def format_timestamp(self, timestamp):
        """Định dạng Unix timestamp thành chuỗi thời gian; trả về 'Unknown' nếu không hợp lệ."""
        try:
            if timestamp and timestamp > 0:
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        return "Unknown"
    
    def find_deleted_filename(self, fs_info, inode_num):
        """Try to find deleted filename (simplified)"""
        try:
            return f"deleted_file_{inode_num}"
        except:
            return None
    
    def guess_file_extension(self, file_obj):
        """Simple file extension guessing"""
        try:
            content = b''
            if hasattr(file_obj, 'read_random'):
                content = file_obj.read_random(0, 16)
            
            # Basic signatures
            if content.startswith(b'\xff\xd8\xff'):
                return '.jpg'
            elif content.startswith(b'\x89PNG'):
                return '.png'
            elif content.startswith(b'%PDF'):
                return '.pdf'
            elif content.startswith(b'MZ'):
                return '.exe'
            return ""
        except:
            return ""
    
    def count_files_by_type(self, partitions):
        """Simple file type counting"""
        return {
            'images': 0, 'videos': 0, 'audio': 0, 'archives': 0,
            'databases': 0, 'html': 0, 'office': 0, 'pdf': 0,
            'plaintext': 0, 'richtext': 0, 'exe': 0, 'dll': 0,
            'bat': 0, 'cmd': 0, 'com': 0, 'other': 0,
            'deleted': 0, 'total': 0
        }
    
    def recover_file(self, file_info):
        """Khôi phục tệp đã xóa (nếu còn dữ liệu), cho phép người dùng chọn nơi lưu ra đĩa."""
        try:
            if not file_info.get('deleted'):
                QMessageBox.warning(self, "Recovery", "This file is not deleted.")
                return
            
            # Ask where to save
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Recovered File",
                file_info['name'],
                "All Files (*.*)"
            )
            
            if not save_path:
                return
            
            # Extract file content
            content = self.extract_raw_file_content(file_info)
            
            if content:
                with open(save_path, 'wb') as f:
                    f.write(content)
                
                # Log recovery activity to database
                if self.current_case_id:
                    self.log_file_recovery(file_info, save_path, len(content))
                
                QMessageBox.information(
                    self,
                    "Recovery Successful",
                    f"File recovered successfully!\n\nSaved to: {save_path}\nSize: {len(content)} bytes"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Recovery Failed",
                    "Could not recover file content. The data may have been overwritten."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Recovery Error",
                f"Error recovering file: {str(e)}"
            )
            
    # ==============================
    # Context menu handlers & utils
    # ==============================
    def on_files_table_context_menu(self, position):
        if not hasattr(self.ui, 'tableFiles'):
            return
        index = self.ui.tableFiles.indexAt(position)
        if not index.isValid():
            return
        row = index.row()
        item = self.ui.tableFiles.item(row, 0)
        file_info = item.data(Qt.UserRole) if item else None
        if not file_info and 0 <= row < len(self.file_list):
            file_info = self.file_list[row]
        if not file_info:
            return

        menu = QMenu(self)
        act_view = QAction("View details", self)
        act_copy = QAction("Copy full path", self)
        act_export = QAction("Export raw...", self)
        act_recover = QAction("Recover (deleted)", self)
        act_recover.setEnabled(bool(file_info.get('deleted')))

        act_view.triggered.connect(lambda: self.show_file_details(file_info))
        act_copy.triggered.connect(lambda: self.copy_text_to_clipboard(file_info.get('path', '')))
        act_export.triggered.connect(lambda: self.export_raw_file(file_info))
        act_recover.triggered.connect(lambda: self.recover_file(file_info))

        menu.addAction(act_view)
        menu.addSeparator()
        menu.addAction(act_copy)
        menu.addAction(act_export)
        menu.addSeparator()
        menu.addAction(act_recover)

        menu.exec_(self.ui.tableFiles.viewport().mapToGlobal(position))

    def on_search_table_context_menu(self, position):
        if not hasattr(self.ui, 'tableSearchResults'):
            return
        index = self.ui.tableSearchResults.indexAt(position)
        if not index.isValid():
            return
        row = index.row()
        item = self.ui.tableSearchResults.item(row, 0)
        file_info = item.data(Qt.UserRole) if item else None
        if not file_info and 0 <= row < len(self.search_results):
            file_info = self.search_results[row].get('file_info')
        if not file_info:
            return

        menu = QMenu(self)
        act_view = QAction("View details", self)
        act_copy = QAction("Copy full path", self)
        act_export = QAction("Export raw...", self)
        act_recover = QAction("Recover (deleted)", self)
        act_recover.setEnabled(bool(file_info.get('deleted')))

        act_view.triggered.connect(lambda: self.show_file_details(file_info))
        act_copy.triggered.connect(lambda: self.copy_text_to_clipboard(file_info.get('path', '')))
        act_export.triggered.connect(lambda: self.export_raw_file(file_info))
        act_recover.triggered.connect(lambda: self.recover_file(file_info))

        menu.addAction(act_view)
        menu.addSeparator()
        menu.addAction(act_copy)
        menu.addAction(act_export)
        menu.addSeparator()
        menu.addAction(act_recover)

        menu.exec_(self.ui.tableSearchResults.viewport().mapToGlobal(position))

    def copy_text_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text or "")

    def export_raw_file(self, file_info):
        try:
            if not file_info:
                return
            suggest_name = file_info.get('name') or 'export.bin'
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Raw Content",
                suggest_name,
                "All Files (*.*)"
            )
            if not save_path:
                return
            content = self.extract_raw_file_content(file_info)
            if content:
                with open(save_path, 'wb') as f:
                    f.write(content)
                QMessageBox.information(self, "Export", f"Exported raw content to:\n{save_path}\nSize: {len(content)} bytes")
            else:
                QMessageBox.warning(self, "Export", "No raw content could be extracted for this file.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting content: {str(e)}")
