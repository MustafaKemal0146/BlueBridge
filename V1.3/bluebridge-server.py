#!/usr/bin/env python3
"""
BlueBridge - Raspberry Pi Bluetooth IP Server (Real Bluetooth)
Automatically starts on boot and sends IP address to connected Android device
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
    
    def get_system_info(self):
        """Get additional system information"""
        try:
            # Get hostname
            hostname = socket.gethostname()
            
            # Get current time
            current_time = datetime.now().isoformat()
            
            # Get IP address
            ip_address = self.get_ip_address()
            
            return {
                "hostname": hostname,
                "ip_address": ip_address,
                "timestamp": current_time,
                "service": self.service_name
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