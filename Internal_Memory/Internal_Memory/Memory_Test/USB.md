# USB Test Specification

| Test cases | Description |
|---|---|
| **Read/Write Test** | Validates read/write operations on the USB device. **1. Creation:** Mounts the USB memory stick partition in the mount directory using the command used for mounting the device. If mount fails, return FAILURE. If device is mounted successfully, creates a file in the USB device and verifies the read/write operations on that file. If both written data and read data are the same, test is PASS, otherwise FAIL. **2. Deletion:** Deletes the above created file from the USB device. If the file is deleted successfully, test is PASS, otherwise FAIL. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.