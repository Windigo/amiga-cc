; Custom bootblock: Init dos.library, then LoadSeg + run binary
; Assembles with: vasmm68k_mot -Fbin -o bootblock.bin bootblock_dosload.asm
;
; This bootblock:
; 1. Initializes dos.library (same as standard bootblock → mounts disk)
; 2. Uses dos.library to LoadSeg("s/startup-sequence")
; 3. Jumps to the loaded code
;
; No Shell needed! LoadSeg loads the binary directly.

	org	0

; --- DOS header ---
	dc.b	'DOS',$00
	dc.l	0		; checksum placeholder
	dc.l	0		; rootblock placeholder

; ===================================================================
; Boot code at offset $C
; Entry: a6 = SysBase (exec.library)
; ===================================================================

; exec.library functions (negative offsets from execbase)
FIND_RESIDENT	equ	-$1E2	; FindResident(name)

; dos.library functions (LVO-based, positive offsets from dosbase)
; We get dosbase from the resident structure
; After InitResident, dosbase is in a0, and the function table is there
; LoadSeg LVO = 150 ($096)
; Actually we use jsr with absolute LVO after getting dosbase

start:
	; --- InitResident("dos.library") ---
	; This mounts the disk and makes files accessible
	lea	dos_name(pc),a1		; resident name
	moveq	#0,d0
	moveq	#0,d1
	jsr	FIND_RESIDENT(a6)	; FindResident
	move.l	d0,a0			; a0 = resident structure
	move.l	22(a0),a0		; a0 = InitResident function
	jsr	(a0)			; InitResident → dos.library initialized
	
	; Now dos.library is ready. a6 still = SysBase
	; We need dos.library base → it's at the top of exec's library list
	; Or we can use the internal DOSBase pointer
	
	; Simpler: after InitResident, we can open dos.library
	; Let's open it properly
	
	; OpenLibrary("dos.library", 0)
	lea	dos_name(pc),a1		; library name
	moveq	#0,d0			; version 0
	move.l	a6,a6
	jsr	-$228(a6)		; OldOpenLibrary (simpler, KS 1.2+)
	move.l	d0,a5			; a5 = DOSBase
	
	; LoadSeg("s/startup-sequence")
	lea	startup_file(pc),a0	; filename
	move.l	a5,a6			; DOSBase
	jsr	-$096(a6)		; LoadSeg (LVO 150 = $096, negative offset = -$096)
	
	; d0 = BPTR to segment list, or NULL on error
	tst.l	d0
	beq.s	fail
	
	; UnLoadSeg the startup info (BMI flag), run the code
	; For LoadSeg result, we need to process the BCPL pointer
	move.l	d0,a0
	add.l	a0,a0
	add.l	a0,a0			; BPTR → APTR
	move.l	a0,a4			; a4 = segment list
	
	; First longword = next segment BPTR
	; Second longword = bytes to skip for code start
	move.l	(a4)+,d0		; next segment (0 if last)
	move.l	(a4)+,d1		; skip bytes
	add.l	d1,a4			; point to code
	
	; Jump to the loaded code!
	jmp	(a4)

fail:
	; Red screen on failure
	move.w	#$0F00,$DFF180
	bra.s	fail

dos_name:
	dc.b	'dos.library',0

startup_file:
	dc.b	's/startup-sequence',0

	cnop	0,2

	; Pad to 1024 bytes
	ds.b	1024-*