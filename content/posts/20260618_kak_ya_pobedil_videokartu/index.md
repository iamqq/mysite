+++
title = "Как я неделю воевал с собственной видеокартой (и победил)"
description = "История о том, как заставить NVIDIA Quadro P2000 работать в контейнере Frigate под Debian trixie, понизить ядро, побороть privileged mode в Docker и победить особенности CUDA-графов."
date = "2026-06-18T19:00:00Z"
image = "nvidia_homelab.png"
draft = false
tags = ["разработка", "homelab", "nvidia", "docker", "frigate"]
+++

Я держу домашнюю лабораторию (homelab). Те, кто в теме, знают: это хобби находится где-то на стыке продуктивности и одержимости. Это когда ты тратишь три вечера на исправление того, что и так технически работало, просто ради того, чтобы оно работало *лучше*. Это как раз одна из таких историй.

## Стенд

Мой домашний NVR (сетевой видеорегистратор) работает на базе **Frigate** — self-hosted системы видеонаблюдения с распознаванием объектов с помощью искусственного интеллекта. Она умеет отличать человека от кошки или от качающейся на ветру тени. Всё это крутится в Docker на сервере с OpenMediaVault, а управление идет через Portainer.

Долгое время Frigate работал отлично. Объекты распознавались. Камеры писали. Жизнь была прекрасна.

Но тут я наткнулся на NVIDIA Quadro P2000 по очень привлекательной цене и подумал: *«Эта штука может взять на себя распознавание объектов, разгрузив процессор»*. За этим решением последовала неделя отладки, которую я в основном проходил рука об руку с Claude, ИИ-ассистентом от Anthropic. В этом посте я подробно описываю весь путь, со всеми ошибками и граблями, чтобы вам не пришлось наступать на них самим.

---

## Акт 1: Не тот драйвер

На сервере установлена Debian trixie (в сборке OMV). На тот момент из репозитория trixie-backports метапакетом `linux-image-amd64` было подтянуто ядро **7.0.10**.

Первая ошибка: я установил первый попавшийся драйвер NVIDIA, который Debian предложила по умолчанию — ветку **610.x**. Установка прошла без ошибок, но утилита `nvidia-smi` видеокарту в упор не видела. Немного поисков в логах выявили причину: начиная с ветки 610.x, NVIDIA прекратила поддержку видеокарт поколения Pascal (к которым относятся Quadro P2000, серия GTX 10xx и их собратья). Драйвер просто установился, ничего не нашел и молча проигнорировал плату.

```
NVRM: GPU at PCI:0000:03:00: GPU-...
NVRM: GPU Board Serial Number: [N/A]
NVRM: Xid (PCI:0000:03:00): 79, ...
```

Вывод `dmesg` выразился предельно ясно: *«supported through the NVIDIA 580.xx Legacy drivers. The 610.43.02 driver will ignore this GPU.»* (поддерживается устаревшими драйверами NVIDIA 580.xx. Драйвер 610.43.02 проигнорирует этот графический процессор).

Значит, нужна более старая ветка драйвера. Для архитектуры Pascal подходит **550.x** (или 535.x, которую я тоже успел попробовать). Но именно здесь всё пошло наперекосяк.

---

## Акт 2: Проблема с ядром

Драйвер 550.x собирает свой модуль ядра через DKMS — то есть компилирует его под запущенное ядро. И в ядре **7.0** удалили или переименовали несколько внутренних API, от которых зависит драйвер 550.x:

| Ошибка в make.log | Причина |
|---|---|
| `VMA_LOCK_OFFSET undeclared` | Удалено в ядре 6.x |
| `__vm_flags has no member` | Переименовано в ядре 6.3 |
| `implicit declaration of in_irq()` | Удалено в ядре 6.10 |

В результате сборка DKMS завершалась ошибкой. Драйвер не мог скомпилироваться. Видеокарта продолжала лежать мертвым грузом.

Решение: откатить ядро до версии **6.12.x**. Оно достаточно свежее, чтобы быть в репозиториях Debian trixie, но при этом драйвер 550.x успешно собирается под него.

```bash
apt-get install linux-image-6.12.90+deb13.1-amd64 \
               linux-headers-6.12.90+deb13.1-amd64
```

Затем загрузились в него через разовый `grub-reboot`, проверили работу и сделали эту загрузку постоянной:

```bash
sed -i 's/GRUB_DEFAULT=.*/GRUB_DEFAULT="gnulinux-advanced-UUID>gnulinux-6.12.90+deb13.1-amd64-advanced-UUID"/' \
  /etc/default/grub
update-grub
```

