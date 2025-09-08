    def collect_process_info(self):
        """Collect detailed process information including DLLs and handles"""
        try:
            output_file = os.path.join(
                self.collection_dir,
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

                    # Collect additional process details
                    try:
                        # Memory information
                        if proc_info["memory_info"]:
                            proc_info["memory_rss_mb"] = proc_info[
                                "memory_info"
                            ].rss / (1024 * 1024)
                            proc_info["memory_vms_mb"] = proc_info[
                                "memory_info"
                            ].vms / (1024 * 1024)

                        # Get process object for additional info
                        process_obj = psutil.Process(proc_info["pid"])

                        # Open files/handles
                        proc_info["open_files"] = []
                        try:
                            open_files = process_obj.open_files()
                            for f in open_files:
                                proc_info["open_files"].append(
                                    {
                                        "path": f.path,
                                        "fd": f.fd if hasattr(f, "fd") else "N/A",
                                    }
                                )
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            proc_info["open_files"] = ["Access Denied"]

                        # Network connections for this process
                        proc_info["connections"] = []
                        try:
                            connections = process_obj.connections()
                            for conn in connections:
                                proc_info["connections"].append(
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
                                )
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            proc_info["connections"] = ["Access Denied"]

                        # CPU and other stats
                        try:
                            proc_info["cpu_percent"] = process_obj.cpu_percent()
                            proc_info["num_threads"] = process_obj.num_threads()
                            proc_info["status"] = str(process_obj.status())
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(processes, f, indent=2, ensure_ascii=False, default=str)

            # Collect DLLs and detailed handles using Windows commands
            self.collect_dlls_and_handles()

            self.evidence_files.extend(output_file)
            return True

        except Exception as e:
            self.log_message.emit(f"❌ Process info error: {str(e)}")
            return False

    def collect_dlls_and_handles(self):
        """Collect DLLs and handles using Windows commands"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Use tasklist to get detailed process info with modules
            self.log_message.emit("📚 Thu thập thông tin DLL và modules...")

            # Get processes with modules (DLLs)
            commands = [
                # Process list with modules
                ("tasklist /m", f"processes_with_modules_{timestamp}.txt"),
                # Detailed process info
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

                    cmd_file = os.path.join(self.collection_dir, filename)
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

            # Collect specific DLL information per process
            self.collect_process_modules()

        except Exception as e:
            self.log_message.emit(f"❌ DLL/Handles collection error: {str(e)}")

    def collect_process_modules(self):
        """Collect loaded modules (DLLs) for each process"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                self.collection_dir, f"process_modules_{timestamp}.txt"
            )

            self.log_message.emit("Thu thập modules cho từng process...")

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("=== PROCESS MODULES (DLLs) ===\n")
                f.write(
                    f"Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write("=" * 60 + "\n\n")

                # Get list of all processes
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        pid = proc.info["pid"]
                        name = proc.info["name"]

                        f.write(f"Process: {name} (PID: {pid})\n")
                        f.write("-" * 40 + "\n")

                        # Use tasklist to get modules for specific process
                        cmd = f'tasklist /m /fi "PID eq {pid}"'
                        result = subprocess.run(
                            cmd, shell=True, capture_output=True, text=True, timeout=30
                        )

                        if result.returncode == 0 and result.stdout:
                            # Parse and clean the output
                            lines = result.stdout.strip().split("\n")
                            for line in lines[3:]:  # Skip header lines
                                if line.strip() and not line.startswith("INFO:"):
                                    f.write(f"  {line.strip()}\n")
                        else:
                            f.write("  [No modules found or access denied]\n")

                        f.write("\n")

                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        subprocess.TimeoutExpired,
                    ):
                        continue
                    except Exception as e:
                        f.write(f"  [Error: {str(e)}]\n\n")

            self.evidence_files.append(output_file)
            self.log_message.emit("✅ Hoàn thành thu thập process modules")

        except Exception as e:
            self.log_message.emit(f"❌ Process modules error: {str(e)}")