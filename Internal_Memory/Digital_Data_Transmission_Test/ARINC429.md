# ARINC 429 Test Specification

| Test cases | Description |
|---|---|
| **ARINC429 Internal Loop Back Test** | Performed with a single ARINC429 channel. One ARINC429 data message with a fixed label number shall be transmitted and received by the receiver and validated. If RX and TX data are the same, test is PASS, otherwise FAIL. |
| **ARINC429 Connector Level Loop Back Test** | Performed with a single ARINC429 channel and dummy receiver channel (if hardware provision available). One ARINC429 data message with a fixed label number shall be transmitted and received by the receiver and validated. If RX and TX data are the same, test is PASS, otherwise FAIL. |
| **ARINC429 External Loop Back Test** | Performed between 2 ARINC429 channels. Data to be transmitted shall be labeled as per protocol. Both Tx and Rx channels shall be configured and data shall be transmitted from Tx to Rx. If both transmitted and received data are the same, test is PASS, otherwise FAIL. To be tested in both scrambled and unscrambled mode if applicable. |
| **ARINC429 Label Matching** | Tx transmits all labels and in RX, a table is created for its labels — ensure messages with labels stored in the Rx table are correctly received. **Note:** Based on the feature available on the system. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.