#!/usr/bin/env python3
'''
Use imu to plot path since the GPS is weak.
'''
import rospy
import math
import folium
import webbrowser
import matplotlib
matplotlib.use('Agg') 
import numpy as np
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from sensor_msgs.msg import Imu, NavSatFix
from std_msgs.msg import String, Float64
from tf.transformations import euler_from_quaternion

class recorderNode:
    def __init__(self, waypoints_file, map_path):
        self.lat, self.lon, self.heading = [], [], 0 # heading radians [-pi,pi]
        self.waypoints = self.extract_coordinates_from_kml(waypoints_file)
        self.map_path = map_path
        self.cone_flg, self.marker_flg, self.cone_dis, self.marker_dis = False, 0, False, 0
    
        rospy.Subscriber('/fix', NavSatFix, self.gps_callback) # current position of pioneer
        rospy.Subscriber('/state', String, self.state_callback)
        rospy.Subscriber('/compass/heading', Float64, self.imu_callback)
        rospy.Subscriber('/detection_msg', String, self.detection_callback) # cone_flg, bucket_flg, cone_dis, bucket_dis
        #self.rate = rospy.Rate(1)  # Set the desired receiving rate to 1 Hz

        self.image_publisher = rospy.Publisher('map_image', Image, queue_size=10) # publish map as image shown in rviz

    def extract_coordinates_from_kml(self, waypoints_file):
        with open(waypoints_file):
            tree = ET.parse(waypoints_file)
            root = tree.getroot()
        coordinates = []
        # Find all <coordinates> elements
        for element in root.iter('{http://www.opengis.net/kml/2.2}coordinates'):
            # Extract and split the coordinate values
            coords = element.text.strip().split()

            # Process each coordinate value
            for coord in coords:
                # Split the coordinate string into latitude, longitude, and optional altitude
                parts = coord.split(',')

                # Append the latitude and longitude to the coordinates array
                latitude = float(parts[1])
                longitude = float(parts[0])
                coordinates.append((latitude, longitude))
        wp_str = [f"({x},{y})" for x, y in coordinates]
        rospy.loginfo('way points: '+ ', '.join(wp_str))
        return coordinates

    def plot_path(self, state='run'):
        wp_latitudes = [coord[0] for coord in self.waypoints]
        wp_longitudes = [coord[1] for coord in self.waypoints]
        # Plot the way points and path coordinates
        plt.plot(wp_longitudes, wp_latitudes, 'ro')
        plt.plot(self.lon, self.lat, 'bo')
        plt.xlim(min(wp_longitudes) - 0.001, max(wp_longitudes) + 0.001) # 0.001 is the offset
        plt.ylim(min(wp_latitudes) - 0.001, max(wp_latitudes) + 0.001) 

        # TODO: change the calculations of heading based on its definition
        if self.cone_flg and len(self.lat) > 0:
            cone_lat = self.lat[-1] + self.cone_dis * math.cos(self.heading)*1e-5
            cone_lon = self.lon[-1] + self.cone_dis * math.sin(self.heading)*1e-5
            self.cone_flg = False
            hd_cone = plt.plot(cone_lon, cone_lat, 'r+')
        if self.marker_flg and len(self.lat) > 0:
            marker_lat = self.lat[-1] + self.marker_dis * math.cos(self.heading)*1e-5
            marker_lon = self.lon[-1] + self.marker_dis * math.sin(self.heading)*1e-5
            self.marker_flg = False
            hd_marker = plt.plot(marker_lon, marker_lat, 'g+')

        # Draw lines between each pair of points
        for i in range(len(self.waypoints) - 1):
            plt.plot([self.waypoints[i][1], self.waypoints[i+1][1]],
                    [self.waypoints[i][0], self.waypoints[i+1][0]],
                    'r--')

        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.title('Coordinate Plot with Lines')
        plt.grid(True)
        fig = plt.gcf()
        fig.canvas.draw()
        image_np = np.array(fig.canvas.renderer.buffer_rgba())

        bridge = CvBridge()
        ros_image = bridge.cv2_to_imgmsg(image_np, "rgba8")
        self.image_publisher.publish(ros_image)

        if state == 'stop': # TODO: modify the name of state
            plt.scatter([], [], c='r', marker='+', label='cone')
            plt.scatter([], [], c='g', marker='+', label='marker')
            plt.scatter([], [], c='b', marker='o', label='path')
            plt.scatter([], [], c='r', marker='o', label='waypoints')

            plt.legend(framealpha=1, frameon=True)
            plt.savefig(self.map_path)
            rospy.loginfo('Map saved! Go ' + self.map_path)
            plt.close()

    def imu_callback(self, msg):
        self.heading = math.radians(msg.data)

    # save the map or not
    def state_callback(self, msg):
        self.plot_path(msg.data)

    def gps_callback(self, msg):
        rospy.loginfo("current pos: %f, %f", msg.latitude, msg.longitude)
        current_latitude = msg.latitude
        current_longitude = msg.longitude
        self.lat.append(current_latitude)
        self.lon.append(current_longitude)
        self.plot_path()

    def detection_callback(self, msg):
        cone_flg, marker_flg, cone_dis, marker_dis = msg.data.split(',')
        self.cone_flg = 'True' if cone_flg == '1' else 'False'
        self.marker_flg = 'True' if marker_flg == '1' else 'False'
        self.cone_dis = float(cone_dis)
        self.marker_dis = float(marker_dis)
        if self.cone_flg or self.marker_flg:
            rospy.loginfo("cone_flg: %s, marker_flg: %s, cone_dis: %f, marker_dis: %f", self.cone_flg, self.marker_flg, self.cone_dis, self.marker_dis)

        self.plot_path()

if __name__ == '__main__':
    rospy.init_node('record_display')

    waypoints_file = rospy.get_param("record_display/waypoints_file")
    map_file = rospy.get_param("record_display/map_file")
    rospy.loginfo('waypoints_file: '+waypoints_file)
    rospy.loginfo('map_file: '+map_file)

    publisher = recorderNode(waypoints_file, map_file)
    
    rospy.spin()

     
