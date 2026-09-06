# Ethernet Test Specification

| Test cases | Description |
|---|---|
| **Ethernet Ping Test** | Performed between 2 ports of different systems or the same system (loop back) considering both ports are connected with LAN cable. Carried out using ping test to target port IP address from host port. If ping test passes, test is PASS, otherwise FAIL. **Note:** Preloaded data will be transferred by the operating system as part of the Ethernet ping test. |
| **Ethernet Socket Test** | Performed between 2 ports of different systems considering both ports are connected with LAN cable. Socket communication shall be established between these 2 systems and data shall be transmitted from client system to server system. The server system transmits the received data back to client. If the transmitted and received data are the same, test is PASS, otherwise FAIL. **Note:** Socket test is only at ATP level. |
| **Ethernet PHY Loop Back Test** | Validates data transfer through the Ethernet adapter within the system. Tx and Rx channels of the same port shall be looped back externally and test data shall be transmitted from Tx to Rx. If the transmitted and received data are the same, test is PASS, otherwise FAIL. **Note:** If there is no OS, then PHY level test is applicable. |
| **Ethernet Data Transfer Rate Test** | Calculates the data transfer rate of Ethernet by transferring a bulk amount of data through Ethernet. **Note:** This test can be done with a separate utility if there is a requirement. |

> **Note:** Descriptions may be modified as per the specific requirement criteria.