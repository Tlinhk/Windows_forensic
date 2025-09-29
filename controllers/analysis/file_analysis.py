import sys
import os
import mimetypes
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pytsk3

from views.pages.analysis_ui.file_analysis_ui import Ui_EvidenceAnalysisWidget


class FileAnalysis(QWidget):
    """
    File Analysis Widget - Forensic file system analysis tool
    
    Optimized version with reduced redundancy while maintaining full functionality
    """
    
    # File type mappings (class-level constant)
    FILE_TYPES = {
        '.txt': 'Text File', '.doc': 'Word Document', '.docx': 'Word Document',
        '.pdf': 'PDF Document', '.xls': 'Excel Spreadsheet', '.xlsx': 'Excel Spreadsheet',
        '.jpg': 'JPEG Image', '.jpeg': 'JPEG Image', '.png': 'PNG Image',
        '.gif': 'GIF Image', '.bmp': 'Bitmap Image', '.mp4': 'MP4 Video',
        '.avi': 'AVI Video', '.mp3': 'MP3 Audio', '.wav': 'WAV Audio',
        '.zip': 'ZIP Archive', '.rar': 'RAR Archive', '.exe': 'Executable'
    }
    
    # File signatures for type detection
    FILE_SIGNATURES = {
        b'\xff\xd8\xff': ('.jpg', 'JPEG Image'),
        b'\x89PNG': ('.png', 'PNG Image'),
        b'GIF8': ('.gif', 'GIF Image'),
        b'%PDF': ('.pdf', 'PDF Document'),
        b'PK\x03\x04': ('.zip', 'ZIP Archive'),
        b'MZ': ('.exe', 'Windows Executable'),
    }
    
    # ============================================================================
    # INITIALIZATION
    # ============================================================================
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.current_case_id = None
        self.current_evidence_path = None
        
        self.file_list = []
        self.timeline_data = []
        self.search_results = []
        self.img_info = None
        self.volume_info = None
        self.fs_info = None
        self.db_manager = None
        
        self.setup_ui()
        self.setup_connections()
        self.initialize_empty_state()
        
        if main_window and hasattr(main_window, 'current_case_id'):
            self.load_case_data(main_window.current_case_id)
    
    def setup_ui(self):
        """Setup UI from Qt Designer file."""
        self.ui = Ui_EvidenceAnalysisWidget()
        self.ui.setupUi(self)
        # retranslateUi is already called in setupUi, but headers are set there
        # So we DON'T need to set them again - just configure resize modes
        self._configure_tables()
    
    def _configure_tables(self):
        """Configure table properties and column resizing."""
        # Create a proper font for headers (fixes the QFont::setPointSize warning)
        header_font = QFont()
        header_font.setFamily("Segoe UI")
        header_font.setPointSize(10)
        header_font.setBold(True)

        # File table - 8 columns
        if hasattr(self.ui, 'tableFiles'):
            # NEVER call setSortingEnabled() - let it stay False as set in .ui
            self.ui.tableFiles.setEditTriggers(QAbstractItemView.NoEditTriggers)

            # Set headers properly - use item by item approach to avoid conflicts
            headers = ['Name', 'Size', 'Modified', 'Accessed', 'Created', 'MFT Modified', 'Type', 'Path']
            for col in range(min(len(headers), self.ui.tableFiles.columnCount())):
                item = self.ui.tableFiles.horizontalHeaderItem(col)
                if item is None:
                    item = QTableWidgetItem()
                    self.ui.tableFiles.setHorizontalHeaderItem(col, item)
                item.setText(headers[col])

            h = self.ui.tableFiles.horizontalHeader()
            h.setFont(header_font)
            h.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
            h.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Size
            h.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Type
            h.setVisible(True)
            # Enable click to sort
            h.setSortIndicatorShown(True)
            h.setSectionsClickable(True)

        # Timeline table - 5 columns
        if hasattr(self.ui, 'tableTimeline'):
            self.ui.tableTimeline.setEditTriggers(QAbstractItemView.NoEditTriggers)

            # Set headers properly - use item by item approach to avoid conflicts
            timeline_headers = ['Date/Time', 'Source', 'Type', 'Description', 'File/Artifact']
            for col in range(min(len(timeline_headers), self.ui.tableTimeline.columnCount())):
                item = self.ui.tableTimeline.horizontalHeaderItem(col)
                if item is None:
                    item = QTableWidgetItem()
                    self.ui.tableTimeline.setHorizontalHeaderItem(col, item)
                item.setText(timeline_headers[col])

            h = self.ui.tableTimeline.horizontalHeader()
            h.setFont(header_font)
            h.setSectionResizeMode(3, QHeaderView.Stretch)  # Description
            h.setVisible(True)
            h.setSortIndicatorShown(True)
            h.setSectionsClickable(True)

        # Search results table - 4 columns
        if hasattr(self.ui, 'tableSearchResults'):
            self.ui.tableSearchResults.setEditTriggers(QAbstractItemView.NoEditTriggers)

            # Set headers properly - use item by item approach to avoid conflicts
            search_headers = ['File Name', 'Path', 'Hits', 'Modified']
            for col in range(min(len(search_headers), self.ui.tableSearchResults.columnCount())):
                item = self.ui.tableSearchResults.horizontalHeaderItem(col)
                if item is None:
                    item = QTableWidgetItem()
                    self.ui.tableSearchResults.setHorizontalHeaderItem(col, item)
                item.setText(search_headers[col])

            h = self.ui.tableSearchResults.horizontalHeader()
            h.setFont(header_font)
            h.setSectionResizeMode(1, QHeaderView.Stretch)  # Path
            h.setVisible(True)
            h.setSortIndicatorShown(True)
            h.setSectionsClickable(True)

        # Metadata and Properties tables - 2 columns
        for table_name in ['tableMetadata', 'tableProperties']:
            if hasattr(self.ui, table_name):
                table = getattr(self.ui, table_name)
                table.setEditTriggers(QAbstractItemView.NoEditTriggers)

                # Set headers properly - use item by item approach to avoid conflicts
                headers = ['Property', 'Value']
                for col in range(min(len(headers), table.columnCount())):
                    item = table.horizontalHeaderItem(col)
                    if item is None:
                        item = QTableWidgetItem()
                        table.setHorizontalHeaderItem(col, item)
                    item.setText(headers[col])

                h = table.horizontalHeader()
                h.setFont(header_font)
                h.setSectionResizeMode(1, QHeaderView.Stretch)  # Value column
                h.setVisible(True)

        # Tree widget
        if hasattr(self.ui, 'treeInvestigation'):
            self.ui.treeInvestigation.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.ui.treeInvestigation.setHeaderLabel("Data Sources")
    
    def setup_connections(self):
        """Connect UI signals to handlers."""
        connections = {
            'cmbEvidenceArtifacts': ('currentIndexChanged', self.on_evidence_artifact_changed),
            'btnLoadSelectedEvidence': ('clicked', self.load_selected_evidence_artifact),
            'btnRefreshEvidence': ('clicked', self.refresh_evidence_artifacts),
            'treeInvestigation': [('itemClicked', self.on_tree_item_clicked),
                                 ('itemExpanded', self.on_tree_item_expanded)],
            'tableFiles': [('itemSelectionChanged', self.on_file_selected),
                          ('customContextMenuRequested', self.on_files_table_context_menu)],
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
                           'textHexView', 'textContentView', 'textAnalysisResults', 'labelPicture']

        for widget_name in widgets_to_clear:
            if hasattr(self.ui, widget_name):
                widget = getattr(self.ui, widget_name)
                if hasattr(widget, 'clear'):
                    widget.clear()
                elif hasattr(widget, 'setRowCount'):
                    widget.setRowCount(0)

        if hasattr(self.ui, 'treeInvestigation'):
            self.ui.treeInvestigation.setHeaderLabel("Data Sources")
        if hasattr(self.ui, 'labelCaseInfo'):
            self.ui.labelCaseInfo.setText("File Analysis - No evidence loaded")
        if hasattr(self.ui, 'btnLoadSelectedEvidence'):
            self.ui.btnLoadSelectedEvidence.setEnabled(False)

        # Ensure table headers are properly set even in empty state
        self.refresh_table_headers()

    def refresh_table_headers(self):
        """Refresh table headers to ensure they display correctly."""
        try:
            # Refresh file table headers
            if hasattr(self.ui, 'tableFiles'):
                headers = ['Name', 'Size', 'Modified', 'Accessed', 'Created', 'MFT Modified', 'Type', 'Path']
                for col in range(min(len(headers), self.ui.tableFiles.columnCount())):
                    item = self.ui.tableFiles.horizontalHeaderItem(col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.ui.tableFiles.setHorizontalHeaderItem(col, item)
                    item.setText(headers[col])

            # Refresh timeline table headers
            if hasattr(self.ui, 'tableTimeline'):
                timeline_headers = ['Date/Time', 'Source', 'Type', 'Description', 'File/Artifact']
                for col in range(min(len(timeline_headers), self.ui.tableTimeline.columnCount())):
                    item = self.ui.tableTimeline.horizontalHeaderItem(col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.ui.tableTimeline.setHorizontalHeaderItem(col, item)
                    item.setText(timeline_headers[col])

            # Refresh search results table headers
            if hasattr(self.ui, 'tableSearchResults'):
                search_headers = ['File Name', 'Path', 'Hits', 'Modified']
                for col in range(min(len(search_headers), self.ui.tableSearchResults.columnCount())):
                    item = self.ui.tableSearchResults.horizontalHeaderItem(col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.ui.tableSearchResults.setHorizontalHeaderItem(col, item)
                    item.setText(search_headers[col])

            # Refresh metadata and properties table headers
            for table_name in ['tableMetadata', 'tableProperties']:
                if hasattr(self.ui, table_name):
                    table = getattr(self.ui, table_name)
                    meta_headers = ['Property', 'Value']
                    for col in range(min(len(meta_headers), table.columnCount())):
                        item = table.horizontalHeaderItem(col)
                        if item is None:
                            item = QTableWidgetItem()
                            table.setHorizontalHeaderItem(col, item)
                        item.setText(meta_headers[col])

        except Exception as e:
            print(f"Error refreshing table headers: {e}")
    
    # ============================================================================
    # CASE & EVIDENCE MANAGEMENT
    # ============================================================================
    
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
        disk_keywords = ['DISK_IMAGE', 'DD', 'IMG', 'RAW', 'E01', '.DD', '.IMG', '.RAW', '.E01', '.001']
        
        evidence_artifacts = [
            a for a in artifacts 
            if any(kw in str(a.get(field, '')).upper() 
                   for field in ['evidence_type', 'name', 'source_path']
                   for kw in disk_keywords)
        ]
        
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
            
            progress.setValue(20)
            self.img_info = pytsk3.Img_Info(file_path)
            image_size = self.img_info.get_size()
            
            progress.setValue(40)
            try:
                self.volume_info = pytsk3.Volume_Info(self.img_info)
                partitions = list(self.volume_info)
            except:
                partitions = [None]
            
            progress.setValue(60)
            self.build_evidence_tree(file_name, partitions)
            
            progress.setValue(80)
            if partitions and partitions[0]:
                self.load_partition_root(partitions[0])
            else:
                self.load_single_filesystem_root()

            progress.setValue(100)
            progress.close()

            # Refresh table headers after loading data
            self.refresh_table_headers()

            deleted = sum(1 for f in self.file_list if f.get('deleted'))
            QMessageBox.information(self, "Evidence Loaded",
                f"Evidence loaded!\n\nFile: {file_name}\n"
                f"Size: {self.format_size(image_size)}\n"
                f"Files: {len(self.file_list):,} ({deleted:,} deleted)")
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")
    
    # ============================================================================
    # TREE & NAVIGATION
    # ============================================================================
    
    def build_evidence_tree(self, evidence_name, partitions):
        """Build evidence tree structure."""
        if not hasattr(self.ui, 'treeInvestigation'):
            return
        
        self.ui.treeInvestigation.clear()
        root = QTreeWidgetItem(self.ui.treeInvestigation, [evidence_name])
        root.setData(0, Qt.UserRole, {'type': 'evidence', 'path': self.current_evidence_path})
        root.setExpanded(True)
        
        if partitions and partitions[0]:
            for i, part in enumerate(partitions):
                self._add_partition_node(root, part, i)
        else:
            self._add_filesystem_node(root, None)
        
        # Add Views
        views = QTreeWidgetItem(self.ui.treeInvestigation, ["Views"])
        views.setExpanded(True)
        deleted = sum(1 for f in self.file_list if f.get('deleted'))
        del_item = QTreeWidgetItem(views, [f"Deleted Files ({deleted})"])
        del_item.setData(0, Qt.UserRole, {'type': 'deleted_files'})
    
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
        """Populate root directory with limited depth."""
        try:
            directory = fs_info.open_dir("/")
            subdirs = []
            
            for entry in list(directory)[:50]:
                try:
                    if entry.info.name.name in [b'.', b'..'] or not entry.info.meta:
                        continue
                    if entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                        subdirs.append(name)
                except:
                    continue
            
            root_item = QTreeWidgetItem(parent, [f"Root Directory [{len(subdirs)} folders]"])
            root_item.setData(0, Qt.UserRole, {'type': 'directory', 'fs_info': fs_info, 'path': '/'})
            
            for subdir in subdirs[:10]:
                sub_item = QTreeWidgetItem(root_item, [subdir])
                sub_item.setData(0, Qt.UserRole, {
                    'type': 'directory', 'fs_info': fs_info, 
                    'path': f"/{subdir}", 'lazy_load': True
                })
        except:
            pass
    
    def on_tree_item_expanded(self, item):
        """Lazy load subdirectories on expansion."""
        data = item.data(0, Qt.UserRole)
        if not data or not data.get('lazy_load'):
            return
        
        fs_info = data.get('fs_info')
        path = data.get('path')
        if not fs_info or not path:
            return
        
        try:
            directory = fs_info.open_dir(path)
            for entry in list(directory)[:20]:
                try:
                    if entry.info.name.name in [b'.', b'..'] or not entry.info.meta:
                        continue
                    if entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                        name = entry.info.name.name.decode('utf-8', errors='ignore')
                        sub_item = QTreeWidgetItem(item, [name])
                        sub_item.setData(0, Qt.UserRole, {
                            'type': 'directory', 'fs_info': fs_info,
                            'path': f"{path.rstrip('/')}/{name}", 'lazy_load': True
                        })
                except:
                    continue
            data['lazy_load'] = False
            item.setData(0, Qt.UserRole, data)
        except:
            pass
    
    def on_tree_item_clicked(self, item, column):
        """Handle tree item clicks."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        handlers = {
            'filesystem': lambda: self.load_directory_files(data['fs_info'], '/'),
            'directory': lambda: self.load_directory_files(data['fs_info'], data.get('path', '/')),
            'deleted_files': lambda: self.load_deleted_files(self._find_fs_info()),
            'partition': lambda: self.load_partition_root(data['partition'])
        }
        
        handler = handlers.get(data.get('type'))
        if handler:
            try:
                handler()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error loading: {e}")
    
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
            fs_info = pytsk3.FS_Info(self.img_info, offset=offset)
            self.load_directory_files(fs_info, "/")
        except:
            pass
    
    def load_single_filesystem_root(self):
        """Load single filesystem root."""
        try:
            self.load_directory_files(pytsk3.FS_Info(self.img_info), "/")
        except:
            pass
    
    def load_directory_files(self, fs_info, path="/"):
        """Load files from directory."""
        try:
            self.file_list = []
            self.fs_info = fs_info
            
            directory = fs_info.open_dir(path)
            for entry in directory:
                if entry.info.name.name in [b'.', b'..']:
                    continue
                file_info = self._extract_file_info(entry, fs_info, path)
                if file_info:
                    self.file_list.append(file_info)
            
            if path == "/":
                self._scan_deleted_inodes(fs_info)
            
            self.file_list.sort(key=lambda x: (x['type'] != 'Directory', x['name'].lower()))
            self.update_file_table()
            self.generate_timeline()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading directory: {e}")
    
    def load_deleted_files(self, fs_info):
        """Scan for deleted files."""
        if not fs_info:
            QMessageBox.warning(self, "Error", "No filesystem available")
            return
        
        try:
            self.file_list = []
            self.fs_info = fs_info
            
            progress = QProgressDialog("Scanning deleted files...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            self._scan_deleted_inodes(fs_info, progress)
            self._walk_deleted_entries(fs_info)
            
            progress.close()
            
            # Remove duplicates
            seen = set()
            unique = []
            for f in self.file_list:
                key = (f['inode'], f['name'])
                if key not in seen:
                    seen.add(key)
                    unique.append(f)
            self.file_list = unique
            
            if self.file_list:
                self.update_file_table()
                QMessageBox.information(self, "Deleted Files", 
                    f"Found {len(self.file_list)} deleted files.")
            else:
                QMessageBox.information(self, "No Deleted Files", 
                    "No deleted files found.")
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.warning(self, "Error", f"Error scanning: {e}")
    
    # ============================================================================
    # FILE INFO EXTRACTION (UNIFIED)
    # ============================================================================
    
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
        
        return 'Unknown File'
    
    def _format_time(self, timestamp):
        """Format timestamp."""
        try:
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp > 0 else 'Unknown'
        except:
            return 'Unknown'
    
    # ============================================================================
    # DELETED FILE SCANNING (SIMPLIFIED)
    # ============================================================================
    
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
    
    # ============================================================================
    # FILE CONTENT EXTRACTION (UNIFIED)
    # ============================================================================
    
    def _extract_file_content(self, file_info, max_size=50000, as_text=True):
        """Universal file content extraction."""
        entry = file_info.get('entry')
        if not entry or (entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR if entry.info.meta else False):
            return None
        
        data = None
        
        # Method 1: Direct read
        try:
            if hasattr(entry, 'read_random'):
                data = entry.read_random(0, max_size)
        except:
            pass
        
        # Method 2: Attribute read (NTFS)
        if not data:
            try:
                for attr in entry:
                    if attr.info.type == 128 and (not attr.info.name or attr.info.name == b''):
                        size = min(attr.info.size, max_size) if hasattr(attr.info, 'size') else max_size
                        data = attr.read_random(0, size)
                        break
            except:
                pass
        
        # Method 3: Filesystem level
        if not data and entry.info.meta.addr:
            try:
                fs_info = file_info.get('fs_info') or self.fs_info
                if fs_info:
                    file_obj = fs_info.open_meta(inode=entry.info.meta.addr)
                    data = file_obj.read_random(0, max_size)
            except:
                pass
        
        if not data:
            return None
        
        # Extract strings if requested
        if as_text:
            try:
                text = data.decode('utf-8', errors='ignore')
                if sum(1 for c in text if c.isprintable() or c in '\n\r\t') / len(text) > 0.8:
                    return text
            except:
                pass
            
            # Extract printable strings
            strings = []
            current = ""
            for byte in data:
                if 32 <= byte <= 126:
                    current += chr(byte)
                else:
                    if len(current) >= 4:
                        strings.append(current)
                    current = ""
            if len(current) >= 4:
                strings.append(current)
            
            return '\n'.join(strings) if strings else f"Binary data ({len(data)} bytes)"
        
        return data
    
    # ============================================================================
    # UI UPDATES
    # ============================================================================
    
    def update_file_table(self):
        """Update file table."""
        if not hasattr(self.ui, 'tableFiles'):
            return
        
        # DO NOT touch sortingEnabled - leave it as False
        self.ui.tableFiles.setRowCount(len(self.file_list))
        
        for row, info in enumerate(self.file_list):
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
    
    def on_file_selected(self):
        """Handle file selection."""
        if not hasattr(self.ui, 'tableFiles'):
            return
        row = self.ui.tableFiles.currentRow()
        if 0 <= row < len(self.file_list):
            self._show_file_details(self.file_list[row])
    
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
            
            # Enable sorting after rendering
            QApplication.processEvents()
            self.ui.tableTimeline.setSortingEnabled(True)
    
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
    
    # ============================================================================
    # SEARCH
    # ============================================================================
    
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
            
            # Enable sorting after rendering
            QApplication.processEvents()
            self.ui.tableSearchResults.setSortingEnabled(True)
        
        if hasattr(self.ui, 'tabWorkArea'):
            self.ui.tabWorkArea.setCurrentIndex(2)
        
        QMessageBox.information(self, "Search", f"Found {len(self.search_results)} files")
    
    # ============================================================================
    # CONTEXT MENUS
    # ============================================================================
    
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
            ("View details", lambda: self._show_file_details(info)),
            ("Copy path", lambda: QApplication.clipboard().setText(info['path'])),
            ("Export raw", lambda: self._export_file(info)),
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
    
    # ============================================================================
    # UTILITIES
    # ============================================================================
    
    def format_size(self, size):
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"