# Internal Memory Test Specifications Index

This directory contains test specifications for qualifying various memory devices, peripherals, communication interfaces, and other hardware components. Each file follows a standard format: a level-1 heading, a markdown table of test cases with descriptions, and a closing note blockquote.

## Memory Type Files

| File | Memory Type | Test Cases |
|---|---|---|
| [DDR.md](Memory_Test/DDR.md) | FPGA DDR (DDR, DDR4, DDR5, LPDDR) | Address Bus, Data Bus, Device, Full Memory, Read/Write |
| [EEPROM.md](Memory_Test/EEPROM.md) | EEPROM | Data Retention (digital signature), Read/Write (0xAA/counter), Write Protection, Full Memory (separate utility), Checksum (default + user), Upload Board Information |
| [FPGA_DDR.md](Memory_Test/FPGA_DDR.md) | FPGA DDR | Address Bus, Data Bus, Device, Full Memory, Read/Write |
| [FPGA_REGISTER.md](Memory_Test/FPGA_REGISTER.md) | FPGA Registers | Board ID check + register read/write (0xAA55 for 16-bit, 0xA5 for 8-bit) |
| [MRAM.md](Memory_Test/MRAM.md) | MRAM | Data Bus, Address Bus, Device, Full Memory (emulator), Read/Write (MCU debugging) |
| [NAND_FLASH.md](Memory_Test/NAND_FLASH.md) | NAND Flash | Upload Board Information, Checksum (default + user), Read/Write, Erase Sector/Page/Device, Upload/Download/Verify Code, Full Memory, Digital Signature |
| [NOR_FLASH.md](Memory_Test/NOR_FLASH.md) | NOR Flash | Upload Board Information, Checksum (default + user), Read/Write, Erase Sector/Page/Device, Upload/Download/Verify Code, Full Memory, Digital Signature |
| [NVSRAM.md](Memory_Test/NVSRAM.md) | NVSRAM | Data Retention (digital signature), Read/Write (0xAA/counter), Write Protection, Full Memory (separate utility), Checksum (default + user), Upload Board Information, Store and Recall |
| [SDRAM.md](Memory_Test/SDRAM.md) | SDRAM (SDRAM, SRAM, DRAM) | Data Bus, Address Bus, Device, Full Memory (emulator), Read/Write (MCU debugging) |
| [SATA.md](Memory_Test/SATA.md) | SATA/SSD/PATA/SD Card | Read/Write (mount, create file with 32-bit counter, delete), Data Transfer Rate |
| [USB.md](Memory_Test/USB.md) | USB Memory Stick | Read/Write (mount, create file, verify, delete) |

## Communication Test Files

| File | Communication Type | Test Cases |
|---|---|---|
| [ETHERNET.md](Communication_Test/ETHERNET.md) | Ethernet | Ping Test (IP connectivity), Socket Test (client-server data transfer), PHY Loop Back Test (Tx-Rx verification), Data Transfer Rate Test |
| [PCIe.md](Communication_Test/PCIe.md) | PCIe | Enumeration Test (Device/Vendor ID), Read/Write Test (memory partition file operations) |
| [RS232_RS422_RS485.md](Communication_Test/RS232_RS422_RS485.md) | RS232/RS422/RS485 | Loop Back Test (256-byte buffer), Echo Back Test (bidirectional transfer), Parity Error Simulation (odd/even mismatch), Format Error Simulation (data bit mismatch) |
| [SFPDP.md](Communication_Test/SFPDP.md) | SFPDP | SFPDP Test (external/internal loop back data transfer) |

## Digital Data Transmission Test Files

| File | Protocol Type | Test Cases |
|---|---|---|
| [1553B.md](Digital_Data_Transmission_Test/1553B.md) | MIL-STD-1553B | Self Test (chip self-test or Data/Address Bus/Memory/Interrupt), Loop Back Test (BC-RT-MT data transfer with sub-address monitoring) |
| [ARINC429.md](Digital_Data_Transmission_Test/ARINC429.md) | ARINC 429 | Internal Loop Back (single channel), Connector Level Loop Back (with dummy receiver), External Loop Back (2-channel), Label Matching (Rx table validation) |
| [ARINC708.md](Digital_Data_Transmission_Test/ARINC708.md) | ARINC 708 | ARINC 708 Test (1600-bit frame transfer, multiple frame provision) |
| [ARINC717.md](Digital_Data_Transmission_Test/ARINC717.md) | ARINC 717 | ARINC 717 Test (4 sub-frame, 38-1K words per sub-frame) |

## Analog and Digital Module Test Files

| File | Module Type | Test Cases |
|---|---|---|
| [ADC_DAC.md](Analog_and_Digital_Module_Test/ADC_DAC.md) | ADC/DAC | ADC-DAC Test (calibrated channel validation, voltage level feeding, sampling with tolerance, DC input range, step size, tolerance logging) |
| [DIO.md](Analog_and_Digital_Module_Test/DIO.md) | Digital I/O | DIO Test (DI-DO channel validation, Walking Ones: 000→001→010→100→111, Walking Zeros: 111→110→101→011→000) |

