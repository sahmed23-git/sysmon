import subprocess
import threading
import time
import webbrowser
import sys
import os

os.chdir(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__))

def run_server():
    subprocess.Popen([sys.executable if not getattr(sys, 'frozen', False) else 'python', 'app.py'])

def run_agent():
    time.sleep(3)
    subprocess.Popen([sys.executable if not getattr(sys, 'frozen', False) else 'python', 'agent.py'])

def open_browser():
    time.sleep(5)
    webbrowser.open('http://localhost:5000')

threading.Thread(target=run_server).start()
threading.Thread(target=run_agent).start()
threading.Thread(target=open_browser).start()