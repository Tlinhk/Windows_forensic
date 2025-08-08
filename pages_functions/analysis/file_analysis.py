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
import pytsk3  # Thư viện forensics: Python binding của The Sleuth Kit (đọc ảnh đĩa/hệ thống tệp)

# Import UI class
from ui.pages.analysis_ui.file_analysis_ui import Ui_EvidenceAnalysisWidget

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
        
    def get_ui_component(self, component_name):
        """Lấy thành phần UI theo tên từ `self` hoặc từ `self.ui` nếu có."""
        if hasattr(self, component_name):
            return getattr(self, component_name)
        elif hasattr(self.ui, component_name):
            return getattr(self.ui, component_name)
        else:
            return None
    
    def setup_table_properties(self):
        """Thiết lập thuộc tính các bảng để hiển thị đẹp, dễ đọc và có sắp xếp."""
        
        # File table
        table_files = self.get_ui_component('tableFiles')
        if table_files:
            # Cột 0 (Name) giãn ra chiếm phần trống, các cột khác tự điều chỉnh
            table_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Name
            table_files.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Size
            table_files.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Type
            table_files.setSortingEnabled(True)
        
        # Timeline table
        table_timeline = self.get_ui_component('tableTimeline')
        if table_timeline:
            table_timeline.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # Description
            table_timeline.setSortingEnabled(True)
        
        # Search results table
        table_search = self.get_ui_component('tableSearchResults')
        if table_search:
            table_search.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Path
            table_search.setSortingEnabled(True)
        
        # Metadata and properties tables
        table_metadata = self.get_ui_component('tableMetadata')
        if table_metadata:
            table_metadata.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        table_properties = self.get_ui_component('tableProperties')
        if table_properties:
            table_properties.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    
    def setup_connections(self):
        """Kết nối các tín hiệu (signal) của UI với các slot xử lý tương ứng."""
        try:
            # Load evidence button
            btn_load = self.get_ui_component('btnLoadEvidence')  # Nút "Load Evidence"
            if btn_load:
                btn_load.clicked.connect(self.load_evidence_dialog)  # Nhấn để mở hộp thoại chọn ảnh đĩa
            
            # Tree widget
            tree = self.get_ui_component('treeInvestigation')  # Cây duyệt dữ liệu (ảnh đĩa/phân vùng/FS/thư mục)
            if tree:
                tree.itemClicked.connect(self.on_tree_item_clicked)  # Click vào node -> xử lý theo loại node
                tree.itemExpanded.connect(self.on_tree_item_expanded)  # Mở rộng node -> lazy load nội dung
            
            # File table
            table_files = self.get_ui_component('tableFiles')  # Bảng liệt kê tệp ở thư mục đang xem
            if table_files:
                table_files.itemSelectionChanged.connect(self.on_file_selected)  # Chọn dòng -> hiển thị chi tiết
            
            # Search controls
            btn_search = self.get_ui_component('btnSearch')  # Nút tìm kiếm theo từ khóa
            if btn_search:
                btn_search.clicked.connect(self.perform_search)  # Bấm để tìm
            
            line_search = self.get_ui_component('lineEditSearch')  # Ô nhập từ khóa tìm kiếm
            if line_search:
                line_search.returnPressed.connect(self.perform_search)  # Nhấn Enter để tìm
            
            # Timeline table
            table_timeline = self.get_ui_component('tableTimeline')  # Bảng hiển thị timeline sự kiện
            if table_timeline:
                table_timeline.itemSelectionChanged.connect(self.on_timeline_selected)  # Chọn -> xem chi tiết sự kiện
                
        except Exception as e:
            pass  # Bỏ qua lỗi kết nối tín hiệu để tránh làm chết UI khi thiếu thành phần
    
    def initialize_empty_state(self):
        """Khởi tạo trạng thái rỗng: dọn cây dữ liệu, bảng và các vùng hiển thị nội dung."""
        
        # Clear the pre-populated tree completely
        tree = self.get_ui_component('treeInvestigation')  # Cây dữ liệu
        if tree:
            tree.clear()  # Xóa toàn bộ node cũ
            tree.setHeaderLabel("Data Sources")  # Tiêu đề cột cây
        
        # Clear all tables
        table_files = self.get_ui_component('tableFiles')  # Bảng tệp
        if table_files:
            table_files.setRowCount(0)  # Xóa nội dung bảng
        
        table_timeline = self.get_ui_component('tableTimeline')  # Bảng timeline
        if table_timeline:
            table_timeline.setRowCount(0)  # Xóa nội dung
        
        table_search = self.get_ui_component('tableSearchResults')  # Bảng kết quả tìm kiếm
        if table_search:
            table_search.setRowCount(0)  # Xóa nội dung
        
        table_metadata = self.get_ui_component('tableMetadata')  # Bảng metadata tệp
        if table_metadata:
            table_metadata.setRowCount(0)
        
        table_properties = self.get_ui_component('tableProperties')  # Bảng thuộc tính tệp
        if table_properties:
            table_properties.setRowCount(0)
        
        # Clear text views
        text_hex = self.get_ui_component('textHexView')  # Ô xem hex
        if text_hex:
            text_hex.clear()
        
        text_content = self.get_ui_component('textContentView')  # Ô xem nội dung văn bản
        if text_content:
            text_content.clear()
        
        text_analysis = self.get_ui_component('textAnalysisResults')  # Ô hiển thị kết quả phân tích khác
        if text_analysis:
            text_analysis.clear()
        
        label_picture = self.get_ui_component('labelPicture')  # Ảnh xem trước (nếu là hình)
        if label_picture:
            label_picture.clear()
        
        # Update case info to show no evidence loaded
        label_case = self.get_ui_component('labelCaseInfo')  # Nhãn tiêu đề trạng thái
        if label_case:
            label_case.setText("File Analysis - No evidence loaded")  # Chưa nạp chứng cứ
    
    def load_case_data(self, case_id):
        """Nạp thông tin vụ án từ cơ sở dữ liệu để hiển thị lên thanh tiêu đề."""
        self.current_case_id = case_id
        
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()  # Quản lý kết nối CSDL
            db.connect()  # Mở kết nối
            
            case_info = db.get_case_with_investigator(case_id)  # Lấy thông tin vụ án + điều tra viên
            if case_info:
                text = f"File Analysis - Case: {case_info['title']} (ID: {case_id})"
                label_case = self.get_ui_component('labelCaseInfo')  # Cập nhật tiêu đề
                if label_case:
                    label_case.setText(text)
                    
        except Exception as e:
            pass
    
    def load_evidence_dialog(self):
        """Hiển thị hộp thoại chọn tệp chứng cứ (ảnh đĩa) để phân tích."""
        
        file_dialog = QFileDialog()  # Hộp thoại chọn tệp
        file_path, _ = file_dialog.getOpenFileName(
            self, 
            "Select Evidence File", 
            "", 
            "Disk Images (*.dd *.img *.raw *.E01 *.001);;All Files (*)"  # Bộ lọc tệp
        )
        
        if file_path and os.path.exists(file_path):  # Người dùng đã chọn và tệp tồn tại
            self.load_evidence_file(file_path)
    
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
            label_case = self.get_ui_component('labelCaseInfo')  # Cập nhật tiêu đề có tên chứng cứ
            if label_case:
                current_text = label_case.text()
                if "Case:" in current_text:
                    label_case.setText(f"{current_text} | Evidence: {file_name}")
                else:
                    label_case.setText(f"File Analysis | Evidence: {file_name}")
            
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
            
            # Show success message
            deleted_count = len([f for f in self.file_list if f.get('deleted', False)])  # Đếm số tệp đã xóa
            QMessageBox.information(
                self, 
                "Evidence Loaded Successfully", 
                f"✅ Successfully loaded evidence file!\n\n"
                f"📁 File: {file_name}\n"
                f"💾 Size: {self.format_file_size(image_size)}\n"
                f"🗂️ Partitions: {len(partitions) if partitions[0] else 1}\n"
                f"📋 Files Found: {len(self.file_list):,}\n"
                f"🗑️ Deleted Files: {deleted_count:,}\n\n"
                f"Use the tree view to navigate and explore the evidence."
            )
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()  # Đảm bảo đóng tiến trình nếu xảy ra lỗi
            
            error_msg = f"Failed to load evidence file:\n\n{str(e)}"
            QMessageBox.critical(self, "Error Loading Evidence", error_msg)
    
    def build_evidence_tree(self, evidence_name, partitions):
        """Xây dựng cây dữ liệu chứng cứ (giống Autopsy) gồm ảnh đĩa, phân vùng và hệ thống tệp."""
        
        tree = self.get_ui_component('treeInvestigation')
        if not tree:
            return
        
        # Clear tree completely
        tree.clear()
        tree.setHeaderLabel("Data Sources")
        
        # Node gốc - tên tệp chứng cứ
        root_item = QTreeWidgetItem(tree, [evidence_name])
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
        views_item = QTreeWidgetItem(tree, ["Views"])
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
        """Đệ quy điền cây thư mục kèm số lượng thư mục con/tệp để hiển thị.

        Giới hạn độ sâu (`max_depth`) và số lượng mục để tránh treo UI.
        """
        
        if depth > max_depth:
            return
        
        try:
            # Open directory
            try:
                directory = fs_info.open_dir(path=path)
            except:
                return  # Không mở được thư mục (có thể do quyền/FS không hỗ trợ)
            
            # Count files and subdirectories
            subdirs = []
            file_count = 0
            total_size = 0
            
            for entry in directory:
                try:
                    if entry.info.name.name in [b'.', b'..']:
                        continue
                    
                    if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                        continue
                    
                    name = entry.info.name.name.decode('utf-8', errors='ignore')
                    
                    # Check if it's a directory
                    if hasattr(entry.info.meta, 'type') and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        # Store subdirectory info
                        subdirs.append({
                            'name': name,
                            'path': f"{path.rstrip('/')}/{name}" if path != "/" else f"/{name}",
                            'entry': entry
                        })
                    else:
                        # It's a file
                        file_count += 1
                        if hasattr(entry.info.meta, 'size'):
                            total_size += entry.info.meta.size
                    
                except:
                    continue  # Bỏ qua entry lỗi để tiếp tục quét
            
            # Create tree item for current directory
            if path == "/":
                dir_label = f"Root Directory (/) [{len(subdirs)} folders, {file_count} files]"
            else:
                dir_name = os.path.basename(path)
                dir_label = f"{dir_name} [{len(subdirs)} folders, {file_count} files]"
            
            if depth == 0:  # Root level
                dir_item = QTreeWidgetItem(parent_item, [dir_label])
            else:
                dir_item = parent_item
            
            dir_item.setData(0, Qt.UserRole, {
                'type': 'directory',
                'fs_info': fs_info,
                'path': path,
                'file_count': file_count,
                'dir_count': len(subdirs),
                'total_size': total_size
            })
            
            # Add icon for directory
            dir_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
            
            # Recursively add subdirectories
            for subdir in subdirs[:20]:  # Limit to first 20 subdirs to avoid UI freeze
                subdir_label = f"{subdir['name']}"
                subdir_item = QTreeWidgetItem(dir_item, [subdir_label])
                subdir_item.setData(0, Qt.UserRole, {
                    'type': 'directory',
                    'fs_info': fs_info,
                    'path': subdir['path'],
                    'lazy_load': True  # Mark for lazy loading
                })
                subdir_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
                
                # Add placeholder child to show expand arrow
                if depth < max_depth - 1:
                    placeholder = QTreeWidgetItem(subdir_item, ["Loading..."])
                    placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})
            
            # If there are more subdirectories, add a "more" indicator
            if len(subdirs) > 20:
                more_item = QTreeWidgetItem(dir_item, [f"... and {len(subdirs) - 20} more folders"])
                more_item.setData(0, Qt.UserRole, {'type': 'more_folders', 'path': path})
                more_item.setForeground(0, QColor(128, 128, 128))
            
        except Exception as e:
            pass  # An toàn: không chặn UI khi có lỗi lẻ tẻ
    
    def on_tree_item_expanded(self, item):
        """Xử lý khi người dùng mở rộng node trong cây (lazy load các thư mục con)."""
        
        data = item.data(0, Qt.UserRole)  # Metadata gắn với node
        if not data:
            return
        
        # Check if this item needs lazy loading
        if data.get('lazy_load', False):
            # Remove placeholder
            for i in range(item.childCount() - 1, -1, -1):
                child = item.child(i)
                child_data = child.data(0, Qt.UserRole)
                if child_data and child_data.get('type') == 'placeholder':
                    item.removeChild(child)
            
            # Load subdirectory contents
            fs_info = data.get('fs_info')
            path = data.get('path')
            
            if fs_info and path:
                try:
                    # Count files and subdirectories
                    directory = fs_info.open_dir(path=path)
                    subdirs = []
                    file_count = 0
                    
                    for entry in directory:
                        try:
                            if entry.info.name.name in [b'.', b'..']:
                                continue
                            
                            if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                                continue
                            
                            name = entry.info.name.name.decode('utf-8', errors='ignore')
                            
                            if hasattr(entry.info.meta, 'type') and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                                subdirs.append({
                                    'name': name,
                                    'path': f"{path.rstrip('/')}/{name}"
                                })
                            else:
                                file_count += 1
                        except:
                            continue
                    
                    # Update item label with counts
                    dir_name = os.path.basename(path) if path != "/" else "Root Directory (/)"
                    item.setText(0, f"{dir_name} [{len(subdirs)} folders, {file_count} files]")
                    
                    # Add subdirectories
                    for subdir in subdirs[:20]:
                        subdir_item = QTreeWidgetItem(item, [subdir['name']])
                        subdir_item.setData(0, Qt.UserRole, {
                            'type': 'directory',
                            'fs_info': fs_info,
                            'path': subdir['path'],
                            'lazy_load': True
                        })
                        subdir_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
                        
                        # Add placeholder for expand arrow
                        placeholder = QTreeWidgetItem(subdir_item, ["Loading..."])
                        placeholder.setData(0, Qt.UserRole, {'type': 'placeholder'})
                    
                    # Remove lazy_load flag
                    data['lazy_load'] = False
                    item.setData(0, Qt.UserRole, data)
                    
                except Exception as e:
                    pass  # Không thể liệt kê thư mục con; giữ nguyên node hiện tại
    
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
            tree = self.get_ui_component('treeInvestigation')  # Cây dữ liệu
            if not tree:
                return None
                
            root = tree.topLevelItem(0)  # Node tệp chứng cứ (cấp trên cùng)
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
        """Lọc và nạp tệp theo loại (map đuôi mở rộng -> nhóm như ảnh, video, tài liệu, thực thi...)."""
        
        try:
            self.file_list = []
            
            # Updated file type mappings to match count_files_by_type
            type_extensions = {
                # By Extension categories
                'images': ['.jpg', '.jpeg', '.png', '.psd', '.nef', '.tiff', '.bmp', '.tec', '.tif', '.webp', '.gif', '.svg', '.ico'],
                'videos': ['.asf', '.3gp', '.avi', '.m1v', '.m2v', '.m4v', '.mp4', '.mov', '.mpeg', '.mpg', '.mpe', '.rm', '.wmv', '.mpv', '.flv', '.swf', '.mkv', '.webm'],
                'audio': ['.aiff', '.aif', '.flac', '.wav', '.m3u', '.ape', '.wma', '.mp2', '.mp1', '.mp3', '.aac', '.m4a', '.m4p', '.m1a', '.m2a', '.mpa', '.mid', '.midi', '.ogg'],
                'archives': ['.zip', '.rar', '.7zip', '.7z', '.arj', '.tar', '.gzip', '.bzip', '.bzip2', '.cab', '.dar', '.cpio', '.ar', '.gz', '.tgz', '.bz2'],
                'databases': ['.db', '.db3', '.sqlite', '.sqlite3'],
                # Document subcategories
                'html': ['.htm', '.html'],
                'office': ['.doc', '.docx', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
                'pdf': ['.pdf'],
                'plaintext': ['.txt'],
                'richtext': ['.rtf'],
                # Executable subcategories
                'exe': ['.exe', '.msi'],
                'dll': ['.dll'],
                'bat': ['.bat'],
                'cmd': ['.cmd'],
                'com': ['.com', '.scr', '.ini', '.reg'],
                'executables': ['.exe', '.dll', '.sys', '.msi', '.bat', '.cmd', '.scr'],  # Legacy support
                'other': []  # Will be populated with files that don't match other categories
            }
            
            target_extensions = type_extensions.get(file_type, [])
            
            # Walk through filesystem
            def find_files_by_type(directory, current_path="/", depth=0):  # Đệ quy duyệt theo loại tệp
                if depth > 10:  # Limit recursion depth
                    return
                    
                try:
                    for entry in directory:
                        try:
                            if entry.info.name.name in [b'.', b'..']:  # Bỏ qua 2 entry đặc biệt
                                continue
                            
                            # Safe check for meta
                            if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                                continue
                            
                            name = entry.info.name.name.decode('utf-8', errors='ignore')  # Tên tệp/thư mục
                            
                            if file_type == 'other':
                                # For "other", include files that don't match any specific category
                                ext = os.path.splitext(name)[1].lower()
                                all_extensions = []  # Tập hợp tất cả đuôi thuộc các nhóm đã biết
                                for exts in type_extensions.values():
                                    all_extensions.extend(exts)
                                
                                if (ext not in all_extensions and 
                                    hasattr(entry.info.meta, 'type') and
                                    entry.info.meta.type != pytsk3.TSK_FS_META_TYPE_DIR):
                                    file_info = self.extract_file_info_safe(entry, fs_info, current_path)  # Tệp thuộc nhóm khác
                                    if file_info:
                                        self.file_list.append(file_info)
                            else:
                                # Check file extension
                                ext = os.path.splitext(name)[1].lower()
                                if ext in target_extensions:
                                    file_info = self.extract_file_info_safe(entry, fs_info, current_path)  # Tệp thuộc nhóm mục tiêu
                                    if file_info:
                                        self.file_list.append(file_info)
                            
                            # Recurse into directories
                            if (hasattr(entry.info.meta, 'type') and 
                                entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR):
                                try:
                                    if name and name not in ['.', '..']:
                                        sub_path = f"{current_path.rstrip('/')}/{name}"  # Cập nhật đường dẫn con
                                        sub_dir = fs_info.open_dir(inode=entry.info.meta.addr)  # Mở thư mục con theo inode
                                        find_files_by_type(sub_dir, sub_path, depth + 1)
                                except:
                                    pass
                                    
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    pass
            
            # Start search
            root_dir = fs_info.open_dir(path="/")
            find_files_by_type(root_dir)
            
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
        
        table_files = self.get_ui_component('tableFiles')
        if not table_files:
            return
        
        table_files.setRowCount(len(self.file_list))
        
        for row, file_info in enumerate(self.file_list):
            # Columns: Name, Size, Modified, Accessed, Created, MFT Modified, Type, Path
            table_files.setItem(row, 0, QTableWidgetItem(file_info['name']))
            table_files.setItem(row, 1, QTableWidgetItem(self.format_file_size(file_info['size'])))
            table_files.setItem(row, 2, QTableWidgetItem(file_info['modified']))
            table_files.setItem(row, 3, QTableWidgetItem(file_info['accessed']))
            table_files.setItem(row, 4, QTableWidgetItem(file_info['created']))
            table_files.setItem(row, 5, QTableWidgetItem(file_info['changed']))  # Using 'changed' for MFT Modified
            table_files.setItem(row, 6, QTableWidgetItem(file_info['type']))
            table_files.setItem(row, 7, QTableWidgetItem(file_info['path']))
            
            # Highlight deleted files
            if file_info.get('deleted', False):
                for col in range(8):
                    item = table_files.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 200, 200))
                        item.setToolTip("🗑️ Deleted file")
    
    def generate_timeline(self):
        """Tạo danh sách sự kiện Timeline từ các mốc thời gian của từng tệp và sắp xếp theo thời gian."""
        
        self.timeline_data = []
        
        for file_info in self.file_list:
            # Add timeline events for each timestamp
            timestamps = [
                ('File Created', file_info['created']),
                ('File Modified', file_info['modified']),
                ('File Accessed', file_info['accessed']),
                ('MFT Changed', file_info['changed'])
            ]
            
            for event_type, timestamp in timestamps:
                if timestamp and timestamp != 'Unknown':
                    self.timeline_data.append({
                        'datetime': timestamp,
                        'source': 'File System',
                        'type': event_type,
                        'description': f"{event_type}: {file_info['name']}",
                        'artifact': file_info['path']
                    })
        
        # Sort by datetime
        self.timeline_data.sort(key=lambda x: x['datetime'])
        
        # Update timeline table
        self.update_timeline_table()
    
    def update_timeline_table(self):
        """Cập nhật bảng Timeline từ dữ liệu đã tạo."""
        
        table_timeline = self.get_ui_component('tableTimeline')
        if not table_timeline:
            return
        
        table_timeline.setRowCount(len(self.timeline_data))
        
        for row, event in enumerate(self.timeline_data):
            table_timeline.setItem(row, 0, QTableWidgetItem(event['datetime']))
            table_timeline.setItem(row, 1, QTableWidgetItem(event['source']))
            table_timeline.setItem(row, 2, QTableWidgetItem(event['type']))
            table_timeline.setItem(row, 3, QTableWidgetItem(event['description']))
            table_timeline.setItem(row, 4, QTableWidgetItem(event['artifact']))
    
    def on_file_selected(self):
        """Xử lý khi người dùng chọn một dòng trong bảng tệp để hiển thị chi tiết."""
        
        table_files = self.get_ui_component('tableFiles')
        if not table_files:
            return
        
        current_row = table_files.currentRow()
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
        
        table_properties = self.get_ui_component('tableProperties')
        if not table_properties:
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
        
        table_properties.setRowCount(len(properties))
        
        for row, (prop, value) in enumerate(properties):
            table_properties.setItem(row, 0, QTableWidgetItem(prop))
            table_properties.setItem(row, 1, QTableWidgetItem(str(value)))
    
    def update_file_metadata(self, file_info):
        """Cập nhật bảng Siêu dữ liệu (Metadata) của tệp đang chọn."""
        
        table_metadata = self.get_ui_component('tableMetadata')
        if not table_metadata:
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
        
        table_metadata.setRowCount(len(metadata))
        
        for row, (prop, value) in enumerate(metadata):
            table_metadata.setItem(row, 0, QTableWidgetItem(prop))
            table_metadata.setItem(row, 1, QTableWidgetItem(str(value)))
    
    def update_file_content(self, file_info):
        """Cập nhật vùng hiển thị nội dung: văn bản, hex, và ảnh xem trước (nếu là ảnh)."""
        
        # Clear previous content
        text_hex = self.get_ui_component('textHexView')
        text_content = self.get_ui_component('textContentView')
        label_picture = self.get_ui_component('labelPicture')
        
        if text_hex:
            text_hex.clear()
        if text_content:
            text_content.clear()
        if label_picture:
            label_picture.clear()
        
        # Try to extract content if file is small enough
        if file_info['size'] > 1024 * 1024:  # > 1MB
            if text_content:
                text_content.setText("File too large to display content")
            if text_hex:
                text_hex.setText("File too large to display hex content")
        elif file_info['size'] == 0:
            if text_content:
                text_content.setText("Empty file")
            if text_hex:
                text_hex.setText("Empty file")
        else:
            try:
                content = self.extract_file_content_safe(file_info)
                if content:
                    # Text view
                    if text_content:
                        text_content.setText(content[:10000])  # First 10KB
                    
                    # Hex view
                    if text_hex:
                        hex_content = self.generate_hex_view(content[:1000])  # First 1KB
                        text_hex.setText(hex_content)
                else:
                    if text_content:
                        text_content.setText("Could not extract file content")
                    if text_hex:
                        text_hex.setText("Could not extract file content")
            except Exception as e:
                if text_content:
                    text_content.setText(f"Error extracting content: {str(e)}")
                if text_hex:
                    text_hex.setText(f"Error extracting content: {str(e)}")
        
            # Picture view
            if label_picture:
                if 'image' in file_info['type'].lower():
                    # Try to show image preview
                    try:
                        raw_content = self.extract_raw_file_content(file_info)
                        if raw_content and len(raw_content) > 0:
                            pixmap = QPixmap()
                            if pixmap.loadFromData(raw_content):
                                # Scale image to fit label
                                scaled_pixmap = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                label_picture.setPixmap(scaled_pixmap)
                            else:
                                label_picture.setText("🖼️ Image file detected\n\nCould not load image preview")
                        else:
                            label_picture.setText("🖼️ Image file detected\n\nNo image data available")
                    except Exception as e:
                        label_picture.setText(f"🖼️ Image file detected\n\nPreview error: {str(e)}")
                else:
                    label_picture.setText(f"📄 {file_info['type']}\n\nNot an image file")
    
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
        """Sinh chuỗi hiển thị nội dung dạng hex kèm cột ASCII để quan sát nhanh."""
        
        if isinstance(content, str):
            content = content.encode('utf-8', errors='ignore')
        
        hex_lines = []
        for i in range(0, len(content), 16):
            chunk = content[i:i+16]
            
            # Offset
            offset = f"{i:08x}"
            
            # Hex bytes
            hex_bytes = ' '.join(f'{b:02x}' for b in chunk)
            hex_bytes = hex_bytes.ljust(48)  # Pad to consistent width
            
            # ASCII representation
            ascii_chars = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            
            hex_lines.append(f"{offset}  {hex_bytes} |{ascii_chars}|")
        
        return '\n'.join(hex_lines)
    
    def generate_hex_preview(self, content):
        """Sinh phần xem trước dạng hex ngắn gọn cho dữ liệu nhị phân."""
        if isinstance(content, str):
            content = content.encode('utf-8', errors='ignore')
        
        hex_lines = []
        preview_size = min(len(content), 256)  # Show first 256 bytes
        
        for i in range(0, preview_size, 16):
            chunk = content[i:i+16]
            offset = f"{i:08x}"
            hex_bytes = ' '.join(f'{b:02x}' for b in chunk)
            hex_bytes = hex_bytes.ljust(48)
            ascii_chars = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            hex_lines.append(f"{offset}  {hex_bytes} |{ascii_chars}|")
        
        if len(content) > preview_size:
            hex_lines.append(f"\n... ({len(content) - preview_size} more bytes) ...")
        
        return '\n'.join(hex_lines)
    
    def get_mime_type(self, filename):
        """Suy đoán kiểu MIME của tệp dựa trên tên/đuôi mở rộng (mimetypes)."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    def perform_search(self):
        """Tìm kiếm theo từ khóa trong danh sách tệp hiện tại (tên và đường dẫn)."""
        
        line_search = self.get_ui_component('lineEditSearch')
        if not line_search:
            return
        
        keyword = line_search.text().strip()
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
        tab_work = self.get_ui_component('tabWorkArea')
        if tab_work:
            tab_work.setCurrentIndex(2)  # Search tab is index 2
        
        QMessageBox.information(
            self, 
            "Search Complete", 
            f"Found {len(self.search_results)} files matching '{keyword}'"
        )
    
    def update_search_results(self):
        """Cập nhật bảng kết quả tìm kiếm (tô màu nếu là tệp đã xóa)."""
        
        table_search = self.get_ui_component('tableSearchResults')
        if not table_search:
            return
        
        table_search.setRowCount(len(self.search_results))
        
        for row, result in enumerate(self.search_results):
            file_info = result['file_info']
            
            table_search.setItem(row, 0, QTableWidgetItem(file_info['name']))
            table_search.setItem(row, 1, QTableWidgetItem(file_info['path']))
            table_search.setItem(row, 2, QTableWidgetItem(str(result['matches'])))
            table_search.setItem(row, 3, QTableWidgetItem(file_info['modified']))
            
            # Highlight deleted files
            if file_info.get('deleted', False):
                for col in range(4):
                    item = table_search.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 200, 200))
    
    def on_timeline_selected(self):
        """Xử lý khi chọn một dòng trong Timeline và hiển thị hộp thoại chi tiết sự kiện."""
        
        table_timeline = self.get_ui_component('tableTimeline')
        if not table_timeline:
            return
        
        current_row = table_timeline.currentRow()
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
        """Quét các inode không còn cấp phát (tệp đã xóa) và tạo bản ghi tạm cho mỗi tệp tìm thấy.

        - Duyệt theo lô (chunk) để tránh tốn bộ nhớ.
        - Cố gắng khôi phục tên tệp đã xóa, nếu không sẽ đặt tên $OrphanFile_<inode>.
        """
        try:
            # Get filesystem info
            fs_type = fs_info.info.ftype if hasattr(fs_info.info, 'ftype') else 0
            last_inum = fs_info.info.last_inum if hasattr(fs_info.info, 'last_inum') else 0
            first_inum = fs_info.info.first_inum if hasattr(fs_info.info, 'first_inum') else 0
            
            if last_inum == 0:
                last_inum = 100000  # Giá trị mặc định khi FS không cung cấp last_inum
            
            deleted_count = 0
            checked_count = 0
            
            # Scan inodes in chunks to avoid memory issues
            chunk_size = 1000  # Quét theo lô để tiết kiệm bộ nhớ
            for start_inode in range(first_inum, min(last_inum, 50000), chunk_size):
                end_inode = min(start_inode + chunk_size, last_inum)
                
                if show_progress:  # Cập nhật tiến trình nếu có hộp thoại
                    progress_pct = int((start_inode / min(last_inum, 50000)) * 100)
                    show_progress.setValue(progress_pct)
                    show_progress.setLabelText(f"Scanning inodes {start_inode} - {end_inode}...")
                    QApplication.processEvents()
                    
                    if show_progress.wasCanceled():
                        break  # Người dùng hủy quét
                
                for inode_num in range(start_inode, end_inode):
                    try:
                        # Try to open the inode
                        f = fs_info.open_meta(inode=inode_num)
                        
                        if f and hasattr(f.info, 'meta') and f.info.meta:
                            meta = f.info.meta
                            
                            # Check if it's unallocated (deleted)
                            if hasattr(meta, 'flags') and (meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC):
                                # Try to get the actual file name from directory entries
                                name = None
                                path = "/$OrphanFiles"
                                
                                # Try to find name from parent directory entries
                                try:
                                    # Walk directory tree to find deleted entries with matching inode
                                    name = self.find_deleted_filename(fs_info, inode_num)
                                except:
                                    pass
                                
                                # If still no name, try from inode info
                                if not name and hasattr(f.info, 'name') and hasattr(f.info.name, 'name'):
                                    try:
                                        temp_name = f.info.name.name.decode('utf-8', errors='ignore')
                                        if temp_name and temp_name not in ['.', '..', '']:
                                            name = temp_name
                                    except:
                                        pass
                                
                                # Generate fallback name if needed
                                if not name or name in ['.', '..', '']:
                                    if hasattr(meta, 'type'):
                                        if meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                                            name = f"$OrphanDirectory_{inode_num}"
                                        else:
                                            # Try to guess extension from file content
                                            ext = self.guess_file_extension(f)
                                            name = f"$OrphanFile_{inode_num}{ext}"
                                    else:
                                        name = f"$Orphan_{inode_num}"
                                else:
                                    # For deleted files with recovered names, mark them clearly
                                    if not name.startswith('$'):
                                        # Keep original name but ensure it's clear it was deleted
                                        pass  # Name is already recovered
                                
                                # Skip . and ..
                                if name in ['.', '..']:
                                    continue
                                
                                # Determine file type from name or metadata
                                file_type = self.determine_file_type(name) if not name.startswith('$') else self.get_file_type_from_meta(meta)
                                
                                # Create file info
                                file_info = {
                                    'name': name,
                                    'size': meta.size if hasattr(meta, 'size') else 0,
                                    'type': file_type,
                                    'path': f"{path}/{name}",
                                    'created': self.format_timestamp(meta.crtime if hasattr(meta, 'crtime') else 0),
                                    'modified': self.format_timestamp(meta.mtime if hasattr(meta, 'mtime') else 0),
                                    'accessed': self.format_timestamp(meta.atime if hasattr(meta, 'atime') else 0),
                                    'changed': self.format_timestamp(meta.ctime if hasattr(meta, 'ctime') else 0),
                                    'deleted': True,
                                    'inode': inode_num,
                                    'entry': f,
                                    'fs_info': fs_info,
                                    'recoverable': True
                                }
                                
                                self.file_list.append(file_info)
                                deleted_count += 1
                        
                        checked_count += 1
                        
                    except Exception:
                        # Inode không tồn tại hoặc không thể đọc -> bỏ qua
                        pass
            
        except Exception as e:
            pass  # Lỗi không xác định khi quét inode -> bỏ qua
    
    def walk_deleted_entries(self, fs_info, progress=None):
        """Duyệt cây thư mục, tìm các entry có cờ UNALLOC (đã xóa) và thêm vào danh sách."""
        try:
            def scan_directory(directory, current_path="/", depth=0):
                if depth > 5:  # Limit depth
                    return
                
                try:
                    for entry in directory:
                        try:
                            # Check for deleted flag
                            if (hasattr(entry.info, 'meta') and entry.info.meta and 
                                hasattr(entry.info.meta, 'flags') and 
                                (entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)):
                                
                                file_info = self.extract_file_info_safe(entry, fs_info, current_path)
                                if file_info:
                                    file_info['deleted'] = True
                                    file_info['recoverable'] = True
                                    self.file_list.append(file_info)
                            
                            # Recurse into subdirectories
                            if (hasattr(entry.info, 'meta') and entry.info.meta and
                                hasattr(entry.info.meta, 'type') and
                                entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR and
                                entry.info.name.name not in [b'.', b'..']):
                                
                                try:
                                    name = entry.info.name.name.decode('utf-8', errors='ignore')
                                    new_path = f"{current_path.rstrip('/')}/{name}"
                                    sub_dir = fs_info.open_dir(inode=entry.info.meta.addr)
                                    scan_directory(sub_dir, new_path, depth + 1)
                                except:
                                    pass  # Mở thư mục con thất bại -> bỏ qua nhánh này
                                    
                        except:
                            continue
                            
                except Exception:
                    pass
            
            # Start from root
            root_dir = fs_info.open_dir(path="/")
            scan_directory(root_dir)
            
        except Exception as e:
            pass  # Lỗi khi walk hệ thống tệp -> bỏ qua (đã có phương pháp quét inode phụ trợ)
    
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
        """Cố gắng tìm lại tên gốc của tệp đã xóa thông qua entry thư mục trỏ tới inode tương ứng."""
        try:
            # Enhanced search for deleted file names
            found_names = []
            
            # Walk through all directories looking for deleted entries with matching inode
            def search_dir(directory, current_path="/", depth=0):
                if depth > 5:  # Increased search depth
                    return None
                
                try:
                    for entry in directory:
                        try:
                            # Check all entries (both allocated and unallocated)
                            if hasattr(entry.info, 'meta') and entry.info.meta:
                                # Check if this entry matches our inode
                                if (hasattr(entry.info.meta, 'addr') and 
                                    entry.info.meta.addr == inode_num):
                                    
                                    # Get the name regardless of allocation status
                                    if hasattr(entry.info, 'name') and hasattr(entry.info.name, 'name'):
                                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                                        if name and name not in ['.', '..', '']:
                                            # Check if it's deleted
                                            if hasattr(entry.info.meta, 'flags') and (entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC):
                                                return name  # Found deleted entry with name
                                            else:
                                                # Store allocated name as fallback
                                                found_names.append(name)
                            
                            # Also check name records even without matching inode (for NTFS MFT entries)
                            if hasattr(entry.info, 'name') and hasattr(entry.info.name, 'name'):
                                try:
                                    # Check if this name entry points to our inode
                                    if (hasattr(entry.info.name, 'meta_addr') and 
                                        entry.info.name.meta_addr == inode_num):
                                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                                        if name and name not in ['.', '..', '']:
                                            return name
                                except:
                                    pass
                            
                            # Recurse into subdirectories
                            if (hasattr(entry.info, 'meta') and entry.info.meta and
                                hasattr(entry.info.meta, 'type') and
                                entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR and
                                entry.info.name.name not in [b'.', b'..']):
                                
                                try:
                                    sub_dir = fs_info.open_dir(inode=entry.info.meta.addr)
                                    name = entry.info.name.name.decode('utf-8', errors='ignore')
                                    new_path = f"{current_path.rstrip('/')}/{name}" if current_path != "/" else f"/{name}"
                                    result = search_dir(sub_dir, new_path, depth + 1)
                                    if result:
                                        return result
                                except:
                                    pass
                        except:
                            continue
                except:
                    pass
                return None
            
            # Start search from root
            root_dir = fs_info.open_dir(path="/")
            result = search_dir(root_dir)
            
            # If no deleted name found, return any found allocated name
            if not result and found_names:
                return found_names[0]
            
            return result
            
        except Exception as e:
            return None
    
    def guess_file_extension(self, file_obj):
        """Phỏng đoán đuôi tệp dựa trên chữ ký đầu tệp (magic bytes) hoặc tính chất văn bản."""
        try:
            # Read first 512 bytes for signature detection
            content = b''
            if hasattr(file_obj, 'read_random'):
                content = file_obj.read_random(0, 512)
            
            if not content or len(content) < 4:
                return ""
            
            # Common file signatures (magic bytes)
            signatures = {
                # Images
                b'\xff\xd8\xff': '.jpg',
                b'\x89PNG': '.png',
                b'GIF87a': '.gif',
                b'GIF89a': '.gif',
                b'BM': '.bmp',
                b'II\x2a\x00': '.tiff',
                b'MM\x00\x2a': '.tiff',
                
                # Documents
                b'%PDF': '.pdf',
                b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': '.doc',  # MS Office
                b'PK\x03\x04': '.docx',  # Also .xlsx, .pptx (zip-based)
                b'{\\rtf': '.rtf',
                
                # Archives
                b'PK': '.zip',
                b'Rar!': '.rar',
                b'7z\xbc\xaf': '.7z',
                
                # Executables
                b'MZ': '.exe',
                
                # Media
                b'\x00\x00\x00\x20ftypmp4': '.mp4',
                b'\x00\x00\x00\x18ftypmp4': '.mp4',
                b'\x00\x00\x00\x14ftyp': '.mp4',
                b'RIFF': '.avi',  # Also .wav
                b'\x1a\x45\xdf\xa3': '.mkv',
                b'ID3': '.mp3',
                b'\xff\xfb': '.mp3',
                b'OggS': '.ogg',
            }
            
            # Check signatures
            for sig, ext in signatures.items():
                if content.startswith(sig):
                    return ext
            
            # Check for text files (mostly printable ASCII)
            try:
                text = content.decode('utf-8', errors='ignore')
                if sum(1 for c in text if c.isprintable() or c.isspace()) / len(text) > 0.9:
                    return '.txt'
            except:
                pass
            
            return ""
            
        except:
            return ""  # Không giải mã được chữ ký -> trả về rỗng
    
    def count_files_by_type(self, partitions):
        """Thống kê số lượng tệp theo loại để hiển thị ở mục `Views` (ảnh, video, audio, tài liệu, thực thi...)."""
        counts = {
            # Main categories
            'images': 0,
            'videos': 0,
            'audio': 0,
            'archives': 0,
            'databases': 0,
            # Document subcategories
            'html': 0,
            'office': 0,
            'pdf': 0,
            'plaintext': 0,
            'richtext': 0,
            # Executable subcategories
            'exe': 0,
            'dll': 0,
            'bat': 0,
            'cmd': 0,
            'com': 0,
            # Others
            'other': 0,
            'deleted': 0,
            'total': 0
        }
        
        # Detailed file type mappings
        type_extensions = {
            # By Extension categories
            'images': ['.jpg', '.jpeg', '.png', '.psd', '.nef', '.tiff', '.bmp', '.tec', '.tif', '.webp', '.gif', '.svg', '.ico'],
            'videos': ['.asf', '.3gp', '.asf', '.avi', '.m1v', '.m2v', '.m4v', '.mp4', '.mov', '.mpeg', '.mpg', '.mpe', '.mp4', '.rm', '.wmv', '.mpv', '.flv', '.swf', '.mkv', '.webm'],
            'audio': ['.aiff', '.aif', '.flac', '.wav', '.m3u', '.ape', '.wma', '.mp2', '.mp1', '.mp3', '.aac', '.mp4', '.m4a', '.m4p', '.m1a', '.m2a', '.mpa', '.mpa', '.mid', '.midi', '.ogg'],
            'archives': ['.zip', '.rar', '.7zip', '.7z', '.arj', '.tar', '.gzip', '.bzip', '.bzip2', '.cab', '.dar', '.cpio', '.ar', '.gz', '.tgz', '.bz2'],
            'databases': ['.db', '.db3', '.sqlite', '.sqlite3'],
            # Document subcategories
            'html': ['.htm', '.html'],
            'office': ['.doc', '.docx', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
            'pdf': ['.pdf'],
            'plaintext': ['.txt'],
            'richtext': ['.rtf'],
            # Executable subcategories
            'exe': ['.exe', '.msi'],
            'dll': ['.dll'],
            'bat': ['.bat'],
            'cmd': ['.cmd'],
            'com': ['.com', '.scr', '.ini', '.reg']
        }
        
        try:
            # Get filesystem info
            fs_info = None
            if partitions and partitions[0] is not None:
                # Multiple partitions - use first one for counting
                try:
                    offset = partitions[0].start * 512 if hasattr(partitions[0], 'start') else 0
                    fs_info = pytsk3.FS_Info(self.img_info, offset=offset)
                except:
                    pass
            else:
                # Single filesystem
                try:
                    fs_info = pytsk3.FS_Info(self.img_info)
                except:
                    pass
            
            if not fs_info:
                return counts
            
            # Quick scan to count files
            def scan_dir(directory, depth=0):
                if depth > 5:  # Limit depth for quick scan
                    return
                
                try:
                    for entry in directory:
                        try:
                            if entry.info.name.name in [b'.', b'..']:
                                continue
                            
                            if not hasattr(entry.info, 'meta') or entry.info.meta is None:
                                continue
                            
                            # Check if deleted
                            is_deleted = False
                            if hasattr(entry.info.meta, 'flags'):
                                is_deleted = bool(entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)
                            
                            if is_deleted:
                                counts['deleted'] += 1
                            
                            # Check if directory
                            if hasattr(entry.info.meta, 'type') and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                                # Recurse into subdirectory
                                if entry.info.name.name not in [b'.', b'..']:
                                    try:
                                        sub_dir = fs_info.open_dir(inode=entry.info.meta.addr)
                                        scan_dir(sub_dir, depth + 1)
                                    except:
                                        pass
                            else:
                                # It's a file - categorize it
                                name = entry.info.name.name.decode('utf-8', errors='ignore')
                                ext = os.path.splitext(name)[1].lower()
                                
                                categorized = False
                                for category, extensions in type_extensions.items():
                                    if ext in extensions:
                                        counts[category] += 1
                                        categorized = True
                                        break
                                
                                if not categorized:
                                    counts['other'] += 1
                                
                                counts['total'] += 1
                        except:
                            continue
                except:
                    pass
            
            # Start scan from root
            try:
                root_dir = fs_info.open_dir(path="/")
                scan_dir(root_dir)
            except:
                pass
            
        except Exception as e:
            pass
        
        return counts
    
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
