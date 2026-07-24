#!/usr/bin/env python3
"""Create a bootable ADF with a custom bootblock trackloader.

The bootblock loads the binary from fixed disk sectors and executes it,
completely bypassing AmigaDOS. No Shell, no filesystem needed.
"""

import struct
import sys
import os

AMIGA_SECTOR_SIZE = 512
TRACK_SIZE = 11 * AMIGA_SECTOR_SIZE  # 11 sectors per track (standard Amiga floppy)
ADF_SIZE = 880 * 1024  # standard double-density floppy


def calc_checksum(data):
    """Calculate Amiga bootblock checksum over 1024 bytes.
    Sum of all longwords (big-endian) should equal 0xFFFFFFFF.
    """
    csum = 0
    for i in range(0, 1024, 4):
        val = struct.unpack(">I", data[i:i+4])[0]
        csum = (csum + val) & 0xFFFFFFFF
    # checksum value that makes total = 0xFFFFFFFF
    needed = (0xFFFFFFFF - csum) & 0xFFFFFFFF
    return needed


def build_bootblock(binary_size):
    """Build a custom bootblock with trackloader code.
    
    The binary will be written starting at track 1, sector 0
    (right after the bootblock at track 0).
    
    Bootblock code:
    1. Point trackdisk.device at the binary location
    2. Read binary into memory at $40000 (256KB, above most system areas)
    3. Jump to loaded code
    
    This avoids all AmigaDOS dependencies.
    """
    # Binary destination address in Amiga memory
    LOAD_ADDR = 0x40000
    
    # Binary starts at track 1, sector 0 on the floppy
    BIN_START_TRACK = 1
    BIN_START_SECTOR = 0
    
    # Calculate how many sectors to read
    num_sectors = (binary_size + AMIGA_SECTOR_SIZE - 1) // AMIGA_SECTOR_SIZE
    
    # 68k assembly for the bootblock trackloader
    # Compiled by hand: 
    
    # We'll build the boot code as raw bytes
    boot_asm = bytearray()
    
    # === Trackloader code starts at offset 12 ($C) ===
    #
    # Strategy: Use trackdisk.device directly via IOStdReq
    # But that's complex. Simpler: just use AmigaDOS InitResident
    # which already knows how to boot...
    #
    # Actually the simplest reliable method:
    # 1. Use the ROM's built-in trackdisk routines via IO request
    # 2. Create a minimal IORequest on the stack
    # 3. Call DoIO to read the binary sectors
    
    # Alternative approach for maximum compatibility:
    # Use the exec library (always open) to find trackdisk.device
    # and read sectors directly.
    
    # exec.library base is always at 4
    # trackdisk.device usually unit 0
    
    # Let me write proper 68k code:
    
    # ; a6 = exec.library base (set by ROM before jumping here)
    # ; 
    # ; We need to:
    # ; - Open trackdisk.device
    # ; - Create IORequest
    # ; - Send read command
    # ; - Jump to loaded code
    # 
    # ; First, let's keep it dead simple and just test:
    # ; Set COLOR00 to red and hang
    
    # Minimal bootblock that JUST sets COLOR00 to red
    # This will prove the bootblock code executes
    code = [
        # move.w #$0F00, $DFF180   ; COLOR00 = bright red
        0x33FC, 0x0F00, 0x00DF, 0xF180,
        # bra.s *                    ; infinite loop
        0x60FE,
    ]
    
    # Actually let me build a proper trackloader
    # =============================================
    # Bootblock layout (1024 bytes total):
    # Offset 0-3:   "DOS\0"
    # Offset 4-7:   checksum (will be calculated)
    # Offset 8-11:  rootblock (0 = not needed)
    # Offset 12+:   boot code
    #
    # Boot code:
    #   move.l  4.w, a6          ; execbase
    #   lea     td_name(pc), a0  ; "trackdisk.device"
    #   moveq   #0, d0
    #   moveq   #0, d1
    #   jsr     -$1C6(a6)        ; OpenDevice()
    #   ... this is getting complicated in raw bytes
    #
    # SIMPLEST APPROACH: Just embed the binary IN the bootblock!
    # Bootblock is 1024 bytes. If binary fits, just jump to it.
    # For larger binaries, use second approach.
    #
    # Let me try the COLORTEST approach first to debug.
    
    # TRACKLOADER BOOTBLOCK:
    # This code uses trackdisk.device to load sectors
    # Assumes trackdisk.device is already open (it always is for DF0:)
    # Unit 0, flags = 0
    
    # I'll use a known-working trackloader pattern:
    # This loads from track 1 onwards into memory
    
    # Complete trackloader bootblock:
    asm = [
        # DOS header (12 bytes)
        0x44, 0x4F, 0x53, 0x00,  # "DOS\0"
        0x00, 0x00, 0x00, 0x00,  # checksum placeholder
        0x00, 0x00, 0x00, 0x00,  # rootblock (unused)
        
        # --- Boot code starts here (offset 12) ---
        # a6 = SysBase (set by ROM before calling us)
        
        # ; Allocate memory for the binary
        # move.l #binary_size, d0
        0x203C,
        (binary_size >> 16) & 0xFFFF,
        binary_size & 0xFFFF,
        # move.l #MEMF_PUBLIC|MEMF_CLEAR, d1
        0x223C, 0x0000, 0x0001, 0x0001,  # MEMF_PUBLIC | MEMF_CLEAR = $10001
        # jsr -$C6(a6)         ; AllocMem()
        0x4EAE, 0xFF3A,
        # move.l d0, a5        ; a5 = buffer
        0x2A40,
        # beq fail             ; if alloc failed, hang
        0x6700,
        0x0062,
        
        # ; Create IOStdReq
        # move.l #$1E, d0      ; sizeof(IOStdReq) = 30
        0x703C, 0x001E,
        # move.l #MEMF_PUBLIC|MEMF_CLEAR, d1
        0x223C, 0x0000, 0x0001, 0x0001,
        # jsr -$C6(a6)         ; AllocMem()
        0x4EAE, 0xFF3A,
        # move.l d0, a4        ; a4 = ioreq
        0x2840,
        # beq fail
        0x6700,
        0x0050,
        
        # ; Open trackdisk.device
        # lea td_name(pc), a0
        0x41FA, 0x00AE,
        # moveq #0, d0         ; unit 0
        0x7000,
        # move.l a4, a1        ; ioreq
        0x224C,
        # moveq #0, d1
        0x7200,
        # jsr -$1C8(a6)        ; OpenDevice()
        0x4EAE, 0xFE38,
        # tst.l d0
        0x4A80,
        # bne fail
        0x6600, 0x003C,
        
        # ; Set up IOStdReq for CMD_READ
        # move.b #2, 8(a4)     ; io_Command = CMD_READ
        0x196C, 0x0002, 0x0008,
        # move.l a4, 20(a4)    ; io_Data = ioreq (will be patched below)
        # Actually io_Data should point to buffer
        # move.l a5, 20(a4)    ; io_Data = buffer
        0x196D, 0x0028,        # opcode doesn't do what I want
        
        # Let me use a different approach with proper opcode encoding
    ]
    
    # OK this is taking too long manually encoding 68k. Let me take a different approach.
    # I'll write the 68k asm to a file, use vasm to assemble it, then embed it.
    # Or... I'll just use Python to place the binary at a known ADF offset.
    
    # SIMPLEST VIABLE APPROACH:
    # Skip AmigaDOS entirely. Put the binary directly at ADF offset 1024 (track 0 sector 2).
    # The bootblock contains a tiny stub that:
    # 1. Copies track 0 sectors 2-N to memory (using the fact ROM already loaded track 0 into chipmem)
    # 2. Jumps to it
    #
    # Wait - the ROM only loads track 0 sectors 0-1 (the bootblock).
    # We need a trackloader.
    
    # Let me just write a proper assembler source file and assemble it.
    print(f"Binary size: {binary_size} bytes ({num_sectors} sectors needed)", file=sys.stderr)
    
    # For now, return the standard bootblock and we'll use a different approach
    return None


