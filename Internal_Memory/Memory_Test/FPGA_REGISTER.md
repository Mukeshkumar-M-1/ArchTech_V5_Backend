# FPGA Register Read/Write Test

| Test cases | Description |
|---|---|
| **FPGA Register Read/Write Test** | Reads the board ID to verify board presence. If board ID is read successfully, performs the read/write test; otherwise returns failure. Writes predefined data (0xAA55 for 16-bit registers, 0xA5 for 8-bit registers) into the specified FPGA register and reads back the data. PASS if both written and read data are the same, otherwise FAIL. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.