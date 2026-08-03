# Display Backlight Temperature Control Test Specification

| Test cases | Description |
|---|---|
| **Display Backlight Temperature Control Test** | Display head shall control the display backlight temperature by reducing the display brightness by 10% for every 1°C raise in Display backlight temperature. If the Display backlight temperature is within the threshold, the previous set brightness shall be restored by the display. This test case shall be done at board level. External voltage shall be injected in the Display Backlight temperature channel and the variations in display brightness shall be monitored. Inject the voltage equivalent to threshold temperature (90°C) and monitor the display brightness. Current Display Brightness (%) value will keep on decreasing by 10% until the value reaches 10% and then it will decrease to 5%. Inject the voltage equivalent to threshold temperature (88°C) and monitor the display brightness. The previous set brightness shall be set by the display head. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.