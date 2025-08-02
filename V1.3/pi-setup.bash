#!/bin/bash

# BlueBridge Raspberry Pi Setup Script
# This script installs and configures BlueBridge server as a system service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    print_success "System packages updated"
}

# Install required packages
install_packages() {
    print_status "Installing required packages..."
    
    # Install Python and pip if not already installed
    apt install -y python3 python3-pip python3-dev
    
    # Install Bluetooth packages
    apt install -y bluetooth bluez bluez-tools rfcomm
    
    # Install Python packages
    pip3 install --upgrade pip
    
    print_success "Required packages installed"
}

# Configure Bluetooth
configure_bluetooth() {
    print_status "Configuring Bluetooth..."
    
    # Enable Bluetooth service
    systemctl enable bluetooth
    systemctl start bluetooth
    
    # Make device discoverable
    bluetoothctl <<EOF
power on
discoverable on
pairable on
agent on
default-agent
EOF

    # Configure Bluetooth settings
    if [ -f /etc/bluetooth/main.conf ]; then
        # Backup original config
        cp /etc/bluetooth/main.conf /etc/bluetooth/main.conf.backup
        
        # Enable classic mode and set device class
        sed -i 's/#Class = 0x000100/Class = 0x000100/' /etc/bluetooth/main.conf
        sed -i 's/#DiscoverableTimeout = 0/DiscoverableTimeout = 0/' /etc/bluetooth/main.conf
        sed -i 's/#PairableTimeout = 0/PairableTimeout = 0/' /etc/bluetooth/main.conf
    fi
    
    print_success "Bluetooth configured"
}

# Install BlueBridge server
install_bluebridge() {
    print_status "Installing BlueBridge server..."
    
    # Create BlueBridge directory
    mkdir -p /opt/bluebridge
    
    # Copy server script
    if [ -f "bluebridge-server.py" ]; then
        cp bluebridge-server.py /opt/bluebridge/
        chmod +x /opt/bluebridge/bluebridge-server.py
    else
        print_error "bluebridge-server.py not found in current directory"
        exit 1
    fi
    
    # Create log directory
    mkdir -p /var/log
    touch /var/log/bluebridge.log
    chmod 644 /var/log/bluebridge.log
    
    print_success "BlueBridge server installed"
}

# Create systemd service
create_service() {
    print_status "Creating systemd service..."
    
    cat > /etc/systemd/system/bluebridge.service << EOF
[Unit]
Description=BlueBridge Bluetooth IP Server
After=bluetooth.service
Wants=bluetooth.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bluebridge
ExecStart=/usr/bin/python3 /opt/bluebridge/bluebridge-server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment variables
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable bluebridge.service
    
    print_success "Systemd service created and enabled"
}

# Configure firewall (if ufw is installed)
configure_firewall() {
    if command -v ufw &> /dev/null; then
        print_status "Configuring firewall..."
        # Allow Bluetooth connections
        ufw allow from any to any port 1 proto tcp
        print_success "Firewall configured"
    fi
}

# Start services
start_services() {
    print_status "Starting services..."
    
    # Restart Bluetooth service
    systemctl restart bluetooth
    sleep 2
    
    # Start BlueBridge service
    systemctl start bluebridge.service
    
    print_success "Services started"
}

# Check service status
check_status() {
    print_status "Checking service status..."
    
    # Check Bluetooth status
    if systemctl is-active --quiet bluetooth; then
        print_success "Bluetooth service is running"
    else
        print_warning "Bluetooth service is not running"
    fi
    
    # Check BlueBridge status
    if systemctl is-active --quiet bluebridge; then
        print_success "BlueBridge service is running"
    else
        print_warning "BlueBridge service is not running"
    fi
    
    # Show service logs
    print_status "Recent BlueBridge logs:"
    journalctl -u bluebridge -n 10 --no-pager
}

# Create uninstall script
create_uninstall() {
    print_status "Creating uninstall script..."
    
    cat > /opt/bluebridge/uninstall.sh << 'EOF'
#!/bin/bash

echo "Uninstalling BlueBridge..."

# Stop and disable service
sudo systemctl stop bluebridge.service
sudo systemctl disable bluebridge.service

# Remove service file
sudo rm -f /etc/systemd/system/bluebridge.service
sudo systemctl daemon-reload

# Remove BlueBridge files
sudo rm -rf /opt/bluebridge

# Remove log file
sudo rm -f /var/log/bluebridge.log

echo "BlueBridge uninstalled successfully"
echo "Note: Bluetooth packages and configuration are left intact"
EOF

    chmod +x /opt/bluebridge/uninstall.sh
    print_success "Uninstall script created at /opt/bluebridge/uninstall.sh"
}

# Main installation function
main() {
    echo ""
    echo "=========================================="
    echo "  BlueBridge Raspberry Pi Setup Script"
    echo "=========================================="
    echo ""
    
    check_root
    
    print_status "Starting BlueBridge installation..."
    
    # Installation steps
    update_system
    install_packages
    configure_bluetooth
    install_bluebridge
    create_service
    configure_firewall
    start_services
    create_uninstall
    
    echo ""
    echo "=========================================="
    print_success "BlueBridge installation completed!"
    echo "=========================================="
    echo ""
    
    print_status "Service Information:"
    echo "  • Service name: bluebridge"
    echo "  • Log file: /var/log/bluebridge.log"
    echo "  • Config directory: /opt/bluebridge"
    echo ""
    
    print_status "Useful Commands:"
    echo "  • Check status: sudo systemctl status bluebridge"
    echo "  • View logs: sudo journalctl -u bluebridge -f"
    echo "  • Restart service: sudo systemctl restart bluebridge"
    echo "  • Stop service: sudo systemctl stop bluebridge"
    echo "  • Uninstall: sudo /opt/bluebridge/uninstall.sh"
    echo ""
    
    print_status "Bluetooth Information:"
    echo "  • Device should be discoverable as: $(hostname)"
    echo "  • Service name: BlueBridge-Service"
    echo "  • Make sure your Android device can discover this Pi"
    echo ""
    
    check_status
    
    echo ""
    print_success "Setup complete! Your Raspberry Pi is ready for BlueBridge connections."
    print_status "You can now use the BlueBridge Android app to connect to this Pi."
    echo ""
}

# Run main function
main "$@"