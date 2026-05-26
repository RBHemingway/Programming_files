\ 26\05\2026 15:15
\ 25May - got Screen LtR/TtB and setPixel etc working
\ 26May - start on lines and rectangles

\ store stack addr into sp0
\ variable sp0
\ sp@ sp0 !   \ sp0 is required in send-cmd
: CLEAR-STACK   ( -- )
    DEPTH 0 ?DO DROP LOOP ;


i2c import
\ hex

0    constant i2c0
4    constant sda-pin
5    constant scl-pin
$3C  constant ssd1306-addr
64   constant OLED-H
128  constant OLED-W
5    constant cmd-buf-size

create cmd-buf  cmd-buf-size allot      
	\ control + 4 command
create data-buf OLED-W 1+ allot 
	\ control + up to 128 data bytes
create frameBuffer 1025 allot \ control + 1 full screen buffer

: i2c-init 
   i2c0 enable-i2c
   i2c0 sda-pin i2c-pin
   i2c0 scl-pin i2c-pin
   400000 i2c0 i2c-clock! \ 400 kHz; use 100000 for 100 kHz 
   i2c0 master-i2c
   i2c0 7-bit-i2c-addr
   ssd1306-addr i2c0 i2c-target-addr! 
;

\ ================================
\ SSD1306 INITIALISATION
\ ================================
\ # register definitions from RNs
$81 constant  SET_CONTRAST 
$a4 constant  SET_ENTIRE_ON  
$a6 constant  SET_NORM_INV   
$ae constant  SET_DISP_OFF
$af constant  SET_DISP_ON       
$20 constant  SET_MEM_ADDR   
$21 constant  SET_COL_ADDR   
$22 constant  SET_PAGE_ADDR  
$40 constant  SET_DISP_START_LINE
$a0 constant  SET_SEG_REMAP  
$a8 constant  SET_MUX_RATIO  
$c0 constant  SET_COM_OUT_DIR
$d3 constant  SET_DISP_OFFSET
$da constant  SET_COM_PIN_CFG
$d5 constant  SET_DISP_CLK_DIV
$d9 constant  SET_PRECHARGE  
$db constant  SET_VCOM_DESEL 
$8d constant  SET_CHARGE_PUMP



