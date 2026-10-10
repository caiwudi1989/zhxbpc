#define UNICODE
#include <windows.h>
int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    MessageBoxW(nullptr, L"原生窗口已就绪", L"PCIDE", MB_OK);
    return 0;
}
