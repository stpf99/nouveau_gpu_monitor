#!/usr/bin/env python3
"""
Nouveau GPU Monitor - Aplikacja do monitorowania kart NVIDIA z sterownikiem Nouveau
Wymagania: PyQt6, PyQt6-Charts
Instalacja: pip install PyQt6 PyQt6-Charts
"""

import sys
import os
import subprocess
import re
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QTabWidget, QTableWidget, 
                             QTableWidgetItem, QGroupBox, QProgressBar, QTextEdit,
                             QHeaderView, QPushButton, QMessageBox)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

class GPUMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nouveau GPU Monitor")
        self.setMinimumSize(1100, 750)
        
        # Historia temperatur dla wykresu
        self.temp_history = []
        self.max_history = 60
        
        # Cache dla informacji o karcie
        self.gpu_info = self.detect_gpu()
        
        self.init_ui()
        
        # Timer do odświeżania co 2 sekundy
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)
        
        # Pierwsze odświeżenie
        self.update_data()
    
    def detect_gpu(self):
        """Wykryj informacje o GPU przy starcie"""
        info = {
            'name': 'Unknown GPU',
            'pci_id': '00:00.0',
            'vram_mb': 0,
            'driver': 'nouveau'
        }
        
        try:
            # Znajdź kartę NVIDIA w lspci
            result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n'):
                if 'NVIDIA' in line and any(x in line for x in ['VGA', '3D', 'Display']):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        info['pci_id'] = parts[0].strip()
                        # Wyciągnij nazwę GPU
                        name_match = re.search(r'NVIDIA Corporation (.*?)(?:\(|$)', line)
                        if name_match:
                            info['name'] = name_match.group(1).strip()
                    break
            
            # Sprawdź VRAM z dmesg
            result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=2)
            vram_match = re.search(r'nouveau.*VRAM:\s*(\d+)\s*MiB', result.stdout)
            if vram_match:
                info['vram_mb'] = int(vram_match.group(1))
            else:
                # Spróbuj z glxinfo
                result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
                vram_match = re.search(r'Dedicated video memory:\s*(\d+)\s*MB', result.stdout)
                if vram_match:
                    info['vram_mb'] = int(vram_match.group(1))
                    
        except Exception as e:
            print(f"Błąd wykrywania GPU: {e}")
        
        return info
    
    def init_ui(self):
        """Inicjalizacja interfejsu użytkownika"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Header z nazwą GPU
        header = QLabel(f"🖥️  {self.gpu_info['name']}  |  VRAM: {self.gpu_info['vram_mb']} MB")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("padding: 10px; background-color: #2a2a2a; border-radius: 5px;")
        main_layout.addWidget(header)
        
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
        
        # Status bar z czasem ostatniego odświeżenia
        self.last_update_label = QLabel()
        self.statusBar().addPermanentWidget(self.last_update_label)
        self.statusBar().showMessage("Nouveau GPU Monitor v1.0")
    
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
        
        vram_note = QLabel("⚠️ Nouveau: ograniczone dane")
        vram_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vram_note.setStyleSheet("color: #888; font-size: 10px;")
        vram_layout.addWidget(vram_note)
        
        vram_group.setLayout(vram_layout)
        top_layout.addWidget(vram_group, 1)
        
        layout.addLayout(top_layout)
        
        # Clock info (jeśli dostępne)
        clock_group = QGroupBox("⚡ Częstotliwości")
        clock_layout = QHBoxLayout()
        
        self.gpu_clock_label = QLabel("GPU: N/A")
        self.mem_clock_label = QLabel("VRAM: N/A")
        clock_layout.addWidget(self.gpu_clock_label)
        clock_layout.addWidget(self.mem_clock_label)
        
        clock_note = QLabel("Nouveau nie eksponuje informacji o zegarach")
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
        axis_x.setRange(0, self.max_history)
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
        from PyQt6.QtGui import QPainter
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
        toolbar.addWidget(info_label)
        
        refresh_btn = QPushButton("🔄 Odśwież")
        refresh_btn.clicked.connect(self.update_processes)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Tabela procesów
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(6)
        self.process_table.setHorizontalHeaderLabels(["PID", "Użytkownik", "Polecenie", "Device", "CPU %", "RAM (MB)"])
        
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.process_table.setAlternatingRowColors(True)
        self.process_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.process_table)
        
        # Informacja o ograniczeniach
        note = QLabel(
            "⚠️ <b>Ograniczenia Nouveau:</b><br>"
            "• Brak informacji o użyciu GPU per proces<br>"
            "• Brak informacji o użyciu VRAM per proces<br>"
            "• Dla pełnego monitoringu rozważ sterownik nvidia-390xx"
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
        from PyQt6.QtWidgets import QScrollArea
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
        info_label = QLabel("Wsparcie kodowania/dekodowania wideo (VA-API)")
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
    
    def update_data(self):
        """Aktualizacja wszystkich danych"""
        self.update_temperature()
        self.update_vram()
        self.update_processes()
        self.update_capabilities()
        
        # Aktualizuj timestamp
        now = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.setText(f"Ostatnia aktualizacja: {now}")
    
    def update_temperature(self):
        """Aktualizacja temperatury GPU"""
        try:
            hwmon_path = self.find_hwmon_path()
            
            if hwmon_path:
                # Temperatura aktualna
                with open(os.path.join(hwmon_path, "temp1_input"), 'r') as f:
                    temp = int(f.read().strip()) / 1000.0
                
                self.temp_label.setText(f"{temp:.1f}°C")
                self.temp_bar.setValue(int(temp))
                
                # Temperatura max
                try:
                    with open(os.path.join(hwmon_path, "temp1_max"), 'r') as f:
                        temp_max = int(f.read().strip()) / 1000.0
                        self.temp_max_label.setText(f"Max: {temp_max:.0f}°C")
                except:
                    self.temp_max_label.setText("Max: N/A")
                
                # Temperatura krytyczna
                try:
                    with open(os.path.join(hwmon_path, "temp1_crit"), 'r') as f:
                        temp_crit = int(f.read().strip()) / 1000.0
                        self.temp_crit_label.setText(f"Crit: {temp_crit:.0f}°C")
                except:
                    self.temp_crit_label.setText("Crit: N/A")
                
                # Kolorowanie
                if temp < 70:
                    self.temp_status.setText("✅ Status: Temperatura OK")
                    self.temp_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    self.temp_bar.setStyleSheet(self.temp_bar.styleSheet().replace("#4CAF50", "#4CAF50"))
                elif temp < 85:
                    self.temp_status.setText("⚠️ Status: Temperatura podwyższona")
                    self.temp_status.setStyleSheet("color: #FF9800; font-weight: bold;")
                    self.temp_bar.setStyleSheet(self.temp_bar.styleSheet().replace("#4CAF50", "#FF9800"))
                else:
                    self.temp_status.setText("🔥 Status: WYSOKA TEMPERATURA!")
                    self.temp_status.setStyleSheet("color: #F44336; font-weight: bold;")
                    self.temp_bar.setStyleSheet(self.temp_bar.styleSheet().replace("#4CAF50", "#F44336"))
                
                # Historia
                self.temp_history.append(temp)
                if len(self.temp_history) > self.max_history:
                    self.temp_history.pop(0)
                
                # Aktualizuj wykres
                self.temp_series.clear()
                for i, t in enumerate(self.temp_history):
                    self.temp_series.append(i * 2, t)  # * 2 bo co 2 sekundy
                
                # Dostosuj zakres Y do danych
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
    
    def update_vram(self):
        """Aktualizacja informacji o VRAM"""
        try:
            # Spróbuj glxinfo dla aktualnego użycia
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            
            # Dedicated video memory (total)
            total_match = re.search(r'Dedicated video memory:\s*(\d+)\s*MB', result.stdout)
            if total_match:
                total = int(total_match.group(1))
                self.vram_total_label.setText(f"Total: {total} MB")
            
            # Currently available
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
    
    def update_capabilities(self):
        """Aktualizacja możliwości karty"""
        try:
            # OpenGL Capabilities
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            glx_output = result.stdout
            
            opengl_text = ""
            
            # Podstawowe info
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
            
            # OpenGL Limits
            limits_text = "Limity renderowania:\n\n"
            
            # Używamy glxinfo do wyciągnięcia limitów
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
                        # Wyczyść formatowanie
                        clean_line = line.strip()
                        # Zamień GL_MAX na bardziej czytelną formę
                        readable = keyword.replace('GL_MAX_', 'Max ').replace('_', ' ').title()
                        # Wyciągnij wartość
                        if '=' in clean_line:
                            value = clean_line.split('=')[1].strip()
                            limits_text += f"{readable}: {value}\n"
            
            self.limits_text.setPlainText(limits_text)
            
            # Extensions - tylko ważne
            extensions_text = "Ważne rozszerzenia:\n\n"
            important_exts = [
                'ARB_framebuffer_object',
                'ARB_vertex_buffer_object',
                'ARB_texture_compression',
                'ARB_shader_objects',
                'EXT_framebuffer_object',
                'EXT_texture_compression_s3tc',
                'NV_',  # NVIDIA-specific
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
            
            for ext in sorted(found_extensions[:30]):  # Limit do 30
                extensions_text += f"  ✓ {ext}\n"
            
            if len(found_extensions) > 30:
                extensions_text += f"\n  ... i {len(found_extensions) - 30} więcej"
            
            self.extensions_text.setPlainText(extensions_text)
            
            # VA-API Capabilities
            self.update_vaapi_table()
            
            # VDPAU Info
            self.check_vdpau()
            
        except Exception as e:
            print(f"Błąd aktualizacji capabilities: {e}")
    
    def update_vaapi_table(self):
        """Aktualizuj tabelę VA-API"""
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
            
            profiles = {}
            current_profile = None
            
            for line in result.stdout.split('\n'):
                if 'VAProfile' in line and ':' in line:
                    parts = line.split(':')
                    profile = parts[0].strip()
                    entrypoint = parts[1].strip() if len(parts) > 1 else ''
                    
                    if profile not in profiles:
                        profiles[profile] = []
                    if entrypoint:
                        profiles[profile].append(entrypoint)
            
            # Usuń VAProfileNone jeśli tylko on jest
            if 'VAProfileNone' in profiles and len(profiles) == 1:
                profiles = {}
            
            self.vaapi_caps_table.setRowCount(len(profiles))
            
            for i, (profile, entrypoints) in enumerate(sorted(profiles.items())):
                # Skróć nazwę profilu dla lepszej czytelności
                short_profile = profile.replace('VAProfile', '')
                self.vaapi_caps_table.setItem(i, 0, QTableWidgetItem(short_profile))
                
                entrypoints_str = ', '.join(e.replace('VAEntrypoint', '') for e in entrypoints)
                self.vaapi_caps_table.setItem(i, 1, QTableWidgetItem(entrypoints_str))
            
            if not profiles:
                self.vaapi_caps_table.setRowCount(1)
                self.vaapi_caps_table.setItem(0, 0, QTableWidgetItem("Brak wsparcia VA-API"))
                self.vaapi_caps_table.setItem(0, 1, QTableWidgetItem("N/A"))
                
        except FileNotFoundError:
            self.vaapi_caps_table.setRowCount(1)
            self.vaapi_caps_table.setItem(0, 0, QTableWidgetItem("vainfo nie zainstalowane"))
            self.vaapi_caps_table.setItem(0, 1, QTableWidgetItem("Zainstaluj: libva-utils"))
        except Exception as e:
            print(f"Błąd VA-API: {e}")
    
    def check_vdpau(self):
        """Sprawdź wsparcie VDPAU"""
        try:
            result = subprocess.run(['vdpauinfo'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Zlicz profile decoder/video mixer
                decoder_count = result.stdout.count('is supported')
                
                info_text = f"✅ <b>VDPAU dostępne</b><br><br>"
                
                # Wyciągnij podstawowe info
                for line in result.stdout.split('\n'):
                    if 'display:' in line.lower():
                        info_text += line.strip() + "<br>"
                    elif 'API version:' in line:
                        info_text += line.strip() + "<br>"
                    elif 'Information string:' in line:
                        info_text += line.strip() + "<br>"
                
                info_text += f"<br>Wspieranych profili: {decoder_count}"
                
                self.vdpau_info.setText(info_text)
            else:
                self.vdpau_info.setText("❌ VDPAU niedostępne lub nie działa")
                
        except FileNotFoundError:
            self.vdpau_info.setText(
                "⚠️ <b>vdpauinfo nie zainstalowane</b><br><br>"
                "VDPAU może działać lepiej niż VA-API na Nouveau<br><br>"
                "Instalacja:<br>"
                "• Arch/CachyOS: <code>sudo pacman -S libvdpau vdpauinfo</code><br>"
                "• Debian/Ubuntu: <code>sudo apt install vdpauinfo</code>"
            )
        except Exception as e:
            self.vdpau_info.setText(f"❌ Błąd: {str(e)}")
    
    def update_processes(self):
        """Aktualizacja listy procesów"""
        try:
            processes = []
            
            # Sprawdź wszystkie urządzenia DRM
            for device in ['card0', 'card1', 'renderD128', 'renderD129']:
                device_path = f'/dev/dri/{device}'
                if not os.path.exists(device_path):
                    continue
                
                try:
                    result = subprocess.run(['lsof', device_path], 
                                          capture_output=True, text=True, timeout=2)
                    processes.extend(self.parse_lsof(result.stdout, device))
                except:
                    pass
            
            # Aktualizuj tabelę
            self.process_table.setRowCount(len(processes))
            for i, proc in enumerate(processes):
                self.process_table.setItem(i, 0, QTableWidgetItem(str(proc['pid'])))
                self.process_table.setItem(i, 1, QTableWidgetItem(proc['user']))
                self.process_table.setItem(i, 2, QTableWidgetItem(proc['command']))
                self.process_table.setItem(i, 3, QTableWidgetItem(proc['device']))
                self.process_table.setItem(i, 4, QTableWidgetItem(proc['cpu']))
                self.process_table.setItem(i, 5, QTableWidgetItem(proc['mem']))
            
            if not processes:
                self.process_table.setRowCount(1)
                self.process_table.setItem(0, 2, QTableWidgetItem("Brak procesów używających GPU"))
                
        except Exception as e:
            print(f"Błąd aktualizacji procesów: {e}")
    
    def parse_lsof(self, output, device):
        """Parsowanie outputu lsof"""
        processes = {}  # Użyj dict zamiast listy, żeby uniknąć duplikatów
        lines = output.strip().split('\n')
        
        for line in lines[1:]:
            if not line or 'WARNING' in line:
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[1]
                user = parts[2]
                command = parts[0]
                
                # Pomiń duplikaty - ten sam PID na tym samym device
                key = f"{pid}_{device}"
                if key in processes:
                    continue
                
                # Pobierz CPU i RAM z ps
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
    
    def update_card_info(self):
        """Aktualizacja informacji o karcie"""
        info_text = f"{'='*70}\n"
        info_text += "  INFORMACJE O KARCIE GRAFICZNEJ\n"
        info_text += f"{'='*70}\n\n"
        
        try:
            # Podstawowe info
            info_text += f"Nazwa: {self.gpu_info['name']}\n"
            info_text += f"PCI ID: {self.gpu_info['pci_id']}\n"
            info_text += f"VRAM: {self.gpu_info['vram_mb']} MB\n"
            info_text += f"Sterownik: {self.gpu_info['driver']}\n\n"
            
            # lspci szczegóły
            info_text += f"{'-'*70}\n"
            info_text += "SZCZEGÓŁY LSPCI\n"
            info_text += f"{'-'*70}\n"
            result = subprocess.run(['lspci', '-v', '-s', self.gpu_info['pci_id']], 
                                  capture_output=True, text=True, timeout=2)
            info_text += result.stdout + "\n"
            
            # OpenGL info
            info_text += f"{'-'*70}\n"
            info_text += "INFORMACJE OPENGL\n"
            info_text += f"{'-'*70}\n"
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            
            for line in result.stdout.split('\n'):
                if any(kw in line.lower() for kw in ['opengl', 'renderer', 'vendor', 
                                                       'version', 'memory', 'profile']):
                    info_text += line + "\n"
            
            # Informacje o sterowniku
            info_text += f"\n{'-'*70}\n"
            info_text += "INFORMACJE O STEROWNIKU NOUVEAU\n"
            info_text += f"{'-'*70}\n"
            result = subprocess.run(['modinfo', 'nouveau'], 
                                  capture_output=True, text=True, timeout=2)
            
            for line in result.stdout.split('\n')[:15]:
                info_text += line + "\n"
            
            # Parametry modułu
            info_text += f"\n{'-'*70}\n"
            info_text += "AKTYWNE PARAMETRY MODUŁU\n"
            info_text += f"{'-'*70}\n"
            
            params_path = "/sys/module/nouveau/parameters/"
            if os.path.exists(params_path):
                for param in sorted(os.listdir(params_path)):
                    try:
                        with open(os.path.join(params_path, param), 'r') as f:
                            value = f.read().strip()
                            info_text += f"{param}: {value}\n"
                    except:
                        pass
            
        except Exception as e:
            info_text += f"\n\nBŁĄD: {str(e)}\n"
        
        self.card_info_text.setPlainText(info_text)
    
    def update_codecs(self):
        """Aktualizacja informacji o kodekach"""
        codec_text = f"{'='*70}\n"
        codec_text += "  WSPARCIE AKCELERACJI WIDEO (VA-API)\n"
        codec_text += f"{'='*70}\n\n"
        
        try:
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
            codec_text += result.stdout
            
            if result.returncode != 0 or "error" in result.stderr.lower():
                codec_text += f"\n\n{'-'*70}\n"
                codec_text += "STDERR:\n"
                codec_text += result.stderr
            
            # Analiza wsparcia
            codec_text += f"\n\n{'-'*70}\n"
            codec_text += "ANALIZA WSPARCIA\n"
            codec_text += f"{'-'*70}\n"
            
            if "VAProfileNone" in result.stdout:
                codec_text += "\n✓ VideoProc (przetwarzanie wideo) dostępne\n"
            
            profiles = re.findall(r'VAProfile\w+', result.stdout)
            if profiles:
                codec_text += f"\n✓ Wykryto {len(set(profiles))} profili:\n"
                for profile in sorted(set(profiles)):
                    codec_text += f"  • {profile}\n"
            
        except FileNotFoundError:
            codec_text += "❌ vainfo nie jest zainstalowane\n\n"
            codec_text += "Aby zainstalować:\n"
            codec_text += "  • Arch/CachyOS: sudo pacman -S libva-utils\n"
            codec_text += "  • Debian/Ubuntu: sudo apt install vainfo\n"
            codec_text += "  • Fedora: sudo dnf install libva-utils\n\n"
            
            codec_text += f"{'-'*70}\n"
            codec_text += "UWAGI DLA NOUVEAU\n"
            codec_text += f"{'-'*70}\n"
            codec_text += "• Nouveau ma bardzo ograniczone wsparcie VA-API\n"
            codec_text += "• GeForce 8xxx (G98) nie wspiera VA-API przez Nouveau\n"
            codec_text += "• Dla pełnej akceleracji wideo rozważ sterownik nvidia-390xx\n"
            codec_text += "• VDPAU może działać lepiej niż VA-API na Nouveau\n"
            
        except Exception as e:
            codec_text += f"❌ BŁĄD: {str(e)}\n"
        
        self.codecs_text.setPlainText(codec_text)
    
    def find_hwmon_path(self):
        """Znajdź ścieżkę do hwmon dla nouveau"""
        try:
            # Sprawdź card0
            drm_path = "/sys/class/drm/card0/device/hwmon/"
            if os.path.exists(drm_path):
                for hwmon_dir in os.listdir(drm_path):
                    temp_file = os.path.join(drm_path, hwmon_dir, "temp1_input")
                    if os.path.exists(temp_file):
                        return os.path.join(drm_path, hwmon_dir)
            
            # Sprawdź card1
            drm_path = "/sys/class/drm/card1/device/hwmon/"
            if os.path.exists(drm_path):
                for hwmon_dir in os.listdir(drm_path):
                    temp_file = os.path.join(drm_path, hwmon_dir, "temp1_input")
                    if os.path.exists(temp_file):
                        return os.path.join(drm_path, hwmon_dir)
            
        except Exception as e:
            print(f"Błąd szukania hwmon: {e}")
        
        return None
    
    def copy_card_info(self):
        """Kopiuj informacje o karcie do schowka"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.card_info_text.toPlainText())
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Informacje skopiowane do schowka!")
        msg.setWindowTitle("Skopiowano")
        msg.exec()