Удаляем заголовки ядра 7.0, чтобы DKMS даже не пытался компилироваться под них:

```bash
apt-get remove linux-headers-7.0.10+deb13-amd64 \
               linux-headers-7.0.10+deb13-common
```

И фиксируем (pin) версию ядра, чтобы `apt upgrade` случайно снова не накатил версию 7.0:

```bash
cat > /etc/apt/preferences.d/kernel-pin << 'EOF'
Package: linux-image-amd64
Pin: release a=trixie-backports
Pin-Priority: -1
EOF
```

Also blacklist nouveau, which was claiming the GPU:

```bash
echo "blacklist nouveau" > /etc/modprobe.d/blacklist-nouveau.conf
echo "options nouveau modeset=0" >> /etc/modprobe.d/blacklist-nouveau.conf
update-initramfs -u
```

После перезагрузки на ядро 6.12 драйвер наконец установился, и `nvidia-smi` выдал долгожданные строчки:

```
NVIDIA-SMI 550.163.01   Driver Version: 550.163.01   CUDA Version: 12.4
Quadro P2000   5120MiB
```

---

## Акт 3: Проброс GPU в контейнер

Frigate крутится в Docker. Чтобы пробросить видеокарту внутрь контейнера, требуется **nvidia-container-toolkit**. Он уже был установлен, но не внедрял библиотеки должным образом, так как контейнер запускался в режиме `privileged: true`.

Это было крайне неочевидное и болезненное открытие. Когда Docker запускает контейнер как привилегированный, он монтирует все устройства хоста напрямую. Инструментарий `nvidia-container-toolkit` видит это и пропускает свой стандартный этап внедрения библиотек, полагая, что у контейнера и так есть полный доступ к устройствам. Но без этого внедрения библиотеки CUDA просто не попадают внутрь контейнера.

Отключение `privileged: true` в файле compose решило проблему с интеграцией библиотек:

```yaml
services:
  frigate:
    container_name: frigate
    runtime: nvidia
    # privileged: true  ← удалено
```

Но возникла другая сложность: toolkit работал в режиме CDI (автоопределение), который требует сгенерированных файлов спецификации устройств, коих не было. Переключаемся в legacy-режим, который выполняет корректное монтирование библиотек через bind-mount:

```bash
nvidia-ctk config --in-place --set nvidia-container-runtime.mode=legacy
systemctl restart docker
```

И, наконец, `libcuda.so` — библиотека драйвера CUDA. На хосте она находилась по пути `/usr/lib/x86_64-linux-gnu/nvidia/current/libcuda.so.550.163.01`, но символические ссылки (`libcuda.so.1`, `libcuda.so`) вели на пустую директорию, оставшуюся от прошлых неудачных попыток установки. Установка нужного пакета всё исправила:

```bash
apt-get install libcuda1
```

После полного пересоздания контейнера (именно пересоздания, а не просто перезапуска, так как toolkit внедряет библиотеки в момент создания контейнера), `nvidia-smi` внутри контейнера наконец показал рабочую CUDA 12.4.

---

## Акт 4: Детектор ONNX

Frigate использует библиотеку ONNX Runtime для распознавания объектов. Теперь, когда GPU виден, пришло время настроить ONNX-детектор:

```yaml
detectors:
  onnx:
    type: onnx
    device: cuda

model:
  model_type: yolo-generic
  width: 320
  height: 320
  input_tensor: nchw
  input_dtype: float
  path: /config/model_cache/yolov9-t-320.onnx
  labelmap_path: /labelmap/coco-80.txt
```

Сама модель была экспортирована из YOLOv9t с помощью утилиты `ultralytics` на хосте:

```bash
pip install ultralytics onnx onnxslim --break-system-packages
python3 -c "from ultralytics import YOLO; YOLO('yolov9t.pt').export(format='onnx', imgsz=320)"
cp /root/yolov9t.onnx /mnt/share/app/portainer/frigate/config/model_cache/yolov9-t-320.onnx
```

Но запуск тут же упал с ошибкой:

```
ONNXRuntimeError: This session cannot use the graph capture feature as requested
by the user as all compute graph nodes have not been partitioned to the
CUDAExecutionProvider
```

В коде Frigate жестко прописано `"enable_cuda_graph": True` при использовании CUDA, однако модель yolov9t содержит узлы, несовместимые с захватом CUDA-графа (graph capture). Настроек, позволяющих отключить это поведение в конфигурационном файле, нет — пришлось править исходный код Frigate напрямую:

