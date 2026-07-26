# 3. EXTERNAL INTERFACE REQUIREMENTS

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The external interface requirements such as the user, hardware, software and communication interfaces are detailed in this section.

## 3.1 User Interfaces

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > - The firmware application software shall be interfaced with user through USB host application. User shall be able to choose the test case to be performed by clicking the options in GUI application.
> >
> > - The user has provision to provide inputs for EEPROM EDID write operation, DVI re-timer configuration, KTM5030 configuration and QSPI communication with FPGA.
> >
> > - Application shall consist of standard GUI layouts such as menu bar, action log, standard
> >
> >   buttons and other user-friendly controls.
> >
> > - Pop up message boxes shall be used to provide warning and error information to intimate the
> >
> >   user about the failures or other serious events.

---

## 3.2 Hardware Interfaces

> \[!NOTE\]
>
> Describe as a paragraph (1- 2 lines)
>
> > \[!CAUTION\]
> >
> > Example: The hardware interface in the DP-XMC-5049 module are listed in the below **Table 3.1**.

**Table 3.1 : Hardware Interfaces**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Device → Refers the Example
>
> > \[!CAUTION\]
> >
> > Device → Example:
> >
> > - ARINC818
> > - FPGA
> > - Micro-controller
> > - Temperature Sensor
> > - Storage Flash
> > - DVI Re-Timer
> > - Micro HDMI Connector
> > - Configuration Flash
> > - KTM5030
>
> - Interface → Refers the Example
>
> > \[!CAUTION\]
> >
> > Interface → Example:
> >
> > - FO
> > - PCIe
> > - USB 2.0
> > - I2C
> > - SPI
> > - HDMI
> > - SPI
> > - DP
>
> - Description → Refers the Example
>
> > \[!CAUTION\]
> >
> > Description → Describe it as (2-3 Lines)
> >
> > Example:
> >
> > Fibre optic cables are interface to transmit and receive the digital ARINC818 video data.

| S.No | Device | Interface | Description |
| --- | --- | --- | --- |
| 1 | \[Device Name\] | \[Interface\] | \[Description for the device\] |
|   |   |   |   |

---

## 3.3 Software Interfaces

> \[!NOTE\]
>
> Describe as a paragraph (1- 2 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The software interface in the DP-XMC-5049 test application are detailed in the below sub-sections.

### 3.3.1 Software interface in Target Application

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

### 3.3.2 Software Interface in Host Application

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

### 3.3.3 Software Interface in Firmware Application

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

---

## 3.4 Communications Interfaces

> Refer example for content formation
>
> Example:
>
> The communication interfaces in the DP-VPX-0750 test application are detailed below:
>
> - PCIe shall be used for establishing communication between the SBC (DP-VPX-0750) and the FPGA (Xilinx Kintex Ultrascale).
>
> - USB is used for establishing communication between the MCU and the Test PC.
>
> - KTM5030 establishes communication with the Test PC through the I2C / UART / AUX interface.