; Raw flat binary - loaded by trackloader at $40000
; No OS, no hunk format, just bare metal 68k code
;
; Assembles with: vasmm68k_mot -Fbin -o rawtest.bin rawtest.asm

	org	$40000

start:
	; COLOR00 = $DFF180 = bright red
	move.w	#$0F00,$DFF180

loop:
	bra.s	loop

	end