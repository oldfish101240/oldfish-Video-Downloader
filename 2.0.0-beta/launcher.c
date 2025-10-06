#include <stdio.h>
#include <stdlib.h>
#include <windows.h>
#include <string.h>
#include <tlhelp32.h>

// 新增：檢查登錄檔用
#include <shlwapi.h>
#pragma comment(lib, "Shlwapi.lib")

// 檢查檔案是否存在
int file_exists(const char* path) {
    DWORD attributes = GetFileAttributesA(path);
    return (attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY));
}

// 顯示錯誤訊息
void show_error(const char* message) {
    // 轉換為 Unicode 以正確顯示中文
    int len = MultiByteToWideChar(CP_UTF8, 0, message, -1, NULL, 0);
    if (len > 0) {
        wchar_t* wmessage = (wchar_t*)malloc(len * sizeof(wchar_t));
        if (wmessage) {
            MultiByteToWideChar(CP_UTF8, 0, message, -1, wmessage, len);
            MessageBoxW(NULL, wmessage, L"OldFish Video Downloader 啟動器", MB_ICONERROR | MB_OK);
            free(wmessage);
        }
    } else {
        // 如果轉換失敗，使用 ANSI 版本
        MessageBoxA(NULL, message, "OldFish Video Downloader 啟動器", MB_ICONERROR | MB_OK);
    }
}

// 檢查進程是否還在運行
int is_process_running(DWORD process_id) {
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, process_id);
    if (hProcess == NULL) {
        return 0; // 進程不存在或無權限
    }
    
    DWORD exit_code;
    BOOL result = GetExitCodeProcess(hProcess, &exit_code);
    CloseHandle(hProcess);
    
    if (result) {
        return (exit_code == STILL_ACTIVE);
    }
    
    return 0;
}

// 終止進程
void terminate_process(DWORD process_id) {
    HANDLE hProcess = OpenProcess(PROCESS_TERMINATE, FALSE, process_id);
    if (hProcess != NULL) {
        TerminateProcess(hProcess, 0);
        CloseHandle(hProcess);
    }
}

// 查找並終止所有 pythonw.exe 進程
void kill_all_pythonw() {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return;
    }
    
    PROCESSENTRY32 pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32);
    
    if (Process32First(hSnapshot, &pe32)) {
        do {
            if (strcmp(pe32.szExeFile, "pythonw.exe") == 0) {
                terminate_process(pe32.th32ProcessID);
            }
        } while (Process32Next(hSnapshot, &pe32));
    }
    
    CloseHandle(hSnapshot);
}

// 獲取應用程式路徑
void get_app_path(char* path, size_t size) {
    // 嘗試獲取可執行檔案路徑
    if (GetModuleFileNameA(NULL, path, (DWORD)size) == 0) {
        // 如果失敗，使用當前目錄
        GetCurrentDirectoryA((DWORD)size, path);
    } else {
        // 移除檔案名稱，只保留目錄
        char* last_slash = strrchr(path, '\\');
        if (last_slash) {
            *(last_slash + 1) = '\0';
        }
    }
}

// 監控進程
void monitor_process(DWORD target_pid) {
    DWORD current_pid = GetCurrentProcessId();
    
    printf("Start monitoring Python process (PID: %lu)...\n", target_pid);
    
    while (1) {
        Sleep(1000); // 每秒檢查一次
        
        // 檢查目標進程是否還在運行
        if (!is_process_running(target_pid)) {
            printf("Python process ended, launcher exiting.\n");
            break;
        }
        
        // 檢查自己是否被終止
        HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (hSnapshot != INVALID_HANDLE_VALUE) {
            PROCESSENTRY32 pe32;
            pe32.dwSize = sizeof(PROCESSENTRY32);
            
            BOOL found_self = FALSE;
            
            if (Process32First(hSnapshot, &pe32)) {
                do {
                    if (pe32.th32ProcessID == current_pid) {
                        found_self = TRUE;
                        break;
                    }
                } while (Process32Next(hSnapshot, &pe32));
            }
            
            CloseHandle(hSnapshot);
            
            // 如果找不到自己，說明被終止了
            if (!found_self) {
                printf("Launcher terminated, cleaning up Python processes...\n");
                // 終止所有 pythonw.exe 進程
                kill_all_pythonw();
                break;
            }
        }
    }
}

