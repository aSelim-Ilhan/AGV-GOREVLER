#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Vector3
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
import math

class MPSToOdomConverter(Node):
    def __init__(self):
        super().__init__('mps_to_odom_converter')
        
        # --- KALIBRASYON HESABI ---
        # Eski deger: 0.2907
        # Hata orani: 130 derece / 90 derece = 1.444
        # Yeni deger: 0.2907 * 1.444 = 0.420 (Yaklasik)
        self.declare_parameter('wheel_base', 0.420) 
        self.declare_parameter('publish_tf', False)
        
        self.wheel_base = self.get_parameter('wheel_base').value
        self.publish_tf = self.get_parameter('publish_tf').value
        
        # Odometry state
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_time = None
        
        # TF broadcaster
        if self.publish_tf:
            self.tf_broadcaster = TransformBroadcaster(self)
        
        # QoS Profile - BEST_EFFORT reliability
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscriber - QoS profili ile
        self.mps_sub = self.create_subscription(
            Vector3,
            '/akiba_1/mps_info',
            self.mps_callback,
            qos_profile  # QoS profili eklendi
        )
        
        # Publisher
        self.odom_pub = self.create_publisher(
            Odometry,
            '/wheel_odom',
            10
        )
        
        self.get_logger().info('=' * 60)
        self.get_logger().info('🔄 MPS to Odom Converter BAŞLATILDI!')
        self.get_logger().info(f'   Wheel base: {self.wheel_base} m (Kalibre Edildi)')
        self.get_logger().info(f'   Publish TF: {self.publish_tf}')
        self.get_logger().info(f'   QoS: BEST_EFFORT')
        self.get_logger().info('=' * 60)
    
    def mps_callback(self, msg):
        """MPS verisini odometriye çevir"""
        current_time = self.get_clock().now()
        
        # İlk mesaj
        if self.last_time is None:
            self.last_time = current_time
            self.get_logger().info('✅ İlk MPS mesajı alındı!')
            return
        
        # Delta time
        dt = (current_time - self.last_time).nanoseconds / 1e9
        if dt <= 0.0:
            return
        
        # Tekerlek hızları
        right_vel = msg.x
        left_vel = msg.y
        
        # Robot hızları (diferansiyel kinematik)
        # Açısal hız hesabı buradaki wheel_base'e bağlıdır.
        # wheel_base büyüdükçe, hesaplanan açısal hız (ve dolayısıyla dönüş açısı) küçülür.
        linear_vel = (right_vel + left_vel) / 2.0
        angular_vel = (right_vel - left_vel) / self.wheel_base
        
        # Dead reckoning - Odometry güncelle
        delta_theta = angular_vel * dt
        delta_s = linear_vel * dt
        
        # Yeni pozisyon
        self.x += delta_s * math.cos(self.theta + delta_theta / 2.0)
        self.y += delta_s * math.sin(self.theta + delta_theta / 2.0)
        self.theta += delta_theta
        
        # Theta'yı [-pi, pi] aralığında tut
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))
        
        # Odometry mesajı
        odom_msg = Odometry()
        odom_msg.header.stamp = current_time.to_msg()
        odom_msg.header.frame_id = 'odom'
        odom_msg.child_frame_id = 'base_link'
        
        # Pose
        odom_msg.pose.pose.position.x = self.x
        odom_msg.pose.pose.position.y = self.y
        odom_msg.pose.pose.position.z = 0.0
        
        # Orientation (quaternion from yaw)
        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)
        odom_msg.pose.pose.orientation.x = 0.0
        odom_msg.pose.pose.orientation.y = 0.0
        odom_msg.pose.pose.orientation.z = qz
        odom_msg.pose.pose.orientation.w = qw
        
        # Pose covariance (encoder uncertainty)
        odom_msg.pose.covariance[0] = 0.01   # x
        odom_msg.pose.covariance[7] = 0.01   # y
        odom_msg.pose.covariance[14] = 1e6   # z (not used)
        odom_msg.pose.covariance[21] = 1e6   # roll (not used)
        odom_msg.pose.covariance[28] = 1e6   # pitch (not used)
        odom_msg.pose.covariance[35] = 0.1   # yaw
        
        # Twist (current velocities)
        odom_msg.twist.twist.linear.x = linear_vel
        odom_msg.twist.twist.linear.y = 0.0
        odom_msg.twist.twist.linear.z = 0.0
        odom_msg.twist.twist.angular.x = 0.0
        odom_msg.twist.twist.angular.y = 0.0
        odom_msg.twist.twist.angular.z = angular_vel
        
        # Twist covariance
        odom_msg.twist.covariance[0] = 0.01   # x_vel
        odom_msg.twist.covariance[7] = 0.01   # y_vel
        odom_msg.twist.covariance[14] = 1e6   # z_vel
        odom_msg.twist.covariance[21] = 1e6   # roll_vel
        odom_msg.twist.covariance[28] = 1e6   # pitch_vel
        odom_msg.twist.covariance[35] = 0.05  # yaw_vel
        
        # Yayınla
        self.odom_pub.publish(odom_msg)
        
        # TF yayınla (opsiyonel)
        if self.publish_tf:
            t = TransformStamped()
            t.header.stamp = current_time.to_msg()
            t.header.frame_id = 'odom'
            t.child_frame_id = 'base_link'
            t.transform.translation.x = self.x
            t.transform.translation.y = self.y
            t.transform.translation.z = 0.0
            t.transform.rotation.x = 0.0
            t.transform.rotation.y = 0.0
            t.transform.rotation.z = qz
            t.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(t)
        
        # Güncelle
        self.last_time = current_time


def main(args=None):
    rclpy.init(args=args)
    node = MPSToOdomConverter()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('\n🛑 Converter durduruldu.')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
