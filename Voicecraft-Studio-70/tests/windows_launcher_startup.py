"""Windows/Wine integration: exercise the compiled launcher with isolated startup fixtures.

Usage: python windows_launcher_startup.py LAUNCHER_EXE BUNDLED_RUNTIME_DIRECTORY
No personal data, AI models, or application installation are accessed.
"""
import ctypes,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from ctypes import wintypes
user=ctypes.WinDLL('user32',use_last_error=True)
user.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR];user.FindWindowW.restype=wintypes.HWND
user.GetDlgItem.argtypes=[wintypes.HWND,ctypes.c_int];user.GetDlgItem.restype=wintypes.HWND
user.IsWindowEnabled.argtypes=[wintypes.HWND]
user.IsWindowVisible.argtypes=[wintypes.HWND];user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
def wait_for(predicate,seconds=20):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        result=predicate()
        if result:return result
        time.sleep(.05)
    raise AssertionError('Launcher state timed out')
def hwnd():return user.FindWindowW('Voicecraft70Desktop',None)
def visible():return bool(hwnd() and user.IsWindowVisible(hwnd()))
launcher,runtime=map(Path,sys.argv[1:3])
with tempfile.TemporaryDirectory(prefix='voicecraft-startup-qa-') as temporary:
    root=Path(temporary);shutil.copy(launcher,root/'VoiceCraft.exe');shutil.copytree(runtime,root/'runtime')
    scripts=root/'app/scripts';scripts.mkdir(parents=True)
    script=scripts/'desktop.py'
    cases=[('warm launch','import time; time.sleep(2); print("VOICECRAFT_READY",flush=True); time.sleep(3)',False,0),
           ('reopen','import time; time.sleep(2); print("VOICECRAFT_READY",flush=True); time.sleep(3)',False,0),
           ('startup error','import time,sys; time.sleep(2); print("QA startup failure",flush=True); sys.exit(7)',True,7),
           ('required repair','import time; time.sleep(2); print("VOICECRAFT_SETUP_",end="",flush=True); time.sleep(.2); print("REQUIRED",flush=True); time.sleep(2); print("VOICECRAFT_READY",flush=True); time.sleep(2)',True,0)]
    for label,code,should_show,exit_code in cases:
        script.write_text(code,encoding='utf-8')
        process=subprocess.Popen([str(root/'VoiceCraft.exe')],creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            wait_for(hwnd)
            initial=time.monotonic()
            while time.monotonic()-initial<1.5:
                assert not visible(),label+' flashed diagnostics before setup/error'
                time.sleep(.02)
            # Repeated shortcut click during quiet startup must not expose diagnostics.
            user.PostMessageW(hwnd(),0x8005,0,0)
            time.sleep(.1);assert not visible()
            if should_show:
                wait_for(visible)
                # Retry and Open Studio controls are real native controls.
                open_button=user.GetDlgItem(hwnd(),102)
                assert not user.IsWindowEnabled(open_button),'Open Studio enabled before engine readiness'
                if exit_code:
                    assert process.poll() is None,'Failure diagnostics should remain available'
                    script.write_text('import time; time.sleep(2); print("VOICECRAFT_READY",flush=True); time.sleep(2)',encoding='utf-8')
                    user.PostMessageW(hwnd(),0x111,101,0)
                    wait_for(lambda:not visible())
                    while process.poll() is None:
                        assert not visible(),'Retry exposed diagnostics after the repair succeeded'
                        time.sleep(.05)
                else:wait_for(lambda:bool(hwnd()) and not visible())
            else:
                while process.poll() is None:
                    assert not visible(),label+' exposed diagnostics during a warm launch'
                    time.sleep(.05)
            assert process.wait(timeout=15)==0
            wait_for(lambda:not hwnd())
            print('WINDOWS_LAUNCHER_'+label.upper().replace(' ','_')+'_OK',flush=True)
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=15)
print('WINDOWS_STARTUP_REOPEN_REPAIR_FAILURE_VISIBILITY_PASSED',flush=True)
