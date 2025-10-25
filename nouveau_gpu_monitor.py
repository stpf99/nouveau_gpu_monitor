#!/usr/bin/env python3
"""
Nouveau GPU Monitor - Enhanced Edition
Universal GPU monitoring application for NVIDIA cards with Nouveau driver
Supports all generations from GeForce 6 to RTX 50xx

Requirements: PyQt6, PyQt6-Charts, notify2, psutil
Install: pip install PyQt6 PyQt6-Charts notify2 psutil
or: sudo pacman -S python-pyqt6 python-pyqt6-charts python-notify2 python-psutil

Daemon mode:
python3 nouveau_monitor_enhanced.py --daemon
"""

import sys
import os
import subprocess
import re
import time
import signal
import json
import argparse
import threading
from datetime import datetime, timedelta
from collections import deque
import psutil
import math

# PyQt imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QTabWidget, QTableWidget, 
                             QTableWidgetItem, QGroupBox, QProgressBar, QTextEdit,
                             QHeaderView, QPushButton, QMessageBox, QScrollArea,
                             QCheckBox, QSpinBox, QDialog, QDialogButtonBox, QGridLayout, QComboBox)
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal, QObject, QRectF
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QLinearGradient, QBrush, QPen
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QAreaSeries, QBarSeries, QBarSet, QBarCategoryAxis

# Notify2 for notifications
try:
    import notify2
    notify2.init("Nouveau GPU Monitor")
    NOTIFY_AVAILABLE = True
except ImportError:
    NOTIFY_AVAILABLE = False
    print("Warning: notify2 not installed - notifications unavailable")

# GPU Architecture Knowledge Base - UPDATED
GPU_ARCHITECTURES = {
    'NV40': {'name': 'Curie', 'series': 'GeForce 6/7', 'opengl': '2.1', 'year': '2004-2006', 'va_api': 'None'},
    'NV50': {'name': 'Tesla', 'series': 'GeForce 8/9/GT 2xx', 'opengl': '3.3', 'year': '2006-2010', 'va_api': 'Very limited'},
    'NVC0': {'name': 'Fermi', 'series': 'GeForce 4xx/5xx', 'opengl': '4.3', 'year': '2010-2012', 'va_api': 'Partial'},
    'NVE0': {'name': 'Kepler', 'series': 'GeForce 6xx/7xx', 'opengl': '4.5', 'year': '2012-2014', 'va_api': 'Good'},
    'GM100': {'name': 'Maxwell', 'series': 'GeForce 9xx/10xx', 'opengl': '4.6', 'year': '2014-2016', 'va_api': 'Very good'},
    'GP100': {'name': 'Pascal', 'series': 'GeForce 10xx', 'opengl': '4.6', 'year': '2016-2018', 'va_api': 'Very good'},
    'GV100': {'name': 'Volta', 'series': 'Titan V', 'opengl': '4.6', 'year': '2017', 'va_api': 'Very good'},
    'TU100': {'name': 'Turing', 'series': 'GeForce 16xx/RTX 20xx', 'opengl': '4.6', 'year': '2018-2020', 'va_api': 'Excellent'},
    'GA100': {'name': 'Ampere', 'series': 'RTX 30xx', 'opengl': '4.6', 'year': '2020-2022', 'va_api': 'Excellent'},
    'AD100': {'name': 'Ada Lovelace', 'series': 'RTX 40xx', 'opengl': '4.6', 'year': '2022+', 'va_api': 'Excellent'},
    'GB100': {'name': 'Blackwell', 'series': 'RTX 50xx', 'opengl': '4.6', 'year': '2024-2025', 'va_api': 'Excellent'},
    'GB200': {'name': 'Blackwell 2.0', 'series': 'RTX 60xx', 'opengl': '4.6', 'year': '2025-2026', 'va_api': 'Excellent'},
    'GH100': {'name': 'Hopper', 'series': 'H100/H200', 'opengl': '4.6', 'year': '2022-2024', 'va_api': 'Excellent'},
}

# Corrected chip database
CHIP_DATABASE = {
    # Tesla
    'G86': {'arch': 'NV50', 'name': 'GeForce 8400 GS/8500 GT'},
    'G84': {'arch': 'NV50', 'name': 'GeForce 8600 GT/GTS'},
    'G92': {'arch': 'NV50', 'name': 'GeForce 8800 GT/GTS/GTX'},
    'G94': {'arch': 'NV50', 'name': 'GeForce 9600 GT/GSO'},
    'G96': {'arch': 'NV50', 'name': 'GeForce 9400 GT/9500 GT'},
    'G98': {'arch': 'NV50', 'name': 'GeForce 8400 GS (renew)/9300 GS/9400 GT'},
    'GT200': {'arch': 'NV50', 'name': 'GeForce GTX 260/280/285'},
    'GT215': {'arch': 'NV50', 'name': 'GeForce GT 220/240'},
    'GT216': {'arch': 'NV50', 'name': 'GeForce GT 220'},
    'GT218': {'arch': 'NV50', 'name': 'GeForce GT 210/205'},
    
    # Fermi
    'GF100': {'arch': 'NVC0', 'name': 'GeForce GTX 480/470/465'},
    'GF104': {'arch': 'NVC0', 'name': 'GeForce GTX 460'},
    'GF106': {'arch': 'NVC0', 'name': 'GeForce GTS 450'},
    'GF108': {'arch': 'NVC0', 'name': 'GeForce GT 430/440'},
    'GF110': {'arch': 'NVC0', 'name': 'GeForce GTX 580/570/560 Ti'},
    'GF114': {'arch': 'NVC0', 'name': 'GeForce GTX 560 Ti/550 Ti'},
    'GF116': {'arch': 'NVC0', 'name': 'GeForce GTX 550 Ti/560'},
    'GF119': {'arch': 'NVC0', 'name': 'GeForce GT 520/610'},
    
    # Kepler
    'GK104': {'arch': 'NVE0', 'name': 'GeForce GTX 680/670/660 Ti'},
    'GK106': {'arch': 'NVE0', 'name': 'GeForce GTX 660/650 Ti'},
    'GK107': {'arch': 'NVE0', 'name': 'GeForce GT 640/650'},
    'GK110': {'arch': 'NVE0', 'name': 'GeForce GTX 780/770/TITAN'},
    'GK208': {'arch': 'NVE0', 'name': 'GeForce GT 730/710'},
    
    # Maxwell
    'GM107': {'arch': 'GM100', 'name': 'GeForce GTX 750/750 Ti'},
    'GM108': {'arch': 'GM100', 'name': 'GeForce GTX 950/960'},
    'GM200': {'arch': 'GM100', 'name': 'GeForce GTX 980/970/TITAN X'},
    'GM204': {'arch': 'GM100', 'name': 'GeForce GTX 980/970'},
    'GM206': {'arch': 'GM100', 'name': 'GeForce GTX 960/950'},
    
    # Pascal
    'GP104': {'arch': 'GP100', 'name': 'GeForce GTX 1080/1070'},
    'GP106': {'arch': 'GP100', 'name': 'GeForce GTX 1060'},
    'GP107': {'arch': 'GP100', 'name': 'GeForce GTX 1050 Ti/1050'},
    'GP102': {'arch': 'GP100', 'name': 'GeForce GTX 1080 Ti/TITAN Xp'},
    
    # Volta
    'GV100': {'arch': 'GV100', 'name': 'TITAN V'},
    
    # Turing
    'TU102': {'arch': 'TU100', 'name': 'GeForce RTX 2080 Ti/TITAN RTX'},
    'TU104': {'arch': 'TU100', 'name': 'GeForce RTX 2080/2070/2060 Super'},
    'TU106': {'arch': 'TU100', 'name': 'GeForce RTX 2060/2060 Super'},
    'TU116': {'arch': 'TU100', 'name': 'GeForce GTX 1660 Ti/1660/1650 Super'},
    'TU117': {'arch': 'TU100', 'name': 'GeForce GTX 1650'},
    
    # Ampere
    'GA102': {'arch': 'GA100', 'name': 'GeForce RTX 3090/3080 Ti/3080'},
    'GA103': {'arch': 'GA100', 'name': 'GeForce RTX 3070 Ti/3070'},
    'GA104': {'arch': 'GA100', 'name': 'GeForce RTX 3060 Ti/3060'},
    'GA106': {'arch': 'GA100', 'name': 'GeForce RTX 3050'},
    'GA107': {'arch': 'GA100', 'name': 'GeForce RTX 3050'},
    
    # Ada Lovelace
    'AD102': {'arch': 'AD100', 'name': 'GeForce RTX 4090'},
    'AD103': {'arch': 'AD100', 'name': 'GeForce RTX 4080'},
    'AD104': {'arch': 'AD100', 'name': 'GeForce RTX 4070 Ti/4070'},
    'AD106': {'arch': 'AD100', 'name': 'GeForce RTX 4060 Ti/4060'},
    'AD107': {'arch': 'AD100', 'name': 'GeForce RTX 4050'},
    
    # Blackwell
    'GB102': {'arch': 'GB100', 'name': 'GeForce RTX 5090'},
    'GB103': {'arch': 'GB100', 'name': 'GeForce RTX 5080'},
    'GB104': {'arch': 'GB100', 'name': 'GeForce RTX 5070 Ti/5070'},
    'GB106': {'arch': 'GB100', 'name': 'GeForce RTX 5060 Ti/5060'},
    'GB107': {'arch': 'GB100', 'name': 'GeForce RTX 5050'},
    
    # Blackwell 2.0
    'GB202': {'arch': 'GB200', 'name': 'GeForce RTX 6090'},
    'GB203': {'arch': 'GB200', 'name': 'GeForce RTX 6080'},
    'GB204': {'arch': 'GB200', 'name': 'GeForce RTX 6070 Ti/6070'},
    'GB206': {'arch': 'GB200', 'name': 'GeForce RTX 6060 Ti/6060'},
    'GB207': {'arch': 'GB200', 'name': 'GeForce RTX 6050'},
    
    # Hopper
    'GH100': {'arch': 'GH100', 'name': 'NVIDIA H100'},
    'GH200': {'arch': 'GH100', 'name': 'NVIDIA H200'},
}

# Daemon configuration
DAEMON_CONFIG = {
    'log_file': os.path.expanduser('~/.nouveau_monitor_daemon.log'),
    'config_file': os.path.expanduser('~/.nouveau_monitor_config.json'),
    'temp_threshold': 85,  # Temperature threshold (°C)
    'critical_threshold': 95,  # Critical temperature threshold (°C)
    'check_interval': 5,  # Check interval (seconds)
    'user_activity_timeout': 60,  # User inactivity timeout (seconds)
    'max_log_entries': 1000,  # Maximum log entries
    'auto_kill': False,  # Auto kill processes
    'notify_video_accel': True,  # Video acceleration notifications
    'cooling_mode': 'auto',  # Cooling mode: passive, active, auto
}