def main():
    app = QApplication(sys.argv)
    
    # Ciemny motyw
    app.setStyle("Fusion")
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    
    app.setPalette(dark_palette)
    
    # Dodatkowe style dla lepszego wyglądu
    app.setStyleSheet("""
        QGroupBox {
            border: 2px solid #555;
            border-radius: 5px;
            margin-top: 1ex;
            font-weight: bold;
            padding: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #555;
            border: 1px solid #777;
            padding: 5px 15px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #666;
        }
        QPushButton:pressed {
            background-color: #444;
        }
        QTabWidget::pane {
            border: 1px solid #555;
            border-radius: 3px;
        }
        QTabBar::tab {
            background-color: #555;
            border: 1px solid #777;
            padding: 8px 20px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #2a82da;
        }
        QTabBar::tab:hover {
            background-color: #666;
        }
        QTableWidget {
            gridline-color: #555;
            border: 1px solid #555;
        }
        QHeaderView::section {
            background-color: #555;
            padding: 5px;
            border: 1px solid #777;
            font-weight: bold;
        }
    """)
    
    # Sprawdź czy jest root dla niektórych operacji
    if os.geteuid() != 0:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText("Aplikacja nie działa z uprawnieniami root")
        msg.setInformativeText(
            "Niektóre informacje (np. lista procesów GPU) mogą być niepełne.\n\n"
            "Aby uzyskać pełny dostęp, uruchom:\n"
            "sudo python3 nouveau_monitor.py"
        )
        msg.setWindowTitle("Brak uprawnień root")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        # Nie blokuj - pokaż tylko ostrzeżenie
        msg.show()
    
    window = GPUMonitor()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()