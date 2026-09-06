# Heater Control Test Specification

| Test cases | Description |
|---|---|
| **Manual Heater ON** | Heater current test shall be performed as per DP_SDG_COM_DISP_07_HTRCURRENT_12. |
| **Manual Heater OFF** | Heater shall be switched off manually until Automatic Heater control command is received from the Host. This shall be used for debugging purpose. |
| **Automatic Heater Control** | Heater shall be switched on when the LCD temperature reaches -5°C and switched off when the LCD temperature reaches +5°C. **Note:** Automatic Heater Control test shall be done at system level when the unit is kept inside a cold chamber. At board level, this can be validated by feeding voltages (according to corresponding temperature) to the LCD temperature channel. |

> **Note:** Descriptions may be modified as per the specific requirement criteria. Option to select Heater Control (ON/OFF/Auto) shall be provided to user.