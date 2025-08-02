#!/usr/bin/env python3
"""
BlueBridge - Raspberry Pi Bluetooth IP Server v1.4.0
Automatically starts on boot and sends IP address + system info to connected Android device
Features: SSH integration, real-time system monitoring, performance metrics
"""

import socket
import subprocess
import time
import logging
import json
from datetime import datetime
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/bluebridge.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BluetoothIPServer:
    def __init__(self):
        self.service_name = "BlueBridge-Service"
        self.version = "1.4.0"
        self.server_socket = None
        self.client_socket = None
        self.is_running = False
        
    def get_ip_address(self):
        """Get the current IP address of the Pi"""
        try:
            # Try to get IP from hostname command
            result = subprocess.run(['hostname', '-I'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                # Return the first non-localhost IP
                for ip in ips:
                    if ip != '127.0.0.1' and not ip.startswith('169.254'):
                        return ip
            
            # Alternative method using socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
            
        except Exception as e:
            logger.error(f"Error getting IP address: {e}")
            return None
    
    def check_ssh_status(self):
        """Check if SSH service is running"""
        try:
            result = subprocess.run(['systemctl', 'is-active', 'ssh'], 
                                  capture_output=True, text=True)
            return result.stdout.strip() == 'active'
        except:
            return False
    
    def get_ssh_info(self):
        """Get SSH connection information"""
        try:
            # Get current user
            current_user = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip()
            
            # Check SSH port (default 22)
            ssh_port = 22
            try:
                with open('/etc/ssh/sshd_config', 'r') as f:
                    for line in f:
                        if line.strip().startswith('Port ') and not line.strip().startswith('#'):
                            ssh_port = int(line.split()[1])
                            break
            except:
                pass
            
            return {
                "ssh_enabled": self.check_ssh_status(),
                "ssh_port": ssh_port,
                "ssh_user": current_user,
                "ssh_command": f"ssh {current_user}@{self.get_ip_address()}"
            }
        except Exception as e:
            logger.error(f"Error getting SSH info: {e}")
            return {
                "ssh_enabled": False,
                "ssh_port": 22,
                "ssh_user": "pi",
                "ssh_command": f"ssh pi@{self.get_ip_address()}"
            }

    def get_performance_info(self):
        """Get system performance information - NEW in v1.4.0"""
        try:
            performance = {}
            
            # CPU usage from load average
            try:
                with open('/proc/loadavg', 'r') as f:
                    load_avg = f.read().strip().split()[0]
                    # Convert load average to percentage (rough estimate)
                    performance['cpu_usage'] = min(int(float(load_avg) * 100), 100)
            except:
                performance['cpu_usage'] = 0
            
            # Memory usage from /proc/meminfo
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    total = int([line for line in meminfo.split('\n') if 'MemTotal' in line][0].split()[1])
                    available = int([line for line in meminfo.split('\n') if 'MemAvailable' in line][0].split()[1])
                    used = total - available
                    performance['memory_usage'] = int((used / total) * 100)
            except:
                performance['memory_usage'] = 0
            
            # Disk usage from df command
            try:
                result = subprocess.run(['df', '/'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 5:
                            usage_percent = parts[4].replace('%', '')
                            performance['disk_usage'] = int(usage_percent)
            except:
                performance['disk_usage'] = 0
            
            # CPU Temperature from thermal zone
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = int(f.read().strip()) / 1000
                    performance['temperature'] = int(temp)
            except:
                performance['temperature'] = 0
            
            return performance
        except Exception as e:
            logger.error(f"Error getting performance info: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'temperature': 0
            }

    def get_system_info(self):
        """Get complete system information including performance metrics"""
        try:
            # Get hostname
            hostname = socket.gethostname()
            
            # Get current time
            current_time = datetime.now().isoformat()
            
            # Get IP address
            ip_address = self.get_ip_address()
            
            # Get SSH info
            ssh_info = self.get_ssh_info()
            
            # Get performance info (NEW in v1.4.0)
            performance_info = self.get_performance_info()
            
            return {
                "hostname": hostname,
                "ip_address": ip_address,
                "timestamp": current_time,
                "service": self.service_name,
                "version": self.version,
                **ssh_info,
                **performance_info
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return None

    def setup_bluetooth_server(self):
        """Setup Bluetooth server using rfcomm"""
        try:
            # Kill any existing rfcomm processes
            subprocess.run(['sudo', 'pkill', '-f', 'rfcomm'], capture_output=True)
            
            # Setup rfcomm server on channel 1
            cmd = ['sudo', 'rfcomm', 'listen', '/dev/rfcomm0', '1']
            self.rfcomm_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info("Bluetooth RFCOMM server started on channel 1")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Bluetooth server: {e}")
            return False

    def handle_bluetooth_connection(self):
        """Handle Bluetooth connections via rfcomm"""
        try:
            while self.is_running:
                try:
                    # Check if rfcomm device exists and is ready
                    if subprocess.run(['test', '-c', '/dev/rfcomm0'], capture_output=True).returncode == 0:
                        # Open rfcomm device for communication
                        with open('/dev/rfcomm0', 'r+b', buffering=0) as rfcomm:
                            logger.info("Bluetooth connection established")
                            
                            while self.is_running:
                                try:
                                    # Send system info every 5 seconds
                                    system_info = self.get_system_info()
                                    if system_info:
                                        message = json.dumps(system_info) + '\n'
                                        rfcomm.write(message.encode('utf-8'))
                                        rfcomm.flush()
                                        logger.info(f"Sent: {system_info}")
                                    
                                    time.sleep(5)
                                    
                                except Exception as e:
                                    logger.error(f"Error in communication: {e}")
                                    break
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error handling connection: {e}")
                    time.sleep(5)
                    
        except Exception as e:
            logger.error(f"Error in Bluetooth handler: {e}")

    def run_simple_server(self):
        """Run simple file-based server as fallback"""
        logger.info("Running simple file-based server")
        
        while self.is_running:
            try:
                system_info = self.get_system_info()
                if system_info:
                    # Write to file for mobile app to read
                    with open('/tmp/bluebridge_info.json', 'w') as f:
                        json.dump(system_info, f)
                    
                    logger.info(f"Updated system info: {system_info}")
                
                time.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in simple server: {e}")
                time.sleep(5)

    def run(self):
        """Main server loop"""
        logger.info("Starting BlueBridge Bluetooth IP Server")
        self.is_running = True
        
        # Try to setup Bluetooth server
        bluetooth_setup = self.setup_bluetooth_server()
        
        if bluetooth_setup:
            # Start Bluetooth handler in separate thread
            bluetooth_thread = threading.Thread(target=self.handle_bluetooth_connection)
            bluetooth_thread.daemon = True
            bluetooth_thread.start()
            logger.info("Bluetooth server thread started")
        
        # Always run simple server as fallback
        try:
            self.run_simple_server()
        except KeyboardInterrupt:
            logger.info("Server shutdown requested")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up...")
        self.is_running = False
        
        try:
            if hasattr(self, 'rfcomm_process'):
                self.rfcomm_process.terminate()
            subprocess.run(['sudo', 'pkill', '-f', 'rfcomm'], capture_output=True)
        except:
            pass

def main():
    logger.info("Starting BlueBridge IP Server")
    
    server = BluetoothIPServer()
    server.run()

if __name__ == "__main__":
    main()