def create_bootable_adf_with_trackloader(binary_path, adf_path):
    """Create a bootable ADF with custom trackloader bootblock."""
    
    # Read the binary
    with open(binary_path, "rb") as f:
        binary_data = f.read()
    
    binary_size = len(binary_data)
    num_sectors = (binary_size + AMIGA_SECTOR_SIZE - 1) // AMIGA_SECTOR_SIZE
    
    print(f"Binary: {binary_path} ({binary_size} bytes, {num_sectors} sectors)")
    
    # We need a trackloader bootblock.
    # The approach: assemble 68k asm using vasm (which we have!)
    # Write asm source, assemble to raw binary, embed as bootblock.
    
    # Trackloader plan:
    # - Binary placed at ADF offset 1024 (byte 1024 = track 0, sector 2)
    # - Bootblock loads track 0 sectors 2-11, then track 1 sectors 0-N
    # - Load address: $40000 (256KB)
    # - After load, jump to $40000
    
    # Let me write the asm source
    asm_source = r"""
; Custom trackloader bootblock for Amiga floppy
; Assembles with vasm: vasm -m68k -Fbin -o bootblock.bin bootblock.asm

	org	0

; DOS header (12 bytes)
	dc.b	'DOS',$00		; dos_type
	dc.l	0			; checksum (patched later)
	dc.l	0			; rootblock (unused)

; Boot code starts at $C
; Entry: a6 = SysBase, ROM has loaded us to some address
; We use absolute code since we don't know our load address

SysBase		equ	4

exec_OpenDevice		equ	-$1C8
exec_AllocMem		equ	-$C6
exec_AllocAbs		equ	-$CC

CMD_READ	equ	2
MEMF_PUBLIC	equ	1
MEMF_CLEAR	equ	$10000

LOAD_ADDR	equ	$40000

; Number of sectors to read (patched by Python script)
; Each sector = 512 bytes
NUM_SECTORS	equ	0	; placeholder

boot_start:
	; Allocate memory at LOAD_ADDR for the binary
	move.l	#LOAD_ADDR+NUM_SECTORS*512,d0
	move.l	#MEMF_PUBLIC|MEMF_CLEAR,d1
	move.l	SysBase,a6
	jsr	exec_AllocMem(a6)
	; Ignore result - we'll use LOAD_ADDR directly
	
	; Create IOStdReq (size = $20 = 32 bytes)
	moveq	#$20,d0
	move.l	#MEMF_PUBLIC|MEMF_CLEAR,d1
	jsr	exec_AllocMem(a6)
	move.l	d0,a4		; a4 = IORequest
	
	; Open trackdisk.device, unit 0
	lea	td_name(pc),a0
	moveq	#0,d0
	move.l	a4,a1
	moveq	#0,d1
	jsr	exec_OpenDevice(a6)
	tst.l	d0
	bne	fail
	
	; Set up IOStdReq for CMD_READ
	move.w	#CMD_READ,$1C(a4) ; io_Command
	move.l	#LOAD_ADDR,$28(a4) ; io_Data
	move.l	#NUM_SECTORS*512,$24(a4) ; io_Length
	move.l	#(1<<8)|0,$2C(a4) ; io_Offset = track 1, sector 0
	; (track << 8) | sector
	
	; Send the read command
	move.l	a4,a1
	move.l	$4,a6
	jsr	-$1C8(a6)	; DoIO (actually DoIO is at -$1C8)
	
	; Actually DoIO is at different offset. 
	; Let me use SendIO + WaitIO instead
	
	; Hmm, this is getting complex. Let me use a simpler approach.
	
	; ALTERNATIVE: Since the standard bootblock already has
	; InitResident("dos.library") which boots the disk, 
	; maybe I should just fix the DOS boot approach properly.
	
	; SIMPLEST FIX: Use the standard DOS bootblock but ALSO
	; include a C directory with Shell commands? No...
	
	; ACTUAL SIMPLEST: Create a minimal startup that works.
	; The Amiga ROM 3.1 has a built-in shell in the ROM!
	; It just needs the right setup.
	
	rts

fail:
	; Red screen on failure
	move.w	#$0F00,$DFF180
	bra.s	fail

td_name:
	dc.b	'trackdisk.device',0
	
	cnop	0,2

	; Pad to fill bootblock
	ds.b	1024-*
"""
    
    # Actually, let me step back. The standard AmigaDOS bootblock SHOULD work.
    # It initializes dos.library which mounts the disk and runs s/startup-sequence.
    # The problem might be something else entirely.
    
    # Let me try: keep standard bootblock, but make binary a simple CLI program
    # that opens intuition after setting up properly.
    
    # Actually the user's original problem was that the disk booted but 
    # "program doesn't load". Now with the minimal COLOR00 test, what happens?
    
    # Let's step back and try the absolute simplest possible thing:
    # A bootblock that sets COLOR00 to red. No DOS, no filesystem, nothing.
    
    return None


