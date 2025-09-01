#!/usr/bin/env python3
"""
WalkingPad GUI Controller
A simple, compact GUI for controlling WalkingPad treadmills with Home Assistant integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
import time
import json
import requests
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

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


class WalkingPadGUI:
    """Main GUI application for WalkingPad control"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WalkingPad Controller")
        self.root.geometry("170x220")  # Reduced height from 320 to 280
        self.root.resizable(False, False)
        
        # Make window stay on top
        self.root.attributes('-topmost', True)
        
        # Configuration file path
        self.config_dir = Path.home() / ".walkingpad_gui"
        self.config_file = self.config_dir / "config.json"
        
        # Default settings
        self.pad_address = "04:57:91:B0:F1:71"  # Default MAC address
        self.sync_interval = 30  # seconds
        self.ha_url = ""
        self.ha_token = ""
        self.ha_entity_id = "input_number.total_steps_all_time"  # Default to input_number helper
        
        # Load saved configuration
        self.load_config()
        
        # WalkingPad controller
        self.controller = Controller()
        self.connected = False
        self.current_status: Optional[WalkingPadCurStatus] = None
        
        # Home Assistant integration
        self.ha_sync = HomeAssistantSync(
            url=self.ha_url,
            token=self.ha_token,
            entity_id=self.ha_entity_id
        )
        
        # Control state
        self.last_sync_time = 0
        
        # Create GUI elements
        self.setup_gui()
        
        # Start async loop in separate thread
        self.loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()
        
        # Start periodic status updates
        self.update_status()
    
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
        
    def setup_gui(self):
        """Create and arrange GUI elements"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Stats frame (moved to top, no status label)
        stats_frame = ttk.LabelFrame(main_frame, text="Stats", padding="5")
        stats_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Speed display
        ttk.Label(stats_frame, text="Speed:").grid(row=0, column=0, sticky=tk.W)
        self.speed_label = ttk.Label(stats_frame, text="0.0 km/h", font=("TkDefaultFont", 10, "bold"))
        self.speed_label.grid(row=0, column=1, sticky=tk.E)
        
        # Steps display (session only)
        ttk.Label(stats_frame, text="Steps:").grid(row=1, column=0, sticky=tk.W)
        self.steps_label = ttk.Label(stats_frame, text="0", font=("TkDefaultFont", 10, "bold"))
        self.steps_label.grid(row=1, column=1, sticky=tk.E)
        
        # Compact button row frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Connect/Disconnect button (shortened text, will be colored)
        style = ttk.Style()
        style.configure("Disconnected.TButton", foreground="red")
        self.connect_btn = ttk.Button(button_frame, text="C", command=self.toggle_connection, style="Disconnected.TButton", width=4)
        self.connect_btn.grid(row=0, column=0, padx=(0, 2))
        
        # Start/Stop button (shortened text)  
        self.start_btn = ttk.Button(button_frame, text="GO", command=self.toggle_belt, state="disabled", width=4)
        self.start_btn.grid(row=0, column=1, padx=2)
        
        # Settings button (shortened text)
        settings_btn = ttk.Button(button_frame, text="S", command=self.open_settings, width=4)
        settings_btn.grid(row=0, column=2, padx=(2, 0))
        
        # Control frame for speed controls
        control_frame = ttk.LabelFrame(main_frame, text="Speed", padding="5")
        control_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        
        # Speed control
        speed_frame = ttk.Frame(control_frame)
        speed_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        
        ttk.Button(speed_frame, text="-", command=self.decrease_speed, width=3).grid(row=0, column=0)
        self.speed_var = tk.StringVar(value="2.0")
        speed_entry = ttk.Entry(speed_frame, textvariable=self.speed_var, width=6, justify="center")
        speed_entry.grid(row=0, column=1, padx=5)
        speed_entry.bind('<Return>', self.set_speed_from_entry)
        ttk.Button(speed_frame, text="+", command=self.increase_speed, width=3).grid(row=0, column=2)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        stats_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        speed_frame.columnconfigure(1, weight=1)
        
    def _run_async_loop(self):
        """Run the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def update_status(self):
        """Periodically update the display with current status"""
        if self.connected:
            # Request status update
            asyncio.run_coroutine_threadsafe(self._get_status(), self.loop)
            
        # Schedule next update
        self.root.after(1000, self.update_status)
        
    async def _get_status(self):
        """Get current status from WalkingPad"""
        try:
            # Ask for statistics - this updates the controller's internal state
            await self.controller.ask_stats()
            
            # The status should be available in the controller after ask_stats
            # We need to access it from the controller's last received status
            if hasattr(self.controller, 'last_status') and self.controller.last_status:
                self.current_status = self.controller.last_status
                self.root.after(0, self._update_display)
                
                # Sync with Home Assistant if enabled and enough time has passed
                current_time = time.time()
                if (current_time - self.last_sync_time) >= self.sync_interval:
                    if self.current_status and hasattr(self.current_status, 'steps') and self.current_status.steps is not None:
                        if self.ha_sync.update_steps(self.current_status.steps):
                            self.last_sync_time = current_time
                        
        except Exception as e:
            print(f"Error getting status: {e}")
            
    def _update_display(self):
        """Update the GUI display with current status"""
        if not self.current_status:
            return
            
        status = self.current_status
        
        # Update speed display
        speed_kmh = status.speed / 10.0
        self.speed_label.config(text=f"{speed_kmh:.1f} km/h")
        
        # Update steps display (session only)
        self.steps_label.config(text=f"{status.steps:,}")
        
        # Update start/stop button based on belt state
        if status.belt_state == 1:  # Running
            self.start_btn.config(text="STP")
        else:  # Stopped
            self.start_btn.config(text="GO")
            
    def _update_connection_status(self):
        """Update connection status display"""
        if self.connected:
            self.connect_btn.config(text="D")
            # Create a style for connected state
            style = ttk.Style()
            style.configure("Connected.TButton", foreground="green")
            self.connect_btn.config(style="Connected.TButton")
            self.start_btn.config(state="normal")
        else:
            self.connect_btn.config(text="C")
            # Create a style for disconnected state
            style = ttk.Style()
            style.configure("Disconnected.TButton", foreground="red")
            self.connect_btn.config(style="Disconnected.TButton")
            self.start_btn.config(state="disabled", text="Play")
            self.speed_label.config(text="0.0 km/h")
            self.steps_label.config(text="0")
            
    def toggle_connection(self):
        """Connect or disconnect from WalkingPad"""
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._disconnect(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
            
    async def _connect(self):
        """Connect to WalkingPad"""
        try:
            await self.controller.run(self.pad_address)
            self.connected = True
            self.root.after(0, self._update_connection_status)
        except Exception as ex:
            error_msg = f"Failed to connect: {ex}"
            self.root.after(0, lambda: messagebox.showerror("Connection Error", error_msg))
            
    async def _disconnect(self):
        """Disconnect from WalkingPad"""
        try:
            # Stop belt and switch to standby before disconnecting
            if self.current_status and self.current_status.belt_state == 1:
                await self.controller.stop_belt()
                await asyncio.sleep(1.0)
            await self.controller.switch_mode(WalkingPad.MODE_STANDBY)
            await self.controller.disconnect()
            self.connected = False
            self.current_status = None
            # Reset session on disconnect
            self.ha_sync.session_initialized = False
            self.root.after(0, self._update_connection_status)
        except Exception as e:
            print(f"Error disconnecting: {e}")
            
    def toggle_belt(self):
        """Start or stop the belt"""
        if not self.connected:
            return
            
        if self.current_status and self.current_status.belt_state == 1:
            # Stop the belt
            asyncio.run_coroutine_threadsafe(self.controller.stop_belt(), self.loop)
        else:
            # Start the belt - set manual mode first, then start
            asyncio.run_coroutine_threadsafe(self._start_belt_sequence(), self.loop)
            
    async def _start_belt_sequence(self):
        """Start belt sequence: set manual mode then start belt"""
        try:
            await self.controller.switch_mode(WalkingPad.MODE_MANUAL)
            await asyncio.sleep(1.0)
            await self.controller.start_belt()
            
            # Set speed from input field after starting
            await asyncio.sleep(5)  # Give belt a moment to start
            initial_speed = float(self.speed_var.get())
            await self._set_speed(initial_speed)

        except Exception as e:
            print(f"Error starting belt: {e}")
            
    def set_speed_from_entry(self, event=None):
        """Set speed from entry widget"""
        try:
            speed = float(self.speed_var.get())
            speed = max(0.5, min(6.0, speed))  # Clamp to valid range
            self.speed_var.set(f"{speed:.1f}")
            asyncio.run_coroutine_threadsafe(self._set_speed(speed), self.loop)
        except ValueError:
            self.speed_var.set("1.0")
            
    def increase_speed(self):
        """Increase speed by 0.5 km/h"""
        try:
            current = float(self.speed_var.get())
            new_speed = min(6.0, current + 0.5)
            self.speed_var.set(f"{new_speed:.1f}")
            asyncio.run_coroutine_threadsafe(self._set_speed(new_speed), self.loop)
        except ValueError:
            pass
            
    def decrease_speed(self):
        """Decrease speed by 0.5 km/h"""
        try:
            current = float(self.speed_var.get())
            new_speed = max(0.5, current - 0.5)
            self.speed_var.set(f"{new_speed:.1f}")
            asyncio.run_coroutine_threadsafe(self._set_speed(new_speed), self.loop)
        except ValueError:
            pass
            
    async def _set_speed(self, speed_kmh: float):
        """Set belt speed"""
        if not self.connected:
            return
            
        try:
            # Convert km/h to internal units (speed * 10)
            speed_units = int(speed_kmh * 10)
            await self.controller.change_speed(speed_units)
        except Exception as e:
            print(f"Error setting speed: {e}")
            
    def open_settings(self):
        """Open settings dialog"""
        SettingsDialog(self.root, self)
        
    def on_closing(self):
        """Handle application closing"""
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._disconnect(), self.loop)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()


