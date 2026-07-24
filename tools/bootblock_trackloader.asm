; Trackloader bootblock for Amiga floppy
; Assembles with: vasmm68k_mot -Fbin -o bootblock.bin bootblock_trackloader.asm
;
; This replaces the standard AmigaDOS bootblock.
; It loads a raw binary from fixed sectors on the floppy
; into memory and jumps to it.
;
; Binary location on ADF: starts at byte 1024 (track 0, sector 2)
; Load address in Amiga memory: $40000

	org	0

; --- DOS header (12 bytes) ---
	dc.b	'DOS',$00	; dos_type
	dc.l	0		; checksum placeholder (patched by Python)
	dc.l	0		; rootblock (unused by us)

; ======================================================================
; Boot code starts at offset $C (12)
; Entry conditions (set by Kickstart ROM):
;   a6 = SysBase (exec.library base)
;   We're loaded somewhere in chipmem, but code is position-independent
;
;   Actually the ROM copies the bootblock to an arbitrary address 
;   (typically $7E000-ish on KS 3.1) and jumps to offset $C.
;   All code must be position-independent.
; ======================================================================

; exec.library LVO offsets (from exec base)
EXEC_OPENDEVICE		equ	-$1C8
EXEC_DOIO		equ	-$1C8	; DoIO()
EXEC_SENDIO		equ	-$1C2	; SendIO()
EXEC_WAITIO		equ	-$1BC	; WaitIO()
EXEC_ALLOCMEM		equ	-$C6
EXEC_FREEMEM		equ	-$D2

; trackdisk.device commands
CMD_READ	equ	2

; MEMF flags
MEMF_PUBLIC	equ	1
MEMF_CLEAR	equ	$10000

; Where to load the binary
LOAD_ADDR	equ	$40000

; These values are patched by the Python script before writing to ADF
; Number of sectors to load (512 bytes each)
NUM_SECTORS	equ	0	; PLACEHOLDER - patched by script

start:
	; Allocate IOStdReq ($20 bytes)
	moveq	#$20,d0
	move.l	#MEMF_PUBLIC|MEMF_CLEAR,d1
	jsr	EXEC_ALLOCMEM(a6)
	tst.l	d0
	beq.s	fail
	move.l	d0,a5			; a5 = IORequest

	; Open trackdisk.device, unit 0
	lea	td_name(pc),a0		; device name
	moveq	#0,d0			; unit 0
	move.l	a5,a1			; IORequest
	moveq	#0,d1			; flags
	jsr	EXEC_OPENDEVICE(a6)
	tst.l	d0
	bne.s	fail

	; Set up IOStdReq for CMD_READ
	move.w	#CMD_READ,$1C(a5)	; io_Command
	move.l	#LOAD_ADDR,$28(a5)	; io_Data = destination buffer
	move.l	#512*NUM_SECTORS,$24(a5) ; io_Length = bytes to read
	move.l	#2,$2C(a5)		; io_Offset = track 0, sector 2
					; (sector 0-1 = bootblock, binary at sector 2+)

	; Send the IO request and wait for completion
	move.l	a5,a1			; IORequest
	jsr	EXEC_DOIO(a6)		; DoIO (synchronous)

	; Check for error
	tst.b	$1F(a5)			; io_Error
	bne.s	fail

	; Success! Free the IO request
	move.l	#$20,d0
	move.l	a5,a1
	jsr	EXEC_FREEMEM(a6)

	; Jump to loaded binary
	move.l	#LOAD_ADDR,a0
	jmp	(a0)

fail:
	; Red screen = boot failure
	move.w	#$0F00,$DFF180
	bra.s	fail

td_name:
	dc.b	'trackdisk.device',0

	; Align to 2 bytes for safety
	cnop	0,2

	; Pad to 1024 bytes
	ds.b	1024-*