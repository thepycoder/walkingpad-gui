# Home Assistant Integration Setup

This guide explains how to set up the WalkingPad GUI with Home Assistant to track cumulative steps using an `input_number` helper and derived sensors.

## Overview

The integration now uses a Home Assistant `input_number` helper as the persistent storage for total steps, with additional template sensors and utility meters for daily/weekly/monthly tracking. This approach provides:

- **Persistent Total Steps**: Survives HA restarts and device reconnections
- **Daily/Weekly/Monthly Tracking**: Automatic reset periods using utility meters
- **Statistics Integration**: Proper metadata for HA statistics and energy dashboard
- **Delta Sync**: Only new steps are added, preventing double counting

## Prerequisites

Before setting up the WalkingPad GUI integration, you must create the necessary helpers and sensors in Home Assistant.

## Home Assistant Setup (Required First)

### 1. Create the Input Number Helper

You can create this via the UI (Settings → Devices & services → Helpers → "Number") or add to your YAML configuration:

```yaml
# In configuration.yaml or helpers.yaml
input_number:
  total_steps_all_time:
    name: Total Steps (All Time)
    min: 0
    max: 999999999
    step: 1
    mode: box
    unit_of_measurement: steps
    icon: mdi:walk
```

### 2. Create Template Sensor (Recommended)

This creates a proper sensor with `state_class: total_increasing` for statistics:

```yaml
# In configuration.yaml
template:
  - sensor:
      - name: "Total Steps"
        unique_id: total_steps_sensor
        unit_of_measurement: "steps"
        state_class: total_increasing
        icon: mdi:walk
        state: "{{ states('input_number.total_steps_all_time') | int(0) }}"
```

### 3. Create Daily/Weekly/Monthly Meters

Use utility meters to automatically track periods:

```yaml
# In configuration.yaml
utility_meter:
  daily_steps:
    source: sensor.total_steps
    cycle: daily
    name: Daily Steps
  
  weekly_steps:
    source: sensor.total_steps
    cycle: weekly
    name: Weekly Steps
    
  monthly_steps:
    source: sensor.total_steps
    cycle: monthly
    name: Monthly Steps
```

### 4. Reload Configuration

After adding the YAML configuration:
1. Go to Developer Tools → YAML
2. Click "Check Configuration"
3. If valid, click "Restart" or reload the specific sections:
   - "Reload Template Entities"
   - "Reload Utility Meter"

### 5. Create Long-Lived Access Token

