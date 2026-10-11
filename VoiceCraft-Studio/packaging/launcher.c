#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <wchar.h>
#define WM_LOG (WM_APP+1)
#define WM_READY (WM_APP+2)
#define WM_DONE (WM_APP+3)
#define WM_TRAY (WM_APP+4)
#define WM_OPEN (WM_APP+5)
static HWND window,logbox,status;
static HANDLE job,child;
static WCHAR base[MAX_PATH];
static BOOL ready=FALSE,busy=FALSE,smoke=FALSE;
static NOTIFYICONDATAW tray;
static void append(const WCHAR *s){int n=GetWindowTextLengthW(logbox);SendMessageW(logbox,EM_SETSEL,n,n);SendMessageW(logbox,EM_REPLACESEL,FALSE,(LPARAM)s);SendMessageW(logbox,EM_SCROLLCARET,0,0);}
static void open_browser(void){ShellExecuteW(NULL,L"open",L"http://127.0.0.1:8790",NULL,NULL,SW_SHOWNORMAL);}
static DWORD WINAPI worker(LPVOID ignored){
    (void)ignored;HANDLE readpipe,writepipe;SECURITY_ATTRIBUTES sa={sizeof(sa),NULL,TRUE};
    if(!CreatePipe(&readpipe,&writepipe,&sa,0)){PostMessageW(window,WM_DONE,1,0);return 1;}
    SetHandleInformation(readpipe,HANDLE_FLAG_INHERIT,0);
    WCHAR command[MAX_PATH*4],python[MAX_PATH*2];
    swprintf(python,sizeof(python)/sizeof(WCHAR),L"%ls\\runtime\\python.exe",base);
    swprintf(command,sizeof(command)/sizeof(WCHAR),L"\"%ls\" -u -X utf8 \"%ls\\app\\scripts\\desktop.py\"%ls",python,base,smoke?L" --check-runtime":L"");
    STARTUPINFOW si={0};si.cb=sizeof(si);si.dwFlags=STARTF_USESTDHANDLES;si.hStdOutput=writepipe;si.hStdError=writepipe;si.hStdInput=GetStdHandle(STD_INPUT_HANDLE);PROCESS_INFORMATION pi={0};
    BOOL ok=CreateProcessW(python,command,NULL,NULL,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,NULL,base,&si,&pi);
    CloseHandle(writepipe);
    if(!ok){CloseHandle(readpipe);PostMessageW(window,WM_DONE,GetLastError(),0);return 1;}
    child=pi.hProcess;
    if(!AssignProcessToJobObject(job,child)){TerminateProcess(child,1);CloseHandle(pi.hThread);CloseHandle(child);child=NULL;CloseHandle(readpipe);PostMessageW(window,WM_DONE,1,0);return 1;}
    ResumeThread(pi.hThread);CloseHandle(pi.hThread);
    char chunk[4097],tail[8192]={0};DWORD count;
    while(ReadFile(readpipe,chunk,4096,&count,NULL)&&count){
        chunk[count]=0;size_t old=strlen(tail);if(old+count>=sizeof(tail)){memmove(tail,tail+old/2,old-old/2+1);old=strlen(tail);}strncat(tail,chunk,sizeof(tail)-old-1);
        if(strstr(tail,"VOICECRAFT_READY"))PostMessageW(window,WM_READY,0,0);
        int len=MultiByteToWideChar(CP_UTF8,0,chunk,(int)count,NULL,0);WCHAR *text=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,(len+1)*sizeof(WCHAR));
        if(text){MultiByteToWideChar(CP_UTF8,0,chunk,(int)count,text,len);PostMessageW(window,WM_LOG,0,(LPARAM)text);}
    }
    CloseHandle(readpipe);WaitForSingleObject(child,INFINITE);DWORD code=1;GetExitCodeProcess(child,&code);CloseHandle(child);child=NULL;PostMessageW(window,WM_DONE,code,0);return code;
}
static void start(void){busy=TRUE;ready=FALSE;SetWindowTextW(status,L"Preparing VoiceCraft. First setup downloads engine packages and models.");HANDLE thread=CreateThread(NULL,0,worker,NULL,0,NULL);if(thread)CloseHandle(thread);else{busy=FALSE;SetWindowTextW(status,L"Cannot start setup. Close and reopen VoiceCraft.");}}
static int CALLBACK browse_callback(HWND hwnd,UINT message,LPARAM param,LPARAM data){
    (void)param;
    if(message==BFFM_INITIALIZED&&data){SendMessageW(hwnd,BFFM_SETSELECTIONW,TRUE,data);}
    return 0;
}
static void choose_storage(void){
    WCHAR path[MAX_PATH],local[MAX_PATH],target[MAX_PATH*2],initial[MAX_PATH]={0};
    if(SUCCEEDED(SHGetFolderPathW(NULL,CSIDL_LOCAL_APPDATA,NULL,0,local))){
        swprintf(target,sizeof(target)/sizeof(WCHAR),L"%ls\\VoiceCraft-Studio\\storage.txt",local);
        HANDLE file=CreateFileW(target,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
        if(file!=INVALID_HANDLE_VALUE){char text[MAX_PATH*4]={0};DWORD count=0;if(ReadFile(file,text,sizeof(text)-1,&count,NULL)&&count){MultiByteToWideChar(CP_UTF8,0,text,-1,initial,MAX_PATH);}CloseHandle(file);}
        if(!initial[0]){swprintf(initial,MAX_PATH,L"%ls\\VoiceCraft-Studio\\data",local);}
    }
    BROWSEINFOW browse={0};browse.lpszTitle=L"Choose VoiceCraft storage. Existing data stays in its current folder; restart VoiceCraft to use the new folder.";browse.ulFlags=BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE;browse.lpfn=browse_callback;browse.lParam=(LPARAM)initial;
    CoInitialize(NULL);LPITEMIDLIST item=SHBrowseForFolderW(&browse);
    if(item&&SHGetPathFromIDListW(item,path)&&SUCCEEDED(SHGetFolderPathW(NULL,CSIDL_LOCAL_APPDATA,NULL,0,local))){
        size_t base_length=wcslen(base);
        if(!_wcsnicmp(path,base,base_length)&&(path[base_length]==0||path[base_length]==L'\\')){
            MessageBoxW(NULL,L"Choose a storage folder outside the application installation folder so uninstalling cannot remove your recordings.",L"VoiceCraft Studio",MB_OK|MB_ICONINFORMATION);
            CoTaskMemFree(item);CoUninitialize();return;
        }
        swprintf(target,sizeof(target)/sizeof(WCHAR),L"%ls\\VoiceCraft-Studio",local);CreateDirectoryW(target,NULL);wcscat(target,L"\\storage.txt");
        HANDLE file=CreateFileW(target,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
        if(file!=INVALID_HANDLE_VALUE){char text[MAX_PATH*4];int len=WideCharToMultiByte(CP_UTF8,0,path,-1,text,sizeof(text),NULL,NULL);DWORD written;WriteFile(file,text,len-1,&written,NULL);CloseHandle(file);MessageBoxW(NULL,L"Storage selection saved. Exit VoiceCraft using its tray icon, then reopen your desktop shortcut. Existing recordings were not moved or deleted.",L"VoiceCraft Studio",MB_OK);}
    }
    if(item){CoTaskMemFree(item);}
    CoUninitialize();
}
static LRESULT CALLBACK proc(HWND h,UINT msg,WPARAM w,LPARAM l){
    switch(msg){
    case WM_CREATE:
        status=CreateWindowW(L"STATIC",L"Your voice. Your stories.",WS_CHILD|WS_VISIBLE,20,18,720,45,h,NULL,NULL,NULL);
        logbox=CreateWindowExW(WS_EX_CLIENTEDGE,L"EDIT",L"",WS_CHILD|WS_VISIBLE|WS_VSCROLL|ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL,20,68,720,310,h,NULL,NULL,NULL);
        SendMessageW(logbox,EM_SETLIMITTEXT,1000000,0);
        CreateWindowW(L"BUTTON",L"Retry setup",WS_CHILD|WS_VISIBLE,20,395,140,32,h,(HMENU)101,NULL,NULL);
        CreateWindowW(L"BUTTON",L"Open Studio",WS_CHILD|WS_VISIBLE,175,395,140,32,h,(HMENU)102,NULL,NULL);return 0;
    case WM_LOG:append((WCHAR*)l);HeapFree(GetProcessHeap(),0,(void*)l);return 0;
    case WM_READY:
        if(!ready){ready=TRUE;SetWindowTextW(status,L"VoiceCraft is running. Use the tray icon to reopen or exit.");ZeroMemory(&tray,sizeof(tray));tray.cbSize=sizeof(tray);tray.hWnd=h;tray.uID=1;tray.uFlags=NIF_MESSAGE|NIF_ICON|NIF_TIP;tray.uCallbackMessage=WM_TRAY;tray.hIcon=LoadIconW(GetModuleHandleW(NULL),MAKEINTRESOURCEW(1));wcscpy(tray.szTip,L"VoiceCraft Studio");Shell_NotifyIconW(NIM_ADD,&tray);ShowWindow(h,SW_HIDE);}return 0;
    case WM_DONE:
        busy=FALSE;if(smoke){PostQuitMessage((int)w);return 0;}
        if(w){WCHAR message[160];swprintf(message,160,L"Setup stopped (code %lu). Read the details below, then Retry setup.",(unsigned long)w);SetWindowTextW(status,message);ShowWindow(h,SW_SHOW);SetForegroundWindow(h);}else{DestroyWindow(h);}return 0;
    case WM_COMMAND:if(LOWORD(w)==101&&!busy)start();if(LOWORD(w)==102&&ready)open_browser();if(LOWORD(w)==201)open_browser();if(LOWORD(w)==202)DestroyWindow(h);return 0;
    case WM_OPEN:if(ready)open_browser();else{ShowWindow(h,SW_SHOW);SetForegroundWindow(h);}return 0;
    case WM_TRAY:
        if(l==WM_LBUTTONDBLCLK){open_browser();}
        if(l==WM_RBUTTONUP){HMENU menu=CreatePopupMenu();AppendMenuW(menu,MF_STRING,201,L"Open VoiceCraft");AppendMenuW(menu,MF_STRING,202,L"Exit VoiceCraft");POINT p;GetCursorPos(&p);SetForegroundWindow(h);TrackPopupMenu(menu,TPM_RIGHTBUTTON,p.x,p.y,0,h,NULL);DestroyMenu(menu);}return 0;
    case WM_CLOSE:if(ready){ShowWindow(h,SW_HIDE);return 0;}if(busy&&MessageBoxW(h,L"Stop setup? Downloads may need to resume next time. Existing recordings are preserved.",L"VoiceCraft Studio",MB_YESNO|MB_ICONQUESTION)!=IDYES)return 0;DestroyWindow(h);return 0;
    case WM_DESTROY:Shell_NotifyIconW(NIM_DELETE,&tray);if(job)CloseHandle(job);PostQuitMessage(0);return 0;
    }return DefWindowProcW(h,msg,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR args,int show){
    (void)previous;GetModuleFileNameW(NULL,base,MAX_PATH);WCHAR *slash=wcsrchr(base,L'\\');if(slash)*slash=0;
    if(wcsstr(args,L"--choose-storage")){choose_storage();return 0;}smoke=wcsstr(args,L"--check-runtime")!=NULL;
    HANDLE mutex=CreateMutexW(NULL,FALSE,L"Local\\VoiceCraftStudioDesktop");if(!smoke&&GetLastError()==ERROR_ALREADY_EXISTS){HWND existing=FindWindowW(L"VoiceCraftDesktop",NULL);if(existing)PostMessageW(existing,WM_OPEN,0,0);CloseHandle(mutex);return 0;}
    job=CreateJobObjectW(NULL,NULL);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={0};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits));
    WNDCLASSW cls={0};cls.lpfnWndProc=proc;cls.hInstance=instance;cls.lpszClassName=L"VoiceCraftDesktop";cls.hCursor=LoadCursorW(NULL,IDC_ARROW);cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);cls.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(1));RegisterClassW(&cls);
    window=CreateWindowW(cls.lpszClassName,L"VoiceCraft Studio — Setup & Diagnostics",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,780,490,NULL,NULL,instance,NULL);ShowWindow(window,smoke?SW_HIDE:show);start();MSG msg;while(GetMessageW(&msg,NULL,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}CloseHandle(mutex);return (int)msg.wParam;
}
