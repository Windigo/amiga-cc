#!/usr/bin/env python3
"""Build a bootable ADF using a custom trackloader bootblock.

The bootblock loads a raw binary from track 0, sector 2+ of the floppy
and executes it. This bypasses AmigaDOS completely - no Shell,
no filesystem, no startup-sequence needed.

Usage: python3 build_trackloader_adf.py <binary> <output.adf>
"""

import struct
import subprocess
import sys
import os
import tempfile

ADF_SIZE = 880 * 1024

# Path to the trackloader assembly source
ASM_SOURCE = os.path.join(os.path.dirname(__file__), "bootblock_trackloader.asm")

# Where to find vasm
VASM = "vasmm68k_mot"

# Where to load the binary in Amiga memory
LOAD_ADDR = 0x40000

def calc_checksum(data):
    """Amiga bootblock checksum over 1024 bytes."""
    csum = 0
    for i in range(0, 1024, 4):
        val = struct.unpack(">I", data[i:i+4])[0]
        csum = (csum + val) & 0xFFFFFFFF
    return (0xFFFFFFFF - csum) & 0xFFFFFFFF

def assemble_bootblock(num_sectors, output_path):
    """Assemble the trackloader bootblock with the correct NUM_SECTORS value."""
    
    # Read the assembly source
    with open(ASM_SOURCE, "r") as f:
        asm = f.read()
    
    # Replace the NUM_SECTORS placeholder
    asm = asm.replace("NUM_SECTORS\tequ\t0", f"NUM_SECTORS\tequ\t{num_sectors}")
    
    # Write modified source to temp file
    tmp_asm = output_path + ".asm"
    with open(tmp_asm, "w") as f:
        f.write(asm)
    
    try:
        result = subprocess.run(
            [VASM, "-Fbin", "-o", output_path, tmp_asm],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"VASM error: {result.stderr}", file=sys.stderr)
            return None
    finally:
        os.unlink(tmp_asm)
    
    # Read assembled bootblock
    with open(output_path, "rb") as f:
        bb = bytearray(f.read())
    
    if len(bb) > 1024:
        print(f"ERROR: bootblock too large: {len(bb)} bytes", file=sys.stderr)
        return None
    
    # Pad to 1024 bytes
    if len(bb) < 1024:
        bb.extend(b'\x00' * (1024 - len(bb)))
    
    # Calculate and patch checksum
    csum = calc_checksum(bytes(bb))
    bb[4:8] = struct.pack(">I", csum)
    
    return bb

def build_adf(binary_path, adf_path):
    """Build the complete ADF with trackloader bootblock + binary."""
    
    # Read the binary
    with open(binary_path, "rb") as f:
        binary = f.read()
    
    binary_size = len(binary)
    # Round up to sector boundary (512 bytes)
    num_sectors = (binary_size + 511) // 512
    padded_size = num_sectors * 512
    binary_padded = binary + b'\x00' * (padded_size - binary_size)
    
    print(f"Binary: {binary_size} bytes → {num_sectors} sectors ({padded_size} padded)")
    
    # Check if binary will fit in ADF (after 1024 byte bootblock)
    max_binary = ADF_SIZE - 1024
    if padded_size > max_binary:
        print(f"ERROR: binary too large ({padded_size} > {max_binary})", file=sys.stderr)
        sys.exit(1)
    
    # Assemble the bootblock (temp file)
    bb_path = adf_path + ".bb"
    bb = assemble_bootblock(num_sectors, bb_path)
    if bb is None:
        sys.exit(1)
    os.unlink(bb_path)
    
    # Write ADF
    with open(adf_path, "wb") as f:
        f.write(bytes(bb))          # 1024 bytes bootblock (track 0, sectors 0-1)
        f.write(binary_padded)      # binary at track 0, sectors 2+
        remaining = ADF_SIZE - 1024 - len(binary_padded)
        if remaining > 0:
            f.write(b'\x00' * remaining)
    
    bootblock_size = len(bb)
    print(f"ADF created: {adf_path}")
    print(f"  Bootblock: {bootblock_size} bytes (trackloader)")
    print(f"  Binary:    {binary_size} bytes at offset {bootblock_size}")
    print(f"  Load addr: ${LOAD_ADDR:06X}")
    print(f"  Boot: ROM → bootblock → reads {num_sectors} sectors → jumps to ${LOAD_ADDR:06X}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <binary> <output.adf>")
        sys.exit(1)
    
    build_adf(sys.argv[1], sys.argv[2])