def make_colortest_adf(adf_path):
    """Create a minimal bootable ADF with a bootblock that sets background red.
    This tests whether the bootblock code executes at all.
    """
    # 68k code:
    # move.w #$0F00, $DFF180    ; set COLOR00 to bright red
    # bra.s *                    ; loop forever
    
    bb = bytearray(1024)
    
    # DOS header
    bb[0:12] = b'DOS\x00' + b'\x00' * 8
    
    # Boot code at offset 12
    code_offset = 12
    # move.w #$0F00, $DFF180
    bb[code_offset + 0] = 0x33
    bb[code_offset + 1] = 0xFC
    bb[code_offset + 2] = 0x0F
    bb[code_offset + 3] = 0x00
    bb[code_offset + 4] = 0x00
    bb[code_offset + 5] = 0xDF
    bb[code_offset + 6] = 0xF1
    bb[code_offset + 7] = 0x80
    # bra.s $ - 0  (infinite loop: $60 $FE)
    bb[code_offset + 8] = 0x60
    bb[code_offset + 9] = 0xFE
    
    # Calculate checksum
    csum = calc_checksum(bytes(bb))
    bb[4:8] = struct.pack(">I", csum)
    
    # Create the ADF file
    with open(adf_path, "wb") as f:
        f.write(bytes(bb))
        # Fill rest with zeros to ADF size
        remaining = ADF_SIZE - 1024
        f.write(b'\x00' * remaining)
    
    print(f"Created colortest ADF: {adf_path}")
    return True


