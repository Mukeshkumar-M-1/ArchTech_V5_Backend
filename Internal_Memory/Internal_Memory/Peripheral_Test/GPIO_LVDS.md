# GPIO/LVDS Test Specification

| Test cases | Description |
|---|---|
| **GPIO/LVDS Test** | Validates GP Input channels and GP Output channels considering input and output channels are connected directly. Walking ones test shall be carried out for 'n' number of input and output pair channels (Test Patterns for 3-bit IO check: 000, 001, 010, 100, 111). Walking zeros test shall be carried out for 'n' number of input and output pair channels (Test Patterns for 3-bit IO check: 111, 110, 101, 011, 000). If the written pattern on output channels and read pattern on input channels are the same, test is PASS, otherwise FAIL. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.