class SettingsDialog:
    """Settings dialog for configuration"""
    
    def __init__(self, parent: tk.Tk, app: WalkingPadGUI):
        self.app = app
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("400x280")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.setup_dialog()
        
    def setup_dialog(self):
        """Create dialog content"""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # WalkingPad settings tab
        pad_frame = ttk.Frame(notebook)
        notebook.add(pad_frame, text="WalkingPad")
        
        ttk.Label(pad_frame, text="MAC Address:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.address_var = tk.StringVar(value=self.app.pad_address)
        address_entry = ttk.Entry(pad_frame, textvariable=self.address_var, width=20)
        address_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(pad_frame, text="Sync Interval (seconds):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.sync_var = tk.StringVar(value=str(self.app.sync_interval))
        sync_entry = ttk.Entry(pad_frame, textvariable=self.sync_var, width=10)
        sync_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Home Assistant settings tab
        ha_frame = ttk.Frame(notebook)
        notebook.add(ha_frame, text="Home Assistant")
        
        ttk.Label(ha_frame, text="Home Assistant URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.ha_url_var = tk.StringVar(value=self.app.ha_url)
        ha_url_entry = ttk.Entry(ha_frame, textvariable=self.ha_url_var, width=30)
        ha_url_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(ha_frame, text="Access Token:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.ha_token_var = tk.StringVar(value=self.app.ha_token)
        ha_token_entry = ttk.Entry(ha_frame, textvariable=self.ha_token_var, width=30, show="*")
        ha_token_entry.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(ha_frame, text="Input Number Entity ID:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.ha_entity_var = tk.StringVar(value=self.app.ha_entity_id)
        ha_entity_entry = ttk.Entry(ha_frame, textvariable=self.ha_entity_var, width=30)
        ha_entity_entry.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(ha_frame, text="Example: input_number.total_steps_all_time").grid(row=3, column=1, sticky=tk.W, padx=5, pady=(0, 5))
        
        # Test button
        test_btn = ttk.Button(ha_frame, text="Test Connection", command=self.test_ha_connection)
        test_btn.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Buttons frame
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ttk.Button(btn_frame, text="Save", command=self.save_settings).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
        
    def test_ha_connection(self):
        """Test Home Assistant connection"""
        url = self.ha_url_var.get().strip().rstrip('/')
        token = self.ha_token_var.get().strip()
        
        if not url or not token:
            messagebox.showwarning("Test Connection", "Please enter URL and token first")
            return
            
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(f"{url}/api/", headers=headers, timeout=5)
            
            if response.status_code == 200:
                messagebox.showinfo("Test Connection", "Connection successful!")
            else:
                messagebox.showerror("Test Connection", f"Connection failed: {response.status_code}")
                
        except Exception as e:
            messagebox.showerror("Test Connection", f"Connection failed: {e}")
            
    def save_settings(self):
        """Save settings and close dialog"""
        # Update WalkingPad settings
        self.app.pad_address = self.address_var.get().strip()
        
        try:
            self.app.sync_interval = max(10, int(self.sync_var.get()))
        except ValueError:
            self.app.sync_interval = 30
            
        # Update Home Assistant settings
        self.app.ha_url = self.ha_url_var.get().strip()
        self.app.ha_token = self.ha_token_var.get().strip()
        self.app.ha_entity_id = self.ha_entity_var.get().strip()
        
        # Recreate Home Assistant sync object with new settings
        self.app.ha_sync = HomeAssistantSync(
            url=self.app.ha_url,
            token=self.app.ha_token,
            entity_id=self.app.ha_entity_id
        )
        
        # Save configuration to disk
        self.app.save_config()
        
        messagebox.showinfo("Settings", "Settings saved successfully!")
        self.dialog.destroy()


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = WalkingPadGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.on_closing()


if __name__ == "__main__":
    main() 