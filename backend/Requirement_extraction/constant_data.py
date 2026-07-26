"""
constant_data.py — Central constants for the extraction pipeline.
All regex patterns, keyword buckets, category anchors, and configuration
values are defined here so every stage module imports from a single source.
"""

from __future__ import annotations

import json
import os
import re
import logging
import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

log = logging.getLogger(__name__)
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="archtech_model"
)

_BACKEND_DIR = Path(__file__).parents[1]

try:
    _backend_dir = Path(__file__).parents[1]
    _sys = __import__("sys")
    if str(_backend_dir) not in _sys.path:
        _sys.path.insert(0, str(_backend_dir))
    from system_config import EMBEDDING_MODEL_PATH
except ImportError:
    try:
        from ..system_config import EMBEDDING_MODEL_PATH
    except ImportError:
        EMBEDDING_MODEL_PATH = _BACKEND_DIR / "Embedding_model" / "E5_large"
        
PROTOCOLS: Set[str] =  set([
    "i2c",
    "i²c",
    "spi",
    "qspi",
    "uart",
    "usart",
    "serial",
    "pci",
    "pcie",
    "pci express",
    "can",
    "can bus",
    "canfd",
    "rs232",
    "rs-232",
    "rs422",
    "rs-422",
    "rs485",
    "rs-485",
    "jtag",
    "boundary scan",
    "adc",
    "dac",
    "ethernet",
    "lan",
    "usb",
    "usb2.0",
    "usb3.0",
    "usb-c",
    "sata",
    "lin",
    "modbus",
    "modbus rtu",
    "modbus tcp",
    "profibus",
    "ethercat",
    "gpio",
    "pwm",
    "hdmi",
    "vga",
    "displayport"
  ]) # set(_lists.get("protocols", []))

DOMAIN_KW: Dict[str, List[str]] = {
    "hardware": [
      "processor",
      "cpu",
      "mcu",
      "soc",
      "fpga",
      "cpld",
      "asic",
      "memory",
      "ram",
      "dram",
      "sram",
      "flash",
      "eeprom",
      "ddr",
      "lpddr",
      "motherboard",
      "pcb",
      "chipset",
      "transceiver",
      "oscillator",
      "clock",
      "crystal",
      "power rail",
      "signal integrity",
      "termination",
      "impedance"
    ],

    "interface": [
      "uart",
      "usart",
      "spi",
      "i2c",
      "can",
      "rs422",
      "rs232",
      "usb",
      "ethernet",
      "pcie",
      "connector",
      "pin",
      "pinout",
      "bus",
      "port",
      "header",
      "interface",
      "lane",
      "phy",
      "transceiver",
      "line driver",
      "receiver"
    ],

    "software": [
      "software",
      "firmware",
      "embedded",
      "driver",
      "device driver",
      "os",
      "rtos",
      "linux",
      "bare metal",
      "bsp",
      "api",
      "sdk",
      "middleware",
      "application",
      "boot",
      "bootloader",
      "interrupt",
      "task",
      "thread",
      "scheduler",
      "ipc"
    ],

    "mechanical": [
      "dimension",
      "weight",
      "size",
      "mounting",
      "cooling",
      "thermal",
      "heatsink",
      "fan",
      "material",
      "mm",
      "kg",
      "enclosure",
      "housing",
      "form factor",
      "rack mount",
      "ip rating",
      "chassis"
    ],

    "environmental": [
      "temperature",
      "humidity",
      "vibration",
      "shock",
      "mil-std",
      "mil std",
      "operating temp",
      "storage temp",
      "altitude",
      "dust",
      "waterproof",
      "ip67",
      "ip68",
      "emc",
      "emi",
      "esd",
      "compliance"
    ],

    "power": [
      "voltage",
      "current",
      "power",
      "watt",
      "ampere",
      "5v",
      "3.3v",
      "12v",
      "1.8v",
      "power supply",
      "psu",
      "dc",
      "ac",
      "battery",
      "charger",
      "consumption",
      "efficiency",
      "dissipation",
      "regulator",
      "ldo",
      "dc-dc",
      "buck",
      "boost"
    ],

    "fpga": [
      "fpga",
      "cpld",
      "hdl",
      "vhdl",
      "verilog",
      "systemverilog",
      "glue logic",
      "ip core",
      "bitstream",
      "synthesis",
      "place and route",
      "timing closure",
      "clock domain",
      "pll",
      "xilinx",
      "vivado",
      "zynq",
      "altera",
      "intel fpga",
      "quartus"
    ],

    "adc_dac": [
      "adc",
      "dac",
      "analog",
      "digital",
      "channel",
      "resolution",
      "sample rate",
      "sampling",
      "throughput",
      "latency",
      "quantization",
      "noise",
      "snr",
      "gain",
      "offset",
      "calibration"
    ],

    "validation": [
      "test",
      "validation",
      "verification",
      "atp",
      "acceptance test",
      "qual",
      "qualification",
      "compliance",
      "fat",
      "factory acceptance",
      "sat",
      "system acceptance",
      "demo",
      "test case",
      "test plan",
      "test bench",
      "unit test",
      "integration test"
    ],

    "communication": [
      "protocol",
      "baud",
      "data rate",
      "bit rate",
      "packet",
      "frame",
      "checksum",
      "crc",
      "latency",
      "throughput",
      "bandwidth",
      "handshake",
      "flow control",
      "full duplex",
      "half duplex",
      "rs422",
      "rs232",
      "ethernet"
    ],

    "traceability": [
      "trace",
      "traceability",
      "requirement id",
      "reference",
      "section",
      "mapped",
      "linkage",
      "coverage",
      "matrix",
      "verification mapping",
      "cross reference"
    ],

    "security": [
      "encryption",
      "authentication",
      "secure boot",
      "tls",
      "ssl",
      "key",
      "certificate",
      "hash",
      "sha",
      "rsa",
      "aes",
      "firewall",
      "secure storage"
    ],

    "networking": [
      "ip",
      "tcp",
      "udp",
      "dhcp",
      "dns",
      "mac address",
      "socket",
      "http",
      "https",
      "ftp",
      "mqtt",
      "coap",
      "websocket"
    ]
  }

