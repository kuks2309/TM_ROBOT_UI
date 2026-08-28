float64 current_velocity
uint8 amr_task
uint8 amr_direction
uint8 docking_direction
uint8 docking_position_success

# publish and Subscription 100ms
# velocity: unit m/s 
# amr_task: 0-no task, 1-moving, 2-docking_AQ, 3-docking_DP, 4-docking_charge, 5-undocking, 6-avoidance, 7-charging
# amr_direction: 1-forward, 2-backward
# docking_direction: 1-left, 2-right
# docking_position_success: 0-Amr have not yet moved to docking position, 1 - moved to docking position
# AmrStatusForSafety