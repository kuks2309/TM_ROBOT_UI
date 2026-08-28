float64 pos_x
float64 pos_y
float64 pos_z
float64 pos_rx
float64 pos_ry
float64 pos_rz

float64 joint_one
float64 joint_two
float64 joint_three
float64 joint_four
float64 joint_five
float64 joint_six

int32 cobot_state       # init 0 / idle 1 / stop 2 / move 3 / reset 4 / homing 5 / scan 6 / pause 7 / error 8 / job done 9
int32 cobot_command     # AQ 3 / DP 4 / SCAN 7 / PAUSE 8 / RESUME 9 / STOP 10 / GO HOME 11 / JOG 12