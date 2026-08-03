# RTC Test Specification

| Test cases | Description |
|---|---|
| **RTC Test** | Carried out with settings at 31/12/1999 23:59:52 and 28/02/abcd 23:59:52 where 'a'/'b' = 0 to 9 and 'cd' is divisible by 4 (leap year validation). Date and time shall be set in RTC and read after a predefined time gap (e.g., 8 seconds). If the second read time is updated with the addition of the expected seconds, test is PASS, otherwise FAIL. **Note:** The test result with a tolerance of +/-1 second in addition to the expected seconds will be considered as PASS. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.