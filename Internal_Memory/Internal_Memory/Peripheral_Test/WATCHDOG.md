# Watch Dog Timer Test Specification

| Test cases | Description |
|---|---|
| **Interrupt Test** | WDT configured in interrupt mode where timeout generates interrupt and a counter is incremented within a preselected time. WDT shall be configured in interrupt mode, timeout value set between 0x1 to 0xFFFFFFFF (depends upon the chip), and WDT enabled. WDT interrupt count value shall be read and compared with the expected count value. If count value is greater than or equal to the expected count, test is PASS, otherwise FAIL. **Note:** The test result with tolerance of +/-1 count in addition to the expected counts will be considered as PASS. |
| **Reset Test** | System is reset when WDT times out. WDT shall be configured in reset mode, timeout value set between 1 msec (0x1) to X msec (0xFFFFFFFF) (depends upon the chip), and WDT enabled. Confirm that the system is reset after the set timeout value and declare as PASS, otherwise FAIL. |
| **Trigger Test** | Tests the WDT reload feature. WDT shall be configured in reset mode, timeout value (X msecs) set between 1 to 0xFFFFFFFF (depends upon the chip), and WDT enabled. After (X - 10) msecs, generate the trigger for WDT reload. If the system is running continuously for predefined Y seconds, test is PASS, otherwise FAIL. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.