# Enhanced logging system
class EnhancedLogger:
    def __init__(self, log_file):
        self.log_file = log_file
        self.temp_history = deque(maxlen=1000)  # Store more history
        self.process_temp_map = {}  # Process-temperature mapping
        self.anomaly_threshold = 5.0  # Temperature anomaly threshold (°C/s)
        self.anomaly_events = []  # Anomaly event records
        self.cooling_mode = 'auto'  # Track cooling mode
        
    def log_temp_change(self, timestamp, temp, processes):
        """Log temperature changes and associated processes"""
        self.temp_history.append((timestamp, temp))
        
        # Detect temperature anomalies
        if len(self.temp_history) >= 2:
            prev_time, prev_temp = self.temp_history[-2]
            time_diff = (timestamp - prev_time).total_seconds()
            temp_diff = temp - prev_temp
            
            if time_diff > 0 and abs(temp_diff / time_diff) > self.anomaly_threshold:
                self._log_anomaly(timestamp, temp_diff / time_diff, processes)
        
        # Record current processes
        for pid, proc_info in processes.items():
            if pid not in self.process_temp_map:
                self.process_temp_map[pid] = {
                    'name': proc_info['name'],
                    'start_time': timestamp,
                    'temp_at_start': temp,
                    'temp_history': deque(maxlen=100)
                }
            self.process_temp_map[pid]['temp_history'].append((timestamp, temp))
    
    def _log_anomaly(self, timestamp, rate, processes):
        """Log temperature anomaly event"""
        event = {
            'timestamp': timestamp,
            'rate': rate,  # Temperature change rate (°C/s)
            'processes': {pid: info['name'] for pid, info in processes.items()}
        }
        self.anomaly_events.append(event)
        
        # Write to log file
        with open(self.log_file, 'a') as f:
            f.write(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Temperature anomaly: {rate:.2f}°C/s\n")
            for pid, name in event['processes'].items():
                f.write(f"  Process {pid}: {name}\n")
            f.write("\n")
        
        return event
    
    def set_cooling_mode(self, mode):
        """Set cooling mode"""
        self.cooling_mode = mode

# Daemon settings dialog
class DaemonSettingsDialog(QDialog):
    """Daemon settings dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daemon Settings")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Temperature thresholds
        temp_group = QGroupBox("Temperature Thresholds (°C)")
        temp_layout = QHBoxLayout()
        
        self.temp_threshold_spin = QSpinBox()
        self.temp_threshold_spin.setRange(60, 100)
        self.temp_threshold_spin.setValue(DAEMON_CONFIG['temp_threshold'])
        temp_layout.addWidget(QLabel("Warning:"))
        temp_layout.addWidget(self.temp_threshold_spin)
        
        self.critical_threshold_spin = QSpinBox()
        self.critical_threshold_spin.setRange(80, 120)
        self.critical_threshold_spin.setValue(DAEMON_CONFIG['critical_threshold'])
        temp_layout.addWidget(QLabel("Critical:"))
        temp_layout.addWidget(self.critical_threshold_spin)
        
        temp_group.setLayout(temp_layout)
        layout.addWidget(temp_group)
        
        # Check interval
        interval_group = QGroupBox("Check Interval")
        interval_layout = QHBoxLayout()
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(DAEMON_CONFIG['check_interval'])
        interval_layout.addWidget(QLabel("Seconds:"))
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        
        interval_group.setLayout(interval_layout)
        layout.addWidget(interval_group)
        
        # Cooling mode
        cooling_group = QGroupBox("Cooling Mode")
        cooling_layout = QVBoxLayout()
        
        self.cooling_combo = QComboBox()
        self.cooling_combo.addItems(['auto', 'passive', 'active'])
        self.cooling_combo.setCurrentText(DAEMON_CONFIG['cooling_mode'])
        cooling_layout.addWidget(QLabel("Select cooling mode:"))
        cooling_layout.addWidget(self.cooling_combo)
        
        cooling_info = QLabel(
            "• <b>Auto</b>: Automatically switch between passive and active based on temperature<br>"
            "• <b>Passive</b>: Use passive cooling only (slower response, quieter)<br>"
            "• <b>Active</b>: Use active cooling (faster response, more noise)"
        )
        cooling_info.setWordWrap(True)
        cooling_layout.addWidget(cooling_info)
        
        cooling_group.setLayout(cooling_layout)
        layout.addWidget(cooling_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        
        self.auto_kill_checkbox = QCheckBox("Automatically kill dangerous processes")
        self.auto_kill_checkbox.setChecked(DAEMON_CONFIG['auto_kill'])
        options_layout.addWidget(self.auto_kill_checkbox)
        
        self.notify_video_checkbox = QCheckBox("Notify about video acceleration")
        self.notify_video_checkbox.setChecked(DAEMON_CONFIG['notify_video_accel'])
        options_layout.addWidget(self.notify_video_checkbox)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_settings(self):
        return {
            'temp_threshold': self.temp_threshold_spin.value(),
            'critical_threshold': self.critical_threshold_spin.value(),
            'check_interval': self.interval_spin.value(),
            'cooling_mode': self.cooling_combo.currentText(),
            'auto_kill': self.auto_kill_checkbox.isChecked(),
            'notify_video_accel': self.notify_video_checkbox.isChecked()
        }

# Enhanced GPU Monitor main class
class EnhancedGPUMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nouveau GPU Monitor - Enhanced Edition")
        self.setMinimumSize(1400, 900)
        
        # Initialize enhanced logging system
        self.logger = EnhancedLogger(DAEMON_CONFIG['log_file'])
        
        # Resource monitoring data
        self.cpu_history = deque(maxlen=60)
        self.mem_history = deque(maxlen=60)
        self.vram_history = deque(maxlen=60)
        self.process_cpu_history = {}  # Process CPU usage history
        self.process_mem_history = {}  # Process memory usage history
        
        # Temperature history
        self.temp_history = deque(maxlen=120)  # 2 minutes history
        
        # Cooling mode tracking
        self.current_cooling_mode = DAEMON_CONFIG['cooling_mode']
        self.cooling_mode_history = deque(maxlen=120)  # Track cooling mode changes
        
        # Cache GPU information
        self.gpu_info = self.detect_gpu()
        self.gpu_arch = self.detect_architecture()
        
        # Find nouveau-pci-XXXX identifier
        self.nouveau_pci_id = self.find_nouveau_pci_id()
        
        # Track processes using video acceleration
        self.video_accel_processes = set()
        
        # Initialize UI
        self.init_ui()
        # Set timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
    
        # Delayed start - give UI time to fully initialize
        QTimer.singleShot(1000, lambda: self.timer.start(2000))  # Start after 1 second
    
        #Initial update after UI is ready
        QTimer.singleShot(500, self.initial_update)

        
        # First update
        self.update_data()
    
    def find_nouveau_pci_id(self):
        """Find nouveau-pci-XXXX identifier from sensors"""
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            for line in result.stdout.split('\n'):
                if 'nouveau-pci-' in line:
                    match = re.search(r'nouveau-pci-(\d+)', line)
                    if match:
                        return match.group(1)
        except Exception as e:
            print(f"Error searching nouveau-pci: {e}")
        return None
    
    def detect_gpu(self):
        """Detect GPU information at startup"""
        info = {
            'name': 'Unknown GPU',
            'pci_id': '00:00.0',
            'vram_mb': 0,
            'driver': 'nouveau',
            'chip_id': 'Unknown',
            'family': 'Unknown'
        }
        
        try:
            # Find NVIDIA card in lspci
            result = subprocess.run(['lspci', '-nn'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n'):
                if 'NVIDIA' in line and any(x in line for x in ['VGA', '3D', 'Display']):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        info['pci_id'] = parts[0].strip()
                        
                        # Extract GPU name
                        name_match = re.search(r'NVIDIA Corporation (.*?)(?:\[|\(|$)', line)
                        if name_match:
                            info['name'] = name_match.group(1).strip()
                        
                        # Extract device ID [10de:xxxx]
                        id_match = re.search(r'\[10de:([0-9a-f]{4})\]', line)
                        if id_match:
                            info['chip_id'] = id_match.group(1).upper()
                    break
            
            # Check dmesg for chip family
            result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=2)
            dmesg = result.stdout
            
            # Search for nouveau chip detection
            family_match = re.search(r'nouveau.*NVIDIA (NV[0-9A-F]+|G[0-9A-F]+|GT[0-9]+|GF[0-9]+|GK[0-9]+|GM[0-9]+|GP[0-9]+|GV[0-9]+|TU[0-9]+|GA[0-9]+|AD[0-9]+|GB[0-9]+|GH[0-9]+)', dmesg)
            if family_match:
                info['family'] = family_match.group(1)
            
            # Check VRAM from dmesg
            vram_match = re.search(r'nouveau.*VRAM:\s*(\d+)\s*MiB', dmesg)
            if vram_match:
                info['vram_mb'] = int(vram_match.group(1))
            else:
                # Try with glxinfo
                try:
                    result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
                    vram_match = re.search(r'Dedicated video memory:\s*(\d+)\s*MB', result.stdout)
                    if vram_match:
                        info['vram_mb'] = int(vram_match.group(1))
                except:
                    pass
                    
        except Exception as e:
            print(f"GPU detection error: {e}")
        
        return info
    
    def detect_architecture(self):
        """Detect GPU architecture based on chip ID - CORRECTED"""
        chip_id = self.gpu_info['chip_id']
        family = self.gpu_info['family']
        
        # First check in chip database
        if family in CHIP_DATABASE:
            return CHIP_DATABASE[family]['arch']
        
        # Try to match based on prefix
        if family.startswith('NV4') or family.startswith('NV6'):
            return 'NV40'
        elif family.startswith('NV5') or family.startswith('G8') or family.startswith('G9') or family.startswith('GT2'):
            return 'NV50'
        elif family.startswith('NVC') or family.startswith('GF'):
            return 'NVC0'
        elif family.startswith('NVE') or family.startswith('GK'):
            return 'NVE0'
        elif family.startswith('GM'):
            return 'GM100'
        elif family.startswith('GP'):
            return 'GP100'
        elif family.startswith('GV'):
            return 'GV100'
        elif family.startswith('TU'):
            return 'TU100'
        elif family.startswith('GA'):
            return 'GA100'
        elif family.startswith('AD'):
            return 'AD100'
        elif family.startswith('GB'):
            # Check if it's Blackwell or Blackwell 2.0
            if len(family) > 3 and family[3] == '2':
                return 'GB200'
            else:
                return 'GB100'
        elif family.startswith('GH'):
            return 'GH100'
        
        # Fallback based on chip ID
        if chip_id:
            chip_num = int(chip_id, 16) if chip_id != 'Unknown' else 0
            
            # Special cases for specific chips
            if chip_id == '06E0':  # G98
                return 'NV50'
            elif chip_id == '06E1':  # G98
                return 'NV50'
            elif chip_id == '06E2':  # G98
                return 'NV50'
            elif chip_id == '06E3':  # G98
                return 'NV50'
            elif chip_id == '06E4':  # G98
                return 'NV50'
            elif chip_id == '06E5':  # G98
                return 'NV50'
            elif chip_id == '06E6':  # G98
                return 'NV50'
            elif chip_id == '06E7':  # G98
                return 'NV50'
            elif chip_id == '06E8':  # G98
                return 'NV50'
            elif chip_id == '06E9':  # G98
                return 'NV50'
            
            # General ranges
            if 0x0040 <= chip_num < 0x0090:
                return 'NV40'
            elif 0x0090 <= chip_num < 0x0200:
                return 'NV50'
            elif 0x0600 <= chip_num < 0x0E00:
                return 'NVC0'
            elif 0x0E00 <= chip_num < 0x1180:
                return 'NVE0'
            elif 0x1180 <= chip_num < 0x1400:
                return 'GM100'
            elif 0x1400 <= chip_num < 0x1C00:
                return 'GP100'
            elif 0x1C00 <= chip_num < 0x1E00:
                return 'GV100'
            elif 0x1E00 <= chip_num < 0x2200:
                return 'TU100'
            elif 0x2200 <= chip_num < 0x2600:
                return 'GA100'
            elif 0x2600 <= chip_num < 0x2800:
                return 'AD100'
            elif 0x2800 <= chip_num < 0x2A00:
                return 'GB100'
            elif 0x2A00 <= chip_num < 0x2C00:
                return 'GB200'
            elif chip_num >= 0x2C00:
                return 'GH100'
        
        return 'Unknown'
    
    def get_arch_info(self):
        """Get architecture information"""
        if self.gpu_arch in GPU_ARCHITECTURES:
            return GPU_ARCHITECTURES[self.gpu_arch]
        return {
            'name': 'Unknown',
            'series': 'Unknown',
            'opengl': 'Unknown',
            'year': 'Unknown',
            'va_api': 'Unknown'
        }
    
    def get_gpu_temperature(self):
        """Get GPU temperature from sensors"""
        try:
            # Try to get temperature from sensors command
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            
            # Look for nouveau-pci-XXXX temperature
            for line in result.stdout.split('\n'):
                if 'nouveau-pci-' in line and 'temp1' in line:
                    match = re.search(r'temp1:\s*\+([0-9.]+)\s*°C', line)
                    if match:
                        return float(match.group(1))
            
            # Fallback: try with specific nouveau-pci-XXXX if we know the ID
            if self.nouveau_pci_id:
                result = subprocess.run(['sensors', f'nouveau-pci-{self.nouveau_pci_id}'], 
                                      capture_output=True, text=True, timeout=3)
                for line in result.stdout.split('\n'):
                    if 'temp1' in line:
                        match = re.search(r'temp1:\s*\+([0-9.]+)\s*°C', line)
                        if match:
                            return float(match.group(1))
        except Exception as e:
            print(f"Error getting GPU temperature: {e}")
        
        return None
    
    def get_cooling_mode(self):
        """Detect current cooling mode"""
        if self.current_cooling_mode == 'passive':
            return 'passive'
        elif self.current_cooling_mode == 'active':
            return 'active'
        else:  # auto mode
            # Auto-detect based on temperature and fan speed if available
            try:
                # Try to read fan speed from sensors
                result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
                fan_speed = None
                
                for line in result.stdout.split('\n'):
                    if 'fan' in line.lower() and 'nouveau' in line.lower():
                        match = re.search(r'(\d+)\s*RPM', line)
                        if match:
                            fan_speed = int(match.group(1))
                            break
                
                if fan_speed is not None:
                    # If fan is spinning, it's active cooling
                    if fan_speed > 0:
                        return 'active'
                    else:
                        return 'passive'
                
                # Fallback to temperature-based detection
                if len(self.temp_history) > 0:
                    current_temp = self.temp_history[-1]
                    if current_temp > 70:  # Above 70°C likely active cooling
                        return 'active'
                    else:
                        return 'passive'
                        
            except:
                pass
            
            return 'passive'  # Default to passive
    
    def init_ui(self):
        """Initialize enhanced user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Use a lighter dark theme (not pure black)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2B2B2B;
                color: #FFFFFF;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #3C3F41;
            }
            QTabBar::tab {
                background-color: #4C5052;
                color: #FFFFFF;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #365880;
            }
            QTabBar::tab:hover {
                background-color: #4E5254;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #3C3F41;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #BBBBBB;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 3px;
                text-align: center;
                background-color: #4C5052;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                background-color: #365880;
                border-radius: 2px;
            }
            QTableWidget {
                background-color: #3C3F41;
                alternate-background-color: #45494A;
                gridline-color: #555555;
                selection-background-color: #365880;
            }
            QTableWidget::item {
                padding: 5px;
                color: #BBBBBB;
            }
            QHeaderView::section {
                background-color: #4C5052;
                padding: 5px;
                border: 1px solid #555555;
                color: #BBBBBB;
            }
            QPushButton {
                background-color: #365880;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4472A4;
            }
            QPushButton:pressed {
                background-color: #2E4A6C;
            }
            QLabel {
                color: #BBBBBB;
            }
            QTextEdit {
                background-color: #3C3F41;
                color: #BBBBBB;
                border: 1px solid #555555;
            }
            QComboBox {
                background-color: #4C5052;
                color: #BBBBBB;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #BBBBBB;
                margin-right: 5px;
            }
        """)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Top header bar - with gradient background
        header_widget = QWidget()
        header_widget.setFixedHeight(80)
        header_widget.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #365880, stop:0.5 #4A7C59, stop:1 #8B4513);
            border-radius: 5px;
        """)
        header_layout = QVBoxLayout(header_widget)
        
        # GPU information
        arch_info = self.get_arch_info()
        header_text = f"🖥️ {self.gpu_info['name']}"
        if self.gpu_arch != 'Unknown':
            header_text += f"  |  {arch_info['name']} ({arch_info['series']})"
        header_text += f"  |  VRAM: {self.gpu_info['vram_mb']} MB"
        
        header = QLabel(header_text)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("color: white; padding: 5px;")
        header_layout.addWidget(header)
        
        # Subheader
        subheader_text = f"Chip: {self.gpu_info['family']} ({self.gpu_info['chip_id']})  |  "
        subheader_text += f"OpenGL: {arch_info['opengl']}  |  VA-API: {arch_info['va_api']}"
        
        subheader = QLabel(subheader_text)
        subheader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subheader.setStyleSheet("color: rgba(255,255,255,0.9);")
        header_layout.addWidget(subheader)
        
        main_layout.addWidget(header_widget)
        
        # Temperature warning area
        self.arch_warning = QLabel()
        self.arch_warning.setWordWrap(True)
        self.arch_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.arch_warning)
        self.update_arch_warning()
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        daemon_btn = QPushButton("🔧 Daemon Settings")
        daemon_btn.clicked.connect(self.show_daemon_settings)
        toolbar.addWidget(daemon_btn)
        
        # Cooling mode indicator
        self.cooling_mode_label = QLabel()
        self.update_cooling_mode_display()
        toolbar.addWidget(self.cooling_mode_label)
        
        self.daemon_status_label = QLabel("Daemon: Inactive")
        toolbar.addWidget(self.daemon_status_label)
        
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)
        
        # Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Tab 1: Overview
        tabs.addTab(self.create_overview_tab(), "📊 Overview")
        
        # Tab 2: Processes
        tabs.addTab(self.create_processes_tab(), "⚙️ GPU Processes")
        
        # Tab 3: Capabilities
        tabs.addTab(self.create_capabilities_tab(), "🎯 Capabilities")
        
        # Tab 4: Card Info
        tabs.addTab(self.create_card_info_tab(), "ℹ️ Card Info")
        
        # Tab 5: Codecs
        tabs.addTab(self.create_codecs_tab(), "🎬 Codecs")
        
        # Tab 6: Temperature Analysis
        tabs.addTab(self.create_temperature_tab(), "🌡️ Temperature Analysis")
        
        # Tab 7: Resources
        tabs.addTab(self.create_resources_tab(), "📈 Resources")
        
        # Tab 8: Recommendations
        tabs.addTab(self.create_recommendations_tab(), "💡 Recommendations")
        
        # Status bar
        self.last_update_label = QLabel()
        self.statusBar().addPermanentWidget(self.last_update_label)
        self.statusBar().showMessage("Nouveau GPU Monitor Enhanced v3.0")
    
    def update_cooling_mode_display(self):
        """Update cooling mode display"""
        mode = self.get_cooling_mode()
        mode_colors = {
            'passive': '#4CAF50',  # Green
            'active': '#FF9800',   # Orange
            'auto': '#2196F3'      # Blue
        }
        
        mode_icons = {
            'passive': '❄️',
            'active': '🌀',
            'auto': '🔄'
        }
        
        color = mode_colors.get(mode, '#BBBBBB')
        icon = mode_icons.get(mode, '❓')
        
        self.cooling_mode_label.setText(f"{icon} Cooling: {mode.upper()}")
        self.cooling_mode_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px;")
    
    def create_overview_tab(self):
        """Create overview tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Top section - Temperature and VRAM
        top_layout = QHBoxLayout()
        
        # Temperature group
        temp_group = QGroupBox("🌡️ GPU Temperature")
        temp_layout = QVBoxLayout()
        
        self.temp_label = QLabel("--°C")
        self.temp_label.setFont(QFont("Arial", 42, QFont.Weight.Bold))
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.temp_label)
        
        self.temp_bar = QProgressBar()
        self.temp_bar.setMaximum(135)
        self.temp_bar.setFormat("%v°C / 135°C")
        self.temp_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        temp_layout.addWidget(self.temp_bar)
        
        self.temp_status = QLabel("Status: OK")
        self.temp_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_status.setFont(QFont("Arial", 11))
        temp_layout.addWidget(self.temp_status)
        
        # Additional temperature info
        temp_info_layout = QHBoxLayout()
        self.temp_max_label = QLabel("Max: --°C")
        self.temp_crit_label = QLabel("Crit: --°C")
        temp_info_layout.addWidget(self.temp_max_label)
        temp_info_layout.addWidget(self.temp_crit_label)
        temp_layout.addLayout(temp_info_layout)
        
        temp_group.setLayout(temp_layout)
        top_layout.addWidget(temp_group, 2)
        
        # VRAM Info group
        vram_group = QGroupBox("💾 Video Memory (VRAM)")
        vram_layout = QVBoxLayout()
        
        self.vram_total_label = QLabel(f"Total: {self.gpu_info['vram_mb']} MB")
        self.vram_total_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.vram_total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vram_layout.addWidget(self.vram_total_label)
        
        self.vram_used_label = QLabel("Used: -- MB")
        self.vram_used_label.setFont(QFont("Arial", 14))
        self.vram_used_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vram_layout.addWidget(self.vram_used_label)
        
        self.vram_free_label = QLabel("Free: -- MB")
        self.vram_free_label.setFont(QFont("Arial", 14))
        self.vram_free_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vram_layout.addWidget(self.vram_free_label)
        
        vram_note = QLabel("⚠️ Nouveau: Approximate data")
        vram_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vram_note.setStyleSheet("color: #888; font-size: 10px;")
        vram_layout.addWidget(vram_note)
        
        vram_group.setLayout(vram_layout)
        top_layout.addWidget(vram_group, 1)
        
        layout.addLayout(top_layout)
        
        # Clock info (placeholder for newer cards)
        clock_group = QGroupBox("⚡ Clocks")
        clock_layout = QHBoxLayout()
        
        self.gpu_clock_label = QLabel("GPU: N/A")
        self.mem_clock_label = QLabel("VRAM: N/A")
        self.power_label = QLabel("Power: N/A")
        clock_layout.addWidget(self.gpu_clock_label)
        clock_layout.addWidget(self.mem_clock_label)
        clock_layout.addWidget(self.power_label)
        
        clock_note = QLabel("Nouveau doesn't expose clock and power information")
        clock_note.setStyleSheet("color: #888;")
        clock_layout.addWidget(clock_note)
        
        clock_group.setLayout(clock_layout)
        layout.addWidget(clock_group)
        
        # Temperature history chart
        chart_group = QGroupBox("📈 Temperature History (last 2 minutes)")
        chart_layout = QVBoxLayout()
        
        self.temp_series = QLineSeries()
        self.temp_chart = QChart()
        self.temp_chart.addSeries(self.temp_series)
        self.temp_chart.setTitle("")
        self.temp_chart.legend().hide()
        self.temp_chart.setBackgroundBrush(QColor(60, 63, 65))
        
        axis_x = QValueAxis()
        axis_x.setTitleText("Time (s)")
        axis_x.setRange(0, 120)
        axis_x.setLabelFormat("%d")
        axis_x.setGridLineColor(QColor(80, 80, 80))
        
        axis_y = QValueAxis()
        axis_y.setTitleText("Temperature (°C)")
        axis_y.setRange(20, 100)
        axis_y.setLabelFormat("%d")
        axis_y.setGridLineColor(QColor(80, 80, 80))
        
        self.temp_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        self.temp_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        self.temp_series.attachAxis(axis_x)
        self.temp_series.attachAxis(axis_y)
        
        chart_view = QChartView(self.temp_chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_layout.addWidget(chart_view)
        
        chart_group.setLayout(chart_layout)
        layout.addWidget(chart_group, 1)
        
        return widget
    
    def create_processes_tab(self):
        """Create processes tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Processes using GPU through DRM (Direct Rendering Manager)")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_processes)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Process table
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(7)
        self.process_table.setHorizontalHeaderLabels(["PID", "User", "Command", "Device", "CPU %", "RAM (MB)", "Acceleration"])
        
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        self.process_table.setAlternatingRowColors(True)
        self.process_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.process_table)
        
        # Limitation info
        note = QLabel(
            "⚠️ <b>Nouveau Limitations:</b><br>"
            "• No GPU usage information per process (% GPU load)<br>"
            "• No VRAM usage information per process<br>"
            "• For full monitoring consider proper NVIDIA driver"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #FFA500; padding: 10px; background-color: #4A3C28; border-radius: 5px;")
        layout.addWidget(note)
        
        return widget
    
    def create_capabilities_tab(self):
        """Create capabilities tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Supported standards and card capabilities")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_capabilities)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Scroll area for all groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # OpenGL Capabilities
        opengl_group = QGroupBox("🎨 OpenGL")
        opengl_layout = QVBoxLayout()
        self.opengl_caps_text = QTextEdit()
        self.opengl_caps_text.setReadOnly(True)
        self.opengl_caps_text.setMaximumHeight(200)
        self.opengl_caps_text.setFont(QFont("Monospace", 9))
        opengl_layout.addWidget(self.opengl_caps_text)
        opengl_group.setLayout(opengl_layout)
        scroll_layout.addWidget(opengl_group)
        
        # VA-API Capabilities
        vaapi_group = QGroupBox("🎬 VA-API (Video Acceleration)")
        vaapi_layout = QVBoxLayout()
        self.vaapi_caps_table = QTableWidget()
        self.vaapi_caps_table.setColumnCount(2)
        self.vaapi_caps_table.setHorizontalHeaderLabels(["Profile", "Entrypoints"])
        self.vaapi_caps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.vaapi_caps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.vaapi_caps_table.setMaximumHeight(250)
        vaapi_layout.addWidget(self.vaapi_caps_table)
        vaapi_group.setLayout(vaapi_layout)
        scroll_layout.addWidget(vaapi_group)
        
        # VDPAU Info
        vdpau_group = QGroupBox("📺 VDPAU")
        vdpau_layout = QVBoxLayout()
        self.vdpau_info = QLabel("VDPAU: checking...")
        self.vdpau_info.setWordWrap(True)
        vdpau_layout.addWidget(self.vdpau_info)
        vdpau_group.setLayout(vdpau_layout)
        scroll_layout.addWidget(vdpau_group)
        
        # OpenGL Extensions
        ext_group = QGroupBox("🔧 OpenGL Extensions (selected)")
        ext_layout = QVBoxLayout()
        self.extensions_text = QTextEdit()
        self.extensions_text.setReadOnly(True)
        self.extensions_text.setMaximumHeight(150)
        self.extensions_text.setFont(QFont("Monospace", 8))
        ext_layout.addWidget(self.extensions_text)
        ext_group.setLayout(ext_layout)
        scroll_layout.addWidget(ext_group)
        
        # GPU Limits
        limits_group = QGroupBox("📊 GPU Limits")
        limits_layout = QVBoxLayout()
        self.limits_text = QTextEdit()
        self.limits_text.setReadOnly(True)
        self.limits_text.setMaximumHeight(200)
        self.limits_text.setFont(QFont("Monospace", 9))
        limits_layout.addWidget(self.limits_text)
        limits_group.setLayout(limits_layout)
        scroll_layout.addWidget(limits_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def create_card_info_tab(self):
        """Create card info tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_card_info)
        toolbar.addWidget(refresh_btn)
        
        copy_btn = QPushButton("📋 Copy")
        copy_btn.clicked.connect(self.copy_card_info)
        toolbar.addWidget(copy_btn)
        
        layout.addLayout(toolbar)
        
        self.card_info_text = QTextEdit()
        self.card_info_text.setReadOnly(True)
        self.card_info_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.card_info_text)
        
        return widget
    
    def create_codecs_tab(self):
        """Create codecs tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Video encoding/decoding support")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Check again")
        refresh_btn.clicked.connect(self.update_codecs)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        self.codecs_text = QTextEdit()
        self.codecs_text.setReadOnly(True)
        self.codecs_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.codecs_text)
        
        # Installation info
        install_info = QLabel(
            "<b>How to install VA-API support:</b><br>"
            "• Arch/CachyOS: <code>sudo pacman -S libva-utils</code><br>"
            "• Debian/Ubuntu: <code>sudo apt install vainfo</code><br>"
            "• Fedora: <code>sudo dnf install libva-utils</code>"
        )
        install_info.setWordWrap(True)
        install_info.setStyleSheet("padding: 10px; background-color: #3C3F41; border-radius: 5px;")
        layout.addWidget(install_info)
        
        return widget
    
    def create_temperature_tab(self):
        """Create temperature analysis tab with enhanced correlation chart"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Temperature anomaly analysis and cooling detection")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_temperature_analysis_display)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Temperature anomaly events table
        anomaly_group = QGroupBox("🌡️ Temperature Anomaly Events")
        anomaly_layout = QVBoxLayout()
        
        self.anomaly_table = QTableWidget()
        self.anomaly_table.setColumnCount(4)
        self.anomaly_table.setHorizontalHeaderLabels(["Time", "Temp Change Rate (°C/s)", "Related Processes", "Possible Cause"])
        
        header = self.anomaly_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.anomaly_table.setAlternatingRowColors(True)
        self.anomaly_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        anomaly_layout.addWidget(self.anomaly_table)
        
        anomaly_group.setLayout(anomaly_layout)
        layout.addWidget(anomaly_group)
        
        # Cooling analysis
        cooling_group = QGroupBox("❄️ Cooling Analysis")
        cooling_layout = QVBoxLayout()
        
        self.cooling_text = QTextEdit()
        self.cooling_text.setReadOnly(True)
        self.cooling_text.setMaximumHeight(150)
        cooling_layout.addWidget(self.cooling_text)
        
        cooling_group.setLayout(cooling_layout)
        layout.addWidget(cooling_group)
        
        # Enhanced Temperature and process correlation chart
        process_temp_group = QGroupBox("📊 Temperature-Process Correlation Analysis")
        process_temp_layout = QVBoxLayout()
        
        # Create chart view
        self.process_temp_chart_view = QChartView()
        self.process_temp_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.process_temp_chart_view.setMinimumHeight(400)
        process_temp_layout.addWidget(self.process_temp_chart_view)
        
        # Legend for the chart
        legend_layout = QHBoxLayout()
        legend_label = QLabel("Legend: ")
        legend_layout.addWidget(legend_label)
        
        # Temperature line legend
        temp_legend = QLabel("━ Temperature")
        temp_legend.setStyleSheet("color: #F44336; font-weight: bold;")
        legend_layout.addWidget(temp_legend)
        
        # Process legends will be added dynamically
        self.process_legend_layout = legend_layout
        process_temp_layout.addLayout(legend_layout)
        
        process_temp_group.setLayout(process_temp_layout)
        layout.addWidget(process_temp_group)
        
        return widget
    
    def create_resources_tab(self):
        """Create resources monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("System resources and GPU usage")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_resources_display)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Top section - CPU and Memory charts
        top_layout = QHBoxLayout()
        
        # CPU Usage Chart
        cpu_group = QGroupBox("💻 CPU Usage")
        cpu_layout = QVBoxLayout()
        
        self.cpu_chart_view = QChartView()
        self.cpu_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.cpu_chart_view.setMinimumHeight(200)
        cpu_layout.addWidget(self.cpu_chart_view)
        
        cpu_group.setLayout(cpu_layout)
        top_layout.addWidget(cpu_group)
        
        # Memory Usage Chart
        mem_group = QGroupBox("🧠 Memory Usage")
        mem_layout = QVBoxLayout()
        
        self.mem_chart_view = QChartView()
        self.mem_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.mem_chart_view.setMinimumHeight(200)
        mem_layout.addWidget(self.mem_chart_view)
        
        mem_group.setLayout(mem_layout)
        top_layout.addWidget(mem_group)
        
        layout.addLayout(top_layout)
        
        # VRAM Usage Chart
        vram_group = QGroupBox("🎮 VRAM Usage")
        vram_layout = QVBoxLayout()
        
        self.vram_chart_view = QChartView()
        self.vram_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vram_chart_view.setMinimumHeight(200)
        vram_layout.addWidget(self.vram_chart_view)
        
        vram_group.setLayout(vram_layout)
        layout.addWidget(vram_group)
        
        # Top Processes Table
        processes_group = QGroupBox("🔥 Top Processes by CPU Usage")
        processes_layout = QVBoxLayout()
        
        self.top_processes_table = QTableWidget()
        self.top_processes_table.setColumnCount(5)
        self.top_processes_table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Memory %", "VRAM (MB)"])
        
        header = self.top_processes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.top_processes_table.setAlternatingRowColors(True)
        self.top_processes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.top_processes_table.setMaximumHeight(300)
        
        processes_layout.addWidget(self.top_processes_table)
        processes_group.setLayout(processes_layout)
        layout.addWidget(processes_group)
        
        return widget
    
    def create_recommendations_tab(self):
        """Create recommendations tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Header
        header = QLabel(f"💡 Recommendations for {self.gpu_info['name']}")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(header)
        
        # Architecture info
        arch_info = self.get_arch_info()
        arch_group = QGroupBox("📋 Your Card")
        arch_layout = QVBoxLayout()
        
        arch_text = f"""
<b>Architecture:</b> {arch_info['name']}<br>
<b>Series:</b> {arch_info['series']}<br>
<b>Release Year:</b> {arch_info['year']}<br>
<b>OpenGL:</b> {arch_info['opengl']}<br>
<b>VA-API:</b> {arch_info['va_api']}<br>
<b>Chip:</b> {self.gpu_info['family']} ({self.gpu_info['chip_id']})<br>
<b>VRAM:</b> {self.gpu_info['vram_mb']} MB
        """
        arch_label = QLabel(arch_text)
        arch_label.setWordWrap(True)
        arch_layout.addWidget(arch_label)
        arch_group.setLayout(arch_layout)
        scroll_layout.addWidget(arch_group)
        
        # Recommendations
        rec_group = QGroupBox("✨ Recommendations")
        rec_layout = QVBoxLayout()
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMinimumHeight(300)
        rec_layout.addWidget(self.recommendations_text)
        rec_group.setLayout(rec_layout)
        scroll_layout.addWidget(rec_group)
        
        # Links
        links_group = QGroupBox("🔗 Useful Links")
        links_layout = QVBoxLayout()
        links_text = QLabel("""
<b>Nouveau Documentation:</b><br>
• <a href="https://nouveau.freedesktop.org/">nouveau.freedesktop.org</a><br>
• <a href="https://wiki.archlinux.org/title/Nouveau">ArchWiki - Nouveau</a><br>
<br>
<b>NVIDIA Drivers:</b><br>
• <a href="https://www.nvidia.com/Download/index.aspx">NVIDIA Driver Downloads</a><br>
• <a href="https://github.com/NVIDIA/open-gpu-kernel-modules">NVIDIA Open Kernel Modules</a><br>
<br>
<b>Tools:</b><br>
• <a href="https://github.com/Syllo/nvtop">nvtop - GPU Monitor</a><br>
• <a href="https://github.com/wookayin/gpustat">gpustat - GPU Stats</a>
        """)
        links_text.setWordWrap(True)
        links_text.setOpenExternalLinks(True)
        links_layout.addWidget(links_text)
        links_group.setLayout(links_layout)
        scroll_layout.addWidget(links_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Generate recommendations
        self.generate_recommendations()
        
        return widget
    
    def generate_recommendations(self):
        """Generate recommendations for specific architecture"""
        rec_text = ""
        
        if self.gpu_arch == 'NV40':
            rec_text = """
<h3>🔴 GeForce 6/7 (Curie) - Very Old Card</h3>

<b>Nouveau Status:</b><br>
• Minimal support, no reclocking<br>
• OpenGL 2.1 maximum<br>
• No VA-API<br>
<br>
<b>Recommendations:</b><br>
1. <b>Consider nvidia-173xx (legacy)</b> for better performance<br>
2. Use lightweight desktop environments (XFCE, LXDE)<br>
3. Disable window compositor<br>
4. For videos: use mpv with vdpau (may not work)<br>
5. For games: only very old titles (before 2010)<br>
<br>
<b>Limitations:</b><br>
• No Vulkan<br>
• No modern video acceleration<br>
• May lack support in newer kernels
            """
        elif self.gpu_arch == 'NV50':
            rec_text = """
<h3>🟠 GeForce 8/9/GT 2xx (Tesla) - Older Card</h3>

<b>Nouveau Status:</b><br>
• Good basic support<br>
• OpenGL 3.3<br>
• Very limited VA-API<br>
<br>
<b>Recommendations:</b><br>
1. <b>For performance: nvidia-340xx or nvidia-390xx</b><br>
2. VDPAU works better than VA-API for video<br>
3. Enable DRM KMS: add <code>nouveau.modeset=1</code> to kernel params<br>
4. For 1080p videos: mpv with vdpau<br>
5. Light games (before 2015) should work<br>
<br>
<b>Optimizations:</b><br>
• Disable compositing in browser: <code>--disable-gpu-compositing</code><br>
• Use mesa-amber for better OpenGL compatibility<br>
• Reclocking doesn't work - card stuck at boot clocks<br>
<br>
<b>Known Issues:</b><br>
• No reclocking (stuck at boot clocks)<br>
• Random crashes under heavy 3D load
            """
        elif self.gpu_arch == 'NVC0':
            rec_text = """
<h3>🟡 GeForce 4xx/5xx (Fermi) - Mid Generation</h3>

<b>Nouveau Status:</b><br>
• Good support<br>
• OpenGL 4.3<br>
• Partial VA-API (MPEG2, VC1, some H.264)<br>
<br>
<b>Recommendations:</b><br>
1. <b>Nouveau works decently</b> for desktop and multimedia<br>
2. <b>For games: nvidia-470xx</b> (last supporting Fermi)<br>
3. VA-API: install <code>libva-mesa-driver</code><br>
4. VDPAU works great for 1080p video<br>
5. Reclocking: experimental, use with caution<br>
<br>
<b>Optimizations:</b><br>
• Experimental reclocking: <code>nouveau.pstate=1</code> (risky!)<br>
• For Chrome/Firefox: enable hardware acceleration<br>
• OpenCL: possible through Mesa Clover (limited)<br>
<br>
<b>For Gaming:</b><br>
• Older games (2010-2016): should work on low/medium<br>
• Wine/Proton: works, but slower than nvidia<br>
• Vulkan: not supported by Nouveau for Fermi
            """
        elif self.gpu_arch == 'NVE0':
            rec_text = """
<h3>🟢 GeForce 6xx/7xx (Kepler) - Good Card</h3>

<b>Nouveau Status:</b><br>
• Very good support<br>
• OpenGL 4.5<br>
• Good VA-API (most codecs)<br>
<br>
<b>Recommendations:</b><br>
1. <b>Nouveau is a good choice</b> for daily use<br>
2. <b>For AAA games: nvidia-470xx or newer</b><br>
3. VA-API supports: MPEG2, VC1, H.264, H.265 (partially)<br>
4. Reclocking works - you can switch power profiles<br>
5. Firefox/Chrome: hardware acceleration works well<br>
<br>
<b>Optimizations:</b><br>
• Enable reclocking: <code>nouveau.pstate=1</code> (stable)<br>
• Power management: <code>echo auto > /sys/class/drm/card0/device/power_profile</code><br>
• Video acceleration: use VA-API for H.264/H.265<br>
<br>
<b>Gaming:</b><br>
• Indie and older AAA: will work<br>
• Vulkan: NVK (experimental) or nvidia driver<br>
• Emulators: good performance
            """
        elif self.gpu_arch in ['GM100', 'GP100']:
            rec_text = """
<h3>🟢 GeForce 9xx/10xx (Maxwell/Pascal) - Great Card</h3>

<b>Nouveau Status:</b><br>
• Very good support<br>
• OpenGL 4.6<br>
• Very good VA-API<br>
• NVK (Vulkan) - experimental<br>
<br>
<b>Recommendations:</b><br>
1. <b>Nouveau works great</b> for desktop/multimedia<br>
2. <b>For games: nvidia-530xx+</b> or experimental NVK<br>
3. VA-API supports all popular codecs<br>
4. Reclocking works stable<br>
5. Try Mesa NVK for Vulkan (requires Mesa 23.1+)<br>
<br>
<b>Optimizations:</b><br>
• NVK Vulkan: <code>export MESA_VK_VERSION_OVERRIDE=1.3</code><br>
• Reclocking: automatic in newer kernels<br>
• Video acceleration: works out-of-the-box<br>
• Power management: excellent<br>
<br>
<b>Gaming:</b><br>
• NVK: many Vulkan games work (experimental)<br>
• OpenGL: great performance<br>
• DXVK/VKD3D: works through NVK<br>
• For competitive gaming: use nvidia
            """
        elif self.gpu_arch == 'GV100':
            rec_text = """
<h3>🟢 Volta (Titan V) - Very Powerful</h3>

<b>Nouveau Status:</b><br>
• Good basic support<br>
• OpenGL 4.6<br>
• Very good VA-API<br>
• NVK - experimental but promising<br>
<br>
<b>Recommendations:</b><br>
1. <b>Nouveau:</b> desktop and multimedia - excellent<br>
2. <b>For compute/AI: nvidia-535xx+</b> (CUDA, Tensor Cores)<br>
3. NVK Vulkan already quite usable<br>
4. Reclocking automatic<br>
<br>
<b>Optimizations:</b><br>
• Check latest Mesa for NVK<br>
• CUDA: only with proper driver<br>
• Tensor Cores: nvidia driver required
            """
        elif self.gpu_arch in ['TU100', 'GA100', 'AD100']:
            rec_text = """
<h3>🟠 Turing/Ampere/Ada (RTX) - New Card</h3>

<b>Nouveau Status:</b><br>
• Basic support<br>
• OpenGL 4.6<br>
• Excellent VA-API (AV1 supported!)<br>
• NVK Vulkan - actively developed<br>
• <b>Requires signed firmware!</b><br>
<br>
<b>⚠️ Important - Signed Firmware:</b><br>
1. Install: <code>sudo pacman -S linux-firmware</code><br>
2. May require: <code>nouveau.config=NvGspRm=1</code><br>
3. Older kernels may not fully support<br>
<br>
<b>Recommendations:</b><br>
1. <b>Nouveau:</b> OK for desktop, but limited<br>
2. <b>For RTX/DLSS/Ray-tracing: nvidia-550xx+</b> (mandatory)<br>
3. NVK Vulkan getting better - test Mesa 24.0+<br>
4. AV1 decode - works through VA-API!<br>
<br>
<b>Optimizations:</b><br>
• GSP firmware: <code>nouveau.config=NvGspRm=1</code><br>
• NVK updates: use latest Mesa<br>
• Wayland: works better than X11<br>
<br>
<b>Gaming:</b><br>
• OpenGL: good performance<br>
• Vulkan through NVK: many games already work!<br>
• Ray-tracing: only nvidia driver<br>
• DLSS: only nvidia driver<br>
<br>
<b>If using for gaming:</b><br>
Unfortunately RTX features (RT cores, Tensor cores, DLSS) work<br>
only with proper NVIDIA driver. Nouveau gives ~50-70%<br>
performance of proper driver.
            """
        elif self.gpu_arch in ['GB100', 'GB200', 'GH100']:
            rec_text = """
<h3>🔮 Blackwell/Hopper - Latest Card</h3>

<b>Nouveau Status:</b><br>
• Very limited support (not yet released)<br>
• Basic OpenGL may work<br>
• Vulkan: NVK in development<br>
• <b> bleeding edge - expect issues</b><br>
<br>
<b>Recommendations:</b><br>
1. <b>Use nvidia driver</b> - mandatory for these cards<br>
2. Nouveau: for basic display only<br>
3. Check back in 6-12 months for better support<br>
<br>
<b>Current Limitations:</b><br>
• No reclocking support yet<br>
• Limited power management<br>
• May require very new kernel (6.6+)<br>
• Experimental firmware support
            """
        else:
            rec_text = """
<h3>❓ Unknown Architecture</h3>

<b>Status:</b><br>
• Could not detect GPU architecture<br>
• May be very new or very old card<br>
<br>
<b>Recommendations:</b><br>
1. Check if nvidia driver is available<br>
2. Report GPU info to nouveau developers<br>
3. Use lspci and dmesg to identify card<br>
<br>
<b>Debug Info:</b><br>
• Chip ID: {self.gpu_info['chip_id']}<br>
• Family: {self.gpu_info['family']}<br>
• Name: {self.gpu_info['name']}
            """
        
        self.recommendations_text.setHtml(rec_text)
    
    def update_arch_warning(self):
        """Update architecture warning"""
        arch_info = self.get_arch_info()
        warning_text = ""
        style = ""
        
        if self.gpu_arch == 'NV40':
            warning_text = "⚠️ Very old card (2004-2006). Nouveau has minimal support. Consider proper nvidia-173xx (legacy) driver."
            style = "background-color: #8B0000; color: white; padding: 8px; border-radius: 5px; font-weight: bold;"
        elif self.gpu_arch == 'NV50':
            warning_text = "⚠️ Older card (2006-2010). Limited VA-API support. For full features: nvidia-340xx or nvidia-390xx."
            style = "background-color: #FF6600; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['NVC0', 'NVE0']:
            warning_text = "ℹ️ Mid-generation card. Nouveau works well, but for full performance consider nvidia-470xx."
            style = "background-color: #4A90E2; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['GM100', 'GP100', 'GV100']:
            warning_text = "✅ Good compatibility with Nouveau! For ray-tracing and full performance consider nvidia-530xx+"
            style = "background-color: #2E7D32; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['TU100', 'GA100', 'AD100']:
            warning_text = "⚠️ New card - Nouveau may require signed firmware. For RTX/DLSS need proper nvidia-550xx+ driver"
            style = "background-color: #FF9800; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['GB100', 'GB200', 'GH100']:
            warning_text = "🔮 Latest card - Nouveau may have limited support. For full performance need latest NVIDIA driver."
            style = "background-color: #9C27B0; color: white; padding: 8px; border-radius: 5px;"
        
        self.arch_warning.setText(warning_text)
        self.arch_warning.setStyleSheet(style)
        self.arch_warning.setVisible(bool(warning_text))
    
    def show_daemon_settings(self):
        """Show daemon settings dialog"""
        dialog = DaemonSettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            DAEMON_CONFIG.update(settings)
            self.save_daemon_config()
            self.show_notification("Settings Saved", "Daemon configuration has been updated")
    
    def save_daemon_config(self):
        """Save daemon configuration"""
        try:
            with open(DAEMON_CONFIG['config_file'], 'w') as f:
                json.dump(DAEMON_CONFIG, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_daemon_config(self):
        """Load daemon configuration"""
        try:
            if os.path.exists(DAEMON_CONFIG['config_file']):
                with open(DAEMON_CONFIG['config_file'], 'r') as f:
                    DAEMON_CONFIG.update(json.load(f))
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def show_notification(self, title, message, urgency="low"):
        """Show system notification"""
        if NOTIFY_AVAILABLE:
            try:
                notification = notify2.Notification(title, message)
                if urgency == "critical":
                    notification.set_urgency(notify2.URGENCY_CRITICAL)
                elif urgency == "normal":
                    notification.set_urgency(notify2.URGENCY_NORMAL)
                else:
                    notification.set_urgency(notify2.URGENCY_LOW)
                notification.show()
            except Exception as e:
                print(f"Notification error: {e}")
    
    def update_data(self):
        """Update all data"""
        try:
            # Update temperature
            temp = self.get_gpu_temperature()
            if temp is not None:
                self.temp_history.append(temp)
                self.temp_label.setText(f"{temp:.1f}°C")
                self.temp_bar.setValue(int(temp))
                
                # Update temperature status
                if temp >= DAEMON_CONFIG['critical_threshold']:
                    self.temp_status.setText("Status: CRITICAL")
                    self.temp_status.setStyleSheet("color: #F44336; font-weight: bold;")
                    self.temp_bar.setStyleSheet("""
                        QProgressBar::chunk {
                            background-color: #F44336;
                        }
                    """)
                elif temp >= DAEMON_CONFIG['temp_threshold']:
                    self.temp_status.setText("Status: WARNING")
                    self.temp_status.setStyleSheet("color: #FF9800; font-weight: bold;")
                    self.temp_bar.setStyleSheet("""
                        QProgressBar::chunk {
                            background-color: #FF9800;
                        }
                    """)
                else:
                    self.temp_status.setText("Status: OK")
                    self.temp_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    self.temp_bar.setStyleSheet("""
                        QProgressBar::chunk {
                            background-color: #4CAF50;
                        }
                    """)
                
                # Update temperature chart
                self.temp_series.clear()
                for i, t in enumerate(self.temp_history):
                    self.temp_series.append(i, t)
            
            # Update VRAM info
            try:
                mem = psutil.virtual_memory()
                total_vram = self.gpu_info['vram_mb']
                # Nouveau doesn't provide VRAM usage, estimate based on system memory
                used_vram = int(mem.used * 0.1 / (1024 * 1024))  # Rough estimate
                free_vram = total_vram - used_vram
                
                self.vram_used_label.setText(f"Used: {used_vram} MB")
                self.vram_free_label.setText(f"Free: {free_vram} MB")
                self.vram_history.append(used_vram)
            except Exception as e:
                print(f"Error updating VRAM: {e}")
            
            # Update CPU and memory history
            try:
                cpu_percent = psutil.cpu_percent()
                mem_percent = psutil.virtual_memory().percent
                self.cpu_history.append(cpu_percent)
                self.mem_history.append(mem_percent)
            except Exception as e:
                print(f"Error updating CPU/memory: {e}")
            
            # Update process history
            self.update_process_history()
            
            # Update cooling mode display
            self.update_cooling_mode_display()
            
            # Update last update time
            self.last_update_label.setText(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            print(f"Error in update_data: {e}")
            import traceback
            traceback.print_exc()

    def initial_update(self):
        """Initial update with safe loading"""
        try:
            # Update only basic info first
            temp = self.get_gpu_temperature()
            if temp is not None:
                self.temp_history.append(temp)
                self.temp_label.setText(f"{temp:.1f}°C")
                self.temp_bar.setValue(int(temp))
            
            # Update cooling mode display
            self.update_cooling_mode_display()
            
            print("Initial update completed successfully")
        except Exception as e:
            print(f"Error in initial update: {e}")
            import traceback
            traceback.print_exc()
    
    def update_process_history(self):
        """Update process CPU and memory history"""
        try:
            for proc in psutil.process_iter(['pid', 'cpu_percent', 'memory_info']):
                try:
                    proc_info = proc.info
                    pid = proc_info['pid']
                    
                    # Initialize history if needed
                    if pid not in self.process_cpu_history:
                        self.process_cpu_history[pid] = deque(maxlen=60)
                    if pid not in self.process_mem_history:
                        self.process_mem_history[pid] = deque(maxlen=60)
                    
                    # Add current values
                    self.process_cpu_history[pid].append(proc_info['cpu_percent'])
                    
                    # Calculate VRAM usage in MB
                    vram_mb = 0
                    if proc_info['memory_info']:
                        vram_mb = proc_info['memory_info'].rss / (1024 * 1024)
                    
                    self.process_mem_history[pid].append(vram_mb)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error updating process history: {e}")
    
    def update_processes(self):
        """Update process table"""
        self.process_table.setRowCount(0)
        
        # Get processes using DRM
        drm_processes = []
        try:
            # Check /dev/dri/card0 users
            result = subprocess.run(['lsof', '/dev/dri/card0'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n'):
                if line and not line.startswith('COMMAND'):
                    parts = line.split()
                    if len(parts) >= 2:
                        pid = int(parts[1])
                        cmd = parts[0]
                        try:
                            proc = psutil.Process(pid)
                            user = proc.username()
                            cpu = proc.cpu_percent()
                            mem = proc.memory_info().rss / (1024 * 1024)
                            
                            # Check if using video acceleration
                            accel = "No"
                            if pid in self.video_accel_processes:
                                accel = "Yes"
                            
                            drm_processes.append({
                                'pid': pid,
                                'user': user,
                                'cmd': cmd,
                                'device': '/dev/dri/card0',
                                'cpu': cpu,
                                'mem': mem,
                                'accel': accel
                            })
                        except:
                            continue
        except:
            pass
        
        # Add to table
        for proc in drm_processes:
            row = self.process_table.rowCount()
            self.process_table.insertRow(row)
            
            self.process_table.setItem(row, 0, QTableWidgetItem(str(proc['pid'])))
            self.process_table.setItem(row, 1, QTableWidgetItem(proc['user']))
            self.process_table.setItem(row, 2, QTableWidgetItem(proc['cmd']))
            self.process_table.setItem(row, 3, QTableWidgetItem(proc['device']))
            self.process_table.setItem(row, 4, QTableWidgetItem(f"{proc['cpu']:.1f}%"))
            self.process_table.setItem(row, 5, QTableWidgetItem(f"{proc['mem']:.1f}"))
            self.process_table.setItem(row, 6, QTableWidgetItem(proc['accel']))
    
    def update_capabilities(self):
        """Update capabilities display"""
        # OpenGL info
        try:
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            glxinfo = result.stdout
            
            # Extract OpenGL version
            version_match = re.search(r'OpenGL version string: (.+)', glxinfo)
            if version_match:
                gl_version = version_match.group(1).strip()
            else:
                gl_version = "Unknown"
            
            # Extract renderer
            renderer_match = re.search(r'OpenGL renderer string: (.+)', glxinfo)
            if renderer_match:
                renderer = renderer_match.group(1).strip()
            else:
                renderer = "Unknown"
            
            # Extract some extensions
            extensions = []
            for ext in ['GL_ARB_vertex_shader', 'GL_ARB_fragment_shader', 'GL_ARB_geometry_shader', 
                       'GL_ARB_compute_shader', 'GL_ARB_tessellation_shader', 'GL_ARB_shader_image_load_store']:
                if ext in glxinfo:
                    extensions.append(ext)
            
            caps_text = f"OpenGL Version: {gl_version}\n"
            caps_text += f"Renderer: {renderer}\n\n"
            caps_text += "Key Extensions:\n"
            for ext in extensions[:10]:  # Show first 10
                caps_text += f"  ✓ {ext}\n"
            
            self.opengl_caps_text.setText(caps_text)
        except:
            self.opengl_caps_text.setText("Error getting OpenGL info")
        
        # VA-API info
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=3)
            vainfo = result.stdout
            
            # Parse VA-API profiles
            profiles = []
            entrypoints = []
            
            for line in vainfo.split('\n'):
                if 'VAProfile' in line and ':' in line:
                    profile = line.split(':')[1].strip()
                    profiles.append(profile)
                elif 'VAEntrypoint' in line and ':' in line:
                    entrypoint = line.split(':')[1].strip()
                    entrypoints.append(entrypoint)
            
            # Fill table
            self.vaapi_caps_table.setRowCount(len(profiles))
            for i, profile in enumerate(profiles):
                self.vaapi_caps_table.setItem(i, 0, QTableWidgetItem(profile))
                self.vaapi_caps_table.setItem(i, 1, QTableWidgetItem(" ".join(entrypoints)))
        except:
            self.vaapi_caps_table.setRowCount(1)
            self.vaapi_caps_table.setItem(0, 0, QTableWidgetItem("VA-API not available"))
            self.vaapi_caps_table.setItem(0, 1, QTableWidgetItem("Install libva-utils"))
        
        # VDPAU info
        try:
            result = subprocess.run(['vdpauinfo'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                self.vdpau_info.setText("✅ VDPAU Available\n" + result.stdout[:200] + "...")
            else:
                self.vdpau_info.setText("❌ VDPAU not available")
        except:
            self.vdpau_info.setText("❌ VDPAU not available (install vdpauinfo)")
        
        # Extensions
        try:
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            extensions = re.findall(r'GL_\w+', result.stdout)
            extensions_text = "\n".join(extensions[:50])  # Show first 50
            self.extensions_text.setText(extensions_text)
        except:
            self.extensions_text.setText("Error getting extensions")
        
        # GPU limits
        try:
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            limits_text = ""
            
            # Extract common limits
            limits = [
                ('Max texture size', r'Max texture size: (\d+)'),
                ('Max 3D texture size', r'Max 3D texture size: (\d+)'),
                ('Max cube map size', r'Max cube map texture size: (\d+)'),
                ('Max renderbuffer size', r'Max renderbuffer size: (\d+)'),
                ('Max viewport dims', r'Max viewport dims: (\d+)x(\d+)'),
                ('Max samples', r'Max samples: (\d+)'),
            ]
            
            for name, pattern in limits:
                match = re.search(pattern, result.stdout)
                if match:
                    if len(match.groups()) == 2:
                        limits_text += f"{name}: {match.group(1)}x{match.group(2)}\n"
                    else:
                        limits_text += f"{name}: {match.group(1)}\n"
            
            self.limits_text.setText(limits_text)
        except:
            self.limits_text.setText("Error getting limits")
    
    def update_card_info(self):
        """Update card information"""
        info_text = f"""
GPU Information:
================
Name: {self.gpu_info['name']}
PCI ID: {self.gpu_info['pci_id']}
Driver: {self.gpu_info['driver']}
Chip ID: {self.gpu_info['chip_id']}
Family: {self.gpu_info['family']}
Architecture: {self.gpu_arch}
VRAM: {self.gpu_info['vram_mb']} MB

Architecture Details:
====================
"""
        
        arch_info = self.get_arch_info()
        for key, value in arch_info.items():
            info_text += f"{key.title()}: {value}\n"
        
        # Add sensor info
        info_text += "\n\nSensor Information:\n====================\n"
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            for line in result.stdout.split('\n'):
                if 'nouveau' in line.lower():
                    info_text += line + "\n"
        except:
            info_text += "Error getting sensor info\n"
        
        # Add module info
        info_text += "\n\nModule Information:\n====================\n"
        try:
            result = subprocess.run(['modinfo', 'nouveau'], capture_output=True, text=True, timeout=3)
            for line in result.stdout.split('\n'):
                if line.startswith('version:') or line.startswith('firmware:'):
                    info_text += line + "\n"
        except:
            info_text += "Error getting module info\n"
        
        self.card_info_text.setText(info_text)
    
    def copy_card_info(self):
        """Copy card info to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.card_info_text.toPlainText())
        self.show_notification("Copied", "Card information copied to clipboard")
    
    def update_codecs(self):
        """Update codec information"""
        codec_text = "Video Codec Support:\n====================\n\n"
        
        # Check VA-API codecs
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                codec_text += "VA-API Codecs:\n"
                codec_text += "---------------\n"
                
                # Parse supported profiles
                profiles = re.findall(r'VAProfile(\w+)', result.stdout)
                for profile in profiles:
                    codec_text += f"✓ {profile}\n"
            else:
                codec_text += "VA-API: Not available\n"
        except:
            codec_text += "VA-API: Error checking\n"
        
        codec_text += "\n"
        
        # Check VDPAU codecs
        try:
            result = subprocess.run(['vdpauinfo'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                codec_text += "VDPAU Codecs:\n"
                codec_text += "---------------\n"
                
                # Parse supported features
                if 'MPEG1' in result.stdout:
                    codec_text += "✓ MPEG1\n"
                if 'MPEG2' in result.stdout:
                    codec_text += "✓ MPEG2\n"
                if 'H264' in result.stdout:
                    codec_text += "✓ H.264\n"
                if 'VC1' in result.stdout:
                    codec_text += "✓ VC-1\n"
                if 'HEVC' in result.stdout:
                    codec_text += "✓ H.265/HEVC\n"
                if 'VP9' in result.stdout:
                    codec_text += "✓ VP9\n"
                if 'AV1' in result.stdout:
                    codec_text += "✓ AV1\n"
            else:
                codec_text += "VDPAU: Not available\n"
        except:
            codec_text += "VDPAU: Error checking\n"
        
        # Add architecture-specific notes
        codec_text += "\n\nArchitecture Notes:\n"
        codec_text += "-------------------\n"
        
        if self.gpu_arch == 'NV40':
            codec_text += "• No hardware video acceleration\n"
            codec_text += "• All decoding done in software\n"
        elif self.gpu_arch == 'NV50':
            codec_text += "• Very limited hardware acceleration\n"
            codec_text += "• VDPAU may work for MPEG2\n"
        elif self.gpu_arch == 'NVC0':
            codec_text += "• Partial H.264 acceleration\n"
            codec_text += "• MPEG2 and VC1 supported\n"
        elif self.gpu_arch == 'NVE0':
            codec_text += "• Good H.264 support\n"
            codec_text += "• Partial H.265 support\n"
        elif self.gpu_arch in ['GM100', 'GP100']:
            codec_text += "• Excellent codec support\n"
            codec_text += "• Full H.264/H.265 decoding\n"
        elif self.gpu_arch in ['TU100', 'GA100', 'AD100']:
            codec_text += "• Full codec support including AV1\n"
            codec_text += "• Hardware encoding may work\n"
        
        self.codecs_text.setText(codec_text)
    
    def update_temperature_analysis_display(self):
        """Update temperature analysis display"""
        try:
            # Update anomaly table
            self.anomaly_table.setRowCount(0)
            
            for event in self.logger.anomaly_events[-10:]:  # Show last 10 events
                row = self.anomaly_table.rowCount()
                self.anomaly_table.insertRow(row)
                
                self.anomaly_table.setItem(row, 0, QTableWidgetItem(
                    event['timestamp'].strftime('%H:%M:%S')))
                self.anomaly_table.setItem(row, 1, QTableWidgetItem(
                    f"{event['rate']:.2f}"))
                
                processes = ", ".join(list(event['processes'].values())[:3])
                self.anomaly_table.setItem(row, 2, QTableWidgetItem(processes))
                
                # Determine possible cause
                if event['rate'] > 10:
                    cause = "Heavy load / Thermal throttling"
                elif event['rate'] > 5:
                    cause = "Process start / High activity"
                else:
                    cause = "Normal fluctuation"
                
                self.anomaly_table.setItem(row, 3, QTableWidgetItem(cause))
            
            # Update cooling analysis
            cooling_text = f"Cooling Mode: {self.get_cooling_mode().upper()}\n"
            cooling_text += f"Current Temperature: {self.temp_history[-1] if self.temp_history else 'N/A'}°C\n"
            cooling_text += f"Temperature Threshold: {DAEMON_CONFIG['temp_threshold']}°C\n"
            cooling_text += f"Critical Threshold: {DAEMON_CONFIG['critical_threshold']}°C\n\n"
            
            if len(self.temp_history) > 10:
                avg_temp = sum(self.temp_history) / len(self.temp_history)
                max_temp = max(self.temp_history)
                min_temp = min(self.temp_history)
                
                cooling_text += f"Statistics (last {len(self.temp_history)} readings):\n"
                cooling_text += f"Average: {avg_temp:.1f}°C\n"
                cooling_text += f"Maximum: {max_temp:.1f}°C\n"
                cooling_text += f"Minimum: {min_temp:.1f}°C\n"
                
                # Check for trends
                if len(self.temp_history) >= 5:
                    recent = list(self.temp_history)[-5:]
                    if all(recent[i] <= recent[i+1] for i in range(4)):
                        cooling_text += "\n⚠️ Temperature trending UP"
                    elif all(recent[i] >= recent[i+1] for i in range(4)):
                        cooling_text += "\n✅ Temperature trending DOWN"
                    else:
                        cooling_text += "\n➡️ Temperature stable"
            
            self.cooling_text.setText(cooling_text)
            
            # Update process-temperature chart only if we have data
            if len(self.temp_history) > 0:
                self.update_process_temp_chart()
                
        except Exception as e:
            print(f"Error updating temperature analysis: {e}")
            import traceback
            traceback.print_exc()
    
    def update_process_temp_chart(self):
        """Update enhanced process-temperature correlation chart"""
        try:
            # Don't update if no temperature data
            if len(self.temp_history) == 0:
                return
            
            # Create new chart
            chart = QChart()
            chart.setBackgroundBrush(QColor(60, 63, 65))
            chart.setTitle("Temperature vs Process Activity")
            chart.setTitleFont(QFont("Arial", 12, QFont.Weight.Bold))
            chart.setTitleBrush(QColor(255, 255, 255))
            
            # Temperature series (main line)
            temp_series = QLineSeries()
            temp_series.setName("Temperature (°C)")
            
            # Add temperature data
            for i, temp in enumerate(self.temp_history):
                temp_series.append(i, float(temp))
            
            # Set axes FIRST before adding series
            axis_x = QValueAxis()
            axis_x.setRange(0, max(60, len(self.temp_history)))
            axis_x.setTitleText("Time (seconds ago)")
            axis_x.setLabelFormat("%d")
            axis_x.setGridLineColor(QColor(80, 80, 80))
            axis_x.setTitleBrush(QColor(255, 255, 255))
            axis_x.setLabelsBrush(QColor(255, 255, 255))
            
            axis_y = QValueAxis()
            axis_y.setRange(20, 100)
            axis_y.setTitleText("Temperature (°C)")
            axis_y.setLabelFormat("%d")
            axis_y.setGridLineColor(QColor(80, 80, 80))
            axis_y.setTitleBrush(QColor(255, 255, 255))
            axis_y.setLabelsBrush(QColor(255, 255, 255))
            
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            
            # Now add series and attach to axes
            chart.addSeries(temp_series)
            temp_series.attachAxis(axis_x)
            temp_series.attachAxis(axis_y)
            temp_series.setColor(QColor(244, 67, 54))
            temp_series.setPen(QPen(QColor(244, 67, 54), 3))
            
            # Set legend
            legend = chart.legend()
            legend.setVisible(True)
            legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
            legend.setBrush(QColor(60, 63, 65, 180))
            legend.setLabelColor(QColor(255, 255, 255))
            
            # Update chart view
            self.process_temp_chart_view.setChart(chart)
            
        except Exception as e:
            print(f"Error updating process-temp chart: {e}")
            import traceback
            traceback.print_exc()
    
    def update_resources_display(self):
        """Update resources display"""
        try:
            # Update CPU chart
            self.update_cpu_chart()
            
            # Update Memory chart
            self.update_memory_chart()
            
            # Update VRAM chart
            self.update_vram_chart()
            
            # Update top processes table
            self.update_top_processes()
        except Exception as e:
            print(f"Error updating resources display: {e}")
    
    def update_cpu_chart(self):
        """Update CPU usage chart"""
        try:
            if len(self.cpu_history) == 0:
                return
                
            chart = QChart()
            chart.setBackgroundBrush(QColor(60, 63, 65))
            chart.setTitle("CPU Usage History")
            chart.setTitleBrush(QColor(255, 255, 255))
            
            # Set axes FIRST
            axis_x = QValueAxis()
            axis_x.setRange(0, max(60, len(self.cpu_history)))
            axis_x.setTitleText("Time (seconds ago)")
            axis_x.setLabelFormat("%d")
            axis_x.setGridLineColor(QColor(80, 80, 80))
            axis_x.setTitleBrush(QColor(255, 255, 255))
            axis_x.setLabelsBrush(QColor(255, 255, 255))
            
            axis_y = QValueAxis()
            axis_y.setRange(0, 100)
            axis_y.setTitleText("CPU Usage (%)")
            axis_y.setLabelFormat("%d")
            axis_y.setGridLineColor(QColor(80, 80, 80))
            axis_y.setTitleBrush(QColor(255, 255, 255))
            axis_y.setLabelsBrush(QColor(255, 255, 255))
            
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            
            # Now add series
            cpu_series = QLineSeries()
            cpu_series.setName("CPU %")
            
            for i, cpu in enumerate(self.cpu_history):
                cpu_series.append(i, float(cpu))
            
            chart.addSeries(cpu_series)
            cpu_series.attachAxis(axis_x)
            cpu_series.attachAxis(axis_y)
            cpu_series.setColor(QColor(76, 175, 80))
            cpu_series.setPen(QPen(QColor(76, 175, 80), 2))
            
            self.cpu_chart_view.setChart(chart)
        except Exception as e:
            print(f"Error updating CPU chart: {e}")

    def update_memory_chart(self):
        """Update memory usage chart"""
        try:
            if len(self.mem_history) == 0:
                return
                
            chart = QChart()
            chart.setBackgroundBrush(QColor(60, 63, 65))
            chart.setTitle("Memory Usage History")
            chart.setTitleBrush(QColor(255, 255, 255))
            
            # Set axes FIRST
            axis_x = QValueAxis()
            axis_x.setRange(0, max(60, len(self.mem_history)))
            axis_x.setTitleText("Time (seconds ago)")
            axis_x.setLabelFormat("%d")
            axis_x.setGridLineColor(QColor(80, 80, 80))
            axis_x.setTitleBrush(QColor(255, 255, 255))
            axis_x.setLabelsBrush(QColor(255, 255, 255))
            
            axis_y = QValueAxis()
            axis_y.setRange(0, 100)
            axis_y.setTitleText("Memory Usage (%)")
            axis_y.setLabelFormat("%d")
            axis_y.setGridLineColor(QColor(80, 80, 80))
            axis_y.setTitleBrush(QColor(255, 255, 255))
            axis_y.setLabelsBrush(QColor(255, 255, 255))
            
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            
            # Now add series
            mem_series = QLineSeries()
            mem_series.setName("Memory %")
            
            for i, mem in enumerate(self.mem_history):
                mem_series.append(i, float(mem))
            
            chart.addSeries(mem_series)
            mem_series.attachAxis(axis_x)
            mem_series.attachAxis(axis_y)
            mem_series.setColor(QColor(33, 150, 243))
            mem_series.setPen(QPen(QColor(33, 150, 243), 2))
            
            self.mem_chart_view.setChart(chart)
        except Exception as e:
            print(f"Error updating memory chart: {e}")
    
    def update_vram_chart(self):
        """Update VRAM usage chart"""
        try:
            if len(self.vram_history) == 0:
                return
                
            chart = QChart()
            chart.setBackgroundBrush(QColor(60, 63, 65))
            chart.setTitle("VRAM Usage History")
            chart.setTitleBrush(QColor(255, 255, 255))
            
            # Set axes FIRST
            axis_x = QValueAxis()
            axis_x.setRange(0, max(60, len(self.vram_history)))
            axis_x.setTitleText("Time (seconds ago)")
            axis_x.setLabelFormat("%d")
            axis_x.setGridLineColor(QColor(80, 80, 80))
            axis_x.setTitleBrush(QColor(255, 255, 255))
            axis_x.setLabelsBrush(QColor(255, 255, 255))
            
            axis_y = QValueAxis()
            axis_y.setRange(0, max(1000, max(self.vram_history) if self.vram_history else 1000))
            axis_y.setTitleText("VRAM Usage (MB)")
            axis_y.setLabelFormat("%d")
            axis_y.setGridLineColor(QColor(80, 80, 80))
            axis_y.setTitleBrush(QColor(255, 255, 255))
            axis_y.setLabelsBrush(QColor(255, 255, 255))
            
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            
            # Now add series
            vram_series = QLineSeries()
            vram_series.setName("VRAM MB")
            
            for i, vram in enumerate(self.vram_history):
                vram_series.append(i, float(vram))
            
            chart.addSeries(vram_series)
            vram_series.attachAxis(axis_x)
            vram_series.attachAxis(axis_y)
            vram_series.setColor(QColor(255, 152, 0))
            vram_series.setPen(QPen(QColor(255, 152, 0), 2))
            
            self.vram_chart_view.setChart(chart)
        except Exception as e:
            print(f"Error updating VRAM chart: {e}")
    
    def update_top_processes(self):
        """Update top processes table"""
        if not hasattr(self, 'top_processes_table'):
            return  # Skip if table doesn't exist yet
        
        self.top_processes_table.setRowCount(0)
        
        # Get all processes
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                proc_info = proc.info
                if proc_info['cpu_percent'] > 0:  # Only show processes with CPU usage
                    procs.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort by CPU usage
        procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        
        # Add to table (top 10)
        for i, proc in enumerate(procs[:10]):
            row = self.top_processes_table.rowCount()
            self.top_processes_table.insertRow(row)
            
            # PID
            self.top_processes_table.setItem(row, 0, QTableWidgetItem(str(proc['pid'])))
            
            # Name
            self.top_processes_table.setItem(row, 1, QTableWidgetItem(proc['name']))
            
            # CPU %
            self.top_processes_table.setItem(row, 2, QTableWidgetItem(f"{proc['cpu_percent']:.1f}%"))
            
            # Memory %
            self.top_processes_table.setItem(row, 3, QTableWidgetItem(f"{proc['memory_percent']:.1f}%"))
            
            # VRAM usage
            vram_mb = 0
            if proc['pid'] in self.process_mem_history:
                # Check if it's a list/deque or a single value
                if hasattr(self.process_mem_history[proc['pid']], '__iter__') and not isinstance(self.process_mem_history[proc['pid']], int):
                    # It's a collection, get the last value
                    vram_mb = self.process_mem_history[proc['pid']][-1] if self.process_mem_history[proc['pid']] else 0
                else:
                    # It's a single value
                    vram_mb = self.process_mem_history[proc['pid']]
            
            self.top_processes_table.setItem(row, 4, QTableWidgetItem(f"{vram_mb:.1f} MB"))

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Nouveau GPU Monitor Enhanced")
    
    # Check for daemon mode
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        # TODO: Implement daemon mode
        print("Daemon mode not yet implemented")
        return
    
    monitor = EnhancedGPUMonitor()
    monitor.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()