: send-cmd  ( n..n' # -- )  \ send n bytes from stack
    \ check that # is less than cmd-buf-size 
    dup cmd-buf-size <      \ n..n' # flag
    if
        dup >r                  \ n..n' #      r: #
        $00                     \ n..n' # 0    r: #
        swap 1+                 \ n..n' 0 #+1  r: #
        0 do                    \ n..n' 0      r: #
            cmd-buf i +         \ n..n' 0 adr+i    r: #
            c!                  \ n..n'        r: #
        loop
        r> 1+                   \ #+1
        cmd-buf swap            \ adr #+1
        I2C0 >i2c-stop drop
    else
        \ we need to restore the stack pointer to remove unused bytes
        \ sp0 @ sp!  
		CLEAR-STACK
    then 
;

: send-data ( d..d' # -- )  \  must be < 129 bytes
    dup OLED-W 1+ <      \ n..n' # flag
    if
        dup >r                  \ n..n' #      r: #
        $40                     \ n..n' # 0    r: #
        swap 1+                 \ n..n' 0 #+1  r: #
        0 do                    \ n..n' 0      r: #
            data-buf i +         \ n..n' 0 adr+i    r: #
            c!                  \ n..n'        r: #
        loop
        r> 1+                   \ #+1
        data-buf swap            \ adr #+1
        I2C0 >i2c-stop drop
    else
        \ we need to restore the stack pointer to remove unused bytes
        \ sp0 @ sp!  
		CLEAR-STACK
    then 
;

: buffer-to-oled ( addr n -- )  \ send n bytes from addr
     I2C0 >i2c-stop drop ;

: set-page ( end start -- )
     \ setting page limits which part of the screen is updated
     \ eg. $03 $03 SET_PAGE_ADDR 3 send-cmd would update only the 4th line.
     SET_PAGE_ADDR 3 send-cmd
     \ we can send one page, two or all seven
     \ we don't need to send all 1024 bytes every time
;

: oled-init ( -- copying from RNs micropython )
	SET_DISP_OFF 1 send-cmd  \ set display off
     $10 SET_CHARGE_PUMP 2 send-cmd
	$00 SET_MEM_ADDR 2 send-cmd  \  horizontal

	\ resolution and layout
	SET_DISP_START_LINE 1 send-cmd	\ set display start line
	SET_SEG_REMAP 1 or 1 send-cmd		\ col addr 127 mapped to SEG0 LtR
	$3f SET_MUX_RATIO 2  send-cmd      \ one less than width = 63d
	SET_COM_OUT_DIR $08 or 1 send-cmd  \ top to bottom
	$00 SET_DISP_OFFSET 2 send-cmd
	$12 SET_COM_PIN_CFG  2 send-cmd    \ timing and driving scheme

	\ timing and driving scheme
	$80 SET_DISP_CLK_DIV 2  send-cmd
	$22 SET_PRECHARGE 2  send-cmd
	$20 SET_VCOM_DESEL 2  send-cmd     \ 0.77 x Vcc

	\ display
	$7f SET_CONTRAST 2  send-cmd
     $7f $00 SET_COL_ADDR 3 send-cmd
     $07 $00 SET_PAGE_ADDR 3 send-cmd
	SET_ENTIRE_ON  1 send-cmd
	SET_NORM_INV 1  send-cmd

	\ charge pump
	$14 SET_CHARGE_PUMP 2  send-cmd
	SET_DISP_ON  1 send-cmd   \ set display on
	;

\ ================================
\ CLEAR SCREEN
\ ================================
: erase  (  addr n -- )
	$00 fill ;

\ ================================
\ words for frameBuffer
\ ================================ 
: fill-frameBuffer ( byte -- )
     frameBuffer 1+ 1024 
     rot
     fill 
;
     
: show-frameBuffer ( -- )
     frameBuffer
     1025 0 do
          dup i + c@ . 
     loop 
     drop 
;

: send-frameBuffer-oled   ( -- ) \ sends whole 1024 frameBuffer
     \ page addresses from  0 to 7
     \ send 128 bytes of data for each of the 8 pages
     7 0 set-page
     $40 frameBuffer c!  \ store $40 cmd byte in frameBuffer[0]
     frameBuffer 1025 buffer-to-oled  \ send frameBuffer to oled
;
\ shortened word
: sfbo send-frameBuffer-oled ;

: oled-clear ( -- )  \ whole screen
     \ fill frameBuffer with $00
     \ send the buffer to oled

	$00 fill-frameBuffer
     send-frameBuffer-oled
;

: oled-fill ( -- )
	$ff fill-frameBuffer
	sfbo
;

: partial-fill-frameBuffer  ( offset number byte -- )   
     rot                 \ num byte offset
     frameBuffer 1+ +       \ num byte addr'
     -rot                \ addr' num byte
     fill
;
\ shortened word
: pffb partial-fill-frameBuffer send-frameBuffer-oled ;

\ to locate a specific buffer index and bit use the following...
\ Valid ranges  x: 0 to 127, y: 0 to 63  ( 128x64 pixels)
\ 
\ Page is 0 to 7, each page is 8 pixels high, so page = y / 8 (y 3 rshift)
\ Bit is 0 to 7, bit = y mod 8 (y 7 and)     
\ Buffer index = x + (page * 128) + 1 = x + ((y 3 rshift) * 128) 1+
\ why 1+ at the end ?
\ because frameBuffer[0] is reserved for the $40 control byte, so the actual pixel data starts from frameBuffer[1]
: check-XY-Ranges ( x y -- x y flag )
	\ x 0-127  y 0-63
    \ flag=true means an error  
    dup 63 > rot 
    dup 127 > rot
    or                  \ y x flag
    -rot swap rot       \ x y flag
;

: get-Mask-BufferIndex  ( x y -- mask index )
    dup 3 rshift 		\ x y page
	>r					\ x y			r: page
	7 and				\ x bit			r: page
	1 swap	lshift		\ x mask 		r: page
	\ compute index
	swap				\ mask x 		r: page
	r> 7 lshift +		\ mask index
;

: setPixelOn ( x y -- )
\ sets pixel in frameBuffer, not the GDDRAM
    \ check ranges of x and y
    check-XY-Ranges    \ x y flag 
    if  \ true means out of range  
        2drop exit
    then           \ x y --  in range
	get-Mask-BufferIndex	\ mask index

    \ OR mask into buffer[index]
    \ remember frameBuffer[0] is $40 control byte
    frameBuffer 1+ +      	\ mask addr'
    dup c@ 					\ mask addr' byte			
	rot 					\ addr' byte mask
	or						\ addr' byte' 
	swap c!					\ --
;

: setPixelOff ( x y -- )
\ sets pixel in frameBuffer, not the GDDRAM
    \ check ranges of x and y
    check-XY-Ranges    \ x y flag 
    if  \ true means out of range  
        2drop exit
    then           \ x y --  in range
	get-Mask-BufferIndex	\ mask index

    \ OR mask into buffer[index]
    \ remember frameBuffer[0] is $40 control byte
    frameBuffer 1+ +      	\ mask addr'
    dup c@ 					\ mask addr' byte			
	rot 					\ addr' byte mask
	xor						\ addr' byte' 
	swap c!					\ --
;

: drawHLine ( x1 x2 y -- )
\ sets pixel in frameBuffer, not the GDDRAM
    \ draw horizontal line from (x1,y) to (x2,y)
	-rot 1+			\ y x1 x2+1
	2dup			\ y x1 x2 x1 x2
	<				\ y x1 x2 flag
	if				\ y x1 x2 
		swap		\ y x2 x1 
	then
	do				\ y
		dup			\ y y
		i swap		\ y x' y
		setPixelOn	\ y 
	loop
	drop
;

: drawVLine  ( y1 y2 x -- )
\ sets pixel in frameBuffer, not the GDDRAM
    \ draw vertical line from (x,y1) to (x,y2)
	-rot 1+			\ x y1 y2+1 
	2dup 			\ x y1 y2 y1 y2 
	< if 			\ x y1 y2 
		swap		\ x y2 y1 
	then
	do				\ x 
		dup			\ x x 
		i 			\ x x y'
		setPixelOn	\ x 
	loop
	drop
;

: drawRectangle ( x1 y1 x2 y2 -- )
\ sets pixel in frameBuffer, not the GDDRAM
	\ have to draw 4 lines
	\ H x1 x2 y1  and x1 x2 y2 
	\ V y1 y2 x1  and y1 y2 x2 
	{ x1 y1 x2 y2 }
	x1 x2 y1 drawHLine
	x1 x2 y2 drawHLine
	y1 y2 x1 drawVLine
	y1 y2 X2 drawVLine
;

: drawOffsetRectangle  ( offset -- )
\ sets pixel in frameBuffer, not the GDDRAM
	\ define the four corner points
	\ offset offset 127-offset 63-offset
	\ then call drawRectangle 
	
	dup					\ offset offset
	OLED-H 2/ 1-			\ offset offset 63
	< if 				\ offset
		dup 2dup		\ offset offset offset offset
		oled-w 			\ offset offset offset offset 128
		swap			\ offset offset offset 128 offset 
		- 1-			\ offset offset offset 127-offset
		swap			\ offset offset 127-offset offset
		OLED-H			\ offset offset 127-offset offset 64
		swap			\ offset offset 127-offset 64 offset
		- 1-			\ offset offset 127-offset 63-offset
		drawRectangle
	else
		drop
	then
;

\ ----------------------------------------------------------------------
\ 5x8 font (from mecrisp-stellaris 2.2.1a, GPL3)
\ ----------------------------------------------------------------------

hex
create font
  00 c, 00 c, 00 c, 00 c, 00 c, \
  00 c, 00 c, 4F c, 00 c, 00 c, \ !
  00 c, 03 c, 00 c, 03 c, 00 c, \ "
  14 c, 3E c, 14 c, 3E c, 14 c, \ #
  24 c, 2A c, 7F c, 2A c, 12 c, \ $
  63 c, 13 c, 08 c, 64 c, 63 c, \ %
  36 c, 49 c, 55 c, 22 c, 50 c, \ &
  00 c, 00 c, 07 c, 00 c, 00 c, \ '
  00 c, 1C c, 22 c, 41 c, 00 c, \ (
  00 c, 41 c, 22 c, 1C c, 00 c, \ )
  0A c, 04 c, 1F c, 04 c, 0A c, \ *
  04 c, 04 c, 1F c, 04 c, 04 c, \ +
  50 c, 30 c, 00 c, 00 c, 00 c, \ ,
  08 c, 08 c, 08 c, 08 c, 08 c, \ -
  60 c, 60 c, 00 c, 00 c, 00 c, \ .
  00 c, 60 c, 1C c, 03 c, 00 c, \ /
  3E c, 41 c, 49 c, 41 c, 3E c, \ 0
  00 c, 02 c, 7F c, 00 c, 00 c, \ 1
  46 c, 61 c, 51 c, 49 c, 46 c, \ 2
  21 c, 49 c, 4D c, 4B c, 31 c, \ 3
  18 c, 14 c, 12 c, 7F c, 10 c, \ 4
  4F c, 49 c, 49 c, 49 c, 31 c, \ 5
  3E c, 51 c, 49 c, 49 c, 32 c, \ 6
  01 c, 01 c, 71 c, 0D c, 03 c, \ 7
  36 c, 49 c, 49 c, 49 c, 36 c, \ 8
  26 c, 49 c, 49 c, 49 c, 3E c, \ 9
  00 c, 33 c, 33 c, 00 c, 00 c, \ :
  00 c, 53 c, 33 c, 00 c, 00 c, \ ;
  00 c, 08 c, 14 c, 22 c, 41 c, \ <
  14 c, 14 c, 14 c, 14 c, 14 c, \ =
  41 c, 22 c, 14 c, 08 c, 00 c, \ >
  06 c, 01 c, 51 c, 09 c, 06 c, \ ?
  3E c, 41 c, 49 c, 15 c, 1E c, \ @
  78 c, 16 c, 11 c, 16 c, 78 c, \ A
  7F c, 49 c, 49 c, 49 c, 36 c, \ B
  3E c, 41 c, 41 c, 41 c, 22 c, \ C
  7F c, 41 c, 41 c, 41 c, 3E c, \ D
  7F c, 49 c, 49 c, 49 c, 49 c, \ E
  7F c, 09 c, 09 c, 09 c, 09 c, \ F
  3E c, 41 c, 41 c, 49 c, 7B c, \ G
  7F c, 08 c, 08 c, 08 c, 7F c, \ H
  00 c, 41 c, 7F c, 41 c, 00 c, \ I
  38 c, 40 c, 40 c, 41 c, 3F c, \ J
  7F c, 08 c, 08 c, 14 c, 63 c, \ K
  7F c, 40 c, 40 c, 40 c, 40 c, \ L
  7F c, 06 c, 18 c, 06 c, 7F c, \ M
  7F c, 06 c, 18 c, 60 c, 7F c, \ N
  3E c, 41 c, 41 c, 41 c, 3E c, \ O
  7F c, 09 c, 09 c, 09 c, 06 c, \ P
  3E c, 41 c, 51 c, 21 c, 5E c, \ Q
  7F c, 09 c, 19 c, 29 c, 46 c, \ R
  26 c, 49 c, 49 c, 49 c, 32 c, \ S
  01 c, 01 c, 7F c, 01 c, 01 c, \ T
  3F c, 40 c, 40 c, 40 c, 7F c, \ U
  0F c, 30 c, 40 c, 30 c, 0F c, \ V
  1F c, 60 c, 1C c, 60 c, 1F c, \ W
  63 c, 14 c, 08 c, 14 c, 63 c, \ X
  03 c, 04 c, 78 c, 04 c, 03 c, \ Y
  61 c, 51 c, 49 c, 45 c, 43 c, \ Z
  00 c, 7F c, 41 c, 00 c, 00 c, \ [
  00 c, 03 c, 1C c, 60 c, 00 c, \ \
  00 c, 41 c, 7F c, 00 c, 00 c, \ ]
  0C c, 02 c, 01 c, 02 c, 0C c, \ ^
  40 c, 40 c, 40 c, 40 c, 40 c, \ _
  00 c, 01 c, 02 c, 04 c, 00 c, \ `
  20 c, 54 c, 54 c, 54 c, 78 c, \ a
  7F c, 48 c, 44 c, 44 c, 38 c, \ b
  38 c, 44 c, 44 c, 44 c, 44 c, \ c
  38 c, 44 c, 44 c, 48 c, 7F c, \ d
  38 c, 54 c, 54 c, 54 c, 18 c, \ e
  08 c, 7E c, 09 c, 09 c, 00 c, \ f
  0C c, 52 c, 52 c, 54 c, 3E c, \ g
  7F c, 08 c, 04 c, 04 c, 78 c, \ h
  00 c, 00 c, 7D c, 00 c, 00 c, \ i
  00 c, 40 c, 3D c, 00 c, 00 c, \ j
  7F c, 10 c, 28 c, 44 c, 00 c, \ k
  00 c, 00 c, 3F c, 40 c, 00 c, \ l
  7C c, 04 c, 18 c, 04 c, 78 c, \ m
  7C c, 08 c, 04 c, 04 c, 78 c, \ n
  38 c, 44 c, 44 c, 44 c, 38 c, \ o
  7F c, 12 c, 11 c, 11 c, 0E c, \ p
  0E c, 11 c, 11 c, 12 c, 7F c, \ q
  00 c, 7C c, 08 c, 04 c, 04 c, \ r
  48 c, 54 c, 54 c, 54 c, 24 c, \ s
  04 c, 3E c, 44 c, 44 c, 00 c, \ t
  3C c, 40 c, 40 c, 20 c, 7C c, \ u
  1C c, 20 c, 40 c, 20 c, 1C c, \ v
  1C c, 60 c, 18 c, 60 c, 1C c, \ w
  44 c, 28 c, 10 c, 28 c, 44 c, \ x
  46 c, 28 c, 10 c, 08 c, 06 c, \ y
  44 c, 64 c, 54 c, 4C c, 44 c, \ z
  00 c, 08 c, 77 c, 41 c, 00 c, \ {
  00 c, 00 c, 7F c, 00 c, 00 c, \ |
  00 c, 41 c, 77 c, 08 c, 00 c, \ }
  10 c, 08 c, 18 c, 10 c, 08 c, \ ~
decimal

\ write byte in display memory:
: wram ( b --) 
   1 send-data ;


\ translate ASCII to address of bit patterns
: a>bp ( c -- c-adr )
  32 max 127 min
  32 - 5 * font + ;

\ draw one character
: drc ( c -- )
  a>bp
  5 0 do
    dup c@ wram
    1+
  loop
  drop ;

\ output u columns of blank pixels (space)
: spc ( u -- )
  0 do 0 wram loop ;

\ display text compiled with $"
: dtext ( adr n -- )
  \ count
  0 do
    dup c@
    dup 32 = if
      3 spc drop
    else
      drc 1 spc
    then
    1+
  loop
  drop ;

\ display number ***** needs work
: d# ( n -- )
  dup abs <# #s swap sign #>
  0 do
    dup c@ drc 1 spc
    1+
  loop
  drop ;




\ ================================ end of code ================================
\ you can write to any location by setting 
\ •	Page address (0–7)
\ •	Column address (0–127)
\ then send the bytes with a $40 leading byte.

i2c-init
oled-init
\ $40 frameBuffer c!  \ store $40 cmd byte in frameBuffer[0]
\ frameBuffer 1025 buffer-to-oled  \ send frameBuffer to oled

