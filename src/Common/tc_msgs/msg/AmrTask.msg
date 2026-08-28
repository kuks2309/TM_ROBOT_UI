###########################################################################################################################################
# Messages ACS → AMR order

# 1st -> send pio_id, task, cs, current_task_count, total_task_count
# 2nd -> check feedback_pio_id == pio_id // Runing Task
# 3rd -> result init value == 0 / 1: SUCCESS, 2: ERROR , 3: RUNNING or BUSY
# 4th -> if ERROR check error_code

# pio_id: equip code(2) + pio_num(1) + equip_num(3)
# task: AQ, DP, CHG, CHG_STOP,
# cs (CS0, CS1, CS2) 0: SPARE, 1: SKT_STAGE_1, 2: SKT_STAGE_2, 3: SKT_STAGE_3, 4: SKT_STAGE_4, 5: SPARE, 6: CALS_LD, 7: CALS_ULD
# total_task_count: total task (total_task_count >= current_task_count)
# current_task_count: current task
# if current_task_count < total_task_count: PIO_CONT is ON.
# if current_task_count = total_task_count, finish the last task and turn OFF PIO_CONT
###########################################################################################################################################

string pio_id
string task
int32 cs
int32 current_task_count
int32 total_task_count

string feedback_pio_id
int32 result
int32 error_code