// 檢查 VS Redist (x64) 是否安裝
int is_vsredist_installed() {
    HKEY hKey;
    // Visual Studio 2015-2022 共用同一組 VC++ Redist Key
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        DWORD value = 0, size = sizeof(DWORD);
        if (RegQueryValueExA(hKey, "Installed", NULL, NULL, (LPBYTE)&value, &size) == ERROR_SUCCESS) {
            RegCloseKey(hKey);
            return value == 1;
        }
        RegCloseKey(hKey);
    }
    // 也可檢查常見 DLL 是否存在於 System32
    char sysdir[MAX_PATH];
    GetSystemDirectoryA(sysdir, MAX_PATH);
    char vcruntime_path[MAX_PATH];
    snprintf(vcruntime_path, MAX_PATH, "%s\\vcruntime140.dll", sysdir);
    if (file_exists(vcruntime_path)) return 1;
    return 0;
}

// 檢查 WebView2 是否安裝
int is_webview2_installed() {
    // 本應用使用 Qt WebEngine，不依賴 WebView2；為避免誤判，永遠視為已安裝
    return 1;
}

// 彈窗詢問是否安裝，並自動下載安裝檔
void prompt_and_install(const wchar_t* title, const wchar_t* msg, const wchar_t* url) {
    int res = MessageBoxW(NULL, msg, title, MB_ICONQUESTION | MB_YESNO);
    if (res == IDYES) {
        // 直接用 ShellExecute 開啟下載網址（讓瀏覽器下載）
        ShellExecuteW(NULL, L"open", url, NULL, NULL, SW_SHOWNORMAL);
    }
}

