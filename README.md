# WalkingPad GUI Controller

A simple, compact GUI application for controlling WalkingPad treadmills with optional Home Assistant integration.

## Features

- **Compact Design**: Small, always-on-top window that won't interfere with your work
- **Real-time Monitoring**: Display current speed, step count, and connection status
- **Easy Control**: Start/stop belt and adjust speed with simple buttons
- **Home Assistant Integration**: Automatically sync step counts to your smart home
- **Bluetooth Connectivity**: Connect to your WalkingPad via Bluetooth LE

## Requirements

- Python 3.9 or higher
- Linux system with Bluetooth support
- WalkingPad treadmill with Bluetooth connectivity
- UV package manager (recommended)

## Installation

### Automatic Installation (Recommended)

```bash
# Clone or download this project
cd walkingpad-gui

# Run the installation script
./install.sh

# Run the application
walkingpad-gui
```

### Manual Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install ph4-walkingpad requests

# Run from source
python main.py
```

### Development Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode for development
pip install -e .

# Run the installed command
walkingpad-gui
```

## Configuration

### WalkingPad Setup

1. **Find your WalkingPad's MAC address:**
   ```bash
   # Scan for Bluetooth devices
   bluetoothctl scan on
   # Look for your WalkingPad device
   ```

2. **Update the MAC address in the GUI:**
   - Click "Settings"
   - Go to "WalkingPad" tab
   - Enter your device's MAC address
   - Set sync interval (default: 30 seconds)

### Home Assistant Integration

The GUI can automatically sync your step count to Home Assistant. This is optional but provides great integration with your smart home.

#### Prerequisites

- Home Assistant instance running and accessible
- Long-lived access token
- Sensor entity configured

#### Setup Steps

