# rgbmatrix-flightoverhead

Project for displaying information about overhead flights on an RGB LED matrix using data from dump1090-fa (ADS-B flight tracking software).

## Installation

### Prerequisites
- Raspberry Pi (or compatible device) with an RGB LED matrix connected
- dump1090-fa installed and running (provides flight data via `/run/dump1090-fa/aircraft.json`)
- Python 3.x
- Adafruit RGB LED Matrix library installed

### Steps
1. Clone this repository:
   ```
   git clone https://github.com/yourusername/rgbmatrix-flightoverhead.git
   cd rgbmatrix-flightoverhead
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install the Adafruit RGB LED Matrix library:
   Follow the instructions at https://github.com/hzeller/rpi-rgb-led-matrix
   or just run `sudo apt-get install python-dev-is-python3 python3-pil cython3`
   and `pip install git+https://github.com/hzeller/rpi-rgb-led-matrix`

4. Configure settings:
   - Copy `settings_template.json` to `settings.json`
   - Edit `settings.json` with your location coordinates, AeroAPI key, and preferences

5. Install and enable the systemd service:
   ```
   sudo cp rgbmatrix-flightoverhead.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable rgbmatrix-flightoverhead
   sudo systemctl start rgbmatrix-flightoverhead
   ```

## Files Description

- `show_flights.py`: Main Python script that reads flight data and displays it on the RGB matrix
- `settings_template.json`: Template configuration file with location settings and display options
- `test.json`: Sample flight data for testing purposes
- `rgbmatrix-flightoverhead.service`: Systemd service file for running the display automatically
- `LICENSE`: Project license
- `README.md`: This file
