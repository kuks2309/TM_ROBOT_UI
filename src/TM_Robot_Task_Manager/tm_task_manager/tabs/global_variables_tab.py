from datetime import datetime

from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView

from .base_tab import BaseTab


class GlobalVariablesTab(BaseTab):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def connect_signals(self):
        self.mw.pushButton_readVariable.clicked.connect(self._on_read_variable)
        self.mw.pushButton_writeVariable.clicked.connect(self._on_write_variable)

        self.mw.pushButton_clearHistory.clicked.connect(self._on_clear_variable_history)

    def init_ui(self):
        header = self.mw.tableWidget_variableHistory.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)


    def _on_read_variable(self):
        variable_name = self.mw.comboBox_variableName.currentText().strip()

        if not variable_name:
            self.mw.label_variableStatus.setText("상태: 변수 이름을 입력하세요")
            return

        if not self.gv_manager:
            self.mw.label_variableStatus.setText("상태: Global Variable Manager가 없습니다")
            return

        self.mw.label_variableStatus.setText(f"상태: '{variable_name}' 읽는 중...")
        self._log(f"Global Variable 읽기 (Service): {variable_name}")

        success, result = self.gv_manager.read_variable(variable_name)

        if success:
            self.mw.label_variableStatus.setText(f"상태: 읽기 성공")
            self.mw.lineEdit_variableValue.setText(str(result))
            self._add_variable_history(variable_name, str(result))
            self._log(f"변수 읽기 성공: {result}")
        else:
            self.mw.label_variableStatus.setText(f"상태: 읽기 실패 - {result}")
            self._log(f"변수 읽기 실패: {result}")


    def _on_write_variable(self):
        variable_name = self.mw.comboBox_variableName.currentText().strip()
        variable_value = self.mw.lineEdit_variableValue.text().strip()

        if not variable_name:
            self.mw.label_variableStatus.setText("상태: 변수 이름을 입력하세요")
            return

        if not variable_value:
            self.mw.label_variableStatus.setText("상태: 변수 값을 입력하세요")
            return

        if not self.gv_manager:
            self.mw.label_variableStatus.setText("상태: Global Variable Manager가 없습니다")
            return

        self.mw.label_variableStatus.setText(f"상태: '{variable_name}' 쓰는 중...")
        self._log(f"Global Variable 쓰기 (Script): {variable_name}={variable_value}")

        success, result = self.gv_manager.write_variable(variable_name, variable_value)

        if success:
            self._log(f"변수 쓰기 성공: {variable_name}={variable_value}")

            exit_success = self.gv_manager.send_script_exit(script_id='gv')
            if exit_success:
                self.mw.label_variableStatus.setText(f"상태: 쓰기 성공")
                self._add_variable_history(variable_name, str(variable_value))
                self._log("ScriptExit() 전송 완료")
            else:
                self.mw.label_variableStatus.setText(f"상태: 쓰기 성공, ScriptExit 실패")
                self._log("ScriptExit() 전송 실패")
        else:
            self.mw.label_variableStatus.setText(f"상태: 쓰기 실패 - {result}")
            self._log(f"변수 쓰기 실패: {result}")


    def _add_variable_history(self, variable_name, value):
        timestamp = datetime.now().strftime("%H:%M:%S")

        row_count = self.mw.tableWidget_variableHistory.rowCount()
        self.mw.tableWidget_variableHistory.insertRow(0)

        self.mw.tableWidget_variableHistory.setItem(0, 0, QTableWidgetItem(timestamp))
        self.mw.tableWidget_variableHistory.setItem(0, 1, QTableWidgetItem(variable_name))
        self.mw.tableWidget_variableHistory.setItem(0, 2, QTableWidgetItem(str(value)))

        if row_count >= 100:
            self.mw.tableWidget_variableHistory.removeRow(100)

    def _on_clear_variable_history(self):
        self.mw.tableWidget_variableHistory.setRowCount(0)
        self.mw.label_variableStatus.setText("상태: 히스토리 삭제됨")