ALL_DOMAIN_KW: Set[str] = {
    kw for lst in DOMAIN_KW.values() for kw in lst
} 

DOC_TYPE_MAP: List = [
    ["syrs", "SyRS"],
    ["sysrs", "SyRS"],
    ["system requirement", "SyRS"],
    ["system requirements", "SyRS"],

    ["hrs", "HRS"],
    ["hardware requirement", "HRS"],
    ["hardware requirements", "HRS"],

    ["srs", "SRS"],
    ["software requirement", "SRS"],
    ["software requirements", "SRS"],

    ["sdd", "SDD"],
    ["software design", "SDD"],
    ["design document", "SDD"],

    ["techspec", "TechSpec"],
    ["tech_spec", "TechSpec"],
    ["technical specification", "TechSpec"],
    ["specification", "TechSpec"],

    ["icd", "ICD"],
    ["interface control document", "ICD"],

    ["bdd", "BDD"],
    ["block design document", "BDD"],

    ["fdd", "FDD"],
    ["functional design document", "FDD"],

    ["test plan", "TEST"],
    ["test specification", "TEST"],
    ["validation report", "TEST"],
    ["verification report", "TEST"]
  ] # _lists.get("document_types", [])

DEFAULT_PAGE_CONCURRENCY   = 3
DEFAULT_LLM_CONCURRENCY    = 3
DEFAULT_BATCH_SIZE         = 8
DEFAULT_MIN_CONFIDENCE     = 0.20
DEFAULT_LRU_CACHE_MAX      = 256
DEFAULT_LRU_CACHE_TRIM     = 192
DEFAULT_QUEUE_MAX          = 1000
DEFAULT_QUEUE_TRIM         = 750
DEFAULT_DEDUP_THRESHOLD    = 88
DEFAULT_LINK_THRESHOLD     = 70
DEBUG_PAGE_LIMIT           = None

DIRECTIVE_STRONG   = re.compile(r'\b(shall|must)\b', re.IGNORECASE)
DIRECTIVE_MODERATE = re.compile(
    r'\b(will|should|required|mandatory|specifies|defines|provides|'
    r'supports|ensures|guarantees|complies|meets|conforms)\b', re.IGNORECASE
)
TECH_UNIT_RE = re.compile(
    r'\d+\.?\d*\s*'
    r'(V|mV|kV|A|mA|uA|nA|W|mW|kW|Hz|kHz|MHz|GHz|THz|'
    r'bps|kbps|Mbps|Gbps|B|KB|MB|GB|TB|ms|us|ns|ps|s|'
    r'mm|cm|m|km|kg|g|mg|°C|°F|K|Ohm|kOhm|MOhm|'
    r'dB|dBm|dBc|ppm|ppb|rpm|bar|Pa|kPa|lux|nit|'
    r'pF|nF|uF|mF|F|nH|uH|mH|H)\b',
    re.IGNORECASE,
)

# Stage 2 Constant Data
TOC_LINE_RE = re.compile(r'\.{5,}\s*\d{1,4}\s*$')
BULLET_RE   = re.compile(r'^\s*[-•*–]\s+')
NUMBERED_RE = re.compile(r'^\s*\d+[.)]\s+')
TOC_CONTENT_DATA = re.compile(r'\b(contents|table of contents)\b', re.IGNORECASE)

