#include <stdint.h>
#include <string.h>
#include <windows.h>

#define EXPORT __declspec(dllexport)
static int active = 0;

EXPORT uint32_t pcide_abi_version(void) { return 1; }
EXPORT int pcide_init(void) { active = 1; return 0; }
EXPORT const char* pcide_call(const char* request) {
    if (!active || !request) return "{\"ok\":false,\"error\":\"NOT_INITIALIZED\"}";
    if (strstr(request, "crash")) { TerminateProcess(GetCurrentProcess(), 71); }
    if (strstr(request, "sleep")) { Sleep(10000); }
    return "{\"ok\":true,\"value\":42,\"abi\":1}";
}
EXPORT void pcide_shutdown(void) { active = 0; }
