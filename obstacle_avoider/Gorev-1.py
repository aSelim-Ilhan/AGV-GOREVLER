import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
import math

class OdomAvoider(Node):
    def __init__(self):
        super().__init__('odom_avoider_node')

        # --- Topic Ayarları ---
        # Hız komutlarını robotuna gönderiyoruz
        self.cmd_pub = self.create_publisher(Twist, '/akiba_1/cmd_vel', 10)
        
        # Lidar verisi
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        
        # ODOMETRİ VERİSİ
        # Senin mps_to_odom.py dosyasının yayınladığı topic'i dinliyoruz
        self.odom_sub = self.create_subscription(Odometry, '/wheel_odom', self.odom_callback, 10)

        # Değişkenler
        self.current_yaw = 0.0
        self.start_yaw = 0.0
        self.target_angle = 90.0  # 90 derece dön
        self.state = "FORWARD" 
        
        self.obstacle_distance = 10.0
        self.wait_start_time = None # Bekleme süresini tutmak için
        
        # Timer: 10Hz (Saniyede 10 kere döngü)
        self.timer = self.create_timer(0.1, self.control_loop)
        
        self.get_logger().info("Odom (Wheel) Destekli Engel Aşma Başlatıldı!")

    def odom_callback(self, msg):
        """
        mps_to_odom.py dosyasından gelen /wheel_odom verisini işler.
        Quaternion -> Euler (Yaw) dönüşümü yapar.
        """
        q = msg.pose.pose.orientation
        
        # Quaternion to Euler (Yaw) dönüşümü
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        yaw_rad = math.atan2(siny_cosp, cosy_cosp)
        
        # Radyanı dereceye çeviriyoruz
        self.current_yaw = math.degrees(yaw_rad)

    def scan_callback(self, msg):
        """Lidar verisinden önündeki mesafeyi hesaplar"""
        # Tam karşıdaki açılardan mesafe al
        mid_i = len(msg.ranges) // 2
        
        # Karşıdaki 10 derecelik ince bir dilimi kontrol et
        ranges = msg.ranges[mid_i-10 : mid_i+10]
        
        # Geçerli okumaları filtrele (0.05m ile 10m arası)
        valid = [r for r in ranges if 0.05 < r < 10.0]
        
        if valid:
            self.obstacle_distance = sum(valid) / len(valid)
        else:
            self.obstacle_distance = 10.0

    def normalize_angle(self, angle):
        """Açıyı -180 ile +180 arasına sıkıştırır"""
        while angle > 180: angle -= 360
        while angle < -180: angle += 360
        return angle

    def control_loop(self):
        cmd = Twist()

        # --- DURUM 1: DÜZ GİT ---
        if self.state == "FORWARD":
            if self.obstacle_distance < 0.5: # 0.5 Metre kala dur
                self.get_logger().warn(f"Engel tespit edildi ({self.obstacle_distance:.2f}m)! Duruluyor...")
                self.state = "WAIT"
                self.wait_start_time = self.get_clock().now() # Sayacı başlat
                cmd.linear.x = 0.0
            else:
                cmd.linear.x = 0.2
                cmd.angular.z = 0.0

        # --- DURUM 2: BEKLEME (5 SANİYE) ---
        elif self.state == "WAIT":
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            
            # Geçen süreyi hesapla
            current_time = self.get_clock().now()
            elapsed_time = (current_time - self.wait_start_time).nanoseconds / 1e9 
            
            if elapsed_time >= 5.0:
                self.get_logger().info("5 Saniye doldu. Engel hala orada mı bakılıyor...")
                self.state = "CHECK_OBSTACLE"

        # --- DURUM 3: ENGEL KONTROLÜ ---
        elif self.state == "CHECK_OBSTACLE":
            cmd.linear.x = 0.0
            
            if self.obstacle_distance > 1.0:
                # Engel gitmiş!
                self.get_logger().info("Engel kalkmış! Yola devam ediliyor.")
                self.state = "FORWARD"
            else:
                # Engel hala orada!
                self.get_logger().warn("Engel hala orada! Sağa dönülüyor.")
                self.start_yaw = self.current_yaw # Şu anki açıyı referans al
                self.state = "TURN_RIGHT"

        # --- DURUM 4: SAĞA DÖN (ODOMETRİ İLE) ---
        elif self.state == "TURN_RIGHT":
            # Ne kadar döndüğümüzü hesapla (normalize edilmiş fark)
            diff = self.normalize_angle(self.current_yaw - self.start_yaw)
            turned_amount = abs(diff)
            
            if turned_amount >= self.target_angle:
                self.get_logger().info("90 Derece Sağa Dönüş Tamamlandı! 3 Saniye bekleniyor...")
                # BURASI DEĞİŞTİ: Hemen FORWARD yapmıyoruz, yeni bekleme moduna geçiyoruz.
                self.state = "WAIT_AFTER_TURN"
                self.wait_start_time = self.get_clock().now() # Yeni sayaç başlat
                
                cmd.angular.z = 0.0
                cmd.linear.x = 0.0
            else:
                cmd.linear.x = 0.0
                # SAĞA DÖNÜŞ İÇİN NEGATİF AÇISAL HIZ
                cmd.angular.z = -0.3 

        # --- DURUM 5: DÖNÜŞ SONRASI BEKLEME (YENİ EKLENDİ) ---
        elif self.state == "WAIT_AFTER_TURN":
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

            # Geçen süreyi hesapla
            current_time = self.get_clock().now()
            elapsed_time = (current_time - self.wait_start_time).nanoseconds / 1e9

            if elapsed_time >= 3.0:
                self.get_logger().info("Dönüş sonrası 3 saniye bekleme bitti. Yola devam ediliyor.")
                self.state = "FORWARD"

        # Mesajı yayınla
        self.cmd_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = OdomAvoider()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Durduruluyor...")
    finally:
        # Dururken robotu güvenli hale getir
        stop_cmd = Twist()
        node.cmd_pub.publish(stop_cmd)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