1. In Home Assistant, go to your user profile (click your username)
2. Scroll down to "Long-lived access tokens"
3. Click "Create Token"
4. Give it a name like "WalkingPad GUI"
5. Copy the token (you won't see it again!)

## WalkingPad GUI Configuration

### 1. Configure the Integration

1. Open the WalkingPad GUI
2. Click the "S" (Settings) button
3. Go to the "Home Assistant" tab
4. Fill in:
   - **Home Assistant URL**: Your HA instance URL (e.g., `http://192.168.1.100:8123`)
   - **Access Token**: The long-lived token you created
   - **Input Number Entity ID**: `input_number.total_steps_all_time`
5. Click "Test Connection" to verify it works
6. Click "Save"

### 2. Verify Setup

After saving, connect to your WalkingPad and take a few steps. You should see:
- The input number value increasing in HA
- Daily steps tracking in `sensor.daily_steps`
- Proper statistics in HA's statistics dashboard

## How It Works

### Step Tracking Logic

1. **Session Initialization**: When first connecting, the current device steps become the session baseline
2. **Delta Calculation**: As you walk, the app calculates step deltas (new steps - previous steps)
3. **Read-Add-Write**: The app reads the current total from the input_number, adds the delta, and updates it
4. **Reconnection Handling**: Device counter resets don't affect the total - a new session starts automatically
5. **Persistent Storage**: All data persists in Home Assistant across restarts

### Service Calls

The integration uses the `input_number.set_value` service:

```yaml
service: input_number.set_value
data:
  entity_id: input_number.total_steps_all_time
  value: 12345  # New total value
```

## Home Assistant Dashboard Examples

### Basic Entity Cards

```yaml
# Total steps (all time)
type: entity
entity: input_number.total_steps_all_time
name: Total Steps

# Today's steps
type: entity
entity: sensor.daily_steps
name: Steps Today

# This week's steps  
type: entity
entity: sensor.weekly_steps
name: Steps This Week
```

### Statistics Graph

```yaml
type: statistics-graph
entities:
  - sensor.total_steps
period: day
stat_type: change
title: Daily Step Trend
```

### Gauge for Daily Progress

```yaml
type: gauge
entity: sensor.daily_steps
min: 0
max: 10000
name: Daily Progress
needle: true
severity:
  green: 8000
  yellow: 5000
  red: 0
```

### Step Goal Card

```yaml
type: custom:mushroom-entity-card
entity: sensor.daily_steps
name: Daily Steps
icon: mdi:walk
primary_info: state
secondary_info: >
  {% set goal = 10000 %}
  {% set current = states('sensor.daily_steps') | int(0) %}
  {% set percent = (current / goal * 100) | round(0) %}
  {{ percent }}% of {{ goal }} goal
```

## Automations

### Daily Goal Notification

```yaml
automation:
  - alias: "Daily Step Goal Achieved"
    trigger:
      - platform: numeric_state
        entity_id: sensor.daily_steps
        above: 10000
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "🎉 Congratulations! You've reached your 10,000 step goal!"
          title: "Step Goal Achieved"
```

### Weekly Summary

```yaml
automation:
  - alias: "Weekly Step Summary"
    trigger:
      - platform: time
        at: "20:00:00"
      - platform: template
        value_template: "{{ now().weekday() == 6 }}"  # Sunday
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: >
            This week you walked {{ states('sensor.weekly_steps') }} steps!
            Total all-time: {{ states('input_number.total_steps_all_time') }} steps.
          title: "Weekly Step Summary"
```

## Manual Step Management

### Adding Steps via REST API

You can manually add steps using curl:

```bash
# Add 1000 steps to current total
curl -X POST \
  -H "Authorization: Bearer YOUR_LONG_LIVED_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "entity_id":"input_number.total_steps_all_time",
        "value":"{{ (states(\"input_number.total_steps_all_time\") | int(0)) + 1000 }}"
      }' \
  http://your-ha-url:8123/api/services/input_number/set_value
```

### Resetting Counters

To reset the total steps:

```yaml
service: input_number.set_value
data:
  entity_id: input_number.total_steps_all_time
  value: 0
```

To reset just daily steps (utility meters have reset services):

```yaml
service: utility_meter.reset
data:
  entity_id: sensor.daily_steps
```

## Troubleshooting

### Steps Not Syncing

1. **Check Connection**: Use "Test Connection" in GUI settings
2. **Verify Entity**: Ensure `input_number.total_steps_all_time` exists in HA
3. **Check Logs**: Look for error messages in the GUI console
4. **Token Validity**: Regenerate the long-lived access token if needed

### Incorrect Step Counts

1. **Manual Adjustment**: Set the input_number to the correct value in HA
2. **Session Reset**: Disconnect and reconnect the WalkingPad to reset the session
3. **Utility Meter Reset**: Reset daily/weekly counters if they seem wrong

### Console Debug Output

The GUI shows helpful debug information:

```
Session reset - device steps: 0
Adding 145 steps: 8234 -> 8379
Successfully updated input_number.total_steps_all_time to 8379 steps
Adding 67 steps: 8379 -> 8446
Device step reset detected: 0 < 67
Session reset - device steps: 0
```

## Benefits of This Approach

1. **Reliability**: Input numbers persist across HA restarts
2. **Flexibility**: Easy to manually adjust totals when needed
3. **Statistics**: Proper `state_class` enables HA statistics integration
4. **Automation**: Utility meters provide automatic period tracking
5. **Dashboard**: Rich dashboard possibilities with proper metadata
6. **API Access**: Easy to integrate with other systems via HA's REST API

## Migration from Old Setup

If you were using the old sensor-based approach:

1. Note your current total steps from the old sensor
2. Set up the new input_number and template sensors as above
3. Set the input_number to your noted total value
4. Update the GUI configuration to use the new entity ID
5. Remove or ignore the old sensor - it will stop updating

The new approach is more robust and provides better integration with Home Assistant's ecosystem. 