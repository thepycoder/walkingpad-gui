#!/usr/bin/env python3
"""
WalkingPad GUI Controller
A simple, compact GUI for controlling WalkingPad treadmills with Home Assistant integration.
"""

import sys
import asyncio
import threading
import time
import json
import requests
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                            QLineEdit, QGroupBox, QDialog, QTabWidget, 
                            QMessageBox, QFrame)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QFont, QPalette

from ph4_walkingpad.pad import Controller, WalkingPadCurStatus, WalkingPad


class HomeAssistantSync:
    """Handles synchronization with Home Assistant using input_number helper"""
    
    def __init__(self, url: str = "", token: str = "", entity_id: str = ""):
        self.url = url.rstrip('/')
        self.token = token
        self.entity_id = entity_id
        self.enabled = bool(url and token and entity_id)
        
        # Delta tracking for step counting
        self.last_device_steps = 0
        self.session_initialized = False
        
    def reset_session(self, current_device_steps: int = 0):
        """Reset session tracking when device reconnects"""
        self.last_device_steps = current_device_steps
        self.session_initialized = True
        print(f"Session reset - device steps: {current_device_steps}")
        
    def get_current_total_from_ha(self) -> int:
        """Get current total steps from Home Assistant input_number"""
        if not self.enabled:
            return 0
            
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            response = requests.get(
                f"{self.url}/api/states/{self.entity_id}",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                try:
                    return int(float(data.get('state', 0)))
                except (ValueError, TypeError):
                    return 0
            else:
                print(f"Failed to get HA state: {response.status_code}")
                return 0
                
        except Exception as e:
            print(f"Failed to get current total from HA: {e}")
            return 0
        
    def update_steps(self, device_steps: int) -> bool:
        """Update step counter with delta tracking using input_number.set_value service"""
        if not self.enabled:
            return False
            
        # Initialize session if needed
        if not self.session_initialized:
            self.reset_session(device_steps)
            return True  # Don't sync on first initialization
            
        # Handle step delta calculation
        if device_steps < self.last_device_steps:
            # Device counter reset (reconnection) - start new session
            print(f"Device step reset detected: {device_steps} < {self.last_device_steps}")
            self.reset_session(device_steps)
            return True  # Don't sync when resetting
        
        # Calculate steps taken in this update
        step_delta = device_steps - self.last_device_steps
        if step_delta <= 0:
            return True  # No new steps
            
        # Get current total from HA and add delta
        current_total = self.get_current_total_from_ha()
        new_total = current_total + step_delta
        
        print(f"Adding {step_delta} steps: {current_total} -> {new_total}")
        
        self.last_device_steps = device_steps
        
        try:
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            # Use input_number.set_value service to update the helper
            service_data = {
                'entity_id': self.entity_id,
                'value': new_total
            }
            
            response = requests.post(
                f"{self.url}/api/services/input_number/set_value",
                headers=headers,
                json=service_data,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"Successfully updated {self.entity_id} to {new_total} steps")
                return True
            else:
                print(f"Failed to update HA input_number: {response.status_code}")
                return False
            
        except Exception as e:
            print(f"Failed to sync with Home Assistant: {e}")
            return False


class AsyncWorker(QObject):
    """Worker class to handle async operations in a separate thread"""
    status_updated = pyqtSignal(object)
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.loop = None
        self.controller = Controller()
        self.connected = False
        
    def setup_loop(self):
        """Setup the asyncio event loop for this thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def run_loop(self):
        """Run the asyncio event loop"""
        if self.loop:
            self.loop.run_forever()
            
    def stop_loop(self):
        """Stop the asyncio event loop"""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
            
    def run_coroutine(self, coro):
        """Run a coroutine in the event loop"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    @staticmethod
    def _address_to_dbus_path(address: str) -> str:
        """Convert a MAC address to a BlueZ D-Bus object path"""
        dev_suffix = address.upper().replace(':', '_')
        return f"/org/bluez/hci0/dev_{dev_suffix}"

    async def _is_device_connected_system(self, address: str) -> bool:
        """Check if a BLE device is already connected at the BlueZ/system level via D-Bus"""
        dbus_path = self._address_to_dbus_path(address)
        try:
            proc = await asyncio.create_subprocess_exec(
                'busctl', 'get-property', 'org.bluez', dbus_path,
                'org.bluez.Device1', 'Connected',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip() == 'b true'
        except Exception as e:
            print(f"Failed to check system BT status via D-Bus: {e}")
            return False

    async def _disconnect_system(self, address: str):
        """Disconnect a device at the BlueZ/system level via bluetoothctl"""
        try:
            print(f"Disconnecting {address} at system level...")
            proc = await asyncio.create_subprocess_exec(
                'bluetoothctl', 'disconnect', address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Failed to disconnect at system level: {e}")

    async def connect(self, address: str):
        """Connect to WalkingPad, releasing any existing system-level connection first"""
        already_connected = await self._is_device_connected_system(address)
        if already_connected:
            print(f"Device already connected at system level, releasing before connecting...")
            await self._disconnect_system(address)
        try:
            await self.controller.run(address)
            self.connected = True
            self.connection_changed.emit(True)
        except Exception as ex:
            self.error_occurred.emit(f"Failed to connect: {ex}")

    async def check_and_auto_connect(self, address: str):
        """On startup, detect if device is already connected and reconnect cleanly"""
        try:
            if not await self._is_device_connected_system(address):
                return
            # Device is already connected to BlueZ — bleak cannot connect while it is, so
            # disconnect at system level first, then reconnect fresh via bleak.
            print(f"WalkingPad {address} already connected at system level, releasing and reconnecting...")
            await self._disconnect_system(address)
            try:
                await self.controller.run(address)
                self.connected = True
                self.connection_changed.emit(True)
                print("Successfully reconnected after system disconnect")
            except Exception as ex:
                print(f"Reconnect after system disconnect failed: {ex}")
        except Exception as e:
            print(f"Auto-connect check failed: {e}")
            
    async def disconnect(self):
        """Disconnect from WalkingPad"""
        try:
            # Stop belt and switch to standby before disconnecting
            if hasattr(self.controller, 'last_status') and self.controller.last_status:
                status = self.controller.last_status
                if status.belt_state == 1:
                    await self.controller.stop_belt()
                    await asyncio.sleep(1.0)
            await self.controller.switch_mode(WalkingPad.MODE_STANDBY)
            await self.controller.disconnect()
            self.connected = False
            self.connection_changed.emit(False)
        except Exception as e:
            print(f"Error disconnecting: {e}")
            
    async def get_status(self):
        """Get current status from WalkingPad"""
        try:
            await self.controller.ask_stats()
            if hasattr(self.controller, 'last_status') and self.controller.last_status:
                self.status_updated.emit(self.controller.last_status)
        except Exception as e:
            print(f"Error getting status: {e}")
            
    async def start_belt(self):
        """Start belt sequence: set manual mode then start belt"""
        try:
            await self.controller.switch_mode(WalkingPad.MODE_MANUAL)
            await asyncio.sleep(1.0)
            await self.controller.start_belt()
        except Exception as e:
            print(f"Error starting belt: {e}")
            
    async def stop_belt(self):
        """Stop the belt"""
        try:
            await self.controller.stop_belt()
        except Exception as e:
            print(f"Error stopping belt: {e}")
            
    async def set_speed(self, speed_kmh: float):
        """Set belt speed"""
        try:
            speed_units = int(speed_kmh * 10)
            await self.controller.change_speed(speed_units)
        except Exception as e:
            print(f"Error setting speed: {e}")


class WalkingPadGUI(QMainWindow):
    """Main GUI application for WalkingPad control"""
    
    def __init__(self):
        super().__init__()
        
        # Configuration file path
        self.config_dir = Path.home() / ".walkingpad_gui"
        self.config_file = self.config_dir / "config.json"
        
        # Default settings
        self.pad_address = "04:57:91:B0:F1:71"  # Default MAC address
        self.sync_interval = 30  # seconds
        self.ha_url = ""
        self.ha_token = ""
        self.ha_entity_id = "input_number.total_steps_all_time"
        
        # Load saved configuration
        self.load_config()
        
        # State variables
        self.connected = False
        self.current_status: Optional[WalkingPadCurStatus] = None
        self.last_sync_time = 0
        
        # Home Assistant integration
        self.ha_sync = HomeAssistantSync(
            url=self.ha_url,
            token=self.ha_token,
            entity_id=self.ha_entity_id
        )
        
        # Setup async worker in separate thread
        self.async_thread = QThread()
        self.async_worker = AsyncWorker()
        self.async_worker.moveToThread(self.async_thread)
        
        # Connect signals
        self.async_worker.status_updated.connect(self.update_display)
        self.async_worker.connection_changed.connect(self.update_connection_status)
        self.async_worker.error_occurred.connect(self.show_error)
        
        # Setup async loop when thread starts
        self.async_thread.started.connect(self.async_worker.setup_loop)
        self.async_thread.started.connect(self.async_worker.run_loop)
        self.async_thread.start()
        
        # Setup UI
        self.setup_ui()
        
        # Setup status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.request_status_update)
        self.status_timer.start(1000)  # 1 second intervals
        
        # Auto-connect if device is already connected at system level
        QTimer.singleShot(1500, self.auto_connect)
        
    def load_config(self):
        """Load configuration from disk"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                # Load WalkingPad settings
                self.pad_address = config.get('pad_address', self.pad_address)
                self.sync_interval = config.get('sync_interval', self.sync_interval)
                
                # Load Home Assistant settings
                self.ha_url = config.get('ha_url', '')
                self.ha_token = config.get('ha_token', '')
                self.ha_entity_id = config.get('ha_entity_id', '')
                
                print(f"Configuration loaded from {self.config_file}")
        except Exception as e:
            print(f"Failed to load configuration: {e}")
            
    def save_config(self):
        """Save configuration to disk"""
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(exist_ok=True)
            
            config = {
                'pad_address': self.pad_address,
                'sync_interval': self.sync_interval,
                'ha_url': self.ha_url,
                'ha_token': self.ha_token,
                'ha_entity_id': self.ha_entity_id
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            print(f"Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"Failed to save configuration: {e}")
            
    def setup_ui(self):
        """Create and arrange GUI elements"""
        self.setWindowTitle("WalkingPad Controller")
        self.setFixedSize(170, 220)
        
        # Make window stay on top
        self.setWindowFlags(self.windowFlags() | 
                           self.windowFlags().__class__.WindowStaysOnTopHint)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Stats group box
        stats_group = QGroupBox("Stats")
        stats_layout = QGridLayout(stats_group)
        
        # Speed display
        stats_layout.addWidget(QLabel("Speed:"), 0, 0)
        self.speed_label = QLabel("0.0 km/h")
        font = QFont()
        font.setBold(True)
        self.speed_label.setFont(font)
        stats_layout.addWidget(self.speed_label, 0, 1)
        
        # Steps display
        stats_layout.addWidget(QLabel("Steps:"), 1, 0)
        self.steps_label = QLabel("0")
        self.steps_label.setFont(font)
        stats_layout.addWidget(self.steps_label, 1, 1)
        
        main_layout.addWidget(stats_group)
        
        # Button row
        button_layout = QHBoxLayout()
        
        # Connect/Disconnect button
        self.connect_btn = QPushButton("C")
        self.connect_btn.setFixedWidth(40)
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.set_button_color(self.connect_btn, "red")
        button_layout.addWidget(self.connect_btn)
        
        # Start/Stop button
        self.start_btn = QPushButton("GO")
        self.start_btn.setFixedWidth(40)
        self.start_btn.clicked.connect(self.toggle_belt)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        
        # Settings button
        settings_btn = QPushButton("S")
        settings_btn.setFixedWidth(40)
        settings_btn.clicked.connect(self.open_settings)
        button_layout.addWidget(settings_btn)
        
        main_layout.addLayout(button_layout)
        
        # Speed control group
        speed_group = QGroupBox("Speed")
        speed_layout = QHBoxLayout(speed_group)
        
        # Decrease speed button
        decrease_btn = QPushButton("-")
        decrease_btn.setFixedWidth(30)
        decrease_btn.clicked.connect(self.decrease_speed)
        speed_layout.addWidget(decrease_btn)
        
        # Speed entry
        self.speed_entry = QLineEdit("2.0")
        self.speed_entry.setFixedWidth(60)
        self.speed_entry.setAlignment(self.speed_entry.alignment().__class__.AlignCenter)
        self.speed_entry.returnPressed.connect(self.set_speed_from_entry)
        speed_layout.addWidget(self.speed_entry)
        
        # Increase speed button
        increase_btn = QPushButton("+")
        increase_btn.setFixedWidth(30)
        increase_btn.clicked.connect(self.increase_speed)
        speed_layout.addWidget(increase_btn)
        
        main_layout.addWidget(speed_group)
        
    def set_button_color(self, button: QPushButton, color: str):
        """Set button text color"""
        button.setStyleSheet(f"QPushButton {{ color: {color}; }}")
        
    def auto_connect(self):
        """On startup, check if WalkingPad is already connected at system BT level and hook in"""
        if not self.connected and self.pad_address:
            self.async_worker.run_coroutine(
                self.async_worker.check_and_auto_connect(self.pad_address)
            )

    def request_status_update(self):
        """Request status update from async worker"""
        if self.connected:
            self.async_worker.run_coroutine(self.async_worker.get_status())
            
    def update_display(self, status: WalkingPadCurStatus):
        """Update the GUI display with current status"""
        self.current_status = status
        
        # Update speed display
        speed_kmh = status.speed / 10.0
        self.speed_label.setText(f"{speed_kmh:.1f} km/h")
        
        # Update steps display
        self.steps_label.setText(f"{status.steps:,}")
        
        # Update start/stop button based on belt state
        if status.belt_state == 1:  # Running
            self.start_btn.setText("STP")
        else:  # Stopped
            self.start_btn.setText("GO")
            
        # Sync with Home Assistant if enabled and enough time has passed
        current_time = time.time()
        if (current_time - self.last_sync_time) >= self.sync_interval:
            if status.steps is not None:
                if self.ha_sync.update_steps(status.steps):
                    self.last_sync_time = current_time
                    
    def update_connection_status(self, connected: bool):
        """Update connection status display"""
        self.connected = connected
        
        if connected:
            self.connect_btn.setText("D")
            self.set_button_color(self.connect_btn, "green")
            self.start_btn.setEnabled(True)
        else:
            self.connect_btn.setText("C")
            self.set_button_color(self.connect_btn, "red")
            self.start_btn.setEnabled(False)
            self.start_btn.setText("GO")
            self.speed_label.setText("0.0 km/h")
            self.steps_label.setText("0")
            # Reset session on disconnect
            self.ha_sync.session_initialized = False
            
    def show_error(self, message: str):
        """Show error message"""
        QMessageBox.critical(self, "Error", message)
        
    def toggle_connection(self):
        """Connect or disconnect from WalkingPad"""
        if self.connected:
            self.async_worker.run_coroutine(self.async_worker.disconnect())
        else:
            self.async_worker.run_coroutine(self.async_worker.connect(self.pad_address))
            
    def toggle_belt(self):
        """Start or stop the belt"""
        if not self.connected:
            return
            
        if self.current_status and self.current_status.belt_state == 1:
            # Stop the belt
            self.async_worker.run_coroutine(self.async_worker.stop_belt())
        else:
            # Start the belt
            self.async_worker.run_coroutine(self.async_worker.start_belt())
            # Set initial speed after a delay
            QTimer.singleShot(10000, self.set_initial_speed)
            
    def set_initial_speed(self):
        """Set initial speed after belt starts"""
        try:
            speed = float(self.speed_entry.text())
            speed = max(0.5, min(6.0, speed))
            self.async_worker.run_coroutine(self.async_worker.set_speed(speed))
        except ValueError:
            pass
            
    def set_speed_from_entry(self):
        """Set speed from entry widget"""
        try:
            speed = float(self.speed_entry.text())
            speed = max(0.5, min(6.0, speed))
            self.speed_entry.setText(f"{speed:.1f}")
            self.async_worker.run_coroutine(self.async_worker.set_speed(speed))
        except ValueError:
            self.speed_entry.setText("1.0")
            
    def increase_speed(self):
        """Increase speed by 0.5 km/h"""
        try:
            current = float(self.speed_entry.text())
            new_speed = min(6.0, current + 0.5)
            self.speed_entry.setText(f"{new_speed:.1f}")
            self.async_worker.run_coroutine(self.async_worker.set_speed(new_speed))
        except ValueError:
            pass
            
    def decrease_speed(self):
        """Decrease speed by 0.5 km/h"""
        try:
            current = float(self.speed_entry.text())
            new_speed = max(0.5, current - 0.5)
            self.speed_entry.setText(f"{new_speed:.1f}")
            self.async_worker.run_coroutine(self.async_worker.set_speed(new_speed))
        except ValueError:
            pass
            
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Settings were saved, update configuration
            self.ha_sync = HomeAssistantSync(
                url=self.ha_url,
                token=self.ha_token,
                entity_id=self.ha_entity_id
            )
            
    def closeEvent(self, event):
        """Handle window close event"""
        if self.connected:
            self.async_worker.run_coroutine(self.async_worker.disconnect())
        
        # Stop the async worker and thread
        self.async_worker.stop_loop()
        self.async_thread.quit()
        self.async_thread.wait()
        
        event.accept()


class SettingsDialog(QDialog):
    """Settings dialog for configuration"""
    
    def __init__(self, parent: WalkingPadGUI):
        super().__init__(parent)
        self.app = parent
        
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 280)
        self.setModal(True)
        
        self.setup_dialog()
        
    def setup_dialog(self):
        """Create dialog content"""
        layout = QVBoxLayout(self)
        
        # Tab widget
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # WalkingPad settings tab
        pad_widget = QWidget()
        pad_layout = QGridLayout(pad_widget)
        
        pad_layout.addWidget(QLabel("MAC Address:"), 0, 0)
        self.address_entry = QLineEdit(self.app.pad_address)
        pad_layout.addWidget(self.address_entry, 0, 1)
        
        pad_layout.addWidget(QLabel("Sync Interval (seconds):"), 1, 0)
        self.sync_entry = QLineEdit(str(self.app.sync_interval))
        pad_layout.addWidget(self.sync_entry, 1, 1)
        
        tab_widget.addTab(pad_widget, "WalkingPad")
        
        # Home Assistant settings tab
        ha_widget = QWidget()
        ha_layout = QGridLayout(ha_widget)
        
        ha_layout.addWidget(QLabel("Home Assistant URL:"), 0, 0)
        self.ha_url_entry = QLineEdit(self.app.ha_url)
        ha_layout.addWidget(self.ha_url_entry, 0, 1)
        
        ha_layout.addWidget(QLabel("Access Token:"), 1, 0)
        self.ha_token_entry = QLineEdit(self.app.ha_token)
        self.ha_token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        ha_layout.addWidget(self.ha_token_entry, 1, 1)
        
        ha_layout.addWidget(QLabel("Input Number Entity ID:"), 2, 0)
        self.ha_entity_entry = QLineEdit(self.app.ha_entity_id)
        ha_layout.addWidget(self.ha_entity_entry, 2, 1)
        
        example_label = QLabel("Example: input_number.total_steps_all_time")
        example_label.setStyleSheet("color: gray; font-style: italic;")
        ha_layout.addWidget(example_label, 3, 1)
        
        # Test button
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self.test_ha_connection)
        ha_layout.addWidget(test_btn, 4, 0, 1, 2)
        
        tab_widget.addTab(ha_widget, "Home Assistant")
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
    def test_ha_connection(self):
        """Test Home Assistant connection"""
        url = self.ha_url_entry.text().strip().rstrip('/')
        token = self.ha_token_entry.text().strip()
        
        if not url or not token:
            QMessageBox.warning(self, "Test Connection", "Please enter URL and token first")
            return
            
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(f"{url}/api/", headers=headers, timeout=5)
            
            if response.status_code == 200:
                QMessageBox.information(self, "Test Connection", "Connection successful!")
            else:
                QMessageBox.critical(self, "Test Connection", f"Connection failed: {response.status_code}")
                
        except Exception as e:
            QMessageBox.critical(self, "Test Connection", f"Connection failed: {e}")
            
    def save_settings(self):
        """Save settings and close dialog"""
        # Update WalkingPad settings
        self.app.pad_address = self.address_entry.text().strip()
        
        try:
            self.app.sync_interval = max(10, int(self.sync_entry.text()))
        except ValueError:
            self.app.sync_interval = 30
            
        # Update Home Assistant settings
        self.app.ha_url = self.ha_url_entry.text().strip()
        self.app.ha_token = self.ha_token_entry.text().strip()
        self.app.ha_entity_id = self.ha_entity_entry.text().strip()
        
        # Save configuration to disk
        self.app.save_config()
        
        QMessageBox.information(self, "Settings", "Settings saved successfully!")
        self.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("WalkingPad Controller")
    app.setApplicationVersion("2.0")
    
    # Create and show main window
    window = WalkingPadGUI()
    window.show()
    
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()