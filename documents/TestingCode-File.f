\ 25\05\2026 19:00

\ store stack addr into sp0
variable sp0
sp@ sp0 !   \ sp0 is required in send-cmd


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
        sp0 @ sp!  
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
        sp0 @ sp!  
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

: setPixel ( x y -- )
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

: drawHLine ( x1 x2 y -- )
    \ draw horizontal line from (x1,y) to (x2,y)
    dup 3 rshift          \ x1 x2 y page
    >r                    \ x1 x2   (page on return stack)
    7 and                 \ x1 bit
    1 swap lshift         \ x1 mask

    \ compute index = x1 + page*128
    swap                  \ mask x2
    r> 7 lshift +         \ mask index

    \ OR mask into buffer[index] for each x from x1 to x2
    begin
        dup frameBuffer 1+ + c@ or dup frameBuffer 1+ + c!  \ update buffer[index]
        dup 127 < while       \ continue until we reach the end of the line
        1+                   \ move to next pixel
    repeat
    drop
;

\ : drawRectangle ( x1 y1 x2 y2 -- )
\      \ draw
\     >r >r              \ x1 y1          (r) y2 x2 
\     2dup               \ x1 y1 x1 y1    (r) y2 x2
\     r@ swap            \ x1 y1 x1 x2 y1 (r) y2 x2   
\     do                 \ loop y from y1 to y2
\         over i setPixel
\     loop

\     r> r>              \ restore x2 y2
\     >r >r              \ stash again for second vertical line
\     2dup               \ x1 y1 x1 y1
\     r@ swap            \ x1 y1 x1 y2
\     do                 \ loop y from y1 to y2
\         r@ i setPixel
\     loop

\     r> r>              \ restore x2 y2
\     2dup               \ x1 y1 x2 y2
\     swap do            \ draw top horizontal line
\         over i setPixel
\     loop

\     swap do            \ draw bottom horizontal line
\         over i setPixel
\     loop

\     2drop 2drop        \ clean up stack
\ ;






\ ================================ end of code ================================
\ you can write to any location by setting 
\ •	Page address (0–7)
\ •	Column address (0–127)
\ then send the bytes with a $40 leading byte.

i2c-init
oled-init
\ $40 frameBuffer c!  \ store $40 cmd byte in frameBuffer[0]
\ frameBuffer 1025 buffer-to-oled  \ send frameBuffer to oled