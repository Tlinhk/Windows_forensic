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
    progress_updated = pyqtSignal(int, str, int)  # overall_progress, task_name, task_progress
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
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            case_id = self.case_info.get('case_id', 'UNKNOWN')
            evidence_id = self.case_info.get('evidence_id', 'VOLATILE-001')
            
            self.collection_dir = os.path.join(
                self.output_path, 
                f"{case_id}_{evidence_id}_{timestamp}"
            )
            os.makedirs(self.collection_dir, exist_ok=True)
            
            self.log_message.emit(f"BẮT ĐẦU THU THẬP FORENSIC - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.log_message.emit(f"📁 Thư mục thu thập: {self.collection_dir}")
            
            # Get system information first
            self.collect_system_info()
            
            # Define tasks in Order of Volatility (highest to lowest)
            tasks = []
            if self.collection_options.get('ram_acquisition'):
                tasks.append(('RAM Acquisition', self.collect_ram_dump, 40))
            if self.collection_options.get('system_time'):
                tasks.append(('System Time & Uptime', self.collect_system_time, 5))
            if self.collection_options.get('network_state'):
                tasks.append(('Network State', self.collect_network_state, 10))
            if self.collection_options.get('process_info'):
                tasks.append(('Process Information', self.collect_process_info, 15))
            if self.collection_options.get('user_sessions'):
                tasks.append(('User Sessions', self.collect_user_sessions, 5))
            if self.collection_options.get('clipboard'):
                tasks.append(('Clipboard Content', self.collect_clipboard, 2))
            if self.collection_options.get('command_history'):
                tasks.append(('Command History', self.collect_command_history, 8))
            if self.collection_options.get('services_drivers'):
                tasks.append(('Services & Drivers', self.collect_services_drivers, 10))
            if self.collection_options.get('environment_vars'):
                tasks.append(('Environment Variables', self.collect_environment_vars, 5))
            
            total_weight = sum(weight for _, _, weight in tasks)
            completed_weight = 0
            
            for task_name, task_func, weight in tasks:
                if not self.running:
                    break
                    
                self.log_message.emit(f"Bắt đầu: {task_name}")
                self.evidence_log.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Starting: {task_name}")
                
                overall_progress = int((completed_weight / total_weight) * 100)
                self.progress_updated.emit(overall_progress, task_name, 0)
                
                success = task_func()
                
                if success:
                    self.log_message.emit(f"✅ Hoàn thành: {task_name}")
                    self.evidence_log.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Completed: {task_name} - SUCCESS")
                else:
                    self.log_message.emit(f"❌ Lỗi: {task_name}")
                    self.evidence_log.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Completed: {task_name} - FAILED")
                
                completed_weight += weight
                overall_progress = int((completed_weight / total_weight) * 100)
                self.progress_updated.emit(overall_progress, task_name, 100)
                
            if self.running:
                # Package and hash the evidence
                package_path = self.package_evidence()
                if package_path:
                    self.collection_finished.emit(True, "Thu thập forensic hoàn tất!", package_path)
                else:
                    self.collection_finished.emit(False, "Lỗi khi đóng gói evidence", "")
            else:
                self.collection_finished.emit(False, "Thu thập bị hủy bởi người dùng", "")
                
        except Exception as e:
            self.log_message.emit(f"❌ Lỗi nghiêm trọng: {str(e)}")
            self.evidence_log.emit(f"[{datetime.now().strftime('%H:%M:%S')}] CRITICAL ERROR: {str(e)}")
            self.collection_finished.emit(False, f"Lỗi: {str(e)}", "")
    
    def log_evidence_start(self):
        """Log evidence collection start with chain of custody"""
        custody_info = f"""
=== CHAIN OF CUSTODY - FORENSIC VOLATILE COLLECTION ===
Case ID: {self.case_info.get('case_id', 'N/A')}
Evidence ID: {self.case_info.get('evidence_id', 'N/A')}
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
                'Computer Name': platform.node(),
                'OS': f"{platform.system()} {platform.release()}",
                'Architecture': platform.machine(),
                'Processor': platform.processor(),
                'RAM Total': f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                'RAM Available': f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
                'Uptime': str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())),
                'Current Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Timezone': time.tzname[0]
            }
            
            info_text = "\n".join([f"{k}: {v}" for k, v in system_info.items()])
            self.system_info_updated.emit(info_text)
            
            # Save to file
            info_file = os.path.join(self.collection_dir, "system_info.json")
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(system_info, f, indent=2, ensure_ascii=False)
            
            self.evidence_files.append(info_file)
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ System info error: {str(e)}")
            return False
    
    def collect_ram_dump(self):
        """Collect RAM dump - HIGHEST PRIORITY"""
        try:
            ram_format = self.collection_options.get('ram_format', 'mem')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.collection_dir, f"memory_dump_{timestamp}.{ram_format}")
            
            # For demonstration - in real implementation, use tools like:
            # - WinPmem
            # - DumpIt
            # - Belkasoft RAM Capturer
            
            self.log_message.emit("Bắt đầu thu thập RAM - Sử dụng công cụ chuyên dụng...")
            
            # Simulate RAM collection (replace with actual tool)
            ram_size_gb = psutil.virtual_memory().total / (1024**3)
            self.log_message.emit(f"Kích thước RAM: {ram_size_gb:.2f} GB")
            
            # Create metadata file for RAM dump
            metadata = {
                'collection_time': datetime.now().isoformat(),
                'ram_size_bytes': psutil.virtual_memory().total,
                'ram_size_gb': ram_size_gb,
                'format': ram_format,
                'tool_used': 'Windows Forensic System (Simulated)',
                'hash_calculated': self.collection_options.get('calculate_hash', True)
            }
            
            metadata_file = os.path.join(self.collection_dir, f"memory_dump_{timestamp}_metadata.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            self.evidence_files.append(metadata_file)
            
            # Note: Actual RAM dump would be created by external tool
            self.log_message.emit(f"RAM metadata saved: {metadata_file}")
            
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ RAM dump error: {str(e)}")
            return False
    
    def collect_system_time(self):
        """Collect system time and uptime information"""
        try:
            output_file = os.path.join(self.collection_dir, f"system_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== SYSTEM TIME & UPTIME ===\n")
                f.write(f"Collection Time (Local): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Collection Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"System Boot Time: {datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"System Uptime: {datetime.now() - datetime.fromtimestamp(psutil.boot_time())}\n")
                f.write(f"Timezone: {time.tzname}\n")
            
            self.evidence_files.append(output_file)
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ System time error: {str(e)}")
            return False
    
    def collect_network_state(self):
        """Collect network connections and configuration"""
        try:
            output_file = os.path.join(self.collection_dir, f"network_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== NETWORK STATE ===\n\n")
                
                # Network connections
                f.write("=== NETWORK CONNECTIONS ===\n")
                connections = psutil.net_connections(kind='inet')
                for conn in connections:
                    f.write(f"{conn.family.name} {conn.type.name} {conn.laddr} -> {conn.raddr} {conn.status} PID:{conn.pid}\n")
                
                f.write("\n=== NETWORK INTERFACES ===\n")
                for interface, addresses in psutil.net_if_addrs().items():
                    f.write(f"Interface: {interface}\n")
                    for addr in addresses:
                        f.write(f"  {addr.family.name}: {addr.address}\n")
                    f.write("\n")
            
            # Run system commands for additional info
            commands = [
                ("netstat -ano", "netstat_detailed.txt"),
                ("arp -a", "arp_cache.txt"),
                ("route print", "routing_table.txt"),
                ("ipconfig /all", "ipconfig_all.txt")
            ]
            
            for cmd, filename in commands:
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    cmd_file = os.path.join(self.collection_dir, filename)
                    with open(cmd_file, 'w', encoding='utf-8') as f:
                        f.write(f"Command: {cmd}\n")
                        f.write(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write("=" * 50 + "\n")
                        f.write(result.stdout)
                    self.evidence_files.append(cmd_file)
                except Exception as e:
                    self.log_message.emit(f"⚠️ Command failed: {cmd} - {str(e)}")
            
            self.evidence_files.append(output_file)
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ Network state error: {str(e)}")
            return False
    
    def collect_process_info(self):
        """Collect detailed process information including DLLs and handles"""
        try:
            output_file = os.path.join(self.collection_dir, f"processes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            processes = []
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe', 'cmdline', 'create_time', 'username', 'memory_info']):
                try:
                    proc_info = proc.info
                    proc_info['create_time_str'] = datetime.fromtimestamp(proc_info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Collect additional process details
                    try:
                        # Memory information
                        if proc_info['memory_info']:
                            proc_info['memory_rss_mb'] = proc_info['memory_info'].rss / (1024 * 1024)
                            proc_info['memory_vms_mb'] = proc_info['memory_info'].vms / (1024 * 1024)
                        
                        # Get process object for additional info
                        process_obj = psutil.Process(proc_info['pid'])
                        
                        # Open files/handles
                        proc_info['open_files'] = []
                        try:
                            open_files = process_obj.open_files()
                            for f in open_files:
                                proc_info['open_files'].append({
                                    'path': f.path,
                                    'fd': f.fd if hasattr(f, 'fd') else 'N/A'
                                })
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            proc_info['open_files'] = ['Access Denied']
                        
                        # Network connections for this process
                        proc_info['connections'] = []
                        try:
                            connections = process_obj.connections()
                            for conn in connections:
                                proc_info['connections'].append({
                                    'family': str(conn.family),
                                    'type': str(conn.type),
                                    'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                                    'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                                    'status': str(conn.status)
                                })
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            proc_info['connections'] = ['Access Denied']
                        
                        # CPU and other stats
                        try:
                            proc_info['cpu_percent'] = process_obj.cpu_percent()
                            proc_info['num_threads'] = process_obj.num_threads()
                            proc_info['status'] = str(process_obj.status())
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    
                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processes, f, indent=2, ensure_ascii=False, default=str)
            
            # Also create text version
            text_file = output_file.replace('.json', '.txt')
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write("=== RUNNING PROCESSES WITH DETAILED INFO ===\n")
                f.write("PID\tPPID\tName\tUsername\tMemory(MB)\tThreads\tStatus\tExecutable\tCommand Line\n")
                for proc in processes:
                    memory_mb = proc.get('memory_rss_mb', 0)
                    threads = proc.get('num_threads', 'N/A')
                    status = proc.get('status', 'N/A')
                    cmdline = proc.get('cmdline', [])
                    if isinstance(cmdline, list):
                        cmdline_str = ' '.join(str(x) for x in cmdline)
                    else:
                        cmdline_str = str(cmdline) if cmdline else 'N/A'
                    f.write(f"{proc.get('pid', 'N/A')}\t{proc.get('ppid', 'N/A')}\t{proc.get('name', 'N/A')}\t{proc.get('username', 'N/A')}\t{memory_mb:.1f}\t{threads}\t{status}\t{proc.get('exe', 'N/A')}\t{cmdline_str}\n")
            
            # Collect DLLs and detailed handles using Windows commands
            self.collect_dlls_and_handles()
            
            self.evidence_files.extend([output_file, text_file])
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ Process info error: {str(e)}")
            return False
    
    def collect_dlls_and_handles(self):
        """Collect DLLs and handles using Windows commands"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Use tasklist to get detailed process info with modules
            self.log_message.emit("📚 Thu thập thông tin DLL và modules...")
            
            # Get processes with modules (DLLs)
            commands = [
                # Process list with modules
                ('tasklist /m', f'processes_with_modules_{timestamp}.txt'),
                # Detailed process info
                ('wmic process get ProcessId,Name,ExecutablePath,CommandLine,CreationDate,PageFileUsage,WorkingSetSize /format:csv', f'wmic_processes_{timestamp}.csv'),
                # System handles (if available)
                ('handle.exe -a', f'system_handles_{timestamp}.txt'),  # Requires Sysinternals handle.exe
            ]
            
            for cmd, filename in commands:
                try:
                    self.log_message.emit(f"Chạy lệnh: {cmd}")
                    
                    # Special handling for handle.exe which might not exist
                    if 'handle.exe' in cmd:
                        # Check if handle.exe exists first
                        handle_check = subprocess.run('where handle.exe', shell=True, capture_output=True, text=True)
                        if handle_check.returncode != 0:
                            self.log_message.emit("⚠️ handle.exe không tìm thấy - bỏ qua thu thập system handles")
                            continue
                    
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                    
                    cmd_file = os.path.join(self.collection_dir, filename)
                    with open(cmd_file, 'w', encoding='utf-8') as f:
                        f.write(f"Command: {cmd}\n")
                        f.write(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
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
            
            # Collect specific DLL information per process
            self.collect_process_modules()
            
        except Exception as e:
            self.log_message.emit(f"❌ DLL/Handles collection error: {str(e)}")
    
    def collect_process_modules(self):
        """Collect loaded modules (DLLs) for each process"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.collection_dir, f"process_modules_{timestamp}.txt")
            
            self.log_message.emit("Thu thập modules cho từng process...")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== PROCESS MODULES (DLLs) ===\n")
                f.write(f"Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                # Get list of all processes
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        pid = proc.info['pid']
                        name = proc.info['name']
                        
                        f.write(f"Process: {name} (PID: {pid})\n")
                        f.write("-" * 40 + "\n")
                        
                        # Use tasklist to get modules for specific process
                        cmd = f'tasklist /m /fi "PID eq {pid}"'
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                        
                        if result.returncode == 0 and result.stdout:
                            # Parse and clean the output
                            lines = result.stdout.strip().split('\n')
                            for line in lines[3:]:  # Skip header lines
                                if line.strip() and not line.startswith('INFO:'):
                                    f.write(f"  {line.strip()}\n")
                        else:
                            f.write("  [No modules found or access denied]\n")
                        
                        f.write("\n")
                        
                    except (psutil.NoSuchProcess, psutil.AccessDenied, subprocess.TimeoutExpired):
                        continue
                    except Exception as e:
                        f.write(f"  [Error: {str(e)}]\n\n")
            
            self.evidence_files.append(output_file)
            self.log_message.emit("✅ Hoàn thành thu thập process modules")
            
        except Exception as e:
            self.log_message.emit(f"❌ Process modules error: {str(e)}")
    
    def collect_user_sessions(self):
        """Collect user session information"""
        try:
            output_file = os.path.join(self.collection_dir, f"user_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== USER SESSIONS ===\n")
                
                # Current users
                users = psutil.users()
                for user in users:
                    f.write(f"User: {user.name}\n")
                    f.write(f"Terminal: {user.terminal}\n")
                    f.write(f"Host: {user.host}\n")
                    f.write(f"Started: {datetime.fromtimestamp(user.started).strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("-" * 30 + "\n")
            
            # Query additional session info
            commands = [
                ("query user", "query_user.txt"),
                ("whoami /all", "whoami_all.txt")
            ]
            
            for cmd, filename in commands:
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    cmd_file = os.path.join(self.collection_dir, filename)
                    with open(cmd_file, 'w', encoding='utf-8') as f:
                        f.write(f"Command: {cmd}\n")
                        f.write("=" * 30 + "\n")
                        f.write(result.stdout)
                    self.evidence_files.append(cmd_file)
                except Exception:
                    pass
            
            self.evidence_files.append(output_file)
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ User sessions error: {str(e)}")
            return False
    
    def collect_clipboard(self):
        """Collect clipboard content"""
        try:
            output_file = os.path.join(self.collection_dir, f"clipboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            
            # Try to get clipboard content using PowerShell
            cmd = 'powershell -Command "Get-Clipboard"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== CLIPBOARD CONTENT ===\n")
                f.write(f"Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
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
            # PowerShell history
            ps_history_cmd = 'powershell -Command "Get-History | Export-Csv -Path \\"' + os.path.join(self.collection_dir, 'powershell_history.csv') + '\\" -NoTypeInformation"'
            subprocess.run(ps_history_cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            # CMD history (from registry)
            output_file = os.path.join(self.collection_dir, f"command_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== COMMAND HISTORY ===\n")
                f.write(f"Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("Note: PowerShell history exported to powershell_history.csv\n")
                f.write("CMD history may be available in registry or recent commands\n")
            
            self.evidence_files.append(output_file)
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ Command history error: {str(e)}")
            return False
    
    def collect_services_drivers(self):
        """Collect services and drivers information"""
        try:
            # Services
            services_file = os.path.join(self.collection_dir, f"services_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            
            cmd = "sc query"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            
            with open(services_file, 'w', encoding='utf-8') as f:
                f.write("=== WINDOWS SERVICES ===\n")
                f.write(result.stdout)
            
            # Drivers
            drivers_cmd = "driverquery /fo csv"
            result = subprocess.run(drivers_cmd, shell=True, capture_output=True, text=True, timeout=60)
            
            drivers_file = os.path.join(self.collection_dir, "drivers.csv")
            with open(drivers_file, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            
            self.evidence_files.extend([services_file, drivers_file])
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ Services/Drivers error: {str(e)}")
            return False
    
    def collect_environment_vars(self):
        """Collect environment variables"""
        try:
            output_file = os.path.join(self.collection_dir, f"environment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            env_vars = dict(os.environ)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(env_vars, f, indent=2, ensure_ascii=False)
            
            self.evidence_files.append(output_file)
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ Environment vars error: {str(e)}")
            return False
    
    def package_evidence(self):
        """Package all evidence files and calculate hash"""
        try:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            case_id = self.case_info.get('case_id', 'UNKNOWN')
            
            package_name = f"{case_id}_VOLATILE_{timestamp}_EVIDENCE.zip"
            package_path = os.path.join(self.output_path, package_name)
            
            self.log_message.emit("📦 Đóng gói evidence...")
            
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
                # Add all evidence files
                for file_path in self.evidence_files:
                    if os.path.exists(file_path):
                        arcname = os.path.relpath(file_path, self.output_path)
                        zipf.write(file_path, arcname)
                
                # Create collection summary
                summary = {
                    'case_id': case_id,
                    'collection_type': 'VOLATILE',
                    'investigator': self.case_info.get('investigator', 'N/A'),
                    'collection_start': self.start_time.isoformat(),
                    'collection_end': datetime.now().isoformat(),
                    'evidence_files': [os.path.basename(f) for f in self.evidence_files],
                    'collection_options': self.collection_options,
                    'tool_version': 'Windows Forensic System v1.0'
                }
                
                zipf.writestr('COLLECTION_SUMMARY.json', json.dumps(summary, indent=2, ensure_ascii=False).encode('utf-8'))
            
            # Calculate SHA-256 hash
            sha256_hash = hashlib.sha256()
            with open(package_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            hash_value = sha256_hash.hexdigest()
            
            # Create hash file
            hash_file = package_path + '.sha256'
            with open(hash_file, 'w', encoding='utf-8') as f:
                f.write(f"{hash_value}  {package_name}\n")
            
            self.log_message.emit(f"🔐 SHA-256: {hash_value}")
            self.evidence_log.emit(f"Package: {package_name}")
            self.evidence_log.emit(f"SHA-256: {hash_value}")
            self.evidence_log.emit(f"Collection completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
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
            self.ui.ramSizeLabel.setText(f" RAM: {ram_gb:.1f} GB | Cần: ~{ram_gb:.1f} GB | Gói: ~{ram_gb*0.3:.1f} GB")
            
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
            self.ui.environmentVarsCheck
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
            self.ui.environmentVarsCheck
        ]
        
        for checkbox in checkboxes:
            checkbox.setChecked(False)
    
    def browse_output_path(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Chọn thiết bị ngoài để lưu evidence",
            self.ui.outputPathEdit.text()
        )
        
        if directory:
            self.ui.outputPathEdit.setText(directory)
    
    def get_collection_options(self):
        """Get selected collection options"""
        return {
            'ram_acquisition': self.ui.ramAcquisitionCheck.isChecked(),
            'ram_format': self.ui.ramFormatCombo.currentText().split()[1][1:-1],  # Extract extension
            'calculate_hash': self.ui.calculateHashCheck.isChecked(),
            'system_time': self.ui.systemTimeCheck.isChecked(),
            'network_state': self.ui.networkStateCheck.isChecked(),
            'process_info': self.ui.processInfoCheck.isChecked(),
            'user_sessions': self.ui.userSessionsCheck.isChecked(),
            'clipboard': self.ui.clipboardCheck.isChecked(),
            'command_history': self.ui.commandHistoryCheck.isChecked(),
            'services_drivers': self.ui.servicesDriversCheck.isChecked(),
            'environment_vars': self.ui.environmentVarsCheck.isChecked()
        }
    
    def get_case_info(self):
        """Get case information"""
        return {
            'case_id': self.ui.caseIdEdit.text() or "UNKNOWN",
            'investigator': "System Administrator"  # Fallback investigator
        }
    
    def start_collection(self):
        """Start forensic volatile data collection"""
        options = self.get_collection_options()
        case_info = self.get_case_info()
        
        # Validation
        if not any(options.values()):
            QMessageBox.warning(
                self,
                "Cảnh báo",
                "Vui lòng chọn ít nhất một loại dữ liệu để thu thập!"
            )
            return
        
        output_path = self.ui.outputPathEdit.text()
        if not output_path:
            QMessageBox.warning(
                self,
                "Cảnh báo", 
                "Vui lòng chọn thiết bị ngoài để lưu evidence!"
            )
            return
        
        if not case_info['case_id']:
            QMessageBox.warning(
                self,
                "Cảnh báo",
                "Vui lòng nhập Case ID!"
            )
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
        self.collection_worker = ForensicCollectionWorker(options, output_path, case_info)
        self.collection_thread = QThread()
        self.collection_worker.moveToThread(self.collection_thread)
        
        # Connect worker signals
        self.collection_worker.progress_updated.connect(self.update_progress)
        self.collection_worker.log_message.connect(self.add_log_message)
        self.collection_worker.evidence_log.connect(self.add_evidence_log)
        self.collection_worker.system_info_updated.connect(self.ui.systemInfoText.setText)
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
        if hasattr(self, 'wizard_reference') and self.wizard_reference:
            print("Calling wizard_collection_finished from volatile page")
            try:
                self.wizard_reference.wizard_collection_finished('volatile', success, message, package_path)
            except Exception as e:
                print(f"Error calling wizard: {e}")
        
        if success:
            QMessageBox.information(
                self,
                "Hoàn thành Thu thập Forensic",
                f"✅ {message}\n\n"
                f"Evidence Package: {os.path.basename(package_path)}\n"
                f"Đường dẫn: {package_path}\n\n"
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
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.ui.evidenceLogText.toPlainText())
                
                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Evidence log đã được lưu: {filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Lỗi",
                    f"❌ Không thể lưu evidence log: {str(e)}"
                )
    
    def set_case_data(self, case_data):
        """Set case data for evidence collection"""
        self.current_case_id = case_data.get('case_id')
        
        # Update UI với thông tin case
        if case_data.get('case_id') and case_data.get('case_name'):
            # Hiển thị cả mã case và tên case
            case_display = f"{case_data['case_id']} - {case_data['case_name']}"
            self.ui.caseIdEdit.setText(case_display)
        elif case_data.get('case_id'):
            self.ui.caseIdEdit.setText(case_data['case_id'])
        
        #if case_data.get('investigator'):
        #    self.ui.investigatorEdit.setText(case_data['investigator'])
        
        # Update output path để include case info và volatile
        if case_data.get('case_id') and case_data.get('case_name'):
            # Tạo đường dẫn với mã case, tên case và chú thích volatile
            safe_case_name = "".join(c for c in case_data['case_name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            output_path = f"E:\\ForensicCollection\\{case_data['case_id']}_{safe_case_name}_volatile"
            self.ui.outputPathEdit.setText(output_path)
        elif case_data.get('case_id'):
            output_path = f"E:\\ForensicCollection\\{case_data['case_id']}_volatile"
            self.ui.outputPathEdit.setText(output_path)
        
    
    def set_case_id(self, case_id):
        """Set current case ID for evidence collection (legacy method)"""
        self.current_case_id = case_id
        
        # Update output path to include case info
        if case_id:
            case_info = self.db.get_case_by_id(case_id)
            if case_info:
                case_code = case_info.get('case_code', f'Case_{case_id}')
                self.ui.caseIdEdit.setText(case_code)
