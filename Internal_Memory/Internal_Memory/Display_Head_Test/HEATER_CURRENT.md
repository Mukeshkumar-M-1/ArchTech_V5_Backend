# Heater Current Test Specification

| Test cases | Description |
|---|---|
| **Heater Current Test** | Reads the display head LCD temperature for 3 times and calculates the median of the samples. Validates the Display Head LCD Temperature within the range; if it is not within the range, return failure. If display head LCD temperature is less than Display Head LCD Maximum Temperature: a) Switch On the Heater, b) Read the ADC value of Heater current, c) Switch OFF the Heater, d) Convert the Heater current value from ADC Value to engineering units. Compare the Heater current value against the tolerance value stored in non-volatile memory. **Note:** Display Head LCD Maximum Temperature shall be configurable. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.