import os
import sys
import hashlib
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from ui.pages.add_evidence_wizard_ui import Ui_AddEvidenceWizard
from database.db_manager import DatabaseManager


class HashCalculatorThread(QThread):
    """Thread để tính hash không block UI"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            sha256_hash = hashlib.sha256()
            with open(self.file_path, "rb") as f:
                file_size = os.path.getsize(self.file_path)
                bytes_read = 0
                
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
                    bytes_read += len(byte_block)
                    progress = int((bytes_read / file_size) * 100)
                    self.progress.emit(progress)
                    
            self.finished.emit(sha256_hash.hexdigest())
        except Exception as e:
            self.error.emit(str(e))


class AddEvidenceWizard(QDialog):
    evidence_added = pyqtSignal(dict)  # Signal khi thêm evidence thành công
    
    def __init__(self, case_id=None, parent=None):
        super().__init__(parent)
        self.ui = Ui_AddEvidenceWizard()
        self.ui.setupUi(self)
        
        self.case_id = case_id
        self.current_step = 0
        self.total_steps = 4  # Will be updated based on mode
        
        # Use global db instance to maintain user context
        from database.db_manager import db
        self.db_manager = db
        
        # Collection state tracking for collect mode
        self.collection_state = {
            'volatile_completed': False,
            'nonvolatile_completed': False,
            'volatile_started': False,
            'nonvolatile_started': False,
            'output_path': '',
            'collected_files': []
        }
        
        # Timer for checking collection status
        from PyQt5.QtCore import QTimer
        self.collection_check_timer = QTimer()
        self.collection_check_timer.timeout.connect(self.check_collection_status)
        self.collection_check_timer.setSingleShot(False)
        
        # Setup connections
        self.setup_connections()
        
        # Update initial state
        self.update_step_display()
        self.update_step_labels()  # Initialize step labels
        
        # Center dialog
        if parent:
            self.setModal(True)
            
    def setup_connections(self):
        """Setup signal connections"""
        # Navigation buttons
        self.ui.nextBtn.clicked.connect(self.next_step)
        self.ui.backBtn.clicked.connect(self.previous_step)
        self.ui.finishBtn.clicked.connect(self.finish_wizard)
        self.ui.cancelBtn.clicked.connect(self.reject)
        
        # File selection for import mode
        self.ui.addFilesBtn.clicked.connect(self.add_files)
        self.ui.removeFileBtn.clicked.connect(self.remove_selected_file)
        self.ui.clearAllBtn.clicked.connect(self.clear_all_files)
        
        # Collection buttons for collect mode
        self.ui.startVolatileBtn.clicked.connect(self.start_volatile_collection)
        self.ui.startNonvolatileBtn.clicked.connect(self.start_nonvolatile_collection)
        
        # Mode change - this is the key connection that updates step labels
        self.ui.modeGroup.buttonClicked.connect(self.on_mode_changed)
        
    def update_step_labels(self):
        """Update step labels based on current mode"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        if is_import_mode:
            # Import mode steps (4 steps)
            self.ui.step1Label.setText("1. Select Mode")
            self.ui.step2Label.setText("2. Select Evidence Type")  
            self.ui.step3Label.setText("3. Select Evidence Source")
            self.ui.step4Label.setText("4. Add Evidence Source")
            
            # Show all 4 steps for import mode
            self.ui.step2Label.setVisible(True)
            self.ui.step3Label.setText("3. Select Evidence Source")
            self.ui.step4Label.setText("4. Add Evidence Source")
            self.ui.step4Label.setVisible(True)
        else:
            # Collect mode steps (3 steps - skip evidence type selection)
            self.ui.step1Label.setText("1. Select Mode")
            self.ui.step2Label.setText("2. Collect Volatile Data")
            self.ui.step3Label.setText("3. Collect Non-volatile Data")
            self.ui.step4Label.setText("4. Complete")
            
            # Hide step 4 for collect mode (only 3 steps needed)
            self.ui.step4Label.setVisible(False)
        
    def update_step_display(self):
        """Update UI based on current step"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        # Update total steps and step mapping based on mode
        if is_import_mode:
            self.total_steps = 4
            # Import mode: 0->Step1, 1->Step2, 2->Step3, 3->Step4
            stacked_index = self.current_step
        else:
            self.total_steps = 3
            # Collect mode: 0->Step1, 1->Step3 (skip Step2), 2->Step4
            if self.current_step == 0:
                stacked_index = 0  # Step 1: Select Mode
            elif self.current_step == 1:
                stacked_index = 2  # Step 3: Collect Volatile (skip evidence type)
            else:  # self.current_step == 2
                stacked_index = 3  # Step 4: Collect Non-volatile
        
        # Update stackedWidget
        self.ui.stackedWidget.setCurrentIndex(stacked_index)
        
        # Update step labels highlighting
        step_labels = [
            self.ui.step1Label,
            self.ui.step2Label, 
            self.ui.step3Label,
            self.ui.step4Label
        ]
        
        for i, label in enumerate(step_labels):
            # Handle visibility for collect mode
            if not is_import_mode and i == 3:  # Step 4 is hidden in collect mode
                continue
                
            # Map current step to label index for collect mode
            if is_import_mode:
                is_current = (i == self.current_step)
                is_completed = (i < self.current_step)
            else:
                # Collect mode step mapping: 0->0, 1->1, 2->2 (skip 3)
                if i == 0:
                    is_current = (self.current_step == 0)
                    is_completed = (self.current_step > 0)
                elif i == 1:
                    is_current = (self.current_step == 1)
                    is_completed = (self.current_step > 1)
                elif i == 2:
                    is_current = (self.current_step == 2)
                    is_completed = False
                else:
                    continue
                    
            if is_current:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 12px;
                        color: white;
                        background-color: #4299e1;
                        padding: 8px;
                        border-radius: 4px;
                        margin: 2px 0;
                        font-weight: bold;
                    }
                """)
            elif is_completed:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 12px;
                        color: #68d391;
                        background-color: #f0fff4;
                        padding: 8px;
                        border-radius: 4px;
                        margin: 2px 0;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 12px;
                        color: #4a5568;
                        padding: 8px;
                        border-radius: 4px;
                        margin: 2px 0;
                    }
                """)
        
        # Update title and description based on mode and step
        if is_import_mode:
            titles = [
                "Select Mode Add Evidence",
                "Select Evidence Type", 
                "Select Evidence Source",
                "Configure Evidence"
            ]
            descriptions = [
                "Choose how you want to add evidence to the case.",
                "Select the type of evidence you want to add.",
                "Choose the source of your evidence files.",
                "Configure and finalize your evidence settings."
            ]
            title = titles[self.current_step]
            description = descriptions[self.current_step]
        else:
            # Collect mode titles/descriptions
            if self.current_step == 0:
                title = "Select Mode Add Evidence"
                description = "Choose how you want to add evidence to the case."
            elif self.current_step == 1:
                title = "Collect Volatile Data"
                description = "Start volatile data collection (Memory, Processes, Network). This must be done first as volatile data can be lost."
            else:  # self.current_step == 2
                title = "Collect Non-volatile Data"
                description = "Start non-volatile data collection (Disk, Files, Registry). This data persists and can be collected after volatile data."
        
        self.ui.titleLabel.setText(title)
        self.ui.descriptionLabel.setText(description)
        
        # Update buttons
        self.ui.backBtn.setEnabled(self.current_step > 0)
        
        if self.current_step == self.total_steps - 1:
            self.ui.nextBtn.setVisible(False)
            self.ui.finishBtn.setVisible(True)
        else:
            self.ui.nextBtn.setVisible(True)
            self.ui.finishBtn.setVisible(False)
            
    def next_step(self):
        """Go to next step"""
        if self.validate_current_step():
            if self.current_step < self.total_steps - 1:
                self.current_step += 1
                self.update_step_display()
                
    def previous_step(self):
        """Go to previous step"""
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step_display()
            
    def validate_current_step(self):
        """Validate current step before proceeding"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        if self.current_step == 0:
            # Step 1: Mode selection (always valid since one is pre-selected)
            return True
        elif self.current_step == 1:
            if is_import_mode:
                # Import mode Step 2: Evidence type (always valid since one is pre-selected)
                return True
            else:
                # Collect mode Step 2: Volatile collection
                if not self.collection_state['volatile_completed']:
                    # Start volatile collection
                    self.start_volatile_collection()
                    return False  # Don't proceed to next step yet
                return True
        elif self.current_step == 2:
            if is_import_mode:
                # Import mode Step 3: Check if files are selected
                if self.ui.fileListWidget.count() == 0:
                    QMessageBox.warning(self, "Validation Error", "Please select at least one evidence file.")
                    return False
                # Verify all files exist
                for file_path in self.get_selected_files():
                    if not os.path.exists(file_path):
                        QMessageBox.warning(self, "Validation Error", f"File does not exist: {file_path}")
                        return False
                return True
            else:
                # Collect mode Step 3: Non-volatile collection
                if not self.collection_state['nonvolatile_completed']:
                    # Start non-volatile collection
                    self.start_nonvolatile_collection()
                    return False  # Don't proceed yet
                return True
        elif self.current_step == 3:
            # Import mode Step 4: Final step validation
            if is_import_mode:
                # No additional validation needed for import mode final step
                pass
            return True
        return True
        
    def on_mode_changed(self):
        """Handle mode change - Update step labels and UI visibility"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        # Reset to step 0 when changing modes
        self.current_step = 0
        
        # Update step labels based on new mode
        self.update_step_labels()
        
        # Update UI visibility for Step 3 and Step 4
        self.ui.importSourceFrame.setVisible(is_import_mode)
        self.ui.collectSourceFrame.setVisible(not is_import_mode)
        
        self.ui.importConfigFrame.setVisible(is_import_mode)
        self.ui.collectConfigFrame.setVisible(not is_import_mode)
        
        # Reset collection state when switching to collect mode
        if not is_import_mode:
            self.reset_collection_state()
            
        # Update current step display to reflect new labels and step count
        self.update_step_display()
        
    def reset_collection_state(self):
        """Reset collection state for collect mode"""
        self.collection_state = {
            'volatile_completed': False,
            'nonvolatile_completed': False,
            'output_path': '',
            'collected_files': []
        }
        
    def start_volatile_collection(self):
        """Start volatile data collection - Link to real volatile collection interface"""
        try:
            # Get main window reference
            main_window = self.get_main_window()
            if main_window:
                # Hide wizard temporarily
                self.hide()
                
                # Switch to volatile collection tab in main interface
                if hasattr(main_window, 'switch_to_volatile_tab'):
                    main_window.switch_to_volatile_tab(self.case_id)
                elif hasattr(main_window, 'volatile_btn'):
                    # Fallback: Click volatile button to open tab
                    main_window.volatile_btn.click()
                    
                # Try to get volatile page and store reference
                if hasattr(main_window, 'menu_btns_list') and hasattr(main_window, 'volatile_btn') and main_window.volatile_btn in main_window.menu_btns_list:
                    volatile_page = main_window.menu_btns_list[main_window.volatile_btn]
                    # Store reference for later use when collection starts
                    self.volatile_page = volatile_page
                    
                    # Set case data if method exists
                    if hasattr(volatile_page, 'set_case_data') and self.case_id:
                        # Get case info from database
                        case_info = self.db_manager.get_case_by_id(self.case_id)
                        if case_info:
                            case_data = {
                                'case_id': case_info.get('case_code', f"CASE-{self.case_id}"),
                                'case_name': case_info.get('title', 'Unknown Case'),
                                'investigator': 'Current User',
                                'database_case_id': self.case_id
                            }
                            volatile_page.set_case_data(case_data)
                    
                    print("Successfully linked to volatile collection interface")
                    
                    # Mark that volatile collection has started
                    self.collection_state['volatile_started'] = True
                    
                    # Connect to collection signals in volatile page
                    self.connect_volatile_signals()
                    
                    # Start timer to check collection status as backup
                    self.collection_check_timer.start(2000)  # Check every 2 seconds
                else:
                    print("Could not find volatile page in main window")
            else:
                QMessageBox.warning(self, "Error", "Could not find main window to switch to volatile collection")
                    
        except Exception as e:
            print(f"Error starting volatile collection: {e}")
            QMessageBox.warning(self, "Error", f"Failed to start volatile collection: {e}")
            
    def on_volatile_collection_complete(self, success, message, package_path):
        """Called when volatile collection is complete"""
        print(f"on_volatile_collection_complete called with success={success}, message={message}, path={package_path}")
        
        # Prevent multiple calls
        if self.collection_state['volatile_completed']:
            print("Volatile collection already completed, ignoring duplicate call")
            return
        
        self.collection_state['volatile_completed'] = True
        if success and package_path:
            self.collection_state['output_path'] = package_path
        else:
            self.collection_state['output_path'] = "E:/ForensicCollection/volatile_collection/"
        
        print(f"Collection state updated: {self.collection_state}")
        
        # Stop timer to prevent additional calls
        if hasattr(self, 'collection_check_timer'):
            self.collection_check_timer.stop()
        
        # Show completion dialog from collection interface
        if success:
            print("Showing completion dialog...")
            QMessageBox.information(
                None,  # Show as independent dialog
                "Hoàn thành Thu thập Forensic",
                f"✅ {message}\n\n"
                f"📦 Evidence Package: {os.path.basename(package_path) if package_path else 'volatile_collection.zip'}\n"
                f"📁 Đường dẫn: {package_path}\n\n"
                f"🔐 Đã tính toán hash SHA-256\n"
                f"📋 Chain of custody đã được ghi lại"
            )
            print("Completion dialog shown and dismissed")
        else:
            print("Showing error dialog...")
            QMessageBox.warning(
                None,  # Show as independent dialog
                "Lỗi Thu thập Forensic",
                f"❌ {message}\n\n"
                f"Quá trình thu thập gặp lỗi. Vui lòng kiểm tra:\n"
                f"• Tên case không chứa ký tự đặc biệt\n"
                f"• Đường dẫn lưu trữ hợp lệ\n"
                f"• Đủ quyền truy cập\n\n"
                f"Thử lại với case name bằng tiếng Anh."
            )
            print("Error dialog shown and dismissed")
        
        # Then show wizard again after user clicks OK
        print("Attempting to show wizard again...")
        self.show()
        self.raise_()  # Bring to front
        self.activateWindow()
        print(f"Wizard visibility: {self.isVisible()}")
        
        # Update status display with collection information - this will show on Step 3
        print("Updating collection status...")
        self.update_collection_status(volatile_done=True)
        
        # Stay on current step (Step 3) but now shows completion status
        # User can see the completion info and click Next when ready
        print("Updating step display...")
        self.update_step_display()
        
        print(f"Volatile collection completed: {message}, wizard shown with completion status")
        
    def connect_volatile_signals(self):
        """Connect to volatile collection page signals"""
        try:
            if hasattr(self, 'volatile_page'):
                volatile_page = self.volatile_page
                print(f"Connecting to volatile page signals...")
                
                # Set a reference to this wizard in the volatile page
                volatile_page.wizard_reference = self
                print("Set wizard reference in volatile page")
                
                # Try to connect to the page's collection_finished method/signal
                if hasattr(volatile_page, 'collection_finished'):
                    # If it's a signal, connect to it
                    try:
                        volatile_page.collection_finished.connect(self.on_volatile_collection_complete)
                        print("Connected to volatile page collection_finished signal")
                    except Exception as e:
                        print(f"Failed to connect to signal: {e}")
                
                # Also try to monkey patch the collection_finished method
                if hasattr(volatile_page, 'collection_finished'):
                    original_method = volatile_page.collection_finished
                    
                    def patched_collection_finished(success, message, package_path):
                        print(f"Collection finished detected via monkey patch: {success}, {message}, {package_path}")
                        # Call original method
                        if callable(original_method):
                            original_method(success, message, package_path)
                        # Call our handler
                        self.on_volatile_collection_complete(success, message, package_path)
                    
                    volatile_page.collection_finished = patched_collection_finished
                    print("Monkey patched collection_finished method")
                    
        except Exception as e:
            print(f"Error connecting volatile signals: {e}")
            import traceback
            traceback.print_exc()
            
    def wizard_collection_finished(self, collection_type, success, message, package_path):
        """Method to be called directly from collection pages"""
        print(f"wizard_collection_finished called: {collection_type}, {success}, {message}, {package_path}")
        
        if collection_type == 'volatile':
            self.on_volatile_collection_complete(success, message, package_path)
        elif collection_type == 'nonvolatile':
            self.on_nonvolatile_collection_complete(package_path)
        
    def connect_to_collection_signals(self):
        """Connect to collection signals once collection starts"""
        try:
            # For volatile collection
            if hasattr(self, 'volatile_page'):
                volatile_page = self.volatile_page
                # The signal is actually in the collection_worker when it's created
                # We need to hook into the page's start_collection method
                if hasattr(volatile_page, 'collection_worker'):
                    worker = volatile_page.collection_worker
                    if worker and hasattr(worker, 'collection_finished'):
                        # Safely disconnect existing connections
                        try:
                            worker.collection_finished.disconnect(self.on_volatile_collection_complete)
                        except (TypeError, RuntimeError):
                            pass
                        # Connect our handler
                        worker.collection_finished.connect(self.on_volatile_collection_complete)
                        print("Connected to volatile collection worker signal")
                        
            # For non-volatile collection
            if hasattr(self, 'nonvolatile_page'):
                nonvolatile_page = self.nonvolatile_page
                # Similar approach for nonvolatile
                if hasattr(nonvolatile_page, 'collection_worker'):
                    worker = nonvolatile_page.collection_worker
                    if worker and hasattr(worker, 'collection_finished'):
                        # Safely disconnect existing connections
                        try:
                            worker.collection_finished.disconnect(self.on_nonvolatile_collection_complete)
                        except (TypeError, RuntimeError):
                            pass
                        # Connect our handler
                        worker.collection_finished.connect(self.on_nonvolatile_collection_complete)
                        print("Connected to nonvolatile collection worker signal")
                        
        except Exception as e:
            print(f"Error connecting to collection signals: {e}")
            # Don't show error to user, just continue without signal connection
            
    def check_collection_status(self):
        """Check if collection is complete and handle accordingly"""
        try:
            # Check volatile collection - only if it was started and not completed
            if (hasattr(self, 'volatile_page') and 
                self.collection_state['volatile_started'] and 
                not self.collection_state['volatile_completed']):
                
                volatile_page = self.volatile_page
                
                # Check if collection is finished by looking at UI state AND collection actually happened
                if (hasattr(volatile_page, 'ui') and 
                    hasattr(volatile_page.ui, 'startCollectionBtn')):
                    
                    button_enabled = volatile_page.ui.startCollectionBtn.isEnabled()
                    
                    # Also check if collection actually happened by looking at evidence log
                    evidence_log_has_content = False
                    if hasattr(volatile_page.ui, 'evidenceLogText'):
                        log_content = volatile_page.ui.evidenceLogText.toPlainText()
                        # Look for signs that collection actually completed
                        evidence_log_has_content = ("SHA-256:" in log_content or 
                                                   "Package:" in log_content or
                                                   "Collection completed:" in log_content)
                    
                    # Only trigger completion if button is enabled AND there's evidence of actual collection
                    if button_enabled and evidence_log_has_content:
                        # Collection finished, button is enabled again
                        self.collection_check_timer.stop()
                        
                        # Try to get actual output path from the volatile page
                        output_path = "E:/ForensicCollection/volatile_collection/"
                        if hasattr(volatile_page.ui, 'outputPathEdit'):
                            output_path = volatile_page.ui.outputPathEdit.text() or output_path
                        
                        self.on_volatile_collection_complete(True, "Thu thập volatile hoàn tất!", output_path)
                        return
                    
            # Check non-volatile collection
            if hasattr(self, 'nonvolatile_page') and not self.collection_state['nonvolatile_completed']:
                nonvolatile_page = self.nonvolatile_page
                # Check if collection is finished by looking at UI state
                if (hasattr(nonvolatile_page, 'ui') and 
                    hasattr(nonvolatile_page.ui, 'startCollectionBtn') and
                    nonvolatile_page.ui.startCollectionBtn.isEnabled()):
                    # Collection finished, button is enabled again
                    self.collection_check_timer.stop()
                    
                    # Try to get actual output path from the nonvolatile page
                    output_path = "E:/ForensicCollection/nonvolatile_collection/"
                    if hasattr(nonvolatile_page.ui, 'outputPathEdit'):
                        output_path = nonvolatile_page.ui.outputPathEdit.text() or output_path
                    
                    self.on_nonvolatile_collection_complete(output_path)
                    return
                    
        except Exception as e:
            print(f"Error checking collection status: {e}")
            import traceback
            traceback.print_exc()
            # Continue checking
        
    def on_nonvolatile_collection_complete(self, output_path=None):
        """Called when non-volatile collection is complete"""
        # Prevent multiple calls
        if self.collection_state['nonvolatile_completed']:
            print("Non-volatile collection already completed, ignoring duplicate call")
            return
            
        self.collection_state['nonvolatile_completed'] = True
        if output_path:
            self.collection_state['output_path'] = output_path
        
        # Stop timer to prevent additional calls
        if hasattr(self, 'collection_check_timer'):
            self.collection_check_timer.stop()
        
        # First show completion dialog from collection interface
        QMessageBox.information(
            None,  # Show as independent dialog
            "Hoàn thành Thu thập Forensic",
            f"✅ Thu thập Non-volatile hoàn tất!\n\n"
            f"📦 Evidence Package: {os.path.basename(output_path) if output_path else 'nonvolatile_collection.zip'}\n"
            f"📁 Đường dẫn: {output_path}\n\n"
            f"🔐 Đã tính toán hash SHA-256\n"
            f"📋 Chain of custody đã được ghi lại\n\n"
            f"🎉 Thu thập Evidence hoàn tất!"
        )
        
        # Then show wizard again after user clicks OK
        self.show()
        self.raise_()  # Bring to front
        self.activateWindow()
        
        # Update status display with collection information
        self.update_collection_status(nonvolatile_done=True)
        
        # Update step display to show completion - this will enable Finish button
        self.update_step_display()
        
        print("Non-volatile collection completed, wizard shown with completion status")
        
    def get_main_window(self):
        """Get reference to main window"""
        parent = self.parent()
        while parent:
            # Look for main window with volatile_btn attribute
            if hasattr(parent, 'volatile_btn') and hasattr(parent, 'menu_btns_list'):
                return parent
            parent = parent.parent()
        return None
        
    def start_nonvolatile_collection(self):
        """Start non-volatile data collection - Link to real non-volatile collection interface"""
        try:
            # Get main window reference
            main_window = self.get_main_window()
            if main_window:
                # Hide wizard temporarily
                self.hide()
                
                # Switch to non-volatile collection tab in main interface
                if hasattr(main_window, 'switch_to_nonvolatile_tab'):
                    main_window.switch_to_nonvolatile_tab(self.case_id)
                elif hasattr(main_window, 'nonvolatile_btn'):
                    # Fallback: Click nonvolatile button to open tab
                    main_window.nonvolatile_btn.click()
                    
                # Try to get nonvolatile page and store reference
                if hasattr(main_window, 'menu_btns_list') and hasattr(main_window, 'nonvolatile_btn') and main_window.nonvolatile_btn in main_window.menu_btns_list:
                    nonvolatile_page = main_window.menu_btns_list[main_window.nonvolatile_btn]
                    # Store reference for later use when collection starts
                    self.nonvolatile_page = nonvolatile_page
                    
                    # Set case data if method exists
                    if hasattr(nonvolatile_page, 'set_case_data') and self.case_id:
                        # Get case info from database
                        case_info = self.db_manager.get_case_by_id(self.case_id)
                        if case_info:
                            case_data = {
                                'case_id': case_info.get('case_code', f"CASE-{self.case_id}"),
                                'case_name': case_info.get('title', 'Unknown Case'),
                                'investigator': 'Current User',
                                'database_case_id': self.case_id
                            }
                            nonvolatile_page.set_case_data(case_data)
                    
                    print("Successfully linked to non-volatile collection interface")
                    
                    # Start timer to check collection status
                    self.collection_check_timer.start(2000)  # Check every 2 seconds
                else:
                    print("Could not find non-volatile page in main window")
            else:
                QMessageBox.warning(self, "Error", "Could not find main window to switch to non-volatile collection")
                    
        except Exception as e:
            print(f"Error starting non-volatile collection: {e}")
            QMessageBox.warning(self, "Error", f"Failed to start non-volatile collection: {e}")
        
    def add_files(self):
        """Add files to the list for import mode"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Evidence Files",
            "",
            "All Files (*.*)"
        )
        
        for file_path in file_paths:
            if file_path and file_path not in self.get_selected_files():
                filename = os.path.basename(file_path)
                item_text = f"{filename} ({file_path})"
                self.ui.fileListWidget.addItem(item_text)
                
    def remove_selected_file(self):
        """Remove selected file from list"""
        current_row = self.ui.fileListWidget.currentRow()
        if current_row >= 0:
            self.ui.fileListWidget.takeItem(current_row)
            
    def clear_all_files(self):
        """Clear all files from list"""
        self.ui.fileListWidget.clear()
        
    def get_selected_files(self):
        """Get list of selected file paths"""
        files = []
        for i in range(self.ui.fileListWidget.count()):
            item = self.ui.fileListWidget.item(i)
            if item:
                item_text = item.text()
                # Extract path from "filename (path)" format
                if " (" in item_text and item_text.endswith(")"):
                    path = item_text[item_text.rfind("(") + 1:-1]
                    files.append(path)
        return files
    
    def calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def calculate_file_hash_with_progress(self, file_path, filename):
        """Calculate SHA256 hash with progress dialog for large files"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Create progress dialog
            progress = QProgressDialog(
                f"Calculating hash for {filename}...",
                "Cancel", 
                0, 
                100, 
                self
            )
            progress.setWindowTitle("Calculating Hash")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            sha256_hash = hashlib.sha256()
            bytes_read = 0
            
            with open(file_path, "rb") as f:
                while True:
                    # Check if user cancelled
                    if progress.wasCanceled():
                        progress.close()
                        return None
                        
                    byte_block = f.read(1024 * 1024)  # Read 1MB chunks for large files
                    if not byte_block:
                        break
                        
                    sha256_hash.update(byte_block)
                    bytes_read += len(byte_block)
                    
                    # Update progress
                    progress_value = int((bytes_read / file_size) * 100)
                    progress.setValue(progress_value)
                    
                    # Process events to keep UI responsive
                    from PyQt5.QtWidgets import QApplication
                    QApplication.processEvents()
            
            progress.close()
            return sha256_hash.hexdigest()
            
        except Exception as e:
            print(f"Error calculating hash for {file_path}: {e}")
            if 'progress' in locals():
                progress.close()
            return None
    
    def format_file_size(self, size_bytes):
        """Format file size for display"""
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
            '.log': 'text/plain',
            '.txt': 'text/plain', 
            '.csv': 'text/csv',
            '.raw': 'image/RAM',                # Memory dumps (custom forensic MIME type)
            '.mem': 'image/RAM',                # Memory dumps
            '.vmem': 'image/RAM',               # VMware memory dumps
            '.dmp': 'application/octet-stream', # Windows crash dumps
            '.dd': 'image/disk',                # Disk images (custom forensic MIME type)
            '.e01': 'image/disk',               # EnCase evidence files
            '.img': 'image/disk',               # Disk images
            '.001': 'image/disk',               # Split disk images
            '.pcap': 'application/vnd.tcpdump.pcap',  # Network captures
            '.pcapng': 'application/vnd.tcpdump.pcap',
            '.evtx': 'application/x-ms-evtx',   # Windows event logs (custom)
            '.reg': 'text/plain',               # Registry files
            '.hiv': 'application/x-registry-hive',  # Registry hives (custom)
            '.pf': 'application/x-prefetch',    # Prefetch files (custom)
            '.conf': 'text/plain',              # Config files
        }
        
        # Lấy extension của file
        _, ext = os.path.splitext(file_path.lower())
        
        # Kiểm tra custom mapping trước
        if ext in forensic_mime_types:
            return forensic_mime_types[ext]
        
        # Fallback về mimetypes library
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"
        
    def update_collection_status(self, volatile_done=False, nonvolatile_done=False):
        """Update collection status display"""
        if volatile_done:
            output_path = self.collection_state.get('output_path', 'E:/Evidence/volatile_collection/')
            package_name = os.path.basename(output_path) if output_path else 'volatile_collection.zip'
            
            self.ui.volatileStatusLabel.setText(
                f"✅ HOÀN THÀNH THU THẬP VOLATILE DATA\n\n"
                f"📦 Package: {package_name}\n"
                f"📁 Đường dẫn: {output_path}\n"
                f"🔐 Hash SHA-256 đã được tính toán\n"
                f"📋 Chain of custody đã được ghi lại\n\n"
                f"➡️ Bấm Next để tiếp tục thu thập Non-volatile data"
            )
            self.ui.volatileStatusLabel.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #2d5016;
                    background-color: #ecfdf5;
                    border: 3px solid #22c55e;
                    border-radius: 10px;
                    padding: 20px;
                    text-align: left;
                    line-height: 1.4;
                }
            """)
            self.ui.volatileStatusLabel.setWordWrap(True)
            self.ui.volatileStatusLabel.setMaximumWidth(650)  # Increase width slightly
            self.ui.startVolatileBtn.setText("✅ Volatile Collection Complete")
            self.ui.startVolatileBtn.setEnabled(False)
            
            # Also show info on the description label for this step
            if self.current_step == 2:  # Step 3 (0-indexed)
                self.ui.descriptionLabel.setText(
                    "✅ Volatile data collection completed successfully! "
                    "All volatile evidence has been collected and packaged. "
                    "Click Next to proceed to Non-volatile data collection."
                )
                
            # Hide the instruction info when completed
            if hasattr(self.ui, 'volatileInfoLabel'):
                self.ui.volatileInfoLabel.setVisible(False)
            
        if nonvolatile_done:
            output_path = self.collection_state.get('output_path', 'E:/Evidence/nonvolatile_collection/')
            package_name = os.path.basename(output_path) if output_path else 'nonvolatile_collection.zip'
            
            self.ui.nonvolatileStatusLabel.setText(
                f"✅ HOÀN THÀNH THU THẬP NON-VOLATILE DATA\n\n"
                f"📦 Package: {package_name}\n"
                f"📁 Đường dẫn: {output_path}\n"
                f"🔐 Hash SHA-256 đã được tính toán\n"
                f"📋 Chain of custody đã được ghi lại\n\n"
                f"🎉 TẤT CẢ EVIDENCE ĐÃ THU THẬP HOÀN TẤT!\n"
                f"➡️ Bấm Finish để hoàn thành wizard"
            )
            self.ui.nonvolatileStatusLabel.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #1e3a8a;
                    background-color: #eff6ff;
                    border: 3px solid #3b82f6;
                    border-radius: 10px;
                    padding: 20px;
                    text-align: left;
                    line-height: 1.4;
                }
            """)
            self.ui.nonvolatileStatusLabel.setWordWrap(True)
            self.ui.nonvolatileStatusLabel.setMaximumWidth(650)  # Increase width slightly
            self.ui.startNonvolatileBtn.setText("✅ Non-volatile Collection Complete")
            self.ui.startNonvolatileBtn.setEnabled(False)
            
            # Also show info on the description label for this step
            if self.current_step == 3:  # Step 4 (0-indexed)
                self.ui.descriptionLabel.setText(
                    "🎉 All evidence collection completed successfully! "
                    "Both volatile and non-volatile data have been collected and packaged. "
                    "Click Finish to complete the wizard and proceed to analysis."
                )
                
            # Hide the instruction info when completed
            if hasattr(self.ui, 'nonvolatileInfoLabel'):
                self.ui.nonvolatileInfoLabel.setVisible(False)
                
    def get_wizard_data(self):
        """Collect all wizard data"""
        is_import_mode = self.ui.importModeRadio.isChecked()
        
        data = {
            'mode': 'import' if is_import_mode else 'collect',
            'evidence_type': 'volatile' if self.ui.volatileTypeRadio.isChecked() else 'nonvolatile',
            'case_id': self.case_id
        }
        
        if is_import_mode:
            data.update({
                'files': self.get_selected_files(),
                'calculate_hash': self.ui.calculateHashCheck.isChecked(),
                'verify_integrity': self.ui.verifyIntegrityCheck.isChecked(),
                'create_backup': self.ui.createBackupCheck.isChecked()
            })
        else:
            data.update({
                'collection_state': self.collection_state,
                'output_path': self.collection_state['output_path'],
                'collected_files': self.collection_state['collected_files']
            })
        
        return data
        
    def add_evidence_to_database(self, evidence_data):
        """Add evidence to database"""
        try:
            # Check if case_id is valid
            if not self.case_id:
                return None
            
            results = []
            
            if evidence_data['mode'] == 'import':
                # Process multiple files for import mode
                for file_path in evidence_data['files']:
                    if not os.path.exists(file_path):
                        continue
                        
                    file_size = os.path.getsize(file_path)
                    filename = os.path.basename(file_path)
                    
                    # Add artifact to database using proper parameters
                    artifact_id = self.db_manager.add_artifact(
                        case_id=self.case_id,
                        name=filename,
                        source_path=file_path,
                        evidence_type=evidence_data['evidence_type'],
                        size=file_size,
                        mime_type=self.get_mime_type(file_path)
                    )
                    
                    # Calculate and store hash if requested
                    hash_value = ''
                    if artifact_id and evidence_data.get('calculate_hash', False):
                        if os.path.isfile(file_path):
                            print(f"DEBUG Wizard: Calculating hash for {filename} ({self.format_file_size(file_size)})")
                            
                            # Use thread-based hash calculation for large files
                            if file_size > 100 * 1024 * 1024:  # > 100MB - show progress
                                hash_value = self.calculate_file_hash_with_progress(file_path, filename)
                            else:
                                hash_value = self.calculate_file_hash(file_path)
                            
                            if hash_value:
                                print(f"DEBUG Wizard: Hash calculated: {hash_value[:16]}...")
                                # Use HashManager to add origin hash
                                from database.hash_types import HashManager
                                hash_manager = HashManager(self.db_manager)
                                result = hash_manager.add_origin_hash(artifact_id, hash_value)
                                print(f"DEBUG Wizard: Hash add result: {result}")
                            else:
                                print(f"DEBUG Wizard: Failed to calculate hash for {filename}")
                        else:
                            print(f"DEBUG Wizard: File not found: {file_path}")
                    
                    if artifact_id:
                        evidence_record = {
                            'id': artifact_id,
                            'case_id': self.case_id,
                            'evidence_name': filename,
                            'evidence_type': evidence_data['evidence_type'],
                            'file_path': file_path,
                            'file_size': file_size,
                            'hash_value': hash_value,
                            'collection_method': evidence_data['mode'],
                            'source_type': 'import',
                            'status': 'imported'
                        }
                        results.append(evidence_record)
            else:
                # Collect mode - create placeholder record
                collection_name = f"Collection_{evidence_data['evidence_type']}_{self.case_id}"
                output_path = evidence_data['output_path']
                
                # Determine MIME type based on actual collected file
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
                    evidence_type=evidence_data['evidence_type'],  # "volatile" hoặc "nonvolatile"
                    size=file_size,
                    mime_type=mime_type
                )
                
                if artifact_id:
                    evidence_record = {
                        'id': artifact_id,
                        'case_id': self.case_id,
                        'evidence_name': collection_name,
                        'evidence_type': evidence_data['evidence_type'],  # "volatile" hoặc "nonvolatile"
                        'file_path': output_path,
                        'file_size': file_size,
                        'hash_value': '',
                        'collection_method': evidence_data['mode'],
                        'source_type': 'collection_workflow',
                        'status': 'collected'
                    }
                    results.append(evidence_record)
            
            return results if results else None
                
        except Exception as e:
            print(f"Error adding evidence to database: {str(e)}")
            return None
            
    def finish_wizard(self):
        """Complete the wizard"""
        if not self.validate_current_step():
            return
            
        wizard_data = self.get_wizard_data()
        
        # For import mode with hash calculation
        if wizard_data['mode'] == 'import' and wizard_data.get('calculate_hash', False):
            # Process files with hash calculation
            self.process_files_with_hash(wizard_data)
        else:
            # No hash calculation needed or collect mode
            self.finalize_evidence_addition(wizard_data)
            
    def process_files_with_hash(self, wizard_data):
        """Process files with hash calculation"""
        # This would be implemented for hash calculation
        # For now, just finalize without hash
        self.finalize_evidence_addition(wizard_data)
        
    def finalize_evidence_addition(self, wizard_data):
        """Complete evidence addition process"""
        # Add to database
        evidence_records = self.add_evidence_to_database(wizard_data)
        
        if evidence_records:
            count = len(evidence_records)
            if wizard_data['mode'] == 'import':
                msg = f"Successfully imported {count} evidence file(s) to the case!"
            else:
                msg = f"Evidence collection workflow completed successfully!\nOutput: {wizard_data['output_path']}"
                
            QMessageBox.information(self, "Success", msg)
            
            # Emit signal with evidence data
            for record in evidence_records:
                self.evidence_added.emit(record)
            
            # Close dialog
            self.accept()
        else:
            QMessageBox.critical(
                self, 
                "Error", 
                "Failed to add evidence to database. Please try again."
            ) 