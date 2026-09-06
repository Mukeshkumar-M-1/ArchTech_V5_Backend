# EEPROM Test Specification

| Test cases | Description |
|---|---|
| **Data Retention Test** | Qualifies authenticity of the memory device. A read operation shall be performed to get the digital signature stored by the manufacturer. If the read signature is the expected value, test is PASS, otherwise FAIL. |
| **Read/Write Test** | Validates read, write, and verify operation of the memory device. The address, number of locations, and data to write will be provided by the user. Counter data can also be written from the start address to the number of locations given by the user. Provision is also given to log the read data into a file and program the memory device from a user-specified file. For example, based on the test start address and number of locations, write 0xAA/counter data and read back. PASS if both values are the same, otherwise FAIL. |
| **Write Protection Test** | Verifies the write protection enable/disable feature of the memory device. The sequence of commands/values given in the data sheet should be followed to enable/disable write protection. For example, selected memory offsets shall be written with specific data/commands like 0xFF/0x55. **Note:** Write protection enable/disable feature must be supported by the memory device. |
| **Full Memory Test** | Validates read, write, and verify operation in the EEPROM. All memory locations shall be written with 0xAA and read back. PASS if both values are the same, otherwise FAIL. **Note:** This should be done with a separate utility. |
| **Checksum Test** | Checks data integrity in the memory device. **Default Checksum Test:** Data is read from a fixed area/locations, checksum is computed, and compared against the pre-loaded/known checksum value. **User Checksum Test:** Data is read from a memory range as specified by the user, checksum is computed, and compared against the pre-loaded/known checksum value. PASS if the stored and computed checksums are the same, otherwise FAIL. |
| **Upload Board Information Test** | Validates proper initialization of the flash device. The flash device shall be read and compared with the pre-loaded value to ensure proper initialization. PASS if both values are the same, otherwise FAIL. **Note:** Information shall be loaded only once for each board. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.


