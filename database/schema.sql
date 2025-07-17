-- Windows Forensic System Database Schema
-- Based on provided ERD diagram

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'INVESTIGATOR',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP

);

-- Cases table (simplified with single investigator)
CREATE TABLE Cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    archive_path TEXT, 
    user_id INTEGER,
    status VARCHAR(20) DEFAULT 'OPEN',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

-- Artefacts table
CREATE TABLE Artefacts (
    artefact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    evidence_type VARCHAR(50),
    name VARCHAR(200) NOT NULL,
    source_path TEXT,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    size INTEGER,
    mime_type VARCHAR(100),
    is_deleted BOOLEAN DEFAULT 0,
    FOREIGN KEY (case_id) REFERENCES Cases(case_id) ON DELETE CASCADE
);

-- Hashes table
CREATE TABLE Hashes (
    hash_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artefact_id INTEGER NOT NULL,
    hash_type VARCHAR(10) NOT NULL,
    sha256 VARCHAR(64),
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    generated_by INTEGER,
    FOREIGN KEY (artefact_id) REFERENCES Artefacts(artefact_id) ON DELETE CASCADE,
    FOREIGN KEY (generated_by) REFERENCES Users(user_id)
);

-- Results table
CREATE TABLE Results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artefact_id INTEGER NOT NULL,
    tool_used VARCHAR(100),
    run_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    summary TEXT,
    result_path TEXT,
    FOREIGN KEY (artefact_id) REFERENCES Artefacts(artefact_id) ON DELETE CASCADE
);

-- Reports table
CREATE TABLE Reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    file_path TEXT,
    format VARCHAR(10) DEFAULT 'PDF',
    generated_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sha256 VARCHAR(64),
    FOREIGN KEY (case_id) REFERENCES Cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (generated_by) REFERENCES Users(user_id)
);

-- Activity_logs table
CREATE TABLE Activity_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artefact_id INTEGER,
    case_id INTEGER,
    user_id INTEGER,
    action VARCHAR(50) NOT NULL,
    details TEXT, -- Added details column
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tool_used VARCHAR(100),
    FOREIGN KEY (artefact_id) REFERENCES Artefacts(artefact_id),
    FOREIGN KEY (case_id) REFERENCES Cases(case_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

-- Create indexes for better performance
CREATE INDEX idx_case_status ON Cases(status);
CREATE INDEX idx_case_created ON Cases(created_at);
CREATE INDEX idx_case_investigator ON Cases(user_id);
CREATE INDEX idx_artefacts_case ON Artefacts(case_id);
CREATE INDEX idx_artefacts_type ON Artefacts(evidence_type);
CREATE INDEX idx_hashes_artefact ON Hashes(artefact_id);
CREATE INDEX idx_hashes_sha256 ON Hashes(sha256);
CREATE INDEX idx_results_artefact ON Results(artefact_id);
CREATE INDEX idx_reports_case ON Reports(case_id);
CREATE INDEX idx_reports_sha256 ON Reports(sha256);
CREATE INDEX idx_activity_case ON Activity_logs(case_id);
CREATE INDEX idx_activity_user ON Activity_logs(user_id);
CREATE INDEX idx_activity_timestamp ON Activity_logs(timestamp);

-- Insert default admin user (password: admin123)
INSERT INTO Users (username, password_hash, full_name, phone_number, email, role, is_active) VALUES 
('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'Hà Thùy Linh','0357857581','halinh9716@gmail.com', 'ADMIN', 1);