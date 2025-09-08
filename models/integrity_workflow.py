"""
Example workflow for Evidence Integrity Verification using Timeline-based Hashes

This demonstrates how to use the hash system to track evidence integrity
throughout the forensic investigation process.
"""

import hashlib
import os
from models.db_manager import DatabaseManager
from models.hash_types import HashManager, HashTypes


class IntegrityWorkflow:
    """Example workflow for managing evidence integrity throughout investigation"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.db.connect()
        self.hash_manager = HashManager(self.db)
    
    def calculate_sha256(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            print(f"Error calculating hash: {e}")
            return ""
    
    def import_evidence_workflow(self, case_id: int, evidence_file_path: str, evidence_name: str):
        """Complete workflow for importing evidence with integrity tracking"""
        
        print(f"🔍 Starting evidence import workflow for: {evidence_name}")
        
        # Step 1: Calculate origin hash when first importing
        print("📋 Step 1: Calculating origin hash...")
        origin_hash = self.calculate_sha256(evidence_file_path)
        if not origin_hash:
            print("❌ Failed to calculate origin hash")
            return None
        
        print(f"✅ Origin SHA256: {origin_hash[:16]}...")
        
        # Step 2: Add evidence to database
        print("📋 Step 2: Adding evidence to database...")
        file_size = os.path.getsize(evidence_file_path)
        artifact_id = self.db.add_artifact(
            case_id=case_id,
            name=evidence_name,
            source_path=evidence_file_path,
            evidence_type="imported_evidence",
            size=file_size
        )
        
        if not artifact_id:
            print("❌ Failed to add evidence to database")
            return None
        
        # Step 3: Store origin hash
        print("📋 Step 3: Storing origin hash...")
        if self.hash_manager.add_origin_hash(artifact_id, origin_hash):
            print("✅ Origin hash stored successfully")
        else:
            print("❌ Failed to store origin hash")
            return None
        
        print(f"🎉 Evidence import completed! Artifact ID: {artifact_id}")
        return artifact_id
    
    def pre_analysis_verification(self, artifact_id: int, evidence_file_path: str):
        """Verify integrity before starting analysis"""
        
        print(f"🔍 Starting pre-analysis verification for artifact {artifact_id}")
        
        # Step 1: Calculate current hash
        print("📋 Step 1: Calculating current hash...")
        current_hash = self.calculate_sha256(evidence_file_path)
        if not current_hash:
            print("❌ Failed to calculate current hash")
            return False
        
        print(f"✅ Current SHA256: {current_hash[:16]}...")
        
        # Step 2: Compare with origin hash
        print("📋 Step 2: Verifying integrity...")
        if self.hash_manager.verify_evidence_integrity(artifact_id, current_hash):
            print("✅ Integrity verified - evidence unchanged")
            
            # Step 3: Store pre-analysis hash
            print("📋 Step 3: Storing pre-analysis hash...")
            if self.hash_manager.add_pre_analysis_hash(artifact_id, current_hash):
                print("✅ Pre-analysis hash stored")
                return True
            else:
                print("❌ Failed to store pre-analysis hash")
                return False
        else:
            print("❌ INTEGRITY VIOLATION - Evidence may have been tampered with!")
            print("🚨 Investigation should be halted for review")
            return False
    
    def pre_report_verification(self, artifact_id: int, evidence_file_path: str):
        """Verify integrity before generating report"""
        
        print(f"🔍 Starting pre-report verification for artifact {artifact_id}")
        
        # Calculate current hash
        current_hash = self.calculate_sha256(evidence_file_path)
        if not current_hash:
            print("❌ Failed to calculate current hash")
            return False
        
        # Verify integrity
        if self.hash_manager.verify_evidence_integrity(artifact_id, current_hash):
            print("✅ Integrity verified for report generation")
            
            # Store pre-report hash
            if self.hash_manager.add_pre_report_hash(artifact_id, current_hash):
                print("✅ Pre-report hash stored")
                return True
            else:
                print("❌ Failed to store pre-report hash")
                return False
        else:
            print("❌ INTEGRITY VIOLATION before report generation!")
            return False
    
    def post_analysis_verification(self, artifact_id: int, evidence_file_path: str):
        """Verify integrity after analysis is complete"""
        
        print(f"🔍 Starting post-analysis verification for artifact {artifact_id}")
        
        # Calculate current hash
        current_hash = self.calculate_sha256(evidence_file_path)
        if not current_hash:
            print("❌ Failed to calculate current hash")
            return False
        
        # Verify integrity
        if self.hash_manager.verify_evidence_integrity(artifact_id, current_hash):
            print("✅ Evidence integrity maintained throughout analysis")
            
            # Store post-analysis hash
            if self.hash_manager.add_post_analysis_hash(artifact_id, current_hash):
                print("✅ Post-analysis hash stored")
                return True
            else:
                print("❌ Failed to store post-analysis hash")
                return False
        else:
            print("❌ INTEGRITY VIOLATION detected after analysis!")
            return False
    
    def get_integrity_timeline(self, artifact_id: int):
        """Get complete integrity timeline for an artifact"""
        print(f"📊 Integrity Timeline for Artifact {artifact_id}")
        print("=" * 50)
        
        hashes = self.hash_manager.get_hash_history(artifact_id)
        
        if not hashes:
            print("No hash records found")
            return
        
        # Sort by generated_at
        sorted_hashes = sorted(hashes, key=lambda x: x['generated_at'])
        
        for hash_record in sorted_hashes:
            hash_type = hash_record['hash_type']
            hash_value = hash_record['sha256']
            timestamp = hash_record['generated_at']
            description = HashTypes.get_description(hash_type)
            
            print(f"⏰ {timestamp}")
            print(f"   📋 Type: {hash_type}")
            print(f"   📝 Description: {description}")
            print(f"   🔐 Hash: {hash_value[:16]}...")
            print()


# Example usage
def example_forensic_workflow():
    """Example of complete forensic workflow with integrity tracking"""
    
    workflow = IntegrityWorkflow()
    
    # Simulate evidence import
    case_id = 1
    evidence_file = "example_evidence.txt"
    
    print("🚀 FORENSIC INVESTIGATION WORKFLOW")
    print("=" * 50)
    
    # Phase 1: Evidence Collection/Import
    print("\n📁 PHASE 1: EVIDENCE COLLECTION")
    artifact_id = workflow.import_evidence_workflow(case_id, evidence_file, "Example Evidence")
    
    if not artifact_id:
        return
    
    # Phase 2: Pre-Analysis Verification
    print("\n🔍 PHASE 2: PRE-ANALYSIS VERIFICATION")
    if not workflow.pre_analysis_verification(artifact_id, evidence_file):
        return
    
    print("\n⚗️ [ANALYSIS PHASE - Tools would run here]")
    print("   • Registry Analysis")
    print("   • File Analysis")  
    print("   • Memory Analysis")
    
    # Phase 3: Pre-Report Verification
    print("\n📋 PHASE 3: PRE-REPORT VERIFICATION")
    if not workflow.pre_report_verification(artifact_id, evidence_file):
        return
    
    print("\n📄 [REPORT GENERATION - Reports would be created here]")
    
    # Phase 4: Post-Analysis Verification
    print("\n✅ PHASE 4: POST-ANALYSIS VERIFICATION")
    workflow.post_analysis_verification(artifact_id, evidence_file)
    
    # Phase 5: Review Timeline
    print("\n📊 PHASE 5: INTEGRITY TIMELINE REVIEW")
    workflow.get_integrity_timeline(artifact_id)
    
    print("🎉 Forensic investigation workflow completed!")


if __name__ == "__main__":
    example_forensic_workflow() 