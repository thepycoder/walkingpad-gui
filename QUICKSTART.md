# Quick Start Guide

## Immediate Setup (5 minutes)

### 1. Install and Run
```bash
cd walkingpad-gui
./install.sh
./run.sh
```

### 2. Update Your MAC Address
- In the GUI, click **Settings**
- Go to **WalkingPad** tab
- Replace `04:57:91:B0:F1:71` with your device's MAC address
- Click **Save**

### 3. Connect
- Power on your WalkingPad
- Click **Connect** in the GUI
- Wait for green "Connected" status

### 4. Start Walking!
- Click **Start** to begin the belt
- Use **+/-** buttons to adjust speed
- Monitor your steps in real-time

## Finding Your WalkingPad MAC Address

### Method 1: Bluetooth Scan
```bash
bluetoothctl scan on
# Look for your WalkingPad device name
```

### Method 2: Using the Original App
1. Open the official WalkingPad app
2. Connect to your device
3. Check app settings or device info for MAC address

### Method 3: System Bluetooth Settings
- Open your system's Bluetooth settings
- Look for previously paired WalkingPad device
- Check device properties for MAC address

## Home Assistant Integration (Optional)

### Quick Setup
1. In Home Assistant: Profile → Security → Create long-lived access token
2. In GUI: Settings → Home Assistant tab
3. Enter:
   - URL: `http://your-home-assistant:8123`
   - Token: (paste your token)
   - Entity ID: `sensor.walkingpad_steps`
4. Click **Test Connection**
5. Click **Save**

The sensor will automatically appear in Home Assistant!

## Troubleshooting

**Can't connect?**
- Ensure WalkingPad is powered on
- Check MAC address is correct
- Make sure no other app is connected

**GUI won't start?**
```bash
# Test dependencies (activate venv first if installed)
source .venv/bin/activate
python test_imports.py
```

**Home Assistant not working?**
- Check URL includes `http://` or `https://`
- Verify token is correct and not expired
- Test connection using the button in settings

## Daily Usage

1. **Run the app**: `./run.sh` or double-click the desktop file
2. **Pin to stay on top**: The window automatically stays above other windows
3. **Quick connect**: The GUI remembers your settings
4. **Monitor stats**: Steps sync to Home Assistant every 30 seconds

That's it! You now have a compact, always-visible WalkingPad controller with smart home integration. 