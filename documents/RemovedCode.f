\ 25th May 2026
: dcmd ( byte -- )
     $00 cmd-buf c! \ control byte for commands
     cmd-buf 1+ c!  \ command byte
     cmd-buf 2 I2C0 >i2c-stop drop ;
	
: dcmds ( b b .. b n -- )  \ send n bytes
     0 do dcmd loop ;

: ddata ( byte -- )
     $40 cmd-buf c! \ control byte for commands
     cmd-buf 1+ c!  \ command byte
     cmd-buf 2 I2C0 >i2c-stop drop ;
	
: ddatas ( b b .. b n -- )  \ send n bytes
     0 do ddata loop ;

\ to print a number to oled we need to convert to ASCII
\ <# #s #> needs a double on stack and returns  adr count
: .num2Buffer  ( n -- adr cnt )
    0           \ convert to double
    <# #s #>
;

: .num2FrameBuffer ( x y n -- )
    .num2Buffer     \ x y adr cnt
    .Str@xy
;

: timestwo 2 * . ;