// 使用 GUI 子系統入口（避免彈出主控台視窗）
int APIENTRY wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nCmdShow) {

    // 檢查 VS Redist
    if (!is_vsredist_installed()) {
        const wchar_t* msg = L"您的系統未安裝 Visual C++ Redistributable (x64)！\n\n是否要自動下載安裝？\n\n按 [是] 會開啟官方下載頁面，安裝完成後請重新啟動本程式。";
        prompt_and_install(L"缺少 Visual C++ Redistributable (x64)", msg, L"https://aka.ms/vs/17/release/vc_redist.x64.exe");
        return 1;
    }
    // 本應用採用 Qt WebEngine，不需 WebView2；跳過檢查

    // GUI 模式：避免使用 printf 以免依賴主控台
    
    // 定義路徑
    char pythonw_path[MAX_PATH];
    char script_path[MAX_PATH];
    char app_path[MAX_PATH];
    
    // 獲取應用程式路徑
    get_app_path(app_path, sizeof(app_path));
    // OutputDebugStringA("launcher: resolved application path\n");
    
    // 構建完整路徑（以隱藏主控台的 main.pyw 為入口）
    snprintf(pythonw_path, sizeof(pythonw_path), "%s\\main\\python_embed\\pythonw.exe", app_path);
    snprintf(script_path, sizeof(script_path), "%s\\main\\main.pyw", app_path);
    
    // OutputDebugStringA("launcher: paths ready\n");
    
    // 檢查檔案是否存在
    if (!file_exists(pythonw_path)) {
        // OutputDebugStringA("Error: pythonw.exe not found\n");
        char error_msg[1024];
        snprintf(error_msg, sizeof(error_msg), 
                "錯誤：找不到 pythonw.exe\n\n預期路徑：%s\n\n請確認檔案是否存在。", pythonw_path);
        show_error(error_msg);
        return 1;
    }
    
    if (!file_exists(script_path)) {
        // OutputDebugStringA("Error: main.pyw not found\n");
        char error_msg[1024];
        snprintf(error_msg, sizeof(error_msg), 
                "錯誤：找不到 main.pyw\n\n預期路徑：%s\n\n請確認檔案是否存在。", script_path);
        show_error(error_msg);
        return 1;
    }
    
    // OutputDebugStringA("launcher: starting pythonw\n");
    
    // 構建命令
    char command[2048];
    snprintf(command, sizeof(command), "\"%s\" \"%s\"", pythonw_path, script_path);
    // OutputDebugStringA("launcher: CreateProcessA command built\n");
    
    // 執行命令
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_SHOW;  // 讓 Python 程式顯示視窗
    ZeroMemory(&pi, sizeof(pi));
    
    // 創建進程
    if (!CreateProcessA(
        NULL,           // 應用程式名稱
        command,        // 命令列
        NULL,           // 進程安全屬性
        NULL,           // 執行緒安全屬性
        FALSE,          // 繼承控制碼
        0,              // 創建標誌 - 正常顯示視窗
        NULL,           // 環境變數
        app_path,       // 當前目錄
        &si,            // 啟動資訊
        &pi             // 進程資訊
    )) {
        DWORD error = GetLastError();
        // OutputDebugStringA("launcher: CreateProcessA failed\n");
        
        char error_msg[1024];
        char error_reason[256];
        
        // 提供更詳細的錯誤資訊
        switch (error) {
            case ERROR_FILE_NOT_FOUND:
                strcpy_s(error_reason, sizeof(error_reason), "找不到指定的檔案");
                break;
            case ERROR_PATH_NOT_FOUND:
                strcpy_s(error_reason, sizeof(error_reason), "找不到指定的路徑");
                break;
            case ERROR_ACCESS_DENIED:
                strcpy_s(error_reason, sizeof(error_reason), "存取被拒絕");
                break;
            case ERROR_INVALID_PARAMETER:
                strcpy_s(error_reason, sizeof(error_reason), "無效的參數");
                break;
            case ERROR_BAD_EXE_FORMAT:
                strcpy_s(error_reason, sizeof(error_reason), "可執行檔案格式錯誤");
                break;
            default:
                snprintf(error_reason, sizeof(error_reason), "未知錯誤 (代碼: %lu)", error);
                break;
        }
        
        snprintf(error_msg, sizeof(error_msg), 
                "錯誤：無法啟動程式。\n\n錯誤代碼：%lu\n錯誤原因：%s\n\n請檢查檔案權限和路徑是否正確。", 
                error, error_reason);
        show_error(error_msg);
        
        // 關閉進程和執行緒控制碼
        if (pi.hProcess) CloseHandle(pi.hProcess);
        if (pi.hThread) CloseHandle(pi.hThread);
        
        return 1;
    }
    
    // OutputDebugStringA("launcher: process started\n");
    
    // 等待一下讓 Python 程式有時間啟動
    Sleep(2000);
    
    // 檢查進程是否還在運行
    if (is_process_running(pi.dwProcessId)) {
        // OutputDebugStringA("launcher: python running\n");
    } else {
        // OutputDebugStringA("launcher: python exited early\n");
    }
    // OutputDebugStringA("launcher: waiting again\n");
    
    // 等待一下讓 Python 程式有時間啟動
    Sleep(2000);
    
    // 檢查進程是否還在運行
    if (is_process_running(pi.dwProcessId)) {
        // OutputDebugStringA("launcher: python still running\n");
    } else {
        // OutputDebugStringA("launcher: python exited early (2)\n");
    }
    
    // 關閉進程控制碼（但保留執行緒控制碼用於監控）
    if (pi.hProcess) CloseHandle(pi.hProcess);
    
    // 開始監控進程
    monitor_process(pi.dwProcessId);
    
    // 關閉執行緒控制碼
    if (pi.hThread) CloseHandle(pi.hThread);
    
    // OutputDebugStringA("launcher: exited\n");
    return 0;
}