1. **Create a Long-lived Access Token in Home Assistant:**
   - Go to Profile → Security → Long-lived access tokens
   - Click "Create Token"
   - Give it a name like "WalkingPad GUI"
   - Copy the token (you won't see it again!)

2. **Configure the GUI:**
   - Click "Settings" in the GUI
   - Go to "Home Assistant" tab
   - Enter your Home Assistant URL (e.g., `http://192.168.1.100:8123`)
   - Enter your access token
   - Enter entity ID (e.g., `sensor.walkingpad_steps`)
   - Click "Test Connection" to verify

3. **The sensor will automatically appear in Home Assistant** when the GUI first syncs data.

## Usage

### Basic Operation

1. **Connect to your WalkingPad:**
   - Ensure your WalkingPad is powered on
   - Click "Connect" in the GUI
   - Wait for "Connected" status (green text)

2. **Control the treadmill:**
   - Click "Start" to begin the belt
   - Use +/- buttons to adjust speed
   - Or type speed directly and press Enter
   - Click "Stop" to stop the belt

3. **Monitor your workout:**
   - Current speed is displayed in km/h
   - Step count updates in real-time
   - Connection status shows at the top

### Speed Control

- **Range**: 0.5 - 6.0 km/h
- **Increment**: 0.5 km/h using +/- buttons
- **Direct Input**: Type any value and press Enter
- **Limits**: Values outside the range are automatically clamped

### Home Assistant Sync

- Steps are synced automatically every 30 seconds (configurable)
- Sync only occurs when connected to the WalkingPad
- Failed syncs are logged but don't interrupt operation
- The sensor includes metadata like last update time

## Home Assistant Integration Tutorial

### Setting Up the Sensor

Once you've configured the GUI with your Home Assistant details, the sensor will automatically be created when data is first synced. However, you can also create it manually:

#### Manual Sensor Configuration

Add this to your `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: WalkingPad Steps
    resource: !secret walkingpad_steps_url
    headers:
      Authorization: !secret walkingpad_token
    value_template: "{{ value_json.state }}"
    unit_of_measurement: "steps"
```

Add to `secrets.yaml`:
```yaml
walkingpad_steps_url: "http://your-ha-instance:8123/api/states/sensor.walkingpad_steps"
walkingpad_token: "Bearer your-long-lived-token"
```

#### Using the Sensor in Automations

Example automation that congratulates you on reaching step goals:

```yaml
automation:
  - alias: "WalkingPad Step Goal Reached"
    trigger:
      - platform: numeric_state
        entity_id: sensor.walkingpad_steps
        above: 1000
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Great job! You've reached 1000 steps on the WalkingPad!"
```

#### Dashboard Card

Add a sensor card to your dashboard:

```yaml
type: sensor
entity: sensor.walkingpad_steps
name: WalkingPad Steps
icon: mdi:walk
```

Or create a more detailed card:

```yaml
type: entities
title: WalkingPad Stats
entities:
  - sensor.walkingpad_steps
  - type: attribute
    entity: sensor.walkingpad_steps
    attribute: last_updated
    name: Last Updated
```

### Advanced Home Assistant Integration

#### Creating a Daily Steps Sensor

Create a utility meter to track daily steps:

```yaml
utility_meter:
  walkingpad_daily_steps:
    source: sensor.walkingpad_steps
    cycle: daily
    name: WalkingPad Daily Steps
```

#### Workout Session Detection

Create a binary sensor to detect active workouts:

```yaml
template:
  - binary_sensor:
      - name: "WalkingPad Active"
        state: >
          {{ (as_timestamp(now()) - as_timestamp(states.sensor.walkingpad_steps.last_updated)) < 120 }}
        device_class: running
```

#### Step Rate Calculation

Calculate steps per minute:

```yaml
template:
  - sensor:
      - name: "WalkingPad Step Rate"
        unit_of_measurement: "steps/min"
        state: >
          {% set current = states('sensor.walkingpad_steps') | int %}
          {% set previous = state_attr('sensor.walkingpad_steps', 'previous_state') | int %}
          {% set time_diff = (as_timestamp(now()) - as_timestamp(states.sensor.walkingpad_steps.last_updated)) / 60 %}
          {% if time_diff > 0 %}
            {{ ((current - previous) / time_diff) | round(1) }}
          {% else %}
            0
          {% endif %}
```

## Troubleshooting

### Connection Issues

**Problem**: Can't connect to WalkingPad
- Ensure the device is powered on and in pairing mode
- Check the MAC address is correct
- Try turning Bluetooth off and on
- Make sure no other app is connected to the device

**Problem**: Connection drops frequently
- Check Bluetooth signal strength
- Move closer to the WalkingPad
- Reduce sync interval in settings

### Home Assistant Issues

**Problem**: Sensor not appearing in Home Assistant
- Verify the URL includes the protocol (http:// or https://)
- Check the access token is valid
- Ensure the entity ID format is correct (e.g., sensor.walkingpad_steps)
- Test the connection using the "Test Connection" button

**Problem**: Data not syncing
- Check Home Assistant logs for errors
- Verify network connectivity
- Confirm the access token has write permissions

### GUI Issues

**Problem**: Window not staying on top
- This is a feature to keep the window visible while working
- You can disable it by removing the `topmost` attribute in the code

**Problem**: GUI freezes or crashes
- Check the terminal for error messages
- Restart the application
- Ensure all dependencies are installed correctly

## Development

### Project Structure

```
walkingpad-gui/
├── main.py              # Main application file
├── pyproject.toml       # Project configuration
├── README.md           # This documentation
└── .gitignore          # Git ignore rules
```

### Code Organization

- `HomeAssistantSync`: Handles Home Assistant API communication
- `WalkingPadGUI`: Main application class with UI and WalkingPad control
- `SettingsDialog`: Configuration dialog for WalkingPad and Home Assistant settings

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. The ph4-walkingpad library is licensed under MIT.

## Credits

- Built using the excellent [ph4-walkingpad](https://github.com/ph4r05/ph4-walkingpad) library
- Inspired by the need for a simple, always-visible WalkingPad controller
- Home Assistant integration for smart home enthusiasts

## Support

If you encounter issues:

1. Check this README for troubleshooting steps
2. Ensure all dependencies are correctly installed
3. Verify your WalkingPad is compatible with the ph4-walkingpad library
4. Check the ph4-walkingpad repository for device-specific issues

For Home Assistant specific questions, refer to the Home Assistant documentation or community forums.