BOILERPLATE_PATTERNS: List = [
    re.compile(r'^\d+(\.\d+)*\s+.{5,80}\.{5,}\s*\d{1,4}\s*$'),
    re.compile(r'^[A-Z]{2,10}/[A-Z]{2,10}/[A-Z0-9]{2,10}/[\d.]+$'),
    re.compile(r'\b(copyright|all rights reserved|confidential|proprietary|no part of)\b', re.IGNORECASE),
    re.compile(r'^(prepared by|reviewed by|approved by|document title|document reference'
               r'|technical review|document review|version number|version date)\b', re.IGNORECASE),
    re.compile(r'^based on (internal|drb|review)', re.IGNORECASE),
    re.compile(r'^\s*(sign\s*:|name\s*:)\s*$', re.IGNORECASE),
    re.compile(r'^amendments? to the document', re.IGNORECASE),
    re.compile(r'^\d{1,2}\.\d{2}\.\d{4}\s*$'),
    re.compile(r'^[A-Z][A-Z\s/]{5,50}$'),
    re.compile(r'^(figure|table|fig\.?)\s+\d', re.IGNORECASE),
    re.compile(r'^for example[,\s]', re.IGNORECASE),
    re.compile(r'naming convention', re.IGNORECASE),
]

MODAL_RE = re.compile(r'\b(should|will|can|may|could|would)\b', re.IGNORECASE)
AMBIG_RE = re.compile(
    r'\b(approximately|as needed|as required|etc\.?|and so on|'
    r'as applicable|where applicable|if necessary|as appropriate)\b',
    re.IGNORECASE,
)

KW_BUCKETS: Dict[str, List[str]] = {
    "Hardware/Power": [
        "voltage", "current", "power", "watt", "5v", "3.3v", "12v",
        "ldo", "dc-dc", "psu", "buck", "boost", "consumption",
        "dissipation", "regulator", "rail", "supply",
        "pmic", "poe", "vrm", "inverter", "fet", "mosfet", "gan", "sic"
    ],
    "Hardware/Memory": [
        "ddr5", "ddr4", "ddr3", "lpddr5", "lpddr", "sram", "flash", 
        "eeprom", "mram", "hbm", "pim", "rom", "cache", "sd card", 
        "sata", "nvm", "nvme", "nor", "nand",
        "fram", "emmc", "ufs", "dimm"
    ],
    "Hardware/Processor": [
        "arm", "cortex", "cortex-m", "cortex-a", "risc-v", "processor", 
        "cpu", "gpu", "tpu", "mcu", "soc",
        "dsp", "npu", "x86", "core"
    ],
    "Hardware/FPGA": [
        "fpga", "cpld", "asic", "bram", "uram", "lut", "zynq", 
        "mpsoc", "versal", "ultrascale", "kintex", "artix", "stratix", 
        "cyclone", "xilinx", "altera", "lattice", "microchip",
        "hls", "rtl", "bitstream", "vivado", "quartus", "serdes", "iobank"
    ],
    "Hardware/Interface": [
        "uart", "spi", "i2c", "can", "rs422", "rs232", "rs485", "usb",
        "ethernet", "pcie", "irig", "nmea", "1pps", "pps", "lvttl",
        "lvds", "gpio", "pwm", "jtag", "mdio",
        "lin", "ethercat", "mipi", "hdmi", "displayport", "i2s", "smbus"
    ],
    "Hardware/Optical": [
        "optical", "sfp", "gth", "gtx", "fiber", "fibre",
        "transceiver", "duplex", "lane", "serdes", "wavelength",
        "qsfp", "cwdm", "dwdm", "laser", "photodiode"
    ],
    "Hardware/Clock": [
        "clock", "oscillator", "pll", "crystal", "reference clock",
        "jitter", "ppb", "holdover", "synchronization", "timing",
        "tcxo", "ocxo",
        "rtc", "vco", "mems oscillator", "phase noise", "ptp"
    ],
    "Hardware/Environmental": [
        "temperature", "humidity", "vibration", "shock", "mil-std",
        "mil std", "ip67", "ip68", "emc", "emi", "esd", "altitude",
        "storage temp", "operating temp",
        "atex", "rohs", "reach", "thermal cycling", "salt spray"
    ],
    "Hardware/Mechanical": [
        "dimension", "weight", "mounting", "heatsink", "fan",
        "form factor", "chassis", "enclosure", "pcb", "rack", "size",
        "din rail", "backplane", "sma", "bnc", "standoff", "thermal pad"
    ],
    "Software/Firmware": [
        "firmware", "rtos", "bsp", "bare metal", "bootloader",
        "boot", "interrupt", "isr", "hal", "embedded software",
        "cmsis", "freertos", "zephyr", "sdk", "ota"
    ],
    "Software/Driver": [
        "driver", "device driver", "kernel module", "linux", "qnx",
        "iio", "v4l2", "sysfs", "ioctl", "u-boot"
    ],
    "Software/Application": [
        "application", "api", "sdk", "middleware", "gui", "hmi",
        "qt", "ros", "cli", "rest", "mqtt"
    ],
    "Non-Functional/Safety": [
        "safety", "sil", "reliability", "mtbf", "availability",
        "fault", "watchdog", "fail-safe", "redundancy",
        "fmea", "iso 26262", "iec 61508", "fit", "ecc"
    ],
    "Non-Functional/Security": [
        "encryption", "authentication", "secure boot", "tls", "ssl",
        "aes", "rsa", "hash", "certificate", "firewall",
        "tpm", "hsm", "root of trust", "ecc", "crypto"
    ],
    "Non-Functional/Performance": [
        "latency", "throughput", "response time", "bandwidth",
        "performance", "speed", "real-time",
        "mips", "flops", "deterministic", "overhead"
    ]
}

