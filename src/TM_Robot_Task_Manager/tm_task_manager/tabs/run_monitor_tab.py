"""Recipe 실행/모니터 탭 — 실행 제어 버튼, executor 콜백 기반 진행 표시, 반복 실행 카운터를 담당한다."""
import os
from datetime import datetime

from PyQt5.QtWidgets import QListWidgetItem, QFileDialog, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from .base_tab import BaseTab

VISION_ORIGIN_CHECK_JOB_TYPE = 'vision_origin_check'


class RunMonitorTab(BaseTab):
    """Run/Pause/Stop/Step/반복 실행 제어와 Job 목록 O/X·진행바 표시, 기준점 확인 배치 검증을 담당하는 탭."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

        self._repeat_remaining = 0
        self._repeat_total = 0
        self._repeat_ok = 0
        self._repeat_fail = 0

    def connect_signals(self):
        self.mw.pushButton_run.clicked.connect(self._on_run)
        self.mw.pushButton_pause.clicked.connect(self._on_pause)
        self.mw.pushButton_stop.clicked.connect(self._on_stop)
        self.mw.pushButton_step.clicked.connect(self._on_step)
        self.mw.pushButton_runFrom.clicked.connect(self._on_run_from)
        self.mw.pushButton_runReverse.clicked.connect(self._on_run_reverse)
        self.mw.pushButton_repeatRun.clicked.connect(self._on_repeat_run)

        self.mw.pushButton_clearLog.clicked.connect(self._on_clear_log)
        self.mw.pushButton_saveLog.clicked.connect(self._on_save_log)

        self.mw.tabWidget_main.currentChanged.connect(self._on_tab_changed)

        # Qt 시그널이 아닌 단일 콜백 속성 대입 — 마지막 대입자가 점유하므로 다른 구독자와 공유 불가
        self.job_executor.on_state_changed = self._on_executor_state_changed
        self.job_executor.on_job_started = self._on_executor_job_started
        self.job_executor.on_job_completed = self._on_executor_job_completed

    def init_ui(self):
        self._update_monitor_jobs()

    def _on_tab_changed(self, index: int):
        if self.mw.tabWidget_main.widget(index) == self.mw.tab_runMonitor:
            self._update_monitor_jobs()

    def _update_monitor_jobs(self):
        self._reset_status("대기 — Run 을 누르세요")
        self.mw.listWidget_monitorJobs.clear()
        recipe = self.recipe_manager.current_recipe
        if recipe:
            for job in recipe.jobs:
                display_name = getattr(job, 'caption', '') or job.name
                item_text = f"{job.id}. [{job.type}] {display_name}"
                item = QListWidgetItem(item_text)
                self.mw.listWidget_monitorJobs.addItem(item)


    def _validate_vision_origin_check_placement(self, recipe):
        """recipe_info 의 vision_origin_check 정책(first/last/both)에 맞게 기준점 확인 Job 이 배치됐는지 검증한다.

        Returns:
            (bool, str): (통과 여부, 실패 사유)
        """
        policy = 'none'
        for job in recipe.jobs:
            if job.type == 'recipe_info':
                policy = job.params.get('vision_origin_check', 'none') or 'none'
                break

        if policy == 'none':
            return True, ''

        steps = [job for job in recipe.jobs if job.type != 'recipe_info']
        if not steps:
            return False, "기준점 확인이 필수로 설정되어 있으나 실행할 Job이 없습니다"

        missing = []
        if policy in ('first', 'both') and steps[0].type != VISION_ORIGIN_CHECK_JOB_TYPE:
            missing.append('첫 번째')
        if policy in ('last', 'both') and steps[-1].type != VISION_ORIGIN_CHECK_JOB_TYPE:
            missing.append('마지막')

        if missing:
            return False, (f"기준점 확인이 필수({policy})로 설정되어 있으나 "
                           f"{' · '.join(missing)} Job이 '기준점 확인'이 아닙니다")

        return True, ''

    def _check_vision_origin_placement_or_warn(self, recipe) -> bool:
        is_valid, reason = self._validate_vision_origin_check_placement(recipe)
        if is_valid:
            return True

        self._log(f"[실행 거부] {reason}")
        QMessageBox.warning(
            self.mw,
            "실행 거부 — 기준점 확인 필수",
            f"{reason}\n\n"
            f"해당 위치에 '기준점 확인' Task를 추가하거나,\n"
            f"Recipe 개요(recipe_info)의 vision_origin_check 설정을 변경하세요."
        )
        return False

    def _on_run(self):
        from ..job_executor import ExecutionState

        recipe = self.recipe_manager.current_recipe
        if recipe is None or not recipe.jobs:
            self._log("실행할 Recipe가 없습니다")
            return

        if self.job_executor.state == ExecutionState.PAUSED:
            self.job_executor.resume()
        else:
            if not self._check_vision_origin_placement_or_warn(recipe):
                return

            self._update_monitor_jobs()
            self.job_executor.load_recipe(recipe)
            self.job_executor.run()

    def _on_pause(self):
        self.job_executor.pause()

    def _on_stop(self):
        self._stop_repeat()
        self.job_executor.stop()

    def _on_step(self):
        from ..job_executor import ExecutionState

        recipe = self.recipe_manager.current_recipe
        if recipe is None or not recipe.jobs:
            self._log("실행할 Recipe가 없습니다")
            return

        if self.job_executor.state == ExecutionState.IDLE:
            self._update_monitor_jobs()
            self.job_executor.load_recipe(recipe)

        self.job_executor.step()

    def _on_run_from(self):
        from ..job_executor import ExecutionState

        recipe = self.recipe_manager.current_recipe
        if recipe is None or not recipe.jobs:
            self._log("실행할 Recipe가 없습니다")
            return

        selected_row = self.mw.listWidget_monitorJobs.currentRow()
        if selected_row < 0:
            self._log("실행할 Task를 선택하세요")
            return

        self._update_monitor_jobs()
        self.job_executor.load_recipe(recipe)
        self.job_executor.run_from(selected_row)

    def _on_run_reverse(self):
        recipe = self.recipe_manager.current_recipe
        if recipe is None or not recipe.jobs:
            self._log("실행할 Recipe가 없습니다")
            return

        selected_row = self.mw.listWidget_monitorJobs.currentRow()
        if selected_row < 0:
            self._log("실행할 Task를 선택하세요")
            return

        self._update_monitor_jobs()
        self.job_executor.load_recipe(recipe)
        self.job_executor.run_reverse_from(selected_row)

    def _on_repeat_run(self):
        recipe = self.recipe_manager.current_recipe
        if recipe is None or not recipe.jobs:
            self._log("실행할 Recipe가 없습니다")
            return

        if not self._check_vision_origin_placement_or_warn(recipe):
            return

        self._repeat_total = self.mw.spinBox_repeatCount.value()
        self._repeat_remaining = self._repeat_total
        self._repeat_ok = 0
        self._repeat_fail = 0
        self._log(f"=== 반복 실행 시작 (총 {self._repeat_total}회) ===")
        self._start_repeat_iteration()

    def _start_repeat_iteration(self):
        current = self._repeat_total - self._repeat_remaining + 1
        self._log(f"--- 반복 {current}/{self._repeat_total} 시작 ---")
        self.mw.statusBar().showMessage(
            f"반복 실행 중: {current}/{self._repeat_total}"
        )
        self._update_monitor_jobs()
        self.job_executor.load_recipe(self.recipe_manager.current_recipe)
        self.job_executor.run()

    def _stop_repeat(self):
        if self._repeat_remaining > 0:
            done = self._repeat_total - self._repeat_remaining
            self._log(f"=== 반복 실행 중지 ({done}/{self._repeat_total}회 완료 · "
                      f"성공 {self._repeat_ok} · 실패 {self._repeat_fail}) ===", kind='warn')
            recipe = self.recipe_manager.current_recipe
            total_jobs = len(recipe.jobs) if recipe else 0
            self._set_status(
                f"반복 중지 — {done}/{self._repeat_total}회 "
                f"(성공 {self._repeat_ok} · 실패 {self._repeat_fail})",
                total_jobs, total_jobs, 'fail')
            self._repeat_remaining = 0
            self._repeat_total = 0


    def _repeat_suffix(self) -> str:
        if self._repeat_total <= 0:
            return ""
        current = self._repeat_total - self._repeat_remaining + 1
        current = min(current, self._repeat_total)
        return (f"  ·  반복 {current}/{self._repeat_total}"
                f"  ·  성공 {self._repeat_ok}  ·  실패 {self._repeat_fail}")

    def _set_status(self, text: str, done: int, total: int, state: str = 'run'):
        colors = {'run': '#1565c0', 'ok': '#0b6b2f', 'fail': '#b00020'}
        marks = {'run': '▶', 'ok': '✔', 'fail': '✕'}
        color = colors.get(state, colors['run'])

        head = f"{marks.get(state, '▶')} {done}/{total}" if total else marks.get(state, '▶')
        self.mw.label_currentTask.setText(f"{head}  {text}{self._repeat_suffix()}")
        self.mw.label_currentTask.setStyleSheet(f"color: {color}; font-weight: bold;")

        bar = self.mw.progressBar_task
        bar.setRange(0, total if total else 1)
        bar.setValue(done)
        bar.setFormat(f"%p%  ({done}/{total})" if total else "%p%")
        bar.setStyleSheet(
            "QProgressBar { text-align: center; }"
            f"QProgressBar::chunk {{ background-color: {color}; }}"
        )

    def _reset_status(self, text: str = "대기"):
        if self._repeat_total <= 0:
            self._repeat_ok = 0
            self._repeat_fail = 0
        self._set_status(text, 0, 0, 'run')
        self.mw.progressBar_task.setValue(0)

    def _on_executor_state_changed(self, state):
        from ..job_executor import ExecutionState

        state_text = {
            ExecutionState.IDLE: "대기",
            ExecutionState.RUNNING: "실행 중",
            ExecutionState.PAUSED: "일시정지",
            ExecutionState.STOPPED: "정지됨",
            ExecutionState.ERROR: "오류",
            ExecutionState.COMPLETED: "완료"
        }.get(state, "알 수 없음")
        self.mw.statusBar().showMessage(f"상태: {state_text}")

        is_running = state == ExecutionState.RUNNING
        is_idle = state in (ExecutionState.IDLE, ExecutionState.STOPPED, ExecutionState.COMPLETED)

        self.mw.pushButton_run.setEnabled(not is_running)
        self.mw.pushButton_pause.setEnabled(is_running)
        self.mw.pushButton_stop.setEnabled(not is_idle)
        self.mw.pushButton_step.setEnabled(
            state in (ExecutionState.IDLE, ExecutionState.PAUSED, ExecutionState.STOPPED)
        )
        is_repeating = self._repeat_remaining > 0
        self.mw.pushButton_runFrom.setEnabled(is_idle and not is_repeating)
        self.mw.pushButton_runReverse.setEnabled(is_idle and not is_repeating)
        self.mw.pushButton_repeatRun.setEnabled(is_idle and not is_repeating)
        self.mw.spinBox_repeatCount.setEnabled(is_idle and not is_repeating)

        if state == ExecutionState.ERROR and self._repeat_remaining > 0:
            self._repeat_fail += 1
            self._stop_repeat()

        if state == ExecutionState.COMPLETED:
            if self._repeat_remaining > 0:
                self._repeat_ok += 1
                self._repeat_remaining -= 1
                if self._repeat_remaining > 0:
                    # executor 콜백 스택 안에서 바로 재실행하지 않고 이벤트 루프 경유로 다음 반복을 예약
                    QTimer.singleShot(500, self._start_repeat_iteration)
                    return
                else:
                    self._log(f"=== 반복 실행 완료 (총 {self._repeat_total}회 · "
                              f"성공 {self._repeat_ok} · 실패 {self._repeat_fail}) ===",
                              kind='ok' if self._repeat_fail == 0 else 'fail')
                    recipe = self.recipe_manager.current_recipe
                    total_jobs = len(recipe.jobs) if recipe else 0
                    self._set_status(
                        f"반복 {self._repeat_total}회 완료 "
                        f"(성공 {self._repeat_ok} · 실패 {self._repeat_fail})",
                        total_jobs, total_jobs,
                        'ok' if self._repeat_fail == 0 else 'fail')
                    self._repeat_total = 0
                    self.mw.pushButton_runFrom.setEnabled(True)
                    self.mw.pushButton_runReverse.setEnabled(True)
                    self.mw.pushButton_repeatRun.setEnabled(True)
                    self.mw.spinBox_repeatCount.setEnabled(True)

            # 동적 정밀도 테스트 연계 — Recipe 완료를 매니저에 통지해 다음 회차를 이어가게 한다
            if (self.mw.precision_test_manager.is_running and
                self.mw.precision_test_manager.test_mode == 'dynamic'):
                self.mw.precision_test_manager.on_recipe_completed()

    def _on_executor_job_started(self, index: int, job):
        self.mw.listWidget_monitorJobs.setCurrentRow(index)
        recipe = self.recipe_manager.current_recipe
        total = len(recipe.jobs) if recipe else 0
        caption = (getattr(job, 'caption', '') or getattr(job, 'name', '') or job.type)
        self._set_status(caption, index, total, 'run')

    def _on_executor_job_completed(self, index: int, job, success: bool):
        item = self.mw.listWidget_monitorJobs.item(index)
        if item:
            status = "O" if success else "X"
            display_name = getattr(job, 'caption', '') or job.name
            item.setText(f"{job.id}. [{job.type}] {display_name} [{status}]")
            if not success:
                item.setBackground(QColor(255, 200, 200))

        recipe = self.recipe_manager.current_recipe
        total = len(recipe.jobs) if recipe else 0
        caption = (getattr(job, 'caption', '') or getattr(job, 'name', '') or job.type)
        self._set_status(caption, min(index + 1, total) if total else 0, total,
                         'ok' if success else 'fail')


    def _on_clear_log(self):
        self.mw.textEdit_log.clear()

    def _on_save_log(self):
        log_text = self.mw.textEdit_log.toPlainText()
        if not log_text.strip():
            self._log("저장할 로그가 없습니다")
            return

        default_name = os.path.join(
            os.path.expanduser("~"),
            f"tm_run_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self.mw, "로그 저장", default_name,
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(log_text)
            self._log(f"로그 저장 완료: {filename}")
        except OSError as e:
            self._log(f"로그 저장 실패: {e}")
