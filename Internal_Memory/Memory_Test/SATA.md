# SATA/SSD/PATA/SD Card Test Specification

| Test cases | Description |
|---|---|
| **Read/Write Test** | Validates read/write operations on the mounted device. **1. Creation:** Mounts the SATA device at the specified mount point and creates a file in the mounted partition, writing 32-bit counter data up to 256KB. Reads the file content from the device and compares it with the written data. If both written and read data are the same, test is PASS, otherwise FAIL. **Note:** Creation can be checked manually. **2. Deletion:** Deletes the above created file from the SATA device. If the file is deleted successfully, test is PASS, otherwise FAIL. |
| **Data Transfer Rate Test** | Calculates the data transfer rate of the SATA device by transferring a bulk amount of data to and from the device. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.