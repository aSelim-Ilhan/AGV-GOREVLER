import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import subprocess
import os

class StraightDriver(Node):
    def __init__(self):
        super().__init__('straight_driver_node')
        
        # Hız komutu yayınlayıcı
        self.cmd_pub = self.create_publisher(Twist, '/akiba_1/cmd_vel', 10)
        
        # Parametreler
        self.linear_speed = 0.2  # m/s
        self.drive_duration = 20.0  # 20 saniye
        
        # Durum değişkenleri
        self.start_time = None
        self.map_saved = False
        self.driving_complete = False
        
        # Harita kayıt dizini
        self.map_dir = os.path.expanduser("~/haritalar")
        if not os.path.exists(self.map_dir):
            os.makedirs(self.map_dir)
            self.get_logger().info(f"Harita dizini oluşturuldu: {self.map_dir}")
        
        # Timer: 10Hz
        self.timer = self.create_timer(0.1, self.control_loop)
        
        self.get_logger().info(f"Düz Sürüş Başlatıldı! {self.drive_duration} saniye boyunca {self.linear_speed} m/s hızla gidilecek.")
    
    def save_map(self):
        """SLAM Toolbox ile haritayı kaydeder"""
        try:
            # Tam dosya yolu
            map_path = os.path.join(self.map_dir, "straight_drive_map")
            
            self.get_logger().info(f"Harita kaydediliyor: {map_path}")
            
            # slam_toolbox'ın serialize_map servisi
            result = subprocess.run(
                [
                    'ros2', 'service', 'call',
                    '/slam_toolbox/serialize_map',
                    'slam_toolbox/srv/SerializePoseGraph',
                    f"{{filename: '{map_path}'}}"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Servis yanıtını logla
            if result.stdout:
                self.get_logger().info(f"Servis yanıtı: {result.stdout.strip()}")
            
            if result.returncode == 0:
                self.get_logger().info(f"✓ Harita başarıyla kaydedildi!")
                self.get_logger().info(f"   📁 Konum: {self.map_dir}")
                self.get_logger().info(f"   📄 Dosya: straight_drive_map.posegraph")
                self.get_logger().info(f"   📄 Dosya: straight_drive_map.data")
                self.map_saved = True
                
                # Dosyaların var olup olmadığını kontrol et
                posegraph_exists = os.path.exists(f"{map_path}.posegraph")
                data_exists = os.path.exists(f"{map_path}.data")
                
                if posegraph_exists:
                    size = os.path.getsize(f"{map_path}.posegraph")
                    self.get_logger().info(f"   ✓ .posegraph dosyası oluşturuldu ({size} bytes)")
                else:
                    self.get_logger().warn("   ⚠ .posegraph dosyası bulunamadı")
                    
                if data_exists:
                    size = os.path.getsize(f"{map_path}.data")
                    self.get_logger().info(f"   ✓ .data dosyası oluşturuldu ({size} bytes)")
                else:
                    self.get_logger().warn("   ⚠ .data dosyası bulunamadı")
            else:
                self.get_logger().error(f"❌ Harita kaydedilemedi!")
                self.get_logger().error(f"Hata kodu: {result.returncode}")
                if result.stderr:
                    self.get_logger().error(f"Hata mesajı: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            self.get_logger().error("❌ Harita kaydetme zaman aşımına uğradı!")
        except Exception as e:
            self.get_logger().error(f"❌ Harita kaydetme hatası: {str(e)}")
    
    def control_loop(self):
        cmd = Twist()
        
        # İlk çağrıda başlangıç zamanını kaydet
        if self.start_time is None:
            self.start_time = self.get_clock().now()
            self.get_logger().info("🚀 Düz sürüş başladı!")
        
        # Geçen süreyi hesapla
        current_time = self.get_clock().now()
        elapsed_time = (current_time - self.start_time).nanoseconds / 1e9
        
        # 20 saniye boyunca düz git
        if elapsed_time < self.drive_duration:
            cmd.linear.x = self.linear_speed
            cmd.angular.z = 0.0
            
            # Her saniye bilgi ver
            if int(elapsed_time) != int(elapsed_time - 0.1):
                remaining = self.drive_duration - elapsed_time
                self.get_logger().info(f"🏃 Sürüyor... Kalan süre: {remaining:.1f} saniye")
        
        # 20 saniye doldu
        elif not self.driving_complete:
            self.get_logger().info(f"✓ {self.drive_duration} saniye tamamlandı! Robot duruyor...")
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            self.cmd_pub.publish(cmd)
            self.driving_complete = True
            
        # Harita kaydet
        elif self.driving_complete and not self.map_saved:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            self.save_map()
        
        # Her şey tamamlandı
        elif self.map_saved:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            self.get_logger().info("✅ Görev tamamlandı!")
            self.get_logger().info(f"📂 Harita konumu: {self.map_dir}")
            self.cmd_pub.publish(cmd)
            self.timer.cancel()
            return
        
        # Komutu yayınla
        self.cmd_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = StraightDriver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("⚠ Kullanıcı tarafından durduruldu...")
    finally:
        # Robotu güvenli şekilde durdur
        stop_cmd = Twist()
        node.cmd_pub.publish(stop_cmd)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
