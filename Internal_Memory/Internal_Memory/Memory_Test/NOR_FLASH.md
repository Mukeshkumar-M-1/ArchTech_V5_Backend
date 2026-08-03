# NOR Flash Test Specification

| Test cases | Description |
|---|---|
| **Upload Board Information Test** | Validates proper initialization of the flash device. The flash device shall be read and compared with the pre-loaded value to ensure proper initialization. PASS if both values are the same, otherwise FAIL. **Note:** Information shall be loaded only once for each board. |
| **Checksum Test** | Checks data integrity in the flash device. **Default Checksum Test:** Data is read from a fixed area/locations, checksum is computed, and compared against the pre-loaded/known checksum value. **User Checksum Test:** Data is read from a memory range as specified by the user, checksum is computed, and compared against the pre-loaded/known checksum value. PASS if the stored and computed checksums are the same, otherwise FAIL. |
| **Read/Write Test** | Validates read, write, and verify operation of the flash device. The address, number of locations, and data to write will be provided by the user. Counter data can also be written from the start address to the number of locations given by the user. Provision is also given to log the read data into a file and program the memory device from a user-specified file. For example, based on the test start address and number of locations, write 0xAA/counter data and read back. PASS if both values are the same, otherwise FAIL. |
| **Erase Sector/Page/Device Test** | Erases the sector, page, or entire device in flash based on user selection. |
| **Upload/Download/Verify Code Test** | Provides provision to upload code/data into flash from a file, download code/data from flash and save to a file (if possible). Verifies the code/data in flash with the available output file (if possible). If upload/download succeeds, checksum of the code shall be displayed (if possible). |
| **Full Memory Test** | Validates read, write, and verify operation in the flash device. All memory locations shall be written with 0xAA and read back. PASS if both values are the same, otherwise FAIL. **Note:** This should be done with a separate utility. |
| **Digital Signature Test** | Qualifies authenticity of the flash device. A read operation shall be performed to get the digital signature stored by the manufacturer. If the read signature is the expected value, test is PASS, otherwise FAIL. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.