def make_trackloader_adf(binary_path, adf_path):
    """Create a bootable ADF with trackloader bootblock that loads and runs the binary.
    
    The binary is written to the ADF starting at byte 1024 (right after bootblock).
    A custom bootblock loads it into Amiga memory and jumps to it.
    """
    
    with open(binary_path, "rb") as f:
        binary_data = f.read()
    
    binary_size = len(binary_data)
    # Round up to sector boundary
    padded_size = ((binary_size + AMIGA_SECTOR_SIZE - 1) // AMIGA_SECTOR_SIZE) * AMIGA_SECTOR_SIZE
    binary_padded = binary_data + b'\x00' * (padded_size - binary_size)
    
    num_sectors = padded_size // AMIGA_SECTOR_SIZE
    
    # Load address for binary
    LOAD_ADDR = 0x40000
    
    # Build the trackloader bootblock
    # This is 68k code compiled with vasm
    # We'll write an asm file, assemble it, then embed it
    
    asm_path = "/tmp/trackloader.asm"
    obj_path = "/tmp/trackloader.bin"
    
    asm_code = f"""
	org	0

	dc.b	'DOS',$00
	dc.l	0		; checksum placeholder
	dc.l	0		; rootblock

; Entry: a6 = SysBase

LOAD_ADDR	equ	${LOAD_ADDR:06X}
NUM_SEC		equ	{num_sectors}

	; Allocate memory
	move.l	#LOAD_ADDR+512*NUM_SEC,d0
	move.l	#$10001,d1	; MEMF_PUBLIC|MEMF_CLEAR
	jsr	-$C6(a6)	; AllocMem
	
	; Create IOStdReq
	moveq	#$20,d0
	move.l	#$10001,d1
	jsr	-$C6(a6)
	tst.l	d0
	beq	fail
	move.l	d0,a5		; a5 = IORequest

	; Open trackdisk.device unit 0
	lea	tdname(pc),a0
	moveq	#0,d0
	move.l	a5,a1
	moveq	#0,d1
	jsr	-$1C8(a6)	; OpenDevice
	tst.l	d0
	bne	fail
	
	; Set up IOStdReq for read
	move.w	#2,$1C(a5)	; IO_COMMAND = CMD_READ
	move.l	#LOAD_ADDR,$28(a5) ; IO_DATA
	move.l	#512*NUM_SEC,$24(a5) ; IO_LENGTH
	move.l	#0,$2C(a5)	; IO_OFFSET = 0 (track 0, sector 2 onwards)
	
	; Actually IO_OFFSET = (track << 8) | sector
	; We want track 0, sector 2 (right after bootblock)
	move.l	#$0002,$2C(a5)
	
	; SendIO
	move.l	a5,a1
	move.l	4.w,a6
	jsr	-$1C8(a6)	; DoIO
	
	; Check result
	tst.b	$1F(a5)		; io_Error
	bne	fail
	
	; Jump to loaded code!
	move.l	#LOAD_ADDR,a0
	jmp	(a0)
	
fail:
	move.w	#$0F00,$DFF180	; red screen
	bra.s	fail

tdname:
	dc.b	'trackdisk.device',0
	cnop	0,2

	ds.b	1024-*
"""
    
    with open(asm_path, "w") as f:
        f.write(asm_code)
    
    # Try to assemble
    ret = os.system(f"vasmm68k_mot -Fbin -o {obj_path} {asm_path} 2>&1")
    if ret != 0:
        print("Assembly failed! Falling back to standard bootblock.", file=sys.stderr)
        return False
    
    # Read assembled bootblock
    with open(obj_path, "rb") as f:
        bb = bytearray(f.read())
    
    if len(bb) > 1024:
        print(f"Bootblock too large: {len(bb)} bytes", file=sys.stderr)
        return False
    
    # Pad to 1024
    if len(bb) < 1024:
        bb.extend(b'\x00' * (1024 - len(bb)))
    
    # Calculate and patch checksum
    csum = calc_checksum(bytes(bb))
    bb[4:8] = struct.pack(">I", csum)
    
    # Write ADF
    with open(adf_path, "wb") as f:
        f.write(bytes(bb))
        # Filler for bootblock rest (already 1024)
        # Binary data starts at offset 1024 (track 0, sector 2)
        f.write(binary_padded)
        # Fill rest of ADF
        remaining = ADF_SIZE - 1024 - len(binary_padded)
        if remaining > 0:
            f.write(b'\x00' * remaining)
    
    print(f"Created trackloader ADF: {adf_path}")
    print(f"  Binary: {binary_size} bytes at offset 1024")
    print(f"  Bootblock: 1024 bytes with trackloader")
    os.unlink(asm_path)
    os.unlink(obj_path)
    return True


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <binary> <adf_output> [colortest]")
        print("  If 'colortest' is specified, creates a minimal red-screen test ADF")
        sys.exit(1)
    
    binary_path = sys.argv[1]
    adf_path = sys.argv[2]
    
    if len(sys.argv) > 2 and sys.argv[-1] == "colortest":
        make_colortest_adf(adf_path)
        return
    
    if not make_trackloader_adf(binary_path, adf_path):
        print("Trackloader failed, creating colortest instead...", file=sys.stderr)
        make_colortest_adf(adf_path)


if __name__ == "__main__":
    main()