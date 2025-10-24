#!/usr/bin/env python3
"""
Nouveau GPU Monitor - Universal Edition
Aplikacja do monitorowania kart NVIDIA z sterownikiem Nouveau
Wspiera wszystkie generacje od GeForce 6 do RTX 50xx

Wymagania: PyQt6, PyQt6-Charts, notify2, psutil
Instalacja: pip install PyQt6 PyQt6-Charts notify2 psutil
lub: sudo pacman -S python-pyqt6 python-pyqt6-charts python-notify2 python-psutil

Tryb daemon:
python3 nouveau_monitor_complete.py --daemon
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

# PyQt imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QTabWidget, QTableWidget, 
                             QTableWidgetItem, QGroupBox, QProgressBar, QTextEdit,
                             QHeaderView, QPushButton, QMessageBox, QScrollArea,
                             QCheckBox, QSpinBox, QDialog, QDialogButtonBox)
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

# Notify2 dla powiadomień
try:
    import notify2
    notify2.init("Nouveau GPU Monitor")
    NOTIFY_AVAILABLE = True
except ImportError:
    NOTIFY_AVAILABLE = False
    print("Uwaga: notify2 nie zainstalowane - brak powiadomień")

# Baza wiedzy o architekturach GPU - ZAKTUALIZOWANA
GPU_ARCHITECTURES = {
    'NV40': {'name': 'Curie', 'series': 'GeForce 6/7', 'opengl': '2.1', 'year': '2004-2006', 'va_api': 'Brak'},
    'NV50': {'name': 'Tesla', 'series': 'GeForce 8/9/GT 2xx', 'opengl': '3.3', 'year': '2006-2010', 'va_api': 'Bardzo ograniczone'},
    'NVC0': {'name': 'Fermi', 'series': 'GeForce 4xx/5xx', 'opengl': '4.3', 'year': '2010-2012', 'va_api': 'Częściowe'},
    'NVE0': {'name': 'Kepler', 'series': 'GeForce 6xx/7xx', 'opengl': '4.5', 'year': '2012-2014', 'va_api': 'Dobre'},
    'GM100': {'name': 'Maxwell', 'series': 'GeForce 9xx/10xx', 'opengl': '4.6', 'year': '2014-2016', 'va_api': 'Bardzo dobre'},
    'GP100': {'name': 'Pascal', 'series': 'GeForce 10xx', 'opengl': '4.6', 'year': '2016-2018', 'va_api': 'Bardzo dobre'},
    'GV100': {'name': 'Volta', 'series': 'Titan V', 'opengl': '4.6', 'year': '2017', 'va_api': 'Bardzo dobre'},
    'TU100': {'name': 'Turing', 'series': 'GeForce 16xx/RTX 20xx', 'opengl': '4.6', 'year': '2018-2020', 'va_api': 'Doskonałe'},
    'GA100': {'name': 'Ampere', 'series': 'RTX 30xx', 'opengl': '4.6', 'year': '2020-2022', 'va_api': 'Doskonałe'},
    'AD100': {'name': 'Ada Lovelace', 'series': 'RTX 40xx', 'opengl': '4.6', 'year': '2022+', 'va_api': 'Doskonałe'},
    'GB100': {'name': 'Blackwell', 'series': 'RTX 50xx', 'opengl': '4.6', 'year': '2024-2025', 'va_api': 'Doskonałe'},
    'GB200': {'name': 'Blackwell 2.0', 'series': 'RTX 60xx', 'opengl': '4.6', 'year': '2025-2026', 'va_api': 'Doskonałe'},
    'GH100': {'name': 'Hopper', 'series': 'H100/H200', 'opengl': '4.6', 'year': '2022-2024', 'va_api': 'Doskonałe'},
}

# Poprawiona baza danych dla konkretnych chipów
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
    'GT218': {'arch': 'NV50', 'name': 'GeForce 210/205'},
    
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

# Konfiguracja daemon
DAEMON_CONFIG = {
    'log_file': os.path.expanduser('~/.nouveau_monitor_daemon.log'),
    'config_file': os.path.expanduser('~/.nouveau_monitor_config.json'),
    'temp_threshold': 85,  # Próg temperatury (°C)
    'critical_threshold': 95,  # Krytyczny próg temperatury (°C)
    'check_interval': 5,  # Interwał sprawdzania (sekundy)
    'user_activity_timeout': 60,  # Czas bez aktywności użytkownika (sekundy)
    'max_log_entries': 1000,  # Maksymalna liczba wpisów w logu
    'auto_kill': False,  # Automatyczne zabijanie procesów
    'notify_video_accel': True,  # Powiadomienia o akceleracji wideo
}

class DaemonSettingsDialog(QDialog):
    """Dialog ustawień daemon"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia Daemon")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Próg temperatury
        temp_group = QGroupBox("Próg temperatury (°C)")
        temp_layout = QHBoxLayout()
        
        self.temp_threshold_spin = QSpinBox()
        self.temp_threshold_spin.setRange(60, 100)
        self.temp_threshold_spin.setValue(DAEMON_CONFIG['temp_threshold'])
        temp_layout.addWidget(QLabel("Ostrzeżenie:"))
        temp_layout.addWidget(self.temp_threshold_spin)
        
        self.critical_threshold_spin = QSpinBox()
        self.critical_threshold_spin.setRange(80, 120)
        self.critical_threshold_spin.setValue(DAEMON_CONFIG['critical_threshold'])
        temp_layout.addWidget(QLabel("Krytyczny:"))
        temp_layout.addWidget(self.critical_threshold_spin)
        
        temp_group.setLayout(temp_layout)
        layout.addWidget(temp_group)
        
        # Interwał sprawdzania
        interval_group = QGroupBox("Interwał sprawdzania")
        interval_layout = QHBoxLayout()
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(DAEMON_CONFIG['check_interval'])
        interval_layout.addWidget(QLabel("Sekundy:"))
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        
        interval_group.setLayout(interval_layout)
        layout.addWidget(interval_group)
        
        # Opcje
        options_group = QGroupBox("Opcje")
        options_layout = QVBoxLayout()
        
        self.auto_kill_checkbox = QCheckBox("Automatycznie zabijaj niebezpieczne procesy")
        self.auto_kill_checkbox.setChecked(DAEMON_CONFIG['auto_kill'])
        options_layout.addWidget(self.auto_kill_checkbox)
        
        self.notify_video_checkbox = QCheckBox("Powiadamiaj o akceleracji wideo")
        self.notify_video_checkbox.setChecked(DAEMON_CONFIG['notify_video_accel'])
        options_layout.addWidget(self.notify_video_checkbox)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Przyciski
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
            'auto_kill': self.auto_kill_checkbox.isChecked(),
            'notify_video_accel': self.notify_video_checkbox.isChecked()
        }

class GPUMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nouveau GPU Monitor - Universal Edition")
        self.setMinimumSize(1200, 800)
        
        # Historia temperatur dla wykresu
        self.temp_history = deque(maxlen=60)
        
        # Cache dla informacji o karcie
        self.gpu_info = self.detect_gpu()
        self.gpu_arch = self.detect_architecture()
        
        # Śledzenie procesów używających akceleracji
        self.video_accel_processes = set()
        
        # Znajdź identyfikator nouveau-pci-XXXX
        self.nouveau_pci_id = self.find_nouveau_pci_id()
        
        self.init_ui()
        
        # Timer do odświeżania co 2 sekundy
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)
        
        # Pierwsze odświeżenie
        self.update_data()
    
    def find_nouveau_pci_id(self):
        """Znajdź identyfikator nouveau-pci-XXXX z sensors"""
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            for line in result.stdout.split('\n'):
                if 'nouveau-pci-' in line:
                    match = re.search(r'nouveau-pci-(\d+)', line)
                    if match:
                        return match.group(1)
        except Exception as e:
            print(f"Błąd wyszukiwania nouveau-pci: {e}")
        return None
    
    def detect_gpu(self):
        """Wykryj informacje o GPU przy starcie"""
        info = {
            'name': 'Unknown GPU',
            'pci_id': '00:00.0',
            'vram_mb': 0,
            'driver': 'nouveau',
            'chip_id': 'Unknown',
            'family': 'Unknown'
        }
        
        try:
            # Znajdź kartę NVIDIA w lspci
            result = subprocess.run(['lspci', '-nn'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n'):
                if 'NVIDIA' in line and any(x in line for x in ['VGA', '3D', 'Display']):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        info['pci_id'] = parts[0].strip()
                        
                        # Wyciągnij nazwę GPU
                        name_match = re.search(r'NVIDIA Corporation (.*?)(?:\[|\(|$)', line)
                        if name_match:
                            info['name'] = name_match.group(1).strip()
                        
                        # Wyciągnij ID urządzenia [10de:xxxx]
                        id_match = re.search(r'\[10de:([0-9a-f]{4})\]', line)
                        if id_match:
                            info['chip_id'] = id_match.group(1).upper()
                    break
            
            # Sprawdź dmesg dla chip family
            result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=2)
            dmesg = result.stdout
            
            # Szukaj nouveau chip detection
            family_match = re.search(r'nouveau.*NVIDIA (NV[0-9A-F]+|G[0-9A-F]+|GT[0-9]+|GF[0-9]+|GK[0-9]+|GM[0-9]+|GP[0-9]+|GV[0-9]+|TU[0-9]+|GA[0-9]+|AD[0-9]+|GB[0-9]+|GH[0-9]+)', dmesg)
            if family_match:
                info['family'] = family_match.group(1)
            
            # Sprawdź VRAM z dmesg
            vram_match = re.search(r'nouveau.*VRAM:\s*(\d+)\s*MiB', dmesg)
            if vram_match:
                info['vram_mb'] = int(vram_match.group(1))
            else:
                # Spróbuj z glxinfo
                try:
                    result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
                    vram_match = re.search(r'Dedicated video memory:\s*(\d+)\s*MB', result.stdout)
                    if vram_match:
                        info['vram_mb'] = int(vram_match.group(1))
                except:
                    pass
                    
        except Exception as e:
            print(f"Błąd wykrywania GPU: {e}")
        
        return info
    
    def detect_architecture(self):
        """Wykryj architekturę GPU na podstawie chip ID - POPRAWIONA"""
        chip_id = self.gpu_info['chip_id']
        family = self.gpu_info['family']
        
        # Najpierw sprawdź w bazie danych chipów
        if family in CHIP_DATABASE:
            return CHIP_DATABASE[family]['arch']
        
        # Spróbuj dopasować na podstawie prefiksu
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
            # Sprawdź czy to Blackwell czy Blackwell 2.0
            if len(family) > 3 and family[3] == '2':
                return 'GB200'
            else:
                return 'GB100'
        elif family.startswith('GH'):
            return 'GH100'
        
        # Fallback na podstawie chip ID
        if chip_id:
            chip_num = int(chip_id, 16) if chip_id != 'Unknown' else 0
            
            # Specjalne przypadki dla konkretnych chipów
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
            
            # Ogólne zakresy
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
        """Pobierz informacje o architekturze"""
        if self.gpu_arch in GPU_ARCHITECTURES:
            return GPU_ARCHITECTURES[self.gpu_arch]
        return {
            'name': 'Unknown',
            'series': 'Unknown',
            'opengl': 'Unknown',
            'year': 'Unknown',
            'va_api': 'Unknown'
        }
    
    def init_ui(self):
        """Inicjalizacja interfejsu użytkownika"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Header z nazwą GPU i architekturą
        arch_info = self.get_arch_info()
        header_text = f"🖥️ {self.gpu_info['name']}"
        if self.gpu_arch != 'Unknown':
            header_text += f"  |  {arch_info['name']} ({arch_info['series']})"
        header_text += f"  |  VRAM: {self.gpu_info['vram_mb']} MB"
        
        header = QLabel(header_text)
        header.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("padding: 10px; background-color: #2a2a2a; border-radius: 5px;")
        main_layout.addWidget(header)
        
        # Sub-header z dodatkowym info
        subheader_text = f"Chip: {self.gpu_info['family']} ({self.gpu_info['chip_id']})  |  "
        subheader_text += f"OpenGL: {arch_info['opengl']}  |  VA-API: {arch_info['va_api']}"
        
        subheader = QLabel(subheader_text)
        subheader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subheader.setStyleSheet("padding: 5px; color: #aaa;")
        main_layout.addWidget(subheader)
        
        # Pokazuj ostrzeżenia dla starszych/nowszych kart
        self.arch_warning = QLabel()
        self.arch_warning.setWordWrap(True)
        self.arch_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.arch_warning)
        self.update_arch_warning()
        
        # Toolbar z opcjami
        toolbar = QHBoxLayout()
        
        daemon_btn = QPushButton("🔧 Ustawienia Daemon")
        daemon_btn.clicked.connect(self.show_daemon_settings)
        toolbar.addWidget(daemon_btn)
        
        self.daemon_status_label = QLabel("Daemon: Nieaktywny")
        toolbar.addWidget(self.daemon_status_label)
        
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)
        
        # Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Tab 1: Przegląd
        tabs.addTab(self.create_overview_tab(), "📊 Przegląd")
        
        # Tab 2: Procesy
        tabs.addTab(self.create_processes_tab(), "⚙️ Procesy GPU")
        
        # Tab 3: Możliwości karty
        tabs.addTab(self.create_capabilities_tab(), "🎯 Możliwości")
        
        # Tab 4: Informacje o karcie
        tabs.addTab(self.create_card_info_tab(), "ℹ️ Informacje")
        
        # Tab 5: Kodeki
        tabs.addTab(self.create_codecs_tab(), "🎬 Kodeki")
        
        # Tab 6: Porady dla twojej karty
        tabs.addTab(self.create_recommendations_tab(), "💡 Porady")
        
        # Status bar z czasem ostatniego odświeżenia
        self.last_update_label = QLabel()
        self.statusBar().addPermanentWidget(self.last_update_label)
        self.statusBar().showMessage("Nouveau GPU Monitor v2.2 - Universal Edition")
    
    def show_daemon_settings(self):
        """Pokaż dialog ustawień daemon"""
        dialog = DaemonSettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            DAEMON_CONFIG.update(settings)
            self.save_daemon_config()
            self.show_notification("Ustawienia zapisane", "Konfiguracja daemon została zaktualizowana")
    
    def save_daemon_config(self):
        """Zapisz konfigurację daemon"""
        try:
            with open(DAEMON_CONFIG['config_file'], 'w') as f:
                json.dump(DAEMON_CONFIG, f, indent=2)
        except Exception as e:
            print(f"Błąd zapisu konfiguracji: {e}")
    
    def load_daemon_config(self):
        """Wczytaj konfigurację daemon"""
        try:
            if os.path.exists(DAEMON_CONFIG['config_file']):
                with open(DAEMON_CONFIG['config_file'], 'r') as f:
                    DAEMON_CONFIG.update(json.load(f))
        except Exception as e:
            print(f"Błąd wczytywania konfiguracji: {e}")
    
    def show_notification(self, title, message, urgency="low"):
        """Pokaż powiadomienie systemowe - POPRAWIONA"""
        if NOTIFY_AVAILABLE:
            try:
                notification = notify2.Notification(title, message)
                # Poprawione poziomy pilności: low, normal, critical
                if urgency == "critical":
                    notification.set_urgency(notify2.URGENCY_CRITICAL)
                elif urgency == "normal":
                    notification.set_urgency(notify2.URGENCY_NORMAL)
                else:
                    notification.set_urgency(notify2.URGENCY_LOW)
                notification.show()
            except Exception as e:
                print(f"Błąd powiadomienia: {e}")
    
    def update_arch_warning(self):
        """Aktualizuj ostrzeżenie zależnie od architektury"""
        arch_info = self.get_arch_info()
        warning_text = ""
        style = ""
        
        if self.gpu_arch == 'NV40':
            warning_text = "⚠️ Bardzo stara karta (2004-2006). Nouveau ma minimalne wsparcie. Rozważ właściwy sterownik nvidia-173xx (legacy)."
            style = "background-color: #8B0000; color: white; padding: 8px; border-radius: 5px; font-weight: bold;"
        elif self.gpu_arch == 'NV50':
            warning_text = "⚠️ Starsza karta (2006-2010). Ograniczone wsparcie VA-API. Dla pełnych funkcji: nvidia-340xx lub nvidia-390xx."
            style = "background-color: #FF6600; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['NVC0', 'NVE0']:
            warning_text = "ℹ️ Karta średniej generacji. Nouveau działa dobrze, ale dla pełnej wydajności rozważ nvidia-470xx."
            style = "background-color: #4A90E2; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['GM100', 'GP100', 'GV100']:
            warning_text = "✅ Dobra współpraca z Nouveau! Dla ray-tracing i pełnej wydajności rozważ nvidia-530xx+"
            style = "background-color: #2E7D32; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['TU100', 'GA100', 'AD100']:
            warning_text = "⚠️ Nowa karta - Nouveau może wymagać signed firmware. Dla RTX/DLSS potrzebny właściwy sterownik nvidia-550xx+"
            style = "background-color: #FF9800; color: white; padding: 8px; border-radius: 5px;"
        elif self.gpu_arch in ['GB100', 'GB200', 'GH100']:
            warning_text = "🔮 Najnowsza karta - Nouveau może mieć ograniczone wsparcie. Dla pełnej wydajności potrzebny najnowszy sterownik NVIDIA."
            style = "background-color: #9C27B0; color: white; padding: 8px; border-radius: 5px;"
        
        self.arch_warning.setText(warning_text)
        self.arch_warning.setStyleSheet(style)
        self.arch_warning.setVisible(bool(warning_text))
    
    def create_overview_tab(self):
        """Tab z przeglądem GPU"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Górna sekcja - temperatura i VRAM
        top_layout = QHBoxLayout()
        
        # Temperatura
        temp_group = QGroupBox("🌡️ Temperatura GPU")
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
        
        # Dodatkowe info o temperaturach
        temp_info_layout = QHBoxLayout()
        self.temp_max_label = QLabel("Max: --°C")
        self.temp_crit_label = QLabel("Crit: --°C")
        temp_info_layout.addWidget(self.temp_max_label)
        temp_info_layout.addWidget(self.temp_crit_label)
        temp_layout.addLayout(temp_info_layout)
        
        temp_group.setLayout(temp_layout)
        top_layout.addWidget(temp_group, 2)
        
        # VRAM Info
        vram_group = QGroupBox("💾 Pamięć wideo (VRAM)")
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
        
        vram_note = QLabel("⚠️ Nouveau: przybliżone dane")
        vram_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vram_note.setStyleSheet("color: #888; font-size: 10px;")
        vram_layout.addWidget(vram_note)
        
        vram_group.setLayout(vram_layout)
        top_layout.addWidget(vram_group, 1)
        
        layout.addLayout(top_layout)
        
        # Clock info (placeholder dla nowszych kart)
        clock_group = QGroupBox("⚡ Częstotliwości")
        clock_layout = QHBoxLayout()
        
        self.gpu_clock_label = QLabel("GPU: N/A")
        self.mem_clock_label = QLabel("VRAM: N/A")
        self.power_label = QLabel("Power: N/A")
        clock_layout.addWidget(self.gpu_clock_label)
        clock_layout.addWidget(self.mem_clock_label)
        clock_layout.addWidget(self.power_label)
        
        clock_note = QLabel("Nouveau nie eksponuje informacji o zegarach i mocy")
        clock_note.setStyleSheet("color: #888;")
        clock_layout.addWidget(clock_note)
        
        clock_group.setLayout(clock_layout)
        layout.addWidget(clock_group)
        
        # Wykres temperatury
        chart_group = QGroupBox("📈 Historia temperatury (ostatnie 2 minuty)")
        chart_layout = QVBoxLayout()
        
        self.temp_series = QLineSeries()
        self.temp_chart = QChart()
        self.temp_chart.addSeries(self.temp_series)
        self.temp_chart.setTitle("")
        self.temp_chart.legend().hide()
        self.temp_chart.setBackgroundBrush(QColor(53, 53, 53))
        
        axis_x = QValueAxis()
        axis_x.setTitleText("Czas (s)")
        axis_x.setRange(0, 120)
        axis_x.setLabelFormat("%d")
        
        axis_y = QValueAxis()
        axis_y.setTitleText("Temperatura (°C)")
        axis_y.setRange(20, 100)
        axis_y.setLabelFormat("%d")
        
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
        """Tab z procesami używającymi GPU"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Procesy używające GPU przez DRM (Direct Rendering Manager)")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Odśwież")
        refresh_btn.clicked.connect(self.update_processes)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Tabela procesów
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(7)
        self.process_table.setHorizontalHeaderLabels(["PID", "Użytkownik", "Polecenie", "Device", "CPU %", "RAM (MB)", "Akceleracja"])
        
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
        
        # Informacja o ograniczeniach
        note = QLabel(
            "⚠️ <b>Ograniczenia Nouveau:</b><br>"
            "• Brak informacji o użyciu GPU per proces (% obciążenia GPU)<br>"
            "• Brak informacji o użyciu VRAM per proces<br>"
            "• Dla pełnego monitoringu rozważ właściwy sterownik NVIDIA"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #FFA500; padding: 10px; background-color: #3a3a3a; border-radius: 5px;")
        layout.addWidget(note)
        
        return widget
    
    def create_capabilities_tab(self):
        """Tab z możliwościami i wspieranymi standardami karty"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Obsługiwane standardy i możliwości karty graficznej")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Odśwież")
        refresh_btn.clicked.connect(self.update_capabilities)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Scroll area dla wszystkich grup
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
        vaapi_group = QGroupBox("🎬 VA-API (Akceleracja Video)")
        vaapi_layout = QVBoxLayout()
        self.vaapi_caps_table = QTableWidget()
        self.vaapi_caps_table.setColumnCount(2)
        self.vaapi_caps_table.setHorizontalHeaderLabels(["Profil", "Entrypoints"])
        self.vaapi_caps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.vaapi_caps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.vaapi_caps_table.setMaximumHeight(250)
        vaapi_layout.addWidget(self.vaapi_caps_table)
        vaapi_group.setLayout(vaapi_layout)
        scroll_layout.addWidget(vaapi_group)
        
        # VDPAU Info
        vdpau_group = QGroupBox("📺 VDPAU")
        vdpau_layout = QVBoxLayout()
        self.vdpau_info = QLabel("VDPAU: sprawdzanie...")
        self.vdpau_info.setWordWrap(True)
        vdpau_layout.addWidget(self.vdpau_info)
        vdpau_group.setLayout(vdpau_layout)
        scroll_layout.addWidget(vdpau_group)
        
        # OpenGL Extensions
        ext_group = QGroupBox("🔧 OpenGL Extensions (wybrane)")
        ext_layout = QVBoxLayout()
        self.extensions_text = QTextEdit()
        self.extensions_text.setReadOnly(True)
        self.extensions_text.setMaximumHeight(150)
        self.extensions_text.setFont(QFont("Monospace", 8))
        ext_layout.addWidget(self.extensions_text)
        ext_group.setLayout(ext_layout)
        scroll_layout.addWidget(ext_group)
        
        # GPU Limits
        limits_group = QGroupBox("📊 Limity GPU")
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
        """Tab z informacjami o karcie"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        
        refresh_btn = QPushButton("🔄 Odśwież")
        refresh_btn.clicked.connect(self.update_card_info)
        toolbar.addWidget(refresh_btn)
        
        copy_btn = QPushButton("📋 Kopiuj")
        copy_btn.clicked.connect(self.copy_card_info)
        toolbar.addWidget(copy_btn)
        
        layout.addLayout(toolbar)
        
        self.card_info_text = QTextEdit()
        self.card_info_text.setReadOnly(True)
        self.card_info_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.card_info_text)
        
        return widget
    
    def create_codecs_tab(self):
        """Tab z informacjami o kodekach"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        info_label = QLabel("Wsparcie kodowania/dekodowania wideo")
        info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Sprawdź ponownie")
        refresh_btn.clicked.connect(self.update_codecs)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        self.codecs_text = QTextEdit()
        self.codecs_text.setReadOnly(True)
        self.codecs_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.codecs_text)
        
        # Info o instalacji
        install_info = QLabel(
            "<b>Jak zainstalować wsparcie VA-API:</b><br>"
            "• Arch/CachyOS: <code>sudo pacman -S libva-utils</code><br>"
            "• Debian/Ubuntu: <code>sudo apt install vainfo</code><br>"
            "• Fedora: <code>sudo dnf install libva-utils</code>"
        )
        install_info.setWordWrap(True)
        install_info.setStyleSheet("padding: 10px; background-color: #3a3a3a; border-radius: 5px;")
        layout.addWidget(install_info)
        
        return widget
    
    def create_recommendations_tab(self):
        """Tab z poradami specyficznymi dla tej karty"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Nagłówek
        header = QLabel(f"💡 Porady dla {self.gpu_info['name']}")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(header)
        
        # Info o architekturze
        arch_info = self.get_arch_info()
        arch_group = QGroupBox("📋 Twoja karta")
        arch_layout = QVBoxLayout()
        
        arch_text = f"""
