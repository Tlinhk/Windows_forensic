"""
Hash Types and Purposes for Digital Forensics Evidence Management

This module defines the various hash types used throughout the forensic investigation process
to ensure evidence integrity and chain of custody.
"""

class HashTypes:
    """Constants for different hash types/purposes in forensic workflow"""
    
    # Timeline-based hash types for integrity verification
    ORIGIN = "origin"                    # Hash when evidence is first collected/imported
    PRE_ANALYSIS = "pre_analysis"       # Hash calculated before starting analysis
    PRE_REPORT = "pre_report"           # Hash calculated before generating report
    POST_ANALYSIS = "post_analysis"     # Hash taken after analysis is complete
    
    # Verification checkpoints
    INTEGRITY_CHECK = "integrity_check"  # General integrity verification
    VERIFICATION = "verification"        # Manual verification checkpoint
    
    # Processing stages
    BACKUP = "backup"                   # Hash of backup copies
    ARCHIVE = "archive"                 # Hash for long-term archival
    DUPLICATE = "duplicate"             # Hash of duplicated evidence
    
    # Quality assurance
    QA_CHECK = "qa_check"              # Quality assurance verification
    AUDIT = "audit"                    # Audit trail purposes
    
    @classmethod
    def get_all_types(cls):
        """Get all available hash types"""
        return [
            cls.ORIGIN, cls.PRE_ANALYSIS, cls.PRE_REPORT, cls.POST_ANALYSIS,
            cls.INTEGRITY_CHECK, cls.VERIFICATION,
            cls.BACKUP, cls.ARCHIVE, cls.DUPLICATE,
            cls.QA_CHECK, cls.AUDIT
        ]
    
    @classmethod
    def get_timeline_types(cls):
        """Get hash types used for timeline tracking"""
        return [cls.ORIGIN, cls.PRE_ANALYSIS, cls.PRE_REPORT, cls.POST_ANALYSIS]
    
    @classmethod
    def get_verification_types(cls):
        """Get hash types used for verification"""
        return [cls.INTEGRITY_CHECK, cls.VERIFICATION, cls.QA_CHECK, cls.AUDIT]
    
    @classmethod
    def get_description(cls, hash_type):
        """Get human-readable description of hash type"""
        descriptions = {
            cls.ORIGIN: "Original evidence hash (when first collected)",
            cls.PRE_ANALYSIS: "Hash calculated before analysis",
            cls.PRE_REPORT: "Hash calculated before report generation",
            cls.POST_ANALYSIS: "Hash calculated after analysis",
            cls.INTEGRITY_CHECK: "Integrity verification hash",
            cls.VERIFICATION: "Manual verification hash",
            cls.BACKUP: "Backup copy hash",
            cls.ARCHIVE: "Archive storage hash",
            cls.DUPLICATE: "Duplicate evidence hash",
            cls.QA_CHECK: "Quality assurance hash",
            cls.AUDIT: "Audit trail hash"
        }
        return descriptions.get(hash_type, "Unknown hash type")


class HashManager:
    """Helper class for managing evidence hashes"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def add_origin_hash(self, artifact_id: int, sha256_hash: str):
        """Add origin SHA256 hash for a new artifact"""
        return self.db.add_hash(artifact_id, HashTypes.ORIGIN, sha256_hash)
    
    def add_pre_analysis_hash(self, artifact_id: int, sha256_hash: str):
        """Add SHA256 hash before analysis starts"""
        return self.db.add_hash(artifact_id, HashTypes.PRE_ANALYSIS, sha256_hash)
    
    def add_pre_report_hash(self, artifact_id: int, sha256_hash: str):
        """Add SHA256 hash before report generation"""
        return self.db.add_hash(artifact_id, HashTypes.PRE_REPORT, sha256_hash)
    
    def add_post_analysis_hash(self, artifact_id: int, sha256_hash: str):
        """Add SHA256 hash after analysis is complete"""
        return self.db.add_hash(artifact_id, HashTypes.POST_ANALYSIS, sha256_hash)
    
    def verify_evidence_integrity(self, artifact_id: int, current_sha256_hash: str):
        """Verify evidence hasn't been tampered with by comparing with origin hash"""
        origin_hash = self.db.get_origin_hash(artifact_id)
        return origin_hash == current_sha256_hash if origin_hash else False
    
    def add_integrity_check(self, artifact_id: int, current_hash: str):
        """Add integrity check hash before analysis"""
        return self.db.add_hash(artifact_id, HashTypes.INTEGRITY_CHECK, current_hash)
    
    def get_hash_history(self, artifact_id: int):
        """Get complete hash history for an artifact"""
        return self.db.get_artefact_hashes(artifact_id)
    
    def get_latest_hash(self, artifact_id: int, purpose: str = None):
        """Get the most recent hash for a specific purpose"""
        if purpose:
            hashes = self.db.fetch_all(
                "SELECT * FROM Hashes WHERE artefact_id = ? AND hash_type = ? ORDER BY generated_at DESC LIMIT 1",
                (artifact_id, purpose)
            )
        else:
            hashes = self.db.fetch_all(
                "SELECT * FROM Hashes WHERE artefact_id = ? ORDER BY generated_at DESC LIMIT 1",
                (artifact_id,)
            )
        return hashes[0] if hashes else None 