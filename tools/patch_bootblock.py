#!/usr/bin/env python3
"""Replace an ADF's bootblock with our custom dosload bootblock.

Usage: python3 patch_bootblock.py <adf_file>
"""

import struct
import subprocess
import sys
import os

ADF_SIZE = 880 * 1024
ASM_SOURCE = os.path.join(os.path.dirname(__file__), "bootblock_dosload.asm")
VASM = "vasmm68k_mot"

def calc_checksum(data):
    csum = 0
    for i in range(0, 1024, 4):
        val = struct.unpack(">I", data[i:i+4])[0]
        csum = (csum + val) & 0xFFFFFFFF
    return (0xFFFFFFFF - csum) & 0xFFFFFFFF

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <adf_file>")
        sys.exit(1)
    
    adf_path = sys.argv[1]
    
    # Read existing bootblock to get rootblock pointer
    with open(adf_path, "r+b") as f:
        existing_bb = f.read(1024)
        rootblock = struct.unpack(">I", existing_bb[8:12])[0]
    
    print(f"Rootblock: {rootblock}")
    
    # Assemble custom bootblock
    tmp_out = "/tmp/custom_bb.bin"
    result = subprocess.run(
        [VASM, "-Fbin", "-o", tmp_out, ASM_SOURCE],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"VASM error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    print(f"VASM: {result.stdout.strip()}")
    
    with open(tmp_out, "rb") as f:
        bb = bytearray(f.read())
    os.unlink(tmp_out)
    
    if len(bb) > 1024:
        print(f"ERROR: bootblock too large: {len(bb)} bytes", file=sys.stderr)
        sys.exit(1)
    
    # Pad to 1024
    if len(bb) < 1024:
        bb.extend(b'\x00' * (1024 - len(bb)))
    
    # Restore rootblock pointer
    bb[8:12] = struct.pack(">I", rootblock)
    
    # Calculate checksum
    csum = calc_checksum(bytes(bb))
    bb[4:8] = struct.pack(">I", csum)
    
    # Write back to ADF
    with open(adf_path, "r+b") as f:
        f.seek(0)
        f.write(bytes(bb))
    
    print(f"Bootblock patched in: {adf_path}")
    print(f"  Rootblock: {rootblock}")
    print(f"  Checksum:  0x{csum:08X}")
    print(f"  Code: InitResident → OpenLibrary → LoadSeg → Run")

if __name__ == "__main__":
    main()