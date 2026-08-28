###bottom_agv_st && top_agv_st######
# SAFETY_STATUS_SAFETY 0
# SAFETY_STATUS_WARNING 1
# SAFETY_STATUS_DANGEROUS 2

uint8 agv_safety_st # combine bottom_agv_st and top_agv_st
uint8 bottom_agv_st # Combine 2 navi lidars, 2 front rear ods lidars 
uint8 top_agv_st # combine left, right ods lidars
uint8 navi_lidar_front_st
uint8 navi_lidar_rear_st
uint8 ods_lidar_front_st
uint8 ods_lidar_rear_st
uint8 ods_lidar_left_st
uint8 ods_lidar_right_st
uint8 navi_lidar_front_field
uint8 navi_lidar_rear_field
uint8 ods_lidar_front_field
uint8 ods_lidar_rear_field
uint8 ods_lidar_left_field
uint8 ods_lidar_right_field