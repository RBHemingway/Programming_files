pwm import
timer import

\ The blinker maximum input shade
variable shade-max-input-shade

\ The blinker maximum shade
variable shade-max-shade

\ The blinker shading
variable shade-shade

\ The blinker shade step delay in 100 us increments
variable shade-step-delay

\ The blinker multiplier
2variable shade-multiply

\ The blinker pre-multiplier
2variable shade-premultiply

\ Shade increment
variable shade-increment

\ Shade level
variable shade-level

\ Maximum shade level
variable max-shade-level

\ Alarm interval
variable alarm-interval

\ PWM slice
4 constant pwm-slice






\ The blinker shade conversion routine
: convert-shade ( i -- shade )
  s>f shade-max-input-shade @ 
  s>f f/ pi f* cos dnegate 1,0 d+ 2,0 f/
  shade-premultiply 2@ f* 
  expm1 shade-premultiply 2@ expm1 f/
  shade-multiply 2@ f* f>s
;    

\ Alarm handler
defer handle-alarm
:noname ( -- )

  0 clear-alarm-int

  [:
Here we increment or decrement shade-level, alternating direction when shade-level reaches 0 or shade-max-input-shade:

    shade-level @ 0<= if
      shade-increment @ abs shade-increment !
    else
      shade-level @ shade-max-input-shade @ >= if
        shade-increment @ abs negate shade-increment !
      then
    then
    shade-increment @ shade-level +!
Here we convert shade-level into a duty cycle value from 0 to max-shade-level, i.e. a duty cycle of 100%, with convert-shade and set the PWM slice compare value for pin B for PWM slice 4 to this value:

    shade-level @ convert-shade pwm-slice pwm-counter-compare-b!
Here we actually catch any exceptions and execute them, to display a message, without causing any unnecessary problems:

  ;] try ?execute
Here we reset alarm 0 for handle-alarm at us-counter-lsb plus alarm-interval:

  us-counter-lsb alarm-interval @ +  ['] handle-alarm 0 set-alarm
; ' handle-alarm defer!
Here we run our LED shader:

\ Shade an LED
: run-shade-led ( -- )
  pwm-slice bit disable-pwm 
  \ Here we disable PWM slice 4:

  125 shade-max-input-shade !
  125,0 shade-multiply 2!
  15,0 shade-premultiply 2!
  2500 alarm-interval !
  0 shade-level !
  1 shade-increment !

  shade-max-input-shade @ convert-shade max-shade-level !

  25 pwm-pin





  0 pwm-slice pwm-counter!
  max-shade-level @ pwm-slice pwm-top!



  0 255 pwm-slice pwm-clock-div!



  true pwm-slice pwm-phase-correct!

  pwm-slice bit enable-pwm
  \ Here we enable PWM slice 4:

  us-counter-lsb alarm-interval @ + 
  ['] handle-alarm 0 set-alarm
;