```bash
docker exec frigate sed -i \
  's/"enable_cuda_graph": True/"enable_cuda_graph": False/' \
  /opt/frigate/frigate/detectors/detection_runners.py
```

Чтобы это изменение сохранялось при пересоздании контейнера, пропатченный файл монтируется из локальной папки:

```bash
docker cp frigate:/opt/frigate/frigate/detectors/detection_runners.py \
  /mnt/share/app/portainer/frigate/config/detection_runners.py
```

```yaml
volumes:
  - /mnt/share/app/portainer/frigate/config/detection_runners.py:/opt/frigate/frigate/detectors/detection_runners.py:ro
```

---

## Акт 5: Декодирование видео на GPU

Когда детектор заработал на видеокарте, следующей целью стало аппаратное декодирование. Камеры отдают поток H264, и ffmpeg (используемый внутри Frigate) умеет перекладывать задачу декодирования H264 на аппаратный декодер NVDEC.

Для этого понадобились еще две недостающие библиотеки:

```bash
apt-get install libnvcuvid1    # библиотека декодера NVDEC
apt-get install libnvrtc12     # CUDA JIT компилятор (нужен для фильтра scale_cuda)
```

Их обе пришлось явно пробросить в контейнер через volumes, так как toolkit автоматически их не подхватывал:

```yaml
volumes:
  - /usr/lib/x86_64-linux-gnu/nvidia/current/libcuda.so.550.163.01:/usr/lib/x86_64-linux-gnu/libcuda.so.1:ro
  - /usr/lib/x86_64-linux-gnu/nvidia/current/libnvcuvid.so.550.163.01:/usr/lib/x86_64-linux-gnu/libnvcuvid.so.1:ro
  - /usr/lib/x86_64-linux-gnu/libnvrtc.so.12:/usr/lib/x86_64-linux-gnu/libnvrtc.so.12:ro
  - /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.4:/usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.4:ro
```

Кроме того, для `libnvrtc` нужно было создать симлинки внутри контейнера (сделано через стартовый скрипт):

```bash
#!/bin/bash
# fix-libs.sh
pip install py3nvml --break-system-packages --quiet
ln -sf /usr/local/lib/python3.11/dist-packages/nvidia/cuda_nvrtc/lib/libnvrtc.so.12 \
  /usr/lib/x86_64-linux-gnu/libnvrtc.so
ln -sf /usr/local/lib/python3.11/dist-packages/nvidia/cuda_nvrtc/lib/libnvrtc-builtins.so.12.5 \
  /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so
ldconfig
```

Запуск скрипта прописан в compose через переопределение точки входа (entrypoint):

```yaml
entrypoint: ["/bin/bash", "-c", "/config/fix-libs.sh && exec /init"]
```

Конфигурация hwaccel во Frigate:

```yaml
ffmpeg:
  hwaccel_args:
    - -hwaccel
    - cuda
    - -hwaccel_output_format
    - nv12
```

Примечание: встроенный пресет Frigate `preset-nvidia-h264` использует фильтр `scale_cuda`, который требует компилятор PTX JIT. И хотя библиотека есть, возникли проблемы совместимости. Ручные параметры выше используют NVDEC для декодирования, но откатываются на CPU для масштабирования (scale), что является разумным компромиссом.

---

## Акт 6: Субпотоки и финальная оптимизация

Камеры (три штуки Tapo и одна Yi 1080p) поддерживают двойной поток — основной в высоком разрешении и субпоток (640×360). Использование субпотока для детекции и основного потока для записи полностью избавляет CPU от необходимости сжимать 1080p кадры до разрешения детектора:

```yaml
go2rtc:
  streams:
    frontyard_tapo:
      - rtsp://tapocamera:***@192.168.86.187:554/stream1
    frontyard_tapo_sub:
      - rtsp://tapocamera:***@192.168.86.187:554/stream2
    # ... аналогично для других камер

cameras:
  frontyard_tapo:
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/frontyard_tapo?video=h264&audio=opus
          roles:
            - record
        - path: rtsp://127.0.0.1:8554/frontyard_tapo_sub?video=h264
          roles:
            - detect
    detect:
      height: 320
      width: 320
      fps: 3
```

---

## Акт 7: Статистика GPU в веб-интерфейсе

И последнее неудобство: панель статистики GPU в веб-интерфейсе Frigate упорно пустовала. Причина крылась в одной строчке исходного кода Frigate:

```python
elif "cuvid" in args or "nvidia" in args:
    # nvidia GPU — collect stats
```

Наши параметры hwaccel (`-hwaccel cuda`) не содержат ни `cuvid`, ни `nvidia`, поэтому сбор метрик GPU Frigate просто не запускал. Патчим код:

```bash
docker exec frigate sed -i \
  's/elif "cuvid" in args or "nvidia" in args:/elif "cuvid" in args or "nvidia" in args or "cuda" in args:/' \
  /opt/frigate/frigate/stats/util.py
```

И также пробрасываем этот файл через bind-mount.

---

## Финал

После всех этих манипуляций вот как выглядит работающая система:

**Три пропатченных файла**, смонтированных внутрь контейнера:
- `detection_runners.py` — отключает CUDA graph capture
- `stats_util.py` — включает сбор метрик GPU для аргументов `cuda`
- `fix-libs.sh` — создает симлинки для nvrtc и устанавливает py3nvml на старте

**Задачи GPU:**
- Декодирование видео H264 (NVDEC) для всех 4 камер
- Инференс детектора через ONNX Runtime с CUDAExecutionProvider

**Задачи CPU:**
- Масштабирование кадров (640×360 → 320×320, очень легкая задача)
- Управление процессами Python
- Запись видео, MQTT, веб-интерфейс

**Производительность:** Сервер работал неплохо и до этого, но теперь нагрузка на процессор хоста упала настолько, что он практически не замечает работу Frigate.

**Веб-интерфейс Frigate теперь показывает:**
- Скорость инференса детектора (inference speed)
- Нагрузку на CPU от детектора
- Загрузку GPU (Quadro P2000 utilization %)

---

## О роли ИИ (Claude)

Хочу сказать честно: большая часть этой отладки прошла в диалоге с Claude. Не потому, что я не справился бы сам, а потому, что цепочка ошибок была слишком длинной и каждое исправление вскрывало новый слой проблем. Не тот драйвер, неподходящее ядро, битая ссылка, конфликт `privileged` режима, сбой инжекции CUDA, несовместимость графов ONNX, отсутствие `libnvcuvid`, отсутствие симлинков `libnvrtc`, зашитые строки в статистике Frigate.

Иметь ИИ-ассистента, который держит весь контекст сессии, помнит предыдущие шаги и рассуждает о причинах ошибок, сэкономило кучу времени. Claude просил конкретные выводы диагностики, вчитывался в них и находил реальную причину вместо банального перебора вариантов. По логу ошибки он сразу указывал на нужную строку кода Frigate. Если фикс не срабатывал, он менял гипотезу, а не твердил одно и то же.

Это не магия. Claude тоже ошибался — к выводу о конфликте режима `privileged` мы пришли далеко не сразу. Но в целом процесс прошел в разы быстрее и с меньшим количеством потраченных нервных клеток.

---

## Полный Compose-файл

```yaml
services:
  frigate:
    container_name: frigate
    runtime: nvidia
    restart: unless-stopped
    stop_grace_period: 30s
    image: ghcr.io/blakeblackshear/frigate:stable-tensorrt
    entrypoint: ["/bin/bash", "-c", "/config/fix-libs.sh && exec /init"]
    shm_size: "512mb"
    labels:
      - autoheal=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu, video]
    devices:
      - /dev/dri:/dev/dri
      - /dev/nvidia0:/dev/nvidia0
      - /dev/nvidiactl:/dev/nvidiactl
      - /dev/nvidia-modeset:/dev/nvidia-modeset
      - /dev/nvidia-uvm:/dev/nvidia-uvm
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /mnt/share/app/portainer/frigate/config:/config
      - /mnt/share/observation/frigate:/media/frigate
      - /usr/lib/x86_64-linux-gnu/nvidia/current/libcuda.so.550.163.01:/usr/lib/x86_64-linux-gnu/libcuda.so.1:ro
      - /usr/lib/x86_64-linux-gnu/nvidia/current/libnvcuvid.so.550.163.01:/usr/lib/x86_64-linux-gnu/libnvcuvid.so.1:ro
      - /usr/lib/x86_64-linux-gnu/libnvrtc.so.12:/usr/lib/x86_64-linux-gnu/libnvrtc.so.12:ro
      - /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.4:/usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.4:ro
      - /mnt/share/app/portainer/frigate/config/detection_runners.py:/opt/frigate/frigate/detectors/detection_runners.py:ro
      - /mnt/share/app/portainer/frigate/config/stats_util.py:/opt/frigate/frigate/stats/util.py:ro
      - type: tmpfs
        target: /tmp/cache
        tmpfs:
          size: 1000000000
    ports:
      - "1984:1984"
      - "8971:8971"
      - "8550:5000"
      - "8554:8554"
      - "8555:8555/tcp"
      - "8555:8555/udp"
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility,video
      - ORT_DISABLE_THREAD_AFFINITY=1
      - OMP_PROC_BIND=false
      - OMP_NUM_THREADS=2
      - SHOW_NV_STATS=1
```

---

## Полный config.yml

```yaml
auth:
  failed_login_rate_limit: 1/second;5/minute;20/hour
  trusted_proxies:
    - 192.168.86.0/24

mqtt:
  enabled: true
  host: 192.168.86.177
  port: 1883
  topic_prefix: frigate
  client_id: frigate
  user: "***"
  password: "***"

ffmpeg:
  hwaccel_args:
    - -hwaccel
    - cuda
    - -hwaccel_output_format
    - nv12

go2rtc:
  streams:
    yi_home_1080p:
      - rtsp://192.168.86.195/ch0_0.h264
    yi_home_1080p_sub:
      - rtsp://192.168.86.195/ch0_1.h264
    frontyard_tapo:
      - rtsp://***:***@192.168.86.187:554/stream1
    frontyard_tapo_sub:
      - rtsp://***:***@192.168.86.187:554/stream2
    backyard_tapo:
      - rtsp://***:***@192.168.86.247:554/stream1
    backyard_tapo_sub:
      - rtsp://***:***@192.168.86.247:554/stream2
    backyard_r_tapo:
      - rtsp://***:***@192.168.86.237:554/stream1
    backyard_r_tapo_sub:
      - rtsp://***:***@192.168.86.237:554/stream2

cameras:
  yi_home_1080p:
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/yi_home_1080p?video=h264&audio=opus
          roles:
            - record
        - path: rtsp://127.0.0.1:8554/yi_home_1080p_sub?video=h264
          roles:
            - detect
    detect:
      height: 320
      width: 320
      fps: 3

  frontyard_tapo:
    enabled: true
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/frontyard_tapo?video=h264&audio=opus
          roles:
            - record
        - path: rtsp://127.0.0.1:8554/frontyard_tapo_sub?video=h264
          roles:
            - detect
    detect:
      height: 320
      width: 320
      fps: 3
    zones:
      frontyard:
        coordinates: 0.001,0.996,0.001,0.292,0.425,0,0.68,0,0.999,0.508,0.998,0.997

  backyard_tapo:
    enabled: true
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/backyard_tapo?video=h264&audio=opus
          roles:
            - record
        - path: rtsp://127.0.0.1:8554/backyard_tapo_sub?video=h264
          roles:
            - detect
    detect:
      height: 320
      width: 320
      fps: 3
    zones:
      backyard:
        coordinates: 0.519,0.031,0.599,0.009,0.997,0.642,0.999,0.996,0,0.999
        loitering_time: 1
        inertia: 3

  backyard_r_tapo:
    enabled: true
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/backyard_r_tapo?video=h264&audio=opus
          roles:
            - record
        - path: rtsp://127.0.0.1:8554/backyard_r_tapo_sub?video=h264
          roles:
            - detect
    detect:
      height: 320
      width: 320
      fps: 3

detectors:
  onnx:
    type: onnx
    device: cuda

model:
  model_type: yolo-generic
  width: 320
  height: 320
  input_tensor: nchw
  input_dtype: float
  path: /config/model_cache/yolov9-t-320.onnx
  labelmap_path: /labelmap/coco-80.txt

record:
  enabled: true
  continuous:
    days: 0
  motion:
    days: 7

objects:
  track:
    - person
    - cat
    - dog
    - bird
  filters:
    person:
      threshold: 0.6

snapshots:
  enabled: true
  timestamp: true
  bounding_box: false
  crop: false
  height: 175
  retain:
    default: 10
    objects:
      person: 15

detect:
  enabled: true
version: 0.17-0

classification:
  bird:
    enabled: true
```

---

*Если вы пытаетесь сделать что-то подобное, главные уроки здесь следующие: проверяйте совместимость поколения видеокарты перед выбором ветки драйверов, никогда не запускайте `nvidia-container-toolkit` с `privileged: true`, всегда делайте полное пересоздание контейнера (а не просто перезапуск) после изменения настроек рантайма и не недооценивайте количество библиотек, необходимых CUDA. Каждая из них будет отваливаться отдельно и сообщать, чего ей не хватает на следующем шаге.*
