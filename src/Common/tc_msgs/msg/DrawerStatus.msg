string state            # none, ready, moving, done, jogging, pause, stop, homing, error
string command          # open, close, pause, resume, estop, reset, home
uint8 running_motor     # 1-z, 2-x
float32[] positions
float32[] velocities
bool[] upper_limits
bool[] lower_limits
int32 alarm_code