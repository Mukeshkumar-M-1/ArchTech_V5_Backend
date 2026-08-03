# ADC-DAC Test Specification

| Test cases | Description |
|---|---|
| **ADC-DAC Test** | Qualifies ADC channels considered that ADC channels and source channels are calibrated. Option to select DC input range, input step size, and output tolerance may be provided and test shall be automatic. Even in case of PASS, tolerance with which it fails to be tested and logged — to know the margin available in fixing the final tolerance. ADC channel shall be fed with various voltage levels within its range by a DAC channel / voltage source (AC / DC). ADC channel shall acquire the data in configured frequency for the configured number of samples. If the sampled data or computed data from the samples is within the tolerance limits, test is PASS, otherwise FAIL. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.