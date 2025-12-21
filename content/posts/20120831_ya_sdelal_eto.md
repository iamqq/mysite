+++
title = "Я сделал это"
description = "До переименования"
image = "/images/blogspot/iamqq/before.png"
date = "2012-08-31T08:31:00Z"
draft = false
tags = ['programmirovanie']
+++

![before.png](/images/blogspot/iamqq/before.png)
До переименования

Я сделал это! Я написал bat файл для переименования каталогов фотографий.

Сохраняем текст программы в файл с расширением bat и запускаем его в папке, содержащей библиотеку фотографий (т.е в папке, содержащей подпапки с фотографиями). Программа обходит все подпапки в текущей папке, анализирует дату создания и добавит в имена подпапок период дат хранящихся  в них фотографий.


![after.png](/images/blogspot/iamqq/after.png)
После переименования





Протокол пеерименования:



( 2011.05.16 - 2011.05.16 ) 2011-05-16 -  2011.05.16-2011-05-16

( 2007.09.28 - 2011.04.04 ) _Разобрать -  2007.09.28-2011.04.04-_Разобрать



Работает на 1 уровень. Дерево целиком не разматывает.






@echo off
setlocal enabledelayedexpansion
for /D %%f in (*) do (
        echo %%f
 dir /O:D /T:W /4 "%%f\*.jpg" > tmp
 set /a crow=0
 FOR /F "eol=  skip=5 tokens=1,2,3  delims=. " %%i in (tmp) do (
  set /a crow+=1
 )
 set /a crow-=2
 set /a mrow=0
 FOR /F "eol=  skip=5 tokens=1,2,3  delims=. " %%i in (tmp) do (
  set /a mrow+=1
  if !mrow! LEQ !crow! (
rem echo #mrow= !mrow!  crow= !crow!
   set "day=%%i"
   set "month=%%j"
   set "year=%%k"
   set dat=%%k%%j%%i
   echo # !year!.!month!.!day! - !dat! - !ndat! - !xdat!
   if !mrow! == 1 (
    set xyear=!year!
    set xmonth=!month!
    set xday=!day!
    set nyear=!year!
    set nmonth=!month!
    set nday=!day!
    set xdat=!xyear!!xmonth!!xday!
    set ndat=!nyear!!nmonth!!nday!
rem echo "f0"
   )
   if !dat! GTR !xdat! (
    set xyear=!year!
    set xmonth=!month!
    set xday=!day!
    set xdat=!xyear!!xmonth!!xday!
rem echo "f1"
   )
   if !dat! LSS !ndat! (
    set nyear=!year!
    set nmonth=!month!
    set nday=!day!
    set ndat=!nyear!!nmonth!!nday!
rem echo "f2"
   )
  )
  echo ##!year!.!month!.!day! - !dat! - !ndat! - !xdat! 
 )
 echo ### !nyear!.!nmonth!.!nday! - !xyear!.!xmonth!.!xday!
 if !xyear! == !nyear! (
  set fdate=!nyear!
  if !xmonth! == !nmonth! (
   set fdate=!fdate!.!nmonth!
   if !xday! == !nday! (
    set fdate=!fdate!.!nday!
   ) else (
    set fdate=!fdate!.!nday!-!xday!
   )    
  ) else (
   set fdate=!fdate!.!nmonth!.!nday!-!xmonth!.!xday!
  )

 ) else (

  set fdate=!nyear!.!nmonth!.!nday!-!xyear!.!xmonth!.!xday!
 )
 set "ouname=!fdate!-%%f"
 set "inname=%%f"
echo ( !nyear!.!nmonth!.!nday! - !xyear!.!xmonth!.!xday! ^) !inname! -  !ouname! 
  rename "!inname!" "!ouname!" 
)
