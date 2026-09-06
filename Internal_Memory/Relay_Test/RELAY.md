# Relay Test Specification

| Test cases | Description |
|---|---|
| **Health Check** | Validates Relay Input channels and Relay Output channels considering input and output channels are connected directly. Walking ones test shall be carried out for 'n' number of input and output pair channels (Test Patterns for 3-bit IO check: 000, 001, 010, 100, 111). Walking zeros test shall be carried out for 'n' number of input and output pair channels (Test Patterns for 3-bit IO check: 111, 110, 101, 011, 000). If the written pattern on output channels and read pattern on input channels are the same, test is PASS, otherwise FAIL. |
| **Performance / Load Check** | Applicable for relays used for switching power supplies — pro-to modules only. Validates relay channel(s) considering relay outputs are directly connected to a digital input signal. Each relay channel shall be set HIGH and same shall be read back from latch memory (if available). Digital Input channel data shall be read and if both values are the same, test is PASS, otherwise FAIL. This shall be repeated by setting relay output to LOW. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.