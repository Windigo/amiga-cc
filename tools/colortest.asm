; Absolute minimal test: set background color to red
; Assembles to Amiga hunk executable format
; vasmm68k_mot -Fhunkexe -o colortest colortest.asm
;
; This binary uses NO libraries, NO startup code.
; Just raw hardware access.

	SECTION code,CODE

_start:
	; Set COLOR00 = 0x0F00 (bright red)
	move.w	#$0F00,$DFF180
	
	; Infinite loop
	bra.s	_start

	END