CAT_ANCHORS: Dict[str, str] = {
    "Hardware/Power":             "supply voltage PMIC GaN SiC regulator power consumption buck boost current rail supply",
    "Hardware/Memory":            "DDR5 LPDDR5 HBM sram flash eMMC NVMe cache memory configuration",
    "Hardware/Processor":         "ARM Cortex RISC-V CPU GPU TPU NPU multi core processor microcontroller mcu soc",
    "Hardware/FPGA":              "FPGA CPLD ASIC logic cells LUT BRAM URAM bitstream Vivado Quartus HLS RTL",
    "Hardware/Interface":         "UART SPI I2C PCIe Gen5 Ethernet 10GbE MIPI CAN FD industrial bus GPIO PWM",
    "Hardware/Optical":           "optical fiber SFP QSFP transceiver lane wavelength coherent optical serdes",
    "Hardware/Clock":             "reference clock PLL jitter phase noise oscillator TCXO OCXO PTP synchronization timing",
    "Hardware/Environmental":      "operating temperature IP67 IP68 EMC EMI ESD vibration shock MIL-STD compliance",
    "Hardware/Mechanical":        "PCB dimensions form factor chassis enclosure heatsink thermal pad mounting rack size",
    "Software/Firmware":          "RTOS FreeRTOS Zephyr firmware bootloader BSP bare metal HAL OTA update",
    "Software/Driver":            "device driver linux kernel module u-boot sysfs ioctl interrupt handler ISR",
    "Software/Application":       "application software API SDK middleware GUI HMI container ROS microservices",
    "Non-Functional/Safety":      "safety integrity SIL ISO 26262 IEC 61508 reliability MTBF watchdog fail-safe redundancy",
    "Non-Functional/Security":    "encryption authentication secure boot TPM HSM root of trust TLS AES crypto hardware security",
    "Non-Functional/Performance": "latency throughput response time execution bandwidth deterministic real-time overhead MIPS",
    "Functional":                 "system shall perform function behavior requirements user interface feature operational flow"
}

DOC_SIGNALS: Dict[str, List[str]] = {
    "HRS":  ["hardware", "power", "voltage", "memory", "ddr", "fpga", "interface", "clock", "optical"],
    "SRS":  ["software", "firmware", "driver", "rtos", "api", "application"],
    "SDD":  ["module", "function", "class", "algorithm", "state", "sequence"],
    "SyRS": ["system", "performance", "availability", "safety", "integration"],
}

PREFIX_MAP: Dict[str, str] = {
    "Hardware": "HAR",
    "Software": "SOF",
    "Non-Functional": "NFR",
    "Functional": "FUN",
}

RULE_THR      = 4
UNIT_ONLY_THR = 3

CONF_RULE_WEIGHT   = 0.3
CONF_SEM_WEIGHT    = 0.5
CONF_KW_WEIGHT     = 0.2

DEFAULT_MAX_KEYWORDS = 8
DEFAULT_YAKE_DEDUP_LIM = 0.8
DEFAULT_YAKE_TOP_N = 12

STAGE_INGEST      = "ingest"
STAGE_SEGMENT     = "segment"
STAGE_DETECT      = "detect"
STAGE_NORMALIZE   = "normalize"
STAGE_CLASSIFY    = "classify"
STAGE_EXPLAIN     = "explain"
STAGE_SCORE       = "score"
STAGE_DEDUP       = "dedup"