## Character LCD Test Files

| File | LCD Type | Test Cases |
|---|---|---|
| [CHARACTER_LCD.md](Character_LCD_Test/CHARACTER_LCD.md) | Character LCD | Character LCD Test (block character "▓" sequential drawing across rows and columns, manual observation) |

## Audio Test Files

| File | Audio Type | Test Cases |
|---|---|---|
| [AUDIO.md](Audio_Test/AUDIO.md) | Audio Message | Audio Test (message number selection, repeat count, delay between messages, volume adjustment) |

## Relay Test Files

| File | Relay Type | Test Cases |
|---|---|---|
| [RELAY.md](Relay_Test/RELAY.md) | Relay Channel | Health Check (Walking Ones/Zeros on relay I/O pairs), Performance/Load Check (HIGH/LOW state validation with latch memory readback) |

## Peripheral Test Files

| File | Peripheral Type | Test Cases |
|---|---|---|
| [ALTIVEC.md](Peripheral_Test/ALTIVEC.md) | Altivec Engine | Vector Integer Operations, Vector Floating Point Operations, Vector Shift Operations, Vector Bit-wise Operations |
| [COUNTER.md](Peripheral_Test/COUNTER.md) | Counter | Counter Test (interrupt count validation, 60-second duration, +/-1 tolerance) |
| [DMA.md](Peripheral_Test/DMA.md) | DMA Controller | DMA Test (PCI-SDRAM, PCI-PCI, SDRAM-SDRAM data transfer timing and verification) |
| [GPIO_LVDS.md](Peripheral_Test/GPIO_LVDS.md) | GPIO/LVDS | GPIO/LVDS Test (Walking Ones/Zeros pattern on I/O pairs, 3-bit test: 000,001,010,100,111 / 111,110,101,011,000) |
| [PCI.md](Peripheral_Test/PCI.md) | PCI Bus | PCI Enumeration Test (Device/Vendor ID matching against expected device list) |
| [PROCESSOR.md](Peripheral_Test/PROCESSOR.md) | Processor | Arithmetic (Add/Sub/Mul/Div), Shift (Left/Right), Logical (AND/OR/NOT), Floating Point Operations |
| [ROCKETIO.md](Peripheral_Test/ROCKETIO.md) | Rocket IO | Rocket IO Test (counter data transmission/reception, data rate calculation based on application requirement) |
| [RTC.md](Peripheral_Test/RTC.md) | Real Time Clock | RTC Test (date/time progression, 31/12/1999 year-end rollover, 28/02 leap year validation, +/-1 second tolerance) |
| [SRIO.md](Peripheral_Test/SRIO.md) | SRIO | SRIO Enumeration Test (generic RIO device/vendor ID enumeration count validation) |
| [TEMPERATURE.md](Peripheral_Test/TEMPERATURE.md) | Temperature Sensor | Temperature Sensor Test (read value validation against configurable low/high limits) |
| [TIMER.md](Peripheral_Test/TIMER.md) | Timer | Timer Test (dual-timer configuration, interrupt count validation, +/-1 tolerance) |
| [VOLTAGE.md](Peripheral_Test/VOLTAGE.md) | Voltage Monitoring | Voltage Monitoring Test (ADM input channel voltage reading, manual verification) |
| [WATCHDOG.md](Peripheral_Test/WATCHDOG.md) | Watch Dog Timer | Interrupt Test (timeout counter, +/-1 tolerance), Reset Test (system reset after configured timeout), Trigger Test (reload feature validation) |

## Display Head Test Files

