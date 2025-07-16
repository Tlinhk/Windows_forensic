# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_AddEvidenceWizard(object):
    def setupUi(self, AddEvidenceWizard):
        AddEvidenceWizard.setObjectName("AddEvidenceWizard")
        AddEvidenceWizard.resize(800, 600)
        AddEvidenceWizard.setWindowTitle("Add Evidence - Windows Forensic System")

        # Main horizontal layout
        self.horizontalLayout = QtWidgets.QHBoxLayout(AddEvidenceWizard)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(0)

        # Left panel - Steps
        self.stepsFrame = QtWidgets.QFrame(AddEvidenceWizard)
        self.stepsFrame.setFixedWidth(200)
        self.stepsFrame.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
            }
        """
        )

        self.stepsLayout = QtWidgets.QVBoxLayout(self.stepsFrame)
        self.stepsLayout.setContentsMargins(20, 30, 20, 30)
        self.stepsLayout.setSpacing(10)

        # Steps header
        self.stepsHeaderLabel = QtWidgets.QLabel("Steps")
        self.stepsHeaderLabel.setStyleSheet(
            """
            font-size: 16px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 10px;
        """
        )
        self.stepsLayout.addWidget(self.stepsHeaderLabel)

        # Step items
        self.step1Label = QtWidgets.QLabel("1. Select Mode Add Evidence")
        self.step2Label = QtWidgets.QLabel("2. Select Evidence Type")
        self.step3Label = QtWidgets.QLabel("3. Select Evidence Source")
        self.step4Label = QtWidgets.QLabel("4. Add Evidence Source")

        # Style for steps
        step_style = """
            QLabel {
                font-size: 12px;
                color: #4a5568;
                padding: 8px;
                border-radius: 4px;
                margin: 2px 0;
            }
        """

        self.step1Label.setStyleSheet(step_style)
        self.step2Label.setStyleSheet(step_style)
        self.step3Label.setStyleSheet(step_style)
        self.step4Label.setStyleSheet(step_style)

        self.stepsLayout.addWidget(self.step1Label)
        self.stepsLayout.addWidget(self.step2Label)
        self.stepsLayout.addWidget(self.step3Label)
        self.stepsLayout.addWidget(self.step4Label)

        # Add stretch to push steps to top
        self.stepsLayout.addStretch()

        self.horizontalLayout.addWidget(self.stepsFrame)

        # Right panel - Content
        self.contentFrame = QtWidgets.QFrame(AddEvidenceWizard)
        self.contentFrame.setStyleSheet("QFrame { background-color: white; }")

        self.contentLayout = QtWidgets.QVBoxLayout(self.contentFrame)
        self.contentLayout.setContentsMargins(30, 30, 30, 20)
        self.contentLayout.setSpacing(20)

        # Header area
        self.headerFrame = QtWidgets.QFrame()
        self.headerLayout = QtWidgets.QVBoxLayout(self.headerFrame)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLayout.setSpacing(5)

        self.titleLabel = QtWidgets.QLabel("Select Mode Add Evidence")
        self.titleLabel.setStyleSheet(
            """
            font-size: 18px;
            font-weight: bold;
            color: #2d3748;
        """
        )

        self.descriptionLabel = QtWidgets.QLabel(
            "Choose how you want to add evidence to the case."
        )
        self.descriptionLabel.setStyleSheet(
            """
            font-size: 12px;
            color: #718096;
        """
        )

        self.headerLayout.addWidget(self.titleLabel)
        self.headerLayout.addWidget(self.descriptionLabel)
        self.contentLayout.addWidget(self.headerFrame)

        # Stacked widget for different steps
        self.stackedWidget = QtWidgets.QStackedWidget()
        self.contentLayout.addWidget(self.stackedWidget)

        # Step 1: Select Mode
        self.step1Widget = QtWidgets.QWidget()
        self.step1Layout = QtWidgets.QVBoxLayout(self.step1Widget)
        self.step1Layout.setSpacing(15)

        self.modeGroup = QtWidgets.QButtonGroup()

        self.importModeRadio = QtWidgets.QRadioButton("Import existing evidence files")
        self.importModeRadio.setChecked(True)
        self.importModeRadio.setStyleSheet("font-size: 14px; padding: 10px;")

        self.collectModeRadio = QtWidgets.QRadioButton("Collect evidence from system")
        self.collectModeRadio.setStyleSheet("font-size: 14px; padding: 10px;")

        self.modeGroup.addButton(self.importModeRadio, 0)
        self.modeGroup.addButton(self.collectModeRadio, 1)

        self.step1Layout.addWidget(self.importModeRadio)
        self.step1Layout.addWidget(self.collectModeRadio)
        self.step1Layout.addStretch()

        self.stackedWidget.addWidget(self.step1Widget)

        # Step 2: Evidence Type
        self.step2Widget = QtWidgets.QWidget()
        self.step2Layout = QtWidgets.QVBoxLayout(self.step2Widget)
        self.step2Layout.setSpacing(15)

        self.typeGroup = QtWidgets.QButtonGroup()

        self.volatileTypeRadio = QtWidgets.QRadioButton(
            "Volatile Data (Memory, Network, Processes, ...)"
        )
        self.volatileTypeRadio.setChecked(True)
        self.volatileTypeRadio.setStyleSheet("font-size: 14px; padding: 10px;")

        self.nonvolatileTypeRadio = QtWidgets.QRadioButton(
            "Non-volatile Data (Disk, Files, Registry, ...)"
        )
        self.nonvolatileTypeRadio.setStyleSheet("font-size: 14px; padding: 10px;")

        self.typeGroup.addButton(self.volatileTypeRadio, 0)
        self.typeGroup.addButton(self.nonvolatileTypeRadio, 1)

        self.step2Layout.addWidget(self.volatileTypeRadio)
        self.step2Layout.addWidget(self.nonvolatileTypeRadio)
        self.step2Layout.addStretch()

        self.stackedWidget.addWidget(self.step2Widget)

        # Step 3: Evidence Source (Dynamic based on mode selection)
        self.step3Widget = QtWidgets.QWidget()
        self.step3Layout = QtWidgets.QVBoxLayout(self.step3Widget)
        self.step3Layout.setSpacing(15)

        # For Import Mode: File selection
        self.importSourceFrame = QtWidgets.QFrame()
        self.importSourceLayout = QtWidgets.QVBoxLayout(self.importSourceFrame)

        # File list widget
        self.fileListWidget = QtWidgets.QListWidget()
        self.fileListWidget.setMinimumHeight(200)
        self.fileListWidget.setStyleSheet(
            """
            QListWidget {
                border: 2px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f3f4;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """
        )

        # File selection buttons
        self.fileButtonFrame = QtWidgets.QFrame()
        self.fileButtonLayout = QtWidgets.QHBoxLayout(self.fileButtonFrame)
        self.fileButtonLayout.setContentsMargins(0, 10, 0, 0)

        self.addFilesBtn = QtWidgets.QPushButton("Add Files")
        self.addFilesBtn.setStyleSheet(
            """
            QPushButton {
                background-color: #4299e1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3182ce;
            }
        """
        )

        self.removeFileBtn = QtWidgets.QPushButton("Remove Selected")
        self.removeFileBtn.setStyleSheet(
            """
            QPushButton {
                background-color: #e53e3e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c53030;
            }
        """
        )

        self.clearAllBtn = QtWidgets.QPushButton("Clear All")
        self.clearAllBtn.setStyleSheet(
            """
            QPushButton {
                background-color: #718096;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a5568;
            }
        """
        )

        spacer = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )

        self.fileButtonLayout.addWidget(self.addFilesBtn)
        self.fileButtonLayout.addWidget(self.removeFileBtn)
        self.fileButtonLayout.addWidget(self.clearAllBtn)
        self.fileButtonLayout.addItem(spacer)

        self.importSourceLayout.addWidget(QtWidgets.QLabel("Selected Evidence Files:"))
        self.importSourceLayout.addWidget(self.fileListWidget)
        self.importSourceLayout.addWidget(self.fileButtonFrame)

        # For Collect Mode: Volatile Collection Interface
        self.collectSourceFrame = QtWidgets.QFrame()
        self.collectSourceLayout = QtWidgets.QVBoxLayout(self.collectSourceFrame)

        '''
        # Collection status header
        self.volatileStatusLabel = QtWidgets.QLabel("🔴 Ready to collect volatile data")
        self.volatileStatusLabel.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #e53e3e;
                background-color: #fed7d7;
                border: 2px solid #fc8181;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
            }
        """)
        '''
        # Collection info
        self.volatileInfoLabel = QtWidgets.QLabel(
            "Volatile data collection will gather:\n\n"
            "- Memory dump\n"
            "- Running processes\n"
            "- Network connections\n"
            "- System information\n"
            "- System time & uptime\n\n"
            "Click 'Start Volatile Collection' to begin data collection.\n"
            "This will open the volatile collection interface."
        )
        self.volatileInfoLabel.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #2d3748;
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
                line-height: 1.5;
            }
        """
        )
        self.volatileInfoLabel.setWordWrap(True)

        # Collection button
        self.startVolatileBtn = QtWidgets.QPushButton("Start Volatile Collection")
        self.startVolatileBtn.setStyleSheet(
            """
            QPushButton {
                background-color: #3182ce;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c5aa0;
            }
            QPushButton:disabled {
                background-color: #e2e8f0;
                color: #a0aec0;
            }
        """
        )

        # self.collectSourceLayout.addWidget(self.volatileStatusLabel)
        self.collectSourceLayout.addWidget(self.volatileInfoLabel)
        self.collectSourceLayout.addWidget(self.startVolatileBtn)
        self.collectSourceLayout.addStretch()

        # Add both frames to step3
        self.step3Layout.addWidget(self.importSourceFrame)
        self.step3Layout.addWidget(self.collectSourceFrame)
        self.step3Layout.addStretch()

        # Initially show import source
        self.importSourceFrame.setVisible(True)
        self.collectSourceFrame.setVisible(False)

        self.stackedWidget.addWidget(self.step3Widget)

        # Step 4: Configure Evidence (Dynamic based on mode and previous selections)
        self.step4Widget = QtWidgets.QWidget()
        self.step4Layout = QtWidgets.QVBoxLayout(self.step4Widget)
        self.step4Layout.setSpacing(15)

        # For Import Mode: Configure imported files
        self.importConfigFrame = QtWidgets.QFrame()
        self.importConfigLayout = QtWidgets.QVBoxLayout(self.importConfigFrame)

        # Evidence collection configuration - no additional input needed

        # Processing options
        self.processingGroup = QtWidgets.QGroupBox("Processing Options")
        self.processingGroupLayout = QtWidgets.QVBoxLayout(self.processingGroup)

        self.calculateHashCheck = QtWidgets.QCheckBox("Calculate file hashes (SHA-256)")
        self.calculateHashCheck.setChecked(True)
        self.calculateHashCheck.setStyleSheet("font-size: 12px; padding: 5px;")

        self.verifyIntegrityCheck = QtWidgets.QCheckBox("Verify file integrity")
        self.verifyIntegrityCheck.setChecked(True)
        self.verifyIntegrityCheck.setStyleSheet("font-size: 12px; padding: 5px;")

        self.createBackupCheck = QtWidgets.QCheckBox("Create backup copies")
        self.createBackupCheck.setStyleSheet("font-size: 12px; padding: 5px;")

        self.processingGroupLayout.addWidget(self.calculateHashCheck)
        self.processingGroupLayout.addWidget(self.verifyIntegrityCheck)
        self.processingGroupLayout.addWidget(self.createBackupCheck)

        self.importConfigLayout.addWidget(self.processingGroup)
        self.importConfigLayout.addStretch()

        # For Collect Mode: Non-volatile Collection Interface
        self.collectConfigFrame = QtWidgets.QFrame()
        self.collectConfigLayout = QtWidgets.QVBoxLayout(self.collectConfigFrame)

        '''
        # Non-volatile status header
        self.nonvolatileStatusLabel = QtWidgets.QLabel(
            "🔵 Ready to collect non-volatile data"
        )
        self.nonvolatileStatusLabel.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #3182ce;
                background-color: #e6f3ff;
                border: 2px solid #63b3ed;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
            }
        """
        )
        '''
        # Non-volatile collection info
        self.nonvolatileInfoLabel = QtWidgets.QLabel(
            "Non-volatile data collection will gather:\n\n"
            "- Disk images\n"
            "- File system artifacts\n"
            "- Registry hives\n"
            "- Event logs\n"
            "- Browser artifacts\n"
            "- System logs\n\n"
            "Click 'Start Non-volatile Collection' to begin data collection.\n"
            "This will open the non-volatile collection interface."
        )
        self.nonvolatileInfoLabel.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #2d3748;
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
                line-height: 1.5;
            }
        """
        )
        self.nonvolatileInfoLabel.setWordWrap(True)

        # Non-volatile collection button
        self.startNonvolatileBtn = QtWidgets.QPushButton(
            "Start Non-volatile Collection"
        )
        self.startNonvolatileBtn.setStyleSheet(
            """
            QPushButton {
                background-color: #3182ce;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c5aa0;
            }
            QPushButton:disabled {
                background-color: #e2e8f0;
                color: #a0aec0;
            }
        """
        )

        #  self.collectConfigLayout.addWidget(self.nonvolatileStatusLabel)
        self.collectConfigLayout.addWidget(self.nonvolatileInfoLabel)
        self.collectConfigLayout.addWidget(self.startNonvolatileBtn)
        self.collectConfigLayout.addStretch()

        # Add both frames to step4
        self.step4Layout.addWidget(self.importConfigFrame)
        self.step4Layout.addWidget(self.collectConfigFrame)
        self.step4Layout.addStretch()

        # Initially show import config
        self.importConfigFrame.setVisible(True)
        self.collectConfigFrame.setVisible(False)

        self.stackedWidget.addWidget(self.step4Widget)

        # Bottom buttons
        self.buttonFrame = QtWidgets.QFrame()
        self.buttonFrame.setStyleSheet(
            """
            QFrame {
                border-top: 1px solid #dee2e6;
                background-color: #f8f9fa;
            }
        """
        )

        self.buttonLayout = QtWidgets.QHBoxLayout(self.buttonFrame)
        self.buttonLayout.setContentsMargins(30, 15, 30, 15)

        # Left side - Back button
        self.backBtn = QtWidgets.QPushButton("< Back")
        self.backBtn.setEnabled(False)

        # Right side buttons
        spacer = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )

        self.nextBtn = QtWidgets.QPushButton("Next >")
        self.finishBtn = QtWidgets.QPushButton("Finish")
        self.finishBtn.setVisible(False)
        self.cancelBtn = QtWidgets.QPushButton("Cancel")

        # Button styles
        button_style = """
            QPushButton {
                background-color: #4299e1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3182ce;
            }
            QPushButton:disabled {
                background-color: #e2e8f0;
                color: #a0aec0;
            }
        """

        cancel_style = """
            QPushButton {
                background-color: #e2e8f0;
                color: #4a5568;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #cbd5e0;
            }
        """

        self.backBtn.setStyleSheet(button_style)
        self.nextBtn.setStyleSheet(button_style)
        self.finishBtn.setStyleSheet(button_style)
        self.cancelBtn.setStyleSheet(cancel_style)

        self.buttonLayout.addWidget(self.backBtn)
        self.buttonLayout.addItem(spacer)
        self.buttonLayout.addWidget(self.nextBtn)
        self.buttonLayout.addWidget(self.finishBtn)
        self.buttonLayout.addWidget(self.cancelBtn)

        self.contentLayout.addWidget(self.buttonFrame)

        self.horizontalLayout.addWidget(self.contentFrame)

        QtCore.QMetaObject.connectSlotsByName(AddEvidenceWizard)
