---
sub_category: Power
parent_category: Hardware
total_requirements: 8
---

# Power Requirements

## Summary

This sub-category defines the electrical power specifications for the module, including required supply rails (5V, 3.3V, 3.3V-AUX), typical current consumption, and total power dissipation limits. It also mandates compliance with VITA 42 standards for power delivery via the XMC connector and specifies methods for measuring and monitoring voltage levels and power analysis.

## Requirements

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0010 | High | Module shall support on board clock generation and power supply generation as per design requirements. Module shall be powered by 5V, 3.3V and 3.3V-AUX via XMC Connector as per VITA 42 standard. | [HAR-0010.md](../requirements/HAR-0010.md) |
| HAR-0013 | High | DP-XMC-5049-HRS-0017: XMC Primary Connector requirements: 5V DC supply; 3.3V DC supply; 3.3V-AUX DC supply; Module JTAG Interface; PCIe REFCLK; 1x x8 PCIe Gen 3 link from FPGA MGT bank. | [HAR-0013.md](../requirements/HAR-0013.md) |
| HAR-0029 | Normal | DP-XMC-5049-HRS-004 Voltage Module supply rails: • +5V • +3.3V • +3.3V-AUX | [HAR-0029.md](../requirements/HAR-0029.md) |
| HAR-0030 | Normal | DP-XMC-5049-HRS-005 Current • 5V @ 2.99 A (TYP) • 3V @ 3.18 A (TYP) • 3.3V-AUX @ 0.002 A (TYP) | [HAR-0030.md](../requirements/HAR-0030.md) |
| HAR-0032 | Normal | Requirement ID: DP-XMC-5049-HRS-005; Requirement: The supply current shall be measured by power analysis of module components; Testing Plan: NA | [HAR-0032.md](../requirements/HAR-0032.md) |
| HAR-0033 | Normal | DP-XMC-5049-HRS-006 Power Dissipation • 15 W (TYP) | [HAR-0033.md](../requirements/HAR-0033.md) |
| HAR-0034 | Normal | DP-XMC-5049-HRS-006 Power dissipation shall be measured by power analysis of module components | [HAR-0034.md](../requirements/HAR-0034.md) |
| HAR-0041 | Normal | DP-XMC-5049-HRS-004: All voltages shall be measured by the multi-meter. Un-sequenced voltages shall be monitored through the voltage monitor section. | [HAR-0041.md](../requirements/HAR-0041.md) |