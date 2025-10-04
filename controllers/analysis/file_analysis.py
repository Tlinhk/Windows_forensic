import os
import mimetypes
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pytsk3

from views.pages.analysis_ui.file_analysis_ui import Ui_EvidenceAnalysisWidget


class FileAnalysis(QWidget):
    """File Analysis Widget - Forensic file system analysis tool"""
    
    # File type mappings
    FILE_TYPES = {
        '.txt': 'Text File', '.doc': 'Word Document', '.docx': 'Word Document',
        '.pdf': 'PDF Document', '.xls': 'Excel Spreadsheet', '.xlsx': 'Excel Spreadsheet',
        '.ppt': 'PowerPoint', '.pptx': 'PowerPoint',
        '.jpg': 'JPEG Image', '.jpeg': 'JPEG Image', '.png': 'PNG Image',
        '.gif': 'GIF Image', '.bmp': 'Bitmap Image', '.tiff': 'TIFF Image', '.tif': 'TIFF Image',
        '.webp': 'WebP Image', '.ico': 'Icon File', '.svg': 'SVG Image',
        '.mp4': 'MP4 Video', '.avi': 'AVI Video', '.mkv': 'MKV Video', '.mov': 'QuickTime Video',
        '.wmv': 'WMV Video', '.flv': 'Flash Video', '.webm': 'WebM Video',
        '.mp3': 'MP3 Audio', '.wav': 'WAV Audio', '.flac': 'FLAC Audio', '.aac': 'AAC Audio',
        '.ogg': 'OGG Audio', '.wma': 'WMA Audio', '.m4a': 'M4A Audio',
        '.zip': 'ZIP Archive', '.rar': 'RAR Archive', '.7z': '7-Zip Archive', '.tar': 'TAR Archive',
        '.gz': 'GZIP Archive', '.bz2': 'BZIP2 Archive', '.xz': 'XZ Archive',
        '.exe': 'Executable', '.dll': 'Dynamic Library', '.msi': 'Windows Installer',
        '.bat': 'Batch File', '.cmd': 'Command File', '.ps1': 'PowerShell Script',
        '.html': 'HTML File', '.htm': 'HTML File', '.css': 'CSS File', '.js': 'JavaScript File',
        '.json': 'JSON File', '.xml': 'XML File', '.csv': 'CSV File',
        '.log': 'Log File', '.ini': 'Configuration File', '.cfg': 'Configuration File',
        '.db': 'Database File', '.sqlite': 'SQLite Database', '.mdb': 'Access Database'
    }
    
    # File signatures for better detection
    FILE_SIGNATURES = {
        b'\xFF\xD8\xFF': ('.jpg', 'JPEG Image'),
        b'\x89PNG\r\n\x1a\n': ('.png', 'PNG Image'),
        b'GIF87a': ('.gif', 'GIF Image'),
        b'GIF89a': ('.gif', 'GIF Image'),
        b'BM': ('.bmp', 'Bitmap Image'),
        b'RIFF': ('.avi', 'AVI Video'),  # Could also be WAV
        b'\x00\x00\x00\x18ftypmp4': ('.mp4', 'MP4 Video'),
        b'\x00\x00\x00\x20ftypM4V': ('.m4v', 'M4V Video'),
        b'ID3': ('.mp3', 'MP3 Audio'),
        b'\xFF\xFB': ('.mp3', 'MP3 Audio'),
        b'RIFF': ('.wav', 'WAV Audio'),
        b'PK\x03\x04': ('.zip', 'ZIP Archive'),
        b'PK\x05\x06': ('.zip', 'ZIP Archive'),
        b'PK\x07\x08': ('.zip', 'ZIP Archive'),
        b'Rar!\x1a\x07\x00': ('.rar', 'RAR Archive'),
        b'Rar!\x1a\x07\x01\x00': ('.rar', 'RAR Archive'),
        b'7z\xbc\xaf\x27\x1c': ('.7z', '7-Zip Archive'),
        b'%PDF': ('.pdf', 'PDF Document'),
        b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': ('.doc', 'Office Document'),
        b'PK\x03\x04\x14\x00\x06\x00': ('.docx', 'Word Document'),
        b'MZ': ('.exe', 'Executable'),
        b'\x7fELF': ('.elf', 'ELF Executable'),
        b'SQLite format 3': ('.sqlite', 'SQLite Database')
    }
    
    # File categories for Views organization
    FILE_CATEGORIES = {
        'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.ico', '.svg'],
        'Videos': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'],
        'Audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'],
        'Documents': ['.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf'],
        'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'],
        'Executables': ['.exe', '.dll', '.msi', '.bat', '.cmd', '.ps1', '.com', '.scr'],
        'Web Files': ['.html', '.htm', '.css', '.js', '.json', '.xml', '.php', '.asp'],
        'Data Files': ['.csv', '.log', '.ini', '.cfg', '.db', '.sqlite', '.mdb', '.dat'],
        'System Files': ['.sys', '.drv', '.ocx', '.cpl', '.scr', '.tmp', '.bak']
    }
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.current_case_id = None
        self.current_evidence_path = None
        
        # Simplified data storage
        self.file_list = []
        self.original_file_list = []  # Store original file list for view switching
        self.all_files = []  # Store ALL files from entire filesystem
        self.timeline_data = []
        self.search_results = []
        self.img_info = None
        self.fs_info = None
        self.db_manager = None
        self.current_directory_path = "/"  # Track current directory
        self.filesystem_scanned = False  # Track if full scan is completed

        self.setup_ui()
        self.setup_connections()
        self.initialize_empty_state()

    def _detect_file_format(self, file_path):
        """Detect file format and return appropriate handler."""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            # Check by extension first (most reliable)
            if ext in ['.e01', '.ex01']:
                return pytsk3.Img_Info(file_path)
            elif ext in ['.dd', '.img', '.raw', '.001', '.002', '.003']:
                return pytsk3.Img_Info(file_path)
            else:
                # Try as raw image for unknown extensions
                return pytsk3.Img_Info(file_path)
                
        except Exception:
            raise Exception("Unsupported file format or corrupted image")

    def setup_ui(self):
        """Setup UI from Qt Designer file."""
        self.ui = Ui_EvidenceAnalysisWidget()
        self.ui.setupUi(self)
        self._configure_tables()
    
    def _configure_tables(self):
        """Configure table properties."""
        # File table - 8 columns
        if hasattr(self.ui, 'tableFiles'):
            self.ui.tableFiles.setEditTriggers(QAbstractItemView.NoEditTriggers)
            headers = ['Name', 'Size', 'Modified', 'Accessed', 'Created', 'MFT Modified', 'Type', 'Path']
            self.ui.tableFiles.setColumnCount(len(headers))
            for col, header in enumerate(headers):
                item = QTableWidgetItem(header)
                self.ui.tableFiles.setHorizontalHeaderItem(col, item)
            
            h = self.ui.tableFiles.horizontalHeader()
            h.setVisible(True)
            h.setSortIndicatorShown(True)
            h.setSectionsClickable(True)
            h.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
            h.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Size
            h.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Type

        # Timeline table - 5 columns
        if hasattr(self.ui, 'tableTimeline'):
            self.ui.tableTimeline.setEditTriggers(QAbstractItemView.NoEditTriggers)
            headers = ['Date/Time', 'Source', 'Type', 'Description', 'File/Artifact']
            self.ui.tableTimeline.setColumnCount(len(headers))
            for col, header in enumerate(headers):
                item = QTableWidgetItem(header)
                self.ui.tableTimeline.setHorizontalHeaderItem(col, item)
            
            h = self.ui.tableTimeline.horizontalHeader()
            h.setVisible(True)
            h.setSortIndicatorShown(True)
            h.setSectionsClickable(True)
            h.setSectionResizeMode(3, QHeaderView.Stretch)  # Description

        # Search results table - 4 columns
        if hasattr(self.ui, 'tableSearchResults'):
            self.ui.tableSearchResults.setEditTriggers(QAbstractItemView.NoEditTriggers)
            headers = ['File Name', 'Path', 'Hits', 'Modified']
            self.ui.tableSearchResults.setColumnCount(len(headers))
            for col, header in enumerate(headers):
                item = QTableWidgetItem(header)
                self.ui.tableSearchResults.setHorizontalHeaderItem(col, item)
            
            h = self.ui.tableSearchResults.horizontalHeader()
            h.setVisible(True)
            h.setSortIndicatorShown(True)
            h.setSectionsClickable(True)
            h.setSectionResizeMode(1, QHeaderView.Stretch)  # Path

        # Metadata and Properties tables - 2 columns
        for table_name in ['tableMetadata', 'tableProperties']:
            if hasattr(self.ui, table_name):
                table = getattr(self.ui, table_name)
                table.setEditTriggers(QAbstractItemView.NoEditTriggers)
                headers = ['Property', 'Value']
                table.setColumnCount(len(headers))
                for col, header in enumerate(headers):
                    item = QTableWidgetItem(header)
                    table.setHorizontalHeaderItem(col, item)
                
                h = table.horizontalHeader()
                h.setVisible(True)
                h.setSectionResizeMode(1, QHeaderView.Stretch)  # Value column
        
        # Tree widget configuration
        if hasattr(self.ui, 'treeInvestigation'):
            self.ui.treeInvestigation.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.ui.treeInvestigation.setHeaderLabel("Data Sources")
            # Enable animated expansion for better UX
            self.ui.treeInvestigation.setAnimated(True)
            # Set uniform row heights for better performance
            self.ui.treeInvestigation.setUniformRowHeights(True)
    
    def setup_connections(self):
        """Connect UI signals to handlers."""
        connections = {
            'cmbEvidenceArtifacts': ('currentIndexChanged', self.on_evidence_artifact_changed),
            'btnLoadSelectedEvidence': ('clicked', self.load_selected_evidence_artifact),
            'btnRefreshEvidence': ('clicked', self.refresh_evidence_artifacts),
            'treeInvestigation': [('itemClicked', self.on_tree_item_clicked),
                                 ('itemExpanded', self.on_tree_item_expanded),
                                 ('itemDoubleClicked', self.on_tree_item_double_clicked)],
            'tableFiles': [('itemSelectionChanged', self.on_file_selected),
                          ('customContextMenuRequested', self.on_files_table_context_menu),
                          ('itemDoubleClicked', self.on_file_double_clicked)],
            'btnSearch': ('clicked', self.perform_search),
            'lineEditSearch': ('returnPressed', self.perform_search),
            'tableSearchResults': ('customContextMenuRequested', self.on_search_table_context_menu),
            'tableTimeline': ('itemSelectionChanged', self.on_timeline_selected),
        }
        
        for widget_name, signals in connections.items():
            if not hasattr(self.ui, widget_name):
                continue
            widget = getattr(self.ui, widget_name)
            if isinstance(signals, tuple):
                signals = [signals]
            for signal_name, handler in signals:
                getattr(widget, signal_name).connect(handler)
    
    def initialize_empty_state(self):
        """Clear all displays."""
        widgets_to_clear = ['treeInvestigation', 'tableFiles', 'tableTimeline',
                           'tableSearchResults', 'tableMetadata', 'tableProperties',
                           'textHexView', 'textContentView', 'labelPicture']

        for widget_name in widgets_to_clear:
            if hasattr(self.ui, widget_name):
                widget = getattr(self.ui, widget_name)
                if hasattr(widget, 'clear'):
                    widget.clear()
                elif hasattr(widget, 'setRowCount'):
                    widget.setRowCount(0)

        if hasattr(self.ui, 'labelCaseInfo'):
            self.ui.labelCaseInfo.setText("File Analysis - No evidence loaded")
        if hasattr(self.ui, 'btnLoadSelectedEvidence'):
            self.ui.btnLoadSelectedEvidence.setEnabled(False)
        
        # Ensure table headers are set
        self._configure_tables()

    
    
    def load_case_data(self, case_id):
        """Load case info and evidence artifacts."""
        self.current_case_id = case_id
        try:
            from models.db_manager import DatabaseManager
            self.db_manager = DatabaseManager()
            self.db_manager.connect()
            
            case_info = self.db_manager.get_case_with_investigator(case_id)
            if case_info and hasattr(self.ui, 'labelCaseInfo'):
                self.ui.labelCaseInfo.setText(f"File Analysis - Case: {case_info['title']} (ID: {case_id})")
            
            self.load_evidence_artifacts_from_case(self.db_manager)
            self.db_manager.disconnect()
        except Exception as e:
            if self.db_manager:
                self.db_manager.disconnect()
    
    def load_evidence_artifacts_from_case(self, db):
        """Load disk image artifacts from case."""
        if not hasattr(self.ui, 'cmbEvidenceArtifacts'):
            return
        
        self.ui.cmbEvidenceArtifacts.clear()
        self.ui.cmbEvidenceArtifacts.addItem("-- Chọn Evidence Artifact --", None)
        
        artifacts = db.get_artifacts_by_case(self.current_case_id)
        # Enhanced keywords for FTK Imager and forensic tools
        disk_keywords = [
            'DISK_IMAGE', 'DD', 'IMG', 'RAW', 'E01', 'FTK', 'TAR',
            '.DD', '.IMG', '.RAW', '.E01', '.TAR', '.001', '.002', '.003', '.004', '.005',
            'DISK', 'IMAGE', 'FORENSIC', 'EVIDENCE'
        ]

        evidence_artifacts = []
        for a in artifacts:
            # Check evidence type, name, and source path
            evidence_type = str(a.get('evidence_type', '')).upper()
            name = str(a.get('name', '')).upper()
            source_path = str(a.get('source_path', '')).upper()

            # Check if it matches any disk image keywords
            is_disk_image = any(
                kw in evidence_type or kw in name or kw in source_path
                for kw in disk_keywords
            )

            # Additional check for files without extension that might be disk images
            if not is_disk_image:
                filepath = a.get('source_path', '')
                if filepath:
                    filename = os.path.basename(filepath)
                    # Files without extension that are large might be disk images
                    try:
                        if not os.path.splitext(filename)[1] and os.path.getsize(filepath) > 50 * 1024 * 1024:  # > 50MB
                            is_disk_image = True
                    except:
                        pass

            if is_disk_image:
                evidence_artifacts.append(a)
        
        for artifact in evidence_artifacts:
            display = f"{artifact.get('name', 'Unknown')} ({artifact.get('evidence_type', 'Unknown')})"
            self.ui.cmbEvidenceArtifacts.addItem(display, artifact)
        
        if not evidence_artifacts:
            self.ui.cmbEvidenceArtifacts.addItem("Không có disk image artifacts", None)
    
    def on_evidence_artifact_changed(self, index):
        """Handle evidence selection."""
        if hasattr(self.ui, 'btnLoadSelectedEvidence'):
            data = self.ui.cmbEvidenceArtifacts.itemData(index) if hasattr(self.ui, 'cmbEvidenceArtifacts') else None
            self.ui.btnLoadSelectedEvidence.setEnabled(data is not None and index > 0)
    
    def load_selected_evidence_artifact(self):
        """Load selected evidence."""
        if not hasattr(self.ui, 'cmbEvidenceArtifacts'):
            return

        artifact = self.ui.cmbEvidenceArtifacts.currentData()
        if not artifact:
            QMessageBox.warning(self, "Chưa chọn Evidence", "Vui lòng chọn evidence artifact.")
            return

        path = artifact.get('source_path')
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File không tồn tại", f"File không tồn tại: {path}")
            return

        # Check file size before loading
        try:
            file_size = os.path.getsize(path)
            print(f"Loading evidence file: {path} ({self.format_size(file_size)})")

            # Warn for very large files
            if file_size > 10 * 1024 * 1024 * 1024:  # 10GB
                reply = QMessageBox.question(self, "Large File Warning",
                    f"File này khá lớn ({self.format_size(file_size)}).\n"
                    "Việc xử lý có thể mất nhiều thời gian. Bạn có muốn tiếp tục?",
                    QMessageBox.Yes | QMessageBox.No)

                if reply != QMessageBox.Yes:
                    return

        except Exception as e:
            QMessageBox.warning(self, "File Access Error", f"Không thể đọc file: {e}")
            return

        self.load_evidence_file(path)
    
    def refresh_evidence_artifacts(self):
        """Refresh evidence list."""
        if not self.current_case_id:
            return
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.connect()
            self.load_evidence_artifacts_from_case(db)
            db.disconnect()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi refresh: {str(e)}")
    
    def showEvent(self, event):
        """Handle widget show - refresh if case changed."""
        super().showEvent(event)
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            main_case = self.main_window.current_case_id
            if main_case != self.current_case_id:
                QTimer.singleShot(100, lambda: self.load_case_data(main_case) if main_case else self.initialize_empty_state())
        
        if self.current_case_id:
            QTimer.singleShot(200, self.refresh_evidence_artifacts)
    
    def load_evidence_file(self, file_path):
        """Load and analyze disk image."""
        try:
            progress = QProgressDialog("Loading evidence...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            self.current_evidence_path = file_path
            file_name = os.path.basename(file_path)
            self.initialize_empty_state()

            if hasattr(self.ui, 'labelCaseInfo'):
                text = self.ui.labelCaseInfo.text()
                self.ui.labelCaseInfo.setText(f"{text} | Evidence: {file_name}" if "Case:" in text else f"File Analysis | Evidence: {file_name}")

            progress.setValue(10)
            QApplication.processEvents()

            # Check file exists and get basic info
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            progress.setValue(20)

            # Try to open the image file

            # Try to open the image
            try:
                self.img_info = self._detect_file_format(file_path)
                image_size = self.img_info.get_size()
            except Exception as e:
                raise Exception(f"Failed to open image file: {e}\n\n"
                              "This could be due to:\n"
                              "• Unsupported image format\n"
                              "• Corrupted or incomplete image\n"
                              "• Missing read permissions")

            progress.setValue(40)

            # Try to get volume information
            partitions = []
            try:
                volume_info = pytsk3.Volume_Info(self.img_info)
                partitions = list(volume_info)
            except Exception:
                partitions = [None]

            progress.setValue(60)
            self.build_evidence_tree(file_name, partitions)

            progress.setValue(60)

            # Try to load filesystem and populate tree
            if partitions and partitions[0]:
                try:
                    self.load_partition_root(partitions[0])
                except Exception as e:
                    print(f"Failed to load partition: {e}")
                    # Try single filesystem as fallback
                    try:
                        self.load_single_filesystem_root()
                    except Exception as e2:
                        print(f"Failed to load single filesystem: {e2}")
            else:
                try:
                    self.load_single_filesystem_root()
                except Exception as e:
                    print(f"Failed to load filesystem: {e}")

            progress.setValue(70)
            
            # Scan entire filesystem for all files (for views)
            if self.fs_info:
                progress.setLabelText("Scanning entire filesystem for file analysis...")
                self._scan_entire_filesystem(progress)
            
            progress.setValue(90)
            
            # Update view counts in tree
            self._update_view_counts()
            
            progress.setValue(100)
            progress.close()


            deleted = sum(1 for f in self.file_list if f.get('deleted'))
            QMessageBox.information(self, "Evidence Loaded",
                f"Evidence loaded!\n\nFile: {file_name}\n"
                f"Size: {self.format_size(image_size)}\n"
                f"Files: {len(self.file_list):,} ({deleted:,} deleted)")
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            print(f"Error in load_evidence_file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load evidence:\n{str(e)}")


    
    def build_evidence_tree(self, evidence_name, partitions):
        """Build evidence tree structure."""
        if not hasattr(self.ui, 'treeInvestigation'):
            return
        
        self.ui.treeInvestigation.clear()
        root = QTreeWidgetItem(self.ui.treeInvestigation, [evidence_name])
        root.setData(0, Qt.UserRole, {'type': 'evidence', 'path': self.current_evidence_path})
        root.setExpanded(True)

        # Add current path label if available
        if hasattr(self.ui, 'labelCurrentPath'):
            self.ui.labelCurrentPath.setText(f"Current: / (Root Directory)")
        
        if partitions and partitions[0]:
            for i, part in enumerate(partitions):
                self._add_partition_node(root, part, i)
        else:
            self._add_filesystem_node(root, None)
        
        # Add Views section with organized categories
        views = QTreeWidgetItem(self.ui.treeInvestigation, ["Views"])
        views.setExpanded(True)
        
        # File Type Categories
        file_types = QTreeWidgetItem(views, ["File Types"])
        file_types.setExpanded(True)
        
        # Add each file category
        for category, extensions in self.FILE_CATEGORIES.items():
            category_item = QTreeWidgetItem(file_types, [f"{category} (0)"])
            category_item.setData(0, Qt.UserRole, {
                'type': 'file_category', 
                'category': category,
                'extensions': extensions
            })
        
        # Special Views
        special_views = QTreeWidgetItem(views, ["Special Views"])
        special_views.setExpanded(True)
        
        # Deleted Files
        deleted_item = QTreeWidgetItem(special_views, [f"Deleted Files (0)"])
        deleted_item.setData(0, Qt.UserRole, {'type': 'deleted_files'})
        
        # Large Files (>10MB)
        large_files_item = QTreeWidgetItem(special_views, [f"Large Files (>10MB) (0)"])
        large_files_item.setData(0, Qt.UserRole, {'type': 'large_files', 'min_size': 10*1024*1024})
        
        # Recently Modified (last 30 days)
        recent_item = QTreeWidgetItem(special_views, [f"Recently Modified (0)"])
        recent_item.setData(0, Qt.UserRole, {'type': 'recent_files', 'days': 30})
        
        # Hidden Files
        hidden_item = QTreeWidgetItem(special_views, [f"Hidden Files (0)"])
        hidden_item.setData(0, Qt.UserRole, {'type': 'hidden_files'})
        
        # Suspicious Files
        suspicious_item = QTreeWidgetItem(special_views, [f"Suspicious Files (0)"])
        suspicious_item.setData(0, Qt.UserRole, {'type': 'suspicious_files'})
    
    def _add_partition_node(self, parent, partition, index):
        """Add partition node to tree."""
        try:
            desc = f"Partition {index+1}"
            if hasattr(partition, 'desc') and partition.desc:
                desc += f" ({partition.desc.decode('utf-8', errors='ignore').strip()})"
            desc += f" - {self.format_size(partition.len * 512 if hasattr(partition, 'len') else 0)}"
            
            part_item = QTreeWidgetItem(parent, [desc])
            part_item.setData(0, Qt.UserRole, {'type': 'partition', 'partition': partition, 'index': index})
            
            try:
                offset = partition.start * 512 if hasattr(partition, 'start') else 0
                fs_info = pytsk3.FS_Info(self.img_info, offset=offset)
                self._add_filesystem_node(part_item, partition, fs_info)
            except:
                pass
        except:
            pass
    
    def _add_filesystem_node(self, parent, partition, fs_info=None):
        """Add filesystem node to tree."""
        try:
            if not fs_info:
                fs_info = pytsk3.FS_Info(self.img_info)
            
            fs_type = fs_info.info.ftype_str if hasattr(fs_info.info, 'ftype_str') else "Unknown"
            fs_item = QTreeWidgetItem(parent, [f"File System ({fs_type})"])
            fs_item.setData(0, Qt.UserRole, {'type': 'filesystem', 'fs_info': fs_info, 'partition': partition})
            
            self._populate_root_directory(fs_item, fs_info)
        except:
            pass
    
    def _populate_root_directory(self, parent, fs_info):
        """Populate root directory with full subdirectory structure."""
        try:
            root_item = QTreeWidgetItem(parent, ["Root Directory"])
            root_item.setData(0, Qt.UserRole, {'type': 'directory', 'fs_info': fs_info, 'path': '/'})
            
            # Populate first level directories
            self._populate_directory_tree(root_item, fs_info, "/")
            
        except Exception as e:
            print(f"Error populating root directory: {e}")
            # Fallback: simple root directory
            root_item = QTreeWidgetItem(parent, ["Root Directory"])
            root_item.setData(0, Qt.UserRole, {'type': 'directory', 'fs_info': fs_info, 'path': '/'})
    
    def _populate_directory_tree(self, parent_item, fs_info, path, max_depth=3, current_depth=0):
        """Recursively populate directory tree structure."""
        if current_depth >= max_depth:
            return
            
        try:
            directory = fs_info.open_dir(path)
            subdirs = []
            
            # Get list of subdirectories
            for entry in list(directory)[:100]:  # Increased limit for better coverage
                try:
                    if entry.info.name.name in [b'.', b'..'] or not entry.info.meta:
                        continue
                    if entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                        if name and name not in ['.', '..']:
                            subdirs.append(name)
                except:
                    continue
            
            # Sort directories for better organization
            subdirs.sort()
            
            # Add subdirectories to tree (simplified, no deep checking)
            for i, subdir in enumerate(sorted(subdirs)[:30]):  # Reduced limit
                try:
                    sub_path = f"{path.rstrip('/')}/{subdir}"
                    sub_item = QTreeWidgetItem(parent_item, [subdir])
                    sub_item.setData(0, Qt.UserRole, {
                        'type': 'directory', 
                        'fs_info': fs_info, 
                        'path': sub_path,
                        'loaded': False
                    })
                    
                    # Always add dummy - we'll check when expanded
                    # This prevents the expensive check that causes freezing
                    dummy = QTreeWidgetItem(sub_item, ["Loading..."])
                    dummy.setData(0, Qt.UserRole, {'type': 'dummy'})
                    
                    # Process events periodically
                    if i % 10 == 0:
                        QApplication.processEvents()
                    
                except Exception as e:
                    print(f"Error adding directory {subdir}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error populating directory tree for {path}: {e}")
    
    def on_tree_item_expanded(self, item):
        """Handle tree item expansion - load subdirectories on demand."""
        data = item.data(0, Qt.UserRole)
        if not data or data.get('type') != 'directory':
            return

        # Check if already loaded
        if data.get('loaded', False):
            return
            
        fs_info = data.get('fs_info')
        path = data.get('path')
        if not fs_info or not path:
            return

        try:
            # Remove all existing children (including dummy)
            while item.childCount() > 0:
                item.removeChild(item.child(0))
            
            # Add loading indicator
            loading_item = QTreeWidgetItem(item, ["Loading..."])
            loading_item.setData(0, Qt.UserRole, {'type': 'loading'})
            
            # Process events to show loading indicator
            QApplication.processEvents()
            
            # Load subdirectories with limits to prevent freeze
            directory = fs_info.open_dir(path)
            subdirs = []
            count = 0

            for entry in directory:
                if count >= 30:  # Reduced limit to prevent freeze
                    break
                    
                try:
                    if entry.info.name.name in [b'.', b'..'] or not entry.info.meta:
                        continue
                    if entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                        if name and name not in ['.', '..']:
                            subdirs.append(name)
                            count += 1
                            
                            # Process events periodically to prevent freeze
                            if count % 10 == 0:
                                QApplication.processEvents()
                                
                except Exception:
                    continue

            # Remove loading indicator
            item.removeChild(loading_item)
            
            # Sort and add subdirectories to tree
            for i, subdir in enumerate(sorted(subdirs)[:20]):  # Further reduced limit
                try:
                    sub_path = f"{path.rstrip('/')}/{subdir}"
                    sub_item = QTreeWidgetItem(item, [subdir])
                    sub_item.setData(0, Qt.UserRole, {
                        'type': 'directory',
                        'fs_info': fs_info,
                        'path': sub_path,
                        'loaded': False
                    })
                    
                    # Simplified check - just add dummy for all directories
                    # We'll check when actually expanded
                    dummy = QTreeWidgetItem(sub_item, ["Loading..."])
                    dummy.setData(0, Qt.UserRole, {'type': 'dummy'})
                    
                    # Process events every few items
                    if i % 5 == 0:
                        QApplication.processEvents()
                        
                except Exception as e:
                    print(f"Error adding subdirectory {subdir}: {e}")
                    continue

            # Mark as loaded
            data['loaded'] = True
            item.setData(0, Qt.UserRole, data)
            
            # If no subdirectories found, show info
            if not subdirs:
                info_item = QTreeWidgetItem(item, ["(No subdirectories)"])
                info_item.setData(0, Qt.UserRole, {'type': 'info'})
            elif len(subdirs) > 20:
                # Show info if there are more directories
                more_item = QTreeWidgetItem(item, [f"... and {len(subdirs) - 20} more directories"])
                more_item.setData(0, Qt.UserRole, {'type': 'info'})

        except Exception as e:
            print(f"Error expanding directory {path}: {e}")
            # Remove loading indicator if still there
            if item.childCount() > 0 and item.child(0).data(0, Qt.UserRole) and item.child(0).data(0, Qt.UserRole).get('type') == 'loading':
                item.removeChild(item.child(0))
            # Add error indicator
            error_item = QTreeWidgetItem(item, [f"Error: {str(e)[:50]}..."])
            error_item.setData(0, Qt.UserRole, {'type': 'error'})
    
    def on_tree_item_clicked(self, item, column):
        """Handle tree item clicks."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        item_type = data.get('type')
        
        # Skip dummy, info, error, and loading items
        if item_type in ['dummy', 'info', 'error', 'loading']:
            return
            
        path = data.get('path', '/')

        # Update current path for breadcrumb
        if hasattr(self.ui, 'labelCurrentPath'):
            display_path = path if path != "/" else "/ (Root Directory)"
            self.ui.labelCurrentPath.setText(f"Current: {display_path}")

        handlers = {
            'filesystem': lambda: self.load_directory_files(data['fs_info'], '/'),
            'directory': lambda: self._handle_directory_click(data, path),
            'deleted_files': lambda: self.load_deleted_files(self._find_fs_info()),
            'partition': lambda: self.load_partition_root(data['partition']),
            'file_category': lambda: self._load_files_by_category(data['category'], data['extensions']),
            'large_files': lambda: self._load_large_files(data['min_size']),
            'recent_files': lambda: self._load_recent_files(data['days']),
            'hidden_files': lambda: self._load_hidden_files(),
            'suspicious_files': lambda: self._load_suspicious_files()
        }

        handler = handlers.get(item_type)
        if handler:
            try:
                handler()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error loading: {e}")
    
    def on_tree_item_double_clicked(self, item, column):
        """Handle tree item double clicks - expand/collapse or navigate."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return
            
        item_type = data.get('type')
        
        # For directories, toggle expansion (with confirmation for large directories)
        if item_type == 'directory':
            if not item.isExpanded():
                # Show cursor change to indicate loading
                self.setCursor(Qt.WaitCursor)
                try:
                    item.setExpanded(True)
                finally:
                    self.setCursor(Qt.ArrowCursor)
            else:
                item.setExpanded(False)
        else:
            # For other items, use single click behavior
            self.on_tree_item_clicked(item, column)

    def _handle_directory_click(self, data, path):
        """Handle directory click."""
        fs_info = data.get('fs_info')
        if fs_info:
            self.load_directory_files(fs_info, path)
    
    def _find_fs_info(self):
        """Find filesystem info from tree."""
        if not hasattr(self.ui, 'treeInvestigation'):
            return None
        
        root = self.ui.treeInvestigation.topLevelItem(0)
        if not root:
            return None
        
        for i in range(root.childCount()):
            data = root.child(i).data(0, Qt.UserRole)
            if data and data.get('type') == 'filesystem':
                return data['fs_info']
            
            for j in range(root.child(i).childCount()):
                data = root.child(i).child(j).data(0, Qt.UserRole)
                if data and data.get('type') == 'filesystem':
                    return data['fs_info']
        return None
    
    # ============================================================================
    # FILE LOADING & OPERATIONS
    # ============================================================================
    
    def load_partition_root(self, partition):
        """Load partition root directory."""
        try:
            offset = partition.start * 512 if hasattr(partition, 'start') else 0
            print(f"Loading partition at offset: {offset}")

            # Try different filesystem types
            fs_info = None
            try:
                fs_info = pytsk3.FS_Info(self.img_info, offset=offset)
                print(f"Filesystem type: {fs_info.info.ftype_str if hasattr(fs_info.info, 'ftype_str') else 'Unknown'}")
            except Exception as e:
                print(f"Failed to load filesystem at offset {offset}: {e}")
                # Try common offsets for different partition types
                for test_offset in [0, 63*512, 2048*512]:
                    if test_offset != offset:
                        try:
                            fs_info = pytsk3.FS_Info(self.img_info, offset=test_offset)
                            print(f"Success with offset {test_offset}")
                            break
                        except:
                            continue

            if fs_info:
                self.load_directory_files(fs_info, "/")
            else:
                print("No valid filesystem found in partition")
        except Exception as e:
            print(f"Error loading partition root: {e}")
    
    def load_single_filesystem_root(self):
        """Load single filesystem root."""
        try:
            # Try different offsets for single filesystem images
            offsets_to_try = [0, 63*512, 2048*512, 256*512]  # Common MBR/EBR offsets

            for offset in offsets_to_try:
                try:
                    print(f"Trying filesystem at offset: {offset}")
                    fs_info = pytsk3.FS_Info(self.img_info, offset=offset)
                    print(f"Success! Filesystem type: {fs_info.info.ftype_str if hasattr(fs_info.info, 'ftype_str') else 'Unknown'}")
                    self.load_directory_files(fs_info, "/")
                    return
                except Exception as e:
                    print(f"Failed at offset {offset}: {e}")
                    continue

            # If all offsets fail, try without offset (raw filesystem)
            try:
                print("Trying raw filesystem without offset")
                fs_info = pytsk3.FS_Info(self.img_info)
                self.load_directory_files(fs_info, "/")
            except Exception as e:
                print(f"Raw filesystem also failed: {e}")
                QMessageBox.warning(self, "Filesystem Error",
                    "Could not detect filesystem. The image may be:\n"
                    "• Encrypted or corrupted\n"
                    "• Using an unsupported filesystem type\n"
                    "• A disk with no valid partitions")

        except Exception as e:
            print(f"Error in load_single_filesystem_root: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load filesystem:\n{str(e)}")
    
    def load_directory_files(self, fs_info, path="/"):
        """Load files from directory."""
        try:
            self.fs_info = fs_info
            self.current_directory_path = path

            print(f"Loading directory: {path}")

            # Load files from directory with progress feedback
            self.file_list = []
            self.current_directory_path = path
            
            # Update current path label
            if hasattr(self.ui, 'labelCurrentPath'):
                if path != "/":
                    parent_path = "/".join(path.rstrip('/').split('/')[:-1]) or "/"
                    self.ui.labelCurrentPath.setText(f"Current: {path}")
                    
                    # Add '..' entry for back navigation (only in table, not tree)
                    back_info = {
                        'name': '..',
                        'size': 0,
                        'type': 'Directory',
                        'path': parent_path,
                        'created': 'N/A',
                        'modified': 'N/A',
                        'accessed': 'N/A',
                        'changed': 'N/A',
                        'deleted': False,
                        'inode': 'N/A',
                        'entry': None,
                        'fs_info': fs_info
                    }
                    self.file_list.insert(0, back_info)
                else:
                    self.ui.labelCurrentPath.setText(f"Current: {path}")
            
            # Load directory with limits to prevent freeze
            directory = fs_info.open_dir(path)
            count = 0

            for entry in directory:
                if count >= 1000:  # Limit to prevent freeze
                    break
                    
                if entry.info.name.name in [b'.', b'..']:
                    continue

                try:
                    file_info = self._extract_file_info(entry, fs_info, path)
                    if file_info:
                        self.file_list.append(file_info)
                        count += 1
                        
                        # Process events periodically
                        if count % 100 == 0:
                            QApplication.processEvents()
                            
                except Exception:
                    continue

            # Sort files (directories first)
            self.file_list.sort(key=lambda x: (x['type'] != 'Directory', x['name'].lower()))
            
            # Store original file list for view switching
            self.original_file_list = self.file_list.copy()
            
            self.update_file_table()
            self.generate_timeline()
            
            # Show info if there are more files
            if count >= 1000:
                if hasattr(self.ui, 'labelCurrentPath'):
                    current_text = self.ui.labelCurrentPath.text()
                    self.ui.labelCurrentPath.setText(f"{current_text} (showing first 1000 items)")

        except Exception as e:
            print(f"Error loading directory {path}: {e}")
            QMessageBox.warning(self, "Error", f"Error loading directory {path}:\n{str(e)}")

            # Try to continue with empty file list
            self.file_list = []
            self.update_file_table()
    
    def _scan_entire_filesystem(self, progress=None):
        """Scan entire filesystem to collect all files for views."""
        if not self.fs_info:
            return
        
        try:
            print("Starting full filesystem scan...")
            self.all_files = []
            scanned_count = 0
            
            # Recursive scan function
            def scan_directory_recursive(path, depth=0, max_depth=10):
                nonlocal scanned_count
                
                # Prevent infinite recursion and too deep scanning
                if depth > max_depth:
                    return
                
                try:
                    directory = self.fs_info.open_dir(path)
                    
                    for entry in directory:
                        # Update progress periodically
                        if progress and scanned_count % 100 == 0:
                            progress.setValue(70 + min(15, scanned_count // 1000))
                            progress.setLabelText(f"Scanning filesystem... ({scanned_count:,} files found)")
                            QApplication.processEvents()
                        
                        # Skip current and parent directory entries
                        if entry.info.name.name in [b'.', b'..']:
                            continue
                        
                        try:
                            if not entry.info.meta:
                                continue
                            
                            file_info = self._extract_file_info(entry, self.fs_info, path)
                            if file_info:
                                self.all_files.append(file_info)
                                scanned_count += 1
                                
                                # If it's a directory, scan it recursively
                                if file_info['type'] == 'Directory' and file_info['name'] not in ['.', '..']:
                                    subdir_path = file_info['path']
                                    scan_directory_recursive(subdir_path, depth + 1, max_depth)
                                
                        except Exception as e:
                            # Skip problematic entries
                            continue
                            
                        # Limit total files to prevent memory issues
                        if scanned_count >= 50000:  # Limit to 50k files
                            print(f"Reached file limit ({scanned_count:,}), stopping scan")
                            return
                            
                except Exception as e:
                    print(f"Error scanning directory {path}: {e}")
                    return
            
            # Start scanning from root
            scan_directory_recursive("/", 0, 8)  # Reduced max depth for performance
            
            # Also scan for deleted files
            if progress:
                progress.setLabelText("Scanning for deleted files...")
                QApplication.processEvents()
            
            self._scan_deleted_files_for_views()
            
            self.filesystem_scanned = True
            print(f"Filesystem scan completed. Found {len(self.all_files):,} total files")
            
        except Exception as e:
            print(f"Error in full filesystem scan: {e}")
            self.filesystem_scanned = False
    
    def _scan_deleted_files_for_views(self):
        """Scan for deleted files and add to all_files."""
        try:
            if not self.fs_info:
                return
            
            # Scan unallocated inodes (limited for performance)
            first = self.fs_info.info.first_inum if hasattr(self.fs_info.info, 'first_inum') else 0
            last = self.fs_info.info.last_inum if hasattr(self.fs_info.info, 'last_inum') else 10000
            limit = min(last, first + 2000)  # Reduced limit for performance
            
            deleted_count = 0
            for inode in range(first, limit):
                try:
                    meta_obj = self.fs_info.open_meta(inode=inode)
                    if not meta_obj or not meta_obj.info.meta:
                        continue
                    
                    if meta_obj.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC:
                        name = self._recover_filename(self.fs_info, inode, meta_obj)
                        file_info = {
                            'name': name,
                            'size': meta_obj.info.meta.size if hasattr(meta_obj.info.meta, 'size') else 0,
                            'type': self._get_file_type(name),
                            'path': f"/$OrphanFiles/{name}",
                            'created': self._format_time(meta_obj.info.meta.crtime if hasattr(meta_obj.info.meta, 'crtime') else 0),
                            'modified': self._format_time(meta_obj.info.meta.mtime if hasattr(meta_obj.info.meta, 'mtime') else 0),
                            'accessed': self._format_time(meta_obj.info.meta.atime if hasattr(meta_obj.info.meta, 'atime') else 0),
                            'changed': self._format_time(meta_obj.info.meta.ctime if hasattr(meta_obj.info.meta, 'ctime') else 0),
                            'deleted': True,
                            'inode': inode,
                            'entry': meta_obj,
                            'fs_info': self.fs_info
                        }
                        self.all_files.append(file_info)
                        deleted_count += 1
                        
                        # Limit deleted files for performance
                        if deleted_count >= 1000:
                            break
                            
                except Exception:
                    continue
                    
            print(f"Found {deleted_count} deleted files")
            
        except Exception as e:
            print(f"Error scanning deleted files: {e}")
    
    def load_deleted_files(self, fs_info):
        """Load deleted files from all_files or scan if needed."""
        if not self.filesystem_scanned:
            QMessageBox.information(self, "Scanning in Progress", 
                "Filesystem scan not completed yet. Please wait for the scan to finish.")
            return
        
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files found. Please load evidence first.")
            return
        
        try:
            # Filter deleted files from all_files
            deleted_files = [f for f in self.all_files if f.get('deleted', False)]
            
            self.file_list = deleted_files
            self.update_file_table()
            
            # Update path label
            if hasattr(self.ui, 'labelCurrentPath'):
                self.ui.labelCurrentPath.setText(f"View: Deleted Files ({len(deleted_files)} files)")
            
            if deleted_files:
                QMessageBox.information(self, "Deleted Files", 
                    f"Found {len(deleted_files)} deleted files from entire filesystem.")
            else:
                QMessageBox.information(self, "No Deleted Files", 
                    "No deleted files found in the filesystem.")
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading deleted files: {e}")
    
    def _load_files_by_category(self, category, extensions):
        """Load files by category (Images, Videos, etc.)."""
        if not self.filesystem_scanned:
            QMessageBox.information(self, "Scanning in Progress", 
                "Filesystem scan not completed yet. Please wait for the scan to finish.")
            return
        
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files found. Please load evidence first.")
            return
        
        try:
            # Filter files by category from all_files
            filtered_files = []
            for file_info in self.all_files:
                if file_info['type'] == 'Directory':
                    continue
                    
                # Check by extension
                ext = os.path.splitext(file_info['name'])[1].lower()
                if ext in extensions:
                    filtered_files.append(file_info)
                    continue
                
                # Check by file signature if available (for files without proper extensions)
                if file_info.get('entry'):
                    try:
                        content = self._extract_file_content(file_info, max_size=32, as_text=False)
                        if content:
                            for sig, (sig_ext, _) in self.FILE_SIGNATURES.items():
                                if content.startswith(sig) and sig_ext in extensions:
                                    filtered_files.append(file_info)
                                    break
                    except:
                        pass
            
            # Sort by name for better organization
            filtered_files.sort(key=lambda x: x['name'].lower())
            
            # Update current display
            self.file_list = filtered_files
            self.update_file_table()
            
            # Update path label
            if hasattr(self.ui, 'labelCurrentPath'):
                self.ui.labelCurrentPath.setText(f"View: {category} ({len(filtered_files)} files)")
            
            # Show info message
            if filtered_files:
                QMessageBox.information(self, f"{category} Files", 
                    f"Found {len(filtered_files)} {category.lower()} files from entire filesystem.")
            else:
                QMessageBox.information(self, f"No {category} Files", 
                    f"No {category.lower()} files found in the filesystem.")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading {category} files: {e}")
    
    def _load_large_files(self, min_size):
        """Load files larger than specified size."""
        if not self.filesystem_scanned:
            QMessageBox.information(self, "Scanning in Progress", 
                "Filesystem scan not completed yet. Please wait for the scan to finish.")
            return
        
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files found. Please load evidence first.")
            return
        
        try:
            filtered_files = [f for f in self.all_files 
                            if f['type'] != 'Directory' and f['size'] >= min_size]
            
            # Sort by size (largest first)
            filtered_files.sort(key=lambda x: x['size'], reverse=True)
            
            self.file_list = filtered_files
            self.update_file_table()
            
            if hasattr(self.ui, 'labelCurrentPath'):
                size_str = self.format_size(min_size)
                self.ui.labelCurrentPath.setText(f"View: Large Files (>{size_str}) ({len(filtered_files)} files)")
            
            if filtered_files:
                QMessageBox.information(self, "Large Files", 
                    f"Found {len(filtered_files)} files larger than {self.format_size(min_size)} from entire filesystem.")
            else:
                QMessageBox.information(self, "No Large Files", 
                    f"No files larger than {self.format_size(min_size)} found in the filesystem.")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading large files: {e}")
    
    def _load_recent_files(self, days):
        """Load recently modified files."""
        if not self.filesystem_scanned:
            QMessageBox.information(self, "Scanning in Progress", 
                "Filesystem scan not completed yet. Please wait for the scan to finish.")
            return
        
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files found. Please load evidence first.")
            return
        
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            filtered_files = []
            for file_info in self.all_files:
                if file_info['type'] == 'Directory':
                    continue
                    
                try:
                    if file_info['modified'] != 'Unknown':
                        mod_date = datetime.strptime(file_info['modified'], '%Y-%m-%d %H:%M:%S')
                        if mod_date >= cutoff_date:
                            filtered_files.append(file_info)
                except:
                    continue
            
            # Sort by modification date (newest first)
            filtered_files.sort(key=lambda x: x['modified'], reverse=True)
            
            self.file_list = filtered_files
            self.update_file_table()
            
            if hasattr(self.ui, 'labelCurrentPath'):
                self.ui.labelCurrentPath.setText(f"View: Recently Modified (last {days} days) ({len(filtered_files)} files)")
            
            if filtered_files:
                QMessageBox.information(self, "Recent Files", 
                    f"Found {len(filtered_files)} files modified in the last {days} days from entire filesystem.")
            else:
                QMessageBox.information(self, "No Recent Files", 
                    f"No files modified in the last {days} days found in the filesystem.")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading recent files: {e}")
    
    def _load_hidden_files(self):
        """Load hidden files (starting with dot or with hidden attributes)."""
        if not self.filesystem_scanned:
            QMessageBox.information(self, "Scanning in Progress", 
                "Filesystem scan not completed yet. Please wait for the scan to finish.")
            return
        
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files found. Please load evidence first.")
            return
        
        try:
            filtered_files = []
            for file_info in self.all_files:
                # Check if filename starts with dot (Unix hidden files)
                if file_info['name'].startswith('.') and file_info['name'] not in ['.', '..']:
                    filtered_files.append(file_info)
                    continue
                
                # Check for Windows hidden attribute (if available in entry metadata)
                try:
                    entry = file_info.get('entry')
                    if entry and hasattr(entry.info, 'meta') and hasattr(entry.info.meta, 'flags'):
                        # Check for hidden flag (this is filesystem dependent)
                        if entry.info.meta.flags & 0x02:  # Hidden attribute
                            filtered_files.append(file_info)
                except:
                    pass
            
            self.file_list = filtered_files
            self.update_file_table()
            
            if hasattr(self.ui, 'labelCurrentPath'):
                self.ui.labelCurrentPath.setText(f"View: Hidden Files ({len(filtered_files)} files)")
            
            if filtered_files:
                QMessageBox.information(self, "Hidden Files", 
                    f"Found {len(filtered_files)} hidden files from entire filesystem.")
            else:
                QMessageBox.information(self, "No Hidden Files", 
                    "No hidden files found in the filesystem.")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading hidden files: {e}")
    
    def _load_suspicious_files(self):
        """Load potentially suspicious files."""
        if not self.filesystem_scanned:
            QMessageBox.information(self, "Scanning in Progress", 
                "Filesystem scan not completed yet. Please wait for the scan to finish.")
            return
        
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files found. Please load evidence first.")
            return
        
        try:
            suspicious_patterns = [
                # Suspicious extensions
                '.scr', '.pif', '.com', '.bat', '.cmd', '.vbs', '.js', '.jar',
                # Double extensions
                '.pdf.exe', '.doc.exe', '.jpg.exe', '.txt.exe',
                # No extension executables
                'svchost', 'winlogon', 'explorer', 'lsass', 'csrss'
            ]
            
            suspicious_names = [
                'autorun.inf', 'desktop.ini', 'thumbs.db', 'pagefile.sys',
                'hiberfil.sys', 'swapfile.sys', '$recycle.bin'
            ]
            
            filtered_files = []
            for file_info in self.all_files:
                if file_info['type'] == 'Directory':
                    continue
                
                name_lower = file_info['name'].lower()
                
                # Check suspicious patterns
                is_suspicious = False
                
                # Check extensions and double extensions
                for pattern in suspicious_patterns:
                    if name_lower.endswith(pattern.lower()):
                        is_suspicious = True
                        break
                
                # Check suspicious names
                if name_lower in [n.lower() for n in suspicious_names]:
                    is_suspicious = True
                
                # Check for executable files with misleading extensions
                if file_info.get('entry'):
                    try:
                        content = self._extract_file_content(file_info, max_size=32, as_text=False)
                        if content and content.startswith(b'MZ'):  # PE executable signature
                            ext = os.path.splitext(name_lower)[1]
                            if ext not in ['.exe', '.dll', '.sys', '.scr', '.com']:
                                is_suspicious = True
                    except:
                        pass
                
                # Check for very large files with common extensions
                if file_info['size'] > 100 * 1024 * 1024:  # >100MB
                    ext = os.path.splitext(name_lower)[1]
                    if ext in ['.txt', '.log', '.ini', '.cfg']:
                        is_suspicious = True
                
                if is_suspicious:
                    filtered_files.append(file_info)
            
            self.file_list = filtered_files
            self.update_file_table()
            
            if hasattr(self.ui, 'labelCurrentPath'):
                self.ui.labelCurrentPath.setText(f"View: Suspicious Files ({len(filtered_files)} files)")
            
            if filtered_files:
                QMessageBox.information(self, "Suspicious Files", 
                    f"Found {len(filtered_files)} potentially suspicious files from entire filesystem.")
            else:
                QMessageBox.information(self, "No Suspicious Files", 
                    "No suspicious files found in the filesystem.")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading suspicious files: {e}")
    
    
    def _extract_file_info(self, entry, fs_info, path):
        """Extract file information from entry."""
        try:
            if not entry.info.meta:
                return None
            
            name = entry.info.name.name.decode('utf-8', errors='ignore')
            if not name or name in ['.', '..']:
                return None
            
            full_path = f"/{name}" if path == "/" else f"{path.rstrip('/')}/{name}"
            is_dir = entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR
            is_deleted = bool(entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC) if hasattr(entry.info.meta, 'flags') else False
            
            return {
                'name': name,
                'size': entry.info.meta.size if hasattr(entry.info.meta, 'size') else 0,
                'type': 'Directory' if is_dir else self._get_file_type(name),
                'path': full_path,
                'created': self._format_time(entry.info.meta.crtime if hasattr(entry.info.meta, 'crtime') else 0),
                'modified': self._format_time(entry.info.meta.mtime if hasattr(entry.info.meta, 'mtime') else 0),
                'accessed': self._format_time(entry.info.meta.atime if hasattr(entry.info.meta, 'atime') else 0),
                'changed': self._format_time(entry.info.meta.ctime if hasattr(entry.info.meta, 'ctime') else 0),
                'deleted': is_deleted,
                'inode': entry.info.meta.addr if hasattr(entry.info.meta, 'addr') else 'Unknown',
                'entry': entry,
                'fs_info': fs_info
            }
        except:
            return None
    
    def _get_file_type(self, filename, content=None):
        """Unified file type detection."""
        # Try extension first
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.FILE_TYPES:
            return self.FILE_TYPES[ext]
        
        # Try signature if content provided
        if content:
            for sig, (_, type_name) in self.FILE_SIGNATURES.items():
                if content.startswith(sig):
                    return type_name
        
        # Try MIME type as fallback
        try:
            mime_type, _ = mimetypes.guess_type(filename)
            if mime_type:
                if mime_type.startswith('image/'):
                    return 'Image File'
                elif mime_type.startswith('video/'):
                    return 'Video File'
                elif mime_type.startswith('audio/'):
                    return 'Audio File'
                elif mime_type.startswith('text/'):
                    return 'Text File'
                elif mime_type.startswith('application/'):
                    return 'Application File'
        except:
            pass
        
        return 'Unknown File'
    
    def _format_time(self, timestamp):
        """Format timestamp."""
        try:
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp > 0 else 'Unknown'
        except:
            return 'Unknown'
    
    def _scan_deleted_inodes(self, fs_info, progress=None):
        """Scan unallocated inodes for deleted files."""
        try:
            first = fs_info.info.first_inum if hasattr(fs_info.info, 'first_inum') else 0
            last = fs_info.info.last_inum if hasattr(fs_info.info, 'last_inum') else 10000
            limit = min(last, first + 5000)
            
            for inode in range(first, limit):
                try:
                    meta_obj = fs_info.open_meta(inode=inode)
                    if not meta_obj or not meta_obj.info.meta:
                        continue
                    
                    if meta_obj.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC:
                        name = self._recover_filename(fs_info, inode, meta_obj)
                        self.file_list.append({
                            'name': name,
                            'size': meta_obj.info.meta.size if hasattr(meta_obj.info.meta, 'size') else 0,
                            'type': self._get_file_type(name),
                            'path': f"/$OrphanFiles/{name}",
                            'created': self._format_time(meta_obj.info.meta.crtime if hasattr(meta_obj.info.meta, 'crtime') else 0),
                            'modified': self._format_time(meta_obj.info.meta.mtime if hasattr(meta_obj.info.meta, 'mtime') else 0),
                            'accessed': self._format_time(meta_obj.info.meta.atime if hasattr(meta_obj.info.meta, 'atime') else 0),
                            'changed': self._format_time(meta_obj.info.meta.ctime if hasattr(meta_obj.info.meta, 'ctime') else 0),
                            'deleted': True,
                            'inode': inode,
                            'entry': meta_obj,
                            'fs_info': fs_info
                        })
                        
                        if progress and len(self.file_list) % 10 == 0:
                            progress.setValue(int((inode - first) / (limit - first) * 100))
                except:
                    continue
        except:
            pass
    
    def _walk_deleted_entries(self, fs_info, max_depth=3):
        """Walk directories for deleted entries."""
        def walk(path, depth):
            if depth >= max_depth:
                return
            try:
                directory = fs_info.open_dir(path)
                for entry in directory:
                    try:
                        if entry.info.name.name in [b'.', b'..'] or not entry.info.meta:
                            continue
                        
                        if entry.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC:
                            info = self._extract_file_info(entry, fs_info, path)
                            if info:
                                info['deleted'] = True
                                self.file_list.append(info)
                        elif entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                            name = entry.info.name.name.decode('utf-8', errors='ignore')
                            if name not in ['.', '..']:
                                walk(f"{path.rstrip('/')}/{name}", depth + 1)
                    except:
                        continue
            except:
                pass
        
        walk("/", 0)
    
    def _recover_filename(self, fs_info, inode, meta_obj):
        """Simple filename recovery."""
        # Try to find in directory entries
        for dir_path in ['/', '/Users', '/Documents']:
            try:
                directory = fs_info.open_dir(dir_path)
                for entry in directory:
                    try:
                        if entry.info.meta and entry.info.meta.addr == inode:
                            name = entry.info.name.name.decode('utf-8', errors='ignore')
                            if name not in ['.', '..']:
                                return name
                    except:
                        continue
            except:
                continue
        
        # Generate name from signature
        try:
            content = meta_obj.read_random(0, 32) if hasattr(meta_obj, 'read_random') else b''
            for sig, (ext, _) in self.FILE_SIGNATURES.items():
                if content.startswith(sig):
                    return f"deleted_{inode}{ext}"
        except:
            pass
        
        return f"deleted_file_{inode}"
    
    
    def _extract_file_content(self, file_info, max_size=50000, as_text=True):
        """Extract file content."""
        entry = file_info.get('entry')
        if not entry:
            return None
        
        try:
            # Try direct read first
            if hasattr(entry, 'read_random'):
                data = entry.read_random(0, max_size)
            else:
                return None
                
            if not data:
                return None
            
            if as_text:
                try:
                    return data.decode('utf-8', errors='ignore')
                except:
                    return f"Binary data ({len(data)} bytes)"
            
            return data
        except:
            return None
    
    
    def update_file_table(self):
        """Update file table."""
        if not hasattr(self.ui, 'tableFiles'):
            return

        # Use file_list for display
        display_files = self.file_list

        self.ui.tableFiles.setRowCount(len(display_files))

        for row, info in enumerate(display_files):
            items = [
                info['name'], self.format_size(info['size']), info['modified'],
                info['accessed'], info['created'], info['changed'],
                info['type'], info['path']
            ]
            for col, value in enumerate(items):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, info)
                if info.get('deleted'):
                    item.setBackground(QColor(255, 200, 200))
                    item.setToolTip("Deleted file")
                self.ui.tableFiles.setItem(row, col, item)
        
        # Update view counts when file table is updated
        self._update_view_counts()
    
    def on_file_selected(self):
        """Handle file selection."""
        if not hasattr(self.ui, 'tableFiles'):
            return
        row = self.ui.tableFiles.currentRow()
        display_files = self.file_list

        if 0 <= row < len(display_files):
            file_info = display_files[row]
            
            # For single click, just show file details (no navigation)
            # Navigation only happens in tree view or double-click
            self._show_file_details(file_info)
    
    def on_file_double_clicked(self, item):
        """Handle file table double clicks - navigate to directory or show file details."""
        row = self.ui.tableFiles.currentRow()
        if 0 <= row < len(self.file_list):
            file_info = self.file_list[row]
            
            # If it's a directory, navigate to it (only on double-click)
            if file_info.get('type') == 'Directory':
                dir_path = file_info.get('path', '/')
                if self.fs_info:
                    try:
                        self.load_directory_files(self.fs_info, dir_path)
                        # Also update tree selection if possible
                        self._sync_tree_with_path(dir_path)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Cannot open directory: {e}")
            else:
                # For files, show details in a separate window or expanded view
                self._show_file_details_expanded(file_info)
    
    def _show_file_details(self, info):
        """Show file details in tabs."""
        # Properties
        if hasattr(self.ui, 'tableProperties'):
            props = [
                ("File Name", info['name']), ("Size", self.format_size(info['size'])),
                ("Type", info['type']), ("Path", info['path']),
                ("Created", info['created']), ("Modified", info['modified']),
                ("Status", "DELETED" if info['deleted'] else "Active"),
                ("Inode", str(info['inode']))
            ]
            self.ui.tableProperties.setRowCount(len(props))
            for i, (k, v) in enumerate(props):
                self.ui.tableProperties.setItem(i, 0, QTableWidgetItem(k))
                self.ui.tableProperties.setItem(i, 1, QTableWidgetItem(v))
        
        # Metadata
        if hasattr(self.ui, 'tableMetadata'):
            meta = [
                ("MIME Type", mimetypes.guess_type(info['name'])[0] or "unknown"),
                ("Extension", os.path.splitext(info['name'])[1]),
                ("Size (bytes)", str(info['size'])),
                ("Is Deleted", "Yes" if info['deleted'] else "No")
            ]
            self.ui.tableMetadata.setRowCount(len(meta))
            for i, (k, v) in enumerate(meta):
                self.ui.tableMetadata.setItem(i, 0, QTableWidgetItem(k))
                self.ui.tableMetadata.setItem(i, 1, QTableWidgetItem(v))
        
        # Content
        if info['size'] > 1024 * 1024:
            if hasattr(self.ui, 'textContentView'):
                self.ui.textContentView.setText("File too large")
        elif info['size'] == 0:
            if hasattr(self.ui, 'textContentView'):
                self.ui.textContentView.setText("Empty file")
        else:
            text = self._extract_file_content(info, as_text=True)
            raw = self._extract_file_content(info, max_size=1000, as_text=False)

            if hasattr(self.ui, 'textContentView') and text:
                self.ui.textContentView.setText(text[:10000])

            if hasattr(self.ui, 'textHexView') and raw:
                self.ui.textHexView.setText(self._generate_hex_view(raw))

            # Image preview
            if hasattr(self.ui, 'labelPicture') and 'image' in info['type'].lower():
                raw_full = self._extract_file_content(info, max_size=5*1024*1024, as_text=False)
                if raw_full:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(raw_full):
                        self.ui.labelPicture.setPixmap(pixmap.scaled(400, 400, Qt.KeepAspectRatio))


    def _generate_hex_view(self, data):
        """Generate hex view."""
        if not data:
            return "No data"
        
        lines = ["Hex View", "=" * 80]
        for i in range(0, min(len(data), 1000), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk).ljust(48)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"{i:08x}  {hex_part}  {ascii_part}")
        return '\n'.join(lines)
    
    def generate_timeline(self):
        """Generate timeline from files."""
        self.timeline_data = [
            {
                'datetime': f['modified'], 'source': 'File System',
                'type': 'Modified', 'description': f"Modified: {f['name']}",
                'artifact': f['path']
            }
            for f in self.file_list[:50] if f['modified'] != 'Unknown'
        ]
        self.timeline_data.sort(key=lambda x: x['datetime'])
        
        if hasattr(self.ui, 'tableTimeline'):
            self.ui.tableTimeline.setRowCount(len(self.timeline_data))
            for i, e in enumerate(self.timeline_data):
                for j, v in enumerate([e['datetime'], e['source'], e['type'], e['description'], e['artifact']]):
                    self.ui.tableTimeline.setItem(i, j, QTableWidgetItem(v))
            
    
    def on_timeline_selected(self):
        """Show timeline event details."""
        if not hasattr(self.ui, 'tableTimeline'):
            return
        row = self.ui.tableTimeline.currentRow()
        if 0 <= row < len(self.timeline_data):
            e = self.timeline_data[row]
            QMessageBox.information(self, "Timeline Event",
                f"Time: {e['datetime']}\nSource: {e['source']}\n"
                f"Type: {e['type']}\nDescription: {e['description']}")
    
    def perform_search(self):
        """Search in files."""
        if not hasattr(self.ui, 'lineEditSearch'):
            return
        
        keyword = self.ui.lineEditSearch.text().strip()
        if not keyword:
            QMessageBox.warning(self, "Search", "Enter keyword")
            return
        
        self.search_results = [
            {'file_info': f, 'matches': f['name'].lower().count(keyword.lower()) + f['path'].lower().count(keyword.lower())}
            for f in self.file_list
            if keyword.lower() in f['name'].lower() or keyword.lower() in f['path'].lower()
        ]
        
        if hasattr(self.ui, 'tableSearchResults'):
            self.ui.tableSearchResults.setRowCount(len(self.search_results))
            for row, r in enumerate(self.search_results):
                info = r['file_info']
                items = [info['name'], info['path'], str(r['matches']), info['modified']]
                for col, val in enumerate(items):
                    item = QTableWidgetItem(val)
                    if col == 0:
                        item.setData(Qt.UserRole, info)
                    if info.get('deleted'):
                        item.setBackground(QColor(255, 200, 200))
                        item.setToolTip("Deleted file")
                    self.ui.tableSearchResults.setItem(row, col, item)
            
        
        if hasattr(self.ui, 'tabWorkArea'):
            self.ui.tabWorkArea.setCurrentIndex(2)
        
        QMessageBox.information(self, "Search", f"Found {len(self.search_results)} files")
    
    def on_files_table_context_menu(self, pos):
        self._show_context_menu(pos, 'tableFiles', self.file_list)
    
    def on_search_table_context_menu(self, pos):
        self._show_context_menu(pos, 'tableSearchResults', 
                                [r['file_info'] for r in self.search_results])
    
    def _show_context_menu(self, pos, table_name, file_list):
        """Unified context menu."""
        if not hasattr(self.ui, table_name):
            return
        
        table = getattr(self.ui, table_name)
        row = table.indexAt(pos).row()
        if row < 0 or row >= len(file_list):
            return
        
        info = file_list[row]
        menu = QMenu(self)
        
        actions = [
            ("View details", lambda: self._show_file_details_expanded(info)),
            ("Navigate to directory", lambda: self._navigate_to_directory(info), info.get('type') == 'Directory'),
            ("Copy path", lambda: QApplication.clipboard().setText(info['path'])),
            ("Export file", lambda: self._export_file(info)),
            ("Export directory (recursive)", lambda: self._export_directory(info), info.get('type') == 'Directory'),
            ("Recover", lambda: self._recover_file(info), info.get('deleted', False))
        ]
        
        for text, handler, *enabled in actions:
            action = QAction(text, self)
            action.triggered.connect(handler)
            if enabled:
                action.setEnabled(enabled[0])
            menu.addAction(action)
        
        menu.exec_(table.viewport().mapToGlobal(pos))
    
    def _export_file(self, info):
        """Export file content."""
        path, _ = QFileDialog.getSaveFileName(self, "Export", info['name'])
        if not path:
            return
        
        try:
            content = self._extract_file_content(info, max_size=10*1024*1024, as_text=False)
            if content:
                with open(path, 'wb') as f:
                    f.write(content)
                QMessageBox.information(self, "Export", f"Exported to:\n{path}")
            else:
                QMessageBox.warning(self, "Export", "No content to export")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def _recover_file(self, info):
        """Recover deleted file."""
        if not info.get('deleted'):
            QMessageBox.warning(self, "Recovery", "File is not deleted")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Recover", info['name'])
        if not path:
            return
        
        try:
            content = self._extract_file_content(info, max_size=100*1024*1024, as_text=False)
            if content:
                with open(path, 'wb') as f:
                    f.write(content)
                QMessageBox.information(self, "Recovery", 
                    f"File recovered!\nSaved to: {path}\nSize: {len(content)} bytes")
            else:
                QMessageBox.warning(self, "Recovery", 
                    "Could not recover content - may be overwritten")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Recovery failed: {e}")
    
    def _export_directory(self, info):
        """Export entire directory contents including subdirectories."""
        if info.get('type') != 'Directory':
            QMessageBox.warning(self, "Export", "Selected item is not a directory")
            return
        
        # Select output directory
        output_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not output_dir:
            return
        
        dir_path = info.get('path', '/')
        dir_name = info.get('name', 'exported_directory')
        
        # Create subdirectory for this export
        export_path = os.path.join(output_dir, dir_name)
        try:
            os.makedirs(export_path, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot create export directory: {e}")
            return
        
        try:
            # Get filesystem info
            fs_info = info.get('fs_info') or self.fs_info
            if not fs_info:
                QMessageBox.warning(self, "Error", "No filesystem information available")
                return
            
            # Progress dialog
            progress = QProgressDialog(f"Exporting directory: {dir_name}", "Cancel", 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setRange(0, 0)  # Indeterminate progress
            progress.show()
            
            exported_files = 0
            exported_dirs = 0
            
            # Recursive export function
            def export_recursive(current_path, current_export_path, depth=0):
                nonlocal exported_files, exported_dirs
                
                # Prevent infinite recursion
                if depth > 10:
                    return
                
                try:
                    directory = fs_info.open_dir(current_path)
                    
                    for entry in directory:
                        if progress.wasCanceled():
                            return
                            
                        if entry.info.name.name in [b'.', b'..']:
                            continue
                        
                        try:
                            name = entry.info.name.name.decode('utf-8', errors='ignore')
                            if not name:
                                continue
                            
                            # Create safe filename
                            safe_name = "".join(c for c in name if c.isalnum() or c in '._- ()')
                            if not safe_name:
                                safe_name = f"item_{exported_files + exported_dirs}"
                            
                            item_path = os.path.join(current_export_path, safe_name)
                            
                            # Update progress
                            progress.setLabelText(f"Exporting: {current_path}/{name}")
                            QApplication.processEvents()
                            
                            if entry.info.meta and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                                # It's a directory - create it and recurse
                                try:
                                    os.makedirs(item_path, exist_ok=True)
                                    exported_dirs += 1
                                    
                                    # Recursively export subdirectory
                                    sub_path = f"{current_path.rstrip('/')}/{name}"
                                    export_recursive(sub_path, item_path, depth + 1)
                                    
                                except Exception as e:
                                    print(f"Error creating directory {item_path}: {e}")
                                    continue
                            else:
                                # It's a file - extract and save
                                try:
                                    file_info = self._extract_file_info(entry, fs_info, current_path)
                                    if file_info:
                                        content = self._extract_file_content(file_info, max_size=100*1024*1024, as_text=False)
                                        if content:
                                            with open(item_path, 'wb') as f:
                                                f.write(content)
                                            exported_files += 1
                                        else:
                                            # Create empty file if no content
                                            with open(item_path, 'wb') as f:
                                                pass
                                            exported_files += 1
                                    
                                except Exception as e:
                                    print(f"Error exporting file {name}: {e}")
                                    continue
                                    
                        except Exception as e:
                            print(f"Error processing item {name}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error reading directory {current_path}: {e}")
                    return
            
            # Start recursive export
            export_recursive(dir_path, export_path)
            
            progress.close()
            
            if exported_files > 0 or exported_dirs > 0:
                QMessageBox.information(self, "Export Complete", 
                    f"Directory exported successfully!\n\n"
                    f"Location: {export_path}\n"
                    f"Files exported: {exported_files}\n"
                    f"Directories created: {exported_dirs}\n"
                    f"Total items: {exported_files + exported_dirs}")
            else:
                QMessageBox.warning(self, "Export", "No files or directories were exported")
                
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    
    def format_size(self, size):
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def _navigate_to_directory(self, info):
        """Navigate to directory (from context menu)."""
        if info.get('type') != 'Directory':
            return
            
        dir_path = info.get('path', '/')
        if self.fs_info:
            try:
                self.load_directory_files(self.fs_info, dir_path)
                self._sync_tree_with_path(dir_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Cannot open directory: {e}")
    
    def _show_file_details_expanded(self, file_info):
        """Show expanded file details in a dialog."""
        if not file_info:
            return
            
        # Create a detailed view dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"File Details: {file_info['name']}")
        dialog.setModal(True)
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # File information
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        
        details = [
            f"File Name: {file_info['name']}",
            f"Size: {self.format_size(file_info['size'])}",
            f"Type: {file_info['type']}",
            f"Path: {file_info['path']}",
            f"Created: {file_info['created']}",
            f"Modified: {file_info['modified']}",
            f"Accessed: {file_info['accessed']}",
            f"Status: {'DELETED' if file_info['deleted'] else 'Active'}",
            f"Inode: {file_info['inode']}",
            "",
            "File Content Preview:",
            "=" * 50
        ]
        
        # Add file content if available
        if file_info['size'] > 0 and file_info['size'] < 1024 * 1024:  # < 1MB
            content = self._extract_file_content(file_info, max_size=10000, as_text=True)
            if content:
                details.append(content[:5000])  # First 5000 chars
                if len(content) > 5000:
                    details.append("\n... (content truncated)")
            else:
                details.append("(No content available)")
        else:
            details.append("(File too large for preview)")
        
        info_text.setText("\n".join(details))
        layout.addWidget(info_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export File")
        export_btn.clicked.connect(lambda: self._export_file(file_info))
        button_layout.addWidget(export_btn)
        
        if file_info.get('deleted'):
            recover_btn = QPushButton("Recover File")
            recover_btn.clicked.connect(lambda: self._recover_file(file_info))
            button_layout.addWidget(recover_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def _sync_tree_with_path(self, path):
        """Try to sync tree selection with the given path."""
        if not hasattr(self.ui, 'treeInvestigation'):
            return
            
        try:
            # This is a simplified sync - could be enhanced
            # For now, just update the current path label
            if hasattr(self.ui, 'labelCurrentPath'):
                display_path = path if path != "/" else "/ (Root Directory)"
                self.ui.labelCurrentPath.setText(f"Current: {display_path}")
        except Exception as e:
            print(f"Error syncing tree with path {path}: {e}")
    
    
    def _update_view_counts(self):
        """Update file counts for all views in tree."""
        if not hasattr(self.ui, 'treeInvestigation'):
            return
        
        # Use all_files if available, otherwise use file_list
        files_to_count = self.all_files if self.filesystem_scanned and self.all_files else self.file_list
        if not files_to_count:
            return
            
        try:
            # Calculate counts for different categories
            counts = {
                'deleted': sum(1 for f in files_to_count if f.get('deleted', False)),
                'large': sum(1 for f in files_to_count if f['type'] != 'Directory' and f['size'] >= 10*1024*1024),
                'hidden': sum(1 for f in files_to_count if f['name'].startswith('.') and f['name'] not in ['.', '..']),
            }
            
            # Count files by category
            category_counts = {}
            for category, extensions in self.FILE_CATEGORIES.items():
                count = 0
                for file_info in files_to_count:
                    if file_info['type'] != 'Directory':
                        ext = os.path.splitext(file_info['name'])[1].lower()
                        if ext in extensions:
                            count += 1
                category_counts[category] = count
            
            # Count recent files (last 30 days)
            recent_count = 0
            try:
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=30)
                for file_info in files_to_count:
                    if file_info['type'] != 'Directory' and file_info['modified'] != 'Unknown':
                        try:
                            mod_date = datetime.strptime(file_info['modified'], '%Y-%m-%d %H:%M:%S')
                            if mod_date >= cutoff_date:
                                recent_count += 1
                        except:
                            pass
            except:
                pass
            
            # Update tree items
            root = self.ui.treeInvestigation.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.text(0) == "Views":
                    self._update_views_recursive(item, counts, category_counts, recent_count)
                    break
                    
        except Exception as e:
            print(f"Error updating view counts: {e}")
    
    def _update_views_recursive(self, item, counts, category_counts, recent_count):
        """Recursively update view counts."""
        try:
            for i in range(item.childCount()):
                child = item.child(i)
                text = child.text(0)
                data = child.data(0, Qt.UserRole)
                
                if not data:
                    # Check child items recursively
                    self._update_views_recursive(child, counts, category_counts, recent_count)
                    continue
                
                item_type = data.get('type')
                
                if item_type == 'file_category':
                    category = data.get('category')
                    if category in category_counts:
                        child.setText(0, f"{category} ({category_counts[category]})")
                        
                elif item_type == 'deleted_files':
                    child.setText(0, f"Deleted Files ({counts['deleted']})")
                    
                elif item_type == 'large_files':
                    child.setText(0, f"Large Files (>10MB) ({counts['large']})")
                    
                elif item_type == 'recent_files':
                    child.setText(0, f"Recently Modified ({recent_count})")
                    
                elif item_type == 'hidden_files':
                    child.setText(0, f"Hidden Files ({counts['hidden']})")
                    
                elif item_type == 'suspicious_files':
                    # Calculate suspicious files count
                    suspicious_count = self._count_suspicious_files()
                    child.setText(0, f"Suspicious Files ({suspicious_count})")
                
                # Recursively update child items
                self._update_views_recursive(child, counts, category_counts, recent_count)
                
        except Exception as e:
            print(f"Error in recursive view update: {e}")
    
    def _count_suspicious_files(self):
        """Count suspicious files."""
        try:
            # Use all_files if available, otherwise use file_list
            files_to_count = self.all_files if self.filesystem_scanned and self.all_files else self.file_list
            
            suspicious_patterns = [
                '.scr', '.pif', '.com', '.bat', '.cmd', '.vbs', '.js', '.jar'
            ]
            
            suspicious_names = [
                'autorun.inf', 'desktop.ini', 'thumbs.db', 'pagefile.sys',
                'hiberfil.sys', 'swapfile.sys', '$recycle.bin'
            ]
            
            count = 0
            for file_info in files_to_count:
                if file_info['type'] == 'Directory':
                    continue
                
                name_lower = file_info['name'].lower()
                
                # Check suspicious patterns
                for pattern in suspicious_patterns:
                    if name_lower.endswith(pattern.lower()):
                        count += 1
                        break
                else:
                    # Check suspicious names
                    if name_lower in [n.lower() for n in suspicious_names]:
                        count += 1
                    # Check for very large files with common extensions
                    elif file_info['size'] > 100 * 1024 * 1024:
                        ext = os.path.splitext(name_lower)[1]
                        if ext in ['.txt', '.log', '.ini', '.cfg']:
                            count += 1
            
            return count
        except:
            return 0