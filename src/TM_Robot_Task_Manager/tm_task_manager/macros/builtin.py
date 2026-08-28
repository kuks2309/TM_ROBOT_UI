import time

from .base import MacroContext, MacroResult, register


@register(
    name='wait',
    summary='정해진 시간만큼 대기한다. 실행 정지 요청이 오면 즉시 중단한다.',
    category='Control',
    params={
        'duration': {'type': 'int', 'default': 1000, 'min': 0,
                     'description': '대기 시간 (ms)'},
    },
)
def wait(ctx: MacroContext, duration: int = 1000) -> MacroResult:
    duration_s = duration / 1000.0
    ctx.log(f"[WAIT] 대기 시작: {duration}ms ({duration_s}초)")

    elapsed = 0.0
    interval = 0.1
    while elapsed < duration_s:
        if ctx.is_stop_requested:
            ctx.log("[WAIT] 대기 취소됨")
            return MacroResult.failure("대기 취소됨")
        time.sleep(interval)
        elapsed += interval

    ctx.log("[WAIT] 대기 완료")
    return MacroResult.success(f"{duration}ms 대기 완료")


@register(
    name='vision_origin_check',
    summary='학습된 TCP 자세로 복귀해 랜드마크를 재측정하고 6축 편차를 판정한다. '
            '허용범위를 벗어나면 알람 콜백을 발화하고 실패로 끝난다.',
    category='Calibration',
    params={
        'move_to_reference': {'type': 'bool', 'default': True,
                              'description': '학습된 TCP 자세로 이동 후 측정'},
        'velocity': {'type': 'float', 'default': 20.0, 'description': '기준 위치 이동 속도 (%)'},
        'repeat_count': {'type': 'int', 'default': 5, 'min': 1, 'max': 20,
                         'description': '반복 측정 횟수'},
        'outlier_method': {'type': 'choice', 'default': 'iqr',
                           'choices': ['none', 'iqr', '3sigma'],
                           'description': 'Outlier 제거 방법'},
        'wait_after_command': {'type': 'int', 'default': 100, 'step': 100,
                               'description': '명령 후 대기 시간 (ms)'},
    },
    requires=['config:taught_origin'],
    produces=['origin_check_result'],
)
def vision_origin_check(ctx: MacroContext,
                        move_to_reference: bool = True,
                        velocity: float = 20.0,
                        repeat_count: int = 5,
                        outlier_method: str = 'iqr',
                        wait_after_command: int = 100) -> MacroResult:
    service = ctx.vision_origin_check_service
    if not service:
        return MacroResult.failure("기준점 확인 서비스가 없습니다")

    if not service.has_reference():
        return MacroResult.failure(
            "기준점이 학습되지 않았습니다 — 좌표계 탭에서 [기준점 학습]을 먼저 수행하세요"
        )

    if not ctx.vision_manager:
        return MacroResult.failure("VisionManager가 없습니다")

    if ctx.ros_node:
        current_base = getattr(ctx.ros_node, 'current_base_name', 'RobotBase')
        if current_base and current_base != 'RobotBase':
            return MacroResult.failure(
                f"현재 좌표계가 RobotBase가 아닙니다: {current_base} — "
                f"vision_origin_check 는 RobotBase 좌표계에서 실행해야 합니다"
            )

    if move_to_reference:
        tcp_pose = service.get_reference_tcp_pose()
        if tcp_pose is None:
            return MacroResult.failure("학습된 TCP 자세를 읽을 수 없습니다")

        ctx.log(f"기준 위치로 이동: X={tcp_pose[0]:.2f}, Y={tcp_pose[1]:.2f}, Z={tcp_pose[2]:.2f}, "
                f"Rx={tcp_pose[3]:.2f}, Ry={tcp_pose[4]:.2f}, Rz={tcp_pose[5]:.2f}")
        moved, msg = ctx.move_to_position(
            'tcp',
            tcp_pose[0], tcp_pose[1], tcp_pose[2],
            tcp_pose[3], tcp_pose[4], tcp_pose[5],
            velocity
        )
        ctx.log(msg)
        if not moved:
            return MacroResult.failure("기준 위치 이동 실패 — 측정하지 않고 중단합니다")

    measured_pose, _ = ctx.scan_landmark_averaged(
        repeat_count, outlier_method, wait_after_command / 1000.0
    )
    if measured_pose is None:
        return MacroResult.failure("기준점 측정 실패 — 유효 측정 0건")

    result = service.evaluate(measured_pose)
    if result is None:
        return MacroResult.failure("기준점 판정 실패")

    ctx.put('origin_check_result', result)
    ctx.log(result.message)

    if result.passed:
        return MacroResult.success(result.message, origin_check_result=result)

    ctx.log("[알람] 로봇 교정이 필요할 수 있습니다")
    ctx.emit('on_origin_check_alarm', result)
    return MacroResult.failure(result.message, origin_check_result=result)
