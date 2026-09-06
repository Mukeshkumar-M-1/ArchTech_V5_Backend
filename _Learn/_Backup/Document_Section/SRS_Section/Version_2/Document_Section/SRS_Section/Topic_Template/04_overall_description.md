## 2. OVERALL DESCRIPTION

### 2.1 Product Perspective

> \[!NOTE\]\
> Describe as a paragraph and also use sub-paragraph - (Detailed)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > DP-XMC-5049 shall be a XMC PCIe based video converter module using XILINX Kintex Ultrascale FPGA Supporting STANAG3350 / RGB / VGA, DVI, ARINC818 and PCIe Interfaces. It is a Single-Width Mezzanine Card with the primary XMC connector occupying connector location P15 and secondary XMC connector occupying connector location P16. Module Kintex Ultrascale FPGA is interfaced with two 32-bit 4GB DDR4 SDRAM controllers, 64MB SPI NOR configuration Flash & 256MB SPI NOR storage flash.
> >
> > The module supports DisplayPort video input from secondary XMC Connector which are electrically translated to the 3 no.s of TMDS level DP++/DVI outputs using DP to DP++/DVI splitter. The DP++ Video splitter shall be interfaced with a 2MB SPI NOR Flash.
> >
> > The module supports high speed communication interface such as PCIe on XMC primary connector for video raw data reception / transmission. The XMC Primary connector interfaces x8 PCIe lines from the carrier module. Module shall optionally support 3x ARINC 818 Transmitter(Tx) & 3x ARINC 818 Receiver(Rx) interfaces from the secondary XMC connector to the MGT bank of FPGA.
> >
> > The module support 1x single link DVI output via DVI equalizer interfaced from either FPGA or DP to DVI splitter to XMC secondary connector. The module shall additionally support 1x single link DVI output from DP to DVI splitter interfaced to the DVI Connector on the Front panel via DVI equalizer. Module shall also support 1x DVI output from DP to DVI splitter interfaced to the XMC secondary connector on the Front panel via DVI equalizer. Module shall support RGBHV / VGA / STANAG 3350 analog video standard output on XMC Secondary connector using Video encoder with recommended front end.
> >
> > Note: ARINC818, DVI & RGBHV/VGA are having FG mount options. Refer block diagram Figure 2.1 & FG configuration sheet for more details.
> >
> > \
> > Module shall support on board clock generation & power supply generation as per design requirements. Module shall be powered by 5V,3.3V & 3.3V-AUX via XMC Connector as per VITA 42 standard.

**Figure 2.1: Block Diagram**

> \[!NOTE\]
>
> Use NA

---

### 2.2 Product Functions

> \[!NOTE\]
>
> Describe as a paragraph and also use sub-paragraph - (Detailed)
>
> > \[!CAUTION\]
> >
> > Example: \
> > The DP-XMC-5049 module shall receive video through ARINC-818 RX channels and transmit processed video through ARINC-818 TX channels from the FPGA. The module shall transmit analog video in STANAG 3350B format through video encoder chips which is processed and transmitted by FPGA
> >
> > The module has a KTM5030 chip as 1:3 video splitter for transmitting digital video which is displayed through DVI ports and a micro-HDMI connector which will be displayed in a monitor. Configuring the KTM5030, EEPROM and DVI re-timer chips from on-board ARM based MCU(ATSAMD51) through I2C channels. EDID data written in EEPROM from MCU is read by KTM5030 as I2C master. The MCU shall be interfaced with host application(GUI) through USB for command, control and communication. The MCU has the provision to communicate with FPGA through QSPI.
> >
> > The module has temperature sensor for monitoring temperature to protect the modules from high or low temperature.

---

### 2.3 User Classes and Characteristics

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example: \
> > The different users of DP-XMC-5049 test application area Data patterns – SDG, HDD, production, QA team. The users are expected to test the product functionality of module.

---

### 2.4 Operating Environment

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The DP-XMC-5049 module testing has three software modules such as target application (DPXMC-5049), host application (Test PC) and firmware applications (ATSAMD51). The development and operating environment of each software modules are detailed in the below sections.

#### 2.4.1 Target Application

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The target application shall be executed in DP-VPX-0750 for accessing DP-XMC-5049 FPGA. The development and environment of target application are detailed below.

#### Table 2.1: Development Environment for Target Application

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Kernel
> > - Processor Architecture
> > - Compiler
> > - Programming Language
> > - RAM
> > - SATA NAND
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Fedora 22 Linux
> > - 4.0.4-301.fc22.x86_64
> > - x86_64
> > - GCC
> > - C Language
> > - 32 GB DDR4
> > - 64 GB

| S.NO | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

#### Table 2.2: Operating Environment for Target Application

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Kernel
> > - Processor Architecture
> > - Compiler
> > - Programming Language
> > - RAM
> > - SATA NAND
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Fedora 22 Linux
> > - 4.0.4-301.fc22.x86_64
> > - x86_64
> > - GCC
> > - C Language
> > - 32 GB DDR4
> > - 64 GB

| [S.No](http://S.NO) | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

#### 2.4.2 Host Application

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > It is a GUI based application shall be executed in test PC for establishing USB communication with MCU for command processing.

#### Table 2.3: Development Environment for Host Application

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Processor Architecture
> > - Programming Language
> > - IDE
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Windows 10
> > - x86
> > - C / C++ Language
> > - QT 5.14

| [S.No](http://S.NO) | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

#### Table 2.4: **Operating Environment for Host Application**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Processor Architecture
> > - Programming Language
> > - IDE
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Windows 10
> > - x86
> > - C / C++ Language
> > - QT 5.14

| [S.No](http://S.NO) | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

---

### 2.5 Design and Implementation Constraints

> \[!IMPORTANT\]
>
> Content should be present like Example, Mention it as NA
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The design and Implementation constraints are detailed in the section
> >
> > 1. Driver (.ko) and shared object (.so) of DP-XMC-5049 is required for implementation of target application.
> >
> >
> > 2) The software packages are detailed in the **Table 2.5** are required for implementation firmware application.
> >
> > 3) The driver and library (.dll) of QSerialPort is required for implementation host application.

---

### 2.6 User Documentation

> \[!IMPORTANT\]
>
> Content should be present like Example, Otherwise Mention it as NA
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The following document shall be prepared for DP-XMC-5049 test application as part Software Development Life Cycle
> >
> > 1. DP-XMC-5049 Software Requirement Specification (SRS)
> >
> > 2. DP-XMC-5049 Software Design Document (SDD)
> >
> > 3. DP-XMC-5049 Version Definition Document (VDD)

---

### 2.7 Assumptions and Dependencies

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The design and development of the software depends on the hardware requirement document. Any changes in the requirement document will affect the design of software

#### 2.7.1 Assumptions

> \[!NOTE\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

#### 2.7.2 Dependencies

> \[!NOTE\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA/