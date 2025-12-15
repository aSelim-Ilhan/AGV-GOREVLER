# AGV-AK-BA-

VİDEO

https://youtu.be/zSRH-MrxQ3o



1. Veri Kaynağı ve İletişim (STM32 & Micro-ROS)

Sistemin kalbinde, düşük seviyeli kontrolcü olan STM32 bulunur. Micro-ROS ajanı başlatıldığında, STM32 kartı ROS2 ağına 3 temel veri başlığı (topic) sunar:

    /akiba_1/rpm_info: Motorların dakikadaki devir sayısı.

    /akiba_1/cmd_vel: Hız komutlarını dinleyen veya mevcut durumu raporlayan kanal.

    /akiba_1/mps_info (Kritik Veri): Projemizin temel taşıdır. Sağ ve sol tekerleğin anlık çizgisel hızlarını (metre/saniye cinsinden) verir.

2. Veri Dönüşümü ve Odometri (Wheel Odometry)

STM32'den gelen ham hız verisi (mps_info), navigasyon için doğrudan kullanılamaz. Burada ara katman yazılımı devreye girer:

    İşleyici: mps_to_odom.py kodu.

    Görevi: Sağ ve sol tekerlek hızlarını alır, robotun kinematik modelini kullanarak (tekerlek çapı ve tekerlekler arası mesafe) robotun uzaydaki konumunu ve açısını hesaplar.

    Çıktı: /wheel_odom topic'i. Bu veri sayesinde robot, "Şu an kaç derece döndüm?" sorusunun cevabını (Yaw açısı) bilir.

3. Çevresel Algılama (Lidar)

Robotun gözü olan Lidar sensörü, ortamı sürekli tarar:

    Topic: /scan

    Görevi: Robotun önündeki nesnelerin mesafesini ölçer. Bu sayede algoritma, 0.5 metre veya 1 metre ötede bir engel olup olmadığını anlar.

4. Karar Mekanizması (Ana Kontrolcü)

Tüm bu veriler, yazdığımız Python Kontrol Düğümünde (OdomAvoider) birleşir. Algoritma şu mantıkla çalışır:

    /scan verisine bak: Önüm boş mu?

    Boşsa /cmd_vel üzerinden STM32'ye "İleri git" komutu gönder.

    Engel varsa dur ve /wheel_odom verisini referans alarak tam 90 derece dön.

<img width="2904" height="4665" alt="Robot Obstacle Avoidance-2025-12-14-183225" src="https://github.com/user-attachments/assets/d73120af-3464-4104-b1a9-991f62611824" />

ALGORİTMA

<img width="2438" height="1760" alt="mermaid-diagram-2025-12-14-212817" src="https://github.com/user-attachments/assets/0df53400-ba57-42cb-a530-abced6d63cd7" />