<b>Architektura:</b> {arch_info['name']}<br>
<b>Seria:</b> {arch_info['series']}<br>
<b>Rok wydania:</b> {arch_info['year']}<br>
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
        
        # Rekomendacje dla konkretnej architektury
        rec_group = QGroupBox("✨ Zalecenia")
        rec_layout = QVBoxLayout()
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMinimumHeight(300)
        rec_layout.addWidget(self.recommendations_text)
        rec_group.setLayout(rec_layout)
        scroll_layout.addWidget(rec_group)
        
        # Linki i zasoby
        links_group = QGroupBox("🔗 Przydatne linki")
        links_layout = QVBoxLayout()
        links_text = QLabel("""
<b>Dokumentacja Nouveau:</b><br>
• <a href="https://nouveau.freedesktop.org/">nouveau.freedesktop.org</a><br>
• <a href="https://wiki.archlinux.org/title/Nouveau">ArchWiki - Nouveau</a><br>
<br>
<b>Sterowniki NVIDIA:</b><br>
• <a href="https://www.nvidia.com/Download/index.aspx">NVIDIA Driver Downloads</a><br>
• <a href="https://github.com/NVIDIA/open-gpu-kernel-modules">NVIDIA Open Kernel Modules</a><br>
<br>
<b>Narzędzia:</b><br>
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
        
        # Generuj rekomendacje
        self.generate_recommendations()
        
        return widget
    
    def generate_recommendations(self):
        """Generuj rekomendacje dla konkretnej architektury"""
        rec_text = ""
        
        if self.gpu_arch == 'NV40':
            rec_text = """
<h3>🔴 GeForce 6/7 (Curie) - Bardzo stara karta</h3>

<b>Status Nouveau:</b><br>
• Minimalne wsparcie, brak reclocking<br>
• OpenGL 2.1 maksymalnie<br>
• Brak VA-API<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Rozważ nvidia-173xx (legacy)</b> dla lepszej wydajności<br>
2. Używaj lekkich środowisk graficznych (XFCE, LXDE)<br>
3. Wyłącz kompozytor okien<br>
4. Dla filmów: używaj mpv z vdpau (może nie działać)<br>
5. Dla gier: tylko bardzo stare tytuły (przed 2010)<br>
<br>
<b>Ograniczenia:</b><br>
• Brak Vulkan<br>
• Brak nowoczesnej akceleracji wideo<br>
• Może brakować wsparcia w nowych kernelach
            """
        elif self.gpu_arch == 'NV50':
            rec_text = """
<h3>🟠 GeForce 8/9/GT 2xx (Tesla) - Starsza karta</h3>

<b>Status Nouveau:</b><br>
• Dobre podstawowe wsparcie<br>
• OpenGL 3.3<br>
• Bardzo ograniczone VA-API<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Dla wydajności: nvidia-340xx lub nvidia-390xx</b><br>
2. VDPAU działa lepiej niż VA-API dla wideo<br>
3. Włącz DRM KMS: dodaj <code>nouveau.modeset=1</code> do kernel params<br>
4. Dla filmów 1080p: mpv z vdpau<br>
5. Lekkie gry (przed 2015) powinny działać<br>
<br>
<b>Optymalizacje:</b><br>
• Wyłącz kompozycję w przeglądarce: <code>--disable-gpu-compositing</code><br>
• Używaj mesa-amber dla lepszej kompatybilności OpenGL<br>
• Reclocking nie działa - karta pracuje na niskich zegarach<br>
<br>
<b>Znane problemy:</b><br>
• Brak reclocking (stuck at boot clocks)<br>
• Przypadkowe zawieszenia przy dużym obciążeniu 3D
            """
        elif self.gpu_arch == 'NVC0':
            rec_text = """
<h3>🟡 GeForce 4xx/5xx (Fermi) - Średnia generacja</h3>

<b>Status Nouveau:</b><br>
• Dobre wsparcie<br>
• OpenGL 4.3<br>
• Częściowe VA-API (MPEG2, VC1, niektóre H.264)<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Nouveau działa przyzwoicie</b> dla desktop i multimediów<br>
2. <b>Dla gier: nvidia-470xx</b> (ostatni wspierający Fermi)<br>
3. VA-API: zainstaluj <code>libva-mesa-driver</code><br>
4. VDPAU działa świetnie dla 1080p wideo<br>
5. Reclocking: eksperymentalny, używaj ostrożnie<br>
<br>
<b>Optymalizacje:</b><br>
• Eksperymentalny reclocking: <code>nouveau.pstate=1</code> (ryzykowne!)<br>
• Dla Chrome/Firefox: włącz akcelerację sprzętową<br>
• OpenCL: możliwe przez Mesa Clover (ograniczone)<br>
<br>
<b>Do gier:</b><br>
• Starsze gry (2010-2016): powinny działać na niskich/średnich<br>
• Wine/Proton: działa, ale wolniej niż nvidia<br>
• Vulkan: nie wspierane przez Nouveau dla Fermi
            """
        elif self.gpu_arch == 'NVE0':
            rec_text = """
<h3>🟢 GeForce 6xx/7xx (Kepler) - Dobra karta</h3>

<b>Status Nouveau:</b><br>
• Bardzo dobre wsparcie<br>
• OpenGL 4.5<br>
• Dobre VA-API (większość kodeków)<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Nouveau to dobry wybór</b> dla użytku codziennego<br>
2. <b>Dla gier AAA: nvidia-470xx lub nowszy</b><br>
3. VA-API wspiera: MPEG2, VC1, H.264, H.265 (częściowo)<br>
4. Reclocking działa - możesz przełączać profile mocy<br>
5. Firefox/Chrome: akceleracja sprzętowa działa dobrze<br>
<br>
<b>Optymalizacje:</b><br>
• Włącz reclocking: <code>nouveau.pstate=1</code> (stabilne)<br>
• Zarządzanie mocą: <code>echo auto > /sys/class/drm/card0/device/power_profile</code><br>
• Akceleracja wideo: używaj VA-API dla H.264/H.265<br>
<br>
<b>Gry:</b><br>
• Indie i starsze AAA: będą działać<br>
• Vulkan: NVK (eksperymentalne) lub nvidia driver<br>
• Emulatory: dobra wydajność
            """
        elif self.gpu_arch in ['GM100', 'GP100']:
            rec_text = """
<h3>🟢 GeForce 9xx/10xx (Maxwell/Pascal) - Świetna karta</h3>

<b>Status Nouveau:</b><br>
• Bardzo dobre wsparcie<br>
• OpenGL 4.6<br>
• Bardzo dobre VA-API<br>
• NVK (Vulkan) - eksperymentalne<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Nouveau świetnie sprawdza się</b> do desktop/multimedia<br>
2. <b>Dla gier: nvidia-530xx+</b> lub eksperymentalny NVK<br>
3. VA-API wspiera wszystkie popularne kodeki<br>
4. Reclocking działa stabilnie<br>
5. Spróbuj Mesa NVK dla Vulkan (wymaga Mesa 23.1+)<br>
<br>
<b>Optymalizacje:</b><br>
• NVK Vulkan: <code>export MESA_VK_VERSION_OVERRIDE=1.3</code><br>
• Reclocking: automatyczny w najnowszych kernelach<br>
• Akceleracja wideo: działa out-of-the-box<br>
• Power management: doskonałe<br>
<br>
<b>Gry:</b><br>
• NVK: wiele gier Vulkan działa (eksperymentalne)<br>
• OpenGL: świetna wydajność<br>
• DXVK/VKD3D: działa przez NVK<br>
• Dla konkurencyjnych gier: używaj nvidia
            """
        elif self.gpu_arch == 'GV100':
            rec_text = """
<h3>🟢 Volta (Titan V) - Bardzo wydajna</h3>

<b>Status Nouveau:</b><br>
• Dobre wsparcie podstawowe<br>
• OpenGL 4.6<br>
• Bardzo dobre VA-API<br>
• NVK - eksperymentalne ale obiecujące<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Nouveau:</b> desktop i multimedia - doskonałe<br>
2. <b>Dla compute/AI: nvidia-535xx+</b> (CUDA, Tensor Cores)<br>
3. NVK Vulkan już całkiem użyteczny<br>
4. Reclocking automatyczny<br>
<br>
<b>Optymalizacje:</b><br>
• Sprawdź najnowszą Mesę dla NVK<br>
• CUDA: tylko z właściwym sterownikiem<br>
• Tensor Cores: nvidia driver required
            """
        elif self.gpu_arch in ['TU100', 'GA100', 'AD100']:
            rec_text = """
<h3>🟠 Turing/Ampere/Ada (RTX) - Nowa karta</h3>

<b>Status Nouveau:</b><br>
• Podstawowe wsparcie<br>
• OpenGL 4.6<br>
• Doskonałe VA-API (AV1 wspierane!)<br>
• NVK Vulkan - aktywnie rozwijany<br>
• <b>Wymaga signed firmware!</b><br>
<br>
<b>⚠️ Ważne - Signed Firmware:</b><br>
1. Zainstaluj: <code>sudo pacman -S linux-firmware</code><br>
2. Może wymagać: <code>nouveau.config=NvGspRm=1</code><br>
3. Starsze kernele mogą nie wspierać w pełni<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Nouveau:</b> OK dla desktop, ale ograniczone<br>
2. <b>Dla RTX/DLSS/Ray-tracing: nvidia-550xx+</b> (obowiązkowo)<br>
3. NVK Vulkan coraz lepszy - testuj Mesa 24.0+<br>
4. AV1 decode - działa przez VA-API!<br>
<br>
<b>Optymalizacje:</b><br>
• GSP firmware: <code>nouveau.config=NvGspRm=1</code><br>
• NVK updates: używaj najnowszej Mesy<br>
• Wayland: działa lepiej niż X11<br>
<br>
<b>Gry:</b><br>
• OpenGL: dobra wydajność<br>
• Vulkan przez NVK: wiele gier już działa!<br>
• Ray-tracing: tylko nvidia driver<br>
• DLSS: tylko nvidia driver<br>
<br>
<b>Jeśli używasz do gier:</b><br>
Niestety RTX features (RT cores, Tensor cores, DLSS) działają<br>
tylko z właściwym sterownikiem NVIDIA. Nouveau daje ~50-70%<br>
wydajności właściwego drivera.
            """
        elif self.gpu_arch in ['GB100', 'GB200', 'GH100']:
            rec_text = """
<h3>🔮 Blackwell/Hopper - Najnowsza karta</h3>

<b>Status Nouveau:</b><br>
• Bardzo ograniczone wsparcie (jeszcze nie released)<br>
• OpenGL 4.6<br>
• Potencjalnie doskonałe VA-API<br>
• NVK Vulkan - w fazie rozwoju<br>
• <b>Wymaga najnowszych sterowników!</b><br>
<br>
<b>⚠️ Ważne - Wsparcie Nouveau:</b><br>
1. Nouveau dla tych kart jest w bardzo wczesnej fazie rozwoju<br>
2. Wymaga najnowszych kerneli (6.7+)<br>
3. Wymaga najnowszej Mesy (24.0+)<br>
4. Może wymagać specyficznego firmware<br>
<br>
<b>Zalecenia:</b><br>
1. <b>Nouveau:</b> Bardzo ograniczone, tylko podstawowe funkcje<br>
2. <b>Dla pełnej wydajności: nvidia-550xx+</b> (obowiązkowo)<br>
3. Dla AI/HPC: CUDA z właściwym sterownikiem<br>
4. Dla gier: tylko nvidia driver<br>
<br>
<b>Ograniczenia:</b><br>
• Brak wsparcia dla ray-tracing<br>
• Brak wsparcia dla DLSS<br>
• Brak wsparcia dla nowych funkcji AI<br>
• Ograniczone reclocking<br>
<br>
<b>Przyszłość:</b><br>
Wsparcie Nouveau dla tych kart będzie rozwijane w ciągu najbliższych lat.
            """
        else:
            rec_text = """
<h3>❓ Nieznana architektura</h3>

Nie udało się dokładnie zidentyfikować architektury karty.<br>
<br>
<b>Ogólne zalecenia dla Nouveau:</b><br>
• Sprawdź wiki nouveau dla swojego modelu<br>
• Testuj najnowsze kernele i Mesę<br>
• Rozważ właściwy sterownik NVIDIA dla gier
            """
        
        self.recommendations_text.setHtml(rec_text)
    
    def update_data(self):
        """Aktualizacja wszystkich danych"""
        self.update_temperature()
        self.update_vram()
        self.update_processes()
        self.update_capabilities()
        self.update_card_info()
        self.update_codecs()
        
        # Aktualizuj timestamp
        now = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.setText(f"Ostatnia aktualizacja: {now}")
    
    def update_temperature(self):
        """Aktualizacja temperatury GPU - POPRAWIONA"""
        try:
            # Najpierw spróbuj z sensors nouveau-pci-XXXX
            temp = self.get_temperature_from_nouveau_sensors()
            
            if temp is not None:
                self.temp_label.setText(f"{temp:.1f}°C")
                self.temp_bar.setValue(int(temp))
                
                # Kolorowanie
                if temp < 70:
                    self.temp_status.setText("✅ Status: Temperatura OK")
                    self.temp_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                elif temp < 85:
                    self.temp_status.setText("⚠️ Status: Temperatura podwyższona")
                    self.temp_status.setStyleSheet("color: #FF9800; font-weight: bold;")
                else:
                    self.temp_status.setText("🔥 Status: WYSOKA TEMPERATURA!")
                    self.temp_status.setStyleSheet("color: #F44336; font-weight: bold;")
                
                # Historia
                self.temp_history.append(temp)
                
                # Aktualizuj wykres
                self.temp_series.clear()
                for i, t in enumerate(self.temp_history):
                    self.temp_series.append(i * 2, t)
                
                # Dostosuj zakres Y
                if self.temp_history:
                    min_temp = max(20, min(self.temp_history) - 5)
                    max_temp = max(self.temp_history) + 10
                    self.temp_chart.axes(Qt.Orientation.Vertical)[0].setRange(min_temp, max_temp)
            else:
                self.temp_label.setText("N/A")
                self.temp_status.setText("❌ Brak sensora temperatury")
                self.temp_status.setStyleSheet("color: #888;")
                
        except Exception as e:
            self.temp_label.setText("ERROR")
            self.temp_status.setText(f"Błąd: {str(e)[:50]}")
    
    def get_temperature_from_nouveau_sensors(self):
        """Pobierz temperaturę z sensors nouveau-pci-XXXX - POPRAWIONA"""
        try:
            # Jeśli mamy zidentyfikowany nouveau-pci-XXXX, użyj go bezpośrednio
            if self.nouveau_pci_id:
                result = subprocess.run(['sensors', f'nouveau-pci-{self.nouveau_pci_id}'], 
                                      capture_output=True, text=True, timeout=3)
                
                for line in result.stdout.split('\n'):
                    if 'temp1' in line:
                        temp_match = re.search(r'\+(\d+\.\d+)°C', line)
                        if temp_match:
                            return float(temp_match.group(1))
            
            # Jeśli nie, spróbuj znaleźć w ogólnym outputcie sensors
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            
            for line in result.stdout.split('\n'):
                if 'nouveau' in line.lower() and 'temp1' in line.lower():
                    temp_match = re.search(r'\+(\d+\.\d+)°C', line)
                    if temp_match:
                        return float(temp_match.group(1))
            
            # Jeśli nie znaleziono w sensors, spróbuj hwmon
            return self.get_temperature_from_hwmon()
            
        except Exception as e:
            print(f"Błąd odczytu temperatury z sensors: {e}")
            return self.get_temperature_from_hwmon()
    
    def get_temperature_from_hwmon(self):
        """Pobierz temperaturę z hwmon"""
        try:
            # Znajdź urządzenie DRM
            drm_path = None
            for device in os.listdir('/sys/class/drm'):
                if device.startswith('card') and '-' not in device:
                    drm_path = f'/sys/class/drm/{device}/device'
                    break
            
            if not drm_path:
                return None
            
            # Znajdź hwmon
            if os.path.exists(drm_path):
                for item in os.listdir(drm_path):
                    if item.startswith('hwmon'):
                        hwmon_path = os.path.join(drm_path, item)
                        if os.path.exists(os.path.join(hwmon_path, 'temp1_input')):
                            with open(os.path.join(hwmon_path, 'temp1_input'), 'r') as f:
                                temp = int(f.read().strip()) / 1000.0
                                return temp
            
            return None
            
        except Exception as e:
            print(f"Błąd odczytu temperatury z hwmon: {e}")
            return None
    
    def update_vram(self):
        """Aktualizacja informacji o VRAM"""
        try:
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            
            total_match = re.search(r'Dedicated video memory:\s*(\d+)\s*MB', result.stdout)
            if total_match:
                total = int(total_match.group(1))
                self.vram_total_label.setText(f"Total: {total} MB")
            
            avail_match = re.search(r'Currently available dedicated video memory:\s*(\d+)\s*MB', result.stdout)
            if avail_match:
                available = int(avail_match.group(1))
                used = total - available if total_match else 0
                
                self.vram_used_label.setText(f"Used: ~{used} MB")
                self.vram_free_label.setText(f"Free: ~{available} MB")
            else:
                self.vram_used_label.setText("Used: N/A")
                self.vram_free_label.setText("Free: N/A")
                
        except Exception as e:
            pass
    
    def update_processes(self):
        """Aktualizacja listy procesów"""
        try:
            processes = []
            
            for device in ['card0', 'card1', 'card2', 'renderD128', 'renderD129']:
                device_path = f'/dev/dri/{device}'
                if not os.path.exists(device_path):
                    continue
                
                try:
                    result = subprocess.run(['lsof', device_path], 
                                          capture_output=True, text=True, timeout=2)
                    processes.extend(self.parse_lsof(result.stdout, device))
                except:
                    pass
            
            # Sprawdź akcelerację wideo
            video_processes = self.check_video_acceleration()
            
            self.process_table.setRowCount(len(processes))
            for i, proc in enumerate(processes):
                self.process_table.setItem(i, 0, QTableWidgetItem(str(proc['pid'])))
                self.process_table.setItem(i, 1, QTableWidgetItem(proc['user']))
                self.process_table.setItem(i, 2, QTableWidgetItem(proc['command']))
                self.process_table.setItem(i, 3, QTableWidgetItem(proc['device']))
                self.process_table.setItem(i, 4, QTableWidgetItem(proc['cpu']))
                self.process_table.setItem(i, 5, QTableWidgetItem(proc['mem']))
                
                # Akceleracja wideo
                accel = "Nie"
                if proc['pid'] in video_processes:
                    accel = video_processes[proc['pid']]
                    # Powiadom o nowym procesie używającym akceleracji
                    if proc['pid'] not in self.video_accel_processes:
                        self.video_accel_processes.add(proc['pid'])
                        if DAEMON_CONFIG.get('notify_video_accel', True):
                            self.show_notification(
                                "Akceleracja wideo",
                                f"Proces {proc['command']} (PID: {proc['pid']}) używa {accel}"
                            )
                
                accel_item = QTableWidgetItem(accel)
                if accel != "Nie":
                    accel_item.setBackground(QColor(100, 200, 100))
                self.process_table.setItem(i, 6, accel_item)
            
            if not processes:
                self.process_table.setRowCount(1)
                self.process_table.setItem(0, 2, QTableWidgetItem("Brak procesów używających GPU"))
                
        except Exception as e:
            print(f"Błąd aktualizacji procesów: {e}")
    
    def check_video_acceleration(self):
        """Sprawdź które procesy używają akceleracji wideo"""
        video_processes = {}
        
        try:
            # Sprawdź procesy używające VA-API
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if any(x in cmdline.lower() for x in ['vaapi', 'vdpau', 'ffmpeg', 'mpv', 'vlc', 'chrome', 'firefox']):
                        # Sprawdź biblioteki
                        try:
                            result = subprocess.run(
                                ['lsof', '-p', str(proc.info['pid'])],
                                capture_output=True, text=True, timeout=1
                            )
                            if 'libva' in result.stdout or 'libvdpau' in result.stdout:
                                if 'libva' in result.stdout:
                                    video_processes[str(proc.info['pid'])] = "VA-API"
                                elif 'libvdpau' in result.stdout:
                                    video_processes[str(proc.info['pid'])] = "VDPAU"
                        except:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Błąd sprawdzania akceleracji wideo: {e}")
        
        return video_processes
    
    def parse_lsof(self, output, device):
        """Parsowanie outputu lsof"""
        processes = {}
        lines = output.strip().split('\n')
        
        for line in lines[1:]:
            if not line or 'WARNING' in line:
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[1]
                user = parts[2]
                command = parts[0]
                
                key = f"{pid}_{device}"
                if key in processes:
                    continue
                
                cpu = "N/A"
                mem = "N/A"
                try:
                    ps_result = subprocess.run(
                        ['ps', '-p', pid, '-o', '%cpu=,%mem=,rss='], 
                        capture_output=True, text=True, timeout=1
                    )
                    ps_data = ps_result.stdout.strip().split()
                    if len(ps_data) >= 3:
                        cpu = f"{float(ps_data[0]):.1f}%"
                        mem_kb = int(ps_data[2])
                        mem = f"{mem_kb / 1024:.1f}"
                except:
                    pass
                
                processes[key] = {
                    'pid': pid,
                    'user': user,
                    'command': command,
                    'device': device,
                    'cpu': cpu,
                    'mem': mem
                }
        
        return list(processes.values())
    
    def update_capabilities(self):
        """Aktualizacja możliwości karty"""
        try:
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            glx_output = result.stdout
            
            opengl_text = ""
            
            for line in glx_output.split('\n'):
                if 'OpenGL vendor string:' in line:
                    opengl_text += line + "\n"
                elif 'OpenGL renderer string:' in line:
                    opengl_text += line + "\n"
                elif 'OpenGL version string:' in line:
                    opengl_text += line + "\n"
                elif 'OpenGL shading language version string:' in line:
                    opengl_text += line + "\n"
                elif 'Max core profile version:' in line:
                    opengl_text += "  " + line.strip() + "\n"
                elif 'Max compat profile version:' in line:
                    opengl_text += "  " + line.strip() + "\n"
            
            self.opengl_caps_text.setPlainText(opengl_text)
            
            # Limity
            limits_text = "Limity renderowania:\n\n"
            
            limits_keywords = [
                'GL_MAX_TEXTURE_SIZE',
                'GL_MAX_3D_TEXTURE_SIZE',
                'GL_MAX_CUBE_MAP_TEXTURE_SIZE',
                'GL_MAX_VIEWPORT_DIMS',
                'GL_MAX_RENDERBUFFER_SIZE',
                'GL_MAX_TEXTURE_IMAGE_UNITS',
                'GL_MAX_VERTEX_ATTRIBS',
                'GL_MAX_VARYING_FLOATS',
                'GL_MAX_VERTEX_UNIFORM_COMPONENTS',
                'GL_MAX_FRAGMENT_UNIFORM_COMPONENTS'
            ]
            
            for line in glx_output.split('\n'):
                for keyword in limits_keywords:
                    if keyword in line:
                        clean_line = line.strip()
                        readable = keyword.replace('GL_MAX_', 'Max ').replace('_', ' ').title()
                        if '=' in clean_line:
                            value = clean_line.split('=')[1].strip()
                            limits_text += f"{readable}: {value}\n"
            
            self.limits_text.setPlainText(limits_text)
            
            # Extensions
            extensions_text = "Ważne rozszerzenia:\n\n"
            important_exts = [
                'ARB_framebuffer_object',
                'ARB_vertex_buffer_object',
                'ARB_texture_compression',
                'ARB_shader_objects',
                'EXT_framebuffer_object',
                'EXT_texture_compression_s3tc',
                'NV_',
                'GL_ARB_multisample'
            ]
            
            found_extensions = []
            for line in glx_output.split('\n'):
                if 'GL_' in line:
                    for ext in line.split(','):
                        ext = ext.strip()
                        for important in important_exts:
                            if important in ext and ext not in found_extensions:
                                found_extensions.append(ext)
            
            for ext in sorted(found_extensions[:30]):
                extensions_text += f"  ✓ {ext}\n"
            
            if len(found_extensions) > 30:
                extensions_text += f"\n  ... i {len(found_extensions) - 30} więcej"
            
            self.extensions_text.setPlainText(extensions_text)
            
            self.update_vaapi_table()
            self.check_vdpau()
            
        except Exception as e:
            print(f"Błąd aktualizacji capabilities: {e}")
    
    def update_vaapi_table(self):
        """Aktualizuj tabelę VA-API"""
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
            
            profiles = {}
            
            for line in result.stdout.split('\n'):
                if 'VAProfile' in line and ':' in line:
                    parts = line.split(':')
                    profile = parts[0].strip()
                    entrypoint = parts[1].strip() if len(parts) > 1 else ''
                    
                    if profile not in profiles:
                        profiles[profile] = []
                    if entrypoint:
                        profiles[profile].append(entrypoint)
            
            if 'VAProfileNone' in profiles and len(profiles) == 1:
                profiles = {}
            
            self.vaapi_caps_table.setRowCount(len(profiles))
            
            for i, (profile, entrypoints) in enumerate(sorted(profiles.items())):
                short_profile = profile.replace('VAProfile', '')
                self.vaapi_caps_table.setItem(i, 0, QTableWidgetItem(short_profile))
                
                entrypoints_str = ', '.join(e.replace('VAEntrypoint', '') for e in entrypoints)
                self.vaapi_caps_table.setItem(i, 1, QTableWidgetItem(entrypoints_str))
            
            if not profiles:
                self.vaapi_caps_table.setRowCount(1)
                self.vaapi_caps_table.setItem(0, 0, QTableWidgetItem("Brak wsparcia VA-API"))
                self.vaapi_caps_table.setItem(0, 1, QTableWidgetItem("Zainstaluj libva-utils"))
        
        except Exception as e:
            self.vaapi_caps_table.setRowCount(1)
            self.vaapi_caps_table.setItem(0, 0, QTableWidgetItem("Błąd"))
            self.vaapi_caps_table.setItem(0, 1, QTableWidgetItem(str(e)))
    
    def check_vdpau(self):
        """Sprawdź wsparcie VDPAU"""
        try:
            result = subprocess.run(['vdpauinfo'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Znajdź informacje o urządzeniu
                device_match = re.search(r'Information string: (.*?)\n', result.stdout)
                device = device_match.group(1) if device_match else "Nieznane urządzenie"
                
                # Znajdź obsługiwane funkcje
                features = []
                for line in result.stdout.split('\n'):
                    if 'name' in line and 'description' in line:
                        feature_match = re.search(r'name\s+([^\s]+)\s+description\s+(.+)', line)
                        if feature_match:
                            features.append(f"{feature_match.group(1)}: {feature_match.group(2)}")
                
                vdpau_text = f"✅ VDPAU dostępne\n\n"
                vdpau_text += f"Urządzenie: {device}\n\n"
                vdpau_text += "Obsługiwane funkcje:\n"
                for feature in features[:10]:  # Pokaż tylko pierwsze 10
                    vdpau_text += f"• {feature}\n"
                
                if len(features) > 10:
                    vdpau_text += f"... i {len(features) - 10} więcej"
            else:
                vdpau_text = "❌ VDPAU niedostępne\n\n"
                vdpau_text += "Możliwe przyczyny:\n"
                vdpau_text += "• Brak sterownika VDPAU\n"
                vdpau_text += "• Niezgodna karta graficzna\n"
                vdpau_text += "• Brak biblioteki libvdpau"
            
            self.vdpau_info.setText(vdpau_text)
            
        except FileNotFoundError:
            self.vdpau_info.setText("❌ vdpauinfo nie zainstalowane\n\n"
                                   "Zainstaluj pakiety:\n"
                                   "• Arch: sudo pacman -S libvdpau\n"
                                   "• Ubuntu: sudo apt install libvdpau1")
        except Exception as e:
            self.vdpau_info.setText(f"Błąd sprawdzania VDPAU: {str(e)}")
    
    def update_card_info(self):
        """Aktualizacja informacji o karcie"""
        try:
            info_text = "=== INFORMACJE O KARCIE ===\n\n"
            
            # Podstawowe informacje
            info_text += f"Nazwa: {self.gpu_info['name']}\n"
            info_text += f"ID PCI: {self.gpu_info['pci_id']}\n"
            info_text += f"Chip ID: {self.gpu_info['chip_id']}\n"
            info_text += f"Chip Family: {self.gpu_info['family']}\n"
            info_text += f"VRAM: {self.gpu_info['vram_mb']} MB\n\n"
            
            # Informacje o architekturze
            arch_info = self.get_arch_info()
            info_text += "=== ARCHITEKTURA ===\n"
            info_text += f"Nazwa kodowa: {arch_info['name']}\n"
            info_text += f"Seria: {arch_info['series']}\n"
            info_text += f"Rok produkcji: {arch_info['year']}\n"
            info_text += f"OpenGL: {arch_info['opengl']}\n"
            info_text += f"VA-API: {arch_info['va_api']}\n\n"
            
            # Informacje z lspci
            try:
                result = subprocess.run(['lspci', '-v', '-s', self.gpu_info['pci_id']], 
                                      capture_output=True, text=True, timeout=3)
                lspci_output = result.stdout
                
                info_text += "=== SZCZEGÓŁY PCI ===\n"
                for line in lspci_output.split('\n'):
                    if line.startswith('\t') and ':' in line:
                        info_text += line.strip() + "\n"
                info_text += "\n"
            except:
                info_text += "Nie udało się uzyskać szczegółów PCI\n\n"
            
            # Informacje z dmesg
            try:
                result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=3)
                dmesg_output = result.stdout
                
                info_text += "=== INFORMACJE Z DMESG ===\n"
                for line in dmesg_output.split('\n'):
                    if 'nouveau' in line and self.gpu_info['pci_id'].replace(':', '').replace('.', '') in line:
                        info_text += line + "\n"
                info_text += "\n"
            except:
                info_text += "Nie udało się uzyskać informacji z dmesg\n\n"
            
            # Informacje o module jądra
            try:
                result = subprocess.run(['modinfo', 'nouveau'], 
                                      capture_output=True, text=True, timeout=3)
                modinfo_output = result.stdout
                
                info_text += "=== MODUŁ JĄDRA NOUVEAU ===\n"
                for line in modinfo_output.split('\n'):
                    if line.startswith('version:') or line.startswith('filename:') or line.startswith('depends:'):
                        info_text += line + "\n"
                info_text += "\n"
            except:
                info_text += "Nie udało się uzyskać informacji o module jądra\n\n"
            
            # Informacje o sterowniku X11 (jeśli dostępne)
            if os.environ.get('DISPLAY'):
                try:
                    result = subprocess.run(['xdpyinfo'], capture_output=True, text=True, timeout=3)
                    if 'Nouveau' in result.stdout:
                        info_text += "=== STEROWNIK X11 ===\n"
                        info_text += "Aktywny sterownik: Nouveau\n\n"
                except:
                    pass
            
            # Informacje o Wayland (jeśli dostępne)
            if os.environ.get('WAYLAND_DISPLAY'):
                info_text += "=== WAYLAND ===\n"
                info_text += "Sesja Wayland aktywna\n\n"
            
            self.card_info_text.setPlainText(info_text)
            
        except Exception as e:
            self.card_info_text.setPlainText(f"Błąd pobierania informacji: {str(e)}")
    
    def copy_card_info(self):
        """Kopiuj informacje o karcie do schowka"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.card_info_text.toPlainText())
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Informacje o karcie skopiowane do schowka")
        msg.setWindowTitle("Kopiowanie")
        msg.exec()
    
    def update_codecs(self):
        """Aktualizacja informacji o kodekach - POPRAWIONA"""
        try:
            codecs_text = "=== WSPIERANE KODEKI (VA-API) ===\n\n"
            
            # Sprawdź VA-API
            try:
                result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    codecs_text += "✅ VA-API dostępne\n\n"
                    
                    # Znajdź profile
                    profiles = []
                    for line in result.stdout.split('\n'):
                        if 'VAProfile' in line and ':' in line:
                            profile = line.split(':')[0].strip()
                            profiles.append(profile)
                    
                    if profiles:
                        codecs_text += "Obsługiwane profile:\n"
                        for profile in sorted(profiles):
                            codecs_text += f"• {profile}\n"
                    else:
                        codecs_text += "Nie znaleziono profili VA-API\n"
                else:
                    codecs_text += "❌ VA-API niedostępne\n"
                    codecs_text += f"Błąd: {result.stderr}\n"
            except FileNotFoundError:
                codecs_text += "❌ vainfo nie zainstalowane\n"
            except Exception as e:
                codecs_text += f"Błąd sprawdzania VA-API: {str(e)}\n"
            
            codecs_text += "\n=== WSPIERANE KODEKI (VDPAU) ===\n\n"
            
            # Sprawdź VDPAU
            try:
                result = subprocess.run(['vdpauinfo'], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    codecs_text += "✅ VDPAU dostępne\n\n"
                    
                    # Znajdź obsługiwane funkcje
                    features = []
                    for line in result.stdout.split('\n'):
                        if 'name' in line and 'description' in line:
                            feature_match = re.search(r'name\s+([^\s]+)\s+description\s+(.+)', line)
                            if feature_match:
                                features.append(f"{feature_match.group(1)}: {feature_match.group(2)}")
                    
                    if features:
                        codecs_text += "Obsługiwane funkcje:\n"
                        for feature in features:
                            codecs_text += f"• {feature}\n"
                    else:
                        codecs_text += "Nie znaleziono funkcji VDPAU\n"
                else:
                    codecs_text += "❌ VDPAU niedostępne\n"
                    codecs_text += f"Błąd: {result.stderr}\n"
            except FileNotFoundError:
                codecs_text += "❌ vdpauinfo nie zainstalowane\n"
            except Exception as e:
                codecs_text += f"Błąd sprawdzania VDPAU: {str(e)}\n"
            
            # Dodaj informacje o kodekach dla konkretnej architektury
            arch_info = self.get_arch_info()
            codecs_text += f"\n=== KODEKI DLA ARCHITEKTURY {arch_info['name']} ===\n\n"
            
            if self.gpu_arch == 'NV40':
                codecs_text += "• Brak akceleracji sprzętowej\n"
                codecs_text += "• Tylko dekodowanie programowe\n"
            elif self.gpu_arch == 'NV50':
                codecs_text += "• MPEG2: Tak (VDPAU)\n"
                codecs_text += "• VC1: Tak (VDPAU)\n"
                codecs_text += "• H.264: Ograniczone (VDPAU)\n"
                codecs_text += "• H.265/HEVC: Brak\n"
                codecs_text += "• VP9: Brak\n"
                codecs_text += "• AV1: Brak\n"
                codecs_text += "• VVC/H.266: Brak\n"
            elif self.gpu_arch == 'NVC0':
                codecs_text += "• MPEG2: Tak (VDPAU/VA-API)\n"
                codecs_text += "• VC1: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.264: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.265/HEVC: Brak\n"
                codecs_text += "• VP9: Brak\n"
                codecs_text += "• AV1: Brak\n"
                codecs_text += "• VVC/H.266: Brak\n"
            elif self.gpu_arch == 'NVE0':
                codecs_text += "• MPEG2: Tak (VDPAU/VA-API)\n"
                codecs_text += "• VC1: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.264: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.265/HEVC: Częściowe (VA-API)\n"
                codecs_text += "• VP9: Brak\n"
                codecs_text += "• AV1: Brak\n"
                codecs_text += "• VVC/H.266: Brak\n"
            elif self.gpu_arch in ['GM100', 'GP100', 'GV100']:
                codecs_text += "• MPEG2: Tak (VDPAU/VA-API)\n"
                codecs_text += "• VC1: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.264: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.265/HEVC: Tak (VA-API)\n"
                codecs_text += "• VP9: Tak (VA-API)\n"
                codecs_text += "• AV1: Brak (z wyjątkiem niektórych Ampere)\n"
                codecs_text += "• VVC/H.266: Brak\n"
            elif self.gpu_arch in ['TU100', 'GA100', 'AD100']:
                codecs_text += "• MPEG2: Tak (VDPAU/VA-API)\n"
                codecs_text += "• VC1: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.264: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.265/HEVC: Tak (VA-API)\n"
                codecs_text += "• VP9: Tak (VA-API)\n"
                codecs_text += "• AV1: Tak (VA-API, Ampere+)\n"
                codecs_text += "• VVC/H.266: Brak (wymaga nowszego sprzętu)\n"
            elif self.gpu_arch in ['GB100', 'GB200', 'GH100']:
                codecs_text += "• MPEG2: Tak (VDPAU/VA-API)\n"
                codecs_text += "• VC1: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.264: Tak (VDPAU/VA-API)\n"
                codecs_text += "• H.265/HEVC: Tak (VA-API)\n"
                codecs_text += "• VP9: Tak (VA-API)\n"
                codecs_text += "• AV1: Tak (VA-API)\n"
                codecs_text += "• VVC/H.266: Tak (VA-API, Blackwell 2.0+)\n"
                codecs_text += "• Następna generacja kodeków: Wsparcie planowane\n"
            
            # Dodaj informacje o brakujących kodekach
            codecs_text += "\n=== BRAKUJĄCE KODEKI ===\n\n"
            codecs_text += "• VVC (H.266): Wymaga najnowszych kart (RTX 50+)\n"
            codecs_text += "• AV1: Tylko karty od Turinga wzwyż\n"
            codecs_text += "• HEVC 10-bit: Ograniczone wsparcie\n"
            
            self.codecs_text.setPlainText(codecs_text)
            
        except Exception as e:
            self.codecs_text.setPlainText(f"Błąd sprawdzania kodeków: {str(e)}")


class GPUMonitorDaemon(QObject):
    """Daemon monitorujący GPU w tle"""
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.gpu_info = None
        self.gpu_arch = None
        self.last_user_activity = time.time()
        self.temp_history = deque(maxlen=100)
        self.process_history = {}
        self.nouveau_pci_id = None
        
        # Wczytaj konfigurację
        self.load_config()
        
        # Ustawienie obsługi sygnałów
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def load_config(self):
        """Wczytaj konfigurację daemon"""
        try:
            if os.path.exists(DAEMON_CONFIG['config_file']):
                with open(DAEMON_CONFIG['config_file'], 'r') as f:
                    DAEMON_CONFIG.update(json.load(f))
        except Exception as e:
            self.log(f"Błąd wczytywania konfiguracji: {e}")
    
    def signal_handler(self, signum, frame):
        """Obsługa sygnałów systemowych"""
        self.log(f"Otrzymano sygnał {signum}, zamykanie daemon...")
        self.running = False
    
    def log(self, message):
        """Zapisz log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # Wyślij sygnał do GUI (jeśli aktywne)
        self.log_signal.emit(log_entry)
        
        # Zapisz do pliku
        try:
            with open(DAEMON_CONFIG['log_file'], 'a') as f:
                f.write(log_entry + "\n")
            
            # Ogranicz rozmiar logu
            self.trim_log()
        except Exception as e:
            print(f"Błąd zapisu logu: {e}")
    
    def trim_log(self):
        """Ogranicz rozmiar pliku logu"""
        try:
            if os.path.exists(DAEMON_CONFIG['log_file']):
                with open(DAEMON_CONFIG['log_file'], 'r') as f:
                    lines = f.readlines()
                
                if len(lines) > DAEMON_CONFIG['max_log_entries']:
                    with open(DAEMON_CONFIG['log_file'], 'w') as f:
                        f.writelines(lines[-DAEMON_CONFIG['max_log_entries']:])
        except Exception as e:
            print(f"Błąd przycinania logu: {e}")
    
    def find_nouveau_pci_id(self):
        """Znajdź identyfikator nouveau-pci-XXXX z sensors"""
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            for line in result.stdout.split('\n'):
                if 'nouveau-pci-' in line:
                    match = re.search(r'nouveau-pci-(\d+)', line)
                    if match:
                        return match.group(1)
        except Exception as e:
            self.log(f"Błąd wyszukiwania nouveau-pci: {e}")
        return None
    
    def detect_gpu(self):
        """Wykryj informacje o GPU"""
        info = {
            'name': 'Unknown GPU',
            'pci_id': '00:00.0',
            'chip_id': 'Unknown',
            'family': 'Unknown'
        }
        
        try:
            result = subprocess.run(['lspci', '-nn'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n'):
                if 'NVIDIA' in line and any(x in line for x in ['VGA', '3D', 'Display']):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        info['pci_id'] = parts[0].strip()
                        
                        name_match = re.search(r'NVIDIA Corporation (.*?)(?:\[|\(|$)', line)
                        if name_match:
                            info['name'] = name_match.group(1).strip()
                        
                        id_match = re.search(r'\[10de:([0-9a-f]{4})\]', line)
                        if id_match:
                            info['chip_id'] = id_match.group(1).upper()
                    break
            
            result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=2)
            dmesg = result.stdout
            
            family_match = re.search(r'nouveau.*NVIDIA (NV[0-9A-F]+|G[0-9A-F]+|GT[0-9]+|GF[0-9]+|GK[0-9]+|GM[0-9]+|GP[0-9]+|GV[0-9]+|TU[0-9]+|GA[0-9]+|AD[0-9]+|GB[0-9]+|GH[0-9]+)', dmesg)
            if family_match:
                info['family'] = family_match.group(1)
                
        except Exception as e:
            self.log(f"Błąd wykrywania GPU: {e}")
        
        return info
    
    def detect_architecture(self):
        """Wykryj architekturę GPU"""
        chip_id = self.gpu_info['chip_id']
        family = self.gpu_info['family']
        
        if family in CHIP_DATABASE:
            return CHIP_DATABASE[family]['arch']
        
        # Spróbuj dopasować na podstawie prefiksu
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
            # Sprawdź czy to Blackwell czy Blackwell 2.0
            if len(family) > 3 and family[3] == '2':
                return 'GB200'
            else:
                return 'GB100'
        elif family.startswith('GH'):
            return 'GH100'
        
        # Fallback na podstawie chip ID
        if chip_id:
            chip_num = int(chip_id, 16) if chip_id != 'Unknown' else 0
            
            # Specjalne przypadki dla konkretnych chipów
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
            
            # Ogólne zakresy
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
    
    def get_temperature(self):
        """Pobierz temperaturę GPU - POPRAWIONA"""
        try:
            # Jeśli mamy zidentyfikowany nouveau-pci-XXXX, użyj go bezpośrednio
            if self.nouveau_pci_id:
                result = subprocess.run(['sensors', f'nouveau-pci-{self.nouveau_pci_id}'], 
                                      capture_output=True, text=True, timeout=3)
                
                for line in result.stdout.split('\n'):
                    if 'temp1' in line:
                        temp_match = re.search(r'\+(\d+\.\d+)°C', line)
                        if temp_match:
                            return float(temp_match.group(1))
            
            # Jeśli nie, spróbuj znaleźć w ogólnym outputcie sensors
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=3)
            
            for line in result.stdout.split('\n'):
                if 'nouveau' in line.lower() and 'temp1' in line.lower():
                    temp_match = re.search(r'\+(\d+\.\d+)°C', line)
                    if temp_match:
                        return float(temp_match.group(1))
            
            return None
        except Exception as e:
            self.log(f"Błąd odczytu temperatury: {e}")
            return None
    
    def check_user_activity(self):
        """Sprawdź aktywność użytkownika"""
        try:
            # Sprawdź aktywność myszy i klawiatury
            result = subprocess.run(['xprintidle'], capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                idle_time = int(result.stdout.strip()) / 1000  # Konwersja na sekundy
                if idle_time < DAEMON_CONFIG['user_activity_timeout']:
                    self.last_user_activity = time.time()
                    return True
            else:
                # Alternatywa: sprawdź ostatnią modyfikację plików w /dev/input
                input_devices = ['/dev/input/mice', '/dev/input/event0']
                for device in input_devices:
                    if os.path.exists(device):
                        stat = os.stat(device)
                        if stat.st_mtime > self.last_user_activity:
                            self.last_user_activity = time.time()
                            return True
        except:
            pass
        
        return False
    
    def get_gpu_processes(self):
        """Pobierz procesy używające GPU"""
        processes = []
        
        try:
            for device in ['card0', 'card1', 'card2', 'renderD128', 'renderD129']:
                device_path = f'/dev/dri/{device}'
                if not os.path.exists(device_path):
                    continue
                
                try:
                    result = subprocess.run(['lsof', device_path], 
                                          capture_output=True, text=True, timeout=2)
                    for line in result.stdout.strip().split('\n')[1:]:
                        if line and 'WARNING' not in line:
                            parts = line.split()
                            if len(parts) >= 3:
                                processes.append({
                                    'pid': parts[1],
                                    'user': parts[2],
                                    'command': parts[0],
                                    'device': device
                                })
                except:
                    pass
        except Exception as e:
            self.log(f"Błąd pobierania procesów GPU: {e}")
        
        return processes
    
    def analyze_temperature_trend(self):
        """Analizuj trend temperatury"""
        if len(self.temp_history) < 5:
            return "stable"
        
        recent = list(self.temp_history)[-5:]
        avg_recent = sum(recent) / len(recent)
        older = list(self.temp_history)[-10:-5] if len(self.temp_history) >= 10 else recent[:len(recent)//2]
        avg_older = sum(older) / len(older)
        
        if avg_recent > avg_older + 5:
            return "rising"
        elif avg_recent < avg_older - 5:
            return "falling"
        else:
            return "stable"
    
    def handle_high_temperature(self, temp, processes):
        """Obsługa wysokiej temperatury"""
        threshold = DAEMON_CONFIG['temp_threshold']
        critical = DAEMON_CONFIG['critical_threshold']
        
        if temp >= critical:
            self.log(f"🔥 KRYTYCZNA TEMPERATURA: {temp:.1f}°C")
            
            # Znajdź procesy z wysokim CPU
            dangerous_processes = []
            for proc in processes:
                try:
                    ps_result = subprocess.run(
                        ['ps', '-p', proc['pid'], '-o', '%cpu='],
                        capture_output=True, text=True, timeout=1
                    )
                    cpu = float(ps_result.stdout.strip())
                    if cpu > 50:  # Proces używający >50% CPU
                        dangerous_processes.append((proc, cpu))
                except:
                    pass
            
            if dangerous_processes:
                # Sortuj po CPU
                dangerous_processes.sort(key=lambda x: x[1], reverse=True)
                
                for proc, cpu in dangerous_processes[:3]:  # Top 3
                    self.log(f"Proces podejrzany o przegrzanie: {proc['command']} (PID: {proc['pid']}, CPU: {cpu:.1f}%)")
                    
                    # Sprawdź czy użytkownik jest aktywny
                    user_active = self.check_user_activity()
                    
                    if DAEMON_CONFIG['auto_kill'] or not user_active:
                        self.log(f"Automatyczne zabijanie procesu {proc['command']} (PID: {proc['pid']})")
                        try:
                            os.kill(int(proc['pid']), signal.SIGTERM)
                            time.sleep(2)
                            # Jeśli nadal działa, zabij siłą
                            if psutil.pid_exists(int(proc['pid'])):
                                os.kill(int(proc['pid']), signal.SIGKILL)
                            self.log(f"Proces {proc['command']} zabity")
                        except Exception as e:
                            self.log(f"Błąd zabijania procesu: {e}")
                    else:
                        self.log(f"Użytkownik aktywny, pytanie o zabijanie procesu {proc['command']}")
                        # Tutaj można dodać interaktywne pytanie
        
        elif temp >= threshold:
            trend = self.analyze_temperature_trend()
            if trend == "rising":
                self.log(f"⚠️ WYSOKA TEMPERATURA: {temp:.1f}°C (trend: rosnący)")
                
                # Powiadomienie systemowe
                if NOTIFY_AVAILABLE:
                    try:
                        notification = notify2.Notification(
                            "Nouveau GPU Monitor",
                            f"Wysoka temperatura GPU: {temp:.1f}°C"
                        )
                        notification.set_urgency(notify2.URGENCY_CRITICAL)
                        notification.show()
                    except:
                        pass
    
    def run(self):
        """Główna pętla daemon"""
        self.running = True
        self.log("Daemon Nouveau GPU Monitor uruchomiony")
        
        # Wykryj GPU
        self.gpu_info = self.detect_gpu()
        self.gpu_arch = self.detect_architecture()
        self.nouveau_pci_id = self.find_nouveau_pci_id()
        
        self.log(f"Wykryto GPU: {self.gpu_info['name']} ({self.gpu_arch})")
        
        while self.running:
            try:
                # Pobierz temperaturę
                temp = self.get_temperature()
                if temp is not None:
                    self.temp_history.append(temp)
                    
                    # Sprawdź progi
                    if temp >= DAEMON_CONFIG['temp_threshold']:
                        processes = self.get_gpu_processes()
                        self.handle_high_temperature(temp, processes)
                
                # Sprawdź procesy używające akceleracji wideo
                if DAEMON_CONFIG.get('notify_video_accel', True):
                    self.check_video_acceleration()
                
                # Czekaj
                time.sleep(DAEMON_CONFIG['check_interval'])
                
            except Exception as e:
                self.log(f"Błąd w pętli daemon: {e}")
                time.sleep(5)
        
        self.log("Daemon zatrzymany")
    
    def check_video_acceleration(self):
        """Sprawdź procesy używające akceleracji wideo"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if any(x in cmdline.lower() for x in ['vaapi', 'vdpau', 'ffmpeg', 'mpv', 'vlc']):
                        # Sprawdź biblioteki
                        result = subprocess.run(
                            ['lsof', '-p', str(proc.info['pid'])],
                            capture_output=True, text=True, timeout=1
                        )
                        if 'libva' in result.stdout or 'libvdpau' in result.stdout:
                            accel_type = "VA-API" if 'libva' in result.stdout else "VDPAU"
                            key = f"{proc.info['pid']}_{accel_type}"
                            
                            if key not in self.process_history:
                                self.process_history[key] = time.time()
                                self.log(f"Akceleracja wideo: {proc.info['name']} (PID: {proc.info['pid']}) używa {accel_type}")
                                
                                # Powiadomienie
                                if NOTIFY_AVAILABLE:
                                    try:
                                        notification = notify2.Notification(
                                            "Akceleracja wideo",
                                            f"{proc.info['name']} używa {accel_type}"
                                        )
                                        notification.set_urgency(notify2.URGENCY_NORMAL)
                                        notification.show()
                                    except:
                                        pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.log(f"Błąd sprawdzania akceleracji wideo: {e}")


def main():
    parser = argparse.ArgumentParser(description='Nouveau GPU Monitor')
    parser.add_argument('--daemon', action='store_true', help='Uruchom w trybie daemon')
    args = parser.parse_args()
    
    if args.daemon:
        # Tryb daemon
        daemon = GPUMonitorDaemon()
        daemon.run()
    else:
        # Tryb GUI
        app = QApplication(sys.argv)
        
        # Ustaw styl aplikacji
        app.setStyle('Fusion')
        
        # Ustaw ciemny motyw
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        app.setPalette(palette)
        
        monitor = GPUMonitor()
        monitor.show()
        
        sys.exit(app.exec())


if __name__ == "__main__":
    main()