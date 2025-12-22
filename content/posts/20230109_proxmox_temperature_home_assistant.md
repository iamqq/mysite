+++
title = "Передача температуры хост системы Proxmox  в Home Assistant"
description = "В качестве домашнего сервера у меня развернут Proxmox на старом ноутбуке и в нем создана виртуальная машина с Home Assistant (НА) по вот этим инструкциям. На..."

date = "2023-01-09T02:00:00Z"
draft = false
tags = ['IT']
+++

В качестве домашнего сервера у меня развернут Proxmox на старом ноутбуке  и в нем создана виртуальная машина с Home Assistant (НА) по вот этим [инструкциям](https://github.com/tteck/Proxmox).

На ноутбуке помирает вентилятор, но в целом и без него сервер не перегревается, но мне все же захотелось  контролировать температуру моего "сервера" и как-то влиять на нее.

Контролировать мне удобнее в HA, но виртуальная машина не видит показаний температуры хост системы. 

На самом сервере   я контролирую температуру командой :



    sensors  

Не помню, делал ли я что-то для установки этой программы или она по умолчаню присутсвует в системе, но инструкций по ее установке полно и если у вас ее нет, найдите и установите по инструкции.

Примерно так выглядит вывод команды (выделил интересующую меня температуру):


    coretemp-isa-0000
    Adapter: ISA adapter  
    Package id 0: +52.0°C (high = +72.0°C, crit = +90.0°C)  
    Core 0:    +52.0°C (high = +72.0°C, crit = +90.0°C)  
    Core 1:    +50.0°C (high = +72.0°C, crit = +90.0°C)
    ....


Почитав help к команде sensors обнаружил у нее приятный ключик -j - выводить в json. В HA установлен add-on "[Samba share](https://github.com/home-assistant/addons/tree/master/samba)". В итоге решил периодический опрашивать температуру через cron, скидывать через smb протокол в HA и там создать сенсор с показаниями интересующей меня температуры через интеграцию file

Вот окончательный скрипт, который я запланировал на ежеминутное исполнение в cron-е хост системы:


 
    sensors -j | tr -d '\n' >  sensors.json
    smbclient //192.168.x.x/config -U user%password --directory tmp -c 'put sensors.json'
    sleep 15
    sensors -j | tr -d '\n' >  sensors.json
    smbclient //192.168.x.x/config -U user%password --directory tmp -c 'put sensors.json'
    sleep 15
    sensors -j | tr -d '\n' >  sensors.json
    smbclient //192.168.x.x/config -U user%password --directory tmp -c 'put sensors.json'
    sleep 15
    sensors -j | tr -d '\n' >  sensors.json
    smbclient //192.168.x.x/config -U user%password --directory tmp -c 'put sensors.json'


Пояснения к коду:


sensors -j - формирую json  с информацией о температуре сервераtr -d '\n' -  убираю все переносы строк, т.к. интеграция file в HA читает только последнюю строку, т.е. мне нужно получить json  в одну строку>  sensors.json сохраняю json  в локальный файл(полная перезапись)smbclient //192.168.x.x/config -U user%password --directory tmp -c 'put sensors.json'  - закидываю файл с json в HA в папку /config/tmpsleep 15 - жду 15 секунд  - зачем? -  дело в том, что через cron можно запланировать выполнение скрипта не чаше раза в минуту, а мне же хотелось получать показания  чуть чаще, поэтому я еще три раза повторил интересующий меня блок с засыпанием в промежутке на 15 секунд, т.е. файл в HA будет обновляться примерно каждые 15 секундТеперь как создан сенсор в HA? В configuration.yaml (или куда вы там вписываете свои сенсоры) добавьте:


 
    sensor:  
      - platform: file
        name: server_temperature
        file_path: /config/tmp/sensors.json
        value_template: "{{ value_json['coretemp-isa-0000']['Package id 0']['temp1_input'] }}"
        unit_of_measurement: "°C"


Дальше я направил на ноутбук простой вентилятор и включаю его через валявшуюся у меня умную розетку при достижении критической температуры (см [generic termostat](https://www.home-assistant.io/integrations/generic_thermostat/))
