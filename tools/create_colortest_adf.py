#!/usr/bin/env python3
"""Minimal ADF with a bootblock that sets background color to red.
No AmigaDOS, no filesystem, no Shell needed.
This tests whether bootblock code executes at all."""

import struct
import sys

ADF_SIZE = 880 * 1024  # 880KB standard floppy

def calc_checksum(data_1024):
    """Calculate Amiga bootblock checksum over 1024 bytes."""
    csum = 0
    for i in range(0, 1024, 4):
        val = struct.unpack(">I", data_1024[i:i+4])[0]
        csum = (csum + val) & 0xFFFFFFFF
    return (0xFFFFFFFF - csum) & 0xFFFFFFFF

def create_adf(output_path):
    bb = bytearray(1024)

    # DOS header: "DOS\0" + checksum (0 for now) + rootblock (0)
    bb[0:4] = b'DOS\x00'          # dos_type
    # bb[4:8] = checksum - calculated later
    bb[8:12] = b'\x00' * 4        # rootblock

    # Boot code at offset 12:
    #   move.w #$0F00, $DFF180    ; COLOR00 = bright red
    #   bra.s  *                   ; infinite loop

    bb[12] = 0x33    # move.w #imm, (An)
    bb[13] = 0xFC    # 
    bb[14] = 0x0F    # high byte of $0F00
    bb[15] = 0x00    # low  byte of $0F00
    bb[16] = 0x00    # high byte of $DFF180
    bb[17] = 0xDF    # 
    bb[18] = 0xF1    # 
    bb[19] = 0x80    # low  byte of $DFF180
    bb[20] = 0x60    # bra.s
    bb[21] = 0xFE    #  -2 (infinite loop)

    # Calculate checksum
    csum = calc_checksum(bytes(bb))
    bb[4:8] = struct.pack(">I", csum)

    # Write ADF
    with open(output_path, "wb") as f:
        f.write(bytes(bb))
        f.write(b'\x00' * (ADF_SIZE - 1024))

    print(f"Created: {output_path}")
    print(f"  Bootblock: 1024 bytes (header + COLOR00 code)")
    print(f"  Checksum:  0x{csum:08X}")
    print(f"  If this boots, the screen should turn red.")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out/colortest.adf"
    create_adf(out)