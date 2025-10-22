import sys
import os
import subprocess
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QTabWidget, QTableWidget, 
                             QTableWidgetItem, QGroupBox, QProgressBar, QTextEdit,
                             QHeaderView, QFrame)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

class GPUMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nouveau GPU Monitor")
        self.setMinimumSize(1000, 700)
        
        # Historia temperatur dla wykresu
        self.temp_history = []
        self.max_history = 60
        
        self.init_ui()
        
        # Timer do odświeżania co 2 sekundy
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)
        
        # Pierwsze odświeżenie
        self.update_data()
    
    def init_ui(self):
        """Inicjalizacja interfejsu użytkownika"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: Przegląd
        tabs.addTab(self.create_overview_tab(), "Przegląd")
        
        # Tab 2: Procesy
        tabs.addTab(self.create_processes_tab(), "Procesy GPU")
        
        # Tab 3: Informacje o karcie
        tabs.addTab(self.create_card_info_tab(), "Informacje")
        
        # Tab 4: Kodeki
        tabs.addTab(self.create_codecs_tab(), "Kodeki")
        
        # Status bar
        self.statusBar().showMessage("Nouveau GPU Monitor - Gotowy")
    
    def create_overview_tab(self):
        """Tab z przeglądem GPU"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Górna sekcja - temperatura i podstawowe info
        top_layout = QHBoxLayout()
        
        # Temperatura
        temp_group = QGroupBox("Temperatura GPU")
        temp_layout = QVBoxLayout()
        self.temp_label = QLabel("--°C")
        self.temp_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.temp_label)
        
        self.temp_bar = QProgressBar()
        self.temp_bar.setMaximum(135)
        self.temp_bar.setFormat("%v°C")
        temp_layout.addWidget(self.temp_bar)
        
        self.temp_status = QLabel("Status: OK")
        self.temp_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.temp_status)
        
        temp_group.setLayout(temp_layout)
        top_layout.addWidget(temp_group)
        
        # VRAM Info
        vram_group = QGroupBox("VRAM")
        vram_layout = QVBoxLayout()
        self.vram_total_label = QLabel("Total: -- MB")
        self.vram_total_label.setFont(QFont("Arial", 14))
        vram_layout.addWidget(self.vram_total_label)
        
        self.vram_info = QLabel("Nouveau nie eksponuje\nużycia VRAM")
        self.vram_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vram_info.setStyleSheet("color: #888;")
        vram_layout.addWidget(self.vram_info)
        
        vram_group.setLayout(vram_layout)
        top_layout.addWidget(vram_group)
        
        layout.addLayout(top_layout)
        
        # Wykres temperatury
        chart_group = QGroupBox("Historia temperatury")
        chart_layout = QVBoxLayout()
        
        self.temp_series = QLineSeries()
        self.temp_chart = QChart()
        self.temp_chart.addSeries(self.temp_series)
        self.temp_chart.setTitle("Temperatura w czasie")
        self.temp_chart.legend().hide()
        
        axis_x = QValueAxis()
        axis_x.setTitleText("Czas (s)")
        axis_x.setRange(0, self.max_history)
        
        axis_y = QValueAxis()
        axis_y.setTitleText("Temperatura (°C)")
        axis_y.setRange(0, 100)
        
        self.temp_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        self.temp_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        self.temp_series.attachAxis(axis_x)
        self.temp_series.attachAxis(axis_y)
        
        chart_view = QChartView(self.temp_chart)

        chart_layout.addWidget(chart_view)
        
        chart_group.setLayout(chart_layout)
        layout.addWidget(chart_group)
        
        return widget
    
    def create_processes_tab(self):
        """Tab z procesami używającymi GPU"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info_label = QLabel("Procesy używające GPU przez DRM (Direct Rendering Manager)")
        layout.addWidget(info_label)
        
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(5)
        self.process_table.setHorizontalHeaderLabels(["PID", "Użytkownik", "Polecenie", "Device", "CPU %"])
        self.process_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.process_table)
        
        note = QLabel("⚠️ Nouveau nie eksponuje obciążenia GPU per proces. "
                     "Dla szczegółowego monitoringu rozważ sterownik nvidia-390xx.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(note)
        
        return widget
    
    def create_card_info_tab(self):
        """Tab z informacjami o karcie"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.card_info_text = QTextEdit()
        self.card_info_text.setReadOnly(True)
        self.card_info_text.setFont(QFont("Monospace", 10))
        layout.addWidget(self.card_info_text)
        
        return widget
    
    def create_codecs_tab(self):
        """Tab z informacjami o kodekach"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info_label = QLabel("Wsparcie kodowania/dekodowania wideo (VA-API)")
        info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(info_label)
        
        self.codecs_text = QTextEdit()
        self.codecs_text.setReadOnly(True)
        self.codecs_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.codecs_text)
        
        return widget
    
    def update_data(self):
        """Aktualizacja wszystkich danych"""
        self.update_temperature()
        self.update_vram()
        self.update_processes()
        self.update_card_info()
        self.update_codecs()
    
    def update_temperature(self):
        """Aktualizacja temperatury GPU"""
        try:
            # Szukaj hwmon dla nouveau
            hwmon_path = None
            drm_path = "/sys/class/drm/card0/device/hwmon/"
            
            if os.path.exists(drm_path):
                for hwmon_dir in os.listdir(drm_path):
                    temp_file = os.path.join(drm_path, hwmon_dir, "temp1_input")
                    if os.path.exists(temp_file):
                        hwmon_path = temp_file
                        break
            
            if hwmon_path:
                with open(hwmon_path, 'r') as f:
                    temp_millidegrees = int(f.read().strip())
                    temp = temp_millidegrees / 1000.0
                
                self.temp_label.setText(f"{temp:.1f}°C")
                self.temp_bar.setValue(int(temp))
                
                # Kolorowanie według temperatury
                if temp < 70:
                    self.temp_status.setText("Status: OK")
                    self.temp_status.setStyleSheet("color: green;")
                elif temp < 85:
                    self.temp_status.setText("Status: Ciepło")
                    self.temp_status.setStyleSheet("color: orange;")
                else:
                    self.temp_status.setText("Status: Gorąco!")
                    self.temp_status.setStyleSheet("color: red;")
                
                # Dodaj do historii
                self.temp_history.append(temp)
                if len(self.temp_history) > self.max_history:
                    self.temp_history.pop(0)
                
                # Aktualizuj wykres
                self.temp_series.clear()
                for i, t in enumerate(self.temp_history):
                    self.temp_series.append(i, t)
                
            else:
                self.temp_label.setText("N/A")
                self.temp_status.setText("Brak sensora temperatury")
                
        except Exception as e:
            self.temp_label.setText("ERROR")
            self.temp_status.setText(f"Błąd: {str(e)}")
    
    def update_vram(self):
        """Aktualizacja informacji o VRAM"""
        try:
            # Sprawdź dmesg dla informacji o VRAM
            result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=2)
            dmesg_output = result.stdout
            
            # Szukaj linii z nouveau i VRAM
            vram_match = re.search(r'nouveau.*VRAM:\s*(\d+)\s*MiB', dmesg_output)
            if vram_match:
                vram_mb = vram_match.group(1)
                self.vram_total_label.setText(f"Total: {vram_mb} MB")
            else:
                self.vram_total_label.setText("Total: Nieznane")
                
        except Exception as e:
            self.vram_total_label.setText(f"Błąd: {str(e)}")
    
    def update_processes(self):
        """Aktualizacja listy procesów"""
        try:
            # Sprawdź procesy używające /dev/dri
            processes = []
            
            # card0
            try:
                result = subprocess.run(['lsof', '/dev/dri/card0'], 
                                      capture_output=True, text=True, timeout=2)
                processes.extend(self.parse_lsof(result.stdout, 'card0'))
            except:
                pass
            
            # renderD128
            try:
                result = subprocess.run(['lsof', '/dev/dri/renderD128'], 
                                      capture_output=True, text=True, timeout=2)
                processes.extend(self.parse_lsof(result.stdout, 'renderD128'))
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
                
        except Exception as e:
            pass
    
    def parse_lsof(self, output, device):
        """Parsowanie outputu lsof"""
        processes = []
        lines = output.strip().split('\n')
        
        for line in lines[1:]:  # Pomiń nagłówek
            if not line or 'WARNING' in line:
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[1]
                user = parts[2]
                command = parts[0]
                
                # Pobierz CPU usage z ps
                cpu = "N/A"
                try:
                    ps_result = subprocess.run(['ps', '-p', pid, '-o', '%cpu='], 
                                              capture_output=True, text=True, timeout=1)
                    cpu = ps_result.stdout.strip() + "%"
                except:
                    pass
                
                processes.append({
                    'pid': pid,
                    'user': user,
                    'command': command,
                    'device': device,
                    'cpu': cpu
                })
        
        return processes
    
    def update_card_info(self):
        """Aktualizacja informacji o karcie"""
        info_text = "=== Informacje o karcie graficznej ===\n\n"
        
        try:
            # lspci info
            result = subprocess.run(['lspci', '-v', '-s', self.find_gpu_pci_id()], 
                                  capture_output=True, text=True, timeout=2)
            info_text += "--- lspci ---\n" + result.stdout + "\n\n"
            
            # glxinfo
            result = subprocess.run(['glxinfo'], capture_output=True, text=True, timeout=3)
            glx_output = result.stdout
            
            info_text += "--- OpenGL Info ---\n"
            for line in glx_output.split('\n'):
                if any(keyword in line.lower() for keyword in ['opengl', 'renderer', 'vendor', 'version', 'memory']):
                    info_text += line + "\n"
            
            info_text += "\n--- Sterownik ---\n"
            result = subprocess.run(['modinfo', 'nouveau'], 
                                  capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n')[:10]:
                info_text += line + "\n"
            
        except Exception as e:
            info_text += f"\nBłąd: {str(e)}\n"
        
        self.card_info_text.setPlainText(info_text)
    
    def update_codecs(self):
        """Aktualizacja informacji o kodekach"""
        codec_text = ""
        
        try:
            # vainfo dla VA-API
            result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=3)
            codec_text += "=== VA-API (Video Acceleration API) ===\n\n"
            codec_text += result.stdout
            
            if "error" in result.stdout.lower() or "failed" in result.stdout.lower():
                codec_text += "\n\n⚠️ VA-API może nie być dostępne dla Nouveau.\n"
                codec_text += "Nouveau ma ograniczone wsparcie dla akceleracji wideo.\n"
                
        except FileNotFoundError:
            codec_text = "vainfo nie jest zainstalowane.\n"
            codec_text += "Zainstaluj: sudo pacman -S libva-utils\n\n"
            codec_text += "⚠️ Nouveau ma bardzo ograniczone wsparcie dla VA-API.\n"
            codec_text += "Dla pełnej akceleracji wideo rozważ sterownik nvidia-390xx."
        except Exception as e:
            codec_text = f"Błąd podczas sprawdzania kodeków: {str(e)}"
        
        self.codecs_text.setPlainText(codec_text)
    
    def find_gpu_pci_id(self):
        """Znajdź PCI ID karty NVIDIA/Nouveau"""
        try:
            result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\n'):
                if 'VGA' in line or 'Display' in line or '3D' in line:
                    if 'NVIDIA' in line or 'nouveau' in line.lower():
                        return line.split()[0]
            
            # Fallback - pierwsza karta VGA
            for line in result.stdout.split('\n'):
                if 'VGA' in line:
                    return line.split()[0]
                    
        except:
            pass
        
        return "00:00.0"

def main():
    app = QApplication(sys.argv)
    
    # Ciemny motyw (opcjonalnie)
    app.setStyle("Fusion")
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
    
    window = GPUMonitor()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()