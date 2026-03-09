import subprocess
import sys
import time

processes = []

try:
    processes.append(subprocess.Popen([sys.executable, "brunch_back.py"]))
    time.sleep(1.5)
    processes.append(subprocess.Popen([sys.executable, "brunch_owner.py"]))
    processes.append(subprocess.Popen([sys.executable, "brunch_user.py"]))

    print("已啟動 backend.py / admin_gui.py / client_gui.py")
    print("關閉本視窗不會自動關掉其他程式。")
except Exception as e:
    print("啟動失敗：", e)