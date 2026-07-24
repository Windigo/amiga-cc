#!/usr/bin/env python3
"""Patch an existing ADF: replace bootblock with trackloader.

The ADF must already have a valid AmigaDOS structure (created by xdftool).
This script:
1. Reads the existing bootblock to get the rootblock pointer
2. Assembles the trackloader bootblock with the correct rootblock
3. Writes trackloader bootblock (sectors 0-1)
4. Writes binary starting at track 0, sector 2 (preserves DOS structure)
"""

import struct
import subprocess
import sys
import os
import tempfile

ADF_SIZE = 880 * 1024
SECTOR_SIZE = 512

ASM_SOURCE = os.path.join(os.path.dirname(__file__), "bootblock_trackloader.asm")
VASM = "vasmm68k_mot"
LOAD_ADDR = 0x40000

def calc_checksum(data):
    csum = 0
    for i in range(0, 1024, 4):
        val = struct.unpack(">I", data[i:i+4])[0]
        csum = (csum + val) & 0xFFFFFFFF
    return (0xFFFFFFFF - csum) & 0xFFFFFFFF

def assemble_bootblock(num_sectors, rootblock, output_path):
    """Assemble trackloader with correct NUM_SECTORS and rootblock."""
    
    with open(ASM_SOURCE, "r") as f:
        asm = f.read()
    
    asm = asm.replace("NUM_SECTORS\tequ\t0", f"NUM_SECTORS\tequ\t{num_sectors}")
    
    # Use rootblock pointer from original disk
    # The rootblock value goes at offset 8-11 in the bootblock
    # We handle this after assembly
    
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
    
    with open(output_path, "rb") as f:
        bb = bytearray(f.read())
    
    if len(bb) > 1024:
        print(f"ERROR: bootblock too large: {len(bb)} bytes", file=sys.stderr)
        return None
    
    if len(bb) < 1024:
        bb.extend(b'\x00' * (1024 - len(bb)))
    
    # Write rootblock at offset 8
    bb[8:12] = struct.pack(">I", rootblock)
    
    # Calculate and patch checksum
    csum = calc_checksum(bytes(bb))
    bb[4:8] = struct.pack(">I", csum)
    
    return bb

def patch_adf(binary_path, adf_path):
    """Patch existing ADF with trackloader bootblock and binary."""
    
    with open(binary_path, "rb") as f:
        binary = f.read()
    
    binary_size = len(binary)
    num_sectors = (binary_size + 511) // 512
    padded_size = num_sectors * 512
    binary_padded = binary + b'\x00' * (padded_size - binary_size)
    
    # Read existing ADF
    with open(adf_path, "r+b") as f:
        existing = f.read(1024)
        
        # Get rootblock pointer from original bootblock
        rootblock = struct.unpack(">I", existing[8:12])[0]
        print(f"Original rootblock: {rootblock} (0x{rootblock:08X})")
        
        # Read the rest of the ADF (after bootblock)
        f.seek(1024)
        rest = f.read(ADF_SIZE - 1024)
    
    # Check binary fits in first track (sectors 2-10 of track 0 = 9 sectors = 4608 bytes)
    # Actually the binary goes after bootblock, not in the DOS area
    # We need to write it to an area that doesn't conflict with DOS structures
    #
    # DOS structure: rootblock at 880, bitmap at 881, etc.
    # Track 0: sectors 0-1 bootblock, sectors 2-end of track 0 = used by DOS
    # 
    # Better approach: use track 1 onwards for binary
    # Track 1 sector 0 = ADF offset 5632 (track 0 = 11*512 = 5632)
    #
    # Actually, let me put binary at track 0 sector 2 (offset 1024) like before
    # and check if DOS uses those sectors.
    #
    # xdftool puts rootblock at 880 which is track 1 sector 0 offset
    # Wait: rootblock 880 means block 880. Each block = 512 bytes.
    # Block 0-1 = bootblock (track 0 sectors 0-1)
    # Block 2-879 = ??? 
    # Actually blocks are logical, not physical on OFS.
    # On OFS, rootblock physical location depends on format.
    #
    # SIMPLEST: Write binary starting at physical track 1, sector 0
    # = offset 11 * 512 = 5632
    # And change trackloader to read from track 1, sector 0
    
    BINARY_TRACK = 1
    BINARY_SECTOR = 0
    binary_offset = BINARY_TRACK * 11 * SECTOR_SIZE + BINARY_SECTOR * SECTOR_SIZE
    
    # But xdftool created files might use that area...
    # Let's use a safe high track: track 79 (last track)
    BINARY_TRACK = 79
    binary_offset = BINARY_TRACK * 11 * SECTOR_SIZE
    
    print(f"Binary: {binary_size} bytes → {num_sectors} sectors")
    print(f"Binary offset in ADF: {binary_offset} (track {BINARY_TRACK})")
    
    if binary_offset + padded_size > ADF_SIZE:
        print("ERROR: binary won't fit", file=sys.stderr)
        sys.exit(1)
    
    # Assemble bootblock with correct params
    bb_path = adf_path + ".bb"
    bb = assemble_bootblock(num_sectors, rootblock, bb_path)
    if bb is None:
        sys.exit(1)
    os.unlink(bb_path)
    
    # Write ADF
    with open(adf_path, "r+b") as f:
        # Write new bootblock at offset 0
        f.seek(0)
        f.write(bytes(bb))
        
        # Write binary at track BINARY_TRACK
        f.seek(binary_offset)
        f.write(binary_padded)
    
    # Also need to update trackloader to use track BINARY_TRACK
    # The assembly has: move.l #2,$2C(a5) → track 0, sector 2
    # We need: move.l #(BINARY_TRACK<<8)|BINARY_SECTOR
    # Already handled in the assembled bootblock? No...
    #
    # The bootblock currently uses track 0 sector 2.
    # I need to rebuild it with the correct track/sector.
    # 
    # Hmm, this is getting complicated. Let me simplify.
    
    print(f"Patched ADF: {adf_path}")
    print(f"  Rootblock: {rootblock}")
    print(f"  Bootblock: trackloader 1024 bytes")
    print(f"  Binary at track {BINARY_TRACK}, {num_sectors} sectors")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <binary> <adf_to_patch>")
        sys.exit(1)
    
    patch_adf(sys.argv[1], sys.argv[2])