| File | Display Test Type | Test Cases |
|---|---|---|
| [AMBIENT_LIGHT_SENSOR.md](Display_Head_Test/AMBIENT_LIGHT_SENSOR.md) | Ambient Light | Ambient Light Sensor Test (3-sample ADC read, median computation, configurable range validation) |
| [BEZEL_KEY_FUNCTIONAL.md](Display_Head_Test/BEZEL_KEY_FUNCTIONAL.md) | Bezel Key Function | Bezel Key Functional Test (press/release status monitoring, green/red indicators, Key 1 to Key n validation) |
| [BEZEL_KEY_ILLUMINATION.md](Display_Head_Test/BEZEL_KEY_ILLUMINATION.md) | Bezel Key Light | RS232/RS422 Brightness Control (25/50/75/100% steps, uniformity check, software panel readback), Analog Input Brightness Control (0-28V variation) |
| [DISPLAY_BACKLIGHT.md](Display_Head_Test/DISPLAY_BACKLIGHT.md) | Display Backlight | Display Backlight Test (Day/NVIS mode current/voltage reading, 3-sample median, configurable tolerance validation) |
| [DISPLAY_BACKLIGHT_TEMP.md](Display_Head_Test/DISPLAY_BACKLIGHT_TEMP.md) | Backlight Temperature | Display Backlight Temperature Control Test (10% brightness reduction per 1°C raise, 90°C threshold injection, 88°C restoration, board-level voltage injection) |
| [DISPLAY_BRIGHTNESS.md](Display_Head_Test/DISPLAY_BRIGHTNESS.md) | Display Brightness | Manual Mode Test (25/50/75/100% luminance steps, Day/Night/NVIS), Auto Mode Test (ambient light sensor response, offset -50 to 50, time constant 9000) |
| [DISPLAY_BRIGHTNESS_MODE.md](Display_Head_Test/DISPLAY_BRIGHTNESS_MODE.md) | Brightness Mode | Display Brightness Mode Switching Test (LCD Back light Driver health check, automatic Day↔NVIS failover on invalid data) |
| [DISPLAY_TEMPERATURE.md](Display_Head_Test/DISPLAY_TEMPERATURE.md) | Display Temperature | Display Head LCD Temperature Test (3-sample read, median computation, configurable range validation) |
| [HEATER_CONTROL.md](Display_Head_Test/HEATER_CONTROL.md) | Heater Control | Manual Heater ON (DP_SDG_COM_DISP_07_HTRCURRENT_12), Manual Heater OFF (debugging), Automatic Heater Control (-5°C ON, +5°C OFF, cold chamber/board-level voltage injection) |
| [HEATER_CURRENT.md](Display_Head_Test/HEATER_CURRENT.md) | Heater Current | Heater Current Test (3-sample LCD temperature median, heater ON/OFF ADC current measurement, engineering units conversion, non-volatile tolerance comparison) |
| [ROTARY_ENCODER.md](Display_Head_Test/ROTARY_ENCODER.md) | Rotary Encoder | Rotary Encoder Position Test (1 to N steps clockwise/anti-clockwise, RS422 transmission to Host, step-position matching) |

## Common Test Case Patterns

### Shared Across Multiple Types

- **Data Bus Test** — Walking 1's and Walking 0's on 32-bit data (DDR, FPGA_DDR, MRAM, SDRAM)
- **Address Bus Test** — Pattern and anti-pattern across addresses (DDR, FPGA_DDR, MRAM, SDRAM)
- **Device Test** — Incremental counter + inverted counter verification (DDR, FPGA_DDR, MRAM, SDRAM)
- **Full Memory Test** — All locations written with 0xAA/counter data, read back and verified (DDR, FPGA_DDR, MRAM, SDRAM, EEPROM, NVSRAM, NAND/NOR Flash)
- **Read/Write Test** — User-provided address, locations, and data pattern; read-back verify (all memory types)
- **Checksum Test** — Default (fixed area) and User (custom range) checksum verification (EEPROM, NVSRAM, NAND/NOR Flash)
- **Upload Board Information Test** — Validates flash initialization against pre-loaded value (EEPROM, NVSRAM, NAND/NOR Flash)
- **Data Retention Test** — Manufacturer digital signature verification (EEPROM, NVSRAM)
- **Loop Back Test** — Tx-Rx data transfer verification (RS232/422/485, Ethernet PHY, SFPDP, 1553B, ARINC 429)
- **Walking Ones/Zeros** — Sequential bit patterns on I/O channels (GPIO/LVDS, DIO, Relay)
- **Enumeration Test** — Device/Vendor ID matching against expected list (PCI, SRIO, PCIe)
- **Sensor Validation** — Read value comparison against configurable limits (Temperature, Voltage, Ambient Light, Display Backlight)
- **Counter/Interrupt Validation** — Expected count comparison with tolerance (Timer, Counter, Watch Dog Timer)
- **Color Pattern Validation** — Visual confirmation of display output (Display, Character LCD)
- **Data Transfer Rate** — Bulk data transmission speed measurement (Rocket IO, DMA, Ethernet, SATA)

### Memory-Type-Specific

- **Write Protection Test** — Enable/disable write protection via data sheet commands (EEPROM, NVSRAM)
- **Store and Recall Test** — NVSRAM-specific store/recall of counter data (NVSRAM only)
- **Erase Sector/Page/Device Test** — Flash sector/page/full device erase (NAND/NOR Flash)
- **Upload/Download/Verify Code Test** — File-based code upload/download with checksum (NAND/NOR Flash)
- **Digital Signature Test** — Manufacturer signature read verification (NAND/NOR Flash)
- **FPGA Register Read/Write Test** — Board ID check + register data write/read (FPGA_REGISTER)

### Display-Specific

- **Brightness Mode Switching** — Automatic Day↔NVIS failover (Display Brightness Mode)
- **Backlight Temperature Control** — 10% brightness reduction per 1°C raise (Display Backlight Temp)
- **Heater Control** — -5°C ON, +5°C OFF thresholds (Display Heater Control)
- **Rotary Encoder** — Position step validation, RS422 transmission (Display Rotary Encoder)
- **Bezel Key Illumination** — Software panel and analog input brightness control (Display Bezel Key)
