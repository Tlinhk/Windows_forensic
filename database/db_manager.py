import sqlite3
import hashlib
import os
import traceback
from typing import List, Dict, Optional
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Sử dụng utility để lấy đường dẫn database
            from utils.path_utils import get_database_path
            self.db_path = get_database_path()
        else:
            self.db_path = db_path
        self.connection = None
        self.current_user_id = None

    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            # Enable foreign key constraints
            self.connection.execute("PRAGMA foreign_keys = ON")
            return True
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return False

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def initialize_database(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

        if not os.path.exists(schema_path):
            print("Schema file not found!")
            return False

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            self.connection.executescript(schema_sql)
            self.connection.commit()
            print("Database initialized successfully!")
            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

    def execute_query(self, query: str, params: tuple = None):
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor
        except sqlite3.Error as e:
            print(f"Query execution error: {e}")
            traceback.print_exc()
            return None

    def fetch_all(self, query: str, params: tuple = None) -> List[Dict]:
        cursor = self.execute_query(query, params)
        if cursor:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        return []

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Fetch single result from query"""
        cursor = self.execute_query(query, params)
        if cursor:
            row = cursor.fetchone()
            return dict(row) if row else None
        return None

    # ==================== USER MANAGEMENT ====================

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password_hash: str, password: str) -> bool:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return password_hash == hashed

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        query = """
            SELECT user_id, username, password_hash, full_name, email, role, is_active 
            FROM Users 
            WHERE username = ? AND is_active = 1
        """
        user = self.fetch_one(query, (username,))

        if user and self.verify_password(user["password_hash"], password):
            self.current_user_id = user["user_id"]
            # Log activity
            self.log_activity(action="LOGIN", user_id=user["user_id"])
            # Remove password_hash from returned dict
            user.pop("password_hash", None)
            return user
        return None

    def create_user(
        self,
        username: str,
        password: str,
        email: str,
        role: str = "ANALYST",
        full_name: str = "",
        phone_number: str = "",
    ) -> bool:

        hashed_password = self.hash_password(password)

        # Nếu không có full_name, dùng username làm mặc định
        if not full_name.strip():
            full_name = username

        query = """
            INSERT INTO Users (username, password_hash, full_name, phone_number, email, role)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute_query(
            query, (username, hashed_password, full_name, phone_number, email, role)
        )
        return cursor is not None

    def update_user(
        self,
        user_id: int,
        username: str = None,
        email: str = None,
        role: str = None,
        is_active: bool = None,
    ) -> bool:
        """
        Cập nhật thông tin người dùng

        Args:
            user_id: ID của người dùng cần cập nhật
            username: Tên đăng nhập mới (nếu cần cập nhật)
            email: Địa chỉ email mới (nếu cần cập nhật)
            role: Vai trò mới (nếu cần cập nhật)
            is_active: Trạng thái hoạt động (nếu cần cập nhật)

        Returns:
            bool: True nếu cập nhật thành công, False nếu thất bại
        """
        try:
            updates = []
            params = []

            print(
                f"update_user called with: user_id={user_id}, username={username}, email={email}, role={role}, is_active={is_active}"
            )

            if username is not None:
                # Kiểm tra xem username mới đã tồn tại chưa (nếu khác với username hiện tại)
                check_query = (
                    "SELECT username FROM Users WHERE user_id != ? AND username = ?"
                )
                existing = self.fetch_one(check_query, (user_id, username))
                if existing:
                    print(f"Username {username} already exists")
                    return False
                updates.append("username = ?")
                params.append(username)
            if email is not None:
                updates.append("email = ?")
                params.append(email)
            if role is not None:
                updates.append("role = ?")
                params.append(role)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(
                    1 if is_active else 0
                )  # SQLite sử dụng 1 và 0 cho boolean

            if not updates:
                print("No updates specified")
                return False

            params.append(user_id)
            query = f"UPDATE Users SET {', '.join(updates)} WHERE user_id = ?"
            print(f"Executing query: {query} with params: {params}")

            cursor = self.execute_query(query, tuple(params))
            result = cursor is not None
            print(f"Update result: {result}")
            return result
        except Exception as e:
            print(f"Error in update_user: {e}")
            traceback.print_exc()
            return False

    def get_users(self) -> List[Dict]:
        query = "SELECT user_id, username, full_name, phone_number, email, role, is_active, created_at FROM Users"
        return self.fetch_all(query)

    def delete_user(self, user_id: int) -> bool:
        """
        Xóa user (soft delete) - chỉ set is_active = 0
        Không thể xóa user cuối cùng có role ADMIN
        """
        try:
            # Kiểm tra user tồn tại
            user = self.fetch_one(
                "SELECT user_id, username, role, is_active FROM Users WHERE user_id = ?",
                (user_id,),
            )
            if not user:
                print(f"User ID {user_id} không tồn tại")
                return False

            # Kiểm tra nếu đang xóa admin cuối cùng
            if user["role"] == "ADMIN":
                admin_count = self.fetch_one(
                    "SELECT COUNT(*) as count FROM Users WHERE role = 'ADMIN' AND is_active = 1"
                )
                if admin_count["count"] <= 1:
                    print("Không thể xóa admin cuối cùng trong hệ thống!")
                    return False

            # Kiểm tra nếu user đang được assign vào case
            case_assignments = self.fetch_one(
                "SELECT COUNT(*) as count FROM Case_Assignees WHERE user_id = ?",
                (user_id,),
            )
            if case_assignments["count"] > 0:
                print(
                    f"Không thể xóa user '{user['username']}' vì đang được gán vào {case_assignments['count']} case(s)!"
                )
                return False

            # Soft delete
            success = self.update_user(user_id, is_active=False)
            if success:
                print(f"Đã xóa user '{user['username']}' thành công")
                # Log activity
                self.log_activity(action="DELETE_USER", user_id=user_id)
            return success

        except Exception as e:
            print(f"Lỗi khi xóa user: {e}")
            traceback.print_exc()
            return False

    def hard_delete_user(self, user_id: int) -> bool:
        """
        Xóa vĩnh viễn user khỏi database (hard delete)
        ⚠️ CẢNH BÁO: Thao tác này KHÔNG THỂ HOÀN TÁC!
        """
        try:
            # Kiểm tra user tồn tại
            user = self.fetch_one(
                "SELECT user_id, username, role, is_active FROM Users WHERE user_id = ?",
                (user_id,),
            )
            if not user:
                print(f"User ID {user_id} không tồn tại")
                return False

            print(f"🔄 Bắt đầu hard delete user '{user['username']}'...")

            # Kiểm tra nếu đang xóa admin cuối cùng
            if user["role"] == "ADMIN":
                admin_count = self.fetch_one(
                    "SELECT COUNT(*) as count FROM Users WHERE role = 'ADMIN'"
                )
                if admin_count["count"] <= 1:
                    print("⚠️ KHÔNG THỂ XÓA ADMIN CUỐI CÙNG!")
                    return False

            # Kiểm tra nếu user đang được assign vào case
            case_assignments = self.fetch_one(
                "SELECT COUNT(*) as count FROM Case_Assignees WHERE user_id = ?",
                (user_id,),
            )
            if case_assignments["count"] > 0:
                print(
                    f"⚠️ User '{user['username']}' đang được gán vào {case_assignments['count']} case(s)!"
                )
                print("Cần remove khỏi tất cả cases trước khi hard delete!")
                return False

            # Kiểm tra activity logs trước khi xóa
            activity_count = self.fetch_one(
                "SELECT COUNT(*) as count FROM Activity_logs WHERE user_id = ?",
                (user_id,),
            )
            activity_logs_count = activity_count["count"] if activity_count else 0

            if activity_logs_count > 0:
                print(
                    f"⚠️ User '{user['username']}' có {activity_logs_count} activity logs!"
                )
                print("Logs sẽ bị mất vĩnh viễn sau khi hard delete!")

            # Log trước khi xóa (để ghi lại việc hard delete)
            self.log_activity(
                action="HARD_DELETE_USER",
                user_id=user_id,
                details=f"Hard delete user '{user['username']}' with role '{user['role']}'",
            )

            # Bắt đầu transaction để đảm bảo tính toàn vẹn
            self.connection.execute("BEGIN TRANSACTION")

            try:
                # 1. Xóa activity logs của user (sửa tên bảng đúng)
                print(f"🔄 Đang xóa {activity_logs_count} activity logs...")
                delete_logs_cursor = self.connection.execute(
                    "DELETE FROM Activity_logs WHERE user_id = ?", (user_id,)
                )
                logs_deleted = delete_logs_cursor.rowcount
                print(f"✅ Đã xóa {logs_deleted} activity logs")

                # 2. Xóa case assignments (nếu có)
                print("🔄 Đang xóa case assignments...")
                delete_assignments_cursor = self.connection.execute(
                    "DELETE FROM Case_Assignees WHERE user_id = ?", (user_id,)
                )
                assignments_deleted = delete_assignments_cursor.rowcount
                print(f"✅ Đã xóa {assignments_deleted} case assignments")

                # 3. Xóa user khỏi bảng Users
                print("🔄 Đang xóa user khỏi Users table...")
                delete_user_cursor = self.connection.execute(
                    "DELETE FROM Users WHERE user_id = ?", (user_id,)
                )
                users_deleted = delete_user_cursor.rowcount

                if users_deleted > 0:
                    # Commit transaction
                    self.connection.commit()
                    print(f"💀 Đã XÓA VĨNH VIỄN user '{user['username']}'!")
                    print(f"📊 Thống kê xóa:")
                    print(f"   • User: {users_deleted}")
                    print(f"   • Activity logs: {logs_deleted}")
                    print(f"   • Case assignments: {assignments_deleted}")
                    print("⚠️ Tất cả dữ liệu liên quan đã bị mất không thể khôi phục!")
                    return True
                else:
                    # Rollback nếu không xóa được user
                    self.connection.rollback()
                    print(
                        f"❌ Không thể xóa user '{user['username']}' khỏi Users table"
                    )
                    return False

            except Exception as e:
                # Rollback transaction nếu có lỗi
                self.connection.rollback()
                print(f"❌ Lỗi trong transaction: {e}")
                return False

        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng khi hard delete user: {e}")
            return False

    # ==================== CASE MANAGEMENT ====================

    def create_case(
        self,
        title: str,
        status: str = "OPEN",
        archive_path: str = "",
        user_id: int = None,
    ) -> Optional[int]:
        # Use current user as investigator if not specified
        if user_id is None:
            user_id = self.current_user_id

        query = """
            INSERT INTO Cases (title, status, archive_path, user_id)
            VALUES (?, ?, ?, ?)
        """
        cursor = self.execute_query(query, (title, status, archive_path, user_id))
        if cursor:
            case_id = cursor.lastrowid
            self.log_activity(case_id=case_id, action="CREATE_CASE")
            return case_id
        return None

    def delete_case(self, case_id: int) -> bool:
        """Xóa case và tất cả data liên quan"""
        try:
            # Xóa artifacts
            self.execute_query("DELETE FROM Artefacts WHERE case_id = ?", (case_id,))
            # Xóa activity logs
            self.execute_query(
                "DELETE FROM Activity_logs WHERE case_id = ?", (case_id,)
            )
            # Xóa reports
            self.execute_query("DELETE FROM Reports WHERE case_id = ?", (case_id,))
            # Xóa case
            cursor = self.execute_query(
                "DELETE FROM Cases WHERE case_id = ?", (case_id,)
            )
            return cursor is not None
        except Exception as e:
            print(f"Error deleting case: {e}")
            return False

    def get_artefact_hashes(self, artefact_id: int) -> List[Dict]:
        """Lấy tất cả hash của một artefact"""
        query = "SELECT * FROM Hashes WHERE artefact_id = ?"
        return self.fetch_all(query, (artefact_id,))

    def get_cases(self, status: str = None) -> List[Dict]:
        """Get all cases or filter by status"""
        if status:
            query = "SELECT * FROM Cases WHERE status = ? ORDER BY created_at DESC"
            return self.fetch_all(query, (status,))
        else:
            query = "SELECT * FROM Cases ORDER BY created_at DESC"
            return self.fetch_all(query)

    def get_case_by_id(self, case_id: int) -> Optional[Dict]:
        query = "SELECT * FROM Cases WHERE case_id = ?"
        return self.fetch_one(query, (case_id,))

    def update_case(self, case_id: int, title: str = None, status: str = None) -> bool:
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return False

        params.append(case_id)
        query = f"UPDATE Cases SET {', '.join(updates)} WHERE case_id = ?"
        cursor = self.execute_query(query, tuple(params))
        return cursor is not None

    # ==================== SIMPLIFIED CASE-INVESTIGATOR RELATIONSHIP ====================

    def get_cases_by_investigator(self, user_id: int) -> List[Dict]:
        """Lấy danh sách cases của một investigator"""
        query = """
            SELECT c.*, u.username, u.full_name 
            FROM Cases c
            LEFT JOIN Users u ON c.user_id = u.user_id
            WHERE c.user_id = ?
            ORDER BY c.created_at DESC
        """
        return self.fetch_all(query, (user_id,))

    def update_case_investigator(self, case_id: int, user_id: int) -> bool:
        """Cập nhật investigator của case"""
        query = "UPDATE Cases SET user_id = ? WHERE case_id = ?"
        cursor = self.execute_query(query, (user_id, case_id))
        if cursor:
            self.log_activity(
                case_id=case_id, user_id=user_id, action="ASSIGN_INVESTIGATOR"
            )
            return True
        return False

    def get_case_with_investigator(self, case_id: int) -> Optional[Dict]:
        """Lấy thông tin case và tên của investigator"""
        query = """
            SELECT c.*, u.full_name 
            FROM Cases c 
            LEFT JOIN Users u ON c.user_id = u.user_id 
            WHERE c.case_id = ?
        """
        return self.fetch_one(query, (case_id,))

    def get_all_cases_details(self) -> List[Dict]:
        """
        Lấy tất cả các case với thông tin chi tiết: tên investigator, số lượng evidence, và đường dẫn.
        Sử dụng một câu lệnh JOIN hiệu quả.
        """
        query = """
            SELECT 
                c.case_id, 
                c.title, 
                c.status, 
                c.created_at,
                c.archive_path, 
                u.full_name AS investigator_name,
                (SELECT COUNT(a.artefact_id) FROM Artefacts a WHERE a.case_id = c.case_id AND a.is_deleted = 0) AS evidence_count
            FROM 
                Cases c
            LEFT JOIN 
                Users u ON c.user_id = u.user_id
            ORDER BY 
                c.created_at DESC;
        """
        return self.fetch_all(query)

    # ==================== ARTIFACT MANAGEMENT ====================

    def add_artifact(
        self,
        case_id: int,
        name: str,
        source_path: str,
        evidence_type: str,
        size: int = None,
        mime_type: str = None,
    ) -> Optional[int]:
        query = """
            INSERT INTO Artefacts (case_id, name, source_path, evidence_type, size, mime_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute_query(
            query, (case_id, name, source_path, evidence_type, size, mime_type)
        )
        if cursor:
            artifact_id = cursor.lastrowid
            self.log_activity(
                case_id=case_id, artefact_id=artifact_id, action="COLLECT_EVIDENCE"
            )
            return artifact_id
        return None

    def get_artifacts_by_case(self, case_id: int) -> List[Dict]:
        query = "SELECT * FROM Artefacts WHERE case_id = ? AND is_deleted = 0 ORDER BY collected_at DESC"
        return self.fetch_all(query, (case_id,))

    def get_deleted_artifacts_by_case(self, case_id: int) -> List[Dict]:
        """Get soft-deleted artifacts for audit purposes (admin only)"""
        query = "SELECT * FROM Artefacts WHERE case_id = ? AND is_deleted = 1 ORDER BY collected_at DESC"
        return self.fetch_all(query, (case_id,))

    def restore_artifact(self, artifact_id: int) -> bool:
        """Restore a soft-deleted artifact (admin only)"""
        try:
            query = "UPDATE Artefacts SET is_deleted = 0 WHERE artefact_id = ?"
            cursor = self.execute_query(query, (artifact_id,))

            if cursor:
                # Log the restoration activity
                self.log_activity(artefact_id=artifact_id, action="RESTORE_EVIDENCE")
                return True
            return False
        except Exception as e:
            print(f"Error restoring artifact: {e}")
            return False

    def delete_artifact(self, artifact_id: int) -> bool:
        """Soft delete artifact following forensic best practices"""
        try:
            # Soft delete the artifact (preserves original data for audit)
            query = "UPDATE Artefacts SET is_deleted = 1 WHERE artefact_id = ?"
            cursor = self.execute_query(query, (artifact_id,))

            if cursor:
                # Clean up hashes since artifact is logically "deleted" from user view
                # But keep them in a way that can be restored if needed for legal purposes
                hash_query = "DELETE FROM Hashes WHERE artefact_id = ?"
                self.execute_query(hash_query, (artifact_id,))

                # Log the deletion activity for audit trail
                self.log_activity(artefact_id=artifact_id, action="DELETE_EVIDENCE")
                return True
            return False
        except Exception as e:
            print(f"Error deleting artifact: {e}")
            return False

    # ==================== HASH MANAGEMENT ====================

    def add_hash(self, artifact_id: int, hash_type: str, hash_value: str) -> bool:
        """
        Add hash for an artifact

        Args:
            artifact_id: ID of the artifact
            hash_type: Purpose/type of hash (e.g., 'origin', 'integrity_check', 'verification', 'backup')
            hash_value: The actual hash value (SHA256, MD5, SHA1, etc.)

        Note:
            - hash_type indicates the PURPOSE of the hash (when/why it was calculated)
            - sha256 column stores the actual hash value regardless of algorithm used
        """
        query = """
            INSERT INTO Hashes (artefact_id, hash_type, sha256, generated_by)
            VALUES (?, ?, ?, ?)
        """
        cursor = self.execute_query(
            query, (artifact_id, hash_type, hash_value, self.current_user_id)
        )
        return cursor is not None

    def get_hash_by_artifact(
        self, artifact_id: int, hash_type: str = None
    ) -> Optional[Dict]:
        """Get hash by artifact ID and optionally filter by hash_type"""
        if hash_type:
            query = "SELECT * FROM Hashes WHERE artefact_id = ? AND hash_type = ?"
            return self.fetch_one(query, (artifact_id, hash_type))
        else:
            query = "SELECT * FROM Hashes WHERE artefact_id = ?"
            return self.fetch_one(query, (artifact_id,))

    def get_origin_hash(self, artifact_id: int) -> Optional[str]:
        """Get the original hash value for integrity verification"""
        result = self.get_hash_by_artifact(artifact_id, "origin")
        return result["sha256"] if result else None

    def add_integrity_check_hash(self, artifact_id: int, hash_value: str) -> bool:
        """Add integrity check hash to verify evidence hasn't been tampered with"""
        return self.add_hash(artifact_id, "integrity_check", hash_value)

    def verify_integrity(self, artifact_id: int, current_hash: str) -> bool:
        """Verify evidence integrity by comparing with origin hash"""
        origin_hash = self.get_origin_hash(artifact_id)
        if not origin_hash:
            return False
        return origin_hash == current_hash

    # ==================== ANALYSIS RESULTS ====================

    def add_analysis_result(
        self, artifact_id: int, tool_used: str, summary: str, result_path: str = None
    ) -> Optional[int]:
        query = """
            INSERT INTO Results (artefact_id, tool_used, summary, result_path)
            VALUES (?, ?, ?, ?)
        """
        cursor = self.execute_query(
            query, (artifact_id, tool_used, summary, result_path)
        )
        if cursor:
            result_id = cursor.lastrowid
            self.log_activity(
                artefact_id=artifact_id, action="ANALYZE", tool_used=tool_used
            )
            return result_id
        return None

    def get_results_by_artifact(self, artifact_id: int) -> List[Dict]:
        query = "SELECT * FROM Results WHERE artefact_id = ? ORDER BY run_at DESC"
        return self.fetch_all(query, (artifact_id,))

    def get_results_by_case(self, case_id: int) -> List[Dict]:
        """Get all analysis results for a specific case"""
        query = """
            SELECT r.*, a.name as artifact_name, a.evidence_type
            FROM Results r
            JOIN Artefacts a ON r.artefact_id = a.artefact_id
            WHERE a.case_id = ? AND a.is_deleted = 0
            ORDER BY r.run_at DESC
        """
        return self.fetch_all(query, (case_id,))

    # ==================== REPORTS ====================

    def create_report(
        self, case_id: int, file_path: str, format: str = "PDF", sha256: str = None
    ) -> Optional[int]:
        query = """
            INSERT INTO Reports (case_id, file_path, format, generated_by, sha256)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor = self.execute_query(
            query, (case_id, file_path, format, self.current_user_id, sha256)
        )
        if cursor:
            report_id = cursor.lastrowid
            self.log_activity(case_id=case_id, action="GENERATE_REPORT")
            return report_id
        return None

    def get_reports_by_case(self, case_id: int) -> List[Dict]:
        query = "SELECT * FROM Reports WHERE case_id = ? ORDER BY created_at DESC"
        return self.fetch_all(query, (case_id,))

    # ==================== ACTIVITY LOGGING ====================

    def log_activity(
        self,
        action: str,
        case_id: int = None,
        artefact_id: int = None,
        user_id: int = None,
        tool_used: str = None,
    ) -> bool:
        # Use current_user_id if user_id not specified
        if user_id is None:
            user_id = self.current_user_id

        # Skip logging if no user_id
        if user_id is None:
            return True

        query = """
            INSERT INTO Activity_logs (case_id, artefact_id, user_id, action, tool_used)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor = self.execute_query(
            query, (case_id, artefact_id, user_id, action, tool_used)
        )
        return cursor is not None

    def get_activity_logs(self, case_id: int = None, limit: int = 100) -> List[Dict]:
        if case_id:
            query = """
                SELECT a.*, u.username 
                FROM Activity_logs a
                LEFT JOIN Users u ON a.user_id = u.user_id
                WHERE a.case_id = ? 
                ORDER BY a.timestamp DESC 
                LIMIT ?
            """
            return self.fetch_all(query, (case_id, limit))
        else:
            query = """
                SELECT a.*, u.username 
                FROM Activity_logs a
                LEFT JOIN Users u ON a.user_id = u.user_id
                ORDER BY a.timestamp DESC 
                LIMIT ?
            """
            return self.fetch_all(query, (limit,))

    # ==================== UTILITY METHODS ====================

    def set_current_user(self, user_id: int):
        self.current_user_id = user_id

    def backup_database(self, backup_path: str) -> bool:
        try:
            backup = sqlite3.connect(backup_path)
            self.connection.backup(backup)
            backup.close()
            return True
        except Exception as e:
            print(f"Backup error: {e}")
            return False

    def get_statistics(self) -> Dict:
        stats = {}

        # Total cases
        stats["total_cases"] = self.fetch_one("SELECT COUNT(*) as count FROM Cases")[
            "count"
        ]
        stats["open_cases"] = self.fetch_one(
            "SELECT COUNT(*) as count FROM Cases WHERE status = 'OPEN'"
        )["count"]

        # Total artifacts
        stats["total_artifacts"] = self.fetch_one(
            "SELECT COUNT(*) as count FROM Artefacts WHERE is_deleted = 0"
        )["count"]

        # Total users
        stats["total_users"] = self.fetch_one(
            "SELECT COUNT(*) as count FROM Users WHERE is_active = 1"
        )["count"]

        # Total reports
        stats["total_reports"] = self.fetch_one(
            "SELECT COUNT(*) as count FROM Reports"
        )["count"]

        return stats

    def save_analysis_result(
        self,
        file_path: str,
        evidence_type: str,
        tool_used: str,
        result_path: str,
        summary: Optional[str] = None,
    ) -> Optional[int]:

        try:
            # Tạo hoặc lấy artifact
            artifact_id = self._get_or_create_artifact(file_path, evidence_type)
            if not artifact_id:
                return None
            if summary is None:
                summary = f"{tool_used} completed for {os.path.basename(file_path)}"
            # Lưu kết quả
            result_id = self.add_analysis_result(
                artifact_id=artifact_id,
                tool_used=tool_used,
                summary=summary,
                result_path=result_path,
            )

            return result_id

        except Exception as e:
            print(f"Error saving analysis result ({tool_used}): {e}")
            return None

    def get_latest_analysis_result(
        self, file_path: str, evidence_type: str, tool_used: str
    ) -> Optional[Dict]:
        """Lấy kết quả phân tích mới nhất cho file và evidence type"""
        try:
            # Tìm artifact theo file path và evidence type
            query = """
                SELECT a.artefact_id 
                FROM Artefacts a 
                WHERE a.source_path = ? AND a.evidence_type = ? AND a.is_deleted = 0
            """
            artifact = self.fetch_one(query, (file_path, evidence_type))

            if not artifact:
                return None

            # Lấy kết quả phân tích mới nhất
            query = """
                SELECT * 
                FROM Results 
                WHERE artefact_id = ? AND tool_used = ?
                ORDER BY run_at DESC 
                LIMIT 1
            """
            result = self.fetch_one(query, (artifact["artefact_id"], tool_used))

            return result
        except Exception as e:
            print(f"Error getting latest analysis result: {e}")
            return None

    def _get_or_create_artifact(
        self, file_path: str, evidence_type: str, case_id: int = None
    ) -> Optional[int]:
        """Tạo hoặc lấy artifact ID cho file path"""
        try:
            # Kiểm tra xem artifact đã tồn tại chưa
            query = """
                SELECT artefact_id 
                FROM Artefacts 
                WHERE source_path = ? AND evidence_type = ? AND is_deleted = 0
            """
            existing = self.fetch_one(query, (file_path, evidence_type))

            if existing:
                return existing["artefact_id"]

            # Tạo artifact mới nếu chưa có
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # Nếu không có case_id, tạo case mặc định
            if not case_id:
                case_id = self._get_or_create_default_case()

            artifact_id = self.add_artifact(
                case_id=case_id,
                name=file_name,
                source_path=file_path,
                evidence_type=evidence_type,
                size=file_size,
            )

            return artifact_id

        except Exception as e:
            print(f"Error getting/creating artifact: {e}")
            return None

    def _get_or_create_default_case(self) -> int:
        """Tạo hoặc lấy case mặc định cho memory analysis"""
        try:
            # Tìm case mặc định
            query = "SELECT case_id FROM Cases WHERE title = 'Memory Analysis Default'"
            existing = self.fetch_one(query)

            if existing:
                return existing["case_id"]

            # Tạo case mặc định
            case_id = self.create_case(title="Memory Analysis Default", status="OPEN")

            return case_id if case_id else 1  # Fallback to case 1

        except Exception as e:
            print(f"Error getting/creating default case: {e}")
            return 1  # Fallback to case 1

    def get_memory_analysis_history(self, file_path: str = None) -> List[Dict]:
        """Lấy lịch sử phân tích memory"""
        try:
            if file_path:
                query = """
                    SELECT r.*, a.source_path, a.evidence_type, a.name
                    FROM Results r
                    JOIN Artefacts a ON r.artefact_id = a.artefact_id
                    WHERE a.source_path = ? AND r.tool_used = 'Memory Analysis'
                    ORDER BY r.run_at DESC
                """
                return self.fetch_all(query, (file_path,))
            else:
                query = """
                    SELECT r.*, a.source_path, a.evidence_type, a.name
                    FROM Results r
                    JOIN Artefacts a ON r.artefact_id = a.artefact_id
                    WHERE r.tool_used = 'Memory Analysis'
                    ORDER BY r.run_at DESC
                """
                return self.fetch_all(query)

        except Exception as e:
            print(f"Error getting memory analysis history: {e}")
            return []


# Global database instance
db = DatabaseManager()
