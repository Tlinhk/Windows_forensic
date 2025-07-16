import os
import sys
import subprocess
import threading
import time
import hashlib
import zipfile
import psutil
import json
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import QTimer, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QTextCursor

from ui.pages.collect_ui.collect_volatile_ui import Ui_Form
from database.db_manager import DatabaseManager


class ForensicCollectionWorker(QObject):
    """Professional forensic volatile data collection worker following Order of Volatility"""

    progress_updated = pyqtSignal(
        int, str, int
    )  # overall_progress, task_name, task_progress
    log_message = pyqtSignal(str)
    evidence_log = pyqtSignal(str)
    system_info_updated = pyqtSignal(str)
    collection_finished = pyqtSignal(bool, str, str)  # success, message, package_path

    def __init__(self, collection_options, output_path, case_info):
        super().__init__()
        self.collection_options = collection_options
        self.output_path = output_path
        self.case_info = case_info
        self.running = True
        self.start_time = datetime.now()
        self.evidence_files = []
        self.collection_log = []

    def run(self):
        """Main forensic collection process following Order of Volatility"""
        try:
            self.log_evidence_start()

            # Create timestamped collection directory
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            case_id = self.case_info.get("case_id", "UNKNOWN")
            evidence_id = self.case_info.get("evidence_id", "VOLATILE-001")

            self.collection_dir = os.path.join(
                self.output_path, f"{case_id}_{evidence_id}_{timestamp}"
            )
            os.makedirs(self.collection_dir, exist_ok=True)

            self.log_message.emit(
                f"BẮT ĐẦU THU THẬP FORENSIC - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.log_message.emit(f"📁 Thư mục thu thập: {self.collection_dir}")

            # Get system information first
            self.collect_system_info()

            # Define tasks in Order of Volatility (highest to lowest)
            tasks = []
            if self.collection_options.get("ram_acquisition"):
                tasks.append(("RAM Acquisition", self.collect_ram_dump, 40))
            if self.collection_options.get("system_time"):
                tasks.append(("System Time & Uptime", self.collect_system_time, 5))
            if self.collection_options.get("network_state"):
                tasks.append(("Network State", self.collect_network_state, 10))
            if self.collection_options.get("process_info"):
                tasks.append(("Process Information", self.collect_process_info, 15))
            if self.collection_options.get("logged_on_users"):
                tasks.append(("Logged-On Users", self.collect_logged_on_users, 5))
            if self.collection_options.get("clipboard"):
                tasks.append(("Clipboard Content", self.collect_clipboard, 2))
            if self.collection_options.get("command_history"):
                tasks.append(("Command History", self.collect_command_history, 8))
            if self.collection_options.get("services_drivers"):
                tasks.append(("Services & Drivers", self.collect_services_drivers, 10))
            if self.collection_options.get("environment_vars"):
                tasks.append(
                    ("Environment Variables", self.collect_environment_vars, 5)
                )
            if self.collection_options.get("shared_resources"):
                tasks.append(("Shared Resources", self.collect_shared_resources, 5))

            total_weight = sum(weight for _, _, weight in tasks)
            completed_weight = 0

            for task_name, task_func, weight in tasks:
                if not self.running:
                    break

                self.log_message.emit(f"Bắt đầu: {task_name}")
                self.evidence_log.emit(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Starting: {task_name}"
                )

                overall_progress = int((completed_weight / total_weight) * 100)
                self.progress_updated.emit(overall_progress, task_name, 0)

                success = task_func()

                if success:
                    self.log_message.emit(f"✅ Hoàn thành: {task_name}")
                    self.evidence_log.emit(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Completed: {task_name} - SUCCESS"
                    )
                else:
                    self.log_message.emit(f"❌ Lỗi: {task_name}")
                    self.evidence_log.emit(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Completed: {task_name} - FAILED"
                    )

                completed_weight += weight
                overall_progress = int((completed_weight / total_weight) * 100)
                self.progress_updated.emit(overall_progress, task_name, 100)

            if self.running:
                # Package and hash the evidence
                self.log_message.emit("🚀 Bắt đầu đóng gói evidence...")
                package_path = self.package_evidence()
                if package_path:
                    self.log_message.emit("🎉 Thu thập forensic hoàn tất thành công!")
                    self.collection_finished.emit(
                        True, "Thu thập forensic hoàn tất!", package_path
                    )
                else:
                    self.log_message.emit("❌ Lỗi khi đóng gói evidence")
                    self.collection_finished.emit(
                        False, "Lỗi khi đóng gói evidence", ""
                    )
            else:
                self.log_message.emit("❌ Thu thập bị hủy bởi người dùng")
                self.collection_finished.emit(
                    False, "Thu thập bị hủy bởi người dùng", ""
                )

        except Exception as e:
            self.log_message.emit(f"❌ Lỗi nghiêm trọng: {str(e)}")
            self.evidence_log.emit(
                f"[{datetime.now().strftime('%H:%M:%S')}] CRITICAL ERROR: {str(e)}"
            )
            self.collection_finished.emit(False, f"Lỗi: {str(e)}", "")

    def log_evidence_start(self):
        """Log evidence collection start with chain of custody"""
        custody_info = f"""
=== CHAIN OF CUSTODY - FORENSIC VOLATILE COLLECTION ===
Case ID: {self.case_info.get('case_id', 'N/A')}
Investigator: {self.case_info.get('investigator', 'N/A')}
Collection Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Target System: {self.collection_options.get('target', 'Local System')}
Output Device: {self.output_path}
Tool: Windows Forensic System - Volatile Collection Module
=== COLLECTION LOG ===
"""
        self.evidence_log.emit(custody_info)

    def collect_system_info(self):
        """Collect and display system information"""
        try:
            import platform

            # Get system info
            system_info = {
                "Computer Name": platform.node(),
                "OS": f"{platform.system()} {platform.release()}",
                "Architecture": platform.machine(),
                "Processor": platform.processor(),
                "RAM Total": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                "RAM Available": f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
                "Uptime": str(
                    datetime.now() - datetime.fromtimestamp(psutil.boot_time())
                ),
                "Current Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Timezone": time.tzname[0],
            }

            info_text = "\n".join([f"{k}: {v}" for k, v in system_info.items()])
            self.system_info_updated.emit(info_text)

            # Save to file
            info_file = os.path.join(self.collection_dir, "system_info.json")
            with open(info_file, "w", encoding="utf-8") as f:
                json.dump(system_info, f, indent=2, ensure_ascii=False)

            self.evidence_files.append(info_file)
            return True

        except Exception as e:
            self.log_message.emit(f"❌ System info error: {str(e)}")
            return False

    def collect_ram_dump(self):
        """Collect RAM dump using WinPmem mini (direct subprocess call)"""
        try:
            # Lấy định dạng từ UI
            ram_format_ui = self.collection_options.get("ram_format", "raw")
            format_map = {
                "raw": ("raw", "raw"),
                "mem": ("raw", "mem"),
                "aff4": ("aff4", "aff4"),
            }
            ext = (
                ram_format_ui.lower()
                .replace(".", "")
                .replace("(", "")
                .replace(")", "")
                .replace(" ", "")
            )
            if "aff4" in ext:
                fmt, ext = format_map["aff4"]
            elif "mem" in ext:
                fmt, ext = format_map["mem"]
            else:
                fmt, ext = format_map["raw"]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                self.collection_dir, f"memory_dump_{timestamp}.{ext}"
            )
            winpmem_path = os.path.abspath(
                os.path.join("tools", "winpmem_mini_x64_rc2.exe")
            )

            # Kiểm tra thư mục
            if not os.path.exists(self.collection_dir):
                try:
                    os.makedirs(self.collection_dir, exist_ok=True)
                except Exception as e:
                    self.log_message.emit(
                        f"❌ Không thể tạo thư mục collection: {str(e)}"
                    )
                    return False

            # Kiểm tra quyền ghi
            try:
                test_file = os.path.join(self.collection_dir, "test_write.tmp")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                self.log_message.emit(f"❌ Không có quyền ghi vào thư mục: {str(e)}")
                return False

            self.log_message.emit(f"Bắt đầu thu thập RAM bằng WinPmem: {winpmem_path}")
            self.log_message.emit(f"Định dạng: {fmt}, File dump: {output_file}")

            if not os.path.exists(winpmem_path):
                self.log_message.emit(f"❌ Không tìm thấy WinPmem tại: {winpmem_path}")
                return False

            # Gọi trực tiếp WinPmem
            cmd = [winpmem_path, output_file]
            self.log_message.emit(
                "🚀 Đang chạy WinPmem (yêu cầu quyền Administrator)..."
            )
            self.log_message.emit("Command: " + " ".join(cmd))

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600
                )

                if result.stdout:
                    self.log_message.emit(f"WinPmem stdout: {result.stdout}")
                if result.stderr:
                    self.log_message.emit(f"WinPmem stderr: {result.stderr}")

                if result.returncode != 0:
                    self.log_message.emit(
                        f"⚠️ Cảnh báo: WinPmem trả về mã lỗi {result.returncode}, nhưng sẽ kiểm tra file dump thực tế..."
                    )

                if not os.path.exists(output_file):
                    self.log_message.emit(f"❌ Không tìm thấy file dump: {output_file}")
                    return False

                # Kiểm tra kích thước
                file_size = os.path.getsize(output_file)
                if file_size == 0:
                    self.log_message.emit(f"❌ File RAM dump rỗng: {output_file}")
                    return False

                file_size_mb = file_size / (1024 * 1024)
                self.log_message.emit(f"✅ Đã thu thập RAM thành công: {output_file}")
                self.log_message.emit(f"📊 Kích thước file: {file_size_mb:.2f} MB")

                # Tính hash SHA-256
                sha256_hash = hashlib.sha256()
                with open(output_file, "rb") as f:
                    while chunk := f.read(4096):
                        sha256_hash.update(chunk)
                hash_value = sha256_hash.hexdigest()
                hash_file = output_file + ".sha256"
                with open(hash_file, "w", encoding="utf-8") as f:
                    f.write(f"{hash_value}  {os.path.basename(output_file)}\n")
                self.log_message.emit(f"🔐 SHA-256: {hash_value}")

                # Ghi metadata
                metadata = {
                    "collection_time": datetime.now().isoformat(),
                    "ram_size_bytes": psutil.virtual_memory().total,
                    "ram_size_gb": psutil.virtual_memory().total / (1024**3),
                    "format": fmt,
                    "tool_used": winpmem_path,
                    "hash_sha256": hash_value,
                    "dump_file": output_file,
                    "collection_method": "WinPmem direct subprocess call (must run as Admin)",
                }
                metadata_file = os.path.join(
                    self.collection_dir, f"memory_dump_{timestamp}_metadata.json"
                )
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                self.evidence_files.extend([output_file, metadata_file, hash_file])
                self.log_message.emit(f"RAM metadata saved: {metadata_file}")
                return True

            except subprocess.TimeoutExpired:
                self.log_message.emit("❌ WinPmem bị timeout sau 600 giây")
                return False
            except subprocess.CalledProcessError as e:
                self.log_message.emit(f"❌ Lỗi WinPmem: {e}")
                return False

        except Exception as e:
            self.log_message.emit(f"❌ RAM dump error: {str(e)}")
            return False

    def collect_system_time(self):
        """Collect system time and uptime information"""
        try:
            output_file = os.path.join(
                self.collection_dir,
                f"system_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            )

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("=== SYSTEM TIME & UPTIME ===\n")
                f.write(
                    f"Collection Time (Local): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(
                    f"Collection Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(
                    f"System Boot Time: {datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(
                    f"System Uptime: {datetime.now() - datetime.fromtimestamp(psutil.boot_time())}\n"
                )
                f.write(f"Timezone: {time.tzname}\n")

            self.evidence_files.append(output_file)
            return True

        except Exception as e:
            self.log_message.emit(f"❌ System time error: {str(e)}")
            return False

    def collect_network_state(self):
        """Collect network connections and configuration"""
        try:
            # Run system commands for additional info
            network_dir = os.path.join(self.collection_dir, "Network_State")
            os.makedirs(network_dir, exist_ok=True)
            commands = [
                ("netstat -ano", "network_netstat_detailed.txt"),
                ("arp -a", "network_arp_cache.txt"),
                ("route print", "network_routing_table.txt"),
                ("ipconfig /all", "network_ipconfig_all.txt"),
            ]

            for cmd, filename in commands:
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=30
                    )
                    cmd_file = os.path.join(network_dir, filename)
                    with open(cmd_file, "w", encoding="utf-8") as f:
                        f.write(f"Command: {cmd}\n")
                        f.write(
                            f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        )
                        f.write("=" * 50 + "\n")
                        f.write(result.stdout)
                    self.evidence_files.append(cmd_file)
                    self.log_message.emit(f"✅ Hoàn thành: {filename}")
                except Exception as e:
                    self.log_message.emit(f"⚠️ Command failed: {cmd} - {str(e)}")
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Network state error: {str(e)}")
            return False

    def collect_process_info(self):
        """Collect detailed process information including DLLs and handles"""
        try:
            process_dir = os.path.join(self.collection_dir, "Process_Information")
            os.makedirs(process_dir, exist_ok=True)
            output_file = os.path.join(
                process_dir,
                f"processes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )

            processes = []
            for proc in psutil.process_iter(
                [
                    "pid",
                    "ppid",
                    "name",
                    "exe",
                    "cmdline",
                    "create_time",
                    "username",
                    "memory_info",
                ]
            ):
                try:
                    proc_info = proc.info
                    proc_info["create_time_str"] = datetime.fromtimestamp(
                        proc_info["create_time"]
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    # Collect additional process details:
                    # Memory information
                    if proc_info["memory_info"]:
                        proc_info["memory_rss_mb"] = proc_info["memory_info"].rss / (
                            1024 * 1024
                        )
                        proc_info["memory_vms_mb"] = proc_info["memory_info"].vms / (
                            1024 * 1024
                        )

                        # Get process object for additional info
                    process_obj = psutil.Process(proc_info["pid"])

                    # Open files/handles

                    try:
                        proc_info["open_files"] = [
                            {"path": f.path, "fd": f.fd if hasattr(f, "fd") else "N/A"}
                            for f in process_obj.open_files()
                        ]
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        proc_info["open_files"] = ["Access Denied"]

                        # Network connections for this process

                    try:
                        proc_info["connections"] = [
                            {
                                "family": str(conn.family),
                                "type": str(conn.type),
                                "laddr": (
                                    f"{conn.laddr.ip}:{conn.laddr.port}"
                                    if conn.laddr
                                    else None
                                ),
                                "raddr": (
                                    f"{conn.raddr.ip}:{conn.raddr.port}"
                                    if conn.raddr
                                    else None
                                ),
                                "status": str(conn.status),
                            }
                            for conn in process_obj.connections()
                        ]
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        proc_info["connections"] = ["Access Denied"]

                        # DLLs (modules)
                    try:
                        proc_info["dlls"] = process_obj.memory_maps()
                        # Only keep the path (dll file path)
                        proc_info["dlls"] = [
                            m.path
                            for m in proc_info["dlls"]
                            if m.path.lower().endswith(".dll")
                        ]
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        proc_info["dlls"] = ["Access Denied or Not Available"]

                        # CPU and other stats
                    try:
                        proc_info["cpu_percent"] = process_obj.cpu_percent()
                        proc_info["num_threads"] = process_obj.num_threads()
                        proc_info["status"] = str(process_obj.status())
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass

                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(processes, f, indent=2, ensure_ascii=False, default=str)

            self.collect_dlls_and_handles()
            self.evidence_files.append(output_file)

            self.log_message.emit(f"✅ Đã thu thập process, lưu: {output_file}")
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Process info error: {str(e)}")
            return False

    def collect_dlls_and_handles(self):
        """Collect DLLs and handles using Windows commands"""
        try:
            process_dir = os.path.join(self.collection_dir, "Process_Information")
            os.makedirs(process_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Use tasklist to get detailed process info with modules
            self.log_message.emit("📚 Thu thập thông tin DLL và modules...")

            # Get processes with modules (DLLs)
            commands = [
                # Process list with modules                # Detailed process info
                (
                    "wmic process get ProcessId,Name,ExecutablePath,CommandLine,CreationDate,PageFileUsage,WorkingSetSize /format:csv",
                    f"wmic_processes_{timestamp}.csv",
                ),
                # System handles (if available)
                (
                    os.path.join("tools", "handle.exe") + " -a",
                    f"system_handles_{timestamp}.txt",
                ),  # Requires Sysinternals handle.exe
            ]

            for cmd, filename in commands:
                try:
                    self.log_message.emit(f"Chạy lệnh: {cmd}")

                    # Special handling for handle.exe which might not exist
                    if "handle.exe" in cmd:
                        # Check if handle.exe exists first
                        handle_path = cmd.split(" ")[0]
                        if not os.path.exists(handle_path):
                            self.log_message.emit(
                                "⚠️ handle.exe không tìm thấy - bỏ qua thu thập system handles"
                            )
                            continue

                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=120
                    )

                    cmd_file = os.path.join(process_dir, filename)
                    with open(cmd_file, "w", encoding="utf-8") as f:
                        f.write(f"Command: {cmd}\n")
                        f.write(
                            f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        )
                        f.write(f"Return Code: {result.returncode}\n")
                        f.write("=" * 60 + "\n")
                        if result.stdout:
                            f.write("STDOUT:\n")
                            f.write(result.stdout)
                        if result.stderr:
                            f.write("\nSTDERR:\n")
                            f.write(result.stderr)

                    self.evidence_files.append(cmd_file)
                    self.log_message.emit(f"✅ Hoàn thành: {filename}")

                except subprocess.TimeoutExpired:
                    self.log_message.emit(f"⏰ Timeout: {cmd}")
                except Exception as e:
                    self.log_message.emit(f"❌ Lỗi lệnh {cmd}: {str(e)}")

        except Exception as e:
            self.log_message.emit(f"❌ DLL/Handles collection error: {str(e)}")

    def collect_logged_on_users(self):
        """Collect logged-on users information (local, network, service)"""
        try:
            folder_name = f"logged_on_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            folder_path = os.path.join(self.collection_dir, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            self.log_message.emit(f"📥 Thu thập thông tin Logged-On Users...")
            # Query additional session info
            commands = [
                ("query user", "query_user.txt"),
                ("net session", "net_session.txt"),
                (os.path.join("tools", "PsLoggedon64.exe"), "psloggedon.txt"),
                (os.path.join("tools", "logonsessions64.exe"), "logonsessions.txt"),
            ]

            for cmd, filename in commands:
                try:
                    self.log_message.emit(f"Chạy lệnh: {cmd}")

                    if any(
                        tool in cmd
                        for tool in ["PsLoggedon64.exe", "logonsessions64.exe"]
                    ):
                        tool_path = cmd.split(" ")[0]
                        if not os.path.exists(tool_path):
                            self.log_message.emit(
                                f"⚠️ {os.path.basename(tool_path)} không tìm thấy - bỏ qua"
                            )
                            continue
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=30
                    )
                    cmd_file = os.path.join(folder_path, filename)
                    with open(cmd_file, "w", encoding="utf-8") as f:
                        f.write(f"Command: {cmd}\n")
                        f.write("=" * 30 + "\n")
                        f.write(result.stdout)
                        if result.stderr:
                            f.write("\nSTDERR:\n")
                            f.write(result.stderr)
                    self.evidence_files.append(cmd_file)
                    self.log_message.emit(f"✅ Hoàn thành: {filename}")
                except subprocess.TimeoutExpired:
                    self.log_message.emit(f"⏰ Timeout: {cmd}")
                except Exception as e:
                    self.log_message.emit(f"❌ Lỗi khi chạy {cmd}: {str(e)}")
            self.log_message.emit(
                f"🎯 Đã thu thập Logged-On Users, lưu ở: {folder_path}"
            )
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Logged-On Users collection error: {str(e)}")
            return False

    def collect_clipboard(self):
        """Collect clipboard content"""
        try:
            output_file = os.path.join(
                self.collection_dir,
                f"clipboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            )

            # Try to get clipboard content using PowerShell
            cmd = 'powershell -Command "Get-Clipboard"'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("=== CLIPBOARD CONTENT ===\n")
                f.write(
                    f"Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write("=" * 30 + "\n")
                if result.stdout:
                    f.write(result.stdout)
                else:
                    f.write("[No clipboard content or access denied]\n")

            self.evidence_files.append(output_file)
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Clipboard error: {str(e)}")
            return False

    def collect_command_history(self):
        """Collect command history from various shells"""
        try:
            # Tạo thư mục con cho command history
            history_dir = os.path.join(self.collection_dir, "Command_History")
            os.makedirs(history_dir, exist_ok=True)

            # PowerShell history
            ps_history_file = os.path.join(history_dir, "powershell_history.csv")
            ps_history_cmd = f'powershell -Command "Get-History | Export-Csv -Path \\"{ps_history_file}\\" -NoTypeInformation"'
            subprocess.run(
                ps_history_cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            self.evidence_files.append(ps_history_file)

            # CMD history (doskey /history)
            cmd_history_file = os.path.join(history_dir, "cmd_history.txt")
            try:
                result = subprocess.run(
                    "doskey /history",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                with open(cmd_history_file, "w", encoding="utf-8") as f:
                    f.write("=== CMD HISTORY (doskey /history) ===\n")
                    f.write(
                        f"Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write("=" * 30 + "\n")
                    if result.stdout:
                        f.write(result.stdout)
                    else:
                        f.write("[No CMD history or not available]\n")
                self.evidence_files.append(cmd_history_file)
            except Exception as e:
                self.log_message.emit(f"❌ CMD history (doskey) error: {str(e)}")

            self.log_message.emit("✅ Hoàn thành thu thập Command History")
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Command history error: {str(e)}")
            return False

    def collect_services_drivers(self):
        """Collect services and drivers information"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Tạo thư mục con
            services_dir = os.path.join(self.collection_dir, "Services_Drivers")
            os.makedirs(services_dir, exist_ok=True)

            # Services
            services_file = os.path.join(services_dir, f"services_{timestamp}.txt")
            cmd = "sc query"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            with open(services_file, "w", encoding="utf-8") as f:
                f.write("=== WINDOWS SERVICES ===\n")
                f.write(result.stdout)

            # Services detail (wmic)
            wmic_file = os.path.join(services_dir, f"wmic_services_{timestamp}.csv")
            wmic_cmd = "wmic service list brief /format:csv"
            result = subprocess.run(
                wmic_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            with open(wmic_file, "w", encoding="utf-8") as f:
                f.write(result.stdout)

            # Drivers
            drivers_cmd = "driverquery /fo csv /v"
            result = subprocess.run(
                drivers_cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            drivers_file = os.path.join(services_dir, "drivers.csv")
            with open(drivers_file, "w", encoding="utf-8") as f:
                f.write(result.stdout)

            self.evidence_files.extend([services_file, wmic_file, drivers_file])
            self.log_message.emit("✅ Thu thập Services & Drivers hoàn tất")
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Services/Drivers error: {str(e)}")
            return False

    def collect_environment_vars(self):
        """Collect environment variables"""
        try:
            output_file = os.path.join(
                self.collection_dir,
                f"environment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )

            env_vars = dict(os.environ)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(env_vars, f, indent=2, ensure_ascii=False)

            self.evidence_files.append(output_file)
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Environment vars error: {str(e)}")
            return False

    def collect_shared_resources(self):
        """Collect locally shared resource information (only net share)"""
        try:
            net_share_file = os.path.join(self.collection_dir, "net_share.txt")
            result = subprocess.run(
                "net share",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            with open(net_share_file, "w", encoding="utf-8") as f:
                f.write("=== NET SHARE ===\n")
                f.write(result.stdout)

            self.evidence_files.append(net_share_file)
            self.log_message.emit("✅ Thu thập Shared Resource hoàn tất")
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Shared Resource error: {str(e)}")
            return False

    def package_evidence(self):
        """Package all evidence files and calculate hash"""
        try:
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            case_id = self.case_info.get("case_id", "UNKNOWN")

            package_name = f"{case_id}_VOLATILE_{timestamp}_EVIDENCE.zip"
            package_path = os.path.join(self.output_path, package_name)

            self.log_message.emit("📦 Đóng gói evidence...")

            # Filter out non-existent files
            existing_files = [f for f in self.evidence_files if os.path.exists(f)]
            missing_files = [f for f in self.evidence_files if not os.path.exists(f)]

            if missing_files:
                self.log_message.emit(
                    f"⚠️ Warning: {len(missing_files)} files not found and will be skipped"
                )
                for missing_file in missing_files[:5]:  # Show first 5 missing files
                    self.log_message.emit(f"   - {os.path.basename(missing_file)}")
                if len(missing_files) > 5:
                    self.log_message.emit(f"   ... and {len(missing_files) - 5} more")

            self.log_message.emit(f"📁 Tổng số file sẽ đóng gói: {len(existing_files)}")

            with zipfile.ZipFile(
                package_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True
            ) as zipf:
                # Add all evidence files
                for i, file_path in enumerate(existing_files):
                    if not self.running:
                        self.log_message.emit("❌ Quá trình bị hủy bởi người dùng")
                        return None

                    try:
                        arcname = os.path.relpath(file_path, self.output_path)
                        zipf.write(file_path, arcname)
                        if i % 5 == 0:  # Log every 5 files
                            self.log_message.emit(
                                f"📦 Đang đóng gói file {i+1}/{len(existing_files)}: {os.path.basename(file_path)}"
                            )
                    except Exception as file_error:
                        self.log_message.emit(
                            f"⚠️ Warning: Could not add file {file_path}: {str(file_error)}"
                        )
                        continue

                # Create collection summary
                self.log_message.emit("📋 Đang tạo collection summary...")
                summary = {
                    "case_id": case_id,
                    "collection_type": "VOLATILE",
                    "investigator": self.case_info.get("investigator", "N/A"),
                    "collection_start": self.start_time.isoformat(),
                    "collection_end": datetime.now().isoformat(),
                    "evidence_files": [os.path.basename(f) for f in existing_files],
                    "missing_files": (
                        [os.path.basename(f) for f in missing_files]
                        if missing_files
                        else []
                    ),
                    "collection_options": self.collection_options,
                    "tool_version": "Windows Forensic System v1.0",
                }

                try:
                    zipf.writestr(
                        "COLLECTION_SUMMARY.json",
                        json.dumps(summary, indent=2, ensure_ascii=False).encode(
                            "utf-8"
                        ),
                    )
                    self.log_message.emit("✅ Collection summary created")
                except Exception as summary_error:
                    self.log_message.emit(
                        f"⚠️ Warning: Could not create summary: {str(summary_error)}"
                    )

            # Calculate SHA-256 hash
            self.log_message.emit("🔐 Đang tính SHA-256 hash...")
            sha256_hash = hashlib.sha256()
            try:
                with open(package_path, "rb") as f:
                    chunk_count = 0
                    while True:
                        if not self.running:
                            self.log_message.emit("❌ Quá trình bị hủy bởi người dùng")
                            return None

                        chunk = f.read(4096)
                        if not chunk:
                            break
                        sha256_hash.update(chunk)
                        chunk_count += 1
                        if chunk_count % 1000 == 0:  # Log every 1000 chunks
                            self.log_message.emit(
                                f"🔐 Đang tính hash... ({chunk_count} chunks processed)"
                            )
            except Exception as hash_calc_error:
                self.log_message.emit(f"❌ Lỗi khi tính hash: {str(hash_calc_error)}")
                return None

            hash_value = sha256_hash.hexdigest()

            # Create hash file
            hash_file = package_path + ".sha256"
            try:
                with open(hash_file, "w", encoding="utf-8") as f:
                    f.write(f"{hash_value}  {package_name}\n")
                self.log_message.emit(f"✅ Hash file created: {hash_file}")
            except Exception as hash_error:
                self.log_message.emit(
                    f"⚠️ Warning: Could not create hash file: {str(hash_error)}"
                )

            self.log_message.emit(f"🔐 SHA-256: {hash_value}")
            self.evidence_log.emit(f"Package: {package_name}")
            self.evidence_log.emit(f"SHA-256: {hash_value}")
            self.evidence_log.emit(
                f"Collection completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            self.log_message.emit("✅ Đóng gói evidence hoàn tất!")
            self.log_message.emit(f"📦 Package: {package_name}")
            self.log_message.emit(f"📁 Location: {package_path}")

            return package_path

        except Exception as e:
            self.log_message.emit(f"❌ Packaging error: {str(e)}")
            return None

    def stop(self):
        """Stop the collection process"""
        self.running = False


class Volatile(QWidget):
    def __init__(self):
        super(Volatile, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # Initialize components
        self.db = DatabaseManager()
        self.db.connect()
        self.current_case_id = None
        self.collection_worker = None
        self.collection_thread = None

        # Timer for elapsed time
        self.start_time = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_elapsed_time)

        # Connect signals
        self.setup_connections()

        # Initialize UI state
        self.initialize_ui()

        # Load system info on startup
        self.load_system_info()

    def setup_connections(self):
        """Setup signal connections"""
        self.ui.selectAllBtn.clicked.connect(self.select_all_options)
        self.ui.clearAllBtn.clicked.connect(self.clear_all_options)
        self.ui.startCollectionBtn.clicked.connect(self.start_collection)
        self.ui.stopCollectionBtn.clicked.connect(self.stop_collection)
        self.ui.browseOutputBtn.clicked.connect(self.browse_output_path)
        self.ui.clearLogBtn.clicked.connect(self.clear_log)
        self.ui.saveLogBtn.clicked.connect(self.save_log)

    def initialize_ui(self):
        """Initialize UI state"""
        self.ui.stopCollectionBtn.setEnabled(False)
        self.update_progress(0, "Sẵn sàng thu thập", 0)

        # Set default values
        self.ui.caseIdEdit.setText(f"CASE-{datetime.now().strftime('%Y-%m%d')}")

    #        self.ui.evidenceIdEdit.setText("VOLATILE-001")

    def load_system_info(self):
        """Load and display basic system information"""
        try:
            import platform

            ram_gb = psutil.virtual_memory().total / (1024**3)
            info = f"""Computer: {platform.node()}
OS: {platform.system()} {platform.release()}
RAM: {ram_gb:.1f} GB
Uptime: {str(datetime.now() - datetime.fromtimestamp(psutil.boot_time()))}
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            self.ui.systemInfoText.setText(info)
            self.ui.ramSizeLabel.setText(
                f" RAM: {ram_gb:.1f} GB | Cần: ~{ram_gb:.1f} GB | Gói: ~{ram_gb*0.3:.1f} GB"
            )

        except Exception as e:
            self.ui.systemInfoText.setText(f"Lỗi khi tải thông tin hệ thống: {str(e)}")

    def select_all_options(self):
        """Select all collection options"""
        checkboxes = [
            self.ui.ramAcquisitionCheck,
            self.ui.systemTimeCheck,
            self.ui.networkStateCheck,
            self.ui.processInfoCheck,
            self.ui.userSessionsCheck,
            self.ui.clipboardCheck,
            self.ui.commandHistoryCheck,
            self.ui.servicesDriversCheck,
            self.ui.environmentVarsCheck,
            self.ui.sharedResourcesCheck,
        ]

        for checkbox in checkboxes:
            checkbox.setChecked(True)

    def clear_all_options(self):
        """Clear all collection options"""
        checkboxes = [
            self.ui.ramAcquisitionCheck,
            self.ui.systemTimeCheck,
            self.ui.networkStateCheck,
            self.ui.processInfoCheck,
            self.ui.userSessionsCheck,
            self.ui.clipboardCheck,
            self.ui.commandHistoryCheck,
            self.ui.servicesDriversCheck,
            self.ui.environmentVarsCheck,
            self.ui.sharedResourcesCheck,
        ]

        for checkbox in checkboxes:
            checkbox.setChecked(False)

    def browse_output_path(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Chọn thiết bị ngoài để lưu evidence", self.ui.outputPathEdit.text()
        )

        if directory:
            self.ui.outputPathEdit.setText(directory)

    def get_collection_options(self):
        """Get selected collection options"""
        return {
            "ram_acquisition": self.ui.ramAcquisitionCheck.isChecked(),
            "ram_format": self.ui.ramFormatCombo.currentText().split()[1][
                1:-1
            ],  # Extract extension
            "calculate_hash": self.ui.calculateHashCheck.isChecked(),
            "system_time": self.ui.systemTimeCheck.isChecked(),
            "network_state": self.ui.networkStateCheck.isChecked(),
            "process_info": self.ui.processInfoCheck.isChecked(),
            "logged_on_users": self.ui.userSessionsCheck.isChecked(),
            "clipboard": self.ui.clipboardCheck.isChecked(),
            "command_history": self.ui.commandHistoryCheck.isChecked(),
            "services_drivers": self.ui.servicesDriversCheck.isChecked(),
            "environment_vars": self.ui.environmentVarsCheck.isChecked(),
            "shared_resources": self.ui.sharedResourcesCheck.isChecked(),
        }

    def get_case_info(self):
        """Get case information"""
        return {
            "case_id": self.ui.caseIdEdit.text() or "UNKNOWN",
            "investigator": "System Administrator",  # Fallback investigator
        }

    def start_collection(self):
        """Start forensic volatile data collection"""
        options = self.get_collection_options()
        case_info = self.get_case_info()

        # Validation
        if not any(options.values()):
            QMessageBox.warning(
                self, "Cảnh báo", "Vui lòng chọn ít nhất một loại dữ liệu để thu thập!"
            )
            return

        output_path = self.ui.outputPathEdit.text()
        if not output_path:
            QMessageBox.warning(
                self, "Cảnh báo", "Vui lòng chọn thiết bị ngoài để lưu evidence!"
            )
            return

        if not case_info["case_id"]:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập Case ID!")
            return

        # Confirmation dialog
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Xác nhận Thu thập Forensic")
        msg.setText("BẮT ĐẦU THU THẬP DỮ LIỆU KHẢ BIẾN")
        msg.setInformativeText(
            f"Case: {case_info['case_id']}\n"
            f"Loại: Thu thập dữ liệu khả biến (VOLATILE)\n"
            f"Investigator: {case_info['investigator']}\n"
            f"Output: {output_path}\n\n"
            f"⚠️ Quá trình này sẽ tác động đến hệ thống và không thể hoàn tác!"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() != QMessageBox.Yes:
            return

        # Update UI state
        self.ui.startCollectionBtn.setEnabled(False)
        self.ui.stopCollectionBtn.setEnabled(True)
        self.start_time = time.time()
        self.timer.start(1000)  # Update every second

        # Create and start worker thread
        self.collection_worker = ForensicCollectionWorker(
            options, output_path, case_info
        )
        self.collection_thread = QThread()
        self.collection_worker.moveToThread(self.collection_thread)

        # Connect worker signals
        self.collection_worker.progress_updated.connect(self.update_progress)
        self.collection_worker.log_message.connect(self.add_log_message)
        self.collection_worker.evidence_log.connect(self.add_evidence_log)
        self.collection_worker.system_info_updated.connect(
            self.ui.systemInfoText.setText
        )
        self.collection_worker.collection_finished.connect(self.collection_finished)

        # Start thread
        self.collection_thread.started.connect(self.collection_worker.run)
        self.collection_thread.start()

    def stop_collection(self):
        """Stop forensic data collection"""
        if self.collection_worker:
            self.collection_worker.stop()
        self.collection_stopped()

    def update_progress(self, overall_progress, task_name, task_progress):
        """Update progress bars and labels"""
        self.ui.overallProgressBar.setValue(overall_progress)
        self.ui.taskProgressBar.setValue(task_progress)
        self.ui.currentTaskLabel.setText(f"Trạng thái: {task_name}")
        self.ui.taskDetailLabel.setText(f"Chi tiết: {task_name} - {task_progress}%")

    def add_log_message(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        # Add to system log (not visible in UI for this design)
        print(formatted_message)

    def add_evidence_log(self, message):
        """Add message to evidence log"""
        self.ui.evidenceLogText.append(message)

        # Auto scroll to bottom
        cursor = self.ui.evidenceLogText.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.ui.evidenceLogText.setTextCursor(cursor)

    def update_elapsed_time(self):
        """Update elapsed time display"""
        if self.start_time:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60

            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.ui.elapsedTimeLabel.setText(f"⏱️ Thời gian: {time_str}")

    def collection_finished(self, success, message, package_path):
        """Handle collection completion"""
        self.timer.stop()

        # Notify wizard if reference exists
        if hasattr(self, "wizard_reference") and self.wizard_reference:
            print("Calling wizard_collection_finished from volatile page")
            try:
                self.wizard_reference.wizard_collection_finished(
                    "volatile", success, message, package_path
                )
            except Exception as e:
                print(f"Error calling wizard: {e}")

        if success:
            QMessageBox.information(
                self,
                "Hoàn thành Thu thập Forensic",
                f"✅ {message}\n\n"
                f"Evidence Package: {os.path.basename(package_path)}\n"
                f"Đường dẫn: {package_path}\n\n",
            )
        else:
            QMessageBox.warning(self, "Lỗi Thu thập", f"❌ {message}")

        self.collection_stopped()

    def collection_stopped(self):
        """Reset UI after collection stops"""
        self.ui.startCollectionBtn.setEnabled(True)
        self.ui.stopCollectionBtn.setEnabled(False)

        if self.collection_thread and self.collection_thread.isRunning():
            self.collection_thread.quit()
            self.collection_thread.wait()

        self.collection_worker = None
        self.collection_thread = None

    def clear_log(self):
        """Clear evidence log"""
        self.ui.evidenceLogText.clear()

    def save_log(self):
        """Save evidence log to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu Evidence Log",
            f"evidence_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)",
        )

        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.ui.evidenceLogText.toPlainText())

                QMessageBox.information(
                    self, "Thành công", f"Evidence log đã được lưu: {filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Lỗi", f"❌ Không thể lưu evidence log: {str(e)}"
                )

    def set_case_data(self, case_data):
        """Set case data for evidence collection"""
        self.current_case_id = case_data.get("case_id")

        # Update UI với thông tin case
        if case_data.get("case_id") and case_data.get("case_name"):
            # Hiển thị cả mã case và tên case
            case_display = f"{case_data['case_id']} - {case_data['case_name']}"
            self.ui.caseIdEdit.setText(case_display)
        elif case_data.get("case_id"):
            self.ui.caseIdEdit.setText(case_data["case_id"])

        # if case_data.get('investigator'):
        #    self.ui.investigatorEdit.setText(case_data['investigator'])

        # Update output path để include case info và volatile
        if case_data.get("case_id") and case_data.get("case_name"):
            # Tạo đường dẫn với mã case, tên case và chú thích volatile
            safe_case_name = "".join(
                c for c in case_data["case_name"] if c.isalnum() or c in (" ", "-", "_")
            ).rstrip()
            output_path = f"E:\\ForensicCollection\\{case_data['case_id']}_{safe_case_name}_volatile"
            self.ui.outputPathEdit.setText(output_path)
        elif case_data.get("case_id"):
            output_path = f"E:\\ForensicCollection\\{case_data['case_id']}_volatile"
            self.ui.outputPathEdit.setText(output_path)

    def set_case_id(self, case_id):
        """Set current case ID for evidence collection (legacy method)"""
        self.current_case_id = case_id

        # Update output path to include case info
        if case_id:
            case_info = self.db.get_case_by_id(case_id)
            if case_info:
                case_code = case_info.get("case_code", f"Case_{case_id}")
                self.ui.caseIdEdit